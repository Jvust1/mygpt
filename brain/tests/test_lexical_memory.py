from datetime import datetime, timedelta, timezone

import pytest

from mygpt_brain.lexical_memory import char_wb_ngrams, normalize_memory_text, tfidf_memory_scores
from mygpt_brain.memory_store import MemoryRecord, MemoryStore

NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def record(memory_id, text, *, namespace="p1", seconds=0, tags=None):
    return MemoryRecord(memory_id=memory_id, namespace=namespace, kind="preference",
                        text=text, tags=tags or [], source="user_explicit",
                        created_at=NOW, updated_at=NOW + timedelta(seconds=seconds))


def test_character_boundaries_and_lexical_normalization():
    assert normalize_memory_text("MATH_学习！\n中文") == "math 学习 中文"
    assert char_wb_ngrams("a") == [" a", "a ", " a "]
    assert char_wb_ngrams("ab\t c") == [" a", "ab", "b ", " ab", "ab ", " c", "c ", " c "]


def test_scores_rank_full_match_above_generic_overlap():
    scores = tfidf_memory_scores("数学 拓扑", ["数学 拓扑", "数学 代数 几何", "语音 设置"])
    assert scores[0] == pytest.approx(1)
    assert scores[0] > scores[1] > scores[2] == 0
    assert tfidf_memory_scores("unknown", ["数学"]) == [0]
    assert tfidf_memory_scores("???", ["数学"]) == [0]
    assert tfidf_memory_scores("数学", ["!!!", ""]) == [0, 0]
    assert tfidf_memory_scores("数学", []) == []


@pytest.mark.parametrize("query,documents", [
    ("x" * 4001, []), (None, []), ("q", ["x"] * 65),
    ("q", ["x" * 4097]), ("q", [None]), ("q", iter(["a"])),
])
def test_scorer_rejects_unbounded_or_invalid_inputs(query, documents):
    with pytest.raises(ValueError):
        tfidf_memory_scores(query, documents)


def test_memory_ranking_overrides_recency_and_preserves_namespace():
    with MemoryStore() as store:
        store.put(record("relevant", "数学 拓扑"))
        store.put(record("newer", "数学 代数 几何", seconds=1))
        store.put(record("private", "数学 拓扑", namespace="other", seconds=2))
        result = store.search("数学 拓扑", namespace="p1", limit=1)
        assert [r.memory_id for r in result] == ["relevant"]


def test_equal_scores_use_recency_then_id_and_lifecycle_is_not_stale(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        for memory_id, seconds in [("b", 0), ("a", 0), ("c", 1)]:
            store.put(record(memory_id, "数学 拓扑", seconds=seconds))
        assert [r.memory_id for r in store.search("数学 拓扑", namespace="p1")] == ["c", "a", "b"]
        store.update("c", text="语音 设置", updated_at=NOW + timedelta(seconds=2))
        store.delete("a", deleted_at=NOW + timedelta(seconds=2))
        assert [r.memory_id for r in store.search("数学 拓扑", namespace="p1")] == ["b"]
        assert store.history("a")[0].action == "DELETE"


@pytest.mark.parametrize("query", ["!?!", "🙂", "x", "_", " \t ", "unrelated"])
def test_no_lexical_evidence_does_not_fallback_to_recent_private_memory(query):
    with MemoryStore() as store:
        store.put(record("private", "数学 拓扑"))
        assert store.search(query, namespace="p1") == []


def test_long_query_retrieves_suffix_and_candidate_work_is_bounded(monkeypatch):
    with MemoryStore() as store:
        store.put(record("target", "拓扑学习"))
        query = "z" * 3996 + "拓扑学习"
        calls = []
        original = store._keyword_candidates
        def probe(window, **kwargs):
            calls.append((window, kwargs["limit"]))
            return original(window, **kwargs)
        monkeypatch.setattr(store, "_keyword_candidates", probe)
        result = store.search(query, namespace="p1")
        assert [r.memory_id for r in result] == ["target"]
        assert len(calls) == 8
        assert max(len(window) for window, _ in calls) <= 500
        assert sum(limit for _, limit in calls) == 64
        with pytest.raises(ValueError, match="too long"):
            store.search(query + "!", namespace="p1")


def test_tag_evidence_is_scored_without_modifying_stored_record():
    with MemoryStore() as store:
        original = record("tagged", "先给一个简单例子", tags=["拓扑"])
        store.put(original)
        assert store.search("拓扑", namespace="p1") == [original]
        assert store.get("tagged") == original
        assert len(store.history("tagged")) == 1
