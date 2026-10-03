"""HTTPS security checks. TLS network traffic is exclusively a local fixture.

Production public-IP policy is never relaxed: the test-only mock dialer asserts
the validated public pin, then connects to its private TLS fixture. No external
hostname is contacted and no credentials/user progress are used.
"""
import base64
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('https_under_test', Path(__file__).with_name('https_callback.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class HttpsCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='book-https-test-')
        cls.cert = str(Path(cls.temp.name) / 'cert.pem')
        cls.key = str(Path(cls.temp.name) / 'key.pem')
        openssl = Path(r'C:\Program Files\Git\usr\bin\openssl.exe')
        if not openssl.is_file():
            raise RuntimeError('TLS test requires existing Git OpenSSL; not silently skipped.')
        subprocess.run([str(openssl), 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', cls.key, '-out', cls.cert, '-days', '1',
                        '-subj', '/CN=callback.test', '-addext', 'subjectAltName=DNS:callback.test'],
                       check=True, capture_output=True, timeout=15)
        cls.seen, cls.sni, cls.delivery_statuses = [], [], []
        cls.signing_key = 'whsec_' + base64.b64encode(b'fixture-key-32-bytes-never-secret!').decode()
        class Receiver(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                cls.seen.append({'path': self.path, 'host': self.headers['Host'], 'body': body,
                                 'headers': dict(self.headers)})
                if self.path in ('/signed', '/bad-challenge'):
                    from standardwebhooks.webhooks import Webhook
                    try:
                        payload = Webhook(cls.signing_key).verify(body.decode(), {k.lower(): v for k, v in self.headers.items()})
                    except Exception:
                        self.send_error(403)
                        return
                    if payload.get('type') != 'verification' and cls.delivery_statuses:
                        status = cls.delivery_statuses.pop(0)
                        self.send_response(status)
                        self.send_header('Content-Length', '0')
                        self.end_headers()
                        return
                    result = json.dumps({'challenge': payload['challenge'] if self.path == '/signed' else 'wrong'}).encode() if payload.get('type') == 'verification' else b'{}'
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(result)))
                    self.end_headers()
                    self.wfile.write(result)
                    return
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', 'https://callback.test/unwanted')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                result = b'x' * 8193 if self.path == '/oversize' else b'{"ok":true}'
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(result)))
                self.end_headers()
                if self.path == '/slow':
                    time.sleep(0.2)
                try:
                    self.wfile.write(result)
                except (OSError, ssl.SSLError):
                    pass
        cls.receiver = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cls.cert, cls.key)
        context.set_servername_callback(lambda sock, name, ctx: cls.sni.append(name))
        cls.receiver.socket = context.wrap_socket(cls.receiver.socket, server_side=True)
        cls.worker = threading.Thread(target=cls.receiver.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.receiver.shutdown()
        cls.receiver.server_close()
        cls.worker.join(timeout=2)
        cls.temp.cleanup()

    def setUp(self):
        self.seen.clear()
        self.sni.clear()
        self.delivery_statuses.clear()
        self.context = ssl.create_default_context(cafile=self.cert)
        self.pins = []

    def transport(self, **kwargs):
        return h.HttpsCallbackTransport(['callback.test'], ssl_context=self.context,
                                       resolver=lambda host, timeout: ['8.8.8.8'], **kwargs)

    def fixture_dial(self, address, port, timeout):
        self.assertEqual((address, port), ('8.8.8.8', 443))
        self.pins.append(address)
        return socket.create_connection(self.receiver.server_address, timeout)

    def test_exact_hosts_no_wildcards_ips_ports_paths_or_uppercase(self):
        for value in ('*.example.com', 'https://example.com', 'example.com:443',
                      '127.0.0.1', 'EXAMPLE.com', 'example.com.', 'example..com',
                      'localhost', 'example.com/x', 'example.com@attacker.test'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                h.HttpsCallbackTransport([value])

    def test_url_validation_blocks_ambiguous_or_out_of_scope_destinations(self):
        transport = self.transport()
        urls = ['http://callback.test/hook', 'https://127.0.0.1/hook',
                'https://callback.test.evil.test/hook', 'https://user@callback.test/hook',
                'https://callback.test:444/hook', 'https://callback.test/hook#',
                ' https://callback.test/hook', 'https://callback.test/\nhook',
                'https://CALLBACK.test/hook', 'https://callback.test\\evil/hook',
                'https://callback.test', 'https://callback.test./hook',
                'https://callback%2etest/hook']
        for url in urls:
            with self.subTest(url=url), self.assertRaises(h.CallbackError):
                transport.validate_url(url)
        self.assertEqual(transport.validate_url('https://callback.test:443/hook?token=fixture'),
                         ('callback.test', '/hook?token=fixture'))

    def test_private_reserved_translation_multicast_addresses_blocked(self):
        for ip in ('127.0.0.1', '10.0.0.1', '172.16.0.1', '192.168.1.1',
                   '169.254.169.254', '100.64.0.1', '0.0.0.0', '255.255.255.255',
                   '224.0.0.1', '192.0.2.1', '::1', '::', 'fe80::1', 'fc00::1',
                   '::ffff:8.8.8.8', '64:ff9b::808:808', '2002:808:808::1',
                   '2001:db8::1', 'ff02::1'):
            with self.subTest(ip=ip): self.assertFalse(h.public_address(ip))
        self.assertTrue(h.public_address('8.8.8.8'))
        self.assertTrue(h.public_address('2606:4700:4700::1111'))

    def test_mixed_public_private_dns_is_rejected_before_connect(self):
        transport = self.transport()
        transport.resolver = lambda host, timeout: ['8.8.8.8', '127.0.0.1']
        with patch.object(h, '_dial_pinned') as dial, self.assertRaises(h.CallbackError):
            transport.post('https://callback.test/hook', b'{}', {})
        dial.assert_not_called()

    def test_real_tls_public_pin_hostname_sni_and_exact_body(self):
        transport = self.transport()
        payload = '{"fixture":"涔?}'.encode()
        with patch.object(h, '_dial_pinned', self.fixture_dial):
            status, raw = transport.post('https://callback.test/hook', payload, {'Content-Type': 'application/json'})
        self.assertEqual((status, raw), (200, b'{"ok":true}'))
        self.assertEqual(self.pins, ['8.8.8.8'])
        self.assertEqual(self.sni, ['callback.test'])
        self.assertEqual(self.seen[0]['host'], 'callback.test')
        self.assertEqual(self.seen[0]['body'], payload)

    def test_dns_rebinding_checked_again_each_delivery(self):
        transport = self.transport()
        answers = iter([['8.8.8.8'], ['127.0.0.1']])
        transport.resolver = lambda host, timeout: next(answers)
        with patch.object(h, '_dial_pinned', self.fixture_dial):
            transport.post('https://callback.test/hook', b'{}', {})
            with self.assertRaises(h.CallbackError):
                transport.post('https://callback.test/hook', b'{"private":"not-sent"}', {})
        self.assertEqual(len(self.seen), 1)

    def test_real_tls_rejects_untrusted_certificate_without_body_leak(self):
        transport = h.HttpsCallbackTransport(['callback.test'], resolver=lambda host, timeout: ['8.8.8.8'])
        with patch.object(h, '_dial_pinned', self.fixture_dial), self.assertRaises(h.CallbackError) as error:
            transport.post('https://callback.test/hook', b'{"private":"not-sent"}', {})
        self.assertEqual(error.exception.reason, 'tls_error')
        self.assertEqual(self.seen, [])

    def test_real_tls_rejects_hostname_mismatch_without_body_leak(self):
        transport = h.HttpsCallbackTransport(['other.test'], ssl_context=self.context,
                                            resolver=lambda host, timeout: ['8.8.8.8'])
        with patch.object(h, '_dial_pinned', self.fixture_dial), self.assertRaises(h.CallbackError) as error:
            transport.post('https://other.test/hook', b'{"private":"not-sent"}', {})
        self.assertEqual(error.exception.reason, 'tls_error')
        self.assertEqual(self.seen, [])

    def test_redirect_does_not_make_a_second_request(self):
        with patch.object(h, '_dial_pinned', self.fixture_dial), self.assertRaises(h.CallbackError):
            self.transport().post('https://callback.test/redirect', b'{}', {})
        self.assertEqual([item['path'] for item in self.seen], ['/redirect'])

    def test_response_bound_and_proxy_environment_ignored(self):
        with patch.dict(os.environ, {'HTTPS_PROXY': 'http://127.0.0.1:1', 'HTTP_PROXY': 'http://127.0.0.1:1'}):
            with patch.object(h, '_dial_pinned', self.fixture_dial), self.assertRaises(h.CallbackError):
                self.transport().post('https://callback.test/oversize', b'{}', {})
        self.assertEqual(len(self.seen), 1)

    def test_unverified_tls_context_rejected(self):
        with self.assertRaises(ValueError):
            h.HttpsCallbackTransport(['callback.test'], ssl_context=ssl._create_unverified_context())

    def test_total_response_deadline_aborts_slow_receiver(self):
        with patch.object(h, '_dial_pinned', self.fixture_dial), self.assertRaises(h.CallbackError) as error:
            start = time.monotonic()
            self.transport(timeout=0.08).post('https://callback.test/slow', b'{}', {})
        self.assertLess(time.monotonic() - start, 0.18)
        self.assertEqual(error.exception.reason, 'timeout')

    def test_dns_timeout_and_error_are_bounded_and_redacted(self):
        def slow(*args, **kwargs):
            time.sleep(0.08)
            return []
        with patch.object(h.socket, 'getaddrinfo', slow):
            start = time.monotonic()
            with self.assertRaises(h.CallbackError) as error:
                h.resolve_addresses('private-name.test', 0.01)
            self.assertLess(time.monotonic() - start, 0.07)
            self.assertEqual(str(error.exception), 'HTTPS callback failed.')
        time.sleep(0.08)

    def load_server(self):
        spec = importlib.util.spec_from_file_location('https_test_overlay', Path(__file__).with_name('run_mcp_bridge.py'))
        overlay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(overlay)
        return overlay.load_overlay()

    def subscription(self, path='/signed', secret=None):
        return {'name': 'book.study.progress.updated', 'arguments': {'producer_session': 'https-fixture'},
                'delivery': {'mode': 'webhook', 'url': 'https://callback.test' + path,
                             'secret': secret or self.signing_key}, 'ttlMs': 10000}

    def test_https_signed_challenge_rotation_and_persistent_subscription(self):
        server = self.load_server()
        with tempfile.TemporaryDirectory(prefix='https-subscription-test-') as state:
            delivery = server.EventDelivery(server.StudyBridge(), state, 'fixture-owner', https_callback_hosts=['callback.test'])
            delivery.https = self.transport()
            delivery.worker.start()
            try:
                with patch.object(h, '_dial_pinned', self.fixture_dial):
                    first = delivery.subscribe(self.subscription())
                    verified_at = delivery.record.verified_at
                    again = delivery.subscribe(self.subscription())
                    self.assertEqual(first['id'], again['id'])
                    self.assertEqual(delivery.record.verified_at, verified_at)
                    self.assertEqual(len(self.seen), 1)
                    old_key = self.signing_key
                    new_key = 'whsec_' + base64.b64encode(b'new-fixture-key-32-bytes-long----').decode()
                    # Receiver still verifies the old key during rotation;
                    # the signed challenge carries both key versions.
                    rotated = delivery.subscribe(self.subscription(secret=new_key))
                    self.assertEqual(first['id'], rotated['id'])
                    self.assertEqual(delivery.record.previous_secret, old_key)
                    self.assertEqual(delivery.record.secret, new_key)
                    self.assertEqual(len(self.seen[-1]['headers']['webhook-signature'].split()), 2)
                restored = server.EventDelivery(server.StudyBridge(), state, 'fixture-owner', https_callback_hosts=['callback.test'])
                self.assertEqual(restored.record.id, first['id'])
                self.assertEqual(restored.delivery_mode, 'https_configured')
                refused = server.EventDelivery(server.StudyBridge(), state, 'fixture-owner', https_callback_hosts=['other.test'])
                self.assertIsNone(refused.record)
                self.assertFalse(delivery.status()['real_dot_connected'])
            finally:
                delivery.stop.set()
                delivery.worker.join(timeout=2)

    def test_failed_https_challenge_never_activates_subscription(self):
        server = self.load_server()
        with tempfile.TemporaryDirectory(prefix='https-subscription-failure-') as state:
            delivery = server.EventDelivery(server.StudyBridge(), state, 'fixture-owner', https_callback_hosts=['callback.test'])
            delivery.https = self.transport()
            delivery.worker.start()
            try:
                with patch.object(h, '_dial_pinned', self.fixture_dial), self.assertRaises(server.RpcError) as error:
                    delivery.subscribe(self.subscription('/bad-challenge'))
                self.assertEqual(error.exception.code, -32015)
                self.assertIsNone(delivery.record)
                self.assertFalse(delivery.path.exists())
                self.assertEqual(len(self.seen), 1)
            finally:
                delivery.stop.set()
                delivery.worker.join(timeout=2)

    def test_outbound_modes_mutually_exclusive_and_default_disabled(self):
        server = self.load_server()
        with tempfile.TemporaryDirectory(prefix='https-mode-test-') as state:
            default = server.EventDelivery(server.StudyBridge(), state, 'fixture-owner')
            self.assertFalse(default.enabled)
            self.assertEqual(default.delivery_mode, 'disabled')
            with self.assertRaises(ValueError):
                server.EventDelivery(server.StudyBridge(), state, 'fixture-owner',
                                     'http://127.0.0.1:1/hook', ['callback.test'])

    def test_https_worker_retry_signed_exact_body_and_unsubscribe(self):
        server = self.load_server()
        with tempfile.TemporaryDirectory(prefix='https-worker-test-') as state:
            bridge = server.StudyBridge()
            delivery = server.EventDelivery(bridge, state, 'fixture-owner', https_callback_hosts=['callback.test'])
            delivery.https = self.transport()
            delivery.worker.start()
            try:
                with patch.object(h, '_dial_pinned', self.fixture_dial):
                    subscription = self.subscription()
                    delivery.subscribe(subscription)
                    self.delivery_statuses.extend([503, 200])
                    stamp = datetime.now(timezone.utc)
                    progress = {'schema': 'book.study-progress.v1', 'producer_session': 'https-fixture',
                                'sequence': 1, 'captured_at': stamp.isoformat(),
                                'expires_at': (stamp + timedelta(seconds=15)).isoformat(),
                                'status': 'disabled', 'visible_seconds': 0, 'idle_seconds': 0,
                                'can_interact': False, 'context': None}
                    bridge.ingest(progress)
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline and delivery.received_count == 0:
                        time.sleep(0.02)
                    self.assertEqual(delivery.received_count, 1)
                    delivered = [item for item in self.seen if 'eventId' in json.loads(item['body'])]
                    self.assertEqual(len(delivered), 2)
                    self.assertEqual(delivered[0]['body'], delivered[1]['body'])
                    self.assertEqual(delivered[0]['headers']['webhook-id'], delivered[1]['headers']['webhook-id'])
                    self.assertEqual(delivery.status()['delivery_status'], 'callback_received_not_decided')
                    delivery.unsubscribe(subscription)
                    progress['sequence'] = 2
                    bridge.ingest(progress)
                    time.sleep(0.15)
                    self.assertEqual(len(self.seen), 3)
                    self.assertFalse(delivery.status()['subscription_active'])
            finally:
                delivery.stop.set()
                delivery.worker.join(timeout=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)

