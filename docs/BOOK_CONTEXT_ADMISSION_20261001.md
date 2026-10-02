# Book context freshness at queued-turn admission

Base: reviewed source checkpoint [PR #48](https://github.com/Jvust1/mygpt/pull/48),
`1e766c00d7ccb857d7d5a858e7af776f66b611df`.

## Reproduced user-facing gap

The companion serializes requests through one runtime lock. It previously read
wall time before waiting for that lock, so a Book context could expire in the
queue yet still reach the Ollama responder and produce a durable answer.
The new real native HTTP/SQLite/Ollama-adapter regression returns 200 with the
old runtime where 409 `book_context_expired` is required. The model endpoint is
synthetic `httpx.MockTransport`; the native HTTP server and SQLite are real.

## Bounded change

The runtime now samples wall time after acquiring its turn lock and checking
the existing current-owner guard. This admission timestamp is used by the
existing Book freshness check and new exchange timestamps. No fallback to the
arrival timestamp, silent retry, clock-error cache or new clock API is added.
The already-supported explicit `now=` override remains deterministic for
callers that deliberately provide it; the production native service does not.

Freshness remains an admission rule: `captured_at <= admission < expires_at`.
It is not continuous revalidation, an output deadline, retrospective deletion
or a guarantee against a faulty wall clock. A Book context accepted before its
expiry may expire while the responder is running. Existing authorization
revocation/completion guards and monotonic responder deadlines are unchanged.

Receipts retain their existing meaning. A previously successful explicit ID
can retrieve its stored result after context expiry without using that source
again, calling the provider or writing another exchange. A changed payload
under the same successful ID remains a conflict. An expired request has no
receipt, so an explicit later retry with fresh context can succeed.

## Evidence

- Deterministic queue tests: fresh/equality/expired/future-capture admission,
  exact admitted timestamp, lower-authority Book projection and no raw Book
  persistence or implicit memory write
- Queued cancellation and owner revocation reject without reading the clock,
  invoking a provider, persisting a receipt or creating history
- Clock-read and timezone-conversion failures propagate once, leave runtime
  caches/SQLite untouched and permit a later explicit retry
- Existing explicit-time behavior and warm/cold-runtime receipt replay remain
- Real native HTTP queue → Ollama adapter → SQLite story rejects expired Book
  input, accepts a fresh explicit retry, then reopens SQLite and replays without
  another provider call after expiry

The aggregate workflow includes this branch and reuses the exact-head source
recovery and Java gates. Final local/hosted counts belong in PR evidence.
No Android/device/live-model or physical audio claim is added.

This is hardening of the existing fused runtime, not another upstream adoption.
AIRI remains pinned at `b40e3e87b149ea5fb75d4944440493829e601411`, MIT, with the
existing exact license and notices. Eligibility was rechecked on 2026-10-01:
49,894 GitHub stars. Ollama/Pipecat/scikit-learn/Gson pins and all dependencies
are unchanged. Book remains the authoritative source; only the existing bounded
ephemeral semantic projection is admitted.
