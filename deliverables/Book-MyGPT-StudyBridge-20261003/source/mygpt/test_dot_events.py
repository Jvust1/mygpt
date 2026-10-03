"""Synthetic event consumer only; no real subscription, callback, dot or model."""
from copy import deepcopy
from datetime import datetime, timedelta
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from test_book_progress import bridge, PRODUCER

spec = importlib.util.spec_from_file_location("mygpt_brain.dot_events", Path(__file__).with_name("dot_events.py"))
events = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = events
spec.loader.exec_module(events)


class EventTests(unittest.TestCase):
    def setUp(self):
        self.progress = deepcopy(PRODUCER["snapshots"][1])
        self.now = datetime.fromisoformat(self.progress["captured_at"].replace("Z", "+00:00"))
        self.outbox = events.BookStudyEventOutbox(clock=lambda: self.now)
        self.args = {"producer_session": self.progress["producer_session"]}

    def offer(self, **changes):
        self.progress = deepcopy(self.progress)
        self.progress.update(changes)
        self.progress["sequence"] += 1
        self.progress["captured_at"] = self.now.isoformat()
        self.progress["expires_at"] = (self.now + timedelta(seconds=15)).isoformat()
        return self.outbox.offer(self.progress)

    def test_mcp_catalog_and_strict_event_body(self):
        catalog = events.event_definition()
        self.assertEqual(events.PROTOCOL_VERSION, "2026-07-28")
        self.assertEqual(catalog["delivery"], ["webhook"])
        self.assertFalse(catalog["inputSchema"]["additionalProperties"])
        self.outbox.offer(self.progress)
        body = self.outbox.next_event(self.args)
        self.assertEqual(body["name"], catalog["name"])
        self.assertIsNone(body["cursor"])
        events.StudyEvent.model_validate(body)
        self.assertEqual(body["data"]["progress"], bridge.BookProgress.model_validate(self.progress).wire())
        self.assertNotIn("PRIVATE_", json.dumps(body))
        self.assertLessEqual(len(json.dumps(body).encode()), 8192)

    def test_filters_are_not_ignored(self):
        self.outbox.offer(self.progress)
        self.assertIsNone(self.outbox.next_event({"producer_session": "different-session"}))
        with self.assertRaises(ValueError): self.outbox.next_event({**self.args, "notes": "PRIVATE"})

    def test_retry_keeps_identity_and_is_not_dot_decision(self):
        self.outbox.offer(self.progress)
        first = self.outbox.next_event(self.args)
        self.assertEqual(first, self.outbox.next_event(self.args))
        first["data"]["progress"]["sequence"] = 0
        self.assertNotEqual(first, self.outbox.next_event(self.args))
        receipt = self.outbox.callback_received(first["eventId"])
        self.assertEqual(receipt["status"], "callback_received_not_decided")
        self.assertFalse(receipt["dot_decision_observed"])

    def test_routine_heartbeats_are_coalesced_with_latest_sequence(self):
        self.outbox.offer(self.progress)
        self.outbox.callback_received(self.outbox.next_event(self.args)["eventId"])
        for seconds in range(5, 31, 5):
            self.now += timedelta(seconds=5)
            result = self.offer()
            self.assertEqual(result["status"], "queued_not_delivered")
            body = self.outbox.next_event(self.args)
            if seconds < 30: self.assertIsNone(body)
        self.assertEqual(body["data"]["progress"]["sequence"], self.progress["sequence"])
        self.assertEqual(self.outbox.current()["sequence"], self.progress["sequence"])

    def test_mode_change_is_immediately_eligible(self):
        self.outbox.offer(self.progress)
        self.outbox.callback_received(self.outbox.next_event(self.args)["eventId"])
        self.now += timedelta(seconds=1)
        context = deepcopy(self.progress["context"]); context["mode"] = "review"
        self.offer(context=context)
        self.assertEqual(self.outbox.next_event(self.args)["data"]["progress"]["context"]["mode"], "review")

    def test_disable_replaces_pending_and_late_receipt_cannot_remove_it(self):
        self.outbox.offer(self.progress)
        old = self.outbox.next_event(self.args)
        self.now += timedelta(seconds=1)
        self.offer(status="disabled", context=None, can_interact=False)
        tombstone = self.outbox.next_event(self.args)
        self.assertIsNone(tombstone["data"]["progress"]["context"])
        self.assertEqual(self.outbox.callback_received(old["eventId"])["status"], "superseded_receipt_ignored")
        self.assertEqual(tombstone, self.outbox.next_event(self.args))

    def test_heartbeat_cannot_delay_unacknowledged_mode_change(self):
        self.outbox.offer(self.progress)
        self.outbox.callback_received(self.outbox.next_event(self.args)["eventId"])
        self.now += timedelta(seconds=1)
        context = deepcopy(self.progress["context"]); context["mode"] = "review"
        self.offer(context=context)
        self.now += timedelta(seconds=1)
        self.offer()
        self.assertEqual(self.outbox.next_event(self.args)["data"]["progress"]["sequence"], self.progress["sequence"])

    def test_expiry_or_private_field_clears_retained_state(self):
        self.outbox.offer(self.progress)
        self.now += timedelta(seconds=16)
        self.assertIsNone(self.outbox.current())
        self.assertIsNone(self.outbox.next_event(self.args))
        self.now -= timedelta(seconds=16)
        self.outbox.offer(self.progress)
        with self.assertRaises(ValueError): self.outbox.offer({**self.progress, "notes": "PRIVATE"})
        self.assertIsNone(self.outbox.current())

    def test_out_of_order_duplicate_and_conflict(self):
        self.outbox.offer(self.progress)
        body = self.outbox.next_event(self.args)
        self.assertEqual(self.outbox.offer(self.progress)["status"], "duplicate_ignored")
        old = deepcopy(self.progress); old["sequence"] -= 1
        self.assertEqual(self.outbox.offer(old)["status"], "stale_ignored")
        bad = deepcopy(self.progress); bad["idle_seconds"] += 1
        with self.assertRaises(bridge.ProgressError): self.outbox.offer(bad)
        self.assertEqual(body, self.outbox.next_event(self.args))


if __name__ == "__main__":
    unittest.main(verbosity=2)

