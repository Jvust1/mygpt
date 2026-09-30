# scikit-learn lexical memory in the Android companion

Base: source-recovered candidate PR #41,
`639d8291f090b52ba99266e4f630453b2a6b49b0`.

## Actual missing path

The Python companion already used the pinned scikit-learn-derived scorer, but
Android `LocalCompanionMemoryStore.search` still counted substrings from only
the first 16 query tokens. A useful term later in a full 4000-character question
could never contribute. The real `CompanionV2Activity.sendText` invokes this
search on its existing IO dispatcher before constructing the user-turn prompt.

That search now invokes `LexicalMemoryScorer.score` directly. This is a Java-8
port of the same actual upstream char-word-boundary n-grams, smoothed IDF,
sublinear TF, L2 normalization and cosine dot product. It is neither an optional
adapter nor a new model/ML dependency.

Upstream: **scikit-learn/scikit-learn**, **67,434 stars** checked again on
2026-09-30 UTC, **BSD-3-Clause**, immutable commit
`bbf8863a869f118a1a42422d8cc67ec6c07f2fe0`. Exact original source/license blobs and
copyright are recorded in `third_party/scikit-learn/NOTICE.md` and `LICENSE`.
Android source attribution and all four shared-source consumers' direct/inherited
license assets are verified by `verify_lexical_integration.py`.

## Preserved boundaries

- The existing namespace-scoped SQL selects at most 100 recent memories
- Only strictly positive lexical scores survive; recency then memory ID break ties
- The full query contributes to scoring; punctuation-only/no-evidence input yields no result
- Memory text remains explicit-user data; no chat turn is automatically added as memory
- Existing memory CRUD, audit history, erase behavior and SQLite schema are untouched
- Recalled snippets still enter the bounded user-turn data block, not trusted system authority
- No network, fitted model, persistent index, Python runtime or new Android dependency

The existing Android limits remain 4000 UTF-16 units per query, 1000 per memory,
and 100 candidates. N-grams use Unicode code points, so supplementary characters
are not split into surrogate halves. Lowercasing and letter/number classification
follow the Java/Android Unicode version. Common CJK, Latin, Greek, numeric and
supplementary characters are checked against the oracle; universal equivalence
across all Unicode releases is not claimed.

This is bounded lexical retrieval, not semantic understanding or exhaustive
corpus search. An older record beyond the recent-100 window can still be missed.
Cloud JVM timing does not establish phone/tablet performance.

## Verification

- 109 deterministic fixture cases are produced and rechecked using actual
  `scikit-learn==1.9.1`, including terms after the old token cap and at query end
- Actual Java consumes those fixtures and compares normalized text plus every
  cosine score within 1e-12; local maximum score error was 6.0e-15
- Null/over-limit query/documents, 100-candidate ceiling, 4000-character query,
  1000-character documents and punctuation-only non-recall have direct Java tests
- The shared Java runner now executes 19 smoke entrypoints, including the existing
  327 Python/Gson cases and new 109 sklearn cases
- Existing production Python hash lock is unchanged
- Source-wiring checks complement the real Java computation; they are not a
  substitute for compiling/running Android SQLite/Kotlin on a device

The exact-head hosted Java 8/17 matrix and actual sklearn fixture recheck are
separate jobs. APK compilation, Android database instrumentation, physical device,
real model and live Book/microphone acceptance remain separate gates.

## Reproduce

```sh
# Existing test-only sklearn environment; no model download.
python android_spike/tools/lexical_sklearn_oracle.py
python android_spike/tools/verify_lexical_integration.py
GSON_JAR=/path/to/gson-2.14.0.jar bash android_spike/tools/run_boundary_smoke.sh
```

Only `--write` regenerates the synthetic fixture. Normal oracle execution checks
all case identities, inputs, normalized text and scores against the installed
pinned upstream. Source and fixture failures fail the gate rather than silently
falling back to the old substring scorer.
