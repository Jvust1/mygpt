"""Real loopback HTTP fixture, synthetic peer: no Your dot/model/Live contact."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

from test_book_progress import bridge, PRODUCER

spec = importlib.util.spec_from_file_location("mygpt_brain.mcp_bridge_client", Path(__file__).with_name("mcp_bridge_client.py"))
client_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = client_module
spec.loader.exec_module(client_module)

TOKEN = "synthetic-ingest-credential-not-a-real-secret"


class ClientTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = []
        cls.status = 200
        cls.content_type = "application/json"
        cls.response = {}
        cls.location = None

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                cls.requests.append((self.path, self.headers.get("Authorization"), json.loads(raw)))
                self.send_response(cls.status)
                self.send_header("Content-Type", cls.content_type)
                if cls.location: self.send_header("Location", cls.location)
                body = cls.response if isinstance(cls.response, bytes) else json.dumps(cls.response).encode()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args): pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        type(self).requests = []
        type(self).status = 200
        type(self).content_type = "application/json"
        type(self).response = {"status": "accepted_locally_not_dot_delivery"}
        type(self).location = None
        self.client = client_module.LocalMcpBridgeClient(self.origin, TOKEN)
        self.feedback = {"schema": "mygpt.dot-study-feedback.v1",
                         "progress": deepcopy(PRODUCER["snapshots"][1]),
                         "interpretation": "position is not comprehension; idle is not proof of distraction"}

    def decision(self):
        now = datetime.now(timezone.utc)
        return {"schema_version": "mygpt.dot-study-decision.v1", "decision_id": "synthetic-local-client-decision",
                "producer_session": self.feedback["progress"]["producer_session"],
                "progress_sequence": self.feedback["progress"]["sequence"], "action": "stay_quiet",
                "captured_at": now.isoformat(), "expires_at": (now + timedelta(seconds=10)).isoformat(),
                "objective": None}

    async def test_report_sends_only_validated_progress_and_local_ingest_token(self):
        self.assertIsNone(await self.client.report(self.feedback))
        path, auth, payload = self.requests[0]
        self.assertEqual(path, "/local/progress")
        self.assertEqual(auth, "Bearer " + TOKEN)
        self.assertEqual(payload, bridge.BookProgress.model_validate(self.feedback["progress"]).wire())
        self.assertNotIn("interpretation", payload)
        self.assertNotIn("PRIVATE_", json.dumps(payload))

    async def test_rejects_extra_private_fields_and_wrong_feedback_without_http(self):
        values = []
        for key, value in [("notes", "PRIVATE_DATA"), ("schema", "other"), ("interpretation", "untrusted instruction")]:
            feedback = deepcopy(self.feedback); feedback[key] = value; values.append(feedback)
        feedback = deepcopy(self.feedback); del feedback["interpretation"]; values.append(feedback)
        feedback = deepcopy(self.feedback); feedback["progress"]["notes"] = "PRIVATE_DATA"; values.append(feedback)
        for value in values:
            with self.assertRaises(client_module.LocalBridgeError): await self.client.report(value)
        self.assertEqual(self.requests, [])

    async def test_local_ack_must_not_claim_dot_delivery(self):
        type(self).response = {"status": "reported_to_dot"}
        with self.assertRaises(client_module.LocalBridgeError): await self.client.report(self.feedback)

    async def test_duplicate_report_is_idempotent_but_stale_is_not_success(self):
        type(self).response = {"status": "duplicate_ignored"}
        self.assertIsNone(await self.client.report(self.feedback))
        type(self).response = {"status": "stale_ignored"}
        with self.assertRaises(client_module.LocalBridgeError): await self.client.report(self.feedback)

    async def test_take_decision_validates_existing_contract_without_starting_anything(self):
        value = self.decision()
        type(self).response = {"status": "available", "decision": value}
        result = await self.client.take_decision()
        self.assertEqual(result, bridge.DotDecision.model_validate(value).model_dump(mode="json"))
        self.assertEqual(self.requests[0][0], "/local/decisions/take")
        self.assertEqual(self.requests[0][2], {})

    async def test_take_empty_queue_returns_none(self):
        type(self).response = {"status": "unavailable", "decision": None}
        self.assertIsNone(await self.client.take_decision())

    async def test_bad_decision_and_unknown_status_fail_closed(self):
        value = self.decision(); value["notes"] = "PRIVATE_DATA"
        for response in [{"status": "available", "decision": value}, {"status": "unknown"},
                         {"status": "unavailable", "decision": self.decision()},
                         {"status": "available", "decision": None}]:
            type(self).response = response
            with self.assertRaises(client_module.LocalBridgeError): await self.client.take_decision()

    async def test_disconnect_requires_local_ack(self):
        type(self).response = {"status": "disconnected"}
        self.assertIsNone(await self.client.disconnect())
        self.assertEqual(self.requests[0][0], "/local/disconnect")
        self.assertEqual(self.requests[0][2], {})
        type(self).response = {"status": "available"}
        with self.assertRaises(client_module.LocalBridgeError): await self.client.disconnect()

    def test_only_literal_loopback_origin_without_path_or_controls(self):
        for origin in ["http://localhost:1234", "http://127.0.0.1:0", "http://127.0.0.1:65536",
                       "http://127.0.0.1:1234/", "http://127.0.0.1:1234/path", "http://user@127.0.0.1:1234",
                       "http://127.0.0.1:1234?query=1", "http://127.0.0.1:1234#fragment", "https://127.0.0.1:1234",
                       "http://127.0.0.2:1234", "http://[::1]:1234", "http://127.0.0.1:1234\n", None]:
            with self.assertRaises(ValueError): client_module.LocalMcpBridgeClient(origin, TOKEN)

    def test_bad_tokens_rejected_without_echoing_credentials(self):
        for token in [None, "", "too-short", "x" * 513, "a" * 32 + "\r\nInjected: yes", "a" * 32 + " ", "a" * 32 + "\u00e9"]:
            with self.assertRaises(ValueError) as error: client_module.LocalMcpBridgeClient(self.origin, token)
            if token: self.assertNotIn(token, str(error.exception))

    async def test_redirect_is_not_followed(self):
        type(self).status = 307
        type(self).location = self.origin + "/unexpected"
        with self.assertRaises(client_module.LocalBridgeError): await self.client.report(self.feedback)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0][0], "/local/progress")

    async def test_environment_proxy_is_not_used(self):
        with patch.dict("os.environ", {"http_proxy": "http://127.0.0.2:1", "HTTP_PROXY": "http://127.0.0.2:1", "no_proxy": "", "NO_PROXY": ""}):
            client = client_module.LocalMcpBridgeClient(self.origin, TOKEN)
            await client.report(self.feedback)
        self.assertEqual(len(self.requests), 1)

    async def test_response_size_type_json_and_status_are_checked(self):
        for status, content_type, body in [(200, "application/json", b" " * 8193),
                                          (200, "text/html", b"{}"), (200, "application/json", b"not-json"),
                                          (200, "application/json", b"[]"), (401, "application/json", b"secret server detail")]:
            type(self).status, type(self).content_type, type(self).response = status, content_type, body
            with self.assertRaises(client_module.LocalBridgeError) as error: await self.client.report(self.feedback)
            self.assertNotIn("secret server detail", str(error.exception))

    async def test_response_timeout_has_unknown_outcome_and_no_retry(self):
        calls = []
        def slow(*args): calls.append(args); time.sleep(0.05); return {"status": "disconnected"}
        with patch.object(client_module, "TIMEOUT_SECONDS", 0.01), patch.object(self.client, "_post", slow):
            with self.assertRaisesRegex(client_module.LocalBridgeError, "outcome unknown"):
                await self.client.disconnect()
        await asyncio.sleep(0.06)
        self.assertEqual(len(calls), 1)

    def test_oversized_request_is_rejected_before_http(self):
        with self.assertRaisesRegex(client_module.LocalBridgeError, "request exceeds"):
            self.client._post("/local/progress", {"text": "x" * 8192})
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()

