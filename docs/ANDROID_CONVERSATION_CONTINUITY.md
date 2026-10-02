# Android companion conversation continuity

Date: 2026-09-30

Companion V2 uses two separate persistence concepts:

1. **Long-term memory** — explicit only, stored in `LocalCompanionMemoryStore`.
2. **Recent conversation history** — visible user/assistant text only, stored in
   `LocalConversationStore`.

They are intentionally not the same database or policy.

## Why a recent-history store is needed

The pinned llama.cpp Android runtime keeps chat/KV state while a model remains
loaded. After process death or model reload that native state disappears.

On the first user turn after a model load, Companion V2 renders at most 10 recent
stored user/assistant turns as
`RECENT_CONVERSATION_HISTORY_JSON`. After that one priming turn, llama.cpp's
own in-memory chat state provides continuity and the durable history block is not
repeated every turn.

## What is stored

Stored:
- visible user text;
- visible assistant reply after AIRI ACT markers are removed;
- timestamps and role.

Not stored:
- Book semantic context;
- recalled-memory prompt blocks;
- system/persona prompt;
- raw microphone audio;
- generated TTS audio;
- AIRI ACT control markers.

The store keeps at most 100 rows per persona namespace.

## Clearing

The UI exposes “清空最近对话”, and the typed command `:clear-chat` performs the
same operation. If a local model is loaded, the app reloads it afterward so the
native llama.cpp chat/KV state is reset as well.

Clearing recent conversation history does not delete explicit long-term memory.
Conversely, `:forget <memory-id>` purges that long-term memory but does not erase
ordinary visible chat history unless the user separately clears recent chat.

## Current-memory freshness

Every user turn carries a `LOCAL_RECALLED_MEMORY` block:
- relevant explicit memory rows, or
- `{"status":"none"}`.

The system prompt treats only the current turn's memory block as current memory.
Older memory blocks retained in llama.cpp's chat/KV history are historical data
and must not override an updated/deleted current memory state.
