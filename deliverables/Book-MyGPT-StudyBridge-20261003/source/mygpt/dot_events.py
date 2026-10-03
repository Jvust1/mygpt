"""Bounded Book event preparation for the documented MCP 2.0 Events route.

This is NOT a running MCP server or a Codex dot connection. The authenticated
plugin host must implement subscriptions, persistent secret storage, verified
HTTPS callbacks and signing. No callback URL, token or endpoint is invented.
Never pass this outbox as DotPort: queuing is not receipt by the real dot.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Callable, Literal

from pydantic import AwareDatetime

from .book_progress import BookProgress, ProgressError
from .core import Contract, Identifier

EVENT_NAME = "book.study.progress.updated"
PROTOCOL_VERSION = "2026-07-28"
OFFICIAL_SOURCE = "https://developers.openai.com/plugins/build/mcp-events"


class SubscriptionArguments(Contract):
    producer_session: Identifier


class StudyEventData(Contract):
    progress: BookProgress


class StudyEvent(Contract):
    eventId: Identifier
    name: Literal["book.study.progress.updated"]
    timestamp: AwareDatetime
    data: StudyEventData
    cursor: None = None  # Ephemeral progress is not a replayable reading history.


def event_definition() -> dict:
    """Catalog data only; a host must not advertise events until implemented."""
    return {
        "name": EVENT_NAME,
        "description": "Current opt-in Book reading metadata or a stop/disable tombstone; not comprehension or instructions.",
        "delivery": ["webhook"],
        "inputSchema": SubscriptionArguments.model_json_schema(),
        "payloadSchema": StudyEventData.model_json_schema(by_alias=True),
    }


def _wire(p: BookProgress) -> str:
    return json.dumps(p.wire(), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _context(p: BookProgress):
    c = p.context
    return (p.producer_session, c.book_id, c.document_id, c.chapter, c.mode,
            c.source_sha256, p.status, p.can_interact) if c else (
                p.producer_session, p.status, p.can_interact)


def _event(p: BookProgress) -> StudyEvent:
    identity = hashlib.sha256(_wire(p).encode("utf-8")).hexdigest()[:40]
    event = StudyEvent.model_validate({
        "eventId": "study-" + identity, "name": EVENT_NAME,
        "timestamp": p.captured_at, "data": {"progress": p.wire()}, "cursor": None,
    })
    if len(json.dumps(event.model_dump(mode="json", by_alias=True),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")) > 8192:
        raise ProgressError("Book event exceeds the local 8192-byte limit")
    return event


class BookStudyEventOutbox:
    """One latest state plus one coalesced event; no network, model or history.

    Context/status changes are immediately eligible. Routine same-chapter
    progress is capped at one event per interval, even if Book saves frequently.
    The real plugin must re-read current state before executing a dot decision.
    Event receipt (HTTP 2xx) does not authorize speech or prove a dot decision.
    """

    def __init__(self, *, clock: Callable[[], datetime] | None = None,
                 interval_seconds: int = 30):
        if type(interval_seconds) is not int or not 5 <= interval_seconds <= 300:
            raise ValueError("event interval must be in 5..300 seconds")
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.interval_seconds = interval_seconds
        self.latest: BookProgress | None = None
        self._pending: StudyEvent | None = None
        self._due_at: datetime | None = None
        self._last_ack_at: datetime | None = None
        self._fingerprint = ""

    def clear(self):
        self.latest = self._pending = self._due_at = None
        self._last_ack_at = None
        self._fingerprint = ""

    def _fresh(self, p: BookProgress):
        now = self.clock()
        if p.captured_at > now or p.expires_at <= now:
            raise ProgressError("expired or future Book event")

    def offer(self, value: BookProgress | dict) -> dict:
        try:
            p = BookProgress.model_validate(value.wire() if isinstance(value, BookProgress) else value)
            self._fresh(p)
        except ValueError:
            self.clear()
            raise
        fingerprint = _wire(p)
        old = self.latest
        if old and old.producer_session == p.producer_session:
            if p.sequence < old.sequence:
                return {"status": "stale_ignored"}
            if p.sequence == old.sequence:
                if fingerprint != self._fingerprint:
                    raise ProgressError("Book event sequence conflict")
                return {"status": "duplicate_ignored"}
        # Do not mutate retained state if encoding fails.
        pending = _event(p)
        changed = old is None or _context(old) != _context(p)
        previous_due = self._due_at if self._pending is not None else None
        self.latest, self._fingerprint, self._pending = p, fingerprint, pending
        now = self.clock()
        if changed or self._last_ack_at is None:
            self._due_at = now
        else:
            routine_due = max(now, self._last_ack_at + timedelta(seconds=self.interval_seconds))
            self._due_at = min(previous_due, routine_due) if previous_due else routine_due
        return {"status": "queued_not_delivered", "model_called": False}

    def current(self) -> dict | None:
        if self.latest is None:
            return None
        try:
            self._fresh(self.latest)
        except ProgressError:
            self.clear()
            return None
        return self.latest.wire()

    def next_event(self, arguments: dict) -> dict | None:
        args = SubscriptionArguments.model_validate(arguments)
        if self.current() is None or self._pending is None:
            return None
        if args.producer_session != self.latest.producer_session:
            return None
        if self._due_at is None or self.clock() < self._due_at:
            return None
        # Return a detached copy; retries preserve the exact eventId/body.
        return self._pending.model_dump(mode="json", by_alias=True)

    def callback_received(self, event_id: str) -> dict:
        """Call ONLY after an actual signed/verified callback receives 2xx.

        A late receipt must not remove a newer queued event or tombstone.
        This local record is not a dot decision or Live presentation receipt.
        """
        if self._pending is None or self._pending.eventId != event_id:
            return {"status": "superseded_receipt_ignored", "dot_decision_observed": False}
        self._pending = self._due_at = None
        self._last_ack_at = self.clock()
        return {"status": "callback_received_not_decided", "dot_decision_observed": False}

