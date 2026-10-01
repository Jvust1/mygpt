"""Optional Mem0 bridge for reviewed mygpt companion memories.

Upstream: mem0ai/mem0 @
94c3fe9f238f3dbf29c9ce98643bd71eb13077cd (Apache-2.0).

mygpt's local MemoryStore remains authoritative. This adapter only mirrors
explicitly reviewed records into Mem0 and retrieves candidates for recall.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .memory_store import MemoryRecord


@dataclass(frozen=True)
class Mem0Recall:
    memory_id: str
    text: str
    score: float
    metadata: dict[str, Any]


class Mem0MemoryBridge:
    def __init__(self, memory: Any, *, user_id: str) -> None:
        if not str(user_id).strip():
            raise ValueError("user_id cannot be empty")
        if not callable(getattr(memory, "add", None)):
            raise TypeError("memory must provide add()")
        if not callable(getattr(memory, "search", None)):
            raise TypeError("memory must provide search()")
        self._memory = memory
        self.user_id = str(user_id)

    def mirror(self, record: MemoryRecord) -> None:
        record = MemoryRecord.model_validate(record)
        metadata = {
            "mygpt_memory_id": record.memory_id,
            "namespace": record.namespace,
            "kind": record.kind,
            "source": record.source,
            "tags": list(record.tags),
        }
        messages = [{"role": "user", "content": record.text}]
        try:
            self._memory.add(
                messages,
                user_id=self.user_id,
                infer=False,
                metadata=metadata,
            )
        except TypeError:
            self._memory.add(
                messages,
                user_id=self.user_id,
                metadata=metadata,
            )

    def search(self, query: str, *, limit: int = 5) -> list[Mem0Recall]:
        if not str(query).strip():
            return []
        if limit < 1:
            raise ValueError("limit must be >= 1")
        try:
            raw = self._memory.search(
                query=query,
                filters={"user_id": self.user_id},
                top_k=limit,
            )
        except TypeError:
            raw = self._memory.search(query, user_id=self.user_id, limit=limit)
        rows = raw.get("results", []) if isinstance(raw, Mapping) else raw
        if not isinstance(rows, list):
            raise RuntimeError("Mem0 search response must contain a list")

        out: list[Mem0Recall] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                continue
            metadata = row.get("metadata")
            metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
            text = row.get("memory") or row.get("text") or ""
            if not isinstance(text, str) or not text.strip():
                continue
            try:
                score = float(row.get("score", row.get("similarity", 0.0)))
            except (TypeError, ValueError):
                score = 0.0
            memory_id = str(
                metadata.get("mygpt_memory_id")
                or row.get("id")
                or f"mem0:{index}"
            )
            out.append(
                Mem0Recall(
                    memory_id=memory_id,
                    text=text,
                    score=score,
                    metadata=metadata,
                )
            )
        out.sort(key=lambda item: (-item.score, item.memory_id))
        return out[:limit]


def create_mem0_bridge(*, user_id: str, config: dict[str, Any] | None = None) -> Mem0MemoryBridge:
    try:
        from mem0 import Memory
    except ImportError as exc:
        raise RuntimeError(
            "Mem0 is optional; install brain[mem0] before enabling external recall"
        ) from exc
    if config is None:
        memory = Memory()
    elif callable(getattr(Memory, "from_config", None)):
        memory = Memory.from_config(config)
    else:
        memory = Memory(config=config)
    return Mem0MemoryBridge(memory, user_id=user_id)
