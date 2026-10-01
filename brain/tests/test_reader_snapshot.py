"""Contract/lifecycle regression; every source sentence here is synthetic."""
from copy import deepcopy
from datetime import timedelta, timezone
import hashlib
import json

import pytest
from pydantic import ValidationError

from mygpt_brain import Brain, StudyEvent
from mygpt_brain.adapters import EvidenceText, validate_evidence, validate_reply
from mygpt_brain.core import ReaderStudyContext, StudyContext, parse_context
from mygpt_brain.reader_snapshot import ReaderSnapshot, ReaderSelection, ReaderMappingError, map_reader_snapshot
from mygpt_brain.reader_demo import fixture, NOW, demo


def mapped(args=None, **kwargs):
    return map_reader_snapshot(*(args or fixture()), expected_session_id="demo-reader-session",
                               expected_epoch=1, now=NOW, **kwargs)


def correction_fixture():
    m, s, snap = fixture()
    r = s["records"][0]
    r["corrections"] = [{"id": "correction-1", "course_id": m["course_id"], "section_id": s["id"],
        "record_id": r["id"], "confidence": "HIGH", "presentation": "prefer_corrected",
        "status": "CHECKED_BY_ASSISTANT", "evidence_status": "SCOPED_EVIDENCE_CHECKED",
        "source_preserved": True, "check_ids": ["synthetic-check"],
        "original_title": r["title"], "original_parts": deepcopy(r["parts"]),
        "corrected_parts": [{"kind": "text", "text": "合成校正示例"}]}]
    snap["selection"].update(layer="correction", layer_id="correction-1")
    return m, s, snap


def derived_fixture():
    m, s, snap = fixture()
    s["practice_groups"] = [{"id": "group-1", "anchor_id": "record-1", "record_ids": ["record-1"],
        "title": "合成问题", "derived_guidance": {"textbook_official_solution": False,
        "source_record_ids": ["record-1"], "source_sections": ["section-1"],
        "hint_parts": [{"kind": "text", "text": "先合并同类项。"}],
        "solution_parts": [{"kind": "math", "latex": "x+x=2x", "display": True}],
        "qualification": "仅作演示"}}]
    snap["selection"].update(layer="derived", layer_id="group-1", portion="solution")
    return m, s, snap


def start(brain, evidence):
    ev = StudyEvent(event_id="start", session_id=evidence.context.session_id, sequence=1,
                    occurred_at=NOW, kind="SESSION_STARTED", context=evidence.context)
    assert brain.ingest(ev, now=NOW).accepted
    return ev


@pytest.mark.parametrize("mode", ["preview", "learn", "review", "practice"])
def test_observed_modes_feed_brain(mode):
    args = fixture();args[2]["mode"] = mode
    e = mapped(args)
    with Brain() as brain:
        start(brain, e)
        assert validate_evidence(brain, e, now=NOW) == e
        assert brain.view(now=NOW)["context"]["mode"] == mode
        assert brain.recent_decisions()[0]["decision"]["action"] == "stay_silent"


@pytest.mark.parametrize("version", ["mathematical_physics_equations_4e@dd824886902c6082",
                                    "functional_analysis_2e_jiang_sun@146e613d41bdc0b4", "v"*160])
def test_version_preserved_not_cleaned(version):
    m,s,snap=fixture()
    m["book_version_id"]=s["book_version_id"]=snap["selection"]["book_version_id"]=version
    e=mapped((m,s,snap))
    assert e.context.book_version == version
    assert parse_context(e.context.model_dump_json()) == e.context
    assert json.loads(e.text)["book_version_id"] == version


@pytest.mark.parametrize("value", ["v"*161, "version:1", "v/1", "../v", "v 1", "v\n1", "", "v%401", 1, True])
def test_version_boundary(value):
    m,s,snap=fixture();snap["selection"]["book_version_id"]=value
    with pytest.raises(ReaderMappingError): mapped((m,s,snap))


def test_v1_reference_and_omitted_tag_compatibility():
    e = mapped()
    fields=e.context.model_dump()
    for k in ("schema_version","source_kind","source_layer","layer_id","source_serialization"):
        fields.pop(k)
    fields["book_version"]="v1"
    old=StudyContext(**fields)
    assert old.reference == "book:demo-book:v1:section-1:record-1"
    assert isinstance(parse_context(fields),StudyContext)
    with pytest.raises(ValidationError): StudyContext(**{**fields,"book_version":"v1@abc"})
    new=ReaderStudyContext(**{**e.context.model_dump(),"book_version":"v1"})
    assert old.reference != new.reference
    with Brain() as b:
        start(b,EvidenceText(context=old,text=e.text))
        ev=StudyEvent(event_id="change",session_id=old.session_id,sequence=2,occurred_at=NOW,
                      kind="CONTEXT_CHANGED",context=new)
        assert b.ingest(ev,now=NOW).disposition=="book_identity_mismatch"


@pytest.mark.parametrize("tag", ["mygpt.reader-context.v99", "mygpt.study-context.v1", None])
def test_v2_cannot_be_downgraded_or_unknown_tag(tag):
    data=mapped().context.model_dump();data["schema_version"]=tag
    with pytest.raises(ValidationError): parse_context(data)


def test_v2_database_restart_and_no_raw_source_persistence(tmp_path):
    e=mapped();path=str(tmp_path/'brain.db')
    with Brain(path) as b: ev=start(b,e)
    with Brain(path) as b:
        assert b.ingest(ev,now=NOW).disposition=="duplicate"
        assert validate_evidence(b,e,now=NOW)==e
        dump='\n'.join(b.db.iterdump())
        assert "两个相同的量相加" not in dump
        assert e.context.reference not in dump # stored only when requesting help
        result=b.ingest(StudyEvent(event_id="help",session_id=e.context.session_id,sequence=2,
                      occurred_at=NOW,kind="HELP_REQUESTED"),now=NOW)
        assert result.decision.source_ref==e.context.reference


@pytest.mark.parametrize("mutation,code", [
    (lambda m,s,e:m.update(schema="other"),"unsupported_reader_pack"),
    (lambda m,s,e:m.update(course_id="other"),"course_mismatch"),
    (lambda m,s,e:s.update(book_version_id="other"),"book_version_mismatch"),
    (lambda m,s,e:m.update(book_version_id="other"),"book_version_mismatch"),
    (lambda m,s,e:s.update(id="elsewhere"),"section_mismatch"),
    (lambda m,s,e:m.update(sections=[]),"section_mismatch"),
    (lambda m,s,e:s.update(records=[]),"selected_record_missing"),
    (lambda m,s,e:s['records'][0].update(section_id="other"),"record_section_mismatch"),
    (lambda m,s,e:s['records'].append(deepcopy(s['records'][0])),"duplicate_identity"),
    (lambda m,s,e:m['sections'].append(deepcopy(m['sections'][0])),"duplicate_identity"),
    (lambda m,s,e:s.update(records=[None]),"expected_json_object"),
    (lambda m,s,e:s['records'][0].update(kind="a:b"),"unsupported_identifier"),
])
def test_identity_rejections(mutation,code):
    args=fixture();mutation(*args)
    with pytest.raises(ReaderMappingError,match='^'+code+'$'): mapped(args)


@pytest.mark.parametrize("value", [None, [], {}, {"record_id":"record-1"}])
def test_no_implicit_selection(value):
    args=fixture();args[2]["selection"]=value
    with pytest.raises(ReaderMappingError,match="invalid_reader_snapshot"): mapped(args)


@pytest.mark.parametrize("key,value", [("evidence_kind","BOOK"),("producer_id","book"),
    ("authenticated",True),("live_ready",True),("password","synthetic-secret"),
    ("epoch",True),("epoch",0),("epoch","1"),("schema_version","v99")])
def test_untrusted_host_claims_rejected(key,value):
    args=fixture();args[2][key]=value
    with pytest.raises(ReaderMappingError): mapped(args)


@pytest.mark.parametrize("session,epoch", [("old",1),("demo-reader-session",2),
                                         ("demo-reader-session",True),("demo-reader-session",0)])
def test_epoch_and_session_reject_stale_expected_state(session,epoch):
    with pytest.raises(ReaderMappingError):
        map_reader_snapshot(*fixture(),expected_session_id=session,expected_epoch=epoch,now=NOW)


@pytest.mark.parametrize("offset", [-1,120,200])
def test_freshness(offset):
    with pytest.raises(ReaderMappingError,match="snapshot_not_fresh"):
        map_reader_snapshot(*fixture(),expected_session_id="demo-reader-session",expected_epoch=1,
                            now=NOW+timedelta(seconds=offset))


def test_timezone_equivalent_snapshot_and_fixed_bytes():
    a=fixture();b=deepcopy(a)
    for key in ('captured_at','expires_at'):b[2][key]=b[2][key].astimezone(timezone(timedelta(hours=8)))
    assert mapped(a)==mapped(b)
    payload=json.loads(mapped(a).text)
    assert payload['parts'][1]=={'kind':'math','latex':'x+x=2x','display':True}
    assert hashlib.sha256(mapped(a).text.encode()).hexdigest()==mapped(a).context.source_sha256


@pytest.mark.parametrize("parts", [[],[{'kind':'image','url':'https://example.invalid'}],
    [{'kind':'text','text':'   '}],[{'kind':'math','latex':'','display':True}],
    [{'kind':'math','latex':'x','display':1}],[{'kind':'text','text':'x'*12001}],
    [{'kind':'text','text':'\ud800'}],[{'kind':'text','text':'\x00'}],
    [{'kind':'unknown','text':'x'}],[{'kind':'text','text':'x'}]*513])
def test_unsupported_body_not_guessed(parts):
    args=fixture();args[1]['records'][0]['parts']=parts
    with pytest.raises(ReaderMappingError):mapped(args)


def test_source_is_not_silently_display_corrected():
    args=correction_fixture();args[2]['selection'].update(layer='source',layer_id=None)
    r=args[1]['records'][0]
    r['parts'][0]['render_text']='different displayed text'
    r['source_completion']={'parts':[{'kind':'text','text':'other complete text'}]}
    r['assets']=[{'path':'private/figure.png'}]
    e=mapped(args);p=json.loads(e.text)
    assert p['parts'][0]['text']=='两个相同的量相加：'
    assert set(p['warnings'])=={'DISPLAY_MAY_USE_ANOTHER_LAYER','RENDER_TRANSFORMS_NOT_APPLIED','IMAGES_NOT_INCLUDED'}
    assert 'different displayed text' not in e.text and 'other complete text' not in e.text


def test_layers_have_distinct_references_and_labels():
    original=mapped();corrected=mapped(correction_fixture());derived=mapped(derived_fixture())
    assert len({e.context.reference for e in (original,corrected,derived)})==3
    assert corrected.context.source_layer=='correction'
    assert 'NOT_OFFICIAL_ERRATUM' in corrected.text
    assert 'NOT_TEXTBOOK_STANDARD_ANSWER' in derived.text
    assert json.loads(derived.text)['qualification']=='仅作演示'
    assert original.context.book_version==corrected.context.book_version==derived.context.book_version


@pytest.mark.parametrize("key,value", [('confidence','MEDIUM'),('source_preserved',False),
    ('record_id','other'),('course_id','other'),('section_id','other'),
    ('status','approved'),('evidence_status','unknown'),('original_title','changed'),
    ('original_parts',[]),('check_ids',[]),('corrected_parts',[]),('presentation','highlight')])
def test_correction_must_be_uniquely_bound(key,value):
    args=correction_fixture();args[1]['records'][0]['corrections'][0][key]=value
    with pytest.raises(ReaderMappingError):mapped(args)


def test_two_eligible_corrections_reject():
    args=correction_fixture();cs=args[1]['records'][0]['corrections']
    cs.append({**deepcopy(cs[0]),'id':'correction-2'})
    with pytest.raises(ReaderMappingError,match='correction_not_uniquely_source_bound'):mapped(args)


@pytest.mark.parametrize("part", ['hint','solution'])
def test_derived_requires_explicit_portion(part):
    args=derived_fixture();args[2]['selection']['portion']=part
    e=mapped(args)
    assert e.context.layer_id=='group-1-'+part
    assert json.loads(e.text)['portion']==part


@pytest.mark.parametrize("mutate", [
    lambda g:g.update(anchor_id='other'),lambda g:g.update(record_ids=['missing']),
    lambda g:g['derived_guidance'].update(source_record_ids=['missing']),
    lambda g:g['derived_guidance'].update(source_sections=['missing']),
    lambda g:g['derived_guidance'].update(textbook_official_solution=True),
    lambda g:g['derived_guidance'].update(solution_parts=[]),
])
def test_derived_binding_rejected(mutate):
    args=derived_fixture();mutate(args[1]['practice_groups'][0])
    with pytest.raises(ReaderMappingError):mapped(args)


def test_same_id_different_bytes_changes_reference():
    a=fixture();b=deepcopy(a);b[1]['records'][0]['parts'][0]['text']+='changed'
    assert mapped(a).context.reference!=mapped(b).context.reference


def test_no_extra_private_fields_or_input_mutation():
    args=fixture();args[0]['api_key']='secret-fixture';args[1]['notes']='private-fixture'
    args[1]['records'][0]['parts'][0]['private']='private-fixture'
    before=deepcopy(args);e=mapped(args)
    assert args==before
    assert 'secret-fixture' not in e.text and 'private-fixture' not in e.text


def test_context_switch_prevents_old_evidence_and_forged_citation():
    e=mapped()
    with Brain() as b:
        start(b,e)
        args=fixture();args[1]['records'][0]['parts'][0]['text']='new content'
        e2=mapped(args)
        assert b.ingest(StudyEvent(event_id='switch',session_id=e2.context.session_id,sequence=2,
                       occurred_at=NOW,kind='CONTEXT_CHANGED',context=e2.context),now=NOW).accepted
        with pytest.raises(ValueError):validate_evidence(b,e,now=NOW)
        with pytest.raises(ValueError):validate_reply({'text':'a','source_refs':[e.context.reference]},e2)


@pytest.mark.parametrize('kind',['SESSION_PAUSED','DISCONNECTED','SESSION_ENDED'])
def test_stop_event_invalidates_evidence(kind):
    e=mapped()
    with Brain() as b:
        start(b,e)
        b.ingest(StudyEvent(event_id='stop',session_id=e.context.session_id,sequence=2,
                           occurred_at=NOW,kind=kind),now=NOW)
        with pytest.raises(ValueError):validate_evidence(b,e,now=NOW)


def test_revalidate_mutated_nested_context():
    e=mapped();object.__setattr__(e.context,'source_layer','pretend-live')
    with pytest.raises(ValidationError):EvidenceText.model_validate(e)


def test_end_to_end_demo():
    result=demo();assert result==demo()
    assert result['help']['decision']['action']=='explain'
    assert result['duplicate']['decision']['action']=='stay_silent'
    assert result['paused']['context'] is None
    assert not result['live_book_connected'] and result['paid_model_calls']==0


def test_book_identity_must_match_selection():
    args=fixture();args[0]['book_id']='other-book'
    with pytest.raises(ReaderMappingError,match='book_identity_mismatch'):mapped(args)


def test_corrected_reference_also_binds_original_source():
    a=correction_fixture();b=deepcopy(a)
    b[1]['records'][0]['parts'][0]['text']='changed original'
    b[1]['records'][0]['corrections'][0]['original_parts']=deepcopy(b[1]['records'][0]['parts'])
    assert mapped(a).context.reference != mapped(b).context.reference
    assert json.loads(mapped(a).text)['parent_sources']!=json.loads(mapped(b).text)['parent_sources']


def test_derived_reference_also_binds_original_source():
    a=derived_fixture();b=deepcopy(a);b[1]['records'][0]['parts'][0]['text']='changed original'
    assert mapped(a).context.reference!=mapped(b).context.reference


@pytest.mark.parametrize('times',[(NOW,NOW),(NOW,NOW+timedelta(seconds=301)),
    (NOW.replace(tzinfo=None),NOW+timedelta(seconds=120))])
def test_snapshot_clock_shape(times):
    args=fixture();args[2]['captured_at'],args[2]['expires_at']=times
    with pytest.raises(ReaderMappingError,match='invalid_reader_snapshot'):mapped(args)
