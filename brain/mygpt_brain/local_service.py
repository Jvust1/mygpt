"""Loopback development HTTP adapter, not a production multi-user server.

Fixed sample mode is unchanged. --enable-selection-intake explicitly enables
bounded, volatile ONE-record input; every imported source remains unverified.
No Book endpoint, cloud provider, upload outside loopback or disk storage exists.
"""
from __future__ import annotations
import argparse
import asyncio
from dataclasses import dataclass
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import threading
from pydantic import ValidationError
from .json_boundary import BoundaryError, load_object
# Re-export historical names so old callers and tests retain the same API.
from .local_engine import (LocalBrainEngine, LocalServiceError, LocalExplainRequest,
    LocalCancelRequest, LocalRevokeRequest, MAX_REQUESTS, Responder, _default_responder)

MAX_BODY = 8192
CLIENT_HEADER = "mygpt-reader-brain-v1"
COOKIE_NAME = "mygpt_local_brain"
STATIC_FILES = {
    "/host/math-preview.js": "host/math-preview.js",
    "/third_party/katex/katex.mjs": "third_party/katex/katex.mjs",
    "/host/selection.html": "host/selection.html",
    "/host/selection.js": "host/selection.js",
    "/host/selection-manual.js": "host/selection-manual.js",
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


class _LoopbackServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, handler, *, engine: LocalBrainEngine, root: Path,
                 token: str, token_seconds: int):
        self.engine, self.root, self.token, self.token_seconds = engine, root, token, token_seconds
        self._connection_slots = threading.BoundedSemaphore(16)
        super().__init__(address, handler)
        host, port = self.server_address
        if host != "127.0.0.1":
            self.server_close()
            raise ValueError("loopback server must bind 127.0.0.1")
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
        self.close_connection = True
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        if cookie:
            self.send_header("Set-Cookie",
                f"{COOKIE_NAME}={self.server.token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={self.server.token_seconds}")
        self.end_headers()

    def _send(self, status: int, body: bytes, content_type="application/json; charset=utf-8", *, cookie=False):
        try:
            self._headers(status, content_type, len(body), cookie=cookie)
            if self.command != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Headers may also race with a browser abort. Never log payloads.
            self.close_connection = True

    def _json(self, status: int, value: dict):
        self._send(status, (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode())

    def _error(self, error: LocalServiceError):
        self.close_connection = True
        self._json(error.status, {"schema_version": "mygpt.local-error.v1", "code": error.code})

    def _cookie_ok(self) -> bool:
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return cookie.get(COOKIE_NAME) is not None and secrets.compare_digest(
                cookie[COOKIE_NAME].value, self.server.token)
        except Exception:
            return False

    def _api_guard(self, *, post=False):
        for name in ("Host", "Origin", "Referer", "Cookie", "X-MyGPT-Client",
                     "Sec-Fetch-Site", "Content-Length", "Content-Type", "Transfer-Encoding"):
            if len(self.headers.get_all(name, [])) > 1:
                raise LocalServiceError("duplicate_http_header", 400)
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

    def _read_json(self, max_bytes=MAX_BODY) -> dict:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise LocalServiceError("content_length_required", 411)
        if not raw_length.isascii() or not raw_length.isdecimal():
            raise LocalServiceError("invalid_content_length", 400)
        length = int(raw_length)
        if length > max_bytes:
            raise LocalServiceError("invalid_body_size", 413)
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise LocalServiceError("incomplete_body", 400)
        try:
            return load_object(raw, max_bytes=max_bytes)
        except BoundaryError as error:
            raise LocalServiceError(str(error), 400) from None

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def handle_expect_100(self):
        self._error(LocalServiceError("expect_not_supported", 417))
        return False

    def do_GET(self):
        if (self.client_address[0] != "127.0.0.1"
                or self.headers.get_all("Host", []) != [self.server.expected_host]):
            self._error(LocalServiceError("invalid_host", 403)); return
        if self.path == "/":
            body = b""
            self.send_response(302)
            self.close_connection = True
            self.send_header("Connection", "close")
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
        # Module MIME must not depend on host registry overrides (Windows may
        # classify .mjs as text/plain). This applies only after STATIC_FILES lookup.
        content_type = ("text/javascript" if path.suffix.lower() in (".js", ".mjs")
                        else mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        if content_type.startswith("text/") or content_type in ("application/javascript",):
            content_type += "; charset=utf-8"
        self._send(200, body, content_type, cookie=self.path in ("/host/brain.html", "/host/selection.html"))

    def do_HEAD(self):
        return self.do_GET()

    def do_POST(self):
        try:
            self._api_guard(post=True)
            if self.path == "/api/v1/selection":
                # Gate before reading a larger body. No change to the default
                # 8 KiB request limit or to default-off import permissions.
                if self.server.engine._selection_store is None:
                    raise LocalServiceError("selection_intake_disabled", 403)
                value = self._read_json(65536)
                raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self._json(200, self.server.engine.import_selection(raw)); return
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
        self.httpd.engine.revoke()
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
                        catalogue: dict | None = None, enable_selection_intake: bool = False) -> LocalBrainServer:
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port must be 0..65535")
    repo_root = (Path(__file__).resolve().parents[2] if root is None else Path(root)).resolve()
    # Refuse surprising roots before opening a listener.
    for relative in ("host/brain.html", "host/brain.js", "companion/mygpt-pet.js"):
        if not (repo_root / relative).is_file():
            raise FileNotFoundError(relative)
    engine = LocalBrainEngine(catalogue=catalogue, authorization_seconds=authorization_seconds,
                              demo_delay_ms=demo_delay_ms, responder=responder, enable_selection_intake=enable_selection_intake)
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
    parser.add_argument("--enable-selection-intake", action="store_true",
                        help="Opt in to explicit one-record local input; source remains unverified, never sent to a provider")
    args = parser.parse_args()
    server = create_local_server(port=args.port, authorization_seconds=args.authorization_seconds,
                                 demo_delay_ms=args.demo_delay_ms, enable_selection_intake=args.enable_selection_intake)
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
