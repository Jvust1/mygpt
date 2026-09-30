# Project AIRI attribution

Upstream: https://github.com/moeru-ai/airi  
Pinned upstream commit: `b40e3e87b149ea5fb75d4944440493829e601411`  
License: MIT (copyright 2024-PRESENT Neko Ayaka)

This MyGPT integration directly adapts selected implementation ideas/code
structures from the following AIRI files:

- `packages/core-agent/src/messages/types.ts`
  - authority-separated system/context conversation model;
- `packages/core-agent/src/session/merge-loaded-session-messages.ts`
  - stable message merge/deduplication semantics;
- `packages/core-agent/src/messages/compaction.ts`
  - bounded recent-turn history compaction;
- `packages/stage-ui/src/database/repos/chat-sessions.repo.ts`
  - local-first durable session/idempotency principles;
- `packages/ccc/src/define/card.ts`
  - character card field organization for persona, scenario, greetings, tags and
    sample conversation behavior;
- `packages/stage-ui-spine/src/constants/emotions.ts`
  - renderer-neutral emotion vocabulary used across character renderers;
- `packages/stage-ui/src/composables/queues.ts`
  - bounded `<|ACT:{...}|>` emotion-control marker parsing/normalization semantics.

Local derived/adapted files:

- `brain/mygpt_brain/conversation.py`
- `brain/mygpt_brain/session_store.py`
- `brain/mygpt_brain/character_card.py`
- `brain/mygpt_brain/airi_act.py`
- `android_spike/src/main/java/dev/mygpt/spike/PresentationEmotion.java`
- `android_spike/src/main/java/dev/mygpt/spike/AiriActEmotionParser.java`

Material changes in MyGPT:

- TypeScript/IndexedDB structures are reimplemented in Python/SQLite/Pydantic.
- MyGPT keeps application context at lower authority than trusted system/developer
  instructions and renders it as data at provider projection.
- Local chat history is bounded; old raw transcript is not silently converted to
  long-term semantic memory.
- Request receipts and message IDs are persisted transactionally for local
  replay/idempotency.
- Provider-specific continuation/media logic is not copied.
- Character-card TypeScript types are reimplemented as a bounded Pydantic
  contract. Imported cards remain descriptive data until a caller explicitly
  approves conversion into trusted persona instructions.
- Memory and Ollama provider modules are original MyGPT integration code built
  around these boundaries, not AIRI source copies.

The upstream MIT license is reproduced in `third_party/airi/LICENSE`.

## 2026-09-30: ACT parser fused into the actual Python reply path

`airi_act.py` directly ports `parseActEmotion`, `normalizeEmotionName`, and
`normalizeIntensity` from the pinned `packages/stage-ui/src/composables/queues.ts`
(Git blob `72e7549144149235ec886f0b7be38dded9d67548`). The vocabulary comes from
`packages/stage-ui/src/constants/emotions.ts` (blob
`b8d5f2edaf5fe589e55142ca649eac8222f3eb23`). Copyright and MIT terms are retained.
The existing LICENSE matches pinned upstream blob
`1bd715572472cd766a5c1444a467f5f011b14aaa`.

Material port changes: TypeScript to dependency-free Python; bounded whole-reply
scanning replaces the greedy regex; strict JSON rejects duplicate keys/nonfinite
numbers; invalid and incomplete ACT envelopes are hidden from speech/history;
the last valid emotion wins. Only presentation is interpreted. No AIRI action,
delay, tool execution or remote connection is enabled. The existing v1 API uses
the emotion name; normalized intensity is not yet part of that API.

`CompanionChatRuntime.send()` invokes the port for every new provider reply before
persisting or returning it. The Ollama adapter requests this narrow output format.
Native HTTP and existing Pipecat consumers receive clean text and separate emotion.
No unrelated AIRI monorepo modules or duplicate vendor directory were imported.

Eligibility checked at 2026-09-30 18:11 UTC via
https://api.github.com/repos/moeru-ai/airi : 49,887 stars, MIT, not archived.
