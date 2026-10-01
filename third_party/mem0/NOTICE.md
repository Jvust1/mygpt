# Mem0 attribution

Upstream: https://github.com/mem0ai/mem0  
Pinned upstream commit: `94c3fe9f238f3dbf29c9ce98643bd71eb13077cd`  
License: Apache-2.0

MyGPT directly adapts the memory lifecycle and audit-history concepts from:

- `mem0-ts/src/oss/src/storage/MemoryHistoryManager.ts`
- the public Mem0 memory surface: add / search / get / update / delete / history.

Local derived/modified file:

- `brain/mygpt_brain/memory_store.py`

Material changes in MyGPT:

- the implementation is SQLite/Pydantic rather than Mem0's storage stack;
- memory creation remains explicit and never auto-captures the whole chat transcript;
- update/delete operations are transactional with an append-only audit table;
- identity fields (namespace/kind/source/created_at) cannot be silently rewritten;
- delete removes active memory content while preserving the local audit event;
- retrieval uses bounded namespace-scoped candidates and the separately
  attributed dependency-free scikit-learn lexical scorer.

The upstream Apache-2.0 license is reproduced in `third_party/mem0/LICENSE`.


Additional Android derived implementation:
- `android_llm_spike/companion/src/main/java/dev/mygpt/companionv2/LocalCompanionMemoryStore.kt`

The Android store keeps the same explicit add/search/get/update/delete/history
lifecycle. It also adds a `purge()` privacy path that removes both active memory
and its audit history when the user explicitly asks to forget/erase a memory.
Chat turns are not automatically written to this store.


Conversation continuity is stored separately from semantic long-term memory:
- `android_llm_spike/companion/src/main/java/dev/mygpt/companionv2/LocalConversationStore.kt`

This bounded SQLite store contains only visible user/assistant text and is used
once to prime recent conversational continuity after a local model reload.
It does not store Book context blocks, recalled-memory blocks, raw audio, or ACT
control markers, and it never promotes conversation text into long-term memory.

Local lifecycle hardening (2026-10-01): Python `MemoryStore.update` holds the
existing reentrant lock across read/validate/write so overlapping operations on
that instance cannot restore stale tags or resurrect a deleted record. Existing
SQLite/audit rollback and explicit-write policy remain intact. This does not
introduce cross-instance/process conflict resolution or import new Mem0 code.
Queued deletes sample their default timestamp after acquiring the same lock;
explicit backward-time rejection remains unchanged.
