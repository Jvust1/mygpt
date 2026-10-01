"""Read-only compatibility audit of Book's observed Mode/Source DTOs.

This checks a selected identity, not the full Book schema, source truth,
current user activity, consent, or teaching quality. It never creates a
StudyContext, calls Book, persists input, or changes Brain's SIMULATED gate.
"""
from __future__ import annotations

import re
from typing import Any

BOOK_CODE_REFERENCE = "7283f2eef7610d67c6b92b2ef7c513e1225ad957"
MODES = frozenset({"preview", "learn", "review", "practice"})
# These are missing integration capabilities, NOT fields to fabricate in Book DTOs.
LIVE_GAPS = (
    "authenticated_authorized_producer",
    "explicit_current_view_selection",
    "session_identity_and_ordered_event_envelope",
    "verified_book_version",
    "agreed_source_bytes_and_verified_hash",
    "capture_expiry_and_disconnect_protocol",
    "source_kind_preservation_in_brain_reference",
)
BRAIN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
MAX_REFS = 4096


class ContractInputError(ValueError):
    """A fixed diagnostic code; never include source text or arbitrary values."""


def _object(value: Any) -> dict:
    if type(value) is not dict:
        raise ContractInputError("expected_json_object")
    return value


def _identifier(value: Any) -> str:
    # Book's DTO declares str, not Brain's narrower Identifier. Preserve exact
    # Unicode and delimiters here; report incompatibility instead of normalizing.
    if (type(value) is not str or not 0 < len(value) <= 512
            or not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ContractInputError("invalid_or_oversized_identifier")
    return value


def _pair(value: Any) -> tuple[str, str]:
    row = _object(value)
    return _identifier(row.get("kind")), _identifier(row.get("source_id"))


def _pairs(value: Any) -> set[tuple[str, str]]:
    if type(value) is not list or len(value) > MAX_REFS:
        raise ContractInputError("invalid_or_oversized_source_list")
    pairs = [_pair(row) for row in value]
    if len(pairs) != len(set(pairs)):
        raise ContractInputError("duplicate_source_pair")
    return set(pairs)


def audit_book_identity(mode_response: Any, source_response: Any,
                        selected_source: Any = None) -> dict[str, Any]:
    """Audit a caller-supplied selection against source/items/ref identities.

    Additional Book fields are deliberately not copied, hashed or persisted.
    A syntactically valid result still cannot authorize a live connection.
    `selected_source` is {kind, source_id}; passing only activeSourceId is not
    accepted. The caller must obtain selection by an explicit, scoped action.
    """
    blockers: list[str] = []
    identity: dict[str, str] | None = None
    incompatible: list[str] = []
    try:
        mode, source = _object(mode_response), _object(source_response)
        learning_mode = mode.get("mode")
        if type(learning_mode) is not str or learning_mode not in MODES:
            raise ContractInputError("unsupported_learning_mode")
        presentation = _object(mode.get("presentation"))
        if presentation.get("schema_version") != "learning_slice_v1":
            raise ContractInputError("unsupported_presentation_version")
        if presentation.get("mode") != learning_mode:
            raise ContractInputError("presentation_mode_mismatch")
        course = _identifier(mode.get("course_id"))
        book = _identifier(mode.get("book_id"))
        section = _identifier(mode.get("section_id"))
        if course != _identifier(source.get("course_id")):
            raise ContractInputError("course_mismatch")
        if book != _identifier(source.get("book_id")):
            raise ContractInputError("book_mismatch")
        if source.get("section_id") is None:
            raise ContractInputError("source_section_unknown")
        if section != _identifier(source.get("section_id")):
            raise ContractInputError("section_mismatch")
        if selected_source is None:
            raise ContractInputError("explicit_source_pair_required")
        selection = _pair(selected_source)
        if selection != _pair(source):
            raise ContractInputError("selected_source_mismatch")
        refs = _pairs(mode.get("source_refs"))
        items = _pairs(mode.get("items"))
        if selection not in refs or selection not in items:
            raise ContractInputError("selected_source_not_in_both_items_and_refs")
        identity = {"course_id": course, "book_id": book, "section_id": section,
                    "mode": learning_mode, "source_kind": selection[0],
                    "source_id": selection[1]}
        incompatible = [name for name in ("course_id", "book_id", "section_id", "source_id")
                        if BRAIN_ID.fullmatch(identity[name]) is None]
    except ContractInputError as error:
        blockers.append(str(error))
    return {
        "schema_version": "mygpt.book-contract-audit.v1",
        "scope": "STATIC_IDENTITY_AUDIT_ONLY",
        "book_code_reference": BOOK_CODE_REFERENCE,
        "identities_match": identity is not None,
        "identity": identity,
        "blockers": blockers,
        "brain_identifier_incompatibilities": incompatible,
        "live_ready": False,
        "remaining_live_capabilities": list(LIVE_GAPS),
        "network_calls": 0,
        "model_calls": 0,
    }
