"""Generated UI examples must match real Reader/Brain synthetic evidence."""
import hashlib
import json
from pathlib import Path

import pytest
from mygpt_brain import Brain, StudyEvent
from mygpt_brain.adapters import EvidenceText, validate_evidence, validate_reply
from mygpt_brain.core import parse_context
from mygpt_brain.host_fixtures import build_catalogue, render_module
from mygpt_brain.reader_demo import NOW


@pytest.mark.parametrize('entry_index', range(5))
@pytest.mark.parametrize('mode',['preview','learn','review','practice'])
def test_generated_entry_through_real_brain(entry_index,mode):
    catalogue=build_catalogue();entry=catalogue['entries'][entry_index]
    context=parse_context({**entry['context'],'mode':mode})
    evidence=EvidenceText(context=context,text=entry['evidence_text'])
    with Brain() as brain:
        assert brain.ingest(StudyEvent(event_id='start',session_id=context.session_id,
            sequence=1,occurred_at=NOW,kind='SESSION_STARTED',context=context),now=NOW).accepted
        assert validate_evidence(brain,evidence,now=NOW)==evidence
        help_event=StudyEvent(event_id='help',session_id=context.session_id,sequence=2,
            occurred_at=NOW,kind='HELP_REQUESTED')
        result=brain.ingest(help_event,now=NOW)
        assert result.decision.source_ref==entry['source_ref']
        assert result.decision.model_called is False
        assert validate_reply({'text':entry['fixture_reply'],'source_refs':[entry['source_ref']]},evidence)
        assert brain.ingest(help_event,now=NOW).disposition=='duplicate'
        assert entry['evidence_text'] not in '\n'.join(brain.db.iterdump())


def test_catalogue_is_exactly_generated_and_contains_no_live_claims():
    data=build_catalogue()
    assert render_module()==render_module()
    file=Path(__file__).resolve().parents[2]/'host/fixtures.js'
    assert file.read_text('utf-8')==render_module()
    assert data['scope']=='SYNTHETIC_FIXED_REPLAY'
    assert data['live_book_connected'] is False and data['model_calls']==0
    assert len(set(e['id'] for e in data['entries']))==5
    assert {e['context']['source_layer'] for e in data['entries']}=={'source','correction','derived'}
    for e in data['entries']:
        assert hashlib.sha256(e['evidence_text'].encode()).hexdigest()==e['context']['source_sha256']
        assert '预先编写的演示回复' in e['fixture_reply']
        assert json.loads(e['evidence_text'])['book_version_id']==e['context']['book_version']
