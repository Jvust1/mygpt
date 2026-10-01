"""End-to-end deterministic Reader selection demo; synthetic text only."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone

from .adapters import validate_evidence
from .core import Brain, StudyEvent
from .reader_snapshot import map_reader_snapshot

NOW = datetime(2026, 9, 23, tzinfo=timezone.utc)


def fixture():
    """Example DTO subset, NOT copied from a textbook or recorded user activity."""
    version = "demo_book@0123456789abcdef"
    manifest = {"schema": "reader_pack_v1", "course_id": "demo-course", "book_id": "demo-book",
                "book_version_id": version, "sections": [{"id": "section-1"}]}
    section = {"id": "section-1", "book_version_id": version,
               "records": [{"id": "record-1", "section_id": "section-1", "kind": "paragraph",
                            "title": "合成演示，不是教材内容", "parts": [
                                {"kind": "text", "text": "两个相同的量相加："},
                                {"kind": "math", "latex": "x+x=2x", "display": True}], "assets": []}],
               "practice_groups": []}
    snapshot = {"session_id": "demo-reader-session", "epoch": 1, "mode": "learn",
                "captured_at": NOW, "expires_at": NOW + timedelta(seconds=120),
                "selection": {"course_id": "demo-course", "book_id": "demo-book", "book_version_id": version,
                              "section_id": "section-1", "record_id": "record-1", "layer": "source"}}
    return manifest, section, snapshot


def demo():
    manifest, section, snap = fixture()
    evidence = map_reader_snapshot(manifest, section, snap, expected_session_id=snap["session_id"],
                                   expected_epoch=1, now=NOW)
    with Brain() as brain:
        start = StudyEvent(event_id="reader-start", session_id=evidence.context.session_id,
                           sequence=1, occurred_at=NOW, kind="SESSION_STARTED", context=evidence.context)
        started = brain.ingest(start, now=NOW)
        assert started.accepted
        validate_evidence(brain, evidence, now=NOW)
        help_event = StudyEvent(event_id="reader-help", session_id=evidence.context.session_id,
                                sequence=2, occurred_at=NOW, kind="HELP_REQUESTED")
        help_result = brain.ingest(help_event, now=NOW)
        duplicate = brain.ingest(help_event, now=NOW)
        brain.ingest(StudyEvent(event_id="reader-pause", session_id=evidence.context.session_id,
                                sequence=3, occurred_at=NOW, kind="SESSION_PAUSED"), now=NOW)
        return {"scope": "SIMULATED_READER_TO_BRAIN", "live_book_connected": False,
                "source_payload": json.loads(evidence.text),
                "source_sha256": evidence.context.source_sha256,
                "context": evidence.context.model_dump(mode="json"),
                "start": started.model_dump(mode="json"), "help": help_result.model_dump(mode="json"),
                "duplicate": duplicate.model_dump(mode="json"), "paused": brain.view(now=NOW),
                "paid_model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(demo(), ensure_ascii=False, sort_keys=True, indent=2))
