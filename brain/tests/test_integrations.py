"""Optional SDK checks: a skip is NOT an integration pass."""
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
        reply = await run_test_model(brain, EvidenceText(context=context(), text=TEXT), "explain", now=NOW)
        assert reply.source_refs == [context().reference]
        assert reply.text.startswith("[SIMULATED]")


@pytest.mark.asyncio
async def test_mcp_in_memory_read_only():
    pytest.importorskip("mcp", reason="optional SDK not installed; integration unverified")
    from mcp import Client
    with Brain() as brain:
        brain.ingest(event(), now=NOW)
        server = make_mcp_server(brain, clock=lambda: NOW)
        async with Client(server) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools} == {
                "get_study_status", "get_current_context", "get_recent_decisions"}
            result = await client.call_tool("get_current_context", {})
            assert result.structured_content["evidence_kind"] == "SIMULATED"
            assert result.structured_content["context"]["section_id"] == "section-1"
        assert brain.view(now=NOW)["last_sequence"] == 1
