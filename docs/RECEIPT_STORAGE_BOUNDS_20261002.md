# Lossless receipt storage and durable-runtime cache bounds

## Status

This independent draft follows [PR #58](https://github.com/Jvust1/mygpt/pull/58)
at `a5862faf8e976ca310bb4d743fea78c5c8211d01`. It addresses the quadratic **new
receipt storage** and retained-runtime-cache portions of MYGPT-002. The full
retention finding remains open: no automatic history deletion, TTL, purge or
data-upload policy is introduced. Main and existing review branches are unchanged.

The input baseline's [exact-head aggregate](https://github.com/Jvust1/mygpt/actions/runs/36964436329)
passed all seven jobs, including real isolated Android APK compilation and both
required-job gates. That is baseline evidence, not this draft's final acceptance.
APK redistribution remains unapproved; only metadata was published.

## Implementation

- Durable `CompanionChatRuntime` retains zero cross-request session/result cache
  entries. It reads a SQLite snapshot containing at most the configured number
  of conversational message bodies, all required authority rows, and the earlier
  message IDs needed by the existing public response contract.
- New receipts encode `compacted_message_ids` only when the list is exactly the
  conversation's ordered non-system ordinal prefix. A separate nullable column
  stores a version, cutoff ordinal, count and SHA-256. The receipt's existing
  result schema is unchanged when read through the API.
- Reads reconstruct and verify the original ordered list. Corrupt references
  fail closed. Non-prefix, reordered, duplicate or unknown-ID lists retain their
  literal representation rather than silently changing meaning.
- History and receipt insert share one transaction. Duplicate requests retain
  fingerprint, session, persona and canonical-JSON result conflict checks.
- Snapshot revisions reject replies whose session changed while the responder
  was running. A single global successful-deletion epoch additionally protects
  an initially absent session from create/delete ABA. No deleted session IDs or
  per-session tombstones are retained.
- Full history remains available through the explicit history API, filtered by
  persona. No conversation becomes explicit long-term memory automatically.

This extends the existing SQLite/AIRI-derived persistence path. It adds no SDK,
model, network destination or competing persistence framework.

## Upgrade contract

**Stop every old MyGPT process using the database before starting the upgraded
runtime. Keep a private local backup before testing the upgrade on valued data.**
Do not upload chat databases or backups to GitHub.

Opening a v1 chat store migrates its schema to v2 in one `BEGIN IMMEDIATE`
transaction. Existing message/receipt rows, including old receipt JSON bytes,
are preserved. Added metadata consists of a session revision column, a nullable
receipt-reference column and one non-identifying deletion counter. Injected DDL,
initialization and keyboard-interrupt failures roll back the entire migration.

An older binary opened afterward rejects schema v2. Already-running v1 binaries
do not recheck the version and must not be used concurrently. Mixed-version use
and in-place downgrade are unsupported. To return to the prior runtime, retain
and use the pre-upgrade backup; do not manually lower the version marker.

No real user database was migrated or deleted by this development/test work.

## Concurrency and deletion boundaries

- A successful deletion prevents a stale in-flight completion from recreating
  the deleted session, including initially-absent create/delete ABA.
- Successful deletion of an unrelated session conservatively invalidates an
  initially absent first turn too; its caller may retry. Existing sessions use
  their own revisions and are not invalidated by that unrelated deletion.
- `delete_session` on a nonexistent session still returns false; it is not a
  provider-cancellation API. Cancel the turn separately when cancellation is desired.
- Deletion and epoch update are atomic. Injecting epoch-update failure restores
  messages and receipts rather than leaving a partly deleted session.
- Cross-process exactly-once provider execution is not promised. This change
  protects durable completion/replay integrity, not external side-effect delivery.

## Local evidence on the final implementation

Linux Python 3.13.15, SQLite 3.53.1, synthetic responder only. Core dependency
installation used the existing hash lock; optional upstream integration extras
retain their existing pinning limits.

- 35 new storage/migration/concurrency tests; full strict Brain **862 passed**,
  zero failed/skipped
- Actual pinned upstream/component gate **49 passed**; root Python **85 passed**; JavaScript **70 passed**
- Independent review compared full-history vs bounded-tail compaction across
  7,161 user/assistant/budget cases with interleaved authority, then checked
  malformed references, literal fallback, mutable caller results, v1 migration,
  transaction rollback and both existing-session and absent-session deletion races
- Two root tests also verify the mandatory fixed 1k/10k workflow wiring and execute the growth CLI at small synthetic scale
- Two runtime files were hashed before and after long-run execution; they did
  not change during the measurements

| Synthetic workload | 1,000 turns | 10,000 turns |
| --- | ---: | ---: |
| Single-session SQLite bytes, after WAL close | 1,679,360 | 17,952,768 |
| Single-session receipt payload bytes | 890,686 | 8,937,668 |
| Many single-turn sessions: SQLite bytes | 1,884,160 | 18,452,480 |
| Retained runtime session/result cache entries | 0 | 0 |
| Maximum single-session provider message rows | 20 | 20 |

At 10,000 turns, all 20,001 single-session messages and 10,000 receipts remain.
First/middle/last warm and cold replays pass without another responder call;
same-ID altered input is rejected. Explicit-memory rows remain zero. All
temporary synthetic databases are cleaned up by the test.

The original 400-turn diagnostic, run unchanged on this candidate, uses 630,784
SQLite bytes instead of the baseline's 5,259,264 bytes, about 88.0% less for that
same workload. This is a measured synthetic comparison, not a device benchmark.

## Important remaining limits

- The API still returns the complete compacted-ID list. A request's transient
  ID memory and work grow with history; cumulative CPU remains near-quadratic.
  The single-session local run took 1.730 seconds at 1k vs 152.055 seconds at 10k.
  Do not describe this as globally constant-memory or linear-time execution.
- Authority rows retain their prior semantics and are not newly capped.
- Without a durable session store, the original in-memory history/replay
  behavior remains; that mode is not advertised as bounded retention.
- Old v1 receipt payloads are preserved, not retroactively compacted. Arbitrary
  non-prefix store callers retain literal receipts. The size result applies to
  new normal runtime receipts under the tested workload.
- Durable history still grows linearly without a hard total lifetime cap. A
  retention/export/deletion product policy remains a separate task and decision.
- No real model, private data, Book signing, microphone, audible TTS or physical
  device test is implied by these synthetic checks.

## Reproduce

From the repository's documented Linux Python 3.13 environment:

```sh
cd brain
python scripts/verify_integrations.py --output ../test-output/receipt-strict-new
python scripts/verify_fusion_upstreams.py --output ../test-output/receipt-upstream-new
python scripts/verify_receipt_growth.py --rounds 1000 10000 --output /tmp/receipt-growth-new.json
```

The output path must not already exist. CI fixes the 1k/10k workload, publishes
only synthetic metrics plus exact checked-out commit identity, and requires the
step in the existing production/aggregate gate. The PR records this candidate's
final exact head, hosted run and downloaded artifact verification after execution.
