"""Per-instance memory update ownership and actual companion recall."""
from datetime import datetime, timedelta, timezone
import asyncio
import itertools
import threading

import pytest

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.memory_store import MemoryRecord, MemoryStore

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def record(memory_id="m1", namespace="p1"):
    return MemoryRecord(memory_id=memory_id, namespace=namespace, kind="fact", text="original note",
                        tags=["original"], source="user_explicit", created_at=NOW, updated_at=NOW)


class ObservedRLock:
    """Real RLock with a deterministic observation of the second writer."""
    def __init__(self):
        self.raw = threading.RLock()
        self.attempted = threading.Event()
        self.blocked = None

    def __enter__(self):
        if threading.current_thread().name == "memory-second" and self.blocked is None:
            acquired = self.raw.acquire(blocking=False)
            self.blocked = not acquired
            self.attempted.set()
            if not acquired:
                self.raw.acquire()
        else:
            self.raw.acquire()
        return self

    def __exit__(self, *_):
        self.raw.release()


def overlap_after_first_read(store, monkeypatch, first, second):
    """Pause after get's own lock exits; update must still own its outer lock."""
    observed = ObservedRLock()
    monkeypatch.setattr(store, "_lock", observed)
    captured, release, second_done = threading.Event(), threading.Event(), threading.Event()
    original_get = store.get
    errors, results = [], {}

    def gated_get(key):
        value = original_get(key)
        if threading.current_thread().name == "memory-first":
            captured.set()
            if not release.wait(3):
                raise AssertionError("first writer was not released")
        return value

    monkeypatch.setattr(store, "get", gated_get)

    def run(which, function):
        try:
            results[which] = function()
        except BaseException as error:
            errors.append(error)
        finally:
            if which == "second":
                second_done.set()

    a = threading.Thread(target=run, args=("first", first), name="memory-first", daemon=True)
    b = threading.Thread(target=run, args=("second", second), name="memory-second", daemon=True)
    a.start()
    try:
        assert captured.wait(2)
        b.start()
        assert observed.attempted.wait(2)
        # On the old implementation, allow the competing commit to complete
        # before releasing its stale snapshot. No scheduling sleeps are needed.
        if not observed.blocked:
            assert second_done.wait(2)
    finally:
        release.set()
        a.join(3)
        if b.ident is not None:
            b.join(3)
    assert not a.is_alive() and not b.is_alive()
    assert errors == []
    assert observed.blocked is True, "update released ownership after reading"
    return results


@pytest.mark.parametrize("first_is_tags", [False, True])
def test_update_serializes_both_orders_and_reopened_runtime_recalls_tags(tmp_path, monkeypatch, first_is_tags):
    path = tmp_path / "memory.db"
    with MemoryStore(path) as store:
        store.put(record())
        store.put(record("private-other", "p2").model_copy(update={"tags": ["quantum"]}))
        sequence = itertools.count(1)
        monkeypatch.setattr(store, "_checked_time", lambda value: value or NOW + timedelta(seconds=next(sequence)))
        text_update = lambda: store.update("m1", text="revised note")
        tag_update = lambda: store.update("m1", text="original note", tags=["quantum"])
        first, second = (tag_update, text_update) if first_is_tags else (text_update, tag_update)
        results = overlap_after_first_read(store, monkeypatch, first, second)
        final = store.get("m1")
        assert final.tags == ["quantum"]
        assert final.text == ("revised note" if first_is_tags else "original note")
        assert results["second"].tags == ["quantum"]
        events = list(reversed(store.history("m1")))
        assert [e.action for e in events] == ["ADD", "UPDATE", "UPDATE"]
        assert [e.created_at for e in events] == [NOW, NOW + timedelta(seconds=1), NOW + timedelta(seconds=2)]
        assert events[1].previous_value == "original note"
        assert events[2].previous_value == events[1].new_value
        assert events[2].new_value == final.text
        assert len(store.history("private-other")) == 1
        assert store._db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "1"

    with MemoryStore(path) as reopened:
        assert [m.memory_id for m in reopened.search("quantum", namespace="p1")] == ["m1"]
        assert [m.memory_id for m in reopened.search("quantum", namespace="p2")] == ["private-other"]
        prompts = []

        async def responder(prompt):
            prompts.append(prompt)
            return "Recalled the explicit note."

        runtime = CompanionChatRuntime(
            persona=CompanionPersona(persona_id="p1", display_name="P", visual_skin_id="skin", instructions="Trusted."),
            responder=responder, memory_store=reopened,
        )
        result = asyncio.run(runtime.send(dict(request_id="r1", session_id="s1", persona_id="p1", text="quantum")))
        assert result.recalled_memory_ids == ["m1"]
        assert [m.memory_id for m in prompts[0].memories] == ["m1"]
        assert any(m.role == "user" and "LOCAL_RECALLED_MEMORY" in m.content and final.text in m.content
                   for m in prompts[0].provider_messages())
        assert len(reopened.history("m1")) == 3  # reading/chat does not create a memory write


@pytest.mark.parametrize("explicit_time", [False, True])
def test_overlapping_delete_cannot_be_undone_by_stale_update(tmp_path, monkeypatch, explicit_time):
    path = tmp_path / "memory.db"
    with MemoryStore(path) as store:
        store.put(record())
        sequence = itertools.count(1)
        monkeypatch.setattr(store, "_checked_time", lambda value: value or NOW + timedelta(seconds=next(sequence)))
        results = overlap_after_first_read(
            store, monkeypatch,
            lambda: store.update("m1", text="revised note"),
            lambda: store.delete("m1", deleted_at=NOW + timedelta(seconds=2) if explicit_time else None),
        )
        assert results["second"] is True and store.get("m1") is None
        events = list(reversed(store.history("m1")))
        assert [e.action for e in events] == ["ADD", "UPDATE", "DELETE"]
        assert [e.created_at for e in events] == [NOW, NOW + timedelta(seconds=1), NOW + timedelta(seconds=2)]
        assert events[-1].previous_value == "revised note" and events[-1].is_deleted
    with MemoryStore(path) as reopened:
        assert reopened.get("m1") is None and reopened.search("revised", namespace="p1") == []
        with pytest.raises(ValueError, match="not found"):
            reopened.update("m1", text="must not resurrect", updated_at=NOW + timedelta(seconds=3))
        assert len(reopened.history("m1")) == 3


def test_absent_update_has_no_record_or_audit():
    with MemoryStore() as store:
        with pytest.raises(ValueError, match="not found"):
            store.update("missing", text="no implicit add")
        assert store.get("missing") is None and store.history("missing") == []


def test_delete_explicit_backward_time_still_rejects_without_mutation():
    with MemoryStore() as store:
        store.put(record())
        latest = store.update("m1", text="revised", updated_at=NOW + timedelta(seconds=1))
        with pytest.raises(ValueError, match="cannot precede latest update"):
            store.delete("m1", deleted_at=NOW)
        assert store.get("m1") == latest and len(store.history("m1")) == 2
        assert store.delete("m1", deleted_at=NOW + timedelta(seconds=2))
        assert store.get("m1") is None and len(store.history("m1")) == 3


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_update_audit_failure_rolls_back_and_releases_reentrant_lock(tmp_path, monkeypatch, failure):
    path = tmp_path / "memory.db"
    with MemoryStore(path) as store:
        store.put(record())
        before = list(store._db.iterdump())
        original_history = store._add_history

        def fail_history(**kwargs):
            if kwargs["action"] == "UPDATE":
                raise failure("synthetic audit failure")
            return original_history(**kwargs)

        monkeypatch.setattr(store, "_add_history", fail_history)
        with pytest.raises(failure, match="synthetic audit failure"):
            store.update("m1", text="must roll back", tags=["quantum"], updated_at=NOW + timedelta(seconds=1))
        assert list(store._db.iterdump()) == before
        monkeypatch.setattr(store, "_add_history", original_history)
        outcome = []
        worker = threading.Thread(target=lambda: outcome.append(store.update(
            "m1", text="valid retry", tags=["quantum"], updated_at=NOW + timedelta(seconds=2))), daemon=True)
        worker.start()
        worker.join(2)
        assert not worker.is_alive() and len(outcome) == 1
        assert len(store.history("m1")) == 2
    with MemoryStore(path) as reopened:
        assert reopened.get("m1").text == "valid retry" and reopened.get("m1").tags == ["quantum"]


@pytest.mark.parametrize("text,tags", [(" ", None), ("x" * 2001, None), ("valid", [" untrimmed"]), ("valid", ["x"] * 17)])
def test_invalid_update_remains_validated_without_partial_commit(text, tags):
    with MemoryStore() as store:
        initial = record()
        store.put(initial)
        with pytest.raises(ValueError):
            store.update("m1", text=text, tags=tags, updated_at=NOW + timedelta(seconds=1))
        assert store.get("m1") == initial and len(store.history("m1")) == 1
        assert store.update("m1", text="valid", updated_at=NOW + timedelta(seconds=2)).tags == ["original"]
