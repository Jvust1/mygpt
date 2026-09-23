"""Build the browser's fixed replay catalogue using the actual Reader mapper.

Synthetic examples only. This file never starts a server, calls a provider, or
reads Book files. Frozen fixture time is not the browser's live selection lease.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path

from .adapters import validate_evidence
from .core import Brain, StudyEvent
from .reader_demo import fixture, NOW
from .reader_snapshot import map_reader_snapshot


def build_catalogue() -> dict:
    manifest, section, snapshot = fixture()
    record = section['records'][0]
    record['title'] = '合成练习 A · 合并同类项'
    record['corrections'] = [{
        'id': 'correction-1', 'course_id': manifest['course_id'],
        'section_id': section['id'], 'record_id': record['id'],
        'confidence': 'HIGH', 'presentation': 'prefer_corrected',
        'status': 'CHECKED_BY_ASSISTANT', 'evidence_status': 'SCOPED_EVIDENCE_CHECKED',
        'source_preserved': True, 'check_ids': ['synthetic-display-check'],
        'original_title': record['title'], 'original_parts': deepcopy(record['parts']),
        'corrected_parts': [{'kind': 'text', 'text': '把系数相加，字母部分保持不变。'},
                            {'kind': 'math', 'latex': '(1+1)x=2x', 'display': True}],
    }]
    section['practice_groups'] = [{
        'id': 'group-1', 'anchor_id': record['id'], 'record_ids': [record['id']],
        'title': '合成练习 A · 思考提示与推导',
        'derived_guidance': {
            'textbook_official_solution': False, 'source_record_ids': [record['id']],
            'source_sections': [section['id']],
            'hint_parts': [{'kind': 'text', 'text': '把两个 x 看作两份相同的量。'}],
            'solution_parts': [{'kind': 'math', 'latex': 'x+x=(1+1)x=2x', 'display': True}],
            'qualification': '人为编写的合成演示，非教材标准答案。',
        },
    }]
    section['records'].append({
        'id': 'record-2', 'section_id': section['id'], 'kind': 'paragraph',
        'title': '合成练习 B · 平方展开', 'assets': [],
        'parts': [{'kind': 'text', 'text': '平方与分别平方后相加不相同：'},
                  {'kind': 'math', 'latex': '(x+1)^2=x^2+2x+1', 'display': True}],
    })
    selections = [
        ('a-source', '练习 A · 原文层', 'record-1', 'source', None, 'body',
         '这是预先编写的演示回复：两个 x 是两份相同的量，因此相加得到 2x。'),
        ('a-correction', '练习 A · 校正层', 'record-1', 'correction', 'correction-1', 'body',
         '这是预先编写的演示回复：当前选择的是合成校正层。系数 1 与 1 相加得到 2，字母部分 x 不变；这不是官方勘误。'),
        ('a-hint', '练习 A · 推导提示', 'record-1', 'derived', 'group-1', 'hint',
         '这是预先编写的演示回复：先想象两份相同的量。此处只回放提示，不自动展开解答。'),
        ('a-solution', '练习 A · 推导解答', 'record-1', 'derived', 'group-1', 'solution',
         '这是预先编写的演示回复：把公共的 x 提出来，得到 (1+1)x，再合并系数为 2x。此内容不是教材标准答案。'),
        ('b-source', '练习 B · 原文层', 'record-2', 'source', None, 'body',
         '这是预先编写的演示回复：(x+1)(x+1) 展开包含两项 x，因此中间项是 2x，不能漏掉。'),
    ]
    entries = []
    for key, label, rid, layer, layer_id, portion, reply in selections:
        snap = deepcopy(snapshot)
        snap['selection'].update(record_id=rid, layer=layer, layer_id=layer_id, portion=portion)
        evidence = map_reader_snapshot(manifest, section, snap,
            expected_session_id=snap['session_id'], expected_epoch=1, now=NOW)
        # Exercise all four Reader modes against the same source: mode is not a
        # content transform. The browser does not invent a new source identity.
        for mode in ('preview', 'learn', 'review', 'practice'):
            other = deepcopy(snap); other['mode'] = mode
            mode_evidence = map_reader_snapshot(manifest, section, other,
                expected_session_id=other['session_id'], expected_epoch=1, now=NOW)
            if (mode_evidence.text != evidence.text
                    or mode_evidence.context.reference != evidence.context.reference
                    or mode_evidence.context.mode != mode):
                raise RuntimeError('mode changed source identity or was not preserved')
        with Brain() as brain:
            brain.ingest(StudyEvent(event_id='host-fixture-start', session_id=snap['session_id'],
                sequence=1, kind='SESSION_STARTED', occurred_at=NOW, context=evidence.context), now=NOW)
            validate_evidence(brain, evidence, now=NOW)
            receipt = brain.ingest(StudyEvent(event_id='host-fixture-help', session_id=snap['session_id'],
                sequence=2, kind='HELP_REQUESTED', occurred_at=NOW), now=NOW)
            if not receipt.accepted or receipt.decision.source_ref != evidence.context.reference:
                raise RuntimeError('fixture did not pass the real Brain proposal path')
        entries.append({'id': key, 'label': label, 'context': evidence.context.model_dump(mode='json'),
            'source_ref': evidence.context.reference, 'evidence_text': evidence.text,
            'brain_receipt': receipt.model_dump(mode='json'), 'fixture_reply': reply})
    return {'schema': 'mygpt.host-replay.v1', 'scope': 'SYNTHETIC_FIXED_REPLAY',
        'live_book_connected': False, 'model_calls': 0,
        'fixture_time': NOW.isoformat(), 'verified_modes': ['preview', 'learn', 'review', 'practice'],
        'entries': entries}


def render_module() -> str:
    data = json.dumps(build_catalogue(), ensure_ascii=False, sort_keys=True, indent=2)
    return ('// Generated by python -m mygpt_brain.host_fixtures. Synthetic replay only.\n'
            '// No live Book/Brain service and no model-generated answer.\n'
            'export const catalogue = ' + data + ';\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', type=Path, help='Compare without overwriting the supplied file')
    parser.add_argument('--output', type=Path, help='Create a new generated module; refuses overwrite')
    args = parser.parse_args()
    if args.check and args.output:
        parser.error('choose --check or --output')
    rendered = render_module()
    if args.check:
        if args.check.read_text('utf-8') != rendered:
            raise SystemExit('fixture module differs from actual mapper/Brain output')
        print('HOST_FIXTURE_EXACT_MATCH')
    elif args.output:
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(rendered)
    else:
        print(rendered, end='')
