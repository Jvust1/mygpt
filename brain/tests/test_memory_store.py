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
