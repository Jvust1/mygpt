"""Actual Pydantic AI TestModel through LocalBrainEngine; still synthetic/offline."""
import pytest
from mygpt_brain.host_fixtures import build_catalogue
from mygpt_brain.local_service import LocalBrainEngine
from test_local_service import NOW, request


@pytest.mark.asyncio
async def test_default_local_engine_runs_real_testmodel_without_provider(monkeypatch):
    pytest.importorskip("pydantic_ai", reason="SDK not installed; local Brain integration unverified")
    from pydantic_ai import models
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    engine = LocalBrainEngine(clock=lambda:NOW, monotonic=lambda:10.0)
    result = await engine.explain(request("a-correction"))
    entry = {x["id"]:x for x in build_catalogue()["entries"]}["a-correction"]
    assert result["text"] == entry["fixture_reply"]
    assert result["source_ref"] == entry["source_ref"]
    assert result["paid_model_calls"] == 0 and result["test_model"] is True
    assert engine.status()["responder_kind"] == "PYDANTIC_AI_TESTMODEL"
