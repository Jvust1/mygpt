"""Loopback-only synthetic host -> real Python Brain/TestModel bridge.

Security posture for this development milestone:
- hard-coded loopback bind only (127.0.0.1), random port supported;
- one ephemeral HttpOnly SameSite=Strict cookie, in-memory only;
- exact Host + same-origin Origin/Referer + client-header checks on /api;
- fixed allow-listed static files and fixed bounded JSON endpoints;
- synthetic catalogue only; no arbitrary source text or model/provider selection;
- cancellation/revocation and short selection/auth expiry;
- no persistence, uploads, Book endpoint, external network or paid model.

This is not a hardened multi-user web service or Android production transport.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import importlib.metadata as metadata
import json
import mimetypes
from pathlib import Path
import secrets
import threading
import time
from typing import Annotated, Awaitable, Callable, Literal

from pydantic import Field, ValidationError

from .adapters import EvidenceText, run_fixture_test_model
from .core import (Brain, Contract, Identifier, ReaderStudyContext, Sequence,
                   StudyEvent, checked_now, parse_context, utc_now)
from .host_fixtures import build_catalogue

MAX_BODY = 8192
MAX_REQUESTS = 128
CLIENT_HEADER = "mygpt-reader-brain-v1"
COOKIE_NAME = "mygpt_local_brain"
STATIC_FILES = {
    "/host/brain.html": "host/brain.html",
    "/host/brain.js": "host/brain.js",
    "/host/brain-adapter.js": "host/brain-adapter.js",
    "/host/controller.js": "host/controller.js",
    "/host/fixtures.js": "host/fixtures.js",
    "/host/reader.css": "host/reader.css",
    "/companion/mygpt-pet.js": "companion/mygpt-pet.js",
    "/companion/animations.js": "companion/animations.js",
    "/companion/assets/jonah.png": "companion/assets/jonah.png",
}


class LocalServiceError(RuntimeError):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


class LocalExplainRequest(Contract):
    schema_version: Literal["mygpt.local-explain.v1"] = "mygpt.local-explain.v1"
    scope: Literal["SYNTHETIC_FIXED_REPLAY"]
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


Responder = Callable[[Brain, EvidenceText, str, str, datetime], Awaitable[object]]


async def _default_responder(brain: Brain, evidence: EvidenceText, question: str,
                             fixture_text: str, now: datetime):
    return await run_fixture_test_model(brain, evidence, question, fixture_text, now=now)


class LocalBrainEngine:
    """Bounded, single-authorization in-memory synthetic request engine."""

    def __init__(self, *, catalogue: dict | None = None, clock: Callable[[], datetime] = utc_now,
                 monotonic: Callable[[], float] = time.monotonic,
                 authorization_seconds: int = 1800, context_seconds: int = 120,
                 demo_delay_ms: int = 0, responder: Responder = _default_responder) -> None:
        if not 60 <= authorization_seconds <= 3600:
            raise ValueError("authorization_seconds must be 60..3600")
        if not 1 <= context_seconds <= 300:
            raise ValueError("context_seconds must be 1..300")
        if not 0 <= demo_delay_ms <= 5000:
            raise ValueError("demo_delay_ms must be 0..5000")
        data = build_catalogue() if catalogue is None else catalogue
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
        if not isinstance(self._created_mono, (int, float)) or not float(self._created_mono) >= 0:
            raise ValueError("invalid monotonic clock")
        self._service_id = "svc-" + secrets.token_hex(12)
        self._lock = threading.RLock()
        self._revoked = False
        self._requests: dict[str, _RequestRecord] = {}
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
            existing = self._requests.get(request.request_id)
            if existing:
                if existing.fingerprint != fingerprint:
                    self._metrics["request_conflicts"] += 1
                    raise LocalServiceError("request_id_conflict", 409)
                if existing.status == "completed" and existing.response is not None:
                    return existing, True
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
        self.require_authorized()
        with self._lock:
            self._metrics["cancel_requests"] += 1
            record = self._requests.get(request_id)
            if record is None:
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
            for record in self._requests.values():
                if record.status == "running":
                    record.cancel.set()
                    record.status = "cancelled"
                    self._metrics["requests_cancelled"] += 1
            return {"schema_version": "mygpt.local-revoke-result.v1",
                    "status": "already_revoked" if already else "revoked"}

    def _fresh_evidence(self, request: LocalExplainRequest, now: datetime) -> tuple[EvidenceText, str]:
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
        context = base.model_copy(update={"session_id": self._service_id, "mode": request.mode,
                                          "captured_at": now, "expires_at": expires})
        # Re-validate after model_copy; do not rely on copy/update bypass semantics.
        context = ReaderStudyContext.model_validate(context.model_dump(mode="json"))
        if context.reference != request.source_ref:
            raise LocalServiceError("source_reference_changed", 409)
        evidence = EvidenceText(context=context, text=entry["evidence_text"])
        return evidence, entry["fixture_reply"]

    async def explain(self, raw: LocalExplainRequest | dict) -> dict:
        try:
            request = LocalExplainRequest.model_validate(raw)
        except ValidationError as error:
            raise LocalServiceError("invalid_explain_request", 400) from None
        record, replayed = self._prepare(request)
        if replayed:
            return dict(record.response, replayed=True)
        try:
            now = self._now()
            evidence, fixture_reply = self._fresh_evidence(request, now)
            if record.cancel.is_set():
                raise LocalServiceError("request_cancelled", 409)
            if self._demo_delay_ms:
                loop = asyncio.get_running_loop()
                deadline = loop.time() + self._demo_delay_ms / 1000
                while loop.time() < deadline:
                    if record.cancel.is_set():
                        raise LocalServiceError("request_cancelled", 409)
                    await asyncio.sleep(min(0.02, max(0.0, deadline - loop.time())))
                if record.cancel.is_set():
                    raise LocalServiceError("request_cancelled", 409)
            with Brain() as brain:
                start_id = "start-" + hashlib.sha256(request.request_id.encode()).hexdigest()[:24]
                help_id = "help-" + hashlib.sha256(request.request_id.encode()).hexdigest()[:24]
                start = StudyEvent(event_id=start_id, session_id=evidence.context.session_id,
                                   sequence=1, occurred_at=now, kind="SESSION_STARTED",
                                   context=evidence.context)
                started = brain.ingest(start, now=now)
                if not started.accepted:
                    raise LocalServiceError("brain_start_rejected", 409)
                decision = brain.ingest(StudyEvent(event_id=help_id,
                    session_id=evidence.context.session_id, sequence=2, occurred_at=now,
                    kind="HELP_REQUESTED"), now=now)
                if (not decision.accepted or decision.decision.action != "explain"
                        or decision.decision.source_ref != request.source_ref):
                    raise LocalServiceError("brain_decision_rejected", 409)
                if record.cancel.is_set():
                    raise LocalServiceError("request_cancelled", 409)
                reply = await self._responder(
                    brain, evidence, "解释当前明确选择的合成片段。", fixture_reply, now)
                if record.cancel.is_set():
                    raise LocalServiceError("request_cancelled", 409)
            response = {"schema_version": "mygpt.local-explain-result.v1",
                        "scope": request.scope, "request_id": request.request_id,
                        "revision": request.revision, "entry_id": request.entry_id,
                        "mode": request.mode, "source_ref": request.source_ref,
                        "source_sha256": request.source_sha256, "text": reply.text,
                        "model_called": False, "test_model": self._test_model,
                        "live_book_connected": False, "paid_model_calls": 0,
                        "brain_action": "explain", "replayed": False}
            with self._lock:
                if record.cancel.is_set() or record.status == "cancelled":
                    raise LocalServiceError("request_cancelled", 409)
                record.status = "completed"
                record.response = response
                self._metrics["requests_completed"] += 1
            return response
        except LocalServiceError:
            with self._lock:
                if record.cancel.is_set() and record.status != "completed":
                    record.status = "cancelled"
            raise
        except Exception:
            # Provider/SDK details are intentionally not sent to the browser.
            with self._lock:
                if record.status != "completed":
                    record.status = "cancelled"
            raise LocalServiceError("local_brain_failure", 500) from None


class _LoopbackServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, handler, *, engine: LocalBrainEngine, root: Path,
                 token: str, token_seconds: int):
        self.engine, self.root, self.token, self.token_seconds = engine, root, token, token_seconds
        super().__init__(address, handler)
        host, port = self.server_address
        if host != "127.0.0.1":
            self.server_close()
            raise ValueError("loopback server must bind 127.0.0.1")
        self.origin = f"http://127.0.0.1:{port}"
        self.expected_host = f"127.0.0.1:{port}"


class LocalBrainHandler(BaseHTTPRequestHandler):
    server: _LoopbackServer
    protocol_version = "HTTP/1.1"
    server_version = "mygpt-local"
    sys_version = ""

    def log_message(self, _format, *_args):
        return

    def _headers(self, status: int, content_type: str, length: int, *, cookie=False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        if cookie:
            self.send_header("Set-Cookie",
                f"{COOKIE_NAME}={self.server.token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={self.server.token_seconds}")
        self.end_headers()

    def _send(self, status: int, body: bytes, content_type="application/json; charset=utf-8", *, cookie=False):
        self._headers(status, content_type, len(body), cookie=cookie)
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # A browser abort/cancel may close its explain request while a
                # parallel bounded cancel reaches the service. Do not turn that
                # expected disconnect into a server-side traceback.
                pass

    def _json(self, status: int, value: dict):
        self._send(status, (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode())

    def _error(self, error: LocalServiceError):
        self._json(error.status, {"schema_version": "mygpt.local-error.v1", "code": error.code})

    def _cookie_ok(self) -> bool:
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return cookie.get(COOKIE_NAME) is not None and secrets.compare_digest(
                cookie[COOKIE_NAME].value, self.server.token)
        except Exception:
            return False

    def _api_guard(self, *, post=False):
        if self.client_address[0] != "127.0.0.1":
            raise LocalServiceError("non_loopback_client", 403)
        if self.headers.get("Host") != self.server.expected_host:
            raise LocalServiceError("invalid_host", 403)
        if self.headers.get("X-MyGPT-Client") != CLIENT_HEADER:
            raise LocalServiceError("invalid_client", 403)
        if not self._cookie_ok():
            raise LocalServiceError("missing_or_invalid_authorization", 403)
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site not in (None, "same-origin"):
            raise LocalServiceError("cross_site_request", 403)
        origin, referer = self.headers.get("Origin"), self.headers.get("Referer")
        if origin is not None and origin != self.server.origin:
            raise LocalServiceError("invalid_origin", 403)
        if referer is not None and not referer.startswith(self.server.origin + "/"):
            raise LocalServiceError("invalid_referer", 403)
        if origin is None and referer is None and fetch_site != "same-origin":
            # The page itself is served with Referrer-Policy: no-referrer, and
            # same-origin GET fetches need not carry Origin. Sec-Fetch-Site plus
            # the exact Host/cookie/custom-header checks is the browser signal.
            raise LocalServiceError("origin_evidence_required", 403)
        if post:
            if origin != self.server.origin:
                raise LocalServiceError("origin_required_for_post", 403)
            if self.headers.get("Transfer-Encoding"):
                raise LocalServiceError("transfer_encoding_not_supported", 400)
            if self.headers.get_content_type() != "application/json":
                raise LocalServiceError("json_content_type_required", 415)
        self.server.engine.require_authorized()

    def _read_json(self) -> dict:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length) if raw_length is not None else -1
        except ValueError:
            raise LocalServiceError("invalid_content_length", 400)
        if length < 0 or length > MAX_BODY:
            raise LocalServiceError("invalid_body_size", 413 if length > MAX_BODY else 411)
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise LocalServiceError("invalid_json", 400)
        if type(value) is not dict:
            raise LocalServiceError("json_object_required", 400)
        return value

    def do_GET(self):
        if self.path == "/":
            body = b""
            self.send_response(302)
            self.send_header("Location", "/host/brain.html")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers(); return
        if self.path == "/api/v1/status":
            try:
                self._api_guard(post=False)
                self._json(200, self.server.engine.status())
            except LocalServiceError as error:
                self._error(error)
            return
        relative = STATIC_FILES.get(self.path)
        if relative is None:
            self._error(LocalServiceError("not_found", 404)); return
        path = (self.server.root / relative).resolve()
        try:
            if self.server.root.resolve() not in path.parents or not path.is_file():
                raise FileNotFoundError
            body = path.read_bytes()
        except OSError:
            self._error(LocalServiceError("not_found", 404)); return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript",):
            content_type += "; charset=utf-8"
        self._send(200, body, content_type, cookie=self.path == "/host/brain.html")

    def do_HEAD(self):
        return self.do_GET()

    def do_POST(self):
        try:
            self._api_guard(post=True)
            value = self._read_json()
            if self.path == "/api/v1/explain":
                result = asyncio.run(self.server.engine.explain(value))
                self._json(200, result); return
            if self.path == "/api/v1/cancel":
                try:
                    request = LocalCancelRequest.model_validate(value)
                except ValidationError:
                    raise LocalServiceError("invalid_cancel_request", 400) from None
                self._json(200, self.server.engine.cancel(request.request_id)); return
            if self.path == "/api/v1/revoke":
                try:
                    LocalRevokeRequest.model_validate(value)
                except ValidationError:
                    raise LocalServiceError("invalid_revoke_request", 400) from None
                self._json(200, self.server.engine.revoke()); return
            raise LocalServiceError("not_found", 404)
        except LocalServiceError as error:
            self._error(error)

    def do_OPTIONS(self):
        # No CORS negotiation; same-origin module code is the intended browser client.
        self._error(LocalServiceError("cors_not_supported", 405))

    def _method_not_allowed(self):
        self._error(LocalServiceError("method_not_allowed", 405))

    do_PUT = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed
    do_CONNECT = _method_not_allowed


@dataclass
class LocalBrainServer:
    httpd: _LoopbackServer
    thread: threading.Thread | None = None

    @property
    def origin(self) -> str:
        return self.httpd.origin

    @property
    def url(self) -> str:
        return self.origin + "/host/brain.html"

    def start(self) -> "LocalBrainServer":
        if self.thread is not None:
            raise RuntimeError("server already started")
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="mygpt-local-brain", daemon=True)
        self.thread.start()
        return self

    def close(self) -> None:
        if self.thread is not None:
            self.httpd.shutdown()
            self.thread.join(timeout=5)
            self.thread = None
        self.httpd.server_close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()


def create_local_server(*, port: int = 0, root: Path | None = None,
                        authorization_seconds: int = 1800, demo_delay_ms: int = 0,
                        responder: Responder = _default_responder,
                        catalogue: dict | None = None) -> LocalBrainServer:
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port must be 0..65535")
    repo_root = (Path(__file__).resolve().parents[2] if root is None else Path(root)).resolve()
    # Refuse surprising roots before opening a listener.
    for relative in ("host/brain.html", "host/brain.js", "companion/mygpt-pet.js"):
        if not (repo_root / relative).is_file():
            raise FileNotFoundError(relative)
    engine = LocalBrainEngine(catalogue=catalogue, authorization_seconds=authorization_seconds,
                              demo_delay_ms=demo_delay_ms, responder=responder)
    token = secrets.token_urlsafe(32)
    httpd = _LoopbackServer(("127.0.0.1", port), LocalBrainHandler, engine=engine,
                            root=repo_root, token=token, token_seconds=authorization_seconds)
    return LocalBrainServer(httpd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="127.0.0.1 port; 0 chooses an ephemeral port")
    parser.add_argument("--authorization-seconds", type=int, default=1800)
    parser.add_argument("--demo-delay-ms", type=int, default=0,
                        help="synthetic cancellable delay before TestModel; 0 for normal local use")
    args = parser.parse_args()
    server = create_local_server(port=args.port, authorization_seconds=args.authorization_seconds,
                                 demo_delay_ms=args.demo_delay_ms)
    try:
        server.start()
        print(f"mygpt local brain: {server.origin}", flush=True)
        print("scope=SYNTHETIC_LOCAL_PYTHON_BRAIN live_book_connected=false paid_model_calls=0", flush=True)
        while server.thread and server.thread.is_alive():
            server.thread.join(timeout=1)
    except KeyboardInterrupt:
        return 0
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
