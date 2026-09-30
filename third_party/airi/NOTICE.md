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

## 2026-09-30: paired history fused into live prompt compaction

`conversation.py` now directly ports the reverse scan from
`keepRecentHistoryItems` in pinned `packages/core-agent/src/messages/compaction.ts`
(blob `59a76a9877086f66b5abc09b0f22802e4e27df7d`). MyGPT maps user messages to
upstream turns and following assistant messages to reactions. It retains the
existing `recent_turn_limit` maximum-row budget by deriving the number of user
turns inside that budget before the upstream scan; the output can shrink but
never expand the configured row budget. If no complete user turn fits, the
trimmed reaction-only tail is omitted. Untrimmed history is unchanged, including
an intentional initial assistant greeting.

This closes a real provider path where slicing two rows produced an orphan old
assistant reply followed by the new user question. Compacted IDs include the
whole omitted group; SQLite history and replay receipts are not deleted or
rewritten. No summaries or long-term memories are generated.

The exact upstream file is retained under `reference/compaction.ts` solely as an
executable test oracle. Node 24's built-in type stripping executes it without npm
packages or runtime Node requirements. Its bytes match the declared Git blob;
full MIT license remains adjacent in this directory. Python tests compare the
port and budget mapping against the actual source on randomized paired histories.

Eligibility rechecked 2026-09-30 20:14 UTC: **49,890 stars**, MIT, not archived.


## Android paired-history budgeting (2026-09-30)

`CompanionPromptBudget.recentHistoryStart` directly ports the reverse scan from
`keepRecentHistoryItems` in the unchanged pinned `compaction.ts` (Git blob
`59a76a9877086f66b5abc09b0f22802e4e27df7d`). The existing Android composer invokes
this scan while selecting recent user turns with their following assistant
reactions; it no longer spends the entire history budget on an orphan reply.

Android adaptation uses list indices, omits assistant-only legacy prefixes, and
fits/truncates each complete positional group under the existing character cap.
It may omit a group if even its minimum representation cannot fit. Current user
text and durable history are untouched. Valid surrogate pairs stay intact when
history/memory snippets are clipped. This does not add semantic summarization or
validate arbitrary reply-to graphs. Full MIT attribution already reaches every
shared-source Android consumer through direct/inherited AIRI asset notices.

`android_spike/tools/airi_history_oracle.mjs` executes the unchanged upstream
TypeScript with Node 24 type stripping, without npm, to verify 128 deterministic
Android suffix-selection fixtures. The actual Java prompt composer additionally
runs bounded-history/authority/Unicode projection regressions.
