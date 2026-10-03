"""Loopback-listening MCP 2.0 study bridge; NOT a connected Your dot.

Protocol: https://developers.openai.com/plugins/build/mcp-events
Local HTTP callbacks remain a TEST extension. Explicit-host HTTPS callbacks
are optional outbound delivery, not plugin registration or dot authentication.
No shell/filesystem tools, models or renderer.
"""
from __future__ import annotations

import argparse
import base64
from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import Annotated, Literal
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler, Request
from urllib.error import HTTPError

from pydantic import AwareDatetime, Field
from standardwebhooks.webhooks import Webhook
from .core import Contract
from .dot_events import EVENT_NAME, PROTOCOL_VERSION, SubscriptionArguments, event_definition
from .mcp_bridge_core import StudyBridge, tool_definitions
from .https_callback import HttpsCallbackTransport, CallbackError

MAX_BODY = 16384
SERVER_INFO = {'name': 'book-mygpt-study-bridge-local', 'version': '0.1.0'}


def now():
    return datetime.now(timezone.utc)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


class RpcError(Exception):
    def __init__(self, code, message, status=400, data=None):
        super().__init__(message)
        self.code, self.status, self.data = code, status, data


class Delivery(Contract):
    mode: Literal['webhook']
    url: Annotated[str, Field(strict=True, min_length=1, max_length=1024)]
    secret: Annotated[str, Field(strict=True, min_length=10, max_length=100)] | None = None


class SubscriptionInput(Contract):
    name: Literal['book.study.progress.updated']
    arguments: SubscriptionArguments
    delivery: Delivery
    cursor: None = None
    ttlMs: Annotated[int, Field(strict=True, ge=1, le=2**53-1)] | None = None


class SavedSubscription(Contract):
    id: str
    owner: str
    arguments: SubscriptionArguments
    url: str
    secret: str
    refresh_before: AwareDatetime
    verified_at: AwareDatetime
    previous_secret: str | None = None
    rotation_until: AwareDatetime | None = None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('callback redirects are prohibited')


def local_url(url):
    if not isinstance(url, str) or any(not 33 <= ord(c) <= 126 for c in url):
        raise ValueError('invalid local callback URL')
    p = urlsplit(url)
    if (p.scheme != 'http' or p.hostname != '127.0.0.1' or p.username or p.password
            or p.port is None or not 1 <= p.port <= 65535 or p.query or p.fragment
            or not p.path.startswith('/') or p.netloc != '127.0.0.1:' + str(p.port)):
        raise ValueError('Only an explicit literal 127.0.0.1 callback is allowed in this LOCAL test.')
    return url


def key_bytes(secret):
    if not isinstance(secret, str) or not secret.startswith('whsec_'):
        raise ValueError('invalid webhook key')
    value = base64.b64decode(secret[6:], validate=True)
    if not 24 <= len(value) <= 64 or base64.b64encode(value).decode() != secret[6:]:
        raise ValueError('invalid webhook key length or encoding')
    return value


class EventDelivery:
    def __init__(self, bridge, state_dir, owner, allowed_callback=None, https_callback_hosts=None):
        self.bridge, self.owner = bridge, owner
        if allowed_callback and https_callback_hosts:
            raise ValueError('Local-test and HTTPS callback modes are mutually exclusive.')
        self.allowed = local_url(allowed_callback) if allowed_callback else None
        self.https = HttpsCallbackTransport(https_callback_hosts) if https_callback_hosts else None
        self.delivery_mode = 'https_configured' if self.https else ('local_test' if self.allowed else 'disabled')
        self.lock, self.stop = threading.RLock(), threading.Event()
        self.record = None
        self.last_status = 'not_subscribed'
        self.blocked_event = None
        self.received_count = 0
        self.path = Path(state_dir).resolve() / 'subscription.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            if self.path.is_symlink() or self.path.stat().st_size > 8192:
                raise ValueError('invalid subscription storage')
            data = decode(self.path.read_bytes())
            if data is not None:
                record = SavedSubscription.model_validate(data)
                key_bytes(record.secret)
                if record.previous_secret:
                    key_bytes(record.previous_secret)
                if record.owner == owner and record.refresh_before > now():
                    try:
                        self.validate_callback(record.url)
                    except ValueError:
                        pass  # A changed allowlist must not revive an old subscription.
                    else:
                        self.record = record
        self.worker = threading.Thread(target=self.run, name='local-mcp-events', daemon=True)

    @property
    def enabled(self):
        return self.delivery_mode != 'disabled'

    def validate_callback(self, url):
        if self.https:
            self.https.validate_url(url)
        elif self.allowed and url == self.allowed:
            local_url(url)
        else:
            raise ValueError('Callback is outside the explicitly configured mode/allowlist.')

    def save(self):
        body = encode(self.record.model_dump(mode='json') if self.record else None)
        temporary = self.path.with_name('.subscription-' + secrets.token_hex(8) + '.tmp')
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def post(self, record, event_id, body):
        self.validate_callback(record.url)
        timestamp = now()
        signer = Webhook(record.secret)
        signatures = [signer.sign(event_id, timestamp, body.decode('utf-8'))]
        if record.previous_secret and record.rotation_until and record.rotation_until > timestamp:
            signatures.append(Webhook(record.previous_secret).sign(event_id, timestamp, body.decode('utf-8')))
        headers = {
            'Content-Type': 'application/json', 'webhook-id': event_id,
            'webhook-timestamp': str(int(timestamp.timestamp())),
            'webhook-signature': ' '.join(signatures), 'X-MCP-Subscription-Id': record.id}
        if self.https:
            return self.https.post(record.url, body, headers)
        request = Request(record.url, data=body, method='POST', headers=headers)
        opener = build_opener(ProxyHandler({}), NoRedirect())
        try:
            with opener.open(request, timeout=2) as response:
                raw = response.read(8193)
                if len(raw) > 8192:
                    raise ValueError('callback response too large')
                return response.status, raw
        except HTTPError as error:
            try:
                return error.code, b''
            finally:
                error.close()

    def subscribe(self, params):
        parsed = SubscriptionInput.model_validate(params)
        try:
            self.validate_callback(parsed.delivery.url)
        except ValueError:
            raise RpcError(-32602, 'Callback is outside the configured allowlist.') from None
        key_bytes(parsed.delivery.secret)
        identity = [self.owner, parsed.delivery.url, EVENT_NAME, parsed.arguments.model_dump()]
        sid = 'sub-' + hashlib.sha256(encode(identity)).hexdigest()[:40]
        with self.lock:
            if self.stop.is_set() or not self.worker.is_alive():
                raise RpcError(-32603, 'Local event worker unavailable; restart required.', 503)
            previous = self.record
            if previous and previous.refresh_before > now() and previous.id != sid:
                raise RpcError(-32602, 'This local prototype supports one subscription; unsubscribe first.')
            stamp = now()
            lifetime = min(parsed.ttlMs if parsed.ttlMs is not None else 3600000, 86400000)
            record = SavedSubscription(id=sid, owner=self.owner, arguments=parsed.arguments,
                url=parsed.delivery.url, secret=parsed.delivery.secret,
                refresh_before=stamp + timedelta(milliseconds=lifetime), verified_at=stamp)
            if previous and previous.id == sid and previous.refresh_before > stamp:
                if previous.secret != record.secret:
                    record = record.model_copy(update={'previous_secret': previous.secret, 'rotation_until': stamp + timedelta(minutes=5)})
                elif previous.rotation_until and previous.rotation_until > stamp:
                    record = record.model_copy(update={'previous_secret': previous.previous_secret, 'rotation_until': previous.rotation_until})
            cached = (previous and previous.id == sid and previous.secret == record.secret
                      and previous.refresh_before > stamp and previous.verified_at + timedelta(minutes=5) > stamp)
            if cached:
                record = record.model_copy(update={'verified_at': previous.verified_at})
            if not cached:
                challenge = secrets.token_urlsafe(32)
                try:
                    status, raw = self.post(record, 'verify-' + secrets.token_hex(16), encode({'type': 'verification', 'challenge': challenge}))
                    reply = decode(raw)
                    if not 200 <= status < 300 or not isinstance(reply, dict) or not isinstance(reply.get('challenge'), str) or not hmac.compare_digest(reply['challenge'].encode(), challenge.encode()):
                        raise ValueError('challenge mismatch')
                except Exception as error:
                    reason = error.reason if isinstance(error, CallbackError) else 'challenge_failed'
                    raise RpcError(-32015, 'Callback verification failed.', data={'reason': reason}) from None
                # The granted lease starts only after verification actually succeeds.
                record = record.model_copy(update={'verified_at': now(), 'refresh_before': now() + timedelta(milliseconds=lifetime)})
            self.record = record
            try:
                self.save()
            except Exception:
                self.record = previous
                raise
            self.blocked_event = None
            self.last_status = 'https_callback_verified_not_dot' if self.https else 'local_callback_verified_not_dot'
            return {'id': sid, 'refreshBefore': record.refresh_before.isoformat(), 'cursor': None, 'truncated': False}

    def unsubscribe(self, params):
        parsed = SubscriptionInput.model_validate(params)
        identity = [self.owner, parsed.delivery.url, EVENT_NAME, parsed.arguments.model_dump()]
        sid = 'sub-' + hashlib.sha256(encode(identity)).hexdigest()[:40]
        with self.lock:
            if self.record and self.record.id == sid:
                self.record = None
                self.save()
            self.last_status = 'unsubscribed'
        return {}

    def status(self):
        with self.lock:
            return {'subscription_active': bool(not self.stop.is_set() and self.worker.is_alive()
                                                and self.record and self.record.refresh_before > now()),
                    'delivery_status': self.last_status, 'callback_receipts': self.received_count,
                    'worker_alive': self.worker.is_alive(),
                    'delivery_mode': self.delivery_mode,
                    'real_dot_connected': False}

    def run(self):
        try:
            self._run()
        except Exception:
            # A failed background worker cannot leave a healthy-looking active
            # subscription. Do not include private paths/payloads in diagnostics.
            with self.lock:
                self.record = None
                self.last_status = 'worker_failed_closed'
                self.stop.set()

    def _run(self):
        while not self.stop.wait(0.1):
            with self.lock:
                record = self.record
                if not record:
                    continue
                if record.refresh_before <= now():
                    self.record = None
                    self.save()
                    continue
                event = self.bridge.next_event(record.arguments.model_dump())
                if event is None or event['eventId'] == self.blocked_event:
                    continue
                body = encode(event)
                if len(body) > 8192:
                    self.blocked_event = event['eventId']
                    continue
                for attempt in range(3):
                    latest = self.bridge.next_event(record.arguments.model_dump())
                    if self.stop.is_set() or self.record is not record or record.refresh_before <= now() or not latest or latest['eventId'] != event['eventId']:
                        break
                    try:
                        status, _ = self.post(record, event['eventId'], body)
                    except Exception:
                        status = 503
                    if 200 <= status < 300:
                        self.bridge.callback_received(event['eventId'])
                        self.received_count += 1
                        self.last_status = 'callback_received_not_decided'
                        break
                    self.last_status = 'callback_delivery_failed'
                    if status == 410:
                        self.record = None
                        self.save()
                    if status in (410, 413) or (400 <= status < 500 and status != 429):
                        self.blocked_event = event['eventId']
                        break
                    if attempt == 2:
                        self.blocked_event = event['eventId']
                    else:
                        self.stop.wait(0.2 * 2 ** attempt)


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, port, mcp_token, ingest_token, state_dir, callback=None, https_callback_hosts=None):
        for token in (mcp_token, ingest_token):
            if not isinstance(token, str) or len(token) < 32 or len(token) > 256 or not token.isascii() or any(c.isspace() for c in token):
                raise ValueError('Provide two distinct random ASCII tokens of at least 32 characters.')
        if hmac.compare_digest(mcp_token, ingest_token):
            raise ValueError('MCP and ingestion tokens must be different.')
        self.bridge = StudyBridge()
        self.mcp_token, self.ingest_token = mcp_token, ingest_token
        self.requests, self.rate_lock = deque(), threading.Lock()
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = 'http://127.0.0.1:' + str(self.server_port)
        self.events = EventDelivery(self.bridge, state_dir, hashlib.sha256(mcp_token.encode()).hexdigest(), callback, https_callback_hosts)
        self.events.worker.start()

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def server_close(self):
        if hasattr(self, 'events'):
            self.events.stop.set()
            self.events.worker.join(timeout=3)
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    server_version = 'BookMCP/0.1'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(3)

    def log_message(self, *args):
        pass  # never log tokens, arguments, progress or callback secrets

    def send(self, status, value=None, extra=None):
        body = b'' if value is None else encode(value)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)
        self.close_connection = True

    def authorize(self):
        expected_host = self.server.origin[7:]
        if (self.headers.get_all('Host') != [expected_host] or len(self.headers.get_all('Origin', [])) > 1
                or self.headers.get('Origin') not in (None, self.server.origin)):
            self.send(403, {'error': 'invalid_origin_or_host'})
            return False
        if self.path not in ('/mcp', '/health', '/local/progress', '/local/decisions/take', '/local/disconnect'):
            self.send(404, {'error': 'not_found'})
            return False
        token = self.server.ingest_token if self.path.startswith('/local/') else self.server.mcp_token
        auth = self.headers.get('Authorization', '')
        if len(self.headers.get_all('Authorization', [])) != 1 or not hmac.compare_digest(auth.encode('utf-8'), ('Bearer ' + token).encode()):
            self.send(401, {'error': 'unauthorized'}, {'WWW-Authenticate': 'Bearer realm="local-mcp-test"'})
            return False
        with self.server.rate_lock:
            stamp = time.monotonic()
            while self.server.requests and self.server.requests[0] < stamp - 60:
                self.server.requests.popleft()
            if len(self.server.requests) >= 240:
                self.send(429, {'error': 'rate_limited'}, {'Retry-After': '60'})
                return False
            self.server.requests.append(stamp)
        return True

    def do_GET(self):
        if not self.authorize():
            return
        if self.path == '/health':
            self.send(200, {'status': 'local_prototype', 'protocol': PROTOCOL_VERSION,
                           'real_dot_connected': False, 'model_calls': 0, **self.server.events.status()})
        else:
            self.send(405, {'error': 'method_not_allowed'}, {'Allow': 'POST'})

    def do_DELETE(self):
        if self.authorize():
            self.send(405, {'error': 'method_not_allowed'}, {'Allow': 'POST'})

    def do_POST(self):
        if not self.authorize():
            return
        request_id = None
        try:
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                raise RpcError(-32600, 'A bounded Content-Length is required.')
            length = int(self.headers['Content-Length'])
            if not 0 < length <= MAX_BODY:
                raise RpcError(-32600, 'Request body exceeds the local limit.', 413)
            if self.headers.get_content_type() != 'application/json':
                raise RpcError(-32600, 'Content-Type must be application/json.', 415)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise RpcError(-32700, 'Incomplete JSON request.')
            try:
                value = decode(raw)
            except (ValueError, UnicodeError):
                raise RpcError(-32700, 'Invalid JSON request.') from None
            if self.path.startswith('/local/'):
                if not isinstance(value, dict):
                    raise ValueError('invalid local object')
                if self.path == '/local/progress':
                    result = self.server.bridge.ingest(value)
                elif value:
                    raise ValueError('empty object required')
                elif self.path == '/local/decisions/take':
                    result = self.server.bridge.take_decision()
                else:
                    result = self.server.bridge.disconnect()
                self.send(200, result)
                return
            if self.path != '/mcp':
                raise RpcError(-32601, 'Method not found.', 404)
            if not isinstance(value, dict) or set(value) != {'jsonrpc', 'id', 'method', 'params'} or value.get('jsonrpc') != '2.0':
                raise RpcError(-32600, 'A single JSON-RPC 2.0 request is required.')
            request_id = value['id']
            if type(request_id) not in (str, int) or (isinstance(request_id, str) and len(request_id) > 96):
                request_id = None
                raise RpcError(-32600, 'Invalid request ID.')
            method, params = value['method'], value['params']
            if not isinstance(method, str) or not isinstance(params, dict):
                raise RpcError(-32600, 'Invalid method or parameters.')
            meta = params.get('_meta')
            if not isinstance(meta, dict) or not isinstance(meta.get('io.modelcontextprotocol/clientCapabilities'), dict) or 'io.modelcontextprotocol/protocolVersion' not in meta:
                raise RpcError(-32602, 'MCP protocol metadata is required.')
            version = meta['io.modelcontextprotocol/protocolVersion']
            if version != PROTOCOL_VERSION:
                raise RpcError(-32022, 'Unsupported protocol version.', data={'supported': [PROTOCOL_VERSION], 'requested': version})
            if self.headers.get('MCP-Protocol-Version') != version or self.headers.get('Mcp-Method') != method:
                raise RpcError(-32020, 'MCP headers do not match the body.')
            if any(len(self.headers.get_all(h, [])) > 1 for h in ('MCP-Protocol-Version', 'Mcp-Method', 'Mcp-Name')):
                raise RpcError(-32020, 'Duplicate MCP mirror headers are prohibited.')
            name_header = self.headers.get('Mcp-Name')
            if name_header is not None and name_header.startswith('=?base64?'):
                try:
                    if not name_header.endswith('?='):
                        raise ValueError('invalid encoded header')
                    name_header = base64.b64decode(name_header[9:-2], validate=True).decode('utf-8')
                except (ValueError, UnicodeError):
                    raise RpcError(-32020, 'Invalid encoded MCP name.') from None
            if (method == 'tools/call' and name_header != params.get('name')) or (method != 'tools/call' and name_header is not None):
                raise RpcError(-32020, 'MCP name does not match the body.')
            accept = self.headers.get('Accept', '')
            if 'application/json' not in accept or 'text/event-stream' not in accept:
                raise RpcError(-32600, 'Accept must include JSON and event-stream.', 406)
            args = {k: v for k, v in params.items() if k != '_meta'}
            if method == 'server/discover':
                if args:
                    raise ValueError('unexpected discovery arguments')
                result = {'supportedVersions': [PROTOCOL_VERSION], 'capabilities': {'tools': {}, **({'events': {}} if self.server.events.enabled else {})}}
            elif method == 'tools/list':
                if args:
                    raise ValueError('unexpected tools/list arguments')
                result = {'tools': tool_definitions(), 'ttlMs': 60000, 'cacheScope': 'private'}
            elif method == 'tools/call':
                if set(args) != {'name', 'arguments'} or not isinstance(args['arguments'], dict):
                    raise ValueError('invalid tool call arguments')
                if args['name'] not in {x['name'] for x in tool_definitions()}:
                    raise RpcError(-32602, 'Unknown tool.')
                try:
                    payload = self.server.bridge.call_tool(args['name'], args['arguments'])
                    result = {'content': [{'type': 'text', 'text': encode(payload).decode()}], 'structuredContent': payload}
                except ValueError:
                    result = {'isError': True, 'content': [{'type': 'text', 'text': 'Study request rejected: invalid, stale, conflicting or inactive evidence.'}]}
            elif method == 'events/list':
                if args:
                    raise ValueError('unexpected events/list arguments')
                result = {'events': [event_definition()] if self.server.events.enabled else []}
            elif method == 'events/subscribe':
                result = self.server.events.subscribe(args)
            elif method == 'events/unsubscribe':
                result = self.server.events.unsubscribe(args)
            else:
                raise RpcError(-32601, 'Method not found.', 404)
            result = {**result, 'resultType': 'complete', '_meta': {'io.modelcontextprotocol/serverInfo': SERVER_INFO}}
            self.send(200, {'jsonrpc': '2.0', 'id': request_id, 'result': result})
        except RpcError as error:
            value = {'code': error.code, 'message': str(error)}
            if error.data is not None:
                value['data'] = error.data
            self.send(error.status, {'jsonrpc': '2.0', **({'id': request_id} if request_id is not None else {}), 'error': value})
        except (ValueError, TypeError, KeyError):
            self.send(400, {'jsonrpc': '2.0', **({'id': request_id} if request_id is not None else {}), 'error': {'code': -32602, 'message': 'Invalid parameters.'}})
        except Exception:
            self.send(500, {'jsonrpc': '2.0', **({'id': request_id} if request_id is not None else {}), 'error': {'code': -32603, 'message': 'Local bridge internal error.'}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--allow-local-test-callback', default=None)
    parser.add_argument('--allow-https-callback-host', action='append', default=[],
                        help='Exact lowercase HTTPS callback DNS host; repeat for multiple hosts. Port 443 only.')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be 0..65535')
    server = BridgeServer(args.port, os.environ.get('MCP_BRIDGE_TOKEN'), os.environ.get('MYGPT_INGEST_TOKEN'), args.state_dir, args.allow_local_test_callback, args.allow_https_callback_host)
    print(json.dumps({'event': 'mcp_bridge_listening', 'url': server.origin + '/mcp', 'protocol': PROTOCOL_VERSION,
                      'local_only': True, 'delivery_mode': server.events.delivery_mode, 'real_dot_connected': False}), flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

