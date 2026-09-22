"""Synthetic DTO subsets, not captured user study sessions or a live API test."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pytest

PATH = Path(__file__).resolve().parents[1] / "mygpt_brain" / "book_contract_audit.py"
spec = importlib.util.spec_from_file_location("book_contract_audit_under_test", PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
audit = module.audit_book_identity


def sample(mode="learn"):
    pair = {"kind": "object", "source_id": "source-1"}
    snapshot = {"mode": mode, "course_id": "course-1", "book_id": "book-1",
                "section_id": "section-1", "items": [dict(pair)],
                "source_refs": [dict(pair)],
                "presentation": {"schema_version": "learning_slice_v1", "mode": mode}}
    source = {"course_id": "course-1", "book_id": "book-1", "section_id": "section-1", **pair}
    return snapshot, source, pair


@pytest.mark.parametrize("mode", sorted(module.MODES))
def test_four_modes_are_mapped_but_never_live(mode):
    args = sample(mode)
    result = audit(*args)
    assert result["identities_match"] is True
    assert result["identity"]["mode"] == mode
    assert result["live_ready"] is False
    assert result["blockers"] == []
    assert result["remaining_live_capabilities"] == list(module.LIVE_GAPS)
    assert result["network_calls"] == result["model_calls"] == 0


@pytest.mark.parametrize("field,code", [("course_id", "course_mismatch"),
                                       ("book_id", "book_mismatch"),
                                       ("section_id", "section_mismatch")])
def test_cross_context_identity_is_rejected(field, code):
    mode, source, selected = sample()
    source[field] = "other"
    result = audit(mode, source, selected)
    assert result["blockers"] == [code]
    assert result["identity"] is None


def test_unknown_source_section_is_not_filled_from_mode():
    mode, source, selected = sample()
    source["section_id"] = None
    assert audit(mode, source, selected)["blockers"] == ["source_section_unknown"]


def test_no_implicit_selection_even_with_one_source():
    mode, source, _ = sample()
    assert audit(mode, source)["blockers"] == ["explicit_source_pair_required"]


def test_active_id_alone_does_not_select_a_kind():
    mode, source, _ = sample()
    assert audit(mode, source, {"source_id": "source-1"})["identities_match"] is False


def test_same_source_id_different_kind_is_not_the_same_source():
    mode, source, selected = sample()
    source["kind"] = "figure"
    assert audit(mode, source, selected)["blockers"] == ["selected_source_mismatch"]


def test_two_kinds_can_share_an_id_without_collapse():
    mode, source, selected = sample()
    figure = {"kind": "figure", "source_id": selected["source_id"]}
    mode["items"].append(dict(figure))
    mode["source_refs"].append(dict(figure))
    source.update(figure)
    result = audit(mode, source, figure)
    assert result["identities_match"] is True
    assert result["identity"]["source_kind"] == "figure"


@pytest.mark.parametrize("key", ["items", "source_refs"])
def test_selection_must_be_in_both_sets(key):
    mode, source, selected = sample()
    mode[key] = []
    assert audit(mode, source, selected)["blockers"] == ["selected_source_not_in_both_items_and_refs"]


@pytest.mark.parametrize("key", ["items", "source_refs"])
def test_duplicate_pairs_are_ambiguous(key):
    mode, source, selected = sample()
    mode[key].append(dict(selected))
    assert audit(mode, source, selected)["blockers"] == ["duplicate_source_pair"]


@pytest.mark.parametrize("value", ["wrong", None, 1, True, [], {}])
def test_unknown_modes_rejected(value):
    mode, source, selected = sample()
    mode["mode"] = value
    assert audit(mode, source, selected)["blockers"] == ["unsupported_learning_mode"]


@pytest.mark.parametrize("value", [None, {}, {"schema_version": "learning_slice_v99", "mode": "learn"},
                                   {"schema_version": "learning_slice_v1", "mode": "practice"}])
def test_invalid_presentation_not_accepted(value):
    mode, source, selected = sample()
    mode["presentation"] = value
    assert audit(mode, source, selected)["identities_match"] is False


@pytest.mark.parametrize("value", [None, [], 2, "payload"])
def test_invalid_input_is_bounded_diagnostic(value):
    assert audit(value, value, value)["blockers"] == ["expected_json_object"]


@pytest.mark.parametrize("value", [None, "", " ", True, 1, "a\n", "a\x7f", "a" * 513])
def test_identifiers_are_not_coerced(value):
    mode, source, selected = sample()
    mode["course_id"] = value
    assert audit(mode, source, selected)["blockers"] == ["invalid_or_oversized_identifier"]


@pytest.mark.parametrize("value", [None, {}, "not a list", [None]])
def test_invalid_lists_are_rejected(value):
    mode, source, selected = sample()
    mode["source_refs"] = value
    assert audit(mode, source, selected)["identities_match"] is False


def test_oversize_lists_rejected_before_traversal():
    mode, source, selected = sample()
    mode["source_refs"] = [selected] * (module.MAX_REFS + 1)
    assert audit(mode, source, selected)["blockers"] == ["invalid_or_oversized_source_list"]


@pytest.mark.parametrize("value", ["来源:一", "source:1", "source/1", "x" * 97])
def test_opaque_book_id_is_preserved_and_brain_incompatibility_reported(value):
    mode, source, selected = sample()
    for row in [source, selected, *mode["items"], *mode["source_refs"]]:
        row["source_id"] = value
    result = audit(mode, source, selected)
    assert result["identities_match"] is True
    assert result["identity"]["source_id"] == value
    assert result["brain_identifier_incompatibilities"] == ["source_id"]
    assert result["live_ready"] is False


def test_untrusted_live_claims_cannot_override_the_audit():
    mode, source, selected = sample()
    for row in [mode, source, selected]:
        row.update(live_ready=True, authenticated=True, book_version="v1",
                   session_id="looks-real", source_sha256="f" * 64)
    result = audit(mode, source, selected)
    assert result["live_ready"] is False
    assert "verified_book_version" in result["remaining_live_capabilities"]
    assert "book_version" not in result["identity"]


def test_body_formula_and_extra_private_payload_not_returned_or_mutated():
    mode, source, selected = sample()
    source.update(content_zh="private-source-fixture", formula="private-formula-fixture",
                  raw_messages="do-not-retain-fixture")
    mode["items"][0]["content_zh"] = "private-source-fixture"
    before = deepcopy((mode, source, selected))
    result = audit(mode, source, selected)
    assert (mode, source, selected) == before
    assert "private" not in repr(result)
    assert "do-not-retain" not in repr(result)


def test_reading_a_response_is_not_proof_of_user_activity():
    result = audit(*sample())
    assert "explicit_current_view_selection" in result["remaining_live_capabilities"]
    assert "session_identity_and_ordered_event_envelope" in result["remaining_live_capabilities"]
    assert "capture_expiry_and_disconnect_protocol" in result["remaining_live_capabilities"]
    assert result["scope"] == "STATIC_IDENTITY_AUDIT_ONLY"


def test_output_mutation_cannot_change_future_gaps():
    first = audit(*sample())
    first["remaining_live_capabilities"].clear()
    second = audit(*sample())
    assert second["remaining_live_capabilities"] == list(module.LIVE_GAPS)
