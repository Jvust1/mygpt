"""Explicit-host HTTPS webhook transport, never a dot identity/authenticator.

No proxies, redirects, ambient cookies, DNS re-resolution on connect, or local
address exceptions. Test harnesses may inject a resolver/dialer by mocking;
there is deliberately no CLI/environment switch to relax address/TLS policy.
"""
from __future__ import annotations

from http.client import HTTPSConnection
import ipaddress
import re
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit


class CallbackError(ValueError):
    def __init__(self, reason='challenge_failed'):
        super().__init__('HTTPS callback failed.')
        self.reason = reason


def exact_host(value):
    if (not isinstance(value, str) or value != value.lower() or len(value) > 253
            or '.' not in value or not re.fullmatch(
                r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?', value)):
        raise ValueError('Use an exact lowercase DNS hostname, without scheme, port or wildcard.')
    return value


def public_address(value):
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if not ip.is_global or ip.is_reserved or ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # Exclude mapped/translation/tunnel ranges rather than guessing their
        # effective IPv4 destination. Ordinary globally routed v6 is 2000::/3.
        if ip not in ipaddress.ip_network('2000::/3') or ip.ipv4_mapped or ip.sixtofour or ip.teredo:
            return False
    return True


_dns_slots = threading.BoundedSemaphore(4)


def resolve_addresses(host, timeout):
    """Bound OS DNS waits without allowing unbounded abandoned resolver threads."""
    if not _dns_slots.acquire(blocking=False):
        raise CallbackError('timeout')
    complete, results = threading.Event(), []
    def lookup():
        try:
            results.append(socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
        except Exception:
            results.append(None)
        finally:
            _dns_slots.release()
            complete.set()
    threading.Thread(target=lookup, name='https-callback-dns', daemon=True).start()
    if not complete.wait(timeout):
        raise CallbackError('timeout')
    if not results[0]:
        raise CallbackError('connection_refused')
    return list(dict.fromkeys(row[4][0] for row in results[0]))


def _dial_pinned(address, port, timeout):
    """Literal socket.connect avoids a second hostname lookup after validation."""
    ip = ipaddress.ip_address(address)
    sock = socket.socket(socket.AF_INET6 if ip.version == 6 else socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((str(ip), port, 0, 0) if ip.version == 6 else (str(ip), port))
        return sock
    except BaseException:
        sock.close()
        raise


class _PinnedHTTPSConnection(HTTPSConnection):
    def __init__(self, host, address, *, timeout, context):
        super().__init__(host, 443, timeout=timeout, context=context)
        self.address = address

    def connect(self):
        raw = _dial_pinned(self.address, self.port, self.timeout)
        self.sock = raw  # Deadline watchdog can abort an in-progress TLS handshake.
        try:
            # Original hostname supplies both TLS SNI and certificate matching.
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            self.sock = None
            raise


class HttpsCallbackTransport:
    def __init__(self, allowed_hosts, *, resolver=None, ssl_context=None, timeout=2):
        self.allowed_hosts = frozenset(exact_host(value) for value in allowed_hosts)
        if not self.allowed_hosts or not 0 < timeout <= 10:
            raise ValueError('At least one exact HTTPS callback host and bounded timeout are required.')
        self.resolver = resolver or resolve_addresses
        self.context = ssl_context or ssl.create_default_context()
        if not self.context.check_hostname or self.context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError('Certificate and hostname verification must remain enabled.')
        self.timeout = timeout

    def validate_url(self, url):
        if (not isinstance(url, str) or not 1 <= len(url) <= 1024
                or any(not 33 <= ord(c) <= 126 for c in url) or '\\' in url or '#' in url):
            raise CallbackError()
        try:
            p = urlsplit(url)
            host = p.hostname
            if (p.scheme != 'https' or not host or host not in self.allowed_hosts
                    or p.username is not None or p.password is not None or p.port not in (None, 443)
                    or p.netloc not in (host, host + ':443') or not p.path.startswith('/')):
                raise ValueError()
        except ValueError:
            raise CallbackError() from None
        return host, p.path + ('?' + p.query if p.query else '')

    def post(self, url, body, headers):
        # Treat headers as internal signed metadata, not an arbitrary HTTP API.
        host, path = self.validate_url(url)
        if not isinstance(body, bytes) or len(body) > 8192:
            raise CallbackError()
        deadline = time.monotonic() + self.timeout
        connection = timer = None
        try:
            addresses = self.resolver(host, self.timeout)
            if not addresses or len(addresses) > 64 or any(not public_address(ip) for ip in addresses):
                raise CallbackError()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CallbackError('timeout')
            connection = _PinnedHTTPSConnection(host, addresses[0], timeout=remaining, context=self.context)
            def abort():
                if connection.sock is not None:
                    try:
                        connection.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                connection.close()
            timer = threading.Timer(remaining, abort)
            timer.daemon = True
            timer.start()
            connection.request('POST', path, body, headers={**headers, 'Content-Length': str(len(body)), 'Connection': 'close'})
            response = connection.getresponse()
            if 300 <= response.status < 400:
                raise CallbackError('http_4xx')
            if not 200 <= response.status < 300:
                return response.status, b''
            raw = response.read(8193)
            if len(raw) > 8192:
                raise CallbackError()
            if time.monotonic() >= deadline:
                raise CallbackError('timeout')
            return response.status, raw
        except CallbackError:
            raise
        except ssl.SSLError:
            raise CallbackError('tls_error') from None
        except (TimeoutError, socket.timeout):
            raise CallbackError('timeout') from None
        except Exception:
            raise CallbackError('timeout' if time.monotonic() >= deadline else 'connection_refused') from None
        finally:
            if timer is not None:
                timer.cancel()
            if connection is not None:
                connection.close()

