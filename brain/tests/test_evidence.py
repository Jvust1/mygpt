from datetime import timedelta
import pytest
from pydantic import ValidationError

from mygpt_brain import Brain
from mygpt_brain.adapters import EvidenceText, GroundedReply, validate_evidence, validate_reply
from mygpt_brain.__main__ import demo
from test_core import NOW, TEXT, context, event


def test_source_bytes_and_current_snapshot():
    with Brain() as brain:
        brain.ingest(event(), now=NOW)
        evidence = EvidenceText(context=context(), text=TEXT)
        assert validate_evidence(brain, evidence, now=NOW) == evidence
        reply = validate_reply({"text": "SIMULATED", "source_refs": [context().reference]}, evidence)
        assert reply.evidence_kind == "SIMULATED"
        assert TEXT not in "\n".join(brain.db.iterdump())


@pytest.mark.parametrize("text", ["", "wrong bytes", "x" * 12001])
def test_bad_source_text(text):
    with pytest.raises(ValidationError):
        EvidenceText(context=context(), text=text)


@pytest.mark.parametrize("refs", [[], ["invented"], [context().reference, "invented"], [context().reference] * 2])
def test_bad_citations(refs):
    with pytest.raises(ValueError):
        validate_reply({"text": "fixture", "source_refs": refs}, EvidenceText(context=context(), text=TEXT))


@pytest.mark.parametrize("field,value", [("text", ""), ("text", "x" * 4001),
                                        ("evidence_kind", "REAL"), ("provider", "unknown")])
def test_reply_schema(field, value):
    data = {"text": "fixture", "source_refs": [context().reference], field: value}
    with pytest.raises(ValidationError):
        GroundedReply.model_validate(data)


def test_source_after_expiry_or_context_switch():
    with Brain() as brain:
        brain.ingest(event(), now=NOW)
        evidence = EvidenceText(context=context(), text=TEXT)
        with pytest.raises(ValueError):
            validate_evidence(brain, evidence, now=NOW + timedelta(seconds=120))
        brain.ingest(event(2, "CONTEXT_CHANGED", context=context(section_id="section-2")), now=NOW)
        with pytest.raises(ValueError):
            validate_evidence(brain, evidence, now=NOW)


def test_demo_is_deterministic_and_has_no_model_calls():
    first = demo()
    assert first == demo()
    assert len(first) == 8
    assert first[3]["kind"] == "DUPLICATE_HELP"
    assert first[3]["receipt"]["decision"]["action"] == "stay_silent"
    assert first[-1]["view"]["status"] == "ended"
    assert all(not row["receipt"]["decision"]["model_called"] for row in first)
