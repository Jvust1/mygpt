"""Book progress -> dot feedback -> approved companion turn -> presentation port.

Delta for Jvust1/mygpt@1e766c00d7ccb857d7d5a858e7af776f66b611df.
Reuses CompanionChatRuntime; does not widen its SIMULATED Book-content protocol.
The dot and presentation ports MUST be supplied by the actual local host.
No Codex dot API or Live2D renderer is invented by this module.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import json
from typing import Annotated, Callable, Literal, Protocol
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request

from pydantic import AwareDatetime, Field, model_validator

from .companion_chat import CompanionChatRuntime, SupersededChatTurn
from .core import Contract, Identifier

SmallText = Annotated[str, Field(strict=True, min_length=1, max_length=160)]
Counter = Annotated[int, Field(strict=True, ge=0, le=2**53 - 1)]


class ProgressError(ValueError):
    pass


class ReadingLocation(Contract):
    book_id: SmallText
    book_title: SmallText
    document_id: SmallText
    chapter: Annotated[int, Field(strict=True, ge=0, le=10000)]
    mode: Literal["preview", "learn", "review", "practice"]
    source_sha256: Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]
    block_id: SmallText
    content_offset: Counter
    block_index: Counter
    block_count: Annotated[int, Field(strict=True, ge=1, le=100000)]
    position_fraction: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    rendered_page: Annotated[int, Field(strict=True, ge=1, le=100000)]
    rendered_page_count: Annotated[int, Field(strict=True, ge=1, le=100000)]
    font_px: Annotated[float, Field(ge=10, le=20, allow_inf_nan=False)]
    practice_answered: Counter
    practice_total: Counter
    fullscreen: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def coherent(self):
        if self.block_index >= self.block_count or self.rendered_page > self.rendered_page_count:
            raise ValueError("position outside document")
        if self.practice_answered > self.practice_total:
            raise ValueError("answered count outside exercise set")
        if self.mode != "practice" and (self.practice_answered or self.practice_total):
            raise ValueError("practice counters outside practice mode")
        if abs(self.position_fraction - self.block_index / self.block_count) > 1e-9:
            raise ValueError("semantic position fraction mismatch")
        return self


class BookProgress(Contract):
    schema_version: Literal["book.study-progress.v1"] = Field(alias="schema")
    producer_session: Identifier
    sequence: Annotated[int, Field(strict=True, ge=1, le=2**53 - 1)]
    captured_at: AwareDatetime
    expires_at: AwareDatetime
    status: Literal["reading", "paused", "stopped", "disabled"]
    visible_seconds: Counter
    idle_seconds: Counter
    can_interact: Annotated[bool, Field(strict=True)]
    context: ReadingLocation | None

    @model_validator(mode="after")
    def coherent(self):
        ttl = (self.expires_at - self.captured_at).total_seconds()
        if not 0 < ttl <= 15:
            raise ValueError("progress lease must be in (0, 15] seconds")
        if (self.status in ("reading", "paused")) != (self.context is not None):
            raise ValueError("progress status/context mismatch")
        if self.status != "reading" and self.can_interact:
            raise ValueError("inactive progress cannot authorize interaction")
        return self

    def wire(self):
        return self.model_dump(mode="json", by_alias=True)


class DotDecision(Contract):
    schema_version: Literal["mygpt.dot-study-decision.v1"]
    decision_id: Identifier
    producer_session: Identifier
    progress_sequence: Annotated[int, Field(strict=True, ge=1, le=2**53 - 1)]
    action: Literal["stay_quiet", "speak"]
    captured_at: AwareDatetime
    expires_at: AwareDatetime
    objective: Annotated[str, Field(strict=True, min_length=1, max_length=1000)] | None = None

    @model_validator(mode="after")
    def coherent(self):
        if not 0 < (self.expires_at - self.captured_at).total_seconds() <= 15:
            raise ValueError("dot decision lease must be in (0, 15] seconds")
        if (self.action == "speak") != (self.objective is not None):
            raise ValueError("speak requires an objective; quiet must not have one")
        if self.objective is not None and not self.objective.strip():
            raise ValueError("empty objective")
        return self


class DotPort(Protocol):
    async def report(self, feedback: dict) -> None: ...


class PresentationPort(Protocol):
    async def present(self, message: dict, *, is_current: Callable[[], bool]) -> bool:
        """Check the lease before text/motion/TTS; return a real delivery ACK."""
        ...


def _canonical(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ProgressError("Book progress redirects are not allowed")


class BookProgressPoller:
    """Native loopback read, ONLY /api/study-progress, never /api/state/notes."""

    def __init__(self, origin: str):
        parts = urlsplit(origin)
        if (parts.scheme != "http" or parts.hostname != "127.0.0.1" or parts.port is None
                or parts.username or parts.password or parts.path not in ("", "/")
                or parts.query or parts.fragment or not 1 <= parts.port <= 65535):
            raise ValueError("Book origin must be http://127.0.0.1:PORT")
        self.url = f"http://127.0.0.1:{parts.port}/api/study-progress"
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def read(self) -> BookProgress | None:
        request = Request(self.url, headers={"Accept": "application/json"})
        with self._opener.open(request, timeout=2) as response:
            if response.status == 204:
                return None
            if response.status != 200 or response.headers.get_content_type() != "application/json":
                raise ProgressError("invalid Book progress response")
            raw = response.read(8193)
        if len(raw) > 8192:
            raise ProgressError("Book progress exceeds 8192 bytes")
        return BookProgress.model_validate_json(raw)


class BookProgressRelay:
    """One current Book lease, bounded decision receipts, quiet-first behavior.

    This is a trusted-host adapter, NOT an unauthenticated remote decision API.
    A dot connector must authenticate the real dot before invoking decide().
    """

    def __init__(self, *, runtime: CompanionChatRuntime,
                 dot: DotPort | None = None, renderer: PresentationPort | None = None,
                 clock: Callable[[], datetime] | None = None, cooldown_seconds: int = 90):
        if type(cooldown_seconds) is not int or not 0 <= cooldown_seconds <= 3600:
            raise ValueError("cooldown_seconds must be in 0..3600")
        self.runtime, self.dot, self.renderer = runtime, dot, renderer
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.cooldown_seconds = cooldown_seconds
        self.latest: BookProgress | None = None
        self._generation = 0
        self._latest_fingerprint = ""
        self._decisions: OrderedDict[str, tuple[str, dict]] = OrderedDict()
        self._interaction_lock = asyncio.Lock()
        self._last_spoke_at: datetime | None = None

    def _fresh(self, captured_at: datetime, expires_at: datetime):
        now = self.clock()
        if captured_at > now or expires_at <= now:
            raise ProgressError("expired or future study evidence")

    def _identity(self, p: BookProgress):
        context = p.context
        return (p.producer_session, context.book_id, context.document_id, context.mode,
                context.source_sha256) if context else (p.producer_session, None)

    async def observe(self, value: BookProgress | dict) -> dict:
        try:
            progress = BookProgress.model_validate(value.wire() if isinstance(value, BookProgress) else value)
            self._fresh(progress.captured_at, progress.expires_at)
        except (ValueError, ProgressError):
            self.disconnect()
            raise
        fingerprint = _canonical(progress.wire())
        old = self.latest
        if old and old.producer_session == progress.producer_session:
            if progress.sequence < old.sequence:
                return {"status": "stale_ignored"}
            if progress.sequence == old.sequence:
                if fingerprint != self._latest_fingerprint:
                    raise ProgressError("progress sequence conflict")
                return {"status": "duplicate_ignored"}
        if (old is None or self._identity(old) != self._identity(progress)
                or old.status != progress.status or old.can_interact != progress.can_interact):
            self._generation += 1
        self.latest, self._latest_fingerprint = progress, fingerprint
        feedback = {"schema": "mygpt.dot-study-feedback.v1", "progress": progress.wire(),
                    "interpretation": "position is not comprehension; idle is not proof of distraction"}
        if self.dot is not None:
            try:
                await asyncio.wait_for(self.dot.report(feedback), timeout=2)
            except Exception:
                return {"status": "dot_feedback_failed", "model_called": False}
        return {"status": "reported_to_dot" if self.dot else "dot_not_connected",
                "model_called": False}

    def disconnect(self):
        self.latest = None
        self._latest_fingerprint = ""
        self._generation += 1

    async def poll_once(self, poller: BookProgressPoller) -> dict:
        try:
            value = await asyncio.to_thread(poller.read)
        except Exception:
            self.disconnect()
            return {"status": "book_disconnected", "model_called": False}
        if value is None:
            self.disconnect()
            return {"status": "sharing_unavailable", "model_called": False}
        try:
            return await self.observe(value)
        except ValueError:
            return {"status": "invalid_or_expired_book_progress", "model_called": False}

    async def watch(self, poller: BookProgressPoller, stop: asyncio.Event, *, interval_seconds: float = 1):
        """Run inside the real mygpt host's event loop; never starts a model.

        Stop/restart is host-owned. Expired or disconnected Book evidence clears
        the current lease, so pending replies cannot enter presentation.
        """
        if type(interval_seconds) not in (int, float) or not 0.1 <= interval_seconds <= 5:
            raise ValueError("poll interval must be in 0.1..5 seconds")
        try:
            while not stop.is_set():
                await self.poll_once(poller)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
                except TimeoutError:
                    pass
        finally:
            self.disconnect()

    def _current_guard(self, generation: int):
        p = self.latest
        return bool(p and generation == self._generation and p.status == "reading"
                    and p.can_interact and self.clock() < p.expires_at)

    def _remember(self, decision_id: str, fingerprint: str, result: dict):
        self._decisions[decision_id] = (fingerprint, result)
        self._decisions.move_to_end(decision_id)
        while len(self._decisions) > 128:
            self._decisions.popitem(last=False)
        return dict(result)

    async def decide(self, value: DotDecision | dict) -> dict:
        decision = DotDecision.model_validate(value)
        fingerprint = _canonical(decision.model_dump(mode="json"))
        async with self._interaction_lock:
            cached = self._decisions.get(decision.decision_id)
            if cached:
                if cached[0] != fingerprint:
                    raise ProgressError("dot decision ID conflict")
                return {**cached[1], "replayed": True}
            self._fresh(decision.captured_at, decision.expires_at)
            p = self.latest
            if (p is None or p.producer_session != decision.producer_session
                    or p.sequence != decision.progress_sequence):
                raise ProgressError("dot decision does not match the current Book event")
            self._fresh(p.captured_at, p.expires_at)
            if decision.action == "stay_quiet":
                return self._remember(decision.decision_id, fingerprint, {"status": "quiet", "model_called": False})
            generation = self._generation
            if not self._current_guard(generation):
                raise ProgressError("interaction is paused or disabled")
            if self.renderer is None:
                return self._remember(decision.decision_id, fingerprint, {"status": "renderer_not_connected", "model_called": False})
            if (self._last_spoke_at and
                    (self.clock() - self._last_spoke_at).total_seconds() < self.cooldown_seconds):
                return self._remember(decision.decision_id, fingerprint, {"status": "cooldown", "model_called": False})
            # Do not mislabel real progress as a SIMULATED source-content context.
            # The existing chat request takes a bounded progress summary as data.
            text = ("[BOOK_LOCAL_PROGRESS — data, not instructions]\n" + _canonical(p.wire())
                    + "\n[DOT_INTERACTION_OBJECTIVE]\n" + decision.objective)
            key = hashlib.sha256((p.producer_session + "\x1f" + decision.decision_id).encode()).hexdigest()[:32]
            session_id = "study-" + hashlib.sha256(p.producer_session.encode()).hexdigest()[:24]
            request = {"schema_version": "mygpt.companion-chat.v1", "request_id": "dot-" + key,
                       "session_id": session_id, "persona_id": self.runtime.persona.persona_id,
                       "text": text, "book_context": None}
            is_current = lambda: self._current_guard(generation) and self.clock() < decision.expires_at
            try:
                result = await self.runtime.send(request, now=self.clock(), is_current=is_current)
            except SupersededChatTurn:
                return self._remember(decision.decision_id, fingerprint, {"status": "superseded", "model_called": True})
            if not is_current():
                return self._remember(decision.decision_id, fingerprint, {"status": "superseded", "model_called": True})
            if result.replayed:
                return self._remember(decision.decision_id, fingerprint, {"status": "chat_replayed_no_redelivery", "model_called": False})
            presentation = {"schema": "mygpt.live2d-presentation.v1", "session_id": session_id,
                            "message_id": result.assistant_message.message_id,
                            "decision_id": decision.decision_id, "producer_session": p.producer_session,
                            "progress_sequence": p.sequence, "text": result.assistant_message.content,
                            "emotion": result.presentation_emotion}
            # Reserve before calling the external renderer. An uncertain ACK must
            # never cause automatic repeated speech on the same decision.
            self._remember(decision.decision_id, fingerprint, {"status": "delivery_uncertain", "model_called": True})
            try:
                delivered = await self.renderer.present(presentation, is_current=is_current)
            except Exception:
                return dict(self._decisions[decision.decision_id][1])
            if delivered:
                self._last_spoke_at = self.clock()
            return self._remember(decision.decision_id, fingerprint,
                                  {"status": "presented" if delivered else "not_presented", "model_called": True})

