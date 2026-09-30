"""AIRI ACT emotion parsing, fused into the companion reply boundary.

Ported from moeru-ai/airi, commit b40e3e87b149ea5fb75d4944440493829e601411,
packages/stage-ui/src/composables/queues.ts (parseActEmotion and normalization).
Copyright (c) 2024-PRESENT Neko Ayaka. MIT; see third_party/airi/LICENSE.

MyGPT additionally bounds input, strips all ACT envelopes (including invalid
ones), rejects ambiguous JSON, and keeps the last valid emotion. These are
presentation hints only: no tool, delay, model or permission action is run.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, get_args

from .json_boundary import BoundaryError, load_object

PresentationEmotion = Literal[
    "happy", "sad", "angry", "think", "surprised", "awkward", "question",
    "curious", "neutral",
]
EMOTION_VALUES = frozenset(get_args(PresentationEmotion))
MAX_REPLY_CHARS = 16000
MAX_MARKER_BYTES = 768
_ACT_START = re.compile(r"<\|ACT\b", re.IGNORECASE)
_PARTIAL_ACT_TAIL = re.compile(r"<\|(?:A|AC)?$", re.IGNORECASE)

# This fixed application instruction is added only to the plain-text Ollama
# provider, never read from a character card, Book context or memory.
ACT_PRESENTATION_INSTRUCTION = (
    'You may append one presentation marker to your reply using '
    '<|ACT:{"emotion":"happy"}|>. Supported emotions: '
    'happy, sad, angry, think, surprised, awkward, question, curious, neutral. '
    'Use only the emotion field; this is a visual hint, never an action or tool call. '
    'Always include a useful visible reply outside the marker. '
    'Do not output delay markers or other machine commands.'
)


@dataclass(frozen=True)
class ActReply:
    text: str
    emotion: PresentationEmotion = "neutral"
    intensity: float = 1.0
    marker_found: bool = False


def _parse_act_emotion(payload_text: str) -> tuple[PresentationEmotion, float] | None:
    """Port AIRI's string/object payload and name/intensity normalization."""
    try:
        payload = load_object(payload_text.encode("utf-8"), max_bytes=MAX_MARKER_BYTES)
    except (BoundaryError, UnicodeError):
        return None
    emotion = payload.get("emotion")
    intensity = 1.0
    if isinstance(emotion, str):
        name = emotion
    elif isinstance(emotion, dict) and isinstance(emotion.get("name"), str):
        name = emotion["name"]
        value = emotion.get("intensity")
        # bool is not a JavaScript number; retain AIRI's default for wrong types.
        if type(value) in (int, float):
            intensity = min(1.0, max(0.0, value))
    else:
        return None
    normalized = name.strip().lower()
    if normalized not in EMOTION_VALUES:
        return None
    return normalized, intensity


def parse_act_reply(text: str) -> ActReply:
    """Separate completed model output into speakable text and an emotion hint.

    Input is bounded before scanning. Complete invalid/overlong envelopes are
    removed; an unterminated ACT tail is discarded so truncated model-control
    syntax never reaches speech/history. Plain text is preserved byte-for-byte.
    This is a whole-reply parser, not a streaming token parser.
    """
    if not isinstance(text, str) or len(text) > MAX_REPLY_CHARS:
        raise ValueError("invalid ACT reply size")
    visible: list[str] = []
    cursor = 0
    last: tuple[PresentationEmotion, float] = ("neutral", 1.0)
    found = False
    while match := _ACT_START.search(text, cursor):
        found = True
        visible.append(text[cursor:match.start()])
        # Delimiter-like characters inside a JSON string belong to the
        # payload, not the envelope. An unclosed string fails closed below.
        end = _envelope_end(text, match.end())
        if end < 0:
            cursor = len(text)
            break
        payload = text[match.end():end].lstrip()
        if payload.startswith(":"):
            payload = payload[1:].lstrip()
        parsed = _parse_act_emotion(payload)
        if parsed is not None:
            last = parsed
        cursor = end + 2
    visible.append(text[cursor:])
    clean = "".join(visible)
    if partial := _PARTIAL_ACT_TAIL.search(clean):
        clean = clean[:partial.start()]
        found = True
    return ActReply(clean, last[0], last[1], found)


def _envelope_end(text: str, start: int) -> int:
    """Find a delimiter outside quoted JSON strings in one bounded scan."""
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif text.startswith("|>", index):
            return index
    return -1
