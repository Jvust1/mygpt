"""Independent receiver tests using synthetic data and a capability test double."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
import pytest
from mygpt_brain.book_bridge import BookReceiver, BookReply, Lease, ReceiverError, SelectedContent, canonical

TOKEN='a'*64

class AuthorityDouble:
    def __init__(self):
        selection=dict(course_id='course',book_id='book',book_version_id='book@v1',section_id='section',
            record_id='record',layer='source',layer_id=None,portion='body',representation='display')
        self.payload=dict(schema='book.selected-content.v1',selection=selection,title='Synthetic fixture',
            parts=[{'kind':'text','text':'A synthetic source, not textbook content.'}],
            origin='SOURCE_TRANSCRIPTION_NOT_INDEPENDENTLY_CERTIFIED',
            parent_sources=[{'record_id':'record','source_parts_sha256':'1'*64}],warnings=[],
            qualification='BODY_ONLY_NO_IMAGES_NO_NOTES_NO_ANSWERS;INDEPENDENT_REVIEW_PENDING')
        self.ticket=dict(schema='book.selection-lease.v1',issuer_id='issuer',session_id='session',epoch=1,
            lease_id='lease',selection=deepcopy(selection),content_sha256=hashlib.sha256(canonical(self.payload)).hexdigest(),
            issued_at_ms=1800000000000,expires_at_ms=1800000090000,mac='2'*64)
        self.active=True;self.lock=threading.RLock();self.resolve_calls=0
    def status(self,token):
        if token!=TOKEN or not self.active:raise ReceiverError('AUTHORITY_INACTIVE')
        return {'active':True}
    def resolve(self,token,ticket):
        self.resolve_calls+=1;self.status(token)
        if ticket!=self.ticket:raise ReceiverError('TICKET_INACTIVE')
        return deepcopy(self.payload)
    def commit_current(self,token,ticket,commit):
        with self.lock:self.resolve(token,ticket);return commit()

@pytest.fixture
def setup():
    a=AuthorityDouble()
    def reply(context,payload,cancelled):return BookReply(text='Fixed test-double response.',source_ref=context.source_ref)
    return a,BookReceiver(a,responder=reply)

def test_new_live_contract_does_not_widen_legacy_simulated_protocol(setup):
    from mygpt_brain.core import parse_context
    a,r=setup;result=r.explain(TOKEN,a.ticket,'help-1')
    assert result['context']['evidence_kind']=='SYNTHETIC_TEST'
    assert result['context']['schema']=='mygpt.book-lease-context.v1'
    assert result['decision']['model_called'] is False
    with pytest.raises(ValueError):parse_context(result['context'])
    assert r.status()['persistent_source_text'] is False
    assert 'parts' not in canonical(result).decode()

def test_receiver_rechecks_authority_and_deduplicates_without_rerunning(setup):
    a,r=setup;first=r.explain(TOKEN,a.ticket,'help-1');before=a.resolve_calls
    assert r.explain(TOKEN,a.ticket,'help-1')==first
    assert a.resolve_calls>before and r.responder_invocations==1
    a.active=False
    with pytest.raises(ReceiverError):r.explain(TOKEN,a.ticket,'help-1')

@pytest.mark.parametrize('field,value',[('note','private'),('answers',{}),('provider','external'),('instruction','do something')])
def test_receiver_rejects_extra_source_fields(setup,field,value):
    a,r=setup;a.payload[field]=value
    with pytest.raises(ReceiverError):r.explain(TOKEN,a.ticket,'help-1')
    assert r.responder_invocations==0

def test_receiver_rejects_changed_payload_even_when_resolver_is_buggy(setup):
    a,r=setup;a.payload['parts'][0]['text']='tampered'
    with pytest.raises(ReceiverError,match='CONTENT_IDENTITY_MISMATCH'):r.explain(TOKEN,a.ticket,'help-1')
    assert r.responder_invocations==0

def test_receiver_requires_exact_selected_layer_and_parent(setup):
    a,r=setup;a.payload['parent_sources'][0]['record_id']='other'
    with pytest.raises(ReceiverError):r.explain(TOKEN,a.ticket,'help-1')
    assert r.responder_invocations==0

def test_receiver_never_accepts_forged_ticket_extra_fields(setup):
    a,r=setup;t=deepcopy(a.ticket);t['body']='secret'
    with pytest.raises(ReceiverError,match='INVALID_TICKET'):r.explain(TOKEN,t,'help-1')

@pytest.mark.parametrize('field,value',[('epoch',True),('expires_at_ms',1800000400000),('mac','bad')])
def test_receiver_ticket_types_and_ttl_are_closed(setup,field,value):
    a,r=setup;t=deepcopy(a.ticket);t[field]=value
    with pytest.raises(ReceiverError):r.explain(TOKEN,t,'help-1')

def test_cancel_before_explain_is_a_tombstone(setup):
    a,r=setup;r.cancel(TOKEN,'help-1')
    with pytest.raises(ReceiverError,match='CANCELLED'):r.explain(TOKEN,a.ticket,'help-1')
    assert r.responder_invocations==0

def test_cancel_after_reply_blocks_cached_delivery(setup):
    a,r=setup;r.explain(TOKEN,a.ticket,'help-1');r.cancel(TOKEN,'help-1')
    with pytest.raises(ReceiverError,match='CANCELLED'):r.explain(TOKEN,a.ticket,'help-1')

def test_conflicting_request_id_and_receipt_bound(setup):
    a,r=setup;r.explain(TOKEN,a.ticket,'help-1');t=deepcopy(a.ticket);t['epoch']=2
    with pytest.raises(ReceiverError,match='CONFLICT'):r.explain(TOKEN,t,'help-1')
    limited=BookReceiver(a,responder=lambda *x:None,receipt_capacity=1)
    limited.cancel(TOKEN,'one')
    with pytest.raises(ReceiverError,match='CAPACITY'):limited.cancel(TOKEN,'two')

@pytest.mark.parametrize('operation',['cancel','revoke'])
def test_inflight_result_does_not_publish_after_cancel_or_revoke(operation):
    a=AuthorityDouble();started=threading.Event();release=threading.Event()
    def delayed(context,payload,cancelled):
        started.set();assert release.wait(3)
        return BookReply(text='Late test reply',source_ref=context.source_ref)
    r=BookReceiver(a,responder=delayed)
    with ThreadPoolExecutor() as pool:
        task=pool.submit(r.explain,TOKEN,a.ticket,'slow')
        assert started.wait(3)
        if operation=='cancel':r.cancel(TOKEN,'slow')
        else:a.active=False
        release.set()
        with pytest.raises(ReceiverError):task.result()
    assert r.responder_invocations==1

def test_wrong_reply_reference_fails_and_is_not_retried(setup):
    a,_=setup
    r=BookReceiver(a,responder=lambda *args:BookReply(text='Wrong reference',source_ref='wrong'))
    with pytest.raises(ReceiverError,match='REPLY_SOURCE'):r.explain(TOKEN,a.ticket,'help-1')
    with pytest.raises(ReceiverError,match='FAILED'):r.explain(TOKEN,a.ticket,'help-1')
    assert r.responder_invocations==1

def test_book_receiver_default_uses_actual_testmodel():
    a=AuthorityDouble();r=BookReceiver(a)
    result=r.explain(TOKEN,a.ticket,'sdk-1')
    assert result['reply']['backend']=='PYDANTIC_AI_TESTMODEL'
    assert result['reply']['source_ref']==Lease.model_validate(a.ticket).reference
    assert result['reply']['teaching_quality_validated'] is False
    assert r.status()['responder_invocations']==1
    assert result['paid_provider_calls']==0

def test_alias_roundtrip_revalidates_instances_but_rejects_internal_wire_names():
    reply=BookReply(text='Fixed response',source_ref='source')
    assert BookReply.model_validate(reply).model_dump(mode='json')['schema']=='mygpt.book-lease-reply.v1'
    bad=reply.model_dump(mode='json');bad['wire_schema']=bad.pop('schema')
    with pytest.raises(ValueError):BookReply.validate_wire(bad)
