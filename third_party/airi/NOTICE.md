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
  - renderer-neutral emotion vocabulary used across character renderers.

Local derived/adapted files:

- `brain/mygpt_brain/conversation.py`
- `brain/mygpt_brain/session_store.py`
- `brain/mygpt_brain/character_card.py`
- `android_spike/src/main/java/dev/mygpt/spike/PresentationEmotion.java`

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
