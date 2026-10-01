# scikit-learn lexical memory source attribution

Upstream: https://github.com/scikit-learn/scikit-learn

- Eligibility checked 2026-09-30 UTC: **67,434 GitHub stars**, not archived
- License: **BSD-3-Clause**, complete upstream `COPYING` retained as `LICENSE`
- Copyright (c) 2007-2026 The scikit-learn developers.
- Immutable source commit: `bbf8863a869f118a1a42422d8cc67ec6c07f2fe0`
- `sklearn/feature_extraction/text.py`: Git blob `0c1d18b83dddd3a09869dc6b0004a60fc93dd20f`
- `sklearn/metrics/pairwise.py`: Git blob `73482e85642e8a51db04215a3bedaf784d5d25df`
- `COPYING`: Git blob `3d7ee432c15b685eaa654b6abe8f8e3ea8126a8d`

## Adapted source and live use

`brain/mygpt_brain/lexical_memory.py` directly ports
`CountVectorizer._char_wb_ngrams`, `TfidfTransformer.fit/transform`'s smoothed IDF
and sublinear term frequency, L2 normalization, and `cosine_similarity`'s
normalized dot-product computation. The existing `MemoryStore.search` invokes
this code on every lexical recall through `CompanionChatRuntime.send`, including
the existing native HTTP and voice paths. This is not an unused optional adapter.

MyGPT fixes the configuration to character word-boundary n-grams of length 2–3,
smoothed IDF, sublinear TF and L2 normalization. Python sparse dictionaries replace
NumPy/SciPy arrays. A MyGPT lexical preprocessor removes punctuation-only evidence;
zero-vocabulary candidates return zeros instead of sklearn's empty-vocabulary
exception. Candidate documents fit the vocabulary/IDF; full user queries are
transformed without refitting, matching the upstream contract. No persistent
index or new model dependency is introduced into the phone-oriented runtime.

The existing SQL keyword selector supplies at most 64 namespace-scoped records
across at most eight 500-character windows. Scoring accepts the full 4000-character
chat input and does not truncate the provider prompt. Recency and memory ID break
score ties. Memory edit/delete audit behavior and lower-authority prompt placement
are unchanged. This is bounded lexical reranking, not semantic search or exhaustive
corpus retrieval; a relevant record outside the candidate budget can be missed.

`scikit-learn==1.9.1` is a **test-only** optional dependency, used as a real SDK
oracle against fixed and deterministic randomized corpora. It is not imported
by the runtime and does not change the hash-locked production/Brain dependencies.

Source links:
- https://github.com/scikit-learn/scikit-learn/blob/bbf8863a869f118a1a42422d8cc67ec6c07f2fe0/sklearn/feature_extraction/text.py
- https://github.com/scikit-learn/scikit-learn/blob/bbf8863a869f118a1a42422d8cc67ec6c07f2fe0/sklearn/metrics/pairwise.py
- https://github.com/scikit-learn/scikit-learn/blob/bbf8863a869f118a1a42422d8cc67ec6c07f2fe0/COPYING

## Android companion integration (2026-09-30)

`android_spike/src/main/java/dev/mygpt/spike/LexicalMemoryScorer.java` ports the
same pinned algorithms into Java 8 sparse maps. The production
`LocalCompanionMemoryStore.search` in Companion V2 now invokes it on the complete
query. The existing namespace-scoped recent-100 candidate SQL and explicit-only
memory lifecycle remain unchanged; positive cosine scores rank candidates and
existing updated-time/ID ordering breaks ties. No implicit write or model is added.

Android-specific limits preserve its existing contracts: 4000 UTF-16 query units,
1000 UTF-16 units per memory and 100 candidates. Token ngrams use Unicode code
points, not split surrogate pairs. Lexical category/case handling follows the
host Java/Android Unicode version; common CJK/Latin/Greek/numeric and supplementary
characters are covered by the actual sklearn fixtures, not every Unicode release.

The 109 deterministic fixture cases are generated and independently rechecked
with actual `scikit-learn==1.9.1`; Java 8/17 consume those fixtures through the
shared boundary runner. No Python, sklearn, Gson reflection or new dependency
is introduced into Android scoring. Full license and short notice assets are
provided to all four modules that compile the shared source (three direct asset
sets, with Companion V2 inheriting the Android spike assets).

## Unicode SQL candidate preprocessing (2026-09-30)

The existing Python `MemoryStore` registers the private, deterministic SQLite
function `mygpt_lexical_lower` on each connection. It calls the same source-derived
`lowercase_lexical_text` as final lexical preprocessing, matching pinned sklearn
`_preprocess(lower=True)` (`doc.lower()`, without an accent function). SQLite's
built-in ASCII-only `lower` is not overridden. This fixes non-ASCII uppercase
text/tag candidates being excluded before the scorer can examine them.

There is no schema migration, persistent normalized copy/index, dependency or
raw-text rewrite. This is Unicode lowercasing, not casefold, NFC/NFKC conversion
or accent removal. Existing punctuation/word rules, parameterized SQL, namespace
scope, query windows and candidate limits remain unchanged. Actual sklearn
preprocessing parity and SQLite reopen/update/runtime-prompt tests cover the path.
