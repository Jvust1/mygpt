# Per-instance memory update ownership

Base: [PR #50](https://github.com/Jvust1/mygpt/pull/50),
`c778aa54f08fbe331b267be8a3134ec53ff32614`.

## Reproduced data and recall gap

`MemoryStore.update()` previously released its lock between reading the record
and writing its replacement. A text-only update could retain an old tag list
while a second writer explicitly replaced those tags, then write the old tags
back. A production-store/companion repro recalled `m1` for `quantum` immediately
after the explicit tag edit, but the overlapping text-only update silently
replaced that tag and the actual companion prompt recalled nothing.

The same stale-snapshot window allowed a concurrent delete to complete before
`put(allow_update=True)` reinserted the removed record. The operation's existing
"atomic" description did not hold across its whole read/modify/write lifecycle.

## Bounded fix

Keep the existing per-instance `threading.RLock` around the complete update:
read, missing-record check, replacement construction/time validation and `put`.
The lock is deliberately reentrant because `get` and `put` already use it.
`put` still revalidates the Pydantic record, owns the SQLite transaction and
records the audit event. Its exception/rollback behavior is not replaced.

An omitted `tags` value now preserves the record observed within that serialized
operation. Explicit values still replace their fields; this is not a general
field-merge system. Delete runs either before update (which then rejects a
missing record) or after its completed write, without stale resurrection.
Delete now samples its default timestamp after acquiring that ownership too;
otherwise waiting behind an update could leave it with an earlier default time
and incorrectly trigger the backwards-time guard. Explicit earlier timestamps
still fail that guard without changing the record or audit.
No schema, external API, dependency, automatic memory capture or new lock is added.

## Evidence

- Deterministic two-thread tests pause after the first read and observe the
  second writer's attempt against a real RLock, without scheduling sleeps
- Both text/tag operation orders preserve explicit tags and ordered audit
  events; a competing delete leaves the record deleted across SQLite reopen
- Missing/deleted records are not implicitly added by update
- Injected audit `RuntimeError` and `KeyboardInterrupt` roll back the complete
  database change; another thread can successfully retry afterward
- Invalid blank/oversized text and malformed tags still fail validation before
  any durable update; a later valid edit succeeds
- Reopened namespace-scoped lexical recall and the actual companion prompt use
  the retained tag, without leaking the sibling namespace or creating new memory
- Overlap regressions fail against the old implementation; default queued
  delete also catches the intermediate timestamp bug. All twelve new cases
  pass after the final lock/time scope changes

The aggregate workflow includes this branch and exact-head recovery/Java gates.
Final local/hosted counts are recorded in PR evidence. No device/model-quality
or physical voice acceptance is implied.

## Source and limits

This is local hardening of the existing Mem0-derived explicit-memory lifecycle,
not a new upstream adoption. Mem0 remains pinned at
`94c3fe9f238f3dbf29c9ce98643bd71eb13077cd`; the complete Apache-2.0 license matches
the pinned upstream bytes (Git blob `d20d5102c3cf97ecbee54afd65893de4a11d26fe`).
Current eligibility recheck on 2026-10-01: 66,391 GitHub stars. Existing sklearn
retrieval source pins/notices and the production dependency lock are unchanged.

Serialization is within one `MemoryStore` instance. Independent connections or
processes do not share this Python lock; cross-process compare-and-swap/conflict
resolution is not introduced or claimed. Existing explicit delete preserves
its audit history, as before; no private user data is changed by these tests.
