# PR #15 companion runtime checkpoint — 2026-09-29

## Objective

Move MyGPT from a skin/demo companion toward the final product: a durable conversational companion beside Book Android, with explicit memory, local model support, voice input foundations, and renderer-neutral character reactions.

## Direct upstream adoption

| Upstream | Pin | License | Adopted scope |
|---|---|---|---|
| moeru-ai/airi | b40e3e87b149ea5fb75d4944440493829e601411 | MIT | chat authority model, merge/dedupe, bounded history, Character Card fields, emotion vocabulary |
| mem0ai/mem0 | 94c3fe9f238f3dbf29c9ce98643bd71eb13077cd | Apache-2.0 | update/delete/history memory lifecycle and audit shape |
| k2-fsa/sherpa-onnx | 040afe360a38e25daaa325ce8889abf93ea02609 | Apache-2.0 | Android 16 kHz mono AudioRecord capture / PCM normalization foundation |

## Current functional chain

`Book semantic context (ephemeral data) -> CompanionChatRuntime -> explicit local memory recall -> injected responder/Ollama interface -> text + presentation_emotion`

The Android side now has:
- a renderer-neutral AIRI-compatible emotion enum;
- conservative 3714430278 animation mapping;
- an explicit microphone PCM capture layer that does not request permission or persist audio.

## Privacy/authority invariants

- imported/context text never gains system authority merely because the app supplied it;
- Book context is transient in this candidate and does not enter durable chat storage;
- long-term memory is explicit and correctable;
- delete preserves audit history but removes active memory;
- external character cards cannot self-approve;
- microphone capture requires pre-granted RECORD_AUDIO permission;
- no raw audio persistence;
- Ollama endpoint remains fixed to loopback for this prototype.

## Validation

- Initial companion Python candidate: 18 passed / 0 failed.
- Exact current Java-8 protocol subset (PCM + emotion + skin mapping): local compile/run PASS.
- GitHub Actions currently cannot allocate runners; representative jobs have runner_id=0 and 0 steps.
- Exact-head full Python, Android build, live Ollama and Xiaomi 14 voice/chat behavior remain pending.

## Next highest-value increments

1. restore/obtain a working CI runner and execute exact-head Python + Android suites;
2. expose CompanionChatRuntime through a bounded transport suitable for the Android host;
3. perform one explicit local Ollama end-to-end chat with the approved 3714430278 character card;
4. benchmark sherpa-onnx vs whisper.cpp behind the shared PCM interface before bundling any ASR engine/model;
5. connect presentation_emotion to the Android chat result path only after the chat transport exists.
