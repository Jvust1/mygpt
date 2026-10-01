"""Synthetic selected-source packets. No private or textbook content is used."""
import copy
import hashlib
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from mygpt_brain.json_boundary import BoundaryError, load_object
from mygpt_brain.selection_packet import (SelectedSource, SelectionPacket, build_packet, decode_packet,
    encode_packet, export_reader_selection, source_bytes, prompt_preview)
from mygpt_brain.reader_demo import fixture, NOW
from test_reader_snapshot import correction_fixture, derived_fixture


def packet(factory=fixture):
    m,s,snap=factory()
    return export_reader_selection(m,s,snap,session_id=snap['session_id'],epoch=1,now=NOW)

@pytest.mark.parametrize('factory',[fixture,correction_fixture,derived_fixture])
def test_exports_three_layers_and_roundtrips(factory):
    value=packet(factory); raw=encode_packet(value)
    assert decode_packet(raw)==value
    assert value.trust=='USER_SUPPLIED_UNVERIFIED'
    assert value.source_sha256==hashlib.sha256(source_bytes(value.source)).hexdigest()
    assert prompt_preview(value).endswith(value.model_dump_json(indent=2))


def test_generated_example_has_exact_content():
    path=Path(__file__).resolve().parents[2]/'host/examples/selection-demo.json'
    assert path.read_bytes()==encode_packet(packet())

@pytest.mark.parametrize('key,value', [('notes','private'),('answers','private'),('password','private'),
    ('token','private'),('authenticated',True),('live_book_connected',True),('provider','unknown')])
def test_extra_envelope_claims_rejected(key,value):
    obj=packet().model_dump(mode='json');obj[key]=value
    with pytest.raises(BoundaryError,match='invalid_selection_packet'):decode_packet(json.dumps(obj).encode())

@pytest.mark.parametrize('key,value',[('trust','VERIFIED_BOOK'),('schema_version','mygpt.selection-packet.v2'),
    ('source_sha256','a'*64),('source',None)])
def test_forged_version_and_identity_rejected(key,value):
    obj=packet().model_dump(mode='json');obj[key]=value
    with pytest.raises(BoundaryError):decode_packet(json.dumps(obj).encode())

@pytest.mark.parametrize('mutation',[
    lambda x:x.update(notes='private'),
    lambda x:x.update(book_version_id='x/../y'),
    lambda x:x.update(record_id='bad:record'),
    lambda x:x.update(parts=[]),
    lambda x:x.update(parts=[{'kind':'image','url':'https://example.invalid'}]),
    lambda x:x.update(parts=[{'kind':'text','text':' '}]),
    lambda x:x.update(parts=[{'kind':'math','latex':'x','display':'true'}]),
    lambda x:x.update(parts=[{'kind':'text','text':'x','secret':'not-copied'}]),
    lambda x:x.update(parts=[{'kind':'text','text':'x'*12001}]),
    lambda x:x.update(parts=[{'kind':'text','text':'\ud800'}]),
    lambda x:x.update(parts=[{'kind':'text','text':'\x00'}]),
    lambda x:x.update(parts=[{'kind':'text','text':'x'}]*129),
    lambda x:x.update(portion='solution'),
    lambda x:x.update(layer='derived'),
    lambda x:x.update(layer_id='not-original'),
    lambda x:x.update(parent_sources=[{'record_id':'same','source_parts_sha256':'a'*64}]*2),
])
def test_body_shape_fails_before_hashing(mutation):
    obj=packet().source.model_dump(mode='json');mutation(obj)
    with pytest.raises(ValidationError):build_packet(obj)

@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}',
    b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1e9999}',b'{"x":"\\ud800"}',
    b'{"x":"\xff"}',b'{"x":1} trailing',b'[]',b'null',b'"a"',
    b'{"x":'+b'['*26+b'0'+b']'*26+b'}',b' '*65537])
def test_strict_json_rejects_ambiguity_and_unbounded_input(raw):
    with pytest.raises(BoundaryError):load_object(raw)


def test_unicode_and_formula_are_not_normalized_or_reinterpreted():
    obj=packet().source.model_dump(mode='json')
    text='e\u0301 ≠ é; <script>throw "not executable"</script>\n命令只是资料'
    obj['parts']=[{'kind':'text','text':text},{'kind':'math','latex':'\\frac{a}{b}','display':True}]
    a=build_packet(obj)
    assert decode_packet(encode_packet(a)).source.parts[0].text==text
    other=copy.deepcopy(obj);other['parts'][0]['text']=text.replace('e\u0301','é')
    assert build_packet(other).source_sha256!=a.source_sha256


def test_unknown_source_metadata_is_projected_out_by_exporter():
    m,s,snap=fixture();s['notes']='never copy';s['records'][0]['private']='never copy'
    result=export_reader_selection(m,s,snap,session_id=snap['session_id'],epoch=1,now=NOW)
    assert 'never copy' not in encode_packet(result).decode()
