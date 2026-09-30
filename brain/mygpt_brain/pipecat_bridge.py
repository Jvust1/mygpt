"""Optional Pipecat text bridge for the mygpt companion brain.

Upstream: pipecat-ai/pipecat @
49dea682fb84bfc515d881d00dfeaaa9e9f1075f (BSD-2-Clause).

Pipecat owns realtime transports/STT/TTS/frame flow. mygpt keeps persona,
memory, Book context and supervision policy inside CompanionChatRuntime.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Callable

from .companion_chat import CompanionChatRuntime


@dataclass(frozen=True)
class PipecatCompanionReply:
    request_id: str
    session_id: str
    text: str
    emotion: str


class PipecatCompanionBridge:
    """Convert finalized transcriptions into CompanionChatRuntime turns."""

    def __init__(self, companion: CompanionChatRuntime, *, session_id: str) -> None:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be non-empty")
        self.companion = companion
        self.session_id = session_id.strip()
        self._turn = 0

    def _request_id(self, text: str) -> str:
        self._turn += 1
        digest = hashlib.sha256(
            f"{self.session_id}\x1f{self._turn}\x1f{text}".encode("utf-8")
        ).hexdigest()[:20]
        return f"pipecat-{digest}"

    async def respond(self, text: str, *, request_id: str | None = None) -> PipecatCompanionReply:
        transcript = str(text).strip()
        if not transcript:
            raise ValueError("transcription text must be non-empty")
        rid = request_id or self._request_id(transcript)
        result = await self.companion.send(
            {
                "schema_version": "mygpt.companion-chat.v1",
                "request_id": rid,
                "session_id": self.session_id,
                "persona_id": self.companion.persona.persona_id,
                "text": transcript,
            }
        )
        return PipecatCompanionReply(
            request_id=result.request_id,
            session_id=result.session_id,
            text=result.assistant_message.content,
            emotion=result.presentation_emotion,
        )


def create_pipecat_companion_processor(
    bridge: PipecatCompanionBridge,
    *,
    forward_transcription: bool = False,
    frame_processor_base: type[Any] | None = None,
    transcription_frame_type: type[Any] | None = None,
    text_frame_type: type[Any] | None = None,
) -> Any:
    """Create a Pipecat FrameProcessor lazily.

    Tests may inject frame classes; production imports Pipecat only here.
    Final TranscriptionFrame input is converted into a TextFrame reply that
    downstream Pipecat TTS/output processors can consume.
    """
    if frame_processor_base is None or transcription_frame_type is None or text_frame_type is None:
        try:
            from pipecat.frames.frames import TextFrame, TranscriptionFrame
            from pipecat.processors.frame_processor import FrameProcessor
        except ImportError as exc:
            raise RuntimeError(
                "Pipecat is optional; install brain[realtime] before enabling the bridge"
            ) from exc
        frame_processor_base = frame_processor_base or FrameProcessor
        transcription_frame_type = transcription_frame_type or TranscriptionFrame
        text_frame_type = text_frame_type or TextFrame

    class CompanionProcessor(frame_processor_base):  # type: ignore[misc, valid-type]
        async def process_frame(self, frame: Any, direction: Any):
            await super().process_frame(frame, direction)
            if isinstance(frame, transcription_frame_type):
                text = str(getattr(frame, "text", "") or "").strip()
                finalized = bool(getattr(frame, "finalized", True))
                if not text or not finalized:
                    if forward_transcription:
                        await self.push_frame(frame, direction)
                    return
                reply = await bridge.respond(text)
                if forward_transcription:
                    await self.push_frame(frame, direction)
                await self.push_frame(text_frame_type(reply.text), direction)
                return
            await self.push_frame(frame, direction)

    return CompanionProcessor()
