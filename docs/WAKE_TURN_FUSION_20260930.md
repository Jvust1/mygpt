# Pipecat task ownership fused into the wake/ASR entry path

Base: Ollama async PR #33, `12ca7c87c5c76cc4c6ac1652d70072ffefee159d`.

## Reproduced gap

The existing wake-word → ASR → companion path created a generation lease, but
ignored a stale lease after slow ASR and failed to release active state on model
errors. An older transcription could finish after a newer reply and still be
returned/persisted as the latest conversation.

## Direct upstream reuse

`TaskManager.cancel_task` from Pipecat source revision
`49dea682fb84bfc515d881d00dfeaaa9e9f1075f` is adapted into the existing
`VoiceActivationRuntime`. It keeps the self-await guard and cancelled-child vs
newly-cancelled-caller distinction. The original BSD-2-Clause license/copyright
and exact source blob are retained in `third_party/pipecat/`. Pipecat's live
16,090-star eligibility check is recorded there.

## Runtime behavior

- Turn ownership is always present; callers may still share an explicit existing
  `VoiceTurnController`
- A new wake-qualified, speech-qualified utterance invalidates and cancels the
  previous owned ASR/model task before starting the new task
- Non-triggering/no-speech input does not interrupt an active conversation
- Generation checks run after ASR, before chat commit and before caller delivery
- Obsolete results return `VoiceActivationResult(superseded=True, chat=None)`;
  stale transcript text is not returned for speaking
- `interrupt()` cancels current/retiring owned work while allowing a future turn
- External `close()` joins owned work and prevents later input from restarting
  the session. Reentrant closes from ASR/model work (including helper tasks)
  signal peers without joining them, avoiding cancellation/await cycles
- External caller cancellation propagates rather than being swallowed, even
  when the ASR clears its own cancellation count
- Failures clear assistant-active state; a later valid utterance can recover
- A reply completed before interruption can remain in history, but is not
  delivered afterward if its generation is no longer current; no retrospective
  history rewrite is attempted

This uses the existing wake gate, injected transcriber, companion runtime,
Ollama provider and AIRI emotion parsing. It introduces no microphone ownership,
model download, remote provider or additional framework dependency.

## Validation

- Full strict Brain suite: **612 passed, 0 failed, 0 skipped** on local Python
  3.12.14 and hash-installed Python 3.13.5
- Focused wake path + real Pipecat integration: **27 passed**
- Cases include slow old ASR, cancellation-swallowing return/error, model failure,
  external cancellation during cleanup/ASR uncancel, closing a retiring ASR task,
  multi-task and helper-task reentrant close, late delivery and non-triggering noise
- Actual Ollama adapter stream is closed by a newer wake turn; only the fresh
  reply and its emotion reach the result/history

Local ASR implementations must cooperate with asyncio cancellation. This does
not claim to forcibly terminate native inference running in another thread or
process. Real wake-word accuracy, ASR/model compute cancellation, phone/tablet
behavior, microphone and audio remain device acceptance gates.

Reproduce from `brain/`:

```sh
python scripts/verify_integrations.py --output /tmp/mygpt-wake-acceptance
python -m pytest -q tests/test_voice_activation.py realtime_tests
```

Hosted exact-head Brain/Pipecat gates must be verified after publication. No
main update, merge or deployment is part of this candidate.
