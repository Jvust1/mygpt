#!/usr/bin/env python3
"""Synthetic growth gate; no network/provider, migration purge or auto-memory.

Run in the project's locked Python environment. Full IDs stay in the public
result, so elapsed work/peak memory are not claimed to be constant. This gate
measures new durable storage and retained runtime cache entries only.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import platform
import resource
import sqlite3
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "brain"))
from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.memory_store import MemoryStore
from mygpt_brain.session_store import ChatSessionStore

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
PERSONA = CompanionPersona(persona_id="audit-persona", display_name="Synthetic audit",
                           visual_skin_id="synthetic-skin", instructions="Synthetic audit only.")


async def probe(directory: Path, rounds: int, many_sessions: bool) -> dict:
    started = time.monotonic()
    path = directory / f"{many_sessions}-{rounds}.sqlite3"
    calls = max_provider_rows = 0
    def body(index):
        return dict(request_id=f"request-{index:06}",
                    session_id=f"session-{index:06}" if many_sessions else "session-long",
                    persona_id=PERSONA.persona_id, text="synthetic question")
    async def responder(prompt):
        nonlocal calls, max_provider_rows
        calls += 1
        max_provider_rows = max(max_provider_rows, len(prompt.provider_messages()))
        return "synthetic reply"
    with ChatSessionStore(path) as store, MemoryStore() as memory:
        runtime = CompanionChatRuntime(persona=PERSONA, responder=responder, session_store=store,
                                       memory_store=memory, recent_turn_limit=20)
        for index in range(1, rounds + 1):
            result = await runtime.send(body(index), now=NOW + timedelta(seconds=index))
            assert runtime._sessions == runtime._requests == {}
        metrics = {
            "kind": "many_sessions_one_turn_each" if many_sessions else "single_session",
            "turns": rounds, "sessions_cache_keys": len(runtime._sessions),
            "sessions_cached_messages_total": sum(map(len, runtime._sessions.values())),
            "requests_cache_keys": len(runtime._requests),
            "cached_results_compacted_ids_total": sum(len(r.compacted_message_ids) for _, r in runtime._requests.values()),
            "last_result_compacted_ids": len(result.compacted_message_ids),
            "max_provider_rows": max_provider_rows,
            "sqlite_receipt_rows": store._db.execute("SELECT COUNT(*) FROM chat_request_receipts").fetchone()[0],
            "sqlite_message_rows": store._db.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0],
            "sqlite_receipt_payload_total_bytes": store._db.execute(
                "SELECT SUM(length(CAST(result_json AS BLOB))+COALESCE(length(CAST(compacted_prefix_json AS BLOB)),0)) FROM chat_request_receipts"
            ).fetchone()[0],
            "prefix_encoded_receipts": store._db.execute(
                "SELECT COUNT(*) FROM chat_request_receipts WHERE compacted_prefix_json IS NOT NULL"
            ).fetchone()[0],
            "explicit_memory_rows": len(memory.recent(namespace=PERSONA.persona_id)),
        }
        assert metrics["sqlite_receipt_rows"] == rounds
        assert metrics["sqlite_message_rows"] == (3 * rounds if many_sessions else 2 * rounds + 1)
        assert max_provider_rows <= 20 and metrics["explicit_memory_rows"] == 0
        for index in (1, rounds // 2, rounds):
            replay = await runtime.send(body(index), now=NOW)
            assert replay.replayed and calls == rounds
            if index == rounds:
                assert replay.model_dump(mode="json") == dict(result.model_dump(mode="json"), replayed=True)
        metrics["warm_replay_first_middle_last"] = True
        try:
            await runtime.send(dict(body(1), text="conflict"), now=NOW)
        except ValueError as error:
            assert str(error) == "request_id conflict"
        else:
            raise AssertionError("same-ID conflict was accepted")
        metrics["warm_conflict_rejected"] = True
    metrics["sqlite_closed_file_bytes"] = path.stat().st_size
    with ChatSessionStore(path) as store, MemoryStore() as memory:
        restarted = CompanionChatRuntime(persona=PERSONA, responder=responder, session_store=store,
                                         memory_store=memory, recent_turn_limit=20)
        for index in (1, rounds // 2, rounds):
            replay = await restarted.send(body(index), now=NOW)
            assert replay.replayed and calls == rounds
            if index == rounds:
                assert replay.model_dump(mode="json") == dict(result.model_dump(mode="json"), replayed=True)
        metrics["cold_replay_first_middle_last"] = True
        assert restarted._sessions == restarted._requests == {}
    metrics["elapsed_seconds"] = round(time.monotonic() - started, 3)
    # Linux process high-water mark, cumulative across probes, not retained cache
    # size or an isolation/performance acceptance claim.
    metrics["process_peak_rss_kib_cumulative"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return metrics


async def main(args):
    implementation_paths = (ROOT / "brain/mygpt_brain/companion_chat.py", ROOT / "brain/mygpt_brain/session_store.py")
    implementation_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in implementation_paths}
    results = []
    with TemporaryDirectory(prefix="mygpt-receipt-growth-") as directory:
        for many in (False, True):
            for rounds in args.rounds:
                metrics = await probe(Path(directory), rounds, many)
                results.append(metrics)
                print(json.dumps(metrics), file=sys.stderr, flush=True)
    growth = []
    for many in ("single_session", "many_sessions_one_turn_each"):
        selected = [row for row in results if row["kind"] == many]
        for before, after in zip(selected, selected[1:]):
            factor = after["turns"] / before["turns"]
            ratio = after["sqlite_closed_file_bytes"] / before["sqlite_closed_file_bytes"]
            payload_ratio = after["sqlite_receipt_payload_total_bytes"] / before["sqlite_receipt_payload_total_bytes"]
            # Generous overhead margin, still excludes near-quadratic growth.
            assert ratio <= factor * 1.5 and payload_ratio <= factor * 1.5
            growth.append({"kind": many, "turn_factor": factor, "db_factor": round(ratio, 4),
                           "receipt_payload_factor": round(payload_ratio, 4)})
    manifest = ROOT / "SOURCE_MANIFEST.json"
    report = {
        "base_source_commit": json.loads(manifest.read_text())["source_commit"] if manifest.exists() else None,
        "working_tree_candidate": True,
        "implementation_sha256": implementation_hashes,
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "synthetic_only": True, "network_model_calls": 0, "accepted": True,
        "retention_policy_complete": False, "results": results, "growth": growth,
    }
    assert implementation_hashes == {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                     for path in implementation_paths}, "implementation changed during probe"
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        with args.output.open("x") as out:
            out.write(text)
    print(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, nargs="+", default=[1000, 10000])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.rounds or args.rounds != sorted(set(args.rounds)) or min(args.rounds) < 2:
        parser.error("rounds must be unique increasing integers >=2")
    asyncio.run(main(args))
