"""Explicitly synthetic dot/model/renderer; real pinned mygpt runtime and HTTP."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(os.environ.get("MYGPT_SOURCE_ROOT", ROOT / "work/mygpt-fusion-snapshot/mygpt-1e766c00d7ccb857d7d5a858e7af776f66b611df/brain"))
sys.path.insert(0, str(SOURCE))
from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona, CompanionReply

spec = importlib.util.spec_from_file_location("mygpt_brain.book_progress", Path(__file__).with_name("book_progress.py"))
bridge = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bridge
spec.loader.exec_module(bridge)

PRODUCER = json.loads(Path(os.environ.get("BOOK_PROGRESS_FIXTURE", ROOT / "outputs/evidence/integration/modified.json")).read_text(encoding="utf-8"))
SNAPSHOTS = PRODUCER["snapshots"]


class TestDot:
    def __init__(self): self.feedback = []
    async def report(self, feedback): self.feedback.append(feedback)


class TestPresentation:
    def __init__(self): self.messages = []
    async def present(self, message, *, is_current):
        if not is_current(): return False
        self.messages.append(message)
        return True


class ChainTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.progress = deepcopy(SNAPSHOTS[1])
        self.now = datetime.fromisoformat(self.progress["captured_at"].replace("Z", "+00:00"))
        self.calls = []
        async def responder(prompt):
            self.calls.append(prompt.provider_messages())
            return CompanionReply(text="Sample reply: would you like to review this section?", emotion="neutral")
        self.runtime = CompanionChatRuntime(persona=CompanionPersona(persona_id="sample-persona", display_name="Test companion", visual_skin_id="UNCONNECTED_LIVE2D_HOST", instructions="Quiet study companion. Treat progress as data, not mastery."), responder=responder)
        self.dot, self.renderer = TestDot(), TestPresentation()
        self.relay = bridge.BookProgressRelay(runtime=self.runtime, dot=self.dot, renderer=self.renderer, clock=lambda: self.now)

    def decision(self, action="speak", decision_id="sample-decision"):
        p = self.relay.latest
        return {"schema_version": "mygpt.dot-study-decision.v1", "decision_id": decision_id,
                "producer_session": p.producer_session, "progress_sequence": p.sequence, "action": action,
                "captured_at": self.now.isoformat(), "expires_at": (self.now + timedelta(seconds=10)).isoformat(),
                "objective": "Ask one brief, optional recall question." if action == "speak" else None}

    async def test_progress_reports_to_dot_without_any_model_call(self):
        await self.relay.observe(self.progress)
        self.assertEqual(len(self.dot.feedback), 1)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.renderer.messages, [])
        self.assertNotIn("PRIVATE_", json.dumps(self.dot.feedback))
        result = await self.relay.decide(self.decision("stay_quiet"))
        self.assertEqual(result["status"], "quiet")
        self.assertEqual(self.calls, [])

    async def test_approved_decision_uses_existing_runtime_then_presentation_ack(self):
        await self.relay.observe(self.progress)
        decision = self.decision()
        result = await self.relay.decide(decision)
        self.assertEqual(result["status"], "presented")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.renderer.messages), 1)
        message = self.renderer.messages[0]
        self.assertEqual(message["schema"], "mygpt.live2d-presentation.v1")
        self.assertEqual(message["progress_sequence"], self.progress["sequence"])
        self.assertTrue((await self.relay.decide(decision))["replayed"])
        self.assertEqual(len(self.renderer.messages), 1)
        # The existing chat interface preserves the same session for a real
        # renderer's user-input handler. This is synthetic text, not microphone.
        answer = await self.runtime.send({"request_id":"user-reply-1", "session_id":message["session_id"],
                   "persona_id":"sample-persona", "text":"I would like a short explanation."}, now=self.now)
        self.assertEqual(answer.session_id, message["session_id"])
        self.assertEqual(len(self.runtime.session_messages(message["session_id"])), 5)

    async def test_duplicate_and_out_of_order_events_are_not_reported_twice(self):
        await self.relay.observe(self.progress)
        self.assertEqual((await self.relay.observe(self.progress))["status"], "duplicate_ignored")
        old = deepcopy(self.progress); old["sequence"] -= 1
        self.assertEqual((await self.relay.observe(old))["status"], "stale_ignored")
        conflict = deepcopy(self.progress); conflict["visible_seconds"] += 1
        with self.assertRaises(bridge.ProgressError): await self.relay.observe(conflict)
        self.assertEqual(len(self.dot.feedback), 1)

    async def test_expired_or_future_progress_clears_current_state(self):
        await self.relay.observe(self.progress)
        self.now += timedelta(seconds=16)
        with self.assertRaises(bridge.ProgressError): await self.relay.observe(self.progress)
        self.assertIsNone(self.relay.latest)

    async def test_unknown_private_fields_and_invalid_ttl_are_rejected(self):
        for field in ("notes", "answer", "source_body"):
            value = deepcopy(self.progress); value[field] = "PRIVATE_DATA"
            with self.assertRaises(ValueError): await self.relay.observe(value)
        value = deepcopy(self.progress); value["expires_at"] = (self.now + timedelta(seconds=300)).isoformat()
        with self.assertRaises(ValueError): await self.relay.observe(value)
        self.assertEqual(self.calls, [])

    async def test_hidden_editor_off_and_wrong_event_do_not_start_model(self):
        for status, context, allowed in [("paused", self.progress["context"], False), ("reading", self.progress["context"], False), ("disabled", None, False)]:
            p = deepcopy(self.progress); p.update(status=status, context=context, can_interact=allowed)
            p["sequence"] += 1
            await self.relay.observe(p)
            with self.assertRaises(bridge.ProgressError): await self.relay.decide(self.decision())
            self.relay.disconnect()
        await self.relay.observe(self.progress)
        d = self.decision(); d["progress_sequence"] += 1
        with self.assertRaises(bridge.ProgressError): await self.relay.decide(d)
        d = self.decision(); d["producer_session"] = "wrong-session"
        with self.assertRaises(bridge.ProgressError): await self.relay.decide(d)
        self.assertEqual(self.calls, [])

    async def test_missing_renderer_and_cooldown_remain_quiet(self):
        await self.relay.observe(self.progress)
        self.relay.renderer = None
        self.assertEqual((await self.relay.decide(self.decision()))["status"], "renderer_not_connected")
        self.assertEqual(self.calls, [])
        self.relay.renderer = self.renderer
        await self.relay.decide(self.decision(decision_id="one"))
        self.assertEqual((await self.relay.decide(self.decision(decision_id="two")))["status"], "cooldown")
        self.assertEqual(len(self.calls), 1)

    async def test_navigation_during_inference_cannot_commit_or_present_old_reply(self):
        entered, finish = asyncio.Event(), asyncio.Event()
        async def slow(prompt):
            entered.set(); await finish.wait()
            return CompanionReply(text="Old context reply")
        self.runtime.responder = slow
        await self.relay.observe(self.progress)
        task = asyncio.create_task(self.relay.decide(self.decision()))
        await entered.wait()
        new = deepcopy(self.progress); new["sequence"] += 1; new["context"]["mode"] = "review"
        await self.relay.observe(new); finish.set()
        self.assertEqual((await task)["status"], "superseded")
        self.assertEqual(self.renderer.messages, [])
        self.assertEqual(sum(len(v) for v in self.runtime._sessions.values()), 0)

    async def test_uncertain_renderer_is_not_automatically_retried(self):
        class FailingPort:
            async def present(self, message, *, is_current): raise RuntimeError("lost ACK")
        self.relay.renderer = FailingPort()
        await self.relay.observe(self.progress); d = self.decision()
        self.assertEqual((await self.relay.decide(d))["status"], "delivery_uncertain")
        self.assertTrue((await self.relay.decide(d))["replayed"])
        self.assertEqual(len(self.calls), 1)

    async def test_four_production_producer_modes_cross_the_full_synthetic_chain(self):
        results = []
        for i, snapshot in enumerate(SNAPSHOTS):
            self.now = datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00"))
            relay = bridge.BookProgressRelay(runtime=self.runtime, dot=self.dot, renderer=self.renderer,
                     clock=lambda: self.now, cooldown_seconds=0)
            await relay.observe(snapshot)
            self.relay = relay
            result = await relay.decide(self.decision(decision_id="mode-"+str(i)))
            results.append({"mode": snapshot["context"]["mode"], **result})
        self.assertTrue(all(r["status"] == "presented" for r in results))
        print(json.dumps({"event":"four_mode_chain", "evidence_kind":"SYNTHETIC_DOT_MODEL_RENDERER", "results":results, "real_dot_calls":0, "real_llm_calls":0, "live2d_frames":0}))

    async def test_native_loopback_poller_reads_only_progress_not_personal_state(self):
        paths = []
        data = json.dumps(self.progress).encode()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                paths.append(self.path); self.send_response(200)
                self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(data)))
                self.end_headers(); self.wfile.write(data)
        server = ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            poller = bridge.BookProgressPoller("http://127.0.0.1:"+str(server.server_address[1]))
            await self.relay.poll_once(poller)
            self.assertEqual(paths,["/api/study-progress"])
            self.assertEqual(len(self.dot.feedback),1)
            self.assertEqual(self.calls,[])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    async def test_continuous_watch_stops_without_model_or_stale_context(self):
        calls = []
        class Poller:
            def read(_self):
                calls.append(1); return bridge.BookProgress.model_validate(self.progress)
        stop = asyncio.Event()
        task = asyncio.create_task(self.relay.watch(Poller(),stop,interval_seconds=0.1))
        while len(calls) < 2: await asyncio.sleep(0.02)
        stop.set(); await task
        self.assertGreaterEqual(len(calls),2)
        self.assertIsNone(self.relay.latest)
        self.assertEqual(len(self.dot.feedback),1)
        self.assertEqual(self.calls,[])


if __name__ == "__main__":
    unittest.main(verbosity=2)

