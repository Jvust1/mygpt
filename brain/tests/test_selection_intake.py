"""Intake uses actual Brain with explicitly unverified input, never Book authority."""
import asyncio
import json
from types import SimpleNamespace
from datetime import timedelta
import pytest
from pydantic import ValidationError
from mygpt_brain import Brain, StudyEvent
from mygpt_brain.core import ImportedReaderContext, parse_context
from mygpt_brain.local_service import LocalBrainEngine, LocalServiceError
from mygpt_brain.selection_store import SelectionStore
from mygpt_brain.selection_packet import encode_packet
from test_selection_packet import packet
from test_reader_snapshot import correction_fixture, derived_fixture
from mygpt_brain.reader_demo import fixture, NOW

async def fixed(_brain, evidence, _question, text, _now):
    assert _brain.view(now=_now)['evidence_kind']=='USER_SUPPLIED_UNVERIFIED'
    return SimpleNamespace(text=text)

def engine(**kwargs):
    return LocalBrainEngine(clock=kwargs.pop('clock',lambda:NOW),monotonic=kwargs.pop('monotonic',lambda:10.),
        responder=kwargs.pop('responder',fixed),**kwargs)

def request(entry,mode='learn',identifier='input-1',end=None):
    return {'schema_version':'mygpt.local-explain.v1','scope':'LOCAL_UNVERIFIED_SELECTION',
        'request_id':identifier,'revision':1,'entry_id':entry['id'],'mode':mode,
        'source_ref':entry['source_ref'],'source_sha256':entry['context']['source_sha256'],
        'selection_expires_at_ms':end or int(NOW.timestamp()*1000)+60000}

@pytest.mark.asyncio
@pytest.mark.parametrize('factory',[fixture,correction_fixture,derived_fixture])
@pytest.mark.parametrize('mode',['preview','learn','review','practice'])
async def test_opt_in_packet_reaches_real_brain(factory,mode):
    e=engine(enable_selection_intake=True)
    value=packet(factory); obj=e.import_selection(encode_packet(value))
    entry=obj['entry']; result=await e.explain(request(entry,mode))
    assert result['brain_action']=='explain' and result['source_trust']=='USER_SUPPLIED_UNVERIFIED'
    assert result['source_ref'].startswith('unverified-import:v1:')
    assert result['mode']==mode and result['model_called'] is False and result['test_model'] is False
    assert e.status()['imports_active']==1
    assert e.revoke()['status']=='revoked' and e.status()['imports_active']==0


def test_default_off_rejects_import_without_loosening_original_protocol():
    e=engine()
    with pytest.raises(LocalServiceError,match='selection_intake_disabled'):
        e.import_selection(encode_packet(packet()))
    assert not e.status()['selection_intake_enabled']


def test_imported_context_cannot_masquerade_as_book_demo():
    e=engine(enable_selection_intake=True);entry=e.import_selection(encode_packet(packet()))['entry']
    ctx=parse_context(entry['context']); assert isinstance(ctx,ImportedReaderContext)
    with pytest.raises(ValidationError,match='context_producer_mismatch'):
        StudyEvent(event_id='start',session_id=ctx.session_id,sequence=1,kind='SESSION_STARTED',
                   occurred_at=NOW,context=ctx)
    data=ctx.model_dump();data['schema_version']='mygpt.reader-context.v2'
    with pytest.raises(ValidationError):parse_context(data)


def test_imported_context_storage_retains_trust_without_source_body(tmp_path):
    e=engine(enable_selection_intake=True);entry=e.import_selection(encode_packet(packet()))['entry']
    ctx=parse_context(entry['context']);path=str(tmp_path/'brain.db')
    with Brain(path) as brain:
        assert brain.ingest(StudyEvent(event_id='start',producer_id='local-selection',session_id=ctx.session_id,
            sequence=1,kind='SESSION_STARTED',occurred_at=NOW,context=ctx),now=NOW).accepted
        assert '两个相同' not in '\n'.join(brain.db.iterdump())
    with Brain(path) as brain:
        assert brain.view(now=NOW)['evidence_kind']=='USER_SUPPLIED_UNVERIFIED'
        brain.ingest(StudyEvent(event_id='pause',producer_id='local-selection',session_id=ctx.session_id,
            sequence=2,kind='SESSION_PAUSED',occurred_at=NOW),now=NOW)
        assert brain.view(now=NOW)['evidence_kind']=='USER_SUPPLIED_UNVERIFIED'
        assert brain.view(now=NOW)['context'] is None

@pytest.mark.asyncio
async def test_import_is_bound_to_current_service_not_a_global_id():
    a=engine(enable_selection_intake=True);b=engine(enable_selection_intake=True)
    entry=a.import_selection(encode_packet(packet()))['entry']
    with pytest.raises(LocalServiceError,match='import_missing_or_expired'):
        await b.explain(request(entry))

@pytest.mark.asyncio
async def test_import_scope_cannot_be_substituted():
    e=engine(enable_selection_intake=True);entry=e.import_selection(encode_packet(packet()))['entry']
    body=request(entry);body['scope']='SYNTHETIC_FIXED_REPLAY'
    with pytest.raises(LocalServiceError,match='unknown_entry'):await e.explain(body)

@pytest.mark.asyncio
async def test_import_expiry_cannot_be_extended_by_new_request_lease():
    wall=[NOW];mono=[10.]
    e=engine(clock=lambda:wall[0],monotonic=lambda:mono[0],enable_selection_intake=True)
    entry=e.import_selection(encode_packet(packet()))['entry']
    wall[0]+=timedelta(seconds=121);mono[0]+=121
    with pytest.raises(LocalServiceError,match='import_missing_or_expired'):
        await e.explain(request(entry,end=int(wall[0].timestamp()*1000)+120000))
    assert e.status()['imports_active']==0


def test_store_is_bounded_without_evicting_active_entries():
    store=SelectionStore(clock=lambda:NOW,monotonic=lambda:10.)
    for _ in range(16):store.add(encode_packet(packet()))
    with pytest.raises(ValueError,match='selection_capacity_exceeded'):store.add(encode_packet(packet()))
    assert store.count()==16
    store.clear();assert store.count()==0


def test_store_does_not_expose_mutable_entry_alias():
    store=SelectionStore(clock=lambda:NOW,monotonic=lambda:10.)
    entry=store.add(encode_packet(packet()));entry['evidence_text']='forged'
    retrieved=store.get(entry['id']);assert retrieved['evidence_text']!='forged'
    retrieved['context']['source_sha256']='a'*64
    assert store.get(entry['id'])['context']['source_sha256']!='a'*64

@pytest.mark.parametrize('wall_delta,mono',[(121,10.),(-1,10.),(0,131.),(0,9.)])
def test_store_expiry_and_backwards_clocks(wall_delta,mono):
    times=[NOW,10.];store=SelectionStore(clock=lambda:times[0],monotonic=lambda:times[1])
    store.add(encode_packet(packet()));times[:]=[NOW+timedelta(seconds=wall_delta),mono]
    assert store.count()==0

@pytest.mark.asyncio
async def test_default_testmodel_handles_imported_context(monkeypatch):
    pytest.importorskip('pydantic_ai',reason='real SDK unavailable; not an integration pass')
    from pydantic_ai import models
    monkeypatch.setattr(models,'ALLOW_MODEL_REQUESTS',False)
    e=LocalBrainEngine(clock=lambda:NOW,monotonic=lambda:10.,enable_selection_intake=True)
    entry=e.import_selection(encode_packet(packet()))['entry']
    result=await e.explain(request(entry))
    assert result['test_model'] is True and result['text'].startswith('[SIMULATED]')
    assert result['source_trust']=='USER_SUPPLIED_UNVERIFIED'
    assert '两个相同' not in result['text']  # fixed receipt, not generated teaching content
