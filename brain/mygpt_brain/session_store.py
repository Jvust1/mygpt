"""Durable local chat sessions and idempotent request receipts.

The local-first persistence/outbox ideas are adapted from Project AIRI's
MIT-licensed chat session repository. mygpt uses SQLite instead of IndexedDB
and keeps model/provider state out of the durable record.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Sequence

from .conversation import ChatMessage


class ChatSessionStore:
    """SQLite-backed chat history with transactional request receipts."""

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
                """CREATE TABLE IF NOT EXISTS chat_meta(
                       key TEXT PRIMARY KEY,
                       value TEXT NOT NULL
                   )"""
            )
            row = self._db.execute(
                "SELECT value FROM chat_meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                self._db.execute(
                    "INSERT INTO chat_meta(key,value) VALUES('schema_version','1')"
                )
            elif row["value"] != "1":
                raise RuntimeError("unsupported chat schema version")

            self._db.execute(
                """CREATE TABLE IF NOT EXISTS chat_sessions(
                       session_id TEXT PRIMARY KEY,
                       persona_id TEXT NOT NULL,
                       created_at TEXT NOT NULL,
                       updated_at TEXT NOT NULL
                   )"""
            )
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS chat_messages(
                       message_id TEXT PRIMARY KEY,
                       session_id TEXT NOT NULL,
                       ordinal INTEGER NOT NULL,
                       role TEXT NOT NULL,
                       authority TEXT,
                       content TEXT NOT NULL,
                       created_at TEXT NOT NULL,
                       reply_to_message_id TEXT,
                       FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
                           ON DELETE CASCADE,
                       UNIQUE(session_id, ordinal)
                   )"""
            )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_messages_session "
                "ON chat_messages(session_id, ordinal)"
            )
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS chat_request_receipts(
                       request_id TEXT PRIMARY KEY,
                       session_id TEXT NOT NULL,
                       fingerprint TEXT NOT NULL,
                       result_json TEXT NOT NULL,
                       completed_at TEXT NOT NULL,
                       FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
                           ON DELETE CASCADE
                   )"""
            )

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> "ChatSessionStore":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def load_messages(self, session_id: str) -> list[ChatMessage]:
        with self._lock:
            rows = self._db.execute(
                """SELECT message_id, session_id, role, authority, content,
                          created_at, reply_to_message_id
                   FROM chat_messages
                   WHERE session_id=?
                   ORDER BY ordinal ASC""",
                (session_id,),
            ).fetchall()
        return [
            ChatMessage(
                message_id=row["message_id"],
                session_id=row["session_id"],
                role=row["role"],
                authority=row["authority"],
                content=row["content"],
                created_at=datetime.fromisoformat(row["created_at"]),
                reply_to_message_id=row["reply_to_message_id"],
            )
            for row in rows
        ]

    def session_persona(self, session_id: str) -> str | None:
        with self._lock:
            row = self._db.execute(
                "SELECT persona_id FROM chat_sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return None if row is None else str(row["persona_id"])

    def get_receipt(self, request_id: str) -> tuple[str, dict[str, Any]] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT fingerprint, result_json FROM chat_request_receipts WHERE request_id=?",
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["fingerprint"]), json.loads(row["result_json"])

    def commit_exchange(
        self,
        *,
        persona_id: str,
        messages: Sequence[ChatMessage],
        request_id: str,
        fingerprint: str,
        result: dict[str, Any],
        completed_at: datetime,
    ) -> None:
        """Atomically persist new messages and the idempotency receipt."""
        if not messages:
            raise ValueError("messages cannot be empty")
        session_id = messages[0].session_id
        if any(message.session_id != session_id for message in messages):
            raise ValueError("messages cannot mix session ids")
        completed = completed_at.astimezone(timezone.utc).isoformat()
        result_json = json.dumps(
            result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

        with self._lock, self._db:
            session = self._db.execute(
                "SELECT persona_id FROM chat_sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if session is None:
                first_time = min(message.created_at for message in messages).isoformat()
                self._db.execute(
                    """INSERT INTO chat_sessions(session_id,persona_id,created_at,updated_at)
                       VALUES(?,?,?,?)""",
                    (session_id, persona_id, first_time, completed),
                )
            elif session["persona_id"] != persona_id:
                raise ValueError("session belongs to another persona")
            else:
                self._db.execute(
                    "UPDATE chat_sessions SET updated_at=? WHERE session_id=?",
                    (completed, session_id),
                )

            receipt = self._db.execute(
                """SELECT fingerprint, result_json FROM chat_request_receipts
                   WHERE request_id=?""",
                (request_id,),
            ).fetchone()
            if receipt is not None:
                if receipt["fingerprint"] != fingerprint:
                    raise ValueError("request_id conflict")
                if receipt["result_json"] != result_json:
                    raise ValueError("request receipt result conflict")
                return

            row = self._db.execute(
                "SELECT COALESCE(MAX(ordinal),0) AS n FROM chat_messages WHERE session_id=?",
                (session_id,),
            ).fetchone()
            next_ordinal = int(row["n"]) + 1
            for message in messages:
                existing = self._db.execute(
                    """SELECT session_id, role, authority, content, created_at,
                              reply_to_message_id
                       FROM chat_messages WHERE message_id=?""",
                    (message.message_id,),
                ).fetchone()
                if existing is not None:
                    expected = (
                        message.session_id,
                        message.role,
                        message.authority,
                        message.content,
                        message.created_at.isoformat(),
                        message.reply_to_message_id,
                    )
                    observed = tuple(existing)
                    if observed != expected:
                        raise ValueError("message_id conflict")
                    continue
                self._db.execute(
                    """INSERT INTO chat_messages(
                           message_id,session_id,ordinal,role,authority,content,
                           created_at,reply_to_message_id
                       ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        message.message_id,
                        message.session_id,
                        next_ordinal,
                        message.role,
                        message.authority,
                        message.content,
                        message.created_at.isoformat(),
                        message.reply_to_message_id,
                    ),
                )
                next_ordinal += 1

            self._db.execute(
                """INSERT INTO chat_request_receipts(
                       request_id,session_id,fingerprint,result_json,completed_at
                   ) VALUES(?,?,?,?,?)""",
                (request_id, session_id, fingerprint, result_json, completed),
            )

    def delete_session(self, session_id: str) -> bool:
        with self._lock, self._db:
            cur = self._db.execute(
                "DELETE FROM chat_sessions WHERE session_id=?", (session_id,)
            )
        return cur.rowcount > 0
