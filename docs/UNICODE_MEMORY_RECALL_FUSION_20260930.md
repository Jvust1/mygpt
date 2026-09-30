# Unicode candidate retrieval with the existing sklearn preprocessor

Base: Android paired-history PR #43,
`93739b994807daeb491a60684bf4255fe79156d6`.

## Reproduced user-visible gap

An explicit memory `CAFÉ préféré` was not recalled for the query `café`. The
scikit-learn-derived final scorer already handled Unicode lowercasing, but
SQLite's built-in `lower()` is ASCII-only: the candidate never reached scoring.
The same mismatch affected Greek/Cyrillic uppercase text and explicit tags.

The existing `MemoryStore` now registers one private deterministic function,
`mygpt_lexical_lower`, on every SQLite connection. It uses the same shared
`lowercase_lexical_text` as scoring, directly matching `_preprocess(lower=True)`
from the already-pinned scikit-learn source. Text and tag candidate SQL invoke
this function instead of SQLite's ASCII-only builtin. The builtin itself is
not overridden; reopened databases receive the same per-connection callback.

Upstream remains **scikit-learn/scikit-learn**, **BSD-3-Clause**, immutable commit
`bbf8863a869f118a1a42422d8cc67ec6c07f2fe0`. The existing exact `text.py` source blob
`0c1d18b83dddd3a09869dc6b0004a60fc93dd20f` contains `_preprocess`; provenance and
full copyright/license remain in `third_party/scikit-learn`.

## Deliberately narrow semantics

This is `str.lower`, not casefold, accent removal, NFC/NFKC conversion or a new
semantic-retrieval engine. Dotted I retains its combining dot; composed and
decomposed accents remain distinct at this lowercase step. The existing later
word/punctuation preprocessing is unchanged, including its treatment of combining
marks as separators. `Straße` is not silently made equal to `STRASSE`, and Latin
lookalikes do not become Cyrillic text.

- No schema migration, normalized-text rewrite, persistent index or new dependency
- Original stored text/tags, timestamps, audit history and explicit-only writes remain intact
- SQL remains parameterized and namespace-scoped; user `%`/`_` do not become SQL patterns
- Public punctuation remains a lexical separator, not literal search syntax
- Full 4000-character queries, eight 500-character windows and at most 64 scored candidates remain
- Recency/ID tie-breaking and lower-authority user-data prompt placement remain

This fixes candidate preprocessing, not the documented bounded-candidate recall
limit. It does not make every Unicode spelling equivalent or prove phone latency.

## Evidence

- The exact SQLite `CAFÉ`/`café` failure now passes through real candidate SQL
- Tests cover accented Latin, Greek, Cyrillic, tags, dotted I, combining marks,
  false-positive controls, wildcard-shaped input, namespace isolation and budgets
- File-backed close/reopen, update/delete/audit and unchanged schema version pass
- Actual CompanionChatRuntime recall reaches the user-level prompt, preserves the
  original full question in SQLite and creates no implicit memory
- Actual `scikit-learn==1.9.1` `_preprocess` independently matches eight Unicode cases
- Full strict Python 3.13 gate: **705 passed, zero failures/skips**
- Combined actual upstream/story gate: **45 passed, zero failures/skips**

The existing aggregate workflow is enabled for this branch, proving the whole
candidate with the unchanged production lock and reusable Java 8/17 gates.
Synthetic model/audio and physical-device acceptance boundaries remain unchanged.
