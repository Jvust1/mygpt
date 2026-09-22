import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from mygpt_brain import Brain, StudyContext, StudyEvent

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
TEXT = "SIMULATED learning source: x + x = 2x."


def context(**changes):
    data = dict(session_id="session-1", course_id="demo-course", book_id="demo-book",
                book_version="v1", section_id="section-1", source_id="source-1",
                source_sha256=hashlib.sha256(TEXT.encode()).hexdigest(), mode="learn",
                captured_at=NOW, expires_at=NOW + timedelta(seconds=120))
    data.update(changes)
    return StudyContext(**data)


def event(sequence=1, kind="SESSION_STARTED", **changes):
    data = dict(event_id=f"event-{sequence}", session_id="session-1", sequence=sequence,
                occurred_at=NOW, kind=kind)
    if kind in ("SESSION_STARTED", "CONTEXT_CHANGED", "SESSION_RESUMED"):
        data["context"] = context()
    data.update(changes)
    return StudyEvent(**data)


@pytest.fixture
def brain():
    with Brain() as value:
        yield value


@pytest.mark.parametrize("mode", ["preview", "learn", "review", "practice"])
def test_context_modes(mode):
    assert StudyContext.model_validate_json(context(mode=mode).model_dump_json()).mode == mode


@pytest.mark.parametrize("field,value", [
    ("schema_version", "v99"), ("evidence_kind", "BOOK"), ("mode", "unknown"),
    ("session_id", ""), ("book_id", "../private"), ("book_id", "https://x.invalid"),
    ("section_id", "x" * 97), ("source_sha256", "a" * 63),
    ("source_sha256", "G" * 64), ("captured_at", NOW.replace(tzinfo=None)),
    ("expires_at", NOW), ("expires_at", NOW + timedelta(seconds=301)),
    ("raw_messages", "private data"), ("api_key", "do-not-store"),
])
def test_context_rejects_bad_input(field, value):
    with pytest.raises(ValidationError):
        context(**{field: value})


@pytest.mark.parametrize("field,value", [
    ("sequence", 0), ("sequence", -1), ("sequence", "1"), ("sequence", True),
    ("sequence", 1.5), ("sequence", 2**53), ("schema_version", "v2"),
    ("producer_id", "untrusted"), ("kind", "SCREENSHOT"),
    ("occurred_at", NOW.replace(tzinfo=None)), ("password", "do-not-store"),
])
def test_event_rejects_bad_input(field, value):
    with pytest.raises(ValidationError):
        event(**{field: value})


@pytest.mark.parametrize("kind", ["SESSION_STARTED", "CONTEXT_CHANGED", "SESSION_RESUMED"])
def test_snapshot_required(kind):
    with pytest.raises(ValidationError):
        event(kind=kind, context=None)


@pytest.mark.parametrize("kind", ["SESSION_PAUSED", "SESSION_ENDED", "DISCONNECTED",
                                 "QUIET_REQUESTED", "HELP_REQUESTED", "RECALL_REQUESTED"])
def test_control_cannot_smuggle_context(kind):
    with pytest.raises(ValidationError):
        event(kind=kind, context=context())


def test_session_and_time_consistency():
    with pytest.raises(ValidationError):
        event(context=context(session_id="other"))
    with pytest.raises(ValidationError):
        event(occurred_at=NOW - timedelta(seconds=1))


def test_default_quiet_and_no_model(brain):
    assert brain.view(now=NOW)["status"] == "no_session"
    receipt = brain.ingest(event(), now=NOW)
    assert receipt.accepted and receipt.decision.action == "stay_silent"
    assert receipt.decision.model_called is False
    assert brain.view(now=NOW)["context"]["section_id"] == "section-1"


def test_ten_replays_do_not_redeliver(brain):
    brain.ingest(event(), now=NOW)
    help_event = event(2, "HELP_REQUESTED")
    assert brain.ingest(help_event, now=NOW).decision.action == "explain"
    for _ in range(10):
        result = brain.ingest(help_event, now=NOW)
        assert result.disposition == "duplicate"
        assert result.decision.action == "stay_silent"
    assert len(brain.recent_decisions()) == 2


def test_event_id_collision(brain):
    brain.ingest(event(), now=NOW)
    assert brain.ingest(event(2, "HELP_REQUESTED", event_id="event-1"), now=NOW).disposition == "event_id_conflict"
    assert brain.view(now=NOW)["last_sequence"] == 1


def test_out_of_order_new_id(brain):
    brain.ingest(event(), now=NOW)
    assert brain.ingest(event(1, "HELP_REQUESTED", event_id="other"), now=NOW).disposition == "out_of_order"
    assert len(brain.recent_decisions()) == 1


def test_gap_invalidates_context_and_explicit_resync(brain):
    brain.ingest(event(), now=NOW)
    assert brain.ingest(event(4, "HELP_REQUESTED"), now=NOW).disposition == "sequence_gap"
    assert brain.view(now=NOW)["context"] is None
    assert brain.view(now=NOW)["status"] == "disconnected"
    assert brain.ingest(event(2, "SESSION_RESUMED"), now=NOW).accepted
    assert brain.ingest(event(3, "HELP_REQUESTED"), now=NOW).decision.action == "explain"


@pytest.mark.parametrize("kind", ["HELP_REQUESTED", "RECALL_REQUESTED"])
def test_explicit_requests_and_quiet_mode(brain, kind):
    brain.ingest(event(), now=NOW)
    brain.ingest(event(2, "QUIET_REQUESTED"), now=NOW)
    result = brain.ingest(event(3, kind), now=NOW)
    assert result.decision.action == ("explain" if kind == "HELP_REQUESTED" else "recall_check")
    assert result.decision.source_ref == context().reference
    assert brain.view(now=NOW)["quiet"] is True
    assert brain.view(now=NOW)["model_calls"] == 0


@pytest.mark.parametrize("kind,status", [("SESSION_PAUSED", "paused"), ("DISCONNECTED", "disconnected"),
                                        ("SESSION_ENDED", "ended")])
def test_stop_events_clear_context(brain, kind, status):
    brain.ingest(event(), now=NOW)
    brain.ingest(event(2, kind), now=NOW)
    assert brain.view(now=NOW)["status"] == status
    assert brain.view(now=NOW)["context"] is None
    assert not brain.ingest(event(3, "HELP_REQUESTED"), now=NOW).accepted


def test_resume_requires_fresh_context(brain):
    brain.ingest(event(), now=NOW)
    brain.ingest(event(2, "SESSION_PAUSED"), now=NOW)
    later = NOW + timedelta(seconds=130)
    stale = event(3, "SESSION_RESUMED", occurred_at=later)
    assert brain.ingest(stale, now=later).disposition == "invalid_context_time"
    fresh = event(3, "SESSION_RESUMED", occurred_at=later,
                  context=context(captured_at=later, expires_at=later + timedelta(seconds=120)))
    assert brain.ingest(fresh, now=later).accepted


def test_expiry_does_not_guess_or_call_model(brain):
    brain.ingest(event(), now=NOW)
    later = NOW + timedelta(seconds=120)
    assert brain.view(now=later)["status"] == "context_expired"
    result = brain.ingest(event(2, "HELP_REQUESTED", occurred_at=later), now=later)
    assert result.decision.reason == "fresh_context_required"
    assert result.decision.action == "stay_silent"
    assert brain.view(now=later)["context"] is None


@pytest.mark.parametrize("delta,reason", [(-301, "stale_event"), (6, "future_event")])
def test_event_clock_boundaries(brain, delta, reason):
    value = event(kind="HELP_REQUESTED", occurred_at=NOW + timedelta(seconds=delta))
    assert brain.ingest(value, now=NOW).disposition == reason
    assert brain.view(now=NOW)["status"] == "no_session"


def test_timezone_equivalent_context(brain):
    value = event(occurred_at=NOW.astimezone(timezone(timedelta(hours=8))))
    assert brain.ingest(value, now=NOW).accepted


def test_time_reversal(brain):
    brain.ingest(event(), now=NOW)
    result = brain.ingest(event(2, "HELP_REQUESTED", occurred_at=NOW - timedelta(seconds=1)), now=NOW)
    assert result.disposition == "time_reversal"


@pytest.mark.parametrize("field", ["course_id", "book_id", "book_version"])
def test_cannot_mix_books_in_session(brain, field):
    brain.ingest(event(), now=NOW)
    result = brain.ingest(event(2, "CONTEXT_CHANGED", context=context(**{field: "different"})), now=NOW)
    assert result.disposition == "book_identity_mismatch"
    assert brain.view(now=NOW)["context"][field] == getattr(context(), field)


def test_previous_session_cannot_take_over(brain):
    brain.ingest(event(), now=NOW)
    new = event(session_id="session-2", event_id="new-start", context=context(session_id="session-2", book_id="other-book"))
    assert brain.ingest(new, now=NOW).accepted
    assert brain.ingest(event(2, "HELP_REQUESTED"), now=NOW).disposition == "inactive_session"
    assert brain.view(now=NOW)["session_id"] == "session-2"


def test_ended_session_cannot_restart(brain):
    brain.ingest(event(), now=NOW)
    brain.ingest(event(2, "SESSION_ENDED"), now=NOW)
    assert brain.ingest(event(3, "SESSION_RESUMED"), now=NOW).disposition == "session_ended"
    assert brain.ingest(event(event_id="different-start"), now=NOW).disposition == "invalid_session_start"


def test_restart_preserves_receipts_and_quiet(tmp_path):
    path = str(tmp_path / "brain.db")
    with Brain(path) as first:
        first.ingest(event(), now=NOW)
        first.ingest(event(2, "QUIET_REQUESTED"), now=NOW)
    with Brain(path) as second:
        assert second.ingest(event(), now=NOW).disposition == "duplicate"
        assert second.view(now=NOW)["quiet"] is True
        assert len(second.recent_decisions()) == 2
        assert second.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_concurrent_instances_deliver_once(tmp_path):
    path = str(tmp_path / "brain.db")
    with Brain(path) as first, Brain(path) as second:
        first.ingest(event(), now=NOW)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(b.ingest, event(2, "HELP_REQUESTED"), now=NOW) for b in (first, second)]
            results = [f.result() for f in futures]
        assert sum(r.accepted for r in results) == 1
        assert len(first.recent_decisions()) == 2


def test_transaction_rolls_back_state_with_event_failure(brain):
    brain.ingest(event(), now=NOW)
    brain.db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'injected'); END")
    with pytest.raises(sqlite3.IntegrityError):
        brain.ingest(event(2, "SESSION_PAUSED"), now=NOW)
    assert brain.view(now=NOW)["status"] == "active"
    assert brain.view(now=NOW)["last_sequence"] == 1
    assert len(brain.recent_decisions()) == 1


@pytest.mark.parametrize("version", [0, 999])
def test_unknown_database_is_preserved(tmp_path, version):
    path = str(tmp_path / "foreign.db")
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE precious (value TEXT)")
        db.execute("INSERT INTO precious VALUES ('unchanged')")
        db.execute(f"PRAGMA user_version={version}")
    with pytest.raises(ValueError):
        Brain(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM precious").fetchone()[0] == "unchanged"
        assert db.execute("PRAGMA user_version").fetchone()[0] == version


@pytest.mark.parametrize("limit", [0, -1, 51, True, "2"])
def test_trace_limit_rejects_invalid_values(brain, limit):
    with pytest.raises(ValueError):
        brain.recent_decisions(limit)


def test_no_private_payload_or_source_body_in_audit(brain):
    brain.ingest(event(), now=NOW)
    dump = "\n".join(brain.db.iterdump())
    assert TEXT not in dump
    assert "raw_messages" not in dump
    assert brain.recent_decisions()[0]["decision"]["model_called"] is False


def test_invalid_model_construct_is_revalidated(brain):
    forged = StudyEvent.model_construct(**event().model_dump(), password="forbidden")
    # model_construct drops forbidden extras, so forge a forbidden field value instead.
    object.__setattr__(forged, "producer_id", "untrusted")
    with pytest.raises(ValidationError):
        brain.ingest(forged, now=NOW)


def test_json_and_large_input_boundaries(brain):
    assert brain.ingest(event().model_dump_json(), now=NOW).accepted
    with pytest.raises(ValueError):
        brain.ingest(" " * 16385)
    with pytest.raises(ValidationError):
        brain.ingest('{"sequence": NaN}')
    with pytest.raises(ValueError):
        brain.view(now=NOW.replace(tzinfo=None))


@pytest.mark.parametrize("field", ["course_id", "book_id", "book_version", "section_id", "source_id"])
def test_reference_delimiter_not_allowed_in_identifiers(field):
    with pytest.raises(ValidationError):
        context(**{field: "a:b"})


def test_expired_help_stays_visibly_blocked(brain):
    brain.ingest(event(), now=NOW)
    later = NOW + timedelta(seconds=120)
    brain.ingest(event(2, "HELP_REQUESTED", occurred_at=later), now=later)
    assert brain.view(now=later)["status"] == "context_unavailable"
    assert brain.view(now=later)["host_state"] == "blocked"


def test_delayed_start_cannot_replace_newer_active_session(brain):
    brain.ingest(event(), now=NOW)
    old = NOW - timedelta(seconds=10)
    value = event(session_id="session-2", event_id="delayed-start", occurred_at=old,
                  context=context(session_id="session-2", captured_at=old))
    assert brain.ingest(value, now=NOW).disposition == "stale_session_start"
    assert brain.view(now=NOW)["session_id"] == "session-1"


def test_equivalent_timezone_replay_is_duplicate(brain):
    value = event()
    brain.ingest(value, now=NOW)
    offset = timezone(timedelta(hours=8))
    other = event(occurred_at=NOW.astimezone(offset),
                  context=context(captured_at=NOW.astimezone(offset),
                                  expires_at=(NOW + timedelta(seconds=120)).astimezone(offset)))
    assert brain.ingest(other, now=NOW).disposition == "duplicate"
