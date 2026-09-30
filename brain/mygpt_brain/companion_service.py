"""Bounded native loopback transport for CompanionChatRuntime.

This is deliberately separate from local_service.py, whose browser-specific
cookie/origin policy remains unchanged. The native transport is loopback-only,
uses a per-process bearer token, and does not expose model/provider/persona
configuration over HTTP.

Owned request tracking/snapshot cancellation adapts Pipecat TaskManager at
49dea682fb84bfc515d881d00dfeaaa9e9f1075f. Copyright (c) 2024–2026, Daily.
BSD-2-Clause; see third_party/pipecat/LICENSE and NOTICE.md.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from concurrent.futures import TimeoutError as FutureTimeoutError
from concurrent.futures import CancelledError as FutureCancelledError, Future
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
import time
from typing import Any, Callable, ContextManager

from pydantic import ValidationError

from .companion_chat import CompanionChatRuntime, SupersededChatTurn
from .json_boundary import BoundaryError, load_object

MAX_BODY = 16384
CLIENT_HEADER = "mygpt-companion-native-v1"


class CompanionServiceError(RuntimeError):
    def __init__(self, code: str, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


class _RuntimeExecutor:
    """Own one asyncio loop so one runtime/Lock is never reused across loops."""

    def __init__(
        self, runtime: CompanionChatRuntime, *,
        is_authorized: Callable[[], bool], authorization_remaining: Callable[[], float],
        completion_guard: Callable[[], ContextManager[None]],
    ) -> None:
        self.runtime = runtime
        self._is_authorized = is_authorized
        self._authorization_remaining = authorization_remaining
        self._completion_guard = completion_guard
        self._pending: set[Future] = set()
        self._pending_lock = threading.Lock()
        self.loop = asyncio.new_event_loop()
        self.started = threading.Event()
        self.closed = False
        self.thread = threading.Thread(
            target=self._run,
            name="mygpt-companion-runtime",
            daemon=True,
        )
        self.thread.start()
        if not self.started.wait(timeout=5):
            raise RuntimeError("companion runtime loop failed to start")
        self.timeout_seconds = min(
            65.0,
            max(2.0, float(getattr(runtime, "request_timeout_seconds", 30.0)) + 2.0),
        )

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.started.set()
        self.loop.run_forever()
        self.loop.close()

    async def _cancel_pending(self) -> None:
        current = asyncio.current_task()
        tasks = [
            task
            for task in asyncio.all_tasks()
            if task is not current and not task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def chat(self, value: dict[str, Any]) -> dict[str, Any]:
        if not self._is_authorized():
            raise CompanionServiceError("authorization_revoked_or_expired", 403)
        wait_seconds = min(self.timeout_seconds, self._authorization_remaining())
        if wait_seconds <= 0:
            raise CompanionServiceError("authorization_revoked_or_expired", 403)
        with self._pending_lock:
            if self.closed:
                raise CompanionServiceError("service_closed", 503)
            future = asyncio.run_coroutine_threadsafe(
                self.runtime.send(
                    value, is_current=self._is_authorized,
                    completion_guard=self._completion_guard,
                ), self.loop,
            )
            self._pending.add(future)
        # Attach outside the lock: already-finished futures invoke callbacks
        # synchronously, and callback removal must never deadlock registration.
        future.add_done_callback(self._discard_pending)
        # A revoke may race registration; fail closed even if its snapshot did
        # not yet contain this future. The runtime has the same precommit guard.
        if not self._is_authorized():
            future.cancel()
        wait_seconds = min(self.timeout_seconds, self._authorization_remaining())
        if wait_seconds <= 0:
            future.cancel()
            raise CompanionServiceError("authorization_revoked_or_expired", 403)
        try:
            result = future.result(timeout=wait_seconds)
        except FutureTimeoutError:
            future.cancel()
            if not self._is_authorized():
                raise CompanionServiceError("authorization_revoked_or_expired", 403) from None
            raise CompanionServiceError("request_timeout", 504) from None
        except (FutureCancelledError, SupersededChatTurn):
            if not self._is_authorized():
                raise CompanionServiceError("authorization_revoked_or_expired", 403) from None
            raise CompanionServiceError("service_closed", 503) from None
        if not self._is_authorized():
            raise CompanionServiceError("authorization_revoked_or_expired", 403)
        return result.model_dump(mode="json")

    def _discard_pending(self, future: Future) -> None:
        with self._pending_lock:
            self._pending.discard(future)

    def cancel_active(self) -> None:
        # Pipecat snapshots owned tasks before cancellation because completion
        # callbacks can mutate the registry. These futures bridge HTTP threads
        # to the one runtime loop and propagate cancel() to the asyncio task.
        with self._pending_lock:
            pending = tuple(self._pending)
        for future in pending:
            future.cancel()

    def close(self) -> None:
        with self._pending_lock:
            if self.closed:
                return
            self.closed = True
        self.cancel_active()
        if self.loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._cancel_pending(), self.loop
                )
                future.result(timeout=5)
            except Exception:
                # Shutdown must still stop the loop even if a provider task ignores
                # cooperative cancellation.
                pass
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)


class _CompanionLoopbackServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(
        self,
        address,
        handler,
        *,
        runtime: CompanionChatRuntime,
        token: str,
        authorization_seconds: int,
    ) -> None:
        if type(authorization_seconds) is not int or not 1 <= authorization_seconds <= 86400:
            raise ValueError("authorization_seconds must be in 1..86400")
        self.runtime = runtime
        self.token = token
        self.authorization_seconds = authorization_seconds
        self.authorization_deadline = time.monotonic() + authorization_seconds
        self._revoked = False
        self._auth_lock = threading.RLock()
        self._connection_slots = threading.BoundedSemaphore(16)
        self.executor = _RuntimeExecutor(
            runtime, is_authorized=self.is_authorized,
            authorization_remaining=self.authorization_remaining,
            completion_guard=self.completion_guard,
        )
        try:
            super().__init__(address, handler)
        except BaseException:
            self.executor.close()
            raise
        host, port = self.server_address
        if host != "127.0.0.1":
            self.server_close()
            self.executor.close()
            raise ValueError("companion service must bind 127.0.0.1")
        self.origin = f"http://127.0.0.1:{port}"
        self.expected_host = f"127.0.0.1:{port}"

    def process_request(self, request, client_address):
        if not self._connection_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()

    def is_authorized(self) -> bool:
        with self._auth_lock:
            return not self._revoked and time.monotonic() < self.authorization_deadline

    def revoke(self) -> None:
        with self._auth_lock:
            self._revoked = True
        # Do not hold auth/pending locks while cancelling: done callbacks may
        # run synchronously and the runtime's guard reads authorization again.
        self.executor.cancel_active()

    @contextmanager
    def completion_guard(self):
        """Linearize synchronous commit/delivery admission against revoke.

        An already admitted completion finishes before revoke can acknowledge.
        After revocation wins, no later completion may enter this section.
        Never hold this guard around provider/ASR awaits.
        """
        with self._auth_lock:
            if not self.is_authorized():
                raise SupersededChatTurn("authorization revoked or expired")
            yield

    def authorization_remaining(self) -> float:
        with self._auth_lock:
            if self._revoked:
                return 0.0
            return max(0.0, self.authorization_deadline - time.monotonic())

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": "mygpt.companion-service-status.v1",
            "transport": "LOOPBACK_NATIVE_TOKEN",
            "authorized": self.is_authorized(),
            "persona_id": self.runtime.persona.persona_id,
            "visual_skin_id": self.runtime.persona.visual_skin_id,
            "book_context_supported": True,
            "memory_mode": "EXPLICIT_LOCAL_ONLY",
            "provider_configurable_over_http": False,
            "remote_bind_supported": False,
        }


class CompanionServiceHandler(BaseHTTPRequestHandler):
    server: _CompanionLoopbackServer
    protocol_version = "HTTP/1.1"
    server_version = "mygpt-companion-local"
    sys_version = ""

    def log_message(self, _format, *_args) -> None:
        return

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)

    def _headers(self, status: int, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(length))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.close_connection = True

    def _json(self, status: int, value: dict[str, Any]) -> None:
        body = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        try:
            self._headers(status, len(body))
            if self.command != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _error(self, error: CompanionServiceError) -> None:
        self._json(
            error.status,
            {
                "schema_version": "mygpt.companion-service-error.v1",
                "code": error.code,
            },
        )

    def _guard(self, *, post: bool = False) -> None:
        for name in (
            "Host",
            "Authorization",
            "X-MyGPT-Client",
            "Content-Length",
            "Content-Type",
            "Transfer-Encoding",
        ):
            if len(self.headers.get_all(name, [])) > 1:
                raise CompanionServiceError("duplicate_http_header", 400)
        if self.client_address[0] != "127.0.0.1":
            raise CompanionServiceError("non_loopback_client", 403)
        if self.headers.get("Host") != self.server.expected_host:
            raise CompanionServiceError("invalid_host", 403)
        if self.headers.get("X-MyGPT-Client") != CLIENT_HEADER:
            raise CompanionServiceError("invalid_client", 403)

        authorization = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            raise CompanionServiceError("missing_or_invalid_authorization", 403)
        supplied = authorization[len(prefix):]
        if not supplied or not secrets.compare_digest(supplied, self.server.token):
            raise CompanionServiceError("missing_or_invalid_authorization", 403)
        if not self.server.is_authorized():
            raise CompanionServiceError("authorization_revoked_or_expired", 403)

        if self.headers.get("Transfer-Encoding"):
            raise CompanionServiceError("transfer_encoding_not_supported", 400)
        if post and self.headers.get_content_type() != "application/json":
            raise CompanionServiceError("json_content_type_required", 415)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise CompanionServiceError("content_length_required", 411)
        if not raw_length.isascii() or not raw_length.isdecimal():
            raise CompanionServiceError("invalid_content_length", 400)
        length = int(raw_length)
        if length <= 0 or length > MAX_BODY:
            raise CompanionServiceError("invalid_body_size", 413)
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise CompanionServiceError("incomplete_body", 400)
        try:
            return load_object(raw, max_bytes=MAX_BODY)
        except BoundaryError as error:
            raise CompanionServiceError(str(error), 400) from None

    @staticmethod
    def _runtime_error(error: BaseException) -> CompanionServiceError:
        if isinstance(error, ValidationError):
            return CompanionServiceError("invalid_chat_request", 400)
        if isinstance(error, ValueError):
            message = str(error)
            if "request_id conflict" in message:
                return CompanionServiceError("request_id_conflict", 409)
            if "book context expired" in message:
                return CompanionServiceError("book_context_expired", 409)
            if "session belongs to another persona" in message:
                return CompanionServiceError("session_persona_conflict", 409)
            return CompanionServiceError("invalid_chat_request", 400)
        if isinstance(error, CompanionServiceError):
            return error
        if isinstance(error, RuntimeError):
            return CompanionServiceError("responder_unavailable", 503)
        return CompanionServiceError("companion_service_failure", 500)

    def do_GET(self) -> None:
        try:
            self._guard(post=False)
            if self.path == "/api/v1/status":
                self._json(200, self.server.status())
                return
            raise CompanionServiceError("not_found", 404)
        except CompanionServiceError as error:
            self._error(error)

    def do_HEAD(self) -> None:
        return self.do_GET()

    def do_POST(self) -> None:
        try:
            self._guard(post=True)
            value = self._read_json()
            if self.path == "/api/v1/chat":
                try:
                    result = self.server.executor.chat(value)
                except BaseException as error:
                    raise self._runtime_error(error) from None
                try:
                    with self.server.completion_guard():
                        self._json(200, result)
                except SupersededChatTurn:
                    raise CompanionServiceError("authorization_revoked_or_expired", 403) from None
                return
            if self.path == "/api/v1/revoke":
                if value != {"schema_version": "mygpt.companion-revoke.v1"}:
                    raise CompanionServiceError("invalid_revoke_request", 400)
                self.server.revoke()
                self._json(
                    200,
                    {
                        "schema_version": "mygpt.companion-revoke-result.v1",
                        "status": "revoked",
                    },
                )
                return
            raise CompanionServiceError("not_found", 404)
        except CompanionServiceError as error:
            self._error(error)

    def do_OPTIONS(self) -> None:
        self._error(CompanionServiceError("cors_not_supported", 405))

    def _method_not_allowed(self) -> None:
        self._error(CompanionServiceError("method_not_allowed", 405))

    do_PUT = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed
    do_CONNECT = _method_not_allowed


@dataclass
class LocalCompanionServer:
    httpd: _CompanionLoopbackServer
    thread: threading.Thread | None = None

    @property
    def origin(self) -> str:
        return self.httpd.origin

    @property
    def token(self) -> str:
        """Process-local handoff token; callers must not log it."""
        return self.httpd.token

    def start(self) -> "LocalCompanionServer":
        if self.thread is not None:
            raise RuntimeError("server already started")
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="mygpt-companion-http",
            daemon=True,
        )
        self.thread.start()
        return self

    def close(self) -> None:
        self.httpd.revoke()
        if self.thread is not None:
            self.httpd.shutdown()
            self.thread.join(timeout=5)
            self.thread = None
        self.httpd.server_close()
        self.httpd.executor.close()

    def __enter__(self) -> "LocalCompanionServer":
        return self.start()

    def __exit__(self, *_args) -> None:
        self.close()


def create_companion_server(
    runtime: CompanionChatRuntime,
    *,
    port: int = 0,
    authorization_seconds: int = 1800,
) -> LocalCompanionServer:
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port must be 0..65535")
    token = secrets.token_urlsafe(32)
    httpd = _CompanionLoopbackServer(
        ("127.0.0.1", port),
        CompanionServiceHandler,
        runtime=runtime,
        token=token,
        authorization_seconds=authorization_seconds,
    )
    return LocalCompanionServer(httpd)
