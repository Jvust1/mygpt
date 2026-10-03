"""Synthetic provider/renderer evidence; real loopback HTTP is tested separately."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from test_book_progress import bridge, PRODUCER
from test_mcp_bridge_core import core
from test_mcp_bridge_client import client_module


def load(name):
    spec = importlib.util.spec_from_file_location("mygpt_brain." + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


host_module = load("study_host")
from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionReply


class FixturePoller:
    def __init__(self, value): self.value = value
    def read(self):
        if isinstance(self.value, Exception): raise self.value
        return deepcopy(self.value)


class FixtureBridge:
    def __init__(self, now):
        self.core = core.StudyBridge(clock=now)
        self.failure = False
        self.requests = []
    async def report(self, envelope):
        self.requests.append(("report", time.monotonic()))
        if self.failure: raise OSError("synthetic outage")
        result = self.core.ingest(envelope["progress"])
        if result["status"] == "stale_ignored": raise ValueError("stale not accepted")
    async def take_decision(self):
        self.requests.append(("take", time.monotonic()))
        if self.failure: raise OSError("synthetic outage")
        return self.core.take_decision()["decision"]
    async def disconnect(self):
        self.requests.append(("disconnect", time.monotonic()))
        self.core.disconnect()


class FixtureRenderer:
    def __init__(self):
        self.messages = []; self.invalidations = 0; self.reply = None; self.fail = False
    async def present(self, message, *, is_current):
        if self.fail: raise OSError("synthetic uncertain renderer ACK")
        if not is_current(): return False
        self.messages.append(deepcopy(message)); return True
    async def invalidate(self):
        self.invalidations += 1; self.reply = None
    async def take_reply(self, session_id):
        value, self.reply = self.reply, None
        return value


class HostTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.progress = deepcopy(PRODUCER["snapshots"][1])
        self.progress["captured_at"] = self.now.isoformat()
        self.progress["expires_at"] = (self.now + timedelta(seconds=15)).isoformat()
        self.poller = FixturePoller(self.progress)
        self.bridge = FixtureBridge(lambda: self.now)
        self.renderer = FixtureRenderer()
        self.calls = []
        self.started, self.release = asyncio.Event(), asyncio.Event()
        self.delayed = False
        async def responder(prompt):
            self.calls.append(prompt.provider_messages())
            self.started.set()
            if self.delayed: await self.release.wait()
            return CompanionReply(text="杩欐槸娴嬭瘯鍥炲锛屼笉浠ｈ〃鐪熷疄妯″瀷銆?, emotion="neutral")
        self.runtime = CompanionChatRuntime(persona=host_module._persona(), responder=responder)
        self.addCleanup(self.runtime.memory_store.close)
        self.host = host_module.StudyHost(poller=self.poller, bridge=self.bridge, renderer=self.renderer,
            runtime=self.runtime, decision_provenance="local_test", clock=lambda: self.now)

    def queue(self, id="synthetic-decision", action="speak"):
        return self.bridge.core.submit_decision({"decision_id": id, "producer_session": self.progress["producer_session"],
            "progress_sequence": self.progress["sequence"], "action": action,
            "objective": "Offer one short optional question." if action == "speak" else None})

    def advance(self, **changes):
        self.now += timedelta(seconds=1)
        self.progress = deepcopy(self.progress); self.progress.update(changes)
        self.progress["sequence"] += 1
        self.progress["captured_at"] = self.now.isoformat()
        self.progress["expires_at"] = (self.now + timedelta(seconds=15)).isoformat()
        self.poller.value = self.progress

    async def test_defaults_mirror_without_model_or_dot_claim(self):
        host = host_module.StudyHost(poller=self.poller, bridge=self.bridge, renderer=self.renderer, clock=lambda: self.now)
        self.addCleanup(host.runtime.memory_store.close)
        result = await host.poll_once()
        self.assertEqual(result["status"], "progress_reported_to_local_mcp_not_dot")
        self.assertFalse(result["real_dot_connected"])
        self.queue()
        self.assertEqual((await host.process_decision_once())["status"], "model_unconfigured")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.renderer.messages, [])

    async def test_unverified_decisions_cannot_call_configured_model(self):
        self.host.decision_provenance = "disabled"
        await self.host.poll_once(); self.queue()
        self.assertEqual((await self.host.process_decision_once())["status"], "decision_provenance_unverified")
        self.assertEqual(self.calls, [])

    async def test_explicit_local_test_end_to_end_reuses_runtime_and_live_contract(self):
        await self.host.poll_once(); self.queue()
        result = await self.host.process_decision_once()
        self.assertEqual(result["status"], "presented")
        self.assertEqual(result["decision_provenance"], "local_test")
        self.assertFalse(result["real_dot_connected"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.renderer.messages), 1)
        self.assertIn("expires_at", self.renderer.messages[0])
        self.queue()
        self.assertEqual((await self.host.process_decision_once())["status"], "no_decision")
        self.assertEqual(len(self.calls), 1)

    async def test_live_user_reply_stays_in_same_runtime_session(self):
        await self.host.poll_once(); self.queue(); await self.host.process_decision_once()
        shown = self.renderer.messages[-1]
        reply = {"schema": "mygpt.live-user-reply.v1", "request_id": "reply-1", "session_id": shown["session_id"],
                 "reply_to_message_id": shown["message_id"], "text": "璇风户缁В閲娿€?, "captured_at": self.now.isoformat()}
        self.renderer.reply = deepcopy(reply)
        result = await self.host.process_reply_once()
        self.assertEqual(result["status"], "user_reply_presented")
        self.assertEqual(self.renderer.messages[-1]["session_id"], shown["session_id"])
        self.assertEqual(len(self.runtime.session_messages(shown["session_id"])), 5)
        self.renderer.reply = reply
        self.assertNotEqual((await self.host.process_reply_once())["status"], "user_reply_presented")
        self.assertEqual(len(self.calls), 2)

    async def test_cooldown_and_quiet_do_not_call_model(self):
        await self.host.poll_once(); self.queue(action="stay_quiet")
        self.assertEqual((await self.host.process_decision_once())["status"], "quiet")
        self.assertEqual(self.calls, [])
        self.queue("speak-once"); await self.host.process_decision_once()
        self.queue("cooldown")
        self.assertEqual((await self.host.process_decision_once())["status"], "cooldown")
        self.assertEqual(len(self.calls), 1)

    async def test_disable_cancels_delayed_model_without_committing_or_presenting(self):
        self.delayed = True
        await self.host.poll_once(); self.queue()
        pending = asyncio.create_task(self.host.process_decision_once())
        await asyncio.wait_for(self.started.wait(), 1)
        self.advance(status="disabled", context=None, can_interact=False)
        await self.host.poll_once()
        result = await asyncio.wait_for(pending, 1)
        self.release.set()
        self.assertEqual(result["status"], "turn_revoked")
        self.assertEqual(self.renderer.messages, [])
        self.assertEqual(self.runtime.session_messages(host_module._session_id(self.progress["producer_session"])), [])
        self.assertGreaterEqual(self.renderer.invalidations, 1)

    async def test_chapter_switch_revokes_and_new_turn_can_run_after_cancellation(self):
        self.delayed = True
        await self.host.poll_once(); self.queue()
        pending = asyncio.create_task(self.host.process_decision_once())
        await asyncio.wait_for(self.started.wait(), 1)
        context = deepcopy(self.progress["context"]); context["chapter"] += 1
        self.advance(context=context)
        await self.host.poll_once(); await asyncio.wait_for(pending, 1)
        self.delayed = False
        self.queue("new-chapter")
        self.assertEqual((await self.host.process_decision_once())["status"], "presented")
        self.assertEqual(len(self.renderer.messages), 1)

    async def test_same_context_heartbeat_does_not_clear_conversation(self):
        await self.host.poll_once(); self.queue(); await self.host.process_decision_once()
        count = self.renderer.invalidations
        self.advance(); await self.host.poll_once()
        self.assertEqual(self.renderer.invalidations, count)
        self.assertIsNotNone(self.host._last_presentation)

    async def test_disconnect_and_bridge_outage_revoke_before_delivery(self):
        await self.host.poll_once(); self.queue()
        self.bridge.failure = True
        self.assertEqual((await self.host.poll_once())["status"], "book_or_mcp_unavailable")
        self.assertIsNone(self.host.relay.latest)
        self.assertEqual(self.renderer.messages, [])
        self.assertEqual(self.calls, [])

    async def test_uncertain_renderer_ack_is_not_retried(self):
        self.renderer.fail = True
        await self.host.poll_once(); self.queue()
        self.assertEqual((await self.host.process_decision_once())["status"], "delivery_uncertain")
        self.queue()
        self.assertEqual((await self.host.process_decision_once())["status"], "no_decision")
        self.assertEqual(len(self.calls), 1)

    async def test_run_polls_while_model_pending_and_stops_cleanly(self):
        self.delayed = True
        stop = asyncio.Event()
        running = asyncio.create_task(self.host.run(stop, poll_interval=1))
        for _ in range(30):
            if self.bridge.core.get_progress()["status"] == "available": break
            await asyncio.sleep(0.01)
        self.queue()
        await asyncio.wait_for(self.started.wait(), 2)
        self.advance(status="stopped", context=None, can_interact=False)
        for _ in range(200):
            if self.host.relay.latest and self.host.relay.latest.status == "stopped": break
            await asyncio.sleep(0.01)
        self.assertEqual(self.host.relay.latest.status, "stopped")
        self.assertEqual(self.renderer.messages, [])
        stop.set()
        await asyncio.wait_for(running, 3)
        self.assertEqual(self.host.status()["status"], "stopped")

    async def test_disabled_consumers_never_poll_or_drain_decisions(self):
        await self.host.poll_once(); self.queue()
        before = len(self.bridge.requests)
        self.host.model_configured = False
        for _ in range(300):
            self.assertEqual((await self.host.process_decision_once())["status"], "model_unconfigured")
        self.host.model_configured = True
        self.host.decision_provenance = "disabled"
        for _ in range(300):
            self.assertEqual((await self.host.process_decision_once())["status"], "decision_provenance_unverified")
        self.assertEqual(len(self.bridge.requests), before)
        self.assertEqual(self.bridge.core.health()["queued_decisions"], 1)
        self.assertEqual(self.calls, [])

    async def test_sustained_run_respects_mcp_request_budget(self):
        stop = asyncio.Event()
        running = asyncio.create_task(self.host.run(stop, poll_interval=1))
        await asyncio.sleep(3.2)
        stop.set(); await asyncio.wait_for(running, 3)
        counts = {kind: sum(kind == request[0] for request in self.bridge.requests)
                  for kind in ("report", "take", "disconnect")}
        self.assertLessEqual(counts["report"], 4)
        self.assertLessEqual(counts["take"], 4)
        self.assertEqual(counts["disconnect"], 2)
        for kind in ("report", "take"):
            timestamps = [stamp for name, stamp in self.bridge.requests if name == kind]
            self.assertTrue(all(b - a >= 0.99 for a, b in zip(timestamps, timestamps[1:])))
        print("SUSTAINED_MCP_REQUEST_COUNTS " + json.dumps(counts, sort_keys=True))

    async def test_subsecond_production_polling_is_rejected_before_network(self):
        with self.assertRaisesRegex(ValueError, "request budget"):
            await self.host.run(asyncio.Event(), poll_interval=0.1)
        self.assertEqual(self.bridge.requests, [])

    async def test_provider_selection_is_explicit_and_does_not_contact_network(self):
        self.assertIsNone(host_module.build_runtime())
        for provider, model in (("disabled", "guessed"), ("ollama", None), ("remote", "x")):
            with self.assertRaises(ValueError): host_module.build_runtime(provider, model)
        runtime = host_module.build_runtime("ollama", "explicit-existing-test-model")
        self.assertEqual(runtime.responder.model, "explicit-existing-test-model")
        runtime.memory_store.close()

    async def test_expired_and_wrong_session_decisions_never_call_model(self):
        await self.host.poll_once()
        self.queue()
        self.now += timedelta(seconds=11)
        self.assertEqual((await self.host.process_decision_once())["status"], "no_decision")
        self.assertEqual(self.calls, [])
        self.advance(); await self.host.poll_once()
        self.queue("wrong-session-source")
        decision = self.bridge.core.take_decision()["decision"]
        decision["producer_session"] = "another-session"
        async def wrong_session(): return decision
        self.bridge.take_decision = wrong_session
        self.assertEqual((await self.host.process_decision_once())["status"], "decision_or_model_failed")
        self.assertEqual(self.calls, [])

    async def test_late_same_session_old_chapter_does_not_clear_ordering_state(self):
        await self.host.poll_once()
        old = deepcopy(self.progress)
        context = deepcopy(self.progress["context"]); context["chapter"] += 1
        self.advance(context=context); await self.host.poll_once()
        invalidations = self.renderer.invalidations
        self.poller.value = old
        self.assertEqual((await self.host.poll_once())["status"], "stale_progress_ignored")
        self.assertEqual(self.host.relay.latest.sequence, self.progress["sequence"])
        self.assertEqual(self.host.relay.latest.context.chapter, self.progress["context"]["chapter"])
        self.assertEqual(self.renderer.invalidations, invalidations)

    async def test_old_remote_cleanup_finishes_before_new_progress_can_publish(self):
        await self.host.poll_once()
        entered, release = asyncio.Event(), asyncio.Event()
        async def slow_invalidate():
            entered.set(); await release.wait()
        self.renderer.invalidate = slow_invalidate
        revoking = asyncio.create_task(self.host._revoke("synthetic_disconnect"))
        await entered.wait()
        self.advance()
        publishing = asyncio.create_task(self.host.poll_once())
        await asyncio.sleep(0.05)
        self.assertFalse(publishing.done())
        self.assertIsNone(self.host.relay.latest)
        release.set()
        await revoking; await publishing
        self.assertEqual(self.host.relay.latest.sequence, self.progress["sequence"])
        self.assertEqual(self.bridge.core.get_progress()["progress"]["sequence"], self.progress["sequence"])

    async def test_lease_watch_cancels_model_while_book_poll_waits(self):
        self.delayed = True
        stop = asyncio.Event()
        running = asyncio.create_task(self.host.run(stop, poll_interval=5))
        for _ in range(30):
            if self.bridge.core.get_progress()["status"] == "available": break
            await asyncio.sleep(0.01)
        self.queue()
        await asyncio.wait_for(self.started.wait(), 2)
        self.now += timedelta(seconds=16)
        for _ in range(100):
            if self.host.relay.latest is None: break
            await asyncio.sleep(0.01)
        self.assertIsNone(self.host.relay.latest)
        self.assertEqual(self.renderer.messages, [])
        stop.set(); await asyncio.wait_for(running, 3)


class HttpWiringTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_book_poller_mcp_http_model_fixture_live_http_and_reply(self):
        load("https_callback")
        server_module = load("mcp_bridge_server")
        now = datetime.now(timezone.utc)
        progress = deepcopy(PRODUCER["snapshots"][1])
        progress.update(captured_at=now.isoformat(), expires_at=(now + timedelta(seconds=15)).isoformat())
        messages, requests, pending_replies = [], [], []
        generation = [0]
        live_token, ingest_token, mcp_token = "fixture-live-token-" + "l"*32, "fixture-ingest-token-" + "i"*32, "fixture-mcp-token-" + "m"*32
        class LocalFixture(BaseHTTPRequestHandler):
            def reply(self, value, status=200):
                raw = json.dumps(value).encode()
                self.send_response(status); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_GET(self):
                requests.append(self.path)
                if self.path == "/study/health":
                    return self.reply({"status":"local_live_chat", "generation":generation[0], "renderer_mode":"offscreen_test"})
                self.reply(progress if self.path == "/api/study-progress" else {}, 200 if self.path == "/api/study-progress" else 404)
            def do_POST(self):
                if self.headers.get("Authorization") != "Bearer " + live_token:
                    return self.reply({}, 401)
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(self.path)
                if self.path == "/study/present":
                    messages.append(data)
                    self.reply({"status":"presented", "display_ack":True, "renderer_mode":"offscreen_test",
                                "message_id": data["message_id"], "session_id": data["session_id"]})
                elif self.path == "/study/replies/take":
                    self.reply({"status":"available", "reply":pending_replies.pop(0)} if pending_replies else {"status":"unavailable", "reply":None})
                else:
                    generation[0] += 1
                    self.reply({"status":"invalidated", "generation":generation[0]})
            def log_message(self, *args): pass
        fixture = ThreadingHTTPServer(("127.0.0.1", 0), LocalFixture)
        fixture_thread = threading.Thread(target=fixture.serve_forever, daemon=True); fixture_thread.start()
        temp = tempfile.TemporaryDirectory()
        mcp = server_module.BridgeServer(0, mcp_token, ingest_token, temp.name)
        mcp_thread = threading.Thread(target=mcp.serve_forever, daemon=True); mcp_thread.start()
        origin = "http://127.0.0.1:" + str(fixture.server_port)
        async def rpc(name, arguments):
            async with host_module.httpx.AsyncClient(trust_env=False) as client:
                response = await client.post(mcp.origin + "/mcp", headers={"Authorization":"Bearer " + mcp_token,
                    "MCP-Protocol-Version":"2026-07-28", "Mcp-Method":"tools/call", "Mcp-Name":name,
                    "Accept":"application/json, text/event-stream"}, json={"jsonrpc":"2.0", "id":"fixture", "method":"tools/call",
                    "params":{"name":name,"arguments":arguments,"_meta":{"io.modelcontextprotocol/clientCapabilities":{},
                    "io.modelcontextprotocol/protocolVersion":"2026-07-28"}}})
                self.assertEqual(response.status_code, 200)
                return response.json()["result"]["structuredContent"]
        calls = []
        async def responder(prompt):
            calls.append(prompt.provider_messages())
            return CompanionReply(text="HTTP wiring fixture, not real model.")
        renderer = host_module.LivePresentationPort(origin, live_token, allow_test_renderer=True)
        host = host_module.StudyHost(poller=bridge.BookProgressPoller(origin),
            bridge=client_module.LocalMcpBridgeClient(mcp.origin, ingest_token), renderer=renderer,
            runtime=CompanionChatRuntime(persona=host_module._persona(), responder=responder), decision_provenance="local_test")
        try:
            self.assertEqual((await host.poll_once())["status"], "progress_reported_to_local_mcp_not_dot")
            self.assertEqual((await rpc("get_study_progress", {}))["progress"]["sequence"], progress["sequence"])
            await rpc("submit_study_decision", {"decision_id":"http-fixture", "producer_session":progress["producer_session"],
                      "progress_sequence":progress["sequence"], "action":"speak", "objective":"Show a labeled test message."})
            self.assertEqual((await host.process_decision_once())["status"], "presented")
            shown = messages[-1]
            pending_replies.append({"schema":"mygpt.live-user-reply.v1", "request_id":"http-reply", "session_id":shown["session_id"],
                "reply_to_message_id":shown["message_id"], "text":"Fixture reply.", "captured_at":datetime.now(timezone.utc).isoformat()})
            self.assertEqual((await host.process_reply_once())["status"], "user_reply_presented")
            self.assertEqual(len(calls), 2)
            self.assertEqual(messages[0]["session_id"], messages[1]["session_id"])
            self.assertIn("/api/study-progress", requests)
            self.assertIn("/study/replies/take", requests)
            # Production adapter does not mistake offscreen fixture ACK for visible presentation.
            production = host_module.LivePresentationPort(origin, live_token)
            self.assertFalse(await production.present(messages[-1], is_current=lambda: True))
        finally:
            await host._revoke("test_finished")
            host.runtime.memory_store.close()
            await asyncio.to_thread(mcp.shutdown); mcp.server_close(); mcp_thread.join(2)
            await asyncio.to_thread(fixture.shutdown); fixture.server_close(); fixture_thread.join(2)
            temp.cleanup()


class LivePortRaceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.port = host_module.LivePresentationPort("http://127.0.0.1:8767", "fixture-token-" + "x"*32, clock=lambda: self.now)
        self.message = {"message_id":"fixture-message", "session_id":"fixture-session",
                        "expires_at":(self.now + timedelta(seconds=10)).isoformat()}

    async def test_invalidation_fences_late_present_and_ack(self):
        sent, release = asyncio.Event(), asyncio.Event()
        requests = []
        async def request(route, payload, *, method="POST"):
            if route == "/study/health": return {"status":"local_live_chat", "generation":1}
            if route == "/study/invalidate": return {"status":"invalidated", "generation":2}
            requests.append(payload); sent.set(); await release.wait()
            return {"status":"presented", "display_ack":True, "renderer_mode":"visible", **self.message}
        self.port._post = request
        presenting = asyncio.create_task(self.port.present(self.message, is_current=lambda: True))
        await sent.wait(); await self.port.invalidate(); release.set()
        self.assertFalse(await presenting)
        self.assertEqual(requests[0]["generation"], 1)
        self.assertEqual(self.port._generation, 2)

    async def test_current_epoch_refreshed_after_natural_renderer_expiry(self):
        generation, sent = [1], []
        async def request(route, payload, *, method="POST"):
            if route == "/study/health": return {"status":"local_live_chat", "generation":generation[0]}
            sent.append(payload["generation"])
            return {"status":"presented", "display_ack":True, "renderer_mode":"visible", **self.message}
        self.port._post = request
        self.assertTrue(await self.port.present(self.message, is_current=lambda: True))
        generation[0] = 2
        self.assertTrue(await self.port.present(self.message, is_current=lambda: True))
        self.assertEqual(sent, [1, 2])

    async def test_cached_ack_cannot_be_a_new_display(self):
        async def request(route, payload, *, method="POST"):
            if route == "/study/health": return {"status":"local_live_chat", "generation":1}
            return {"status":"presented", "display_ack":True, "renderer_mode":"visible", "replayed":True, **self.message}
        self.port._post = request
        self.assertFalse(await self.port.present(self.message, is_current=lambda: True))

    async def test_invalidating_during_health_prevents_old_body_dispatch(self):
        reading, release = asyncio.Event(), asyncio.Event()
        sent = []
        async def request(route, payload, *, method="POST"):
            if route == "/study/health":
                reading.set(); await release.wait()
                return {"status":"local_live_chat", "generation":1}
            if route == "/study/invalidate": return {"status":"invalidated", "generation":2}
            sent.append(payload); return {}
        self.port._post = request
        presenting = asyncio.create_task(self.port.present(self.message, is_current=lambda: True))
        await reading.wait()
        invalidating = asyncio.create_task(self.port.invalidate())
        await asyncio.sleep(0); release.set()
        self.assertFalse(await presenting)
        await invalidating
        self.assertEqual(sent, [])


if __name__ == "__main__": unittest.main(verbosity=2)

