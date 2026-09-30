from datetime import datetime, timedelta, timezone
import pytest
from mygpt_brain.memory_store import MemoryRecord, MemoryStore

NOW=datetime(2026,9,29,14,0,tzinfo=timezone.utc)

def rec(mid,text,**kw):
    return MemoryRecord(memory_id=mid,namespace="companion",kind=kw.get("kind","preference"),
        text=text,tags=kw.get("tags",[]),source=kw.get("source","user_explicit"),
        created_at=NOW,updated_at=kw.get("updated_at",NOW))

def test_explicit_memory_round_trip_and_no_duplicate_overwrite():
    with MemoryStore() as store:
        store.put(rec("m1","我喜欢简洁回答",tags=["style"]))
        assert store.get("m1").text=="我喜欢简洁回答"
        with pytest.raises(ValueError,match="already exists"):
            store.put(rec("m1","different"))

def test_search_is_namespace_bounded():
    with MemoryStore() as store:
        store.put(rec("m1","数学学习时希望先看预习",tags=["数学","学习"]))
        other=MemoryRecord(memory_id="m2",namespace="other",kind="fact",text="数学 secret",
            tags=[],source="user_explicit",created_at=NOW,updated_at=NOW)
        store.put(other)
        result=store.search("数学 学习",namespace="companion")
        assert [x.memory_id for x in result]==["m1"]

def test_update_requires_explicit_flag():
    with MemoryStore() as store:
        store.put(rec("m1","A"))
        newer=rec("m1","B",updated_at=NOW+timedelta(seconds=1))
        store.put(newer,allow_update=True)
        assert store.get("m1").text=="B"


def test_memory_history_preserves_add_update_delete(tmp_path):
    path = tmp_path / "memory.sqlite3"
    with MemoryStore(path) as store:
        store.put(rec("m-history", "old", tags=["原始"]))
        store.update(
            "m-history",
            text="new",
            tags=["修正"],
            updated_at=NOW + timedelta(seconds=1),
        )
        assert store.get("m-history").text == "new"
        events = store.history("m-history")
        assert [event.action for event in events] == ["UPDATE", "ADD"]
        assert events[0].previous_value == "old"
        assert events[0].new_value == "new"

        assert store.delete(
            "m-history", deleted_at=NOW + timedelta(seconds=2)
        ) is True
        assert store.get("m-history") is None
        events = store.history("m-history")
        assert [event.action for event in events] == ["DELETE", "UPDATE", "ADD"]
        assert events[0].previous_value == "new"
        assert events[0].new_value is None
        assert events[0].is_deleted is True


def test_identical_update_does_not_spam_history():
    with MemoryStore() as store:
        store.put(rec("m-noop", "same", tags=["x"]))
        same = rec("m-noop", "same", tags=["x"], updated_at=NOW + timedelta(seconds=1))
        store.put(same, allow_update=True)
        assert [event.action for event in store.history("m-noop")] == ["ADD"]


def test_memory_identity_fields_cannot_be_rewritten():
    with MemoryStore() as store:
        store.put(rec("m-identity", "A"))
        moved = MemoryRecord(
            memory_id="m-identity",
            namespace="other",
            kind="preference",
            text="B",
            tags=[],
            source="user_explicit",
            created_at=NOW,
            updated_at=NOW + timedelta(seconds=1),
        )
        with pytest.raises(ValueError, match="immutable memory identity"):
            store.put(moved, allow_update=True)


def test_delete_missing_memory_is_idempotent():
    with MemoryStore() as store:
        assert store.delete("missing", deleted_at=NOW) is False
        assert store.history("missing") == []
