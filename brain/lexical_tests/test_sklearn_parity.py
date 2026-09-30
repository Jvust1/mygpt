"""Actual upstream SDK oracle, never a stub or a production dependency."""
import importlib.metadata
import random

import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from mygpt_brain.lexical_memory import char_wb_ngrams, normalize_memory_text, tfidf_memory_scores


def vectorizer():
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3),
                           sublinear_tf=True, smooth_idf=True, norm="l2", lowercase=False)


def test_oracle_is_exact_pinned_upstream_release():
    assert importlib.metadata.version("scikit-learn") == "1.9.1"


@pytest.mark.parametrize("query,documents", [
    ("数学 拓扑", ["数学 拓扑", "数学 代数 几何", "语音 设置"]),
    ("topology study", ["topology study", "study exam review", "voice local"]),
    ("a a a b", ["a b", "a a a a b", "b b b", "c"]),
    ("Mixed! 中文_123", ["MIXED 中文", "123 456", "other"]),
    ("unknown", ["数学", "语音"]),
    ("???", ["数学", ""]),
    ("长" * 3996 + "拓扑学习", ["拓扑学习", "数学"]),
])
def test_sparse_port_matches_actual_sklearn_cosine(query, documents):
    oracle = vectorizer()
    fitted = oracle.fit_transform([normalize_memory_text(d) for d in documents])
    transformed = oracle.transform([normalize_memory_text(query)])
    expected = cosine_similarity(transformed, fitted)[0].tolist()
    assert tfidf_memory_scores(query, documents) == pytest.approx(expected, abs=1e-12)


def test_tokenizer_and_scores_match_deterministic_randomized_corpus():
    rng = random.Random(20260930)
    vocabulary = ["数学", "拓扑", "代数", "a", "longword", "学习", "voice", "42"]
    oracle = vectorizer()
    for _ in range(25):
        documents = [" ".join(rng.choices(vocabulary, k=rng.randint(1, 20))) for _ in range(8)]
        query = " ".join(rng.choices(vocabulary, k=10))
        for doc in documents:
            assert char_wb_ngrams(doc) == oracle.build_analyzer()(doc)
        fitted = oracle.fit_transform(documents)
        expected = cosine_similarity(oracle.transform([query]), fitted)[0].tolist()
        assert tfidf_memory_scores(query, documents) == pytest.approx(expected, abs=1e-12)
