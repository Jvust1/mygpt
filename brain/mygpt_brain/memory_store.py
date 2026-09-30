"""Small local companion-memory store.

The store is deliberately explicit: chat transcripts are not silently turned
into memories. Callers must create bounded MemoryRecord values after a separate
policy/consent decision.

The update/delete/history lifecycle and audit-log shape are adapted from Mem0's
Apache-2.0 licensed memory APIs and MemoryHistoryManager. See
third_party/mem0/NOTICE.md.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, field_validator

from .core import Contract, Identifier
from .lexical_memory import (
    MAX_CANDIDATES, MAX_QUERY_CHARS, lowercase_lexical_text,
    normalize_memory_text, tfidf_memory_scores,
)

MemoryKind = Literal[
    "preference",
    "fact",
    "study_pattern",
    "user_instruction",
    "companion_state",
]
MemorySource = Literal["user_explicit", "reviewed_inference", "imported_reference"]
MemoryTag = Annotated[str, Field(min_length=1, max_length=48)]
MemoryAction = Literal["ADD", "UPDATE", "DELETE"]


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


class MemoryHistoryEvent(Contract):
    schema_version: Literal["mygpt.memory-history.v1"] = "mygpt.memory-history.v1"
    history_id: Annotated[int, Field(strict=True, ge=1)]
    memory_id: Identifier
    previous_value: str | None = None
    new_value: str | None = None
    action: MemoryAction
    created_at: AwareDatetime
    is_deleted: bool = False

    @field_validator("created_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class MemoryStore:
    """SQLite-backed local memory index with bounded retrieval and edit history."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        # Use the same pinned sklearn preprocessing in candidate SQL and the
        # final scorer. Register per connection, including reopened databases;
        # no data rewrite, persistent index or global SQLite override is needed.
        self._db.create_function("mygpt_lexical_lower", 1, lowercase_lexical_text, deterministic=True)
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
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS memory_history(
                       history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                       memory_id TEXT NOT NULL,
                       previous_value TEXT,
                       new_value TEXT,
                       action TEXT NOT NULL,
                       created_at TEXT NOT NULL,
                       is_deleted INTEGER NOT NULL DEFAULT 0
                   )"""
            )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_history_id "
                "ON memory_history(memory_id, history_id DESC)"
            )

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    @staticmethod
    def _checked_time(value: datetime | None) -> datetime:
        result = value or datetime.now(timezone.utc)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError("memory lifecycle time must be timezone-aware")
        return result.astimezone(timezone.utc)

    def _add_history(
        self,
        *,
        memory_id: str,
        previous_value: str | None,
        new_value: str | None,
        action: MemoryAction,
        at: datetime,
        is_deleted: bool = False,
    ) -> None:
        self._db.execute(
            """INSERT INTO memory_history(
                   memory_id,previous_value,new_value,action,created_at,is_deleted
               ) VALUES(?,?,?,?,?,?)""",
            (
                memory_id,
                previous_value,
                new_value,
                action,
                at.isoformat(),
                1 if is_deleted else 0,
            ),
        )

    def put(self, record: MemoryRecord, *, allow_update: bool = False) -> MemoryRecord:
        record = MemoryRecord.model_validate(record)
        if record.updated_at < record.created_at:
            raise ValueError("updated_at cannot precede created_at")
        tags_json = json.dumps(record.tags, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self._db:
            existing = self._db.execute(
                "SELECT * FROM memories WHERE memory_id=?", (record.memory_id,)
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
                self._add_history(
                    memory_id=record.memory_id,
                    previous_value=None,
                    new_value=record.text,
                    action="ADD",
                    at=record.updated_at,
                )
            else:
                immutable_existing = (
                    existing["namespace"],
                    existing["kind"],
                    existing["source"],
                    existing["created_at"],
                )
                immutable_new = (
                    record.namespace,
                    record.kind,
                    record.source,
                    record.created_at.isoformat(),
                )
                if immutable_existing != immutable_new:
                    raise ValueError("immutable memory identity fields changed")
                if record.updated_at < datetime.fromisoformat(existing["updated_at"]):
                    raise ValueError("memory update time cannot move backwards")
                if existing["text"] == record.text and existing["tags"] == tags_json:
                    return record
                self._db.execute(
                    """UPDATE memories
                       SET text=?, tags=?, updated_at=?
                       WHERE memory_id=?""",
                    (
                        record.text,
                        tags_json,
                        record.updated_at.isoformat(),
                        record.memory_id,
                    ),
                )
                self._add_history(
                    memory_id=record.memory_id,
                    previous_value=existing["text"],
                    new_value=record.text,
                    action="UPDATE",
                    at=record.updated_at,
                )
        return record

    def update(
        self,
        memory_id: str,
        *,
        text: str,
        tags: list[str] | None = None,
        updated_at: datetime | None = None,
    ) -> MemoryRecord:
        """Update one memory atomically while preserving an audit event."""
        current = self.get(memory_id)
        if current is None:
            raise ValueError("memory_id not found")
        next_record = current.model_copy(
            update={
                "text": text,
                "tags": current.tags if tags is None else tags,
                "updated_at": self._checked_time(updated_at),
            }
        )
        return self.put(next_record, allow_update=True)

    def delete(self, memory_id: str, *, deleted_at: datetime | None = None) -> bool:
        """Delete active memory bytes while preserving the edit/delete audit trail."""
        at = self._checked_time(deleted_at)
        with self._lock, self._db:
            existing = self._db.execute(
                "SELECT * FROM memories WHERE memory_id=?", (memory_id,)
            ).fetchone()
            if existing is None:
                return False
            if at < datetime.fromisoformat(existing["updated_at"]):
                raise ValueError("memory delete time cannot precede latest update")
            self._add_history(
                memory_id=memory_id,
                previous_value=existing["text"],
                new_value=None,
                action="DELETE",
                at=at,
                is_deleted=True,
            )
            self._db.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
        return True

    def history(self, memory_id: str, *, limit: int = 100) -> list[MemoryHistoryEvent]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be in 1..100")
        with self._lock:
            rows = self._db.execute(
                """SELECT history_id,memory_id,previous_value,new_value,action,
                          created_at,is_deleted
                   FROM memory_history
                   WHERE memory_id=?
                   ORDER BY history_id DESC
                   LIMIT ?""",
                (memory_id, limit),
            ).fetchall()
        return [
            MemoryHistoryEvent(
                history_id=row["history_id"],
                memory_id=row["memory_id"],
                previous_value=row["previous_value"],
                new_value=row["new_value"],
                action=row["action"],
                created_at=datetime.fromisoformat(row["created_at"]),
                is_deleted=bool(row["is_deleted"]),
            )
            for row in rows
        ]

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
        """Bounded candidate lookup plus scikit-learn-derived lexical relevance.

        The chat contract accepts 4000 characters; keep all of that user text
        for the provider. Only candidate lookup is split into <=500-char windows.
        At most eight windows and 64 namespace-scoped records reach the scorer.
        """
        if not isinstance(query, str) or not query.strip():
            return []
        if len(query) > MAX_QUERY_CHARS:
            raise ValueError("query too long")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("limit must be in 1..20")
        if len(normalize_memory_text(query)) < 2:
            return []
        windows = [query[start:start + 500] for start in range(0, len(query), 500)]
        per_window = min(20, MAX_CANDIDATES // len(windows))
        candidates: dict[str, MemoryRecord] = {}
        with self._lock:
            for window in windows:
                projection = normalize_memory_text(window)[:500]
                for record in self._keyword_candidates(projection, namespace=namespace, limit=per_window):
                    candidates[record.memory_id] = record
        records = list(candidates.values())
        documents = [record.text + " " + " ".join(record.tags) for record in records]
        scores = tfidf_memory_scores(query, documents)
        ranked = [(score, record) for score, record in zip(scores, records) if score > 0.0]
        ranked.sort(key=lambda item: (-item[0], -item[1].updated_at.timestamp(), item[1].memory_id))
        return [record for _score, record in ranked[:limit]]

    def _keyword_candidates(
        self,
        query: str,
        *,
        namespace: str = "default",
        limit: int = 8,
    ) -> list[MemoryRecord]:
        """Existing bounded SQL candidate selector; not the final ranking."""
        if not isinstance(query, str) or not query.strip():
            return []
        if len(query) > 500:
            raise ValueError("query too long")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("limit must be in 1..20")

        tokens: list[str] = []
        lowered = lowercase_lexical_text(query)
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
            return []

        clauses = []
        params: list[object] = [namespace]
        for token in tokens:
            clauses.append("(mygpt_lexical_lower(text) LIKE ? ESCAPE '\\' OR mygpt_lexical_lower(tags) LIKE ? ESCAPE '\\')")
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
