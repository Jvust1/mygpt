"""Pure engine tests for the loopback milestone; no socket or provider access."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from mygpt_brain.host_fixtures import build_catalogue
from mygpt_brain.local_service import LocalBrainEngine, LocalServiceError, MAX_REQUESTS

NOW = datetime(2026, 9, 23, 3, 0, tzinfo=timezone.utc)


def request(entry_id="a-source", request_id="req-1", mode="learn", *, offset_ms=120000):
    entry = {x["id"]: x for x in build_catalogue()["entries"]}[entry_id]
    return {
        "schema_version": "mygpt.local-explain.v1",
        "scope": "SYNTHETIC_FIXED_REPLAY",
        "request_id": request_id,
        "revision": 1,
        "entry_id": entry_id,
        "mode": mode,
        "source_ref": entry["source_ref"],
        "source_sha256": entry["context"]["source_sha256"],
        "selection_expires_at_ms": int(NOW.timestamp()*1000)+offset_ms,
    }


def engine(**kwargs):
    async def responder(_brain, _evidence, _question, fixture_text, _now):
        return SimpleNamespace(text=fixture_text)
    return LocalBrainEngine(clock=lambda: NOW, monotonic=lambda: 10.0, responder=responder, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("entry_id", ["a-source", "a-correction", "a-hint", "a-solution", "b-source"])
@pytest.mark.parametrize("mode", ["preview", "learn", "review", "practice"])
async def test_all_fixture_layers_and_modes_run_real_brain_policy(entry_id, mode):
    e = engine()
    result = await e.explain(request(entry_id, f"req-{entry_id}-{mode}", mode))
    entry = {x["id"]: x for x in build_catalogue()["entries"]}[entry_id]
    assert result["source_ref"] == entry["source_ref"]
    assert result["source_sha256"] == entry["context"]["source_sha256"]
    assert result["brain_action"] == "explain"
    assert result["text"] == entry["fixture_reply"]
    assert result["test_model"] is False and result["model_called"] is False
    assert e.status()["requests_completed"] == 1
    assert e.status()["test_model"] is False and e.status()["responder_kind"] == "INJECTED_TEST_FIXTURE"


@pytest.mark.asyncio
async def test_identical_request_id_replays_cached_result_without_second_responder_call():
    calls = 0
    async def responder(_brain, _evidence, _question, fixture_text, _now):
        nonlocal calls; calls += 1; return SimpleNamespace(text=fixture_text)
    e = LocalBrainEngine(clock=lambda: NOW, monotonic=lambda: 10.0, responder=responder)
    body = request()
    first = await e.explain(body)
    second = await e.explain(body)
    assert calls == 1
    assert first["replayed"] is False and second["replayed"] is True
    assert first["text"] == second["text"]


@pytest.mark.asyncio
async def test_conflicting_request_id_is_rejected_not_reused():
    e = engine(); await e.explain(request())
    other = request(entry_id="b-source")
    with pytest.raises(LocalServiceError, match="request_id_conflict") as caught:
        await e.explain(other)
    assert caught.value.status == 409
    assert e.status()["request_conflicts"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value,code", [
    ("entry_id", "missing", "unknown_entry"),
    ("source_ref", "reader:v2:forged", "source_identity_mismatch"),
    ("source_sha256", "a"*64, "source_identity_mismatch"),
    ("selection_expires_at_ms", int(NOW.timestamp()*1000), "selection_expired_or_unbounded"),
    ("selection_expires_at_ms", int(NOW.timestamp()*1000)+301000, "selection_expired_or_unbounded"),
])
async def test_identity_and_lease_fail_closed(field, value, code):
    e=engine(); body=request(); body[field]=value
    with pytest.raises(LocalServiceError, match=code): await e.explain(body)


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("scope", "LIVE"), ("revision", 0), ("revision", True), ("mode", "focus"),
    ("request_id", "../bad"), ("selection_expires_at_ms", "123"),
    ("schema_version", "v99"), ("api_key", "fixture-secret"),
])
async def test_request_schema_rejects_untrusted_extensions(field, value):
    e=engine(); body=request(); body[field]=value
    with pytest.raises(LocalServiceError, match="invalid_explain_request"):
        await e.explain(body)


@pytest.mark.asyncio
async def test_cancel_during_demo_delay_prevents_model_path():
    calls = 0
    async def responder(*_args):
        nonlocal calls; calls += 1; return SimpleNamespace(text="should not happen")
    e=LocalBrainEngine(clock=lambda:NOW,monotonic=lambda:10.0,responder=responder,demo_delay_ms=200)
    task=asyncio.create_task(e.explain(request()))
    await asyncio.sleep(0.02)
    assert e.cancel("req-1")["status"] == "cancelled"
    with pytest.raises(LocalServiceError, match="request_cancelled"): await task
    assert calls == 0
    assert e.status()["requests_cancelled"] == 1


@pytest.mark.asyncio
async def test_cancel_during_async_responder_discards_returned_result():
    started=asyncio.Event()
    async def responder(_brain,_evidence,_question,fixture_text,_now):
        started.set(); await asyncio.sleep(0.05); return SimpleNamespace(text=fixture_text)
    e=LocalBrainEngine(clock=lambda:NOW,monotonic=lambda:10.0,responder=responder)
    task=asyncio.create_task(e.explain(request()))
    await started.wait(); e.cancel("req-1")
    with pytest.raises(LocalServiceError, match="request_cancelled"): await task
    assert e.status()["requests_completed"] == 0


@pytest.mark.asyncio
async def test_revoke_cancels_running_and_blocks_future_requests():
    e=engine(demo_delay_ms=200)
    task=asyncio.create_task(e.explain(request()))
    await asyncio.sleep(0.02)
    assert e.revoke()["status"] == "revoked"
    with pytest.raises(LocalServiceError, match="request_cancelled"): await task
    assert e.status()["authorized"] is False and e.status()["revoked"] is True
    with pytest.raises(LocalServiceError, match="authorization_revoked_or_expired"):
        await e.explain(request(request_id="req-2"))


def test_authorization_uses_monotonic_deadline_and_no_token_is_in_status():
    mono=[10.0]
    e=LocalBrainEngine(clock=lambda:NOW,monotonic=lambda:mono[0],authorization_seconds=60,
                       responder=lambda *_: None)
    assert e.status()["authorized"] is True
    mono[0]=70.0
    assert e.status()["authorized"] is False
    assert "token" not in " ".join(e.status()).lower()


@pytest.mark.asyncio
async def test_capacity_is_bounded_without_evicting_receipts():
    e=engine()
    for i in range(MAX_REQUESTS):
        await e.explain(request(request_id=f"r-{i}"))
    with pytest.raises(LocalServiceError, match="request_capacity_exceeded"):
        await e.explain(request(request_id="overflow"))
    assert e.status()["requests_completed"] == MAX_REQUESTS


def test_cancel_unknown_is_bounded_and_does_not_create_record():
    e=engine()
    assert e.cancel("never-seen")["status"] == "unknown_request"
    assert e.status()["requests_started"] == 0
