"""Small local companion-memory store.

The store is deliberately explicit: chat transcripts are not silently turned
into memories. Callers must create bounded MemoryRecord values after a separate
policy/consent decision.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import threading
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, field_validator

from .core import Contract, Identifier

MemoryKind = Literal[
    "preference",
    "fact",
    "study_pattern",
    "user_instruction",
    "companion_state",
]
MemorySource = Literal["user_explicit", "reviewed_inference", "imported_reference"]
MemoryTag = Annotated[str, Field(min_length=1, max_length=48)]


class MemoryRecord(Contract):
    schema_version: Literal["mygpt.memory-record.v1"] = "mygpt.memory-record.v1"
    memory_id: Identifier
    namespace: Identifier = "default"
    kind: MemoryKind
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    tags: Annotated[list[MemoryTag], Field(max_length=16)] = Field(default_factory=list)
    source: MemorySource
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in value:
            if tag != tag.strip() or any(ord(ch) < 32 for ch in tag):
                raise ValueError("memory tags must be trimmed printable text")
            if tag not in cleaned:
                cleaned.append(tag)
        return cleaned

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("memory text must not be blank")
        return value


class MemoryStore:
    """SQLite-backed local memory index with bounded retrieval."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._db:
            self._db.execute("PRAGMA foreign_keys=ON")
            if self.path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS meta(
                       key TEXT PRIMARY KEY,
                       value TEXT NOT NULL
                   )"""
            )
            row = self._db.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO meta(key,value) VALUES('schema_version','1')"
                )
            elif row["value"] != "1":
                raise RuntimeError("unsupported memory schema version")
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS memories(
                       memory_id TEXT PRIMARY KEY,
                       namespace TEXT NOT NULL,
                       kind TEXT NOT NULL,
                       text TEXT NOT NULL,
                       tags TEXT NOT NULL,
                       source TEXT NOT NULL,
                       created_at TEXT NOT NULL,
                       updated_at TEXT NOT NULL
                   )"""
            )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_namespace_updated "
                "ON memories(namespace, updated_at DESC)"
            )

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def put(self, record: MemoryRecord, *, allow_update: bool = False) -> MemoryRecord:
        record = MemoryRecord.model_validate(record)
        if record.updated_at < record.created_at:
            raise ValueError("updated_at cannot precede created_at")
        import json
        tags_json = json.dumps(record.tags, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self._db:
            existing = self._db.execute(
                "SELECT memory_id FROM memories WHERE memory_id=?", (record.memory_id,)
            ).fetchone()
            if existing is not None and not allow_update:
                raise ValueError("memory_id already exists")
            if existing is None:
                self._db.execute(
                    """INSERT INTO memories(
                           memory_id, namespace, kind, text, tags, source,
                           created_at, updated_at
                       ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        record.memory_id,
                        record.namespace,
                        record.kind,
                        record.text,
                        tags_json,
                        record.source,
                        record.created_at.isoformat(),
                        record.updated_at.isoformat(),
                    ),
                )
            else:
                self._db.execute(
                    """UPDATE memories
                       SET namespace=?, kind=?, text=?, tags=?, source=?, updated_at=?
                       WHERE memory_id=?""",
                    (
                        record.namespace,
                        record.kind,
                        record.text,
                        tags_json,
                        record.source,
                        record.updated_at.isoformat(),
                        record.memory_id,
                    ),
                )
        return record

    def get(self, memory_id: str) -> MemoryRecord | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM memories WHERE memory_id=?", (memory_id,)
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def recent(self, *, namespace: str = "default", limit: int = 8) -> list[MemoryRecord]:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit must be in 1..50")
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM memories WHERE namespace=? "
                "ORDER BY updated_at DESC, memory_id ASC LIMIT ?",
                (namespace, limit),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def search(
        self,
        query: str,
        *,
        namespace: str = "default",
        limit: int = 8,
    ) -> list[MemoryRecord]:
        """Simple dependency-free retrieval for the first local prototype."""
        if not isinstance(query, str) or not query.strip():
            return []
        if len(query) > 500:
            raise ValueError("query too long")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("limit must be in 1..20")

        tokens: list[str] = []
        lowered = query.lower()
        # Latin/digit words use whitespace tokenization. CJK text additionally
        # contributes short bigrams so natural Chinese queries can retrieve
        # a concise memory such as "喜欢简洁回答" from "请简洁一点陪我学习".
        for raw in lowered.split():
            token = "".join(ch for ch in raw if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
            if len(token) >= 2 and token not in tokens:
                tokens.append(token)
        cjk = "".join(ch for ch in lowered if "\u4e00" <= ch <= "\u9fff")
        for index in range(max(0, len(cjk) - 1)):
            token = cjk[index:index + 2]
            if token not in tokens:
                tokens.append(token)
            if len(tokens) >= 12:
                break
        tokens = tokens[:12]
        if not tokens:
            return self.recent(namespace=namespace, limit=min(limit, 8))

        clauses = []
        params: list[object] = [namespace]
        for token in tokens:
            clauses.append("(lower(text) LIKE ? ESCAPE '\\' OR lower(tags) LIKE ? ESCAPE '\\')")
            pattern = "%" + token.replace("%", "\\%").replace("_", "\\_") + "%"
            params.extend((pattern, pattern))
        params.append(limit)
        sql = (
            "SELECT * FROM memories WHERE namespace=? AND ("
            + " OR ".join(clauses)
            + ") ORDER BY updated_at DESC, memory_id ASC LIMIT ?"
        )
        with self._lock:
            rows = self._db.execute(sql, params).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> MemoryRecord:
        import json
        return MemoryRecord(
            memory_id=row["memory_id"],
            namespace=row["namespace"],
            kind=row["kind"],
            text=row["text"],
            tags=json.loads(row["tags"]),
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
