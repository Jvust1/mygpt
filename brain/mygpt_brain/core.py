"""Validated semantic events, transactional receipts, and quiet-first policy.

This prototype accepts synthetic Book events, not an authenticated Book feed.
It never calls a model, captures a screen, or infers attention from inactivity.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated, Iterator, Literal
from urllib.parse import quote

from pydantic import (AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field,
                      TypeAdapter, field_validator, model_validator)

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")]
Sequence = Annotated[int, Field(strict=True, ge=1, le=2**53 - 1)]
Kind = Literal[
    "SESSION_STARTED", "CONTEXT_CHANGED", "SESSION_PAUSED", "SESSION_RESUMED",
    "SESSION_ENDED", "DISCONNECTED", "QUIET_REQUESTED", "HELP_REQUESTED",
    "RECALL_REQUESTED",
]
CONTEXT_EVENTS = {"SESSION_STARTED", "CONTEXT_CHANGED", "SESSION_RESUMED"}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class StudyContext(Contract):
    schema_version: Literal["mygpt.study-context.v1"] = "mygpt.study-context.v1"
    evidence_kind: Literal["SIMULATED"] = "SIMULATED"
    session_id: Identifier
    course_id: Identifier
    book_id: Identifier
    book_version: Identifier
    section_id: Identifier
    source_id: Identifier
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    mode: Literal["preview", "learn", "review", "practice"]
    captured_at: AwareDatetime
    expires_at: AwareDatetime

    @field_validator("captured_at", "expires_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def bounded_lifetime(self) -> StudyContext:
        lifetime = (self.expires_at - self.captured_at).total_seconds()
        if not 0 < lifetime <= 300:
            raise ValueError("context lifetime must be in (0, 300] seconds")
        return self

    @property
    def reference(self) -> str:
        return f"book:{self.book_id}:{self.book_version}:{self.section_id}:{self.source_id}"

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.course_id, self.book_id, self.book_version


# v1 identifiers, references, and persisted receipts remain unchanged. Only the
# explicitly versioned Reader context accepts the observed @-bearing versions.
ReaderBookVersion = Annotated[str, Field(
    strict=True, min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,159}$")]


class ReaderStudyContext(StudyContext):
    schema_version: Literal["mygpt.reader-context.v2"] = "mygpt.reader-context.v2"
    book_version: ReaderBookVersion
    source_kind: Identifier
    source_layer: Literal["source", "correction", "derived"]
    layer_id: Identifier
    source_serialization: Literal["reader-selected-json-v1"] = "reader-selected-json-v1"

    @property
    def reference(self) -> str:
        # Each segment is escaped independently. Include bytes and layer identity:
        # a correction or a changed body must never inherit the original's ref.
        fields = (self.course_id, self.book_id, self.book_version, self.section_id,
                  self.source_kind, self.source_id, self.source_layer, self.layer_id,
                  self.source_serialization, self.source_sha256)
        return "reader:v2:" + ":".join(quote(x, safe="") for x in fields)

    @property
    def identity(self) -> tuple[str, ...]:
        # A session cannot silently change its context protocol.
        return (*super().identity, self.schema_version)


class ImportedReaderContext(ReaderStudyContext):
    """A local user-selected source, NOT authenticated Book activity or truth."""
    schema_version: Literal["mygpt.imported-reader-context.v1"] = "mygpt.imported-reader-context.v1"
    evidence_kind: Literal["USER_SUPPLIED_UNVERIFIED"] = "USER_SUPPLIED_UNVERIFIED"
    source_serialization: Literal["selected-source-json-v1"] = "selected-source-json-v1"

    @property
    def reference(self) -> str:
        return "unverified-import:v1:" + super().reference


def _legacy_context_tag(value):
    # Backward compatibility for original callers that omitted v1's default tag.
    # Explicit unknown tags never fall back to v1.
    if isinstance(value, dict) and "schema_version" not in value:
        return {"schema_version": "mygpt.study-context.v1", **value}
    return value


ContextValue = Annotated[
    StudyContext | ReaderStudyContext | ImportedReaderContext,
    Field(discriminator="schema_version"), BeforeValidator(_legacy_context_tag),
]
_CONTEXT = TypeAdapter(ContextValue)


def parse_context(value: dict | StudyContext | str) -> StudyContext | ReaderStudyContext:
    return _CONTEXT.validate_json(value) if isinstance(value, str) else _CONTEXT.validate_python(value)


class StudyEvent(Contract):
    schema_version: Literal["mygpt.study-event.v1"] = "mygpt.study-event.v1"
    event_id: Identifier
    producer_id: Literal["book-demo", "local-selection"] = "book-demo"
    session_id: Identifier
    sequence: Sequence
    occurred_at: AwareDatetime
    kind: Kind
    context: ContextValue | None = None

    @field_validator("occurred_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def check_context(self) -> StudyEvent:
        if (self.kind in CONTEXT_EVENTS) != (self.context is not None):
            raise ValueError("context is required only for start/change/resume")
        if self.context:
            expected = "local-selection" if isinstance(self.context, ImportedReaderContext) else "book-demo"
            if self.producer_id != expected:
                raise ValueError("context_producer_mismatch")
            if self.context.session_id != self.session_id:
                raise ValueError("context/session mismatch")
            if self.context.captured_at > self.occurred_at:
                raise ValueError("context cannot be captured after its event")
        return self


class Decision(Contract):
    action: Literal["stay_silent", "explain", "recall_check"] = "stay_silent"
    reason: str
    source_ref: str | None = None
    # A decision is a proposal, never evidence that a model was called.
    model_called: Literal[False] = False
    policy_version: Literal["quiet-explicit-v1"] = "quiet-explicit-v1"


class Receipt(Contract):
    event_id: str
    accepted: bool
    disposition: str
    decision: Decision


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def checked_now(value: datetime | None) -> datetime:
    now = value if value is not None else utc_now()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("clock must be timezone-aware")
    return now.astimezone(timezone.utc)


def canonical(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class Brain:
    """Single-user projection with durable deduplication and fail-closed gaps.

    One SQLite transaction commits an accepted event, its decision and state.
    A duplicate receives a silent receipt; it cannot retrigger an action.
    File databases use WAL. Separate instances serialize via BEGIN IMMEDIATE.
    """

    def __init__(self, database: str = ":memory:") -> None:
        self._lock = threading.RLock()
        self.db = sqlite3.connect(database, isolation_level=None, timeout=5,
                                  check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        try:
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            tables = {r[0] for r in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if version not in (0, 1) or (version == 0 and tables):
                raise ValueError("unsupported database; refusing automatic migration")
            if version == 0:
                with self._transaction():
                    self.db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
                    self.db.execute("""CREATE TABLE sessions (
                        id TEXT PRIMARY KEY, last_sequence INTEGER NOT NULL,
                        last_time TEXT NOT NULL, status TEXT NOT NULL,
                        quiet INTEGER NOT NULL, identity_json TEXT NOT NULL,
                        context_json TEXT)""")
                    self.db.execute("""CREATE TABLE events (
                        id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                        sequence INTEGER NOT NULL, fingerprint TEXT NOT NULL,
                        received_at TEXT NOT NULL, kind TEXT NOT NULL,
                        decision_json TEXT NOT NULL, UNIQUE(session_id, sequence))""")
                    self.db.execute("PRAGMA user_version=1")
            else:
                # Validate the existing shape before changing journal mode.
                self.db.execute("SELECT key,value FROM meta LIMIT 0")
                self.db.execute("SELECT id,last_sequence,last_time,status,quiet,"
                                "identity_json,context_json FROM sessions LIMIT 0")
                self.db.execute("SELECT id,session_id,sequence,fingerprint,received_at,"
                                "kind,decision_json FROM events LIMIT 0")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA busy_timeout=5000")
        except BaseException:
            self.db.close()
            raise

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self.db.close()

    def __enter__(self) -> Brain:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _reject(event: StudyEvent, reason: str) -> Receipt:
        return Receipt(event_id=event.event_id, accepted=False, disposition=reason,
                       decision=Decision(reason=reason))

    def ingest(self, value: StudyEvent | dict | str, *, now: datetime | None = None) -> Receipt:
        if isinstance(value, str):
            if len(value.encode("utf-8")) > 16384:
                raise ValueError("event exceeds 16 KiB")
            event = StudyEvent.model_validate_json(value)
        else:
            event = StudyEvent.model_validate(value)
        clock = checked_now(now)
        fingerprint = hashlib.sha256(canonical(event).encode()).hexdigest()
        with self._transaction():
            old = self.db.execute("SELECT fingerprint FROM events WHERE id=?",
                                  (event.event_id,)).fetchone()
            if old:
                return self._reject(event, "duplicate" if old[0] == fingerprint
                                    else "event_id_conflict")
            age = (clock - event.occurred_at).total_seconds()
            if age < -5:
                return self._reject(event, "future_event")
            if age > 300:
                return self._reject(event, "stale_event")
            if event.context and not (event.context.captured_at <= clock < event.context.expires_at):
                return self._reject(event, "invalid_context_time")
            row = self.db.execute("SELECT * FROM sessions WHERE id=?",
                                  (event.session_id,)).fetchone()
            active = self.db.execute("SELECT value FROM meta WHERE key='active'").fetchone()
            if event.kind == "SESSION_STARTED":
                if row is not None or event.sequence != 1:
                    return self._reject(event, "invalid_session_start")
                if active:
                    current = self.db.execute("SELECT last_time FROM sessions WHERE id=?",
                                              (active[0],)).fetchone()
                    if current and event.occurred_at < datetime.fromisoformat(current[0]):
                        return self._reject(event, "stale_session_start")
                assert event.context is not None
                status, quiet = "active", False
                identity = json.dumps(event.context.identity)
            else:
                if row is None:
                    return self._reject(event, "unknown_session")
                if active is None or active[0] != event.session_id:
                    return self._reject(event, "inactive_session")
                if row["status"] == "ended":
                    return self._reject(event, "session_ended")
                if event.sequence <= row["last_sequence"]:
                    return self._reject(event, "out_of_order")
                if event.sequence != row["last_sequence"] + 1:
                    self.db.execute("UPDATE sessions SET status='disconnected',context_json=NULL WHERE id=?",
                                    (event.session_id,))
                    return self._reject(event, "sequence_gap")
                if event.occurred_at < datetime.fromisoformat(row["last_time"]):
                    return self._reject(event, "time_reversal")
                if event.context and list(event.context.identity) != json.loads(row["identity_json"]):
                    return self._reject(event, "book_identity_mismatch")
                status, quiet, identity = row["status"], bool(row["quiet"]), row["identity_json"]
                if event.kind in ("CONTEXT_CHANGED", "HELP_REQUESTED", "RECALL_REQUESTED") and status != "active":
                    return self._reject(event, "session_not_active")
                if event.kind == "SESSION_RESUMED" and status not in ("paused", "disconnected"):
                    return self._reject(event, "invalid_resume")
                if event.kind == "SESSION_PAUSED" and status != "active":
                    return self._reject(event, "invalid_pause")
            context = event.context
            if context is None and row and row["context_json"]:
                context = parse_context(row["context_json"])
            if event.kind in CONTEXT_EVENTS:
                status = "active"
            elif event.kind == "SESSION_PAUSED":
                status, context = "paused", None
            elif event.kind == "DISCONNECTED":
                status, context = "disconnected", None
            elif event.kind == "SESSION_ENDED":
                status, context = "ended", None
            elif event.kind == "QUIET_REQUESTED":
                quiet = True
            if context and clock >= context.expires_at:
                context = None
            decision = Decision(reason="quiet_by_default")
            if event.kind in ("HELP_REQUESTED", "RECALL_REQUESTED"):
                if context is None:
                    decision = Decision(reason="fresh_context_required")
                else:
                    decision = Decision(action="explain" if event.kind == "HELP_REQUESTED" else "recall_check",
                                        reason="explicit_user_request", source_ref=context.reference)
            # Quiet mode suppresses proactive suggestions. Explicit help still works.
            self.db.execute("""INSERT INTO sessions VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET last_sequence=excluded.last_sequence,
                last_time=excluded.last_time,status=excluded.status,quiet=excluded.quiet,
                identity_json=excluded.identity_json,context_json=excluded.context_json""",
                (event.session_id, event.sequence, event.occurred_at.isoformat(), status,
                 int(quiet), identity, canonical(context) if context else None))
            self.db.execute("INSERT INTO meta VALUES ('active',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                            (event.session_id,))
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)",
                            (event.event_id, event.session_id, event.sequence, fingerprint,
                             clock.isoformat(), event.kind, canonical(decision)))
            return Receipt(event_id=event.event_id, accepted=True, disposition="accepted", decision=decision)

    def view(self, *, now: datetime | None = None) -> dict:
        clock = checked_now(now)
        with self._lock:
            row = self.db.execute("SELECT s.* FROM sessions s JOIN meta m ON m.value=s.id WHERE m.key='active'").fetchone()
            if row is None:
                return {"evidence_kind": "SIMULATED", "status": "no_session", "context": None,
                        "quiet": True, "host_state": "idle", "model_calls": 0}
            context = parse_context(row["context_json"]) if row["context_json"] else None
            status = row["status"]
            if context and not (context.captured_at <= clock < context.expires_at):
                context, status = None, "context_expired"
            if status == "active" and context is None:
                status = "context_unavailable"
            if status != "active":
                context = None
            evidence_kind = ("USER_SUPPLIED_UNVERIFIED"
                if "mygpt.imported-reader-context.v1" in json.loads(row["identity_json"]) else "SIMULATED")
            return {"evidence_kind": evidence_kind, "status": status, "session_id": row["id"],
                    "last_sequence": row["last_sequence"], "quiet": bool(row["quiet"]),
                    "context": context.model_dump(mode="json") if context else None,
                    "host_state": "blocked" if status in ("disconnected", "context_expired", "context_unavailable") else "idle",
                    "model_calls": 0}

    def recent_decisions(self, limit: int = 20) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit must be an integer in [1, 50]")
        with self._lock:
            rows = self.db.execute("SELECT id,session_id,kind,received_at,decision_json FROM events ORDER BY rowid DESC LIMIT ?",
                                   (limit,)).fetchall()
            return [{"event_id": r["id"], "session_id": r["session_id"], "kind": r["kind"],
                     "received_at": r["received_at"], "decision": json.loads(r["decision_json"])} for r in rows]
