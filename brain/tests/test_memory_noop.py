"""Idempotent memory writes return the record that is actually persisted."""
from datetime import datetime, timedelta, timezone

import pytest

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.memory_store import MemoryRecord, MemoryStore

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def record(memory_id="m1", namespace="p1", *, updated_at=NOW):
    return MemoryRecord(memory_id=memory_id, namespace=namespace, kind="fact", text="quantum memory",
                        tags=["a", "b"], source="user_explicit", created_at=NOW, updated_at=updated_at)


def write(store, item, operation, *, text=None, tags=None, at=NOW + timedelta(seconds=10)):
    text = item.text if text is None else text
    if operation == "update":
        return store.update(item.memory_id, text=text, tags=tags, updated_at=at)
    candidate = item.model_copy(update={"text": text, "tags": item.tags if tags is None else tags, "updated_at": at})
    return store.put(candidate, allow_update=True)


@pytest.mark.parametrize("operation", ["put", "update"])
def test_noop_returns_current_record_without_writes_even_after_reopen(tmp_path, operation):
    path = tmp_path / "memory.db"
    original = record()
    with MemoryStore(path) as store:
        store.put(original)
        baseline = store._db.total_changes
        for step in range(1, 5):
            returned = write(store, original, operation, at=NOW + timedelta(seconds=step))
            assert returned == store.get("m1") == original
            assert returned.model_dump(mode="json") == original.model_dump(mode="json")
            assert store._db.total_changes == baseline
            assert len(store.history("m1")) == 1
    with MemoryStore(path) as reopened:
        returned = write(reopened, original, operation)
        assert returned == reopened.get("m1") == original
        assert reopened._db.total_changes == 0 and len(reopened.history("m1")) == 1


@pytest.mark.parametrize("operation", ["put", "update"])
def test_noop_uses_existing_tag_deduplication_and_time_normalization(operation):
    original = record()
    with MemoryStore() as store:
        store.put(original)
        later_offset = (NOW + timedelta(seconds=20)).astimezone(timezone(timedelta(hours=8)))
        returned = write(store, original, operation, tags=["a", "a", "b"], at=later_offset)
        assert returned == original and returned.tags == ["a", "b"]
        assert returned.updated_at == NOW and len(store.history("m1")) == 1


@pytest.mark.parametrize("operation", ["put", "update"])
def test_noop_does_not_bypass_backward_or_naive_time_validation(operation):
    original = record(updated_at=NOW + timedelta(seconds=2))
    with MemoryStore() as store:
        store.put(original)
        for at in (NOW + timedelta(seconds=1), NOW.replace(tzinfo=None)):
            with pytest.raises(ValueError):
                write(store, original, operation, at=at)
            assert store.get("m1") == original and len(store.history("m1")) == 1
        assert write(store, original, operation, at=original.updated_at) == original


@pytest.mark.parametrize("operation", ["put", "update"])
@pytest.mark.parametrize("changes", [{"text": "quantum memory "}, {"tags": []}, {"tags": ["b", "a"]}])
def test_genuine_whitespace_or_tag_change_returns_new_persisted_record(operation, changes):
    original = record()
    with MemoryStore() as store:
        store.put(original)
        returned = write(store, original, operation, **changes)
        assert returned == store.get("m1") and returned != original
        assert returned.updated_at == NOW + timedelta(seconds=10)
        assert returned.text == changes.get("text", original.text)
        assert returned.tags == changes.get("tags", original.tags)
        events = store.history("m1")
        assert [event.action for event in events] == ["UPDATE", "ADD"]
        assert events[0].previous_value == original.text and events[0].new_value == returned.text


@pytest.mark.parametrize("operation", ["put", "update"])
def test_noop_candidate_still_rejects_untrimmed_tags_and_blank_text(operation):
    original = record()
    with MemoryStore() as store:
        store.put(original)
        baseline = store._db.total_changes
        for changes in ({"tags": ["a ", "b"]}, {"text": " \t\n"}):
            with pytest.raises(ValueError):
                write(store, original, operation, **changes)
            assert store.get("m1") == original and store._db.total_changes == baseline


def test_put_still_requires_allow_update_for_existing_id():
    original = record()
    with MemoryStore() as store:
        store.put(original)
        with pytest.raises(ValueError, match="already exists"):
            store.put(original)
        assert store.get("m1") == original and len(store.history("m1")) == 1


@pytest.mark.asyncio
async def test_noop_preserves_reopened_actual_recall_recency_and_namespace(tmp_path):
    path = tmp_path / "memory.db"
    old = record()
    newer = record("m2", updated_at=NOW + timedelta(seconds=1))
    with MemoryStore(path) as store:
        store.put(old)
        store.put(newer)
        store.put(record("private-other", "p2", updated_at=NOW + timedelta(seconds=100)))
        assert write(store, old, "update", at=NOW + timedelta(seconds=200)) == old
        assert [m.memory_id for m in store.recent(namespace="p1")] == ["m2", "m1"]
    with MemoryStore(path) as reopened:
        assert write(reopened, old, "put", at=NOW + timedelta(seconds=300)) == old
        prompts = []

        async def responder(prompt):
            prompts.append(prompt)
            return "Recalled the stored notes."

        runtime = CompanionChatRuntime(
            persona=CompanionPersona(persona_id="p1", display_name="P", visual_skin_id="skin", instructions="Trusted."),
            responder=responder, memory_store=reopened,
        )
        result = await runtime.send(dict(request_id="r1", session_id="s1", persona_id="p1", text="quantum memory"))
        assert result.recalled_memory_ids == ["m2", "m1"]
        assert [m.memory_id for m in prompts[0].memories] == ["m2", "m1"]
        assert [m.updated_at for m in prompts[0].memories] == [newer.updated_at, old.updated_at]
        assert reopened._db.total_changes == 0
        assert len(reopened.history("m1")) == len(reopened.history("m2")) == 1
