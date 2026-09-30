from datetime import datetime, timezone

from mygpt_brain.mem0_bridge import Mem0MemoryBridge
from mygpt_brain.memory_store import MemoryRecord


class FakeMem0:
    def __init__(self):
        self.added = []

    def add(self, messages, **kwargs):
        self.added.append((messages, kwargs))

    def search(self, **kwargs):
        return {
            "results": [
                {
                    "id": "remote-1",
                    "memory": "用户更喜欢先看预习再做题。",
                    "score": 0.91,
                    "metadata": {
                        "mygpt_memory_id": "m1",
                        "namespace": "study",
                    },
                }
            ]
        }


def record():
    now = datetime(2026, 9, 30, 16, 0, tzinfo=timezone.utc)
    return MemoryRecord(
        memory_id="m1",
        namespace="study",
        kind="study_pattern",
        text="用户更喜欢先看预习再做题。",
        tags=["book"],
        source="user_explicit",
        created_at=now,
        updated_at=now,
    )


def test_mem0_bridge_mirrors_reviewed_record_without_inference():
    client = FakeMem0()
    bridge = Mem0MemoryBridge(client, user_id="user-1")
    bridge.mirror(record())
    messages, kwargs = client.added[0]
    assert messages[0]["content"] == record().text
    assert kwargs["user_id"] == "user-1"
    assert kwargs["infer"] is False
    assert kwargs["metadata"]["mygpt_memory_id"] == "m1"


def test_mem0_bridge_search_restores_local_memory_identity():
    bridge = Mem0MemoryBridge(FakeMem0(), user_id="user-1")
    hits = bridge.search("学习习惯", limit=3)
    assert hits[0].memory_id == "m1"
    assert hits[0].score == 0.91
    assert hits[0].metadata["namespace"] == "study"
