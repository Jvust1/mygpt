# Mem0 companion-memory bridge — 2026-09-30

Upstream: `mem0ai/mem0`  
Revision: `94c3fe9f238f3dbf29c9ce98643bd71eb13077cd`  
License: Apache-2.0

mygpt keeps the local SQLite `MemoryStore` authoritative. Only explicitly reviewed `MemoryRecord` values are mirrored to Mem0. The adapter uses `infer=False` when supported, preserves the local memory ID in metadata, and uses Mem0 only as optional external recall.
