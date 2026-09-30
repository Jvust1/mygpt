"""Wake-word -> transcription -> companion-chat composition.

This composes existing mygpt boundaries without opening microphones or choosing
an ASR backend. Callers inject a local transcriber (for example the existing
Sherpa path) and supply already-buffered utterance audio.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .companion_chat import CompanionChatResult, CompanionChatRuntime
from .wakeword import OpenWakeWordGate, WakeWordResult
from .turn_control import VoiceTurnController


Transcriber = Callable[[bytes], Awaitable[str]]


@dataclass(frozen=True)
class VoiceActivationResult:
    wakeword: WakeWordResult
    transcript: str = ""
    chat: CompanionChatResult | None = None
    interrupted_previous: bool = False


class VoiceActivationRuntime:
    """Compose wake-word detection, injected ASR and CompanionChatRuntime."""

    def __init__(
        self,
        *,
        gate: OpenWakeWordGate,
        transcriber: Transcriber,
        companion: CompanionChatRuntime,
        speech_detector: Any | None = None,
        turn_controller: VoiceTurnController | None = None,
    ) -> None:
        if not callable(transcriber):
            raise TypeError("transcriber must be async-callable")
        self.gate = gate
        self.transcriber = transcriber
        self.companion = companion
        self.speech_detector = speech_detector
        self.turn_controller = turn_controller

    async def process(
        self,
        *,
        wake_frame: Any,
        utterance_audio: bytes,
        request_id: str,
        session_id: str,
        speech_frames: list[Any] | None = None,
    ) -> VoiceActivationResult:
        wake = self.gate.process(wake_frame)
        if not wake.triggered:
            return VoiceActivationResult(wakeword=wake)

        if self.speech_detector is not None and speech_frames is not None:
            has_speech = getattr(self.speech_detector, "has_speech", None)
            if not callable(has_speech):
                raise TypeError("speech_detector must provide has_speech(frames)")
            if not has_speech(speech_frames):
                return VoiceActivationResult(wakeword=wake)

        if not isinstance(utterance_audio, (bytes, bytearray)) or not utterance_audio:
            raise ValueError("utterance_audio must contain local PCM/audio bytes")

        lease = self.turn_controller.begin_user_turn() if self.turn_controller is not None else None
        transcript = (await self.transcriber(bytes(utterance_audio))).strip()
        if not transcript:
            raise RuntimeError("transcriber returned empty transcript")

        if lease is not None:
            self.turn_controller.begin_assistant_turn(lease)
        chat = await self.companion.send(
            {
                "schema_version": "mygpt.companion-chat.v1",
                "request_id": request_id,
                "session_id": session_id,
                "persona_id": self.companion.persona.persona_id,
                "text": transcript,
            }
        )
        if lease is not None:
            self.turn_controller.finish_assistant_turn(lease)
        return VoiceActivationResult(
            wakeword=wake,
            transcript=transcript,
            chat=chat,
            interrupted_previous=(lease.interrupted_previous if lease is not None else False),
        )
