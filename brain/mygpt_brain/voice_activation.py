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


Transcriber = Callable[[bytes], Awaitable[str]]


@dataclass(frozen=True)
class VoiceActivationResult:
    wakeword: WakeWordResult
    transcript: str = ""
    chat: CompanionChatResult | None = None


class VoiceActivationRuntime:
    """Compose wake-word detection, injected ASR and CompanionChatRuntime."""

    def __init__(
        self,
        *,
        gate: OpenWakeWordGate,
        transcriber: Transcriber,
        companion: CompanionChatRuntime,
    ) -> None:
        if not callable(transcriber):
            raise TypeError("transcriber must be async-callable")
        self.gate = gate
        self.transcriber = transcriber
        self.companion = companion

    async def process(
        self,
        *,
        wake_frame: Any,
        utterance_audio: bytes,
        request_id: str,
        session_id: str,
    ) -> VoiceActivationResult:
        wake = self.gate.process(wake_frame)
        if not wake.triggered:
            return VoiceActivationResult(wakeword=wake)

        if not isinstance(utterance_audio, (bytes, bytearray)) or not utterance_audio:
            raise ValueError("utterance_audio must contain local PCM/audio bytes")

        transcript = (await self.transcriber(bytes(utterance_audio))).strip()
        if not transcript:
            raise RuntimeError("transcriber returned empty transcript")

        chat = await self.companion.send(
            {
                "schema_version": "mygpt.companion-chat.v1",
                "request_id": request_id,
                "session_id": session_id,
                "persona_id": self.companion.persona.persona_id,
                "text": transcript,
            }
        )
        return VoiceActivationResult(
            wakeword=wake,
            transcript=transcript,
            chat=chat,
        )
