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
- retrieval remains dependency-free keyword/CJK matching for the current prototype.

The upstream Apache-2.0 license is reproduced in `third_party/mem0/LICENSE`.
