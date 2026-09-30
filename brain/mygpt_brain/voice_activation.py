"""Wake-word -> transcription -> companion-chat composition.

This composes existing mygpt boundaries without opening microphones or choosing
an ASR backend. Callers inject a local transcriber (for example the existing
Sherpa path) and supply already-buffered utterance audio.

Cancellation ownership is adapted from Pipecat TaskManager.cancel_task at
49dea682fb84bfc515d881d00dfeaaa9e9f1075f. Copyright (c) 2024–2026, Daily.
BSD-2-Clause; see third_party/pipecat/LICENSE and NOTICE.md.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .companion_chat import CompanionChatResult, CompanionChatRuntime, SupersededChatTurn
from .wakeword import OpenWakeWordGate, WakeWordResult
from .turn_control import VoiceTurnController


Transcriber = Callable[[bytes], Awaitable[str]]
_VOICE_OWNERS: ContextVar[tuple[tuple[Any, asyncio.Task], ...]] = ContextVar(
    "mygpt_voice_owners", default=(),
)


@dataclass(frozen=True)
class VoiceActivationResult:
    wakeword: WakeWordResult
    transcript: str = ""
    chat: CompanionChatResult | None = None
    interrupted_previous: bool = False
    superseded: bool = False


async def _cancel_owned_task(task: asyncio.Task) -> None:
    """Port Pipecat's child-vs-caller cancellation distinction, without logging.

    Local ASR providers must cooperate with asyncio cancellation. This does not
    claim to forcibly stop native inference running in another thread/process.
    """
    caller = asyncio.current_task()
    if task is caller:
        return
    cancels_requested = caller.cancelling() if caller else 0
    if not task.cancelling():
        task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        # The old process() caller owns its error/result. Obsolete child
        # errors must not poison the next utterance or expose provider data.
        pass
    finally:
        # A cancelled child is expected; a new cancellation of the caller is
        # not. Preserve the latter rather than letting teardown outlive it.
        if caller is not None and caller.cancelling() > cancels_requested:
            raise asyncio.CancelledError


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
        self.turn_controller = turn_controller or VoiceTurnController()
        self._task: asyncio.Task[VoiceActivationResult] | None = None
        self._owned_tasks: set[asyncio.Task[VoiceActivationResult]] = set()
        self._closed = False

    async def _cancel_active(self) -> bool:
        task = self._task
        self._task = None
        active = task is not None and not task.done()
        if active:
            await _cancel_owned_task(task)
        return active

    async def interrupt(self) -> None:
        """Discard this utterance and stop its owned asynchronous ASR/model work."""
        self.turn_controller.begin_user_turn()
        self._task = None
        caller = asyncio.current_task()
        # Context follows helper tasks spawned by an ASR/model callback too.
        # Looking only at current_task() misses await create_task(close()).
        owners = {task for runtime, task in _VOICE_OWNERS.get() if runtime is self}
        reentrant = caller in self._owned_tasks or bool(owners)
        # Include an older task whose cancellation is still unwinding while a
        # newer process() is waiting. Keep ownership until its done callback.
        for task in tuple(self._owned_tasks):
            if not task.done():
                if reentrant:
                    # An owned ASR/model task must never join another owned
                    # task: that task may already be awaiting its completion.
                    # Signal peers and let an external close() join them.
                    if task is not caller and task not in owners and not task.cancelling():
                        task.cancel()
                else:
                    await _cancel_owned_task(task)

    async def close(self) -> None:
        """Close and join from outside; reentrant callers only signal teardown."""
        self._closed = True
        await self.interrupt()

    async def process(
        self,
        *,
        wake_frame: Any,
        utterance_audio: bytes,
        request_id: str,
        session_id: str,
        speech_frames: list[Any] | None = None,
    ) -> VoiceActivationResult:
        process_owner = asyncio.current_task()
        if self._closed:
            raise RuntimeError("voice activation runtime is closed")
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

        lease = self.turn_controller.begin_user_turn()
        cancelled_previous = await self._cancel_active()
        interrupted_previous = cancelled_previous or lease.interrupted_previous
        def current() -> bool:
            return (
                not self._closed
                and not (process_owner is not None and process_owner.cancelling())
                and self.turn_controller.is_current(lease)
            )
        def superseded() -> VoiceActivationResult:
            return VoiceActivationResult(wakeword=wake, superseded=True, interrupted_previous=interrupted_previous)
        if not current():
            if process_owner is not None and process_owner.cancelling():
                raise asyncio.CancelledError
            return superseded()

        async def run_turn() -> VoiceActivationResult:
            owner = asyncio.current_task()
            ownership = _VOICE_OWNERS.set((*_VOICE_OWNERS.get(), (self, owner)))
            try:
                transcript = (await self.transcriber(bytes(utterance_audio))).strip()
                owner = asyncio.current_task()
                if owner is not None and owner.cancelling():
                    raise asyncio.CancelledError
                if not current():
                    raise SupersededChatTurn("voice turn superseded after transcription")
                if not transcript:
                    raise RuntimeError("transcriber returned empty transcript")
                if not self.turn_controller.begin_assistant_turn(lease):
                    raise SupersededChatTurn("voice turn superseded")
                chat = await self.companion.send(
                    {
                        "schema_version": "mygpt.companion-chat.v1",
                        "request_id": request_id,
                        "session_id": session_id,
                        "persona_id": self.companion.persona.persona_id,
                        "text": transcript,
                    },
                    is_current=current,
                )
                if not current():
                    raise SupersededChatTurn("voice turn superseded")
                return VoiceActivationResult(
                    wakeword=wake, transcript=transcript, chat=chat,
                    interrupted_previous=interrupted_previous,
                )
            finally:
                _VOICE_OWNERS.reset(ownership)
                self.turn_controller.finish_assistant_turn(lease)
                owner = asyncio.current_task()
                if owner is not None and owner.cancelling():
                    raise asyncio.CancelledError

        task = asyncio.create_task(run_turn(), name="mygpt-voice-activation")
        self._task = task
        self._owned_tasks.add(task)
        task.add_done_callback(self._owned_tasks.discard)
        try:
            result = await task
            return result if current() else superseded()
        except SupersededChatTurn:
            return superseded()
        except asyncio.CancelledError:
            owner = asyncio.current_task()
            if owner is not None and owner.cancelling():
                raise
            if not current():
                return superseded()
            raise
        except Exception:
            if not current():
                return superseded()
            raise
        finally:
            if self._task is task:
                self._task = None
            # The child may explicitly uncancel itself. That never grants it
            # authority to uncancel the public process() caller or commit a
            # cancelled user turn; current() also guards the precommit path.
            if process_owner is not None and process_owner.cancelling():
                raise asyncio.CancelledError
