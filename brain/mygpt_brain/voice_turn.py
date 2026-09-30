"""Compose wake-word and VAD adapters into one local voice-turn gate."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class VoiceGateState(str, Enum):
    WAIT_WAKE = "wait_wake"
    WAIT_SPEECH = "wait_speech"
    READY = "ready"


@dataclass(frozen=True)
class VoiceTurnDecision:
    state: VoiceGateState
    activated: bool = False
    speech_detected: bool = False
    wake_label: str = ""
    wake_score: float = 0.0


class VoiceTurnGate:
    """openWakeWord -> Silero VAD composition without microphone ownership."""

    def __init__(self, wakeword_gate: Any, vad_detector: Any) -> None:
        if not callable(getattr(wakeword_gate, "process", None)):
            raise TypeError("wakeword_gate must provide process(frame)")
        if not callable(getattr(vad_detector, "has_speech", None)):
            raise TypeError("vad_detector must provide has_speech(frames)")
        self._wakeword = wakeword_gate
        self._vad = vad_detector
        self._state = VoiceGateState.WAIT_WAKE

    @property
    def state(self) -> VoiceGateState:
        return self._state

    def reset(self) -> None:
        self._state = VoiceGateState.WAIT_WAKE
        for item in (self._wakeword, self._vad):
            reset = getattr(item, "reset", None)
            if callable(reset):
                reset()

    def process_wake_frame(self, frame: Any) -> VoiceTurnDecision:
        if self._state is not VoiceGateState.WAIT_WAKE:
            return VoiceTurnDecision(state=self._state)
        result = self._wakeword.process(frame)
        if bool(getattr(result, "triggered", False)):
            self._state = VoiceGateState.WAIT_SPEECH
            return VoiceTurnDecision(
                state=self._state,
                activated=True,
                wake_label=str(getattr(result, "label", "") or ""),
                wake_score=float(getattr(result, "score", 0.0) or 0.0),
            )
        return VoiceTurnDecision(
            state=self._state,
            wake_label=str(getattr(result, "label", "") or ""),
            wake_score=float(getattr(result, "score", 0.0) or 0.0),
        )

    def confirm_speech(self, frames: Iterable[Any]) -> VoiceTurnDecision:
        if self._state is not VoiceGateState.WAIT_SPEECH:
            return VoiceTurnDecision(state=self._state)
        speech = bool(self._vad.has_speech(frames))
        self._state = VoiceGateState.READY if speech else VoiceGateState.WAIT_WAKE
        return VoiceTurnDecision(
            state=self._state,
            speech_detected=speech,
        )

    def consume_ready(self) -> bool:
        if self._state is not VoiceGateState.READY:
            return False
        self._state = VoiceGateState.WAIT_WAKE
        return True
