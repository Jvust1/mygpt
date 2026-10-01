"""Pipecat response lifecycle fused with the mygpt companion brain.

Upstream: pipecat-ai/pipecat @
49dea682fb84bfc515d881d00dfeaaa9e9f1075f (BSD-2-Clause).

Pipecat owns realtime transports/STT/TTS/frame flow. mygpt keeps persona,
memory, Book context and supervision policy inside CompanionChatRuntime.

The response Start/try/End lifecycle is adapted from Pipecat's
src/pipecat/services/openai/base_llm.py at the pinned revision.
Copyright (c) 2024–2026, Daily. BSD-2-Clause; third_party/pipecat/LICENSE.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import re
import uuid
from typing import Any, Awaitable, Callable

from .companion_chat import CompanionChatRuntime, SupersededChatTurn
from .turn_control import TurnLease, VoiceTurnController


@dataclass(frozen=True)
class PipecatCompanionReply:
    request_id: str
    session_id: str
    text: str
    emotion: str
    replayed: bool = False


class PipecatCompanionBridge:
    """Convert finalized transcriptions into CompanionChatRuntime turns."""

    def __init__(
        self, companion: CompanionChatRuntime, *, session_id: str,
        turn_controller: VoiceTurnController | None = None,
    ) -> None:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be non-empty")
        self.companion = companion
        self.session_id = session_id.strip()
        self._turn = 0
        # Automatic voice events are new inputs, even when text/counter repeat
        # after restart. This ephemeral correlation nonce is never a credential
        # or separately persisted identity. Explicit IDs remain retry keys.
        self._incarnation = uuid.uuid4().hex
        self.turn_controller = turn_controller or VoiceTurnController()
        self.closed = False

    def begin_turn(self) -> TurnLease:
        if self.closed:
            raise RuntimeError("Pipecat companion session is closed")
        return self.turn_controller.begin_user_turn()

    def is_current(self, lease: TurnLease) -> bool:
        return not self.closed and self.turn_controller.is_current(lease)

    def interrupt(self) -> None:
        self.turn_controller.begin_user_turn()

    def close(self) -> None:
        self.closed = True
        self.interrupt()

    def _request_id(self, text: str) -> str:
        self._turn += 1
        digest = hashlib.sha256(
            f"{self.session_id}\x1f{self._incarnation}\x1f{self._turn}\x1f{text}".encode("utf-8")
        ).hexdigest()[:20]
        return f"pipecat-{digest}"

    async def respond(
        self, text: str, *, request_id: str | None = None, lease: TurnLease | None = None,
    ) -> PipecatCompanionReply:
        transcript = str(text).strip()
        if not transcript:
            raise ValueError("transcription text must be non-empty")
        rid = self._request_id(transcript) if request_id is None else request_id
        lease = lease or self.begin_turn()
        if not self.is_current(lease):
            raise SupersededChatTurn("companion turn superseded")
        self.turn_controller.begin_assistant_turn(lease)
        try:
            result = await self.companion.send(
                {
                    "schema_version": "mygpt.companion-chat.v1",
                    "request_id": rid,
                    "session_id": self.session_id,
                    "persona_id": self.companion.persona.persona_id,
                    "text": transcript,
                },
                is_current=lambda: self.is_current(lease),
            )
            if not self.is_current(lease):
                raise SupersededChatTurn("companion turn superseded")
        finally:
            self.turn_controller.finish_assistant_turn(lease)
        return PipecatCompanionReply(
            request_id=result.request_id,
            session_id=result.session_id,
            text=result.assistant_message.content,
            emotion=result.presentation_emotion,
            replayed=result.replayed,
        )


def _explicit_frame_request_id(frame: Any) -> str | None:
    """Optional receipt retry key; it cannot override session/persona authority."""
    metadata = getattr(frame, "metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("invalid frame metadata")
    if "mygpt" not in metadata:
        return None
    control = metadata["mygpt"]
    if not isinstance(control, dict):
        raise ValueError("invalid MyGPT frame metadata")
    if "request_id" not in control:
        return None
    value = control["request_id"]
    if not isinstance(value, str) or not value:
        raise ValueError("explicit request_id must be a nonempty string")
    # Identifier syntax/length are validated by CompanionChatRequest, not a
    # second divergent transport schema. Invalid values never fall back to new.
    return value


# The upstream full Markdown filter intentionally discards some punctuation.
# Learning replies need literal operators/code/cell boundaries, so only a
# narrow, flat heading/link presentation subset is eligible for conversion.
_MAX_SPEECH_FILTER_CHARS = 1200
_FLAT_SPEECH_LINK = re.compile(r"\[([^\[\]\n]{1,200})\]\((https?://[^\s()]{1,500})\)")


def _speech_filter_eligible(text: str) -> bool:
    if len(text) > _MAX_SPEECH_FILTER_CHARS:
        return False
    if any(char in text for char in "`*|_\\<>§&~") or "![" in text:
        return False
    if sum(text.count(char) for char in "[]()") > 16:
        return False
    # Keep signs, list numbering and separators rather than asking a Markdown
    # renderer whether they were mathematical content or presentation syntax.
    if re.search(r"(?m)^[ \t]*(?:[-+=>]|[0-9]+[.)][ \t])", text):
        return False
    plain, links = _FLAT_SPEECH_LINK.subn(r"\1", text)
    if any(char in plain for char in "[]()"):
        return False
    heading = re.search(r"(?m)^#{1,6}[ \t]+[^\n]*\w", text)
    return bool(links or heading)


def _filter_speech_blocking(text: str) -> str:
    """Execute the actual pinned upstream filter off the event loop."""
    from pipecat.utils.text.markdown_text_filter import MarkdownTextFilter

    formatter = MarkdownTextFilter(params=MarkdownTextFilter.InputParams(
        enable_text_filter=True,
        filter_code=False,
        filter_tables=False,
        filter_repeated_sequences=False,
    ))
    return asyncio.run(formatter.filter(text))


async def _format_speech_text(text: str) -> str:
    """Use pinned Pipecat formatting only for short, unambiguous headings/links.

    Source blob 08b2a1f743d8cf7d2faa937915e97f52e3997d04, BSD-2-Clause (Daily).
    Unsafe/complex syntax is preserved verbatim, not guessed or truncated. The
    bounded eligible subset runs in a worker; interruption abandons its result,
    not the thread itself. A fresh filter avoids cross-response state.
    """
    if not _speech_filter_eligible(text):
        return text
    return await asyncio.to_thread(_filter_speech_blocking, text)


def create_pipecat_companion_processor(
    bridge: PipecatCompanionBridge,
    *,
    forward_transcription: bool = False,
    frame_processor_base: type[Any] | None = None,
    frame_types: Any | None = None,
    downstream_direction: Any | None = None,
    speech_formatter: Callable[[str], Awaitable[str]] | None = None,
) -> Any:
    """Create a Pipecat FrameProcessor lazily.

    Tests may inject frame types, processor base and the speech formatter.
    Production uses conservative pinned Pipecat heading/link speech presentation
    while durable/native replies retain their original text. Production lazily
    imports the pinned Pipecat API. Final downstream transcriptions become
    Start -> LLMText -> End, so TTS flushes short responses. Interruption and
    CancelFrame invalidate the turn before Pipecat cancels its processing task.
    EndFrame is graceful: it closes after previously queued work has drained.
    """
    if frame_processor_base is None or frame_types is None or downstream_direction is None:
        try:
            from pipecat.frames import frames
            from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
        except ImportError as exc:
            raise RuntimeError(
                "Pipecat is optional; install brain[realtime] before enabling the bridge"
            ) from exc
        frame_processor_base = frame_processor_base or FrameProcessor
        frame_types = frame_types or frames
        downstream_direction = downstream_direction or FrameDirection.DOWNSTREAM

    format_speech = speech_formatter or _format_speech_text

    class CompanionProcessor(frame_processor_base):  # type: ignore[misc, valid-type]
        async def process_frame(self, frame: Any, direction: Any):
            # Invalidate before super(): Pipecat's interruption handler awaits
            # task cancellation, and a provider may take time to acknowledge it.
            if isinstance(frame, frame_types.InterruptionFrame):
                bridge.interrupt()
            elif isinstance(frame, (frame_types.CancelFrame, frame_types.EndFrame)):
                bridge.close()
            await super().process_frame(frame, direction)
            if isinstance(frame, frame_types.TranscriptionFrame) and direction == downstream_direction:
                text = str(getattr(frame, "text", "") or "").strip()
                finalized = bool(getattr(frame, "finalized", True))
                if bridge.closed:
                    return
                if not text or not finalized:
                    if forward_transcription:
                        await self.push_frame(frame, direction)
                    return
                lease = bridge.begin_turn()
                if forward_transcription:
                    await self.push_frame(frame, direction)
                # Adapted from Pipecat BaseOpenAILLMService.process_frame:
                # start/end lifecycle frames are part of the TTS contract.
                reply = None
                try:
                    if not bridge.is_current(lease):
                        return
                    await self.push_frame(frame_types.LLMFullResponseStartFrame(), direction)
                    reply = await bridge.respond(text, request_id=_explicit_frame_request_id(frame), lease=lease)
                    if reply.replayed:
                        # Receipt recovery retrieves stored data, not a new
                        # speech command. No formatter/synthesis side effect.
                        return
                    if bridge.is_current(lease):
                        try:
                            # Isolate callback cancellation from this queue's
                            # owner, including a callback that uncancels itself.
                            speech_text = await asyncio.ensure_future(format_speech(reply.text))
                        finally:
                            owner = asyncio.current_task()
                            if owner is not None and owner.cancelling():
                                raise asyncio.CancelledError
                        if not isinstance(speech_text, str):
                            raise TypeError("invalid speech formatter result")
                    if bridge.is_current(lease):
                        output = frame_types.LLMTextFrame(speech_text)
                        output.metadata["mygpt"] = {
                            "request_id": reply.request_id,
                            "presentation_emotion": reply.emotion,
                            "replayed": False,
                        }
                        await self.push_frame(output, direction)
                except SupersededChatTurn:
                    pass
                except Exception:
                    # No raw provider error, user transcript or credentials in
                    # pipeline error output. Cancellation remains a BaseException.
                    await self.push_error(error_msg="MyGPT companion reply unavailable")
                finally:
                    # An interruption frame already clears downstream TTS. Do
                    # not flush stale text/end frames after that invalidation.
                    if bridge.is_current(lease):
                        end = frame_types.LLMFullResponseEndFrame()
                        if reply is not None:
                            end.metadata["mygpt"] = {
                                "request_id": reply.request_id, "replayed": reply.replayed,
                            }
                        await self.push_frame(end, direction)
                return
            await self.push_frame(frame, direction)

        async def cleanup(self):
            bridge.close()
            await super().cleanup()

    return CompanionProcessor()
