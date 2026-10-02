# Idempotent memory results match persisted state

Base: [PR #52](https://github.com/Jvust1/mygpt/pull/52),
`72c6017a704e78db9a640e59895c86565b10401f`.

An unchanged `MemoryStore.put(..., allow_update=True)` intentionally writes
neither data nor audit. It previously returned the caller's draft anyway,
including a newer `updated_at`. The same path is used by `update()`. The returned
record disagreed with `get()` and SQLite reopen, despite reporting success.

The no-op branch now returns the existing row through the existing validated
row decoder. It still makes no write, creates no audit event and does not advance
retrieval recency. Validation, explicit update permission, immutable identity
fields and backward-time rejection still occur before the no-op check.

Existing normalization semantics are preserved: duplicate tags are removed in
their original order and timestamps normalize to UTC. Text whitespace is not
silently stripped; changed whitespace is a real edit. Untrimmed tags and blank
text still reject, while tag removal/reordering remains a real change.

Evidence covers both `put` and `update`: repeated no-ops, explicit times/timezone
normalization, backward/naive-time errors, tag normalization, genuine changes,
unchanged SQL total-change counts, audit behavior and cold reopen. An actual
companion prompt still recalls the newer note first, with namespace isolation
and the persisted timestamps. Five cases fail against the old implementation;
all sixteen new cases pass with the one-line return correction.

This is hardening of the existing Mem0-derived persistence surface, not a new
upstream adoption. The pin `94c3fe9f238f3dbf29c9ce98643bd71eb13077cd`, exact
Apache-2.0 license, other upstream identities and dependency lock are unchanged.
The current per-instance ownership scope remains; no cross-process serialization,
schema migration, implicit memory capture or deletion-policy change is introduced.

The existing aggregate workflow also runs source recovery and Java gates at the
exact published head. Local/hosted counts are recorded in the PR evidence.
These tests do not establish live-model, Android/device or audible acceptance.
