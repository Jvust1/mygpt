# Voice restart and explicit receipt recovery

Base: Book output-integrity PR #45,
`e62ad5edaa5b88b1312900826cc18f7763edb0d9`.
This repairs the existing Pipecat/SQLite integration, without a new dependency.

## Reproduced default-path failure

Automatic voice request IDs previously hashed session ID, an in-memory turn
counter and text. Recreating the bridge reset the counter. The same first
utterance after restart therefore hit an old SQLite receipt: it returned the
old answer, made no new model call and stored no new exchange.

Each bridge now has one ephemeral UUID incarnation in automatic ID derivation.
It is local correlation randomness, not an account/device identity, credential,
permission or separately persisted secret. Existing stored request IDs and
receipts remain readable. A newly spoken event is new even when its words and
counter position repeat after restart.

## Explicit retries are different from new speech

The existing bridge `respond(..., request_id=...)` path remains idempotent.
The frame processor now also accepts an optional retry ID in the existing
metadata namespace:

```json
{"mygpt":{"request_id":"client-turn-123"}}
```

- Absent ID means a fresh automatic voice event
- A supplied ID is validated by the existing request contract; empty/malformed
  IDs fail closed instead of falling back to a new event
- Session/persona are fixed by the bridge, never overridden by metadata
- Reusing an ID with different text/session/persona produces the existing conflict
- A completed receipt returns its stored text and `replayed=true` through the bridge
- The Pipecat processor emits no new LLM text, formatting or TTS synthesis for a replay
- Its response-end metadata carries the request ID and replay flag; fresh replies
  carry `replayed=false` in text/end metadata

Start/end lifecycle framing remains valid for the actual TTS machinery. The
receipt lookup is data recovery, not an automatic request to speak again.
A genuine new spoken request receives a new ID and normal inference/output.

## Delivery limit

A completed SQLite receipt is **not** proof that audio was heard. If the process
dies after committing a reply but before audible delivery, explicit receipt
recovery remains silent and exposes the stored text. This change does not add
an audio acknowledgment, exactly-once physical playback or hard model-compute
cancellation. A caller may display the retrieved data or initiate a genuinely
new turn; it must not mistake a receipt for a device-delivery guarantee.

## Verification

- Default same-text event across SQLite close/reopen now generates a fresh answer,
  retaining the earlier conversation as context
- Explicit cold receipt retrieval produces no duplicate model call, SQLite commit,
  formatter invocation or TTS text/synthesis; later fresh continuation works normally
- Real queued interruption before commit leaves no history/receipt; restart with
  that explicit ID succeeds once, and a further retry stays silent
- Session/persona/text conflicts, malformed metadata and explicit IDs fail closed
- 5000 automatic IDs and counters crossing the signed-64-bit boundary remain distinct
- The actual installed Pipecat queues and final TTS synthesis handoff are used;
  only model replies/audio generation are synthetic, with no device/network calls
- Strict Python 3.13: **724 passed**, zero failures/skips
- Combined actual upstream/story gate: **48 passed**, zero failures/skips
- All three restart/retry scenarios are named requirements of the fail-closed gate

No schema/production-lock change, persistent identity/credential creation, model
selection, app permission or external service is introduced. The existing
aggregate hosted workflow verifies the exact candidate together with Java 8/17.
