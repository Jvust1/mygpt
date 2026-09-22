"""Optional SDK checks: a skip is NOT an integration pass."""
import asyncio
from datetime import timedelta
import pytest
from mygpt_brain import Brain
from mygpt_brain.adapters import EvidenceText, make_mcp_server, run_test_model
from test_core import NOW, TEXT, context, event


@pytest.mark.asyncio
async def test_pydantic_ai_test_model_only(monkeypatch):
    pytest.importorskip("pydantic_ai", reason="optional SDK not installed; integration unverified")
    from pydantic_ai import models
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    with Brain() as brain:
        brain.ingest(event(), now=NOW)
        reply = await asyncio.wait_for(
            run_test_model(brain, EvidenceText(context=context(), text=TEXT), "explain", now=NOW), timeout=10)
        assert reply.source_refs == [context().reference]
        assert reply.text.startswith("[SIMULATED]")


@pytest.mark.asyncio
async def test_mcp_in_memory_read_only():
    pytest.importorskip("mcp", reason="optional SDK not installed; integration unverified")
    from mcp import Client
    with Brain() as brain:
        brain.ingest(event(), now=NOW)
        clock = [NOW]
        server = make_mcp_server(brain, clock=lambda: clock[0])
        async with asyncio.timeout(15), Client(server) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools} == {
                "get_study_status", "get_current_context", "get_recent_decisions"}
            result = await client.call_tool("get_current_context", {})
            assert result.structured_content["evidence_kind"] == "SIMULATED"
            assert result.structured_content["context"]["section_id"] == "section-1"
            status = await client.call_tool("get_study_status", {})
            assert status.structured_content["status"] == "active"
            traces = await client.call_tool("get_recent_decisions", {"limit": 1})
            assert traces.content  # list output encoding is SDK-owned
            clock[0] = NOW + timedelta(seconds=121)
            stale = await client.call_tool("get_current_context", {})
            assert stale.structured_content["context"] is None
            assert stale.structured_content["status"] == "context_expired"
        assert brain.view(now=NOW)["last_sequence"] == 1
        assert len(brain.recent_decisions()) == 1
