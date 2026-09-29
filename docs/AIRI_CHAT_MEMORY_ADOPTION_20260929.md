# AIRI chat/memory adoption checkpoint — 2026-09-29

## Goal

Advance MyGPT's final companion form by moving proven chat/session patterns from Project AIRI into MyGPT's existing Python Brain without importing the AIRI monorepo or changing Book/Live authority boundaries.

## Upstream identity

- repository: https://github.com/moeru-ai/airi
- pinned commit: `b40e3e87b149ea5fb75d4944440493829e601411`
- license: MIT
- local attribution: `third_party/airi/LICENSE`, `third_party/airi/NOTICE.md`

## Directly adapted upstream areas

- `packages/core-agent/src/messages/types.ts`: authority-separated turns/context;
- `packages/core-agent/src/session/merge-loaded-session-messages.ts`: deterministic stored/current merge and dedupe;
- `packages/core-agent/src/messages/compaction.ts`: bounded recent history;
- `packages/stage-ui/src/database/repos/chat-sessions.repo.ts`: local-first durable session/idempotency principles.

## MyGPT implementation

- `brain/mygpt_brain/conversation.py`
- `brain/mygpt_brain/session_store.py`
- `brain/mygpt_brain/memory_store.py`
- `brain/mygpt_brain/companion_chat.py`
- `brain/mygpt_brain/providers.py`
- `brain/scripts/chat_local_ollama.py`

The SQLite memory and Ollama adapter are MyGPT integration code. Raw chat is not automatically promoted into long-term memory. The CLI requires `:remember` for explicit memory creation.

## Provider and authority boundary

Only `http://127.0.0.1:11434/api/chat` is accepted by the prototype Ollama responder. Application context and recalled memories are rendered as data blocks rather than trusted system instructions. This preserves Book-first semantics without allowing imported Book text or recalled memory text to silently gain instruction authority.

## Verification

Local isolated suite: 18 passed / 0 failed. GitHub Actions run 36590899728 was attempted twice; both attempts failed before any step ran with runner_id=0. Therefore remote CI is infrastructure-blocked and must not be reported as a test failure or pass. A real Ollama inference has not yet been accepted as evidence.

## Next engineering increments

1. obtain exact-head remote Brain CI execution when a runner becomes available;
2. expose the chat runtime through a bounded local transport suitable for the Android host;
3. inject trusted Book semantic context through the lower-authority context channel;
4. keep memory writes explicit/reviewable, then add a separate opt-in extraction policy only after evaluation;
5. benchmark a local model on the user's actual hardware before selecting a default model.
