"""Bounded character TF-IDF ranking ported from scikit-learn.

Sources at bbf8863a869f118a1a42422d8cc67ec6c07f2fe0:
feature_extraction/text.py: _preprocess, _char_wb_ngrams, TfidfTransformer.fit/transform;
metrics/pairwise.py: cosine_similarity.
Copyright (c) 2007-2026 The scikit-learn developers. BSD-3-Clause.
See third_party/scikit-learn/LICENSE and NOTICE.md.

This deliberately implements only char_wb (2,3), smoothed IDF, sublinear TF
and L2/cosine scoring. Standard-library sparse dictionaries replace SciPy/NumPy;
no fitted model, persisted index, runtime ML dependency or network is needed.
"""
from __future__ import annotations

from collections import Counter
import math
import re

MAX_QUERY_CHARS = 4000
MAX_DOCUMENT_CHARS = 4096
MAX_CANDIDATES = 64
_WORDS = re.compile(r"[^\W_]+", re.UNICODE)
_WHITE_SPACES = re.compile(r"\s\s+")


def lowercase_lexical_text(text: str) -> str:
    """sklearn _preprocess(lower=True), shared by SQL candidates and scoring.

    SQLite's built-in lower() only handles ASCII. Keep the same Unicode
    lowercase behavior at both retrieval stages; this is not accent stripping
    or the stronger Unicode casefold operation.
    """
    if not isinstance(text, str):
        raise ValueError("lexical text must be a string")
    return text.lower()


def normalize_memory_text(text: str) -> str:
    """Keep lexical evidence; punctuation alone must not recall private memory."""
    return " ".join(_WORDS.findall(lowercase_lexical_text(text)))


def char_wb_ngrams(text_document: str) -> list[str]:
    """Direct bounded-range port of CountVectorizer._char_wb_ngrams."""
    text_document = _WHITE_SPACES.sub(" ", text_document)
    ngrams: list[str] = []
    append = ngrams.append
    for word in text_document.split():
        word = " " + word + " "
        word_len = len(word)
        for n in range(2, 4):
            offset = 0
            append(word[offset:offset + n])
            while offset + n < word_len:
                offset += 1
                append(word[offset:offset + n])
            if offset == 0:
                break
    return ngrams


def tfidf_memory_scores(query: str, documents: list[str] | tuple[str, ...]) -> list[float]:
    """Fit candidate-local IDF and return cosine relevance for the full query.

    Query features outside the candidate vocabulary are ignored, as in the
    upstream fitted vectorizer. Empty/no-overlap inputs produce zero scores.
    """
    if not isinstance(query, str) or len(query) > MAX_QUERY_CHARS:
        raise ValueError("invalid lexical query size")
    if not isinstance(documents, (list, tuple)) or len(documents) > MAX_CANDIDATES:
        raise ValueError("invalid lexical candidate count")
    if any(not isinstance(text, str) or len(text) > MAX_DOCUMENT_CHARS for text in documents):
        raise ValueError("invalid lexical document size")
    counts = [Counter(char_wb_ngrams(normalize_memory_text(text))) for text in documents]
    df = Counter(term for document in counts for term in document)
    if not df:
        return [0.0] * len(documents)
    # TfidfTransformer: df += smooth_idf; n += smooth_idf; log(n / df) + 1.
    n_samples = len(documents) + 1
    idf = {term: math.log(n_samples / (frequency + 1)) + 1.0 for term, frequency in df.items()}

    def normalized_vector(counter: Counter[str]) -> dict[str, float]:
        # TfidfTransformer sublinear_tf, then feature-wise IDF multiplication.
        weighted = {term: (1.0 + math.log(count)) * idf[term] for term, count in counter.items() if term in idf}
        norm = math.sqrt(sum(value * value for value in weighted.values()))
        return {term: value / norm for term, value in weighted.items()} if norm else {}

    query_vector = normalized_vector(Counter(char_wb_ngrams(normalize_memory_text(query))))
    result = []
    for document in counts:
        vector = normalized_vector(document)
        # cosine_similarity is the dot product of the L2-normalized vectors.
        score = sum(query_vector.get(term, 0.0) * value for term, value in vector.items())
        result.append(min(1.0, max(0.0, score)))
    return result
