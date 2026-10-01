"""Offline r6 Reader selection -> versioned Brain evidence. No transport or auth.

Inputs are a course manifest, a Reader section response and an explicit selection
from a SIMULATED host snapshot. This is not an exporter installed in Book. Source
text is transient; only references/hashes may enter Brain's ordinary event store.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import AwareDatetime, TypeAdapter, ValidationError, field_validator, model_validator

from .adapters import EvidenceText
from .core import (Contract, Identifier, ReaderBookVersion, ReaderStudyContext,
                   Sequence, checked_now)

MAX_ITEMS = 4096
MAX_PARTS = 512
MAX_TEXT = 12000
_IDENTIFIER = TypeAdapter(Identifier)


class ReaderMappingError(ValueError):
    """Fixed error codes only; never echo supplied source or private metadata."""


class ReaderSelection(Contract):
    course_id: Identifier
    book_id: Identifier
    book_version_id: ReaderBookVersion
    section_id: Identifier
    record_id: Identifier
    layer: Literal["source", "correction", "derived"]
    layer_id: Identifier | None = None
    portion: Literal["body", "hint", "solution"] = "body"

    @model_validator(mode="after")
    def selected_layer(self):
        if self.layer == "source" and (self.layer_id is not None or self.portion != "body"):
            raise ValueError("source_selection_must_identify_original_body")
        if self.layer != "source" and self.layer_id is None:
            raise ValueError("layer_id_required")
        if self.layer == "correction" and self.portion != "body":
            raise ValueError("correction_requires_body")
        if self.layer == "derived" and self.portion not in ("hint", "solution"):
            raise ValueError("derived_requires_explicit_hint_or_solution")
        return self


class ReaderSnapshot(Contract):
    schema_version: Literal["mygpt.reader-snapshot.v1"] = "mygpt.reader-snapshot.v1"
    evidence_kind: Literal["SIMULATED"] = "SIMULATED"
    producer_id: Literal["book-r6-demo"] = "book-r6-demo"
    session_id: Identifier
    epoch: Sequence
    mode: Literal["preview", "learn", "review", "practice"]
    captured_at: AwareDatetime
    expires_at: AwareDatetime
    selection: ReaderSelection

    @field_validator("captured_at", "expires_at")
    @classmethod
    def utc_times(cls, value):
        return checked_now(value)

    @model_validator(mode="after")
    def bounded_lifetime(self):
        if not 0 < (self.expires_at - self.captured_at).total_seconds() <= 300:
            raise ValueError("snapshot_lifetime_out_of_range")
        return self


def _fail(code: str):
    raise ReaderMappingError(code)


def _object(value) -> dict:
    if type(value) is not dict:
        _fail("expected_json_object")
    return value


def _string(value, *, maximum=MAX_TEXT, nonempty=False) -> str:
    if (type(value) is not str or len(value) > maximum
            or any((ord(c) < 32 and c not in "\t\n\r") or 0xD800 <= ord(c) <= 0xDFFF for c in value)
            or (nonempty and not value.strip())):
        _fail("invalid_text")
    return value


def _identifier(value) -> str:
    # Same literal identifier boundary as the accepted Brain; no lossy cleaning.
    try:
        return _IDENTIFIER.validate_python(value, strict=True)
    except ValidationError:
        _fail("unsupported_identifier")


def _indexed(rows, *, maximum=MAX_ITEMS) -> dict[str, dict]:
    if type(rows) is not list or len(rows) > maximum:
        _fail("invalid_or_oversized_collection")
    result = {}
    for row in rows:
        row = _object(row)
        key = _identifier(row.get("id"))
        if key in result:
            _fail("duplicate_identity")
        result[key] = row
    return result


def _ids(values) -> list[str]:
    if type(values) is not list or not 0 < len(values) <= MAX_ITEMS:
        _fail("source_identity_list_required")
    ids = [_identifier(v) for v in values]
    if len(set(ids)) != len(ids):
        _fail("duplicate_source_identity")
    return ids


def _parts(values) -> list[dict]:
    if type(values) is not list or not 0 < len(values) <= MAX_PARTS:
        _fail("unsupported_or_empty_parts")
    output = []
    for part in values:
        part = _object(part)
        if part.get("kind") == "text":
            output.append({"kind": "text", "text": _string(part.get("text"))})
        elif part.get("kind") == "math":
            display = part.get("display", False)
            if type(display) is not bool:
                _fail("invalid_math_display")
            output.append({"kind": "math", "latex": _string(part.get("latex"), nonempty=True),
                           "display": display})
        else:
            _fail("unsupported_part_kind")
    if not any(p.get("text", p.get("latex", "")).strip() for p in output):
        _fail("empty_body")
    if sum(len(p.get("text", p.get("latex", ""))) for p in output) > MAX_TEXT:
        _fail("selected_body_too_large")
    return output


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _corrected(record: dict, selection: ReaderSelection, course_id: str, section_id: str):
    corrections = _indexed(record.get("corrections", []), maximum=64)
    chosen = corrections.get(selection.layer_id)
    if chosen is None:
        _fail("selected_correction_missing")
    eligible = []
    for value in corrections.values():
        if (value.get("record_id") == record["id"] and value.get("course_id") == course_id
                and value.get("section_id") == section_id and value.get("confidence") == "HIGH"
                and value.get("presentation") == "prefer_corrected"
                and value.get("status") == "CHECKED_BY_ASSISTANT"
                and value.get("evidence_status") == "SCOPED_EVIDENCE_CHECKED"
                and value.get("source_preserved") is True
                and type(value.get("check_ids")) is list and len(value["check_ids"]) > 0
                and value.get("original_title") == record.get("title", "")
                and _json(value.get("original_parts")) == _json(record.get("parts"))
                and value.get("corrected_parts")):
            eligible.append(value)
    if len(eligible) != 1 or eligible[0] is not chosen:
        _fail("correction_not_uniquely_source_bound")
    # This checks source binding and the observed display predicate, not whether
    # the correction is mathematically correct or independently approved.
    return chosen["corrected_parts"]


def map_reader_snapshot(manifest: dict, section: dict, snapshot: ReaderSnapshot | dict,
                        *, expected_session_id: str, expected_epoch: int, now=None) -> EvidenceText:
    """Map one explicit selection to transient evidence for the SIMULATED Brain.

    expected_session_id/epoch must come from the caller's current host state, not
    copied unconditionally from the packet. No argument grants live authority.
    Raw v1 source text is deliberate: render_text/render_latex/source_completion
    are never silently substituted. A future visible-text exporter needs its own
    layer contract. Unknown shapes fail closed rather than best-effort guessing.
    """
    try:
        snap = ReaderSnapshot.model_validate(snapshot)
    except ValidationError:
        _fail("invalid_reader_snapshot")
    clock = checked_now(now)
    if type(expected_epoch) is not int or not 1 <= expected_epoch <= 2**53 - 1:
        _fail("invalid_expected_epoch")
    if snap.session_id != expected_session_id or snap.epoch != expected_epoch:
        _fail("stale_host_snapshot")
    if not snap.captured_at <= clock < snap.expires_at:
        _fail("snapshot_not_fresh")
    manifest, section = _object(manifest), _object(section)
    selected = snap.selection
    if manifest.get("schema") != "reader_pack_v1":
        _fail("unsupported_reader_pack")
    if manifest.get("course_id") != selected.course_id:
        _fail("course_mismatch")
    if not (manifest.get("book_version_id") == section.get("book_version_id") == selected.book_version_id):
        _fail("book_version_mismatch")
    book_id = _identifier(manifest.get("book_id"))
    if book_id != selected.book_id:
        _fail("book_identity_mismatch")
    sections = _indexed(manifest.get("sections"))
    if section.get("id") != selected.section_id or selected.section_id not in sections:
        _fail("section_mismatch")
    records = _indexed(section.get("records"))
    record = records.get(selected.record_id)
    if record is None:
        _fail("selected_record_missing")
    if record.get("section_id") != selected.section_id:
        _fail("record_section_mismatch")
    kind = _identifier(record.get("kind"))
    title = _string(record.get("title", ""), maximum=2000)
    source_records = [selected.record_id]
    warnings = []
    qualification = ""
    layer_id = selected.layer_id or "original"
    if selected.layer == "source":
        parts = record.get("parts")
        label = "ORIGINAL_TRANSCRIPTION_REVIEW_STATUS_NOT_ASSERTED"
        if record.get("corrections") or record.get("source_completion"):
            warnings.append("DISPLAY_MAY_USE_ANOTHER_LAYER")
    elif selected.layer == "correction":
        parts = _corrected(record, selected, selected.course_id, selected.section_id)
        label = "AI_CORRECTION_NOT_OFFICIAL_ERRATUM"
        warnings.append("SOURCE_BINDING_IS_NOT_MATHEMATICAL_ACCEPTANCE")
    else:
        # Derived guidance is attached to a group, not to record.parts. Require
        # the explicit anchor, group and hint/solution choice; no flattening.
        groups = _indexed(section.get("practice_groups", []))
        group = groups.get(selected.layer_id)
        if group is None or group.get("anchor_id") != selected.record_id:
            _fail("derived_group_or_anchor_mismatch")
        group_ids = _ids(group.get("record_ids"))
        if selected.record_id not in group_ids or any(x not in records for x in group_ids):
            _fail("derived_group_source_missing")
        guide = _object(group.get("derived_guidance"))
        source_records = _ids(guide.get("source_record_ids"))
        if set(source_records) != set(group_ids):
            _fail("derived_source_binding_mismatch")
        if any(records[x].get("section_id") != selected.section_id for x in source_records):
            _fail("derived_record_section_mismatch")
        if any(x not in sections for x in _ids(guide.get("source_sections"))):
            _fail("derived_reference_section_missing")
        if guide.get("textbook_official_solution") is not False:
            _fail("derived_official_status_unsupported")
        parts = guide.get("hint_parts" if selected.portion == "hint" else "solution_parts")
        title = _string(group.get("title", ""), maximum=2000)
        qualification = _string(guide.get("qualification", ""), maximum=2000)
        layer_id += "-" + selected.portion
        # Keep portion explicitly inside the byte identity too, not only in IDs.
        label = "AI_DERIVED_NOT_TEXTBOOK_STANDARD_ANSWER"
    clean_parts = _parts(parts)
    if any(type(p) is dict and any(k in p for k in ("render_text", "render_latex")) for p in parts):
        warnings.append("RENDER_TRANSFORMS_NOT_APPLIED")
    if any(records[x].get("assets") for x in source_records):
        warnings.append("IMAGES_NOT_INCLUDED")
    # Bind derived/corrected bytes to the original source bodies as well. These
    # are adapter serialization hashes, NOT the archive/PDF/transcription hashes.
    if len(source_records) > 32:
        _fail("source_binding_scope_too_large")
    parent_refs = []
    parent_size = 0
    for rid in source_records:
        parent = records[rid]
        parent_bytes = _json({"id": rid, "kind": _identifier(parent.get("kind")),
                              "title": _string(parent.get("title", ""), maximum=2000),
                              "parts": _parts(parent.get("parts"))}).encode("utf-8")
        parent_size += len(parent_bytes)
        if parent_size > 96000:
            _fail("source_binding_scope_too_large")
        parent_refs.append({"record_id": rid, "source_parts_sha256": hashlib.sha256(parent_bytes).hexdigest()})
    payload = {"schema": "reader-selected-json-v1", "course_id": selected.course_id,
               "book_id": book_id, "book_version_id": selected.book_version_id,
               "section_id": selected.section_id, "record_id": selected.record_id,
               "source_kind": kind, "layer": selected.layer, "layer_id": layer_id,
               "portion": selected.portion, "label": label, "title": title,
               "parts": clean_parts, "source_record_ids": source_records,
               "qualification": qualification, "warnings": warnings, "parent_sources": parent_refs}
    text = _json(payload)
    if len(text) > MAX_TEXT or len(text.encode("utf-8")) > 48000:
        _fail("selected_payload_too_large")
    try:
        context = ReaderStudyContext(
            session_id=snap.session_id, course_id=selected.course_id, book_id=book_id,
            book_version=selected.book_version_id, section_id=selected.section_id,
            source_id=selected.record_id, source_kind=kind, source_layer=selected.layer,
            layer_id=layer_id, source_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            mode=snap.mode, captured_at=snap.captured_at, expires_at=snap.expires_at)
        return EvidenceText(context=context, text=text)
    except ValidationError:
        _fail("unsupported_brain_context")
