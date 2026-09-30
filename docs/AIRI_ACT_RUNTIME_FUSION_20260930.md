# AIRI ACT → MyGPT speech/emotion runtime fusion

## Why this change exists

Base: PR #15 branch `feat/airi-chat-memory-brain-20260929`, commit
`1f1e1e1db4c053a3a2abdaea1a93aec9aa3ce16d`.

The Android companion already understood AIRI emotion markers. The Python
Ollama path returned plain strings and therefore persisted/spoke the raw marker
while reporting `neutral`. This change closes that existing path rather than
adding another optional provider or vendoring a second AIRI tree.

## Direct upstream code and license

- Project: https://github.com/moeru-ai/airi
- Live eligibility check: 2026-09-30 18:11 UTC, GitHub API reported **49,887 stars**
- License: MIT, copyright (c) 2024-PRESENT Neko Ayaka
- Pin: `b40e3e87b149ea5fb75d4944440493829e601411`
- Ported code: `parseActEmotion`, `normalizeEmotionName`, `normalizeIntensity`
  in [queues.ts](https://github.com/moeru-ai/airi/blob/b40e3e87b149ea5fb75d4944440493829e601411/packages/stage-ui/src/composables/queues.ts)
- Vocabulary: [emotions.ts](https://github.com/moeru-ai/airi/blob/b40e3e87b149ea5fb75d4944440493829e601411/packages/stage-ui/src/constants/emotions.ts)
- Retained license and exact source blob identities: `third_party/airi/`

`brain/mygpt_brain/airi_act.py` is a direct Python port with bounded parsing and
invalid-marker handling. It is called by `CompanionChatRuntime.send()` on every
new provider reply, before message creation, SQLite commit, HTTP output or voice
bridge output. It is not an unused reference file.

## Working path

1. Existing `serve_companion_ollama.py` builds the usual approved persona/runtime
2. Existing `OllamaResponder` requests the narrow AIRI presentation format using
   a fixed application instruction; Book and memory remain lower-authority data
3. Reply text such as `继续学这节。<|ACT:{"emotion":"happy"}|>` is parsed
4. Native `/api/v1/chat` returns visible text `继续学这节。` and
   `presentation_emotion: happy`
5. Only cleaned assistant text is stored, and restart/idempotent replay retains
   the separate emotion
6. Existing `PipecatCompanionBridge` receives cleaned speech plus emotion; its
   text processor no longer sends ACT syntax downstream to TTS

Plain replies remain unchanged. Explicit structured-responder emotions take
precedence over embedded markers. Last valid ACT emotion wins; malformed,
unknown, overlong and truncated ACT envelopes are removed. A marker-only reply
fails without committing an exchange. Only the nine existing emotion names are
interpreted. Normalized intensity is not added to the existing v1 API.

Review hardening also covers delimiters inside escaped JSON strings and every
partial opener from `<|` onward. A pre-existing first-reply-failure bug exposed
by marker-only rejection is fixed: the initial persona is staged with the
successful exchange, so failure → retry → restart cannot lose system authority.

No action/tool/delay execution, new SDK dependency, screen capture, microphone,
cloud inference, Dot API, LAN listener or skin asset is introduced. Historical
receipts are not rewritten or migrated; this normalization applies to new model
replies.

## Validation

Executed locally on Linux / CPython 3.12.14 with the repository's exact top-level
test/integration dependency pins:

- Strict Brain SDK acceptance: **563 passed, 0 failed, 0 skipped**
- Root Python unit tests: **44 passed**
- JavaScript unit tests: **66 passed**
- `compileall`, `pip check`, `git diff --check`: pass

Reproduce the strict gate from `brain/`:

```sh
python scripts/verify_integrations.py --output /tmp/mygpt-act-acceptance
```

The HTTP regression uses the actual local authenticated service and actual
Ollama adapter, with a synthetic response at the model I/O boundary. Pipecat
tests inject frame classes. These prove runtime wiring, authority preservation,
clean speech and durable replay, not real model quality or audible TTS. No model
weights or real user text were used. The initial dependency-incomplete run was
not accepted; strict acceptance above followed installation of the pinned SDKs.

Remote CI must be checked on the published head. Windows/Xiaomi 14, real Book
APK signing/transport, phone-hosted Qwen, physical character rendering and live
audio remain separate acceptance gates. No main update, merge or deployment is
part of this candidate.
