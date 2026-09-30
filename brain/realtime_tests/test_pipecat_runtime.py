"""Exercise installed Pipecat 1.12.0 queues, frames and TTS aggregation offline.

These tests do not mock FrameProcessor. Synthesis is replaced with a probe at
the final text handoff; no audio device, model, provider or network is used.
"""
import asyncio
from importlib.metadata import version
from types import SimpleNamespace

import pytest
from loguru import logger
from pipecat.clocks.system_clock import SystemClock
from pipecat.frames import frames
from pipecat.processors.frame_processor import FrameDirection, FrameProcessorSetup
from pipecat.services.tts_service import TTSService
from pipecat.services.settings import TTSSettings
from pipecat.utils.asyncio.task_manager import TaskManager

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.pipecat_bridge import PipecatCompanionBridge, create_pipecat_companion_processor
from mygpt_brain.session_store import ChatSessionStore

DOWN = FrameDirection.DOWNSTREAM


class TTSProbe(TTSService):
    def __init__(self):
        super().__init__(enable_direct_mode=True, settings=TTSSettings(model=None, voice=None, language=None))
        self.spoken = []
        self.ready = asyncio.Event()

    async def run_tts(self, text, context_id):
        raise AssertionError("No synthesis provider is used in this offline test")
        yield None

    async def _push_tts_frames(self, frame, **kwargs):
        self.spoken.append(frame.text)
        self.ready.set()


def runtime_for(responder, store=None):
    return CompanionChatRuntime(
        persona=CompanionPersona(persona_id="p1", display_name="P", visual_skin_id="3714430278", instructions="Trusted."),
        responder=responder, session_store=store,
    )


def setup_for():
    return FrameProcessorSetup(
        clock=SystemClock(), task_manager=TaskManager(), pipeline_worker=SimpleNamespace(),
    )


def transcript(text):
    return frames.TranscriptionFrame(text=text, user_id="local-user", timestamp="2026-09-30T18:00:00Z", finalized=True)


@pytest.mark.asyncio
async def test_actual_tts_requires_end_frame_to_flush_short_text():
    assert version("pipecat-ai") == "1.12.0"
    tts = TTSProbe()
    await tts.setup(setup_for())
    try:
        await tts.process_frame(frames.LLMFullResponseStartFrame(), DOWN)
        await tts.process_frame(frames.LLMTextFrame("继续学这一节"), DOWN)
        assert tts.spoken == []  # The previous TextFrame-only bridge stopped here.
        await tts.process_frame(frames.LLMFullResponseEndFrame(), DOWN)
        assert tts.spoken == ["继续学这一节"]
    finally:
        await tts.cleanup()


@pytest.mark.asyncio
async def test_production_factory_real_queue_flushes_clean_act_speech():
    async def responder(_prompt): return '继续学这一节<|ACT:{"emotion":"happy"}|>'
    bridge = PipecatCompanionBridge(runtime_for(responder), session_id="s1")
    processor = create_pipecat_companion_processor(bridge)
    tts = TTSProbe()
    processor.link(tts)
    setup = setup_for()
    await processor.setup(setup)
    await tts.setup(setup)
    emitted = []
    @processor.event_handler("on_before_push_frame")
    async def record(_processor, frame): emitted.append(frame)
    try:
        await processor.queue_frame(frames.StartFrame())
        await processor.queue_frame(transcript("继续学习"))
        await asyncio.wait_for(tts.ready.wait(), 2)
        assert tts.spoken == ["继续学这一节"]
        reply = next(f for f in emitted if isinstance(f, frames.LLMTextFrame))
        assert reply.metadata["mygpt"]["presentation_emotion"] == "happy"
        assert [type(f) for f in emitted if isinstance(f, (frames.LLMFullResponseStartFrame, frames.LLMTextFrame, frames.LLMFullResponseEndFrame))] == [
            frames.LLMFullResponseStartFrame, frames.LLMTextFrame, frames.LLMFullResponseEndFrame,
        ]
    finally:
        await processor.cleanup()
        await tts.cleanup()
    assert setup.task_manager.current_tasks() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", [frames.InterruptionFrame, frames.CancelFrame])
@pytest.mark.parametrize("fail_after_cancel", [False, True])
async def test_real_queue_interrupts_running_model_without_stale_speech_or_commit(tmp_path, ending, fail_after_cancel):
    entered, cancelled = asyncio.Event(), asyncio.Event()
    async def responder(_prompt):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            # Deliberately hostile to cancellation: finishing still must not
            # create stale speech/history after the turn was invalidated.
            if fail_after_cancel:
                raise RuntimeError("obsolete provider failure")
            return "迟到的旧回复"
    with ChatSessionStore(tmp_path / "chat.sqlite3") as store:
        runtime = runtime_for(responder, store)
        bridge = PipecatCompanionBridge(runtime, session_id="s1")
        processor = create_pipecat_companion_processor(bridge)
        setup = setup_for()
        await processor.setup(setup)
        logs = []
        log_sink = logger.add(lambda message: logs.append(str(message)))
        seen = []
        ended = asyncio.Event()
        fresh = asyncio.Event()
        @processor.event_handler("on_before_push_frame")
        async def record(_processor, frame):
            seen.append(frame)
            if isinstance(frame, ending): ended.set()
            if isinstance(frame, frames.LLMTextFrame): fresh.set()
        try:
            await processor.queue_frame(frames.StartFrame())
            await processor.queue_frame(transcript("旧问题"))
            await asyncio.wait_for(entered.wait(), 2)
            await processor.queue_frame(ending())
            await asyncio.wait_for(ended.wait(), 2)
            assert cancelled.is_set()
            assert not any("timed out waiting for task to cancel" in line for line in logs)
            assert not any(isinstance(f, (frames.LLMTextFrame, frames.LLMFullResponseEndFrame)) for f in seen)
            assert not any(isinstance(f, frames.ErrorFrame) for f in seen)
            assert store.load_messages("s1") == []
            assert runtime.session_messages("s1") == []
            if ending is frames.InterruptionFrame:
                async def recover(_prompt): return "新的回答"
                runtime.responder = recover
                await processor.queue_frame(transcript("新问题"))
                await asyncio.wait_for(fresh.wait(), 2)
                assert [f.text for f in seen if isinstance(f, frames.LLMTextFrame)] == ["新的回答"]
                assert [m.content for m in store.load_messages("s1")] == ["Trusted.", "新问题", "新的回答"]
        finally:
            await processor.cleanup()
            logger.remove(log_sink)
        assert setup.task_manager.current_tasks() == []


@pytest.mark.asyncio
async def test_real_end_frame_gracefully_drains_current_reply_before_closing():
    entered, release, ended = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def responder(_prompt):
        entered.set()
        await release.wait()
        return "完成当前回答"
    runtime = runtime_for(responder)
    bridge = PipecatCompanionBridge(runtime, session_id="s1")
    processor = create_pipecat_companion_processor(bridge)
    setup = setup_for()
    await processor.setup(setup)
    emitted = []
    @processor.event_handler("on_before_push_frame")
    async def record(_processor, frame):
        emitted.append(frame)
        if isinstance(frame, frames.EndFrame): ended.set()
    try:
        await processor.queue_frame(frames.StartFrame())
        await processor.queue_frame(transcript("完成后结束"))
        await asyncio.wait_for(entered.wait(), 2)
        await processor.queue_frame(frames.EndFrame())
        assert not bridge.closed
        release.set()
        await asyncio.wait_for(ended.wait(), 2)
        assert bridge.closed
        assert [type(f) for f in emitted if not isinstance(f, frames.StartFrame)] == [
            frames.LLMFullResponseStartFrame, frames.LLMTextFrame,
            frames.LLMFullResponseEndFrame, frames.EndFrame,
        ]
        assert runtime.session_messages("s1")[-1].content == "完成当前回答"
    finally:
        await processor.cleanup()
    assert setup.task_manager.current_tasks() == []
