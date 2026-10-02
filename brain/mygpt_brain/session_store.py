"""Durable local chat sessions and idempotent request receipts.

The local-first persistence/outbox ideas are adapted from Project AIRI's
MIT-licensed chat session repository. mygpt uses SQLite instead of IndexedDB
and keeps model/provider state out of the durable record.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Sequence
from uuid import uuid4

from .conversation import ChatMessage


_UNCHECKED_REVISION = object()


@dataclass(frozen=True)
class SessionPromptState:
    messages: list[ChatMessage]
    compacted_message_ids: list[str]
    persona_id: str | None
    revision: str | None
    deletion_epoch: int


class ChatSessionStore:
    """SQLite-backed chat history with transactional request receipts."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        try:
            self._init_schema()
        except BaseException:
            self._db.close()
            raise

    def _init_schema(self) -> None:
        with self._lock, self._db:
            self._db.execute("PRAGMA foreign_keys=ON")
            if self.path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            # DDL and the version marker migrate together, or not at all.
            self._db.execute("BEGIN IMMEDIATE")
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
                    "INSERT INTO chat_meta(key,value) VALUES('schema_version','2')"
                )
            elif row["value"] not in ("1", "2"):
                raise RuntimeError("unsupported chat schema version")

            self._db.execute(
                """CREATE TABLE IF NOT EXISTS chat_sessions(
                       session_id TEXT PRIMARY KEY,
                       persona_id TEXT NOT NULL,
                       created_at TEXT NOT NULL,
                       updated_at TEXT NOT NULL,
                       revision TEXT NOT NULL DEFAULT ''
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
                       compacted_prefix_json TEXT,
                       FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
                           ON DELETE CASCADE
                   )"""
            )
            # Additive dispatch journal: failed/ambiguous desktop requests must
            # not contact the provider again merely because a client retries.
            # No transcript copy, retention policy, or schema-2 rewrite.
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS chat_dispatch_claims(
                       request_id TEXT PRIMARY KEY,
                       session_id TEXT NOT NULL,
                       fingerprint TEXT NOT NULL,
                       generation TEXT NOT NULL
                   )"""
            )
            if row is not None and row["value"] == "1":
                self._db.execute("ALTER TABLE chat_sessions ADD COLUMN revision TEXT NOT NULL DEFAULT ''")
                self._db.execute("ALTER TABLE chat_request_receipts ADD COLUMN compacted_prefix_json TEXT")
                self._db.execute("UPDATE chat_meta SET value='2' WHERE key='schema_version'")
            self._db.execute("INSERT OR IGNORE INTO chat_meta(key,value) VALUES('deletion_epoch','0')")
            # v1 messages/receipts remain byte-for-byte intact. A changed version
            # makes old binaries fail closed instead of misreading v2 receipts.

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> "ChatSessionStore":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def claim_dispatch(self, request_id: str, session_id: str, fingerprint: str) -> tuple[bool, str]:
        """Persist the no-reexecution boundary before contacting a provider.

        A false fresh flag requires receipt recovery or an explicit unknown-outcome
        error, never a second dispatch. The generation binds admission to this
        claim lifecycle, including deletion before the runtime history snapshot. Claims retain hashes only and intentionally
        survive missing/failed exchanges; they are not proof of a saved reply.
        Explicit delete_session removes that session's claims with its history.
        """
        with self._lock, self._db:
            self._db.execute("BEGIN IMMEDIATE")
            prior = self._db.execute(
                "SELECT session_id, fingerprint, generation FROM chat_dispatch_claims WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if prior is not None:
                if (prior["session_id"], prior["fingerprint"]) != (session_id, fingerprint):
                    raise ValueError("request_id_conflict")
                return False, str(prior["generation"])
            generation = uuid4().hex
            self._db.execute(
                "INSERT INTO chat_dispatch_claims(request_id,session_id,fingerprint,generation) VALUES(?,?,?,?)",
                (request_id, session_id, fingerprint, generation),
            )
            return True, generation

    def dispatch_is_current(self, request_id: str, generation: str) -> bool:
        with self._lock:
            return self._db.execute(
                "SELECT 1 FROM chat_dispatch_claims WHERE request_id=? AND generation=?",
                (request_id, generation),
            ).fetchone() is not None

    def history_page(self, session_id: str, *, persona_id: str,
                     before: int | None = None, limit: int = 40) -> dict:
        """Bounded keyset page of saved visible messages; never load all bodies."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid_history_limit")
        if before is not None and (type(before) is not int or not 1 <= before <= 2**63-1):
            raise ValueError("invalid_history_cursor")
        cursor_clause = "AND m.ordinal<?" if before is not None else ""
        params = (session_id, persona_id, before, limit + 1) if before is not None else (session_id, persona_id, limit + 1)
        with self._lock:
            rows = self._db.execute(
                """SELECT m.* FROM chat_messages m JOIN chat_sessions s USING(session_id)
                   WHERE m.session_id=? AND s.persona_id=? AND m.role IN ('user','assistant')
                   """ + cursor_clause + " ORDER BY m.ordinal DESC LIMIT ?",
                params,
            ).fetchall()
        page = rows[:limit]
        return {
            "session_id": session_id,
            "messages": [m.model_dump(mode="json") for m in self._messages_from_rows(list(reversed(page)))],
            "next_before": int(page[-1]["ordinal"]) if len(rows) > limit else None,
        }

    def load_messages(self, session_id: str, *, persona_id: str | None = None) -> list[ChatMessage]:
        with self._lock:
            rows = self._db.execute(
                """SELECT message_id, session_id, role, authority, content,
                          created_at, reply_to_message_id
                   FROM chat_messages
                   WHERE session_id=? AND (? IS NULL OR EXISTS(
                       SELECT 1 FROM chat_sessions WHERE session_id=? AND persona_id=?))
                   ORDER BY ordinal ASC""",
                (session_id, persona_id, session_id, persona_id),
            ).fetchall()
        return self._messages_from_rows(rows)

    @staticmethod
    def _messages_from_rows(rows) -> list[ChatMessage]:
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

    def load_prompt_state(self, session_id: str, recent_turn_limit: int) -> SessionPromptState:
        """Read one consistent snapshot without materializing old message bodies.

        IDs outside the tail remain part of the public compaction result; they
        are transient, not a retained runtime cache. Authority rows are never
        silently discarded, even for histories inserted by another caller.
        """
        if type(recent_turn_limit) is not int or recent_turn_limit <= 0:
            raise ValueError("recent_turn_limit must be a positive integer")
        with self._lock, self._db:
            self._db.execute("BEGIN")
            session = self._db.execute(
                "SELECT persona_id, revision FROM chat_sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            cutoff = self._db.execute(
                """SELECT ordinal FROM chat_messages WHERE session_id=? AND role!='system'
                   ORDER BY ordinal DESC LIMIT 1 OFFSET ?""", (session_id, recent_turn_limit - 1)
            ).fetchone()
            ordinal = cutoff["ordinal"] if cutoff is not None else 0
            rows = self._db.execute(
                """SELECT * FROM chat_messages WHERE session_id=?
                   AND (role='system' OR ordinal>=?) ORDER BY ordinal""", (session_id, ordinal)
            ).fetchall()
            compacted = [row[0] for row in self._db.execute(
                """SELECT message_id FROM chat_messages WHERE session_id=?
                   AND role!='system' AND ordinal<? ORDER BY ordinal""", (session_id, ordinal)
            )]
            return SessionPromptState(
                self._messages_from_rows(rows), compacted,
                session["persona_id"] if session is not None else None,
                session["revision"] if session is not None else None,
                int(self._db.execute("SELECT value FROM chat_meta WHERE key='deletion_epoch'").fetchone()[0]),
            )

    @staticmethod
    def _ids_digest(ids: list[str]) -> str:
        return hashlib.sha256(json.dumps(ids, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _decode_receipt(self, row) -> dict[str, Any]:
        result = json.loads(row["result_json"])
        encoded = row["compacted_prefix_json"]
        if encoded is None:
            return result
        reference = json.loads(encoded)
        if (not isinstance(reference, dict)
                or set(reference) != {"version", "through_ordinal", "count", "sha256"}
                or reference["version"] != "conversation-prefix-v1"
                or type(reference["through_ordinal"]) is not int
                or type(reference["count"]) is not int
                or reference["through_ordinal"] <= 0 or reference["count"] <= 0
                or not isinstance(result, dict) or "compacted_message_ids" in result):
            raise RuntimeError("invalid compacted receipt reference")
        ids = [item[0] for item in self._db.execute(
            """SELECT message_id FROM chat_messages WHERE session_id=? AND role!='system'
               AND ordinal<=? ORDER BY ordinal""", (row["session_id"], reference["through_ordinal"])
        )]
        if len(ids) != reference["count"] or self._ids_digest(ids) != reference["sha256"]:
            raise RuntimeError("compacted receipt history integrity failure")
        result["compacted_message_ids"] = ids
        return result

    def _encode_receipt(self, session_id: str, result: dict[str, Any]) -> tuple[str, str | None]:
        ids = result.get("compacted_message_ids")
        reference = None
        # A generic store caller may supply non-prefix IDs or non-chat results.
        # Store those literally; never change ordering, membership or semantics.
        if isinstance(ids, list) and ids and all(isinstance(item, str) for item in ids):
            rows = self._db.execute(
                """SELECT message_id, ordinal FROM chat_messages
                   WHERE session_id=? AND role!='system' ORDER BY ordinal LIMIT ?""",
                (session_id, len(ids)),
            ).fetchall()
            if [row["message_id"] for row in rows] == ids:
                reference = json.dumps({
                    "version": "conversation-prefix-v1", "through_ordinal": rows[-1]["ordinal"],
                    "count": len(ids), "sha256": self._ids_digest(ids),
                }, sort_keys=True, separators=(",", ":"))
                result = {key: value for key, value in result.items() if key != "compacted_message_ids"}
        return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")), reference

    def get_receipt(self, request_id: str) -> tuple[str, dict[str, Any]] | None:
        with self._lock, self._db:
            # Reference and messages must come from the same SQLite snapshot,
            # including when another connection deletes a session concurrently.
            self._db.execute("BEGIN")
            row = self._db.execute(
                "SELECT * FROM chat_request_receipts WHERE request_id=?", (request_id,)
            ).fetchone()
            if row is None:
                return None
            return str(row["fingerprint"]), self._decode_receipt(row)

    def commit_exchange(
        self,
        *,
        persona_id: str,
        messages: Sequence[ChatMessage],
        request_id: str,
        fingerprint: str,
        result: dict[str, Any],
        completed_at: datetime,
        expected_revision: str | None | object = _UNCHECKED_REVISION,
        expected_deletion_epoch: int | None = None,
    ) -> None:
        """Atomically persist new messages and the idempotency receipt."""
        if not messages:
            raise ValueError("messages cannot be empty")
        session_id = messages[0].session_id
        if any(message.session_id != session_id for message in messages):
            raise ValueError("messages cannot mix session ids")
        completed = completed_at.astimezone(timezone.utc).isoformat()
        with self._lock, self._db:
            # Serialize competing connections before checking receipt/history.
            self._db.execute("BEGIN IMMEDIATE")
            session = self._db.execute(
                "SELECT persona_id, revision FROM chat_sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if session is not None and session["persona_id"] != persona_id:
                raise ValueError("session belongs to another persona")
            receipt = self._db.execute(
                "SELECT * FROM chat_request_receipts WHERE request_id=?", (request_id,)
            ).fetchone()
            if receipt is not None:
                if receipt["fingerprint"] != fingerprint or receipt["session_id"] != session_id:
                    raise ValueError("request_id conflict")
                if json.dumps(self._decode_receipt(receipt), sort_keys=True, ensure_ascii=False) != json.dumps(
                    result, sort_keys=True, ensure_ascii=False
                ):
                    raise ValueError("request receipt result conflict")
                return
            if expected_revision is not _UNCHECKED_REVISION:
                revision = session["revision"] if session is not None else None
                if revision != expected_revision:
                    raise ValueError("session changed during chat turn")
                # An absent snapshot can otherwise miss create->delete ABA.
                # One global counter retains no deleted session IDs. A delete
                # of an unrelated session conservatively invalidates initial
                # turns only; existing sessions have their own UUID revision.
                if expected_revision is None and expected_deletion_epoch is not None:
                    deletion_epoch = int(self._db.execute(
                        "SELECT value FROM chat_meta WHERE key='deletion_epoch'"
                    ).fetchone()[0])
                    if deletion_epoch != expected_deletion_epoch:
                        raise ValueError("session changed during chat turn")
            if session is None:
                first_time = min(message.created_at for message in messages).isoformat()
                self._db.execute(
                    """INSERT INTO chat_sessions(session_id,persona_id,created_at,updated_at,revision)
                       VALUES(?,?,?,?,?)""",
                    (session_id, persona_id, first_time, completed, uuid4().hex),
                )
            elif session["persona_id"] != persona_id:
                raise ValueError("session belongs to another persona")
            else:
                self._db.execute(
                    "UPDATE chat_sessions SET updated_at=?, revision=? WHERE session_id=?",
                    (completed, uuid4().hex, session_id),
                )

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

            result_json, reference = self._encode_receipt(session_id, result)
            self._db.execute(
                """INSERT INTO chat_request_receipts(
                       request_id,session_id,fingerprint,result_json,completed_at,compacted_prefix_json
                   ) VALUES(?,?,?,?,?,?)""",
                (request_id, session_id, fingerprint, result_json, completed, reference),
            )

    def delete_session(self, session_id: str) -> bool:
        with self._lock, self._db:
            self._db.execute("BEGIN IMMEDIATE")
            cur = self._db.execute(
                "DELETE FROM chat_sessions WHERE session_id=?", (session_id,)
            )
            claims = self._db.execute(
                "DELETE FROM chat_dispatch_claims WHERE session_id=?", (session_id,)
            )
            deleted = cur.rowcount > 0 or claims.rowcount > 0
            if deleted:
                epoch = int(self._db.execute("SELECT value FROM chat_meta WHERE key='deletion_epoch'").fetchone()[0])
                self._db.execute("UPDATE chat_meta SET value=? WHERE key='deletion_epoch'", (str(epoch + 1),))
        return deleted
