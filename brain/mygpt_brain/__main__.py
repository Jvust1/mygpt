"""Run a deterministic, no-network demonstration: python -m mygpt_brain."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from .core import Brain, StudyContext, StudyEvent


def demo() -> list[dict]:
    now = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
    context = StudyContext(session_id="demo-session", course_id="demo-course", book_id="demo-book",
                           book_version="v1", section_id="section-1", source_id="source-1",
                           source_sha256=hashlib.sha256(b"SIMULATED: x + x = 2x.").hexdigest(),
                           mode="learn", captured_at=now, expires_at=now + timedelta(seconds=120))
    outputs = []
    with Brain() as brain:
        kinds = ["SESSION_STARTED", "QUIET_REQUESTED", "HELP_REQUESTED", "SESSION_PAUSED",
                 "SESSION_RESUMED", "RECALL_REQUESTED", "SESSION_ENDED"]
        for sequence, kind in enumerate(kinds, 1):
            event = StudyEvent(event_id=f"demo-{sequence}", session_id=context.session_id,
                               sequence=sequence, occurred_at=now, kind=kind,
                               context=context if kind in ("SESSION_STARTED", "SESSION_RESUMED") else None)
            receipt = brain.ingest(event, now=now)
            outputs.append({"evidence_kind": "SIMULATED", "kind": kind,
                            "receipt": receipt.model_dump(mode="json"), "view": brain.view(now=now)})
            if kind == "HELP_REQUESTED":
                outputs.append({"evidence_kind": "SIMULATED", "kind": "DUPLICATE_HELP",
                                "receipt": brain.ingest(event, now=now).model_dump(mode="json")})
    return outputs


if __name__ == "__main__":
    for item in demo():
        print(json.dumps(item, ensure_ascii=False, sort_keys=True))
