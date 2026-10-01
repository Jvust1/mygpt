"""Transport-independent request engine for fixed samples and explicit local inputs.

Imported content remains USER_SUPPLIED_UNVERIFIED. No provider can be chosen
through this interface. Cooperative cancellation is not an OS process sandbox.
"""
from __future__ import annotations
import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata as metadata
import json
import math
import secrets
import threading
import time
from typing import Annotated, Awaitable, Callable, Literal
from pydantic import Field, ValidationError
from .adapters import EvidenceText, run_fixture_test_model
from .core import (Brain, Contract, Identifier, ReaderStudyContext, ImportedReaderContext,
                   Sequence, StudyEvent, checked_now, parse_context, utc_now)
from .host_fixtures import build_catalogue

MAX_REQUESTS = 128


class LocalServiceError(RuntimeError):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


class LocalExplainRequest(Contract):
    schema_version: Literal["mygpt.local-explain.v1"] = "mygpt.local-explain.v1"
    scope: Literal["SYNTHETIC_FIXED_REPLAY", "LOCAL_UNVERIFIED_SELECTION"]
    request_id: Identifier
    revision: Sequence
    entry_id: Identifier
    mode: Literal["preview", "learn", "review", "practice"]
    source_ref: Annotated[str, Field(min_length=1, max_length=1024)]
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    selection_expires_at_ms: Annotated[int, Field(strict=True, ge=1, le=2**53 - 1)]


class LocalCancelRequest(Contract):
    schema_version: Literal["mygpt.local-cancel.v1"] = "mygpt.local-cancel.v1"
    request_id: Identifier


class LocalRevokeRequest(Contract):
    schema_version: Literal["mygpt.local-revoke.v1"] = "mygpt.local-revoke.v1"


@dataclass
class _RequestRecord:
    fingerprint: str
    cancel: threading.Event = field(default_factory=threading.Event)
    status: str = "running"
    response: dict | None = None
    error_code: str | None = None
    error_status: int = 409
    captured_at: datetime | None = None
    expires_at: datetime | None = None
    mono_end: float | None = None


Responder = Callable[[Brain, EvidenceText, str, str, datetime], Awaitable[object]]


async def _default_responder(brain: Brain, evidence: EvidenceText, question: str,
                             fixture_text: str, now: datetime):
    return await run_fixture_test_model(brain, evidence, question, fixture_text, now=now)


class LocalBrainEngine:
    """Bounded, single-authorization in-memory synthetic request engine."""

    def __init__(self, *, catalogue: dict | None = None, clock: Callable[[], datetime] = utc_now,
                 monotonic: Callable[[], float] = time.monotonic,
                 authorization_seconds: int = 1800, context_seconds: int = 120,
                 demo_delay_ms: int = 0, responder: Responder = _default_responder,
                 request_timeout_seconds: float = 8.0, enable_selection_intake: bool = False) -> None:
        if (type(request_timeout_seconds) not in (int, float)
                or not math.isfinite(request_timeout_seconds)
                or not 0 < request_timeout_seconds <= 30):
            raise ValueError("request_timeout_seconds must be in (0, 30]")
        if any(type(x) is not int for x in (authorization_seconds, context_seconds, demo_delay_ms)):
            raise ValueError("integer configuration required")
        if not 60 <= authorization_seconds <= 3600:
            raise ValueError("authorization_seconds must be 60..3600")
        if not 1 <= context_seconds <= 300:
            raise ValueError("context_seconds must be 1..300")
        if not 0 <= demo_delay_ms <= 5000:
            raise ValueError("demo_delay_ms must be 0..5000")
        data = build_catalogue() if catalogue is None else deepcopy(catalogue)
        if (data.get("schema") != "mygpt.host-replay.v1"
                or data.get("scope") != "SYNTHETIC_FIXED_REPLAY"
                or data.get("live_book_connected") is not False or data.get("model_calls") != 0):
            raise ValueError("only the fixed synthetic catalogue is accepted")
        self._entries = {entry["id"]: entry for entry in data.get("entries", [])}
        if not self._entries or len(self._entries) != len(data.get("entries", [])) or len(self._entries) > 32:
            raise ValueError("invalid synthetic catalogue")
        self._clock, self._monotonic = clock, monotonic
        self._context_seconds = context_seconds
        self._demo_delay_ms = demo_delay_ms
        from .selection_store import SelectionStore
        if type(enable_selection_intake) is not bool:
            raise ValueError("enable_selection_intake must be bool")
        self._selection_store = SelectionStore(clock=clock, monotonic=monotonic) if enable_selection_intake else None
        self._request_timeout = request_timeout_seconds
        self._responder = responder
        self._test_model = responder is _default_responder
        self._responder_kind = "PYDANTIC_AI_TESTMODEL" if self._test_model else "INJECTED_TEST_FIXTURE"
        if self._test_model:
            try:
                version = metadata.version("pydantic-ai-slim")
            except metadata.PackageNotFoundError:
                raise RuntimeError("pydantic-ai-slim==2.46.0 is required for the local TestModel service") from None
            if version != "2.46.0":
                raise RuntimeError("local TestModel service requires pydantic-ai-slim==2.46.0")
        self._created_wall = checked_now(clock())
        self._created_mono = monotonic()
        self._auth_seconds = authorization_seconds
        if type(self._created_mono) not in (int, float) or not math.isfinite(self._created_mono) or self._created_mono < 0:
            raise ValueError("invalid monotonic clock")
        self._service_id = "svc-" + secrets.token_hex(12)
        self._lock = threading.RLock()
        self._revoked = False
        self._requests: dict[str, _RequestRecord] = {}
        self._cancelled_ids: set[str] = set()
        self._metrics = {"requests_started": 0, "requests_completed": 0,
                         "cancel_requests": 0, "requests_cancelled": 0,
                         "request_conflicts": 0}

    def _now(self) -> datetime:
        return checked_now(self._clock())

    def _authorized(self) -> bool:
        mono = self._monotonic()
        return (not self._revoked and isinstance(mono, (int, float))
                and self._created_mono <= mono < self._created_mono + self._auth_seconds)

    def require_authorized(self) -> None:
        with self._lock:
            if not self._authorized():
                raise LocalServiceError("authorization_revoked_or_expired", 403)

    def status(self) -> dict:
        with self._lock:
            authorized = self._authorized()
            metrics = dict(self._metrics)
            return {"schema_version": "mygpt.local-status.v1",
                    "scope": "SYNTHETIC_LOCAL_PYTHON_BRAIN",
                    "authorized": authorized, "revoked": self._revoked,
                    "live_book_connected": False, "test_model": self._test_model,
                    "responder_kind": self._responder_kind,
                    "paid_model_calls": 0, "source_text_persisted": False,
                    "service_id": self._service_id,
                    "selection_intake_enabled": self._selection_store is not None,
                    "imports_active": self._selection_store.count() if self._selection_store else 0,
                    "authorization_expires_at": (self._created_wall + timedelta(seconds=self._auth_seconds)).isoformat(),
                    **metrics}

    @staticmethod
    def _fingerprint(request: LocalExplainRequest) -> str:
        raw = json.dumps(request.model_dump(mode="json"), ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _prepare(self, request: LocalExplainRequest) -> tuple[_RequestRecord, bool]:
        self.require_authorized()
        fingerprint = self._fingerprint(request)
        with self._lock:
            self.require_authorized()
            if request.request_id in self._cancelled_ids:
                raise LocalServiceError("request_cancelled", 409)
            existing = self._requests.get(request.request_id)
            if existing:
                if existing.fingerprint != fingerprint:
                    self._metrics["request_conflicts"] += 1
                    raise LocalServiceError("request_id_conflict", 409)
                if existing.status == "completed" and existing.response is not None:
                    self._check_record(existing)
                    return existing, True
                if existing.status in ("failed", "expired"):
                    raise LocalServiceError(existing.error_code or "request_failed", existing.error_status)
                if existing.status == "cancelled":
                    raise LocalServiceError("request_cancelled", 409)
                raise LocalServiceError("request_in_progress", 409)
            if len(self._requests) >= MAX_REQUESTS:
                raise LocalServiceError("request_capacity_exceeded", 429)
            record = _RequestRecord(fingerprint=fingerprint)
            self._requests[request.request_id] = record
            self._metrics["requests_started"] += 1
            return record, False

    def cancel(self, request_id: str) -> dict:
        try:
            LocalCancelRequest(request_id=request_id)
        except ValidationError:
            raise LocalServiceError("invalid_cancel_request", 400) from None
        self.require_authorized()
        with self._lock:
            self._metrics["cancel_requests"] += 1
            record = self._requests.get(request_id)
            if record is None:
                if len(self._cancelled_ids) >= MAX_REQUESTS and request_id not in self._cancelled_ids:
                    raise LocalServiceError("cancel_capacity_exceeded", 429)
                self._cancelled_ids.add(request_id)
                return {"schema_version": "mygpt.local-cancel-result.v1", "status": "unknown_request"}
            if record.status == "completed":
                return {"schema_version": "mygpt.local-cancel-result.v1", "status": "already_settled"}
            record.cancel.set()
            if record.status != "cancelled":
                record.status = "cancelled"
                self._metrics["requests_cancelled"] += 1
            return {"schema_version": "mygpt.local-cancel-result.v1", "status": "cancelled"}

    def revoke(self) -> dict:
        with self._lock:
            already = self._revoked
            self._revoked = True
            if self._selection_store is not None:
                self._selection_store.clear()
            for record in self._requests.values():
                record.response = None
                if record.status == "running":
                    record.cancel.set()
                    record.status = "cancelled"
                    self._metrics["requests_cancelled"] += 1
            return {"schema_version": "mygpt.local-revoke-result.v1",
                    "status": "already_revoked" if already else "revoked"}

    def _fresh_evidence(self, request: LocalExplainRequest, now: datetime) -> tuple[EvidenceText, str]:
        if request.scope == "LOCAL_UNVERIFIED_SELECTION":
            if self._selection_store is None:
                raise LocalServiceError("selection_intake_disabled", 403)
            try:
                entry = self._selection_store.get(request.entry_id)
            except ValueError:
                raise LocalServiceError("import_missing_or_expired", 409) from None
        else:
            entry = self._entries.get(request.entry_id)
        if entry is None:
            raise LocalServiceError("unknown_entry", 404)
        if (entry.get("source_ref") != request.source_ref
                or entry.get("context", {}).get("source_sha256") != request.source_sha256):
            raise LocalServiceError("source_identity_mismatch", 409)
        now_ms = int(now.timestamp() * 1000)
        if request.selection_expires_at_ms <= now_ms or request.selection_expires_at_ms > now_ms + 300_000:
            raise LocalServiceError("selection_expired_or_unbounded", 409)
        base = parse_context(entry["context"])
        if not isinstance(base, ReaderStudyContext):
            raise LocalServiceError("unsupported_context_protocol", 409)
        client_end = datetime.fromtimestamp(request.selection_expires_at_ms / 1000, timezone.utc)
        expires = min(now + timedelta(seconds=self._context_seconds), client_end)
        if expires <= now:
            raise LocalServiceError("selection_expired_or_unbounded", 409)
        if isinstance(base, ImportedReaderContext):
            if request.scope != "LOCAL_UNVERIFIED_SELECTION":
                raise LocalServiceError("source_scope_mismatch", 409)
            expires = min(expires, base.expires_at)
        elif request.scope != "SYNTHETIC_FIXED_REPLAY":
            raise LocalServiceError("source_scope_mismatch", 409)
        context = base.model_copy(update={"session_id": self._service_id, "mode": request.mode,
                                          "captured_at": now, "expires_at": expires})
        # Re-validate after model_copy; do not rely on copy/update bypass semantics.
        context = parse_context(context.model_dump(mode="json"))
        if context.reference != request.source_ref:
            raise LocalServiceError("source_reference_changed", 409)
        evidence = EvidenceText(context=context, text=entry["evidence_text"])
        return evidence, entry["fixture_reply"]

    def import_selection(self, raw: bytes) -> dict:
        with self._lock:
            self.require_authorized()
            if self._selection_store is None:
                raise LocalServiceError("selection_intake_disabled", 403)
            try:
                entry = self._selection_store.add(raw)
            except ValueError as error:
                raise LocalServiceError(str(error), 400) from None
            return {"schema_version": "mygpt.selection-intake-result.v1",
                    "trust": "USER_SUPPLIED_UNVERIFIED", "live_book_connected": False,
                    "entry": entry}

    def _check_record(self, record: _RequestRecord) -> None:
        # Called before dispatch, during cooperative waits, after await, at commit
        # and on cache reads. Browser timers never determine server freshness.
        if record.cancel.is_set():
            raise LocalServiceError("request_cancelled", 409)
        self.require_authorized()
        wall, mono = self._now(), self._monotonic()
        if (record.expires_at is None or record.mono_end is None
                or type(mono) not in (int, float) or not math.isfinite(mono)
                or wall < record.captured_at or wall >= record.expires_at
                or mono < self._created_mono or mono >= record.mono_end):
            with self._lock:
                record.response = None
                record.status, record.error_code, record.error_status = "expired", "selection_expired", 409
            raise LocalServiceError("selection_expired", 409)

    async def _await_responder(self, record, brain, evidence, text, now):
        # Trusted cooperative TestModel only. This is not a killable sandbox for
        # native blocking code or a responder that deliberately swallows cancel.
        question = ("解释当前明确选择的本机导入片段；来源尚未核验。"
                    if isinstance(evidence.context, ImportedReaderContext) else "解释当前明确选择的合成片段。")
        task = asyncio.create_task(self._responder(brain, evidence, question, text, now))
        deadline = asyncio.get_running_loop().time() + self._request_timeout
        try:
            while not task.done():
                self._check_record(record)
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise LocalServiceError("request_timeout", 504)
                await asyncio.wait({task}, timeout=min(0.02, remaining))
            self._check_record(record)
            if task.cancelled():
                raise LocalServiceError("responder_cancelled", 500)
            return task.result()
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def explain(self, raw: LocalExplainRequest | dict) -> dict:
        try:
            request = LocalExplainRequest.model_validate(raw)
        except ValidationError as error:
            raise LocalServiceError("invalid_explain_request", 400) from None
        record, replayed = self._prepare(request)
        if replayed:
            with self._lock:
                self._check_record(record)
                return dict(record.response, replayed=True)
        try:
            now = self._now()
            evidence, fixture_reply = self._fresh_evidence(request, now)
            record.captured_at = now
            record.expires_at = evidence.context.expires_at
            record.mono_end = self._monotonic() + (record.expires_at - now).total_seconds()
            self._check_record(record)
            if self._demo_delay_ms:
                loop = asyncio.get_running_loop()
                deadline = loop.time() + self._demo_delay_ms / 1000
                while loop.time() < deadline:
                    self._check_record(record)
                    await asyncio.sleep(min(0.02, max(0.0, deadline - loop.time())))
                if record.cancel.is_set():
                    raise LocalServiceError("request_cancelled", 409)
            with Brain() as brain:
                start_id = "start-" + hashlib.sha256(request.request_id.encode()).hexdigest()[:24]
                help_id = "help-" + hashlib.sha256(request.request_id.encode()).hexdigest()[:24]
                producer = "local-selection" if isinstance(evidence.context, ImportedReaderContext) else "book-demo"
                start = StudyEvent(event_id=start_id, producer_id=producer, session_id=evidence.context.session_id,
                                   sequence=1, occurred_at=now, kind="SESSION_STARTED",
                                   context=evidence.context)
                started = brain.ingest(start, now=now)
                if not started.accepted:
                    raise LocalServiceError("brain_start_rejected", 409)
                decision = brain.ingest(StudyEvent(event_id=help_id, producer_id=producer,
                    session_id=evidence.context.session_id, sequence=2, occurred_at=now,
                    kind="HELP_REQUESTED"), now=now)
                if (not decision.accepted or decision.decision.action != "explain"
                        or decision.decision.source_ref != request.source_ref):
                    raise LocalServiceError("brain_decision_rejected", 409)
                if record.cancel.is_set():
                    raise LocalServiceError("request_cancelled", 409)
                self._check_record(record)
                reply = await self._await_responder(record, brain, evidence, fixture_reply, now)
                if (not isinstance(reply.text, str) or not reply.text.strip() or len(reply.text) > 4000):
                    raise LocalServiceError("invalid_responder_reply", 500)
                self._check_record(record)
            response = {"schema_version": "mygpt.local-explain-result.v1",
                        "scope": request.scope, "request_id": request.request_id,
                        "revision": request.revision, "entry_id": request.entry_id,
                        "mode": request.mode, "source_ref": request.source_ref,
                        "source_sha256": request.source_sha256, "text": reply.text,
                        "model_called": False, "test_model": self._test_model,
                        "source_trust": evidence.context.evidence_kind,
                        "live_book_connected": False, "paid_model_calls": 0,
                        "brain_action": "explain", "replayed": False}
            with self._lock:
                self._check_record(record)
                record.status = "completed"
                record.response = response
                self._metrics["requests_completed"] += 1
            return response
        except asyncio.CancelledError:
            with self._lock:
                record.cancel.set()
                if record.status != "cancelled":
                    self._metrics["requests_cancelled"] += 1
                record.status = "cancelled"
                record.response = None
            raise
        except LocalServiceError as error:
            with self._lock:
                record.response = None
                record.status = "cancelled" if record.cancel.is_set() else "failed"
                record.error_code, record.error_status = error.code, error.status
            raise
        except Exception:
            # Provider/SDK details are intentionally not sent to the browser.
            with self._lock:
                record.status, record.response = "failed", None
                record.error_code, record.error_status = "local_brain_failure", 500
            raise LocalServiceError("local_brain_failure", 500) from None


