"""Real SDKs, synthetic Reader data. Skips never count as integration acceptance."""
import asyncio
import pytest

from mygpt_brain import Brain
from mygpt_brain.adapters import make_mcp_server, run_test_model
from test_reader_snapshot import NOW, mapped, fixture, correction_fixture, derived_fixture, start


@pytest.mark.asyncio
@pytest.mark.parametrize('factory', [fixture, correction_fixture, derived_fixture])
async def test_reader_v2_testmodel_and_mcp_preserve_identity(factory, monkeypatch):
    pytest.importorskip('pydantic_ai', reason='SDK not installed; Reader integration unverified')
    pytest.importorskip('mcp', reason='SDK not installed; Reader integration unverified')
    from pydantic_ai import models
    from mcp import Client
    monkeypatch.setattr(models, 'ALLOW_MODEL_REQUESTS', False)
    evidence=mapped(factory())
    with Brain() as brain:
        start(brain,evidence)
        reply=await asyncio.wait_for(run_test_model(brain,evidence,'解释这段合成内容',now=NOW),10)
        assert reply.source_refs==[evidence.context.reference]
        assert reply.text.startswith('[SIMULATED]')
        async with asyncio.timeout(15), Client(make_mcp_server(brain,clock=lambda:NOW)) as client:
            result=await client.call_tool('get_current_context',{})
            ctx=result.structured_content['context']
            assert ctx['schema_version']=='mygpt.reader-context.v2'
            assert ctx['source_layer']==evidence.context.source_layer
            assert ctx['book_version']==evidence.context.book_version
            assert ctx['source_sha256']==evidence.context.source_sha256
        assert brain.view(now=NOW)['model_calls']==0
