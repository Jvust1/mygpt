"""Synthetic clock and Book fixture: no real dot, model, renderer or network."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest

from test_book_progress import bridge, PRODUCER
from test_dot_events import events

spec = importlib.util.spec_from_file_location("mygpt_brain.mcp_bridge_core", Path(__file__).with_name("mcp_bridge_core.py"))
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


class StudyBridgeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        self.progress = deepcopy(PRODUCER["snapshots"][1])
        self.progress["captured_at"] = self.now.isoformat()
        self.progress["expires_at"] = (self.now + timedelta(seconds=15)).isoformat()
        self.bridge = core.StudyBridge(clock=lambda: self.now)

    def offer(self, **updates):
        self.progress = deepcopy(self.progress)
        self.progress.update(updates)
        self.progress["sequence"] += 1
        self.progress["captured_at"] = self.now.isoformat()
        self.progress["expires_at"] = (self.now + timedelta(seconds=15)).isoformat()
        return self.bridge.ingest(self.progress)

    def decision(self, **updates):
        args = {"decision_id": "synthetic-decision", "producer_session": self.progress["producer_session"],
                "progress_sequence": self.progress["sequence"], "action": "speak",
                "objective": "Offer one optional review question."}
        args.update(updates)
        return args

    def test_tool_catalog_strict_actual_contracts_and_empty_arguments(self):
        catalog = core.tool_definitions()
        self.assertEqual([t["name"] for t in catalog], ["get_study_progress", "submit_study_decision"])
        for tool in catalog:
            self.assertFalse(tool["inputSchema"]["additionalProperties"])
        self.assertIn("objective", catalog[1]["inputSchema"]["required"])
        self.assertEqual(self.bridge.call_tool("get_study_progress", {})["status"], "unavailable")
        for args in ({"extra": True}, [], None):
            with self.assertRaises(ValueError): self.bridge.call_tool("get_study_progress", args)
        with self.assertRaises(ValueError): self.bridge.call_tool("unknown", {})

    def test_fresh_progress_is_detached_and_queue_is_not_execution(self):
        result = self.bridge.ingest(self.progress)
        self.assertEqual(result["status"], "accepted_locally_not_dot_delivery")
        self.assertEqual(result["outbox_status"], "queued_not_delivered")
        result = self.bridge.get_progress()
        self.assertFalse(result["real_dot_connected"])
        result["progress"]["context"]["book_title"] = "MUTATED"
        self.assertNotEqual(self.bridge.get_progress()["progress"]["context"]["book_title"], "MUTATED")
        receipt = self.bridge.call_tool("submit_study_decision", self.decision())
        self.assertEqual(receipt["status"], "queued_not_executed")
        self.assertFalse(receipt["model_called"])
        self.assertFalse(receipt["real_dot_connected"])
        drained = self.bridge.take_decision()
        decision = bridge.DotDecision.model_validate(drained["decision"])
        self.assertEqual(decision.expires_at, self.now + timedelta(seconds=10))
        self.assertEqual(self.bridge.take_decision()["status"], "unavailable")

    def test_decision_lease_never_outlives_progress(self):
        self.bridge.ingest(self.progress)
        self.now += timedelta(seconds=12)
        self.bridge.submit_decision(self.decision())
        decision = bridge.DotDecision.model_validate(self.bridge.take_decision()["decision"])
        self.assertEqual(decision.expires_at, self.now + timedelta(seconds=3))

    def test_expiry_invalidates_progress_event_and_queued_decision(self):
        self.bridge.ingest(self.progress)
        self.bridge.submit_decision(self.decision())
        self.now += timedelta(seconds=16)
        self.assertEqual(self.bridge.take_decision()["status"], "unavailable")
        self.assertEqual(self.bridge.get_progress()["status"], "unavailable")
        self.assertIsNone(self.bridge.next_event({"producer_session": self.progress["producer_session"]}))
        with self.assertRaises(ValueError): self.bridge.submit_decision(self.decision(decision_id="expired"))

    def test_decision_can_expire_before_progress(self):
        self.bridge.ingest(self.progress)
        self.bridge.submit_decision(self.decision())
        self.now += timedelta(seconds=11)
        self.assertEqual(self.bridge.take_decision()["reason"], "stale")
        self.assertEqual(self.bridge.get_progress()["status"], "available")

    def test_sequence_change_and_mismatched_session_cannot_execute(self):
        self.bridge.ingest(self.progress)
        old = self.decision()
        self.bridge.submit_decision(old)
        self.offer()
        self.assertEqual(self.bridge.take_decision()["status"], "unavailable")
        with self.assertRaises(ValueError): self.bridge.submit_decision({**old, "decision_id": "old-sequence"})
        with self.assertRaises(ValueError): self.bridge.submit_decision(self.decision(producer_session="wrong-session"))
        self.bridge.submit_decision(self.decision(decision_id="new-sequence"))
        self.assertEqual(self.bridge.take_decision()["status"], "available")

    def test_duplicate_identical_receipt_cannot_requeue_and_conflict_rejected(self):
        self.bridge.ingest(self.progress)
        request = self.decision()
        first = self.bridge.submit_decision(request)
        self.bridge.take_decision()
        replay = self.bridge.submit_decision(request)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["decision_id"], first["decision_id"])
        self.assertEqual(self.bridge.take_decision()["status"], "unavailable")
        with self.assertRaises(ValueError):
            self.bridge.submit_decision({**request, "objective": "Changed objective."})

    def test_duplicate_progress_and_out_of_order_sequence(self):
        self.bridge.ingest(self.progress)
        self.bridge.submit_decision(self.decision())
        self.assertEqual(self.bridge.ingest(self.progress)["status"], "duplicate_ignored")
        stale = deepcopy(self.progress); stale["sequence"] -= 1
        self.assertEqual(self.bridge.ingest(stale)["status"], "stale_ignored")
        self.assertEqual(self.bridge.take_decision()["status"], "available")
        conflict = deepcopy(self.progress); conflict["idle_seconds"] += 1
        with self.assertRaises(ValueError): self.bridge.ingest(conflict)
        self.assertEqual(self.bridge.get_progress()["status"], "unavailable")

    def test_retired_session_cannot_reactivate_or_remove_current_decision(self):
        self.progress.update(producer_session="session-A", sequence=10)
        self.bridge.ingest(self.progress)
        old = deepcopy(self.progress)
        self.progress.update(producer_session="session-B", sequence=1)
        self.bridge.ingest(self.progress)
        self.bridge.submit_decision(self.decision(decision_id="current-B"))
        old["sequence"] = 9
        ignored = self.bridge.ingest(old)
        self.assertEqual(ignored["status"], "stale_ignored")
        self.assertEqual(ignored["reason"], "retired_session")
        self.assertEqual(self.bridge.get_progress()["progress"]["producer_session"], "session-B")
        self.assertEqual(self.bridge.take_decision()["decision"]["decision_id"], "current-B")
        # Retirement also rejects a restarted old producer offering a new lease,
        # not just late low-sequence packets inside the original lease.
        self.now += timedelta(seconds=5)
        old.update(sequence=99, captured_at=self.now.isoformat(),
                   expires_at=(self.now + timedelta(seconds=15)).isoformat())
        self.assertEqual(self.bridge.ingest(old)["reason"], "retired_session")
        self.bridge.disconnect()
        self.assertEqual(self.bridge.ingest(old)["reason"], "retired_session")
        self.assertEqual(self.bridge.get_progress()["status"], "unavailable")

    def test_retired_session_capacity_fails_closed_without_forgetting(self):
        for n in range(129):
            self.progress.update(producer_session="bounded-session-" + str(n), sequence=1)
            self.bridge.ingest(self.progress)
        self.assertEqual(self.bridge.health()["retired_session_count"], 128)
        rejected = deepcopy(self.progress)
        rejected.update(producer_session="new-session-over-capacity", sequence=1)
        with self.assertRaisesRegex(ValueError, "retired session capacity"):
            self.bridge.ingest(rejected)
        self.assertEqual(self.bridge.get_progress()["status"], "unavailable")
        self.assertEqual(self.bridge.health()["retired_session_count"], 128)
        # Current producer can resume monotonically; no retired ID is evicted.
        self.offer()
        retired = deepcopy(self.progress)
        retired.update(producer_session="bounded-session-0", sequence=1000)
        self.assertEqual(self.bridge.ingest(retired)["reason"], "retired_session")
        self.assertEqual(self.bridge.get_progress()["progress"]["producer_session"], "bounded-session-128")

    def test_invalid_future_and_private_fields_clear_retained_state(self):
        for case in ("notes", "answer", "source_body", "future", "invalid_type"):
            self.offer()
            self.bridge.submit_decision(self.decision(decision_id="pending-" + case))
            bad = deepcopy(self.progress)
            if case == "future":
                bad["captured_at"] = (self.now + timedelta(seconds=1)).isoformat()
            elif case == "invalid_type":
                bad = []
            else:
                bad[case] = "PRIVATE_DATA"
            with self.assertRaises(ValueError): self.bridge.ingest(bad)
            self.assertEqual(self.bridge.get_progress()["status"], "unavailable")
            self.assertEqual(self.bridge.take_decision()["status"], "unavailable")

    def test_stopped_disabled_paused_and_unavailable_do_not_authorize_speech(self):
        for status in ("paused", "stopped", "disabled"):
            context = deepcopy(PRODUCER["snapshots"][1]["context"]) if status == "paused" else None
            self.offer(status=status, context=context, can_interact=False)
            with self.assertRaises(ValueError): self.bridge.submit_decision(self.decision(decision_id=status))
            self.bridge.submit_decision(self.decision(decision_id="quiet-" + status, action="stay_quiet", objective=None))
            self.assertEqual(self.bridge.take_decision()["decision"]["action"], "stay_quiet")
        self.assertIsNone(self.bridge.get_progress()["progress"]["context"])
        self.assertEqual(self.bridge.disconnect()["status"], "disconnected")
        self.assertEqual(self.bridge.get_progress()["status"], "unavailable")

    def test_strict_decision_arguments_do_not_accept_timestamps_or_unknown_fields(self):
        self.bridge.ingest(self.progress)
        for update in ({"captured_at": self.now.isoformat()}, {"expires_at": self.now.isoformat()},
                       {"progress_sequence": str(self.progress["sequence"])}, {"objective": " "},
                       {"action": "stay_quiet"}, {"action": "speak", "objective": None}):
            with self.assertRaises(ValueError): self.bridge.submit_decision(self.decision(**update))
        request = self.decision(); del request["objective"]
        with self.assertRaises(ValueError): self.bridge.submit_decision(request)

    def test_event_receipt_is_not_decision_and_is_filtered(self):
        self.bridge.ingest(self.progress)
        args = {"producer_session": self.progress["producer_session"]}
        event = self.bridge.next_event(args)
        self.assertEqual(event, self.bridge.next_event(args))
        self.assertIsNone(self.bridge.next_event({"producer_session": "another-session"}))
        self.assertEqual(self.bridge.callback_received(event["eventId"])["status"], "callback_received_not_decided")
        self.assertEqual(self.bridge.take_decision()["status"], "unavailable")

    def test_storage_bounded_and_health_has_no_reading_contents(self):
        self.bridge.ingest(self.progress)
        for n in range(150): self.bridge.submit_decision(self.decision(decision_id="bounded-" + str(n)))
        health = self.bridge.health()
        self.assertEqual(health["receipt_count"], 128)
        self.assertEqual(health["queued_decisions"], 1)
        self.assertNotIn(self.progress["context"]["book_title"], json.dumps(health))
        self.assertNotIn("objective", json.dumps(health))
        self.assertEqual(self.bridge.take_decision()["decision"]["decision_id"], "bounded-149")
        self.assertEqual(self.bridge.take_decision()["status"], "unavailable")

    def test_concurrent_duplicates_queue_and_drain_only_once(self):
        self.bridge.ingest(self.progress)
        receipts = []
        lock = threading.Lock()
        def submit():
            result = self.bridge.submit_decision(self.decision())
            with lock: receipts.append(result)
        threads = [threading.Thread(target=submit) for _ in range(16)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(len(receipts), 16)
        self.assertEqual(sum(not result["replayed"] for result in receipts), 1)
        self.assertEqual(self.bridge.take_decision()["status"], "available")
        self.assertEqual(self.bridge.take_decision()["status"], "unavailable")


if __name__ == "__main__":
    unittest.main(verbosity=2)

