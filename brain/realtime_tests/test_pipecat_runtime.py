"""Exercise installed Pipecat 1.12.0 queues, frames and TTS aggregation offline.

These tests do not mock FrameProcessor. Synthesis is replaced with a probe at
the final text handoff; no audio device, model, provider or network is used.
"""
import asyncio
import json
import httpx
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
from mygpt_brain.providers import OllamaResponder

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


@pytest.mark.asyncio
async def test_real_pipecat_interruption_closes_ollama_http_connection(monkeypatch):
    received, disconnected, interrupted = asyncio.Event(), asyncio.Event(), asyncio.Event()
    connections = set()
    async def serve(reader, writer):
        task = asyncio.current_task()
        connections.add(task)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(int(line.split(b":", 1)[1]) for line in headers.split(b"\r\n") if line.lower().startswith(b"content-length:"))
            payload = json.loads(await reader.readexactly(length))
            assert payload["model"] == "synthetic-cancel-test"
            received.set()
            assert await reader.read() == b""
            disconnected.set()
        finally:
            writer.close()
            await writer.wait_closed()
            connections.discard(task)
    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    class OwnedTestPort(httpx.AsyncBaseTransport):
        def __init__(self): self.inner = httpx.AsyncHTTPTransport()
        async def handle_async_request(self, request):
            assert str(request.url) == "http://127.0.0.1:11434/api/chat"
            request.url = request.url.copy_with(port=port)
            return await self.inner.handle_async_request(request)
        async def aclose(self): await self.inner.aclose()
    clients = []
    def factory(**kwargs):
        client = httpx.AsyncClient(transport=OwnedTestPort(), **kwargs)
        clients.append(client)
        return client
    monkeypatch.setattr("mygpt_brain.providers._ASYNC_CLIENT", factory)
    runtime = runtime_for(OllamaResponder("synthetic-cancel-test"))
    processor = create_pipecat_companion_processor(PipecatCompanionBridge(runtime, session_id="s1"))
    setup = setup_for()
    await processor.setup(setup)
    emitted = []
    @processor.event_handler("on_before_push_frame")
    async def record(_processor, frame):
        emitted.append(frame)
        if isinstance(frame, frames.InterruptionFrame): interrupted.set()
    try:
        await processor.queue_frame(frames.StartFrame())
        await processor.queue_frame(transcript("先等一下"))
        await asyncio.wait_for(received.wait(), 2)
        await processor.queue_frame(frames.InterruptionFrame())
        await asyncio.wait_for(interrupted.wait(), 2)
        await asyncio.wait_for(disconnected.wait(), 2)
        assert clients[0].is_closed
        assert runtime.session_messages("s1") == []
        assert not any(isinstance(f, (frames.LLMTextFrame, frames.ErrorFrame)) for f in emitted)
    finally:
        await processor.cleanup()
        server.close()
        await server.wait_closed()
        for task in list(connections): task.cancel()
        await asyncio.gather(*connections, return_exceptions=True)
    assert setup.task_manager.current_tasks() == []


class SynthesisTextProbe(TTSService):
    """Keep actual aggregation/filter/context machinery; replace synthesis only."""
    def __init__(self):
        super().__init__(enable_direct_mode=True, settings=TTSSettings(model=None, voice=None, language=None))
        self.spoken = []

    async def run_tts(self, text, context_id):
        self.spoken.append(text)
        if False:
            yield None


@pytest.mark.asyncio
@pytest.mark.parametrize("source,expected", [
    ("先看定义，再做 [练习](https://example.invalid/book)。", "先看定义，再做 练习。"),
    ("## 学习数字\n保留 100000 和 aaaaa。", "学习数字 保留 100000 和 aaaaa。"),
    ("## 学习小结\n\n先看定义。", "学习小结 先看定义。"),
    ("使用 `x_1` 与 `x_2`。", "使用 `x_1` 与 `x_2`。"),
    ("![diagram](https://example.invalid/diagram)", "![diagram](https://example.invalid/diagram)"),
])
async def test_real_markdown_filter_reaches_actual_synthesis_boundary_only(tmp_path, source, expected):
    async def responder(_): return source + '<|ACT:{"emotion":"happy"}|>'
    with ChatSessionStore(tmp_path / "speech.sqlite3") as store:
        runtime = runtime_for(responder, store)
        processor = create_pipecat_companion_processor(PipecatCompanionBridge(runtime, session_id="speech"))
        tts = SynthesisTextProbe()
        processor.link(tts)
        setup = setup_for()
        await processor.setup(setup)
        await tts.setup(setup)
        ended = asyncio.Event()
        outputs = []
        @tts.event_handler("on_after_process_frame")
        async def complete(_processor, frame):
            if isinstance(frame, frames.LLMFullResponseEndFrame):
                ended.set()
        @processor.event_handler("on_before_push_frame")
        async def record(_processor, frame):
            if isinstance(frame, frames.LLMTextFrame):
                outputs.append(frame)
        try:
            await processor.queue_frame(frames.StartFrame())
            await processor.queue_frame(transcript("继续学习"))
            await asyncio.wait_for(ended.wait(), 2)
            assert " ".join("".join(tts.spoken).split()) == expected
            assert len(outputs) == 1
            assert outputs[0].metadata["mygpt"]["presentation_emotion"] == "happy"
            assert store.load_messages("speech")[-1].content == source
            assert runtime.session_messages("speech")[-1].content == source
            if not expected:
                assert tts.spoken == []
        finally:
            await processor.cleanup()
            await tts.cleanup()
        assert setup.task_manager.current_tasks() == []


def test_actual_markdown_filter_matches_pinned_source_blob():
    import hashlib
    import inspect
    from pathlib import Path
    from pipecat.utils.text.markdown_text_filter import MarkdownTextFilter
    raw = Path(inspect.getfile(MarkdownTextFilter)).read_bytes()
    assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == "08b2a1f743d8cf7d2faa937915e97f52e3997d04"


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_after_cancel", [False, True])
async def test_actual_queue_cancels_owned_formatter_without_timeout_fallback(fail_after_cancel):
    entered = asyncio.Event()
    interrupted = asyncio.Event()
    calls = 0
    async def responder(_): return "**answer**"
    async def formatter(_):
        nonlocal calls
        calls += 1
        if calls > 1:
            return "fresh"
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            asyncio.current_task().uncancel()
            if fail_after_cancel:
                raise RuntimeError("obsolete private formatting failure")
            return "stale speech"
    runtime = runtime_for(responder)
    processor = create_pipecat_companion_processor(PipecatCompanionBridge(runtime, session_id="s1"), speech_formatter=formatter)
    tts = SynthesisTextProbe()
    processor.link(tts)
    setup = setup_for()
    await processor.setup(setup)
    await tts.setup(setup)
    logs = []
    sink = logger.add(lambda message: logs.append(str(message)))
    fresh = asyncio.Event()
    @tts.event_handler("on_after_process_frame")
    async def complete(_processor, frame):
        if isinstance(frame, frames.InterruptionFrame):
            interrupted.set()
        if isinstance(frame, frames.LLMFullResponseEndFrame):
            fresh.set()
    try:
        await processor.queue_frame(frames.StartFrame())
        await processor.queue_frame(transcript("old"))
        await asyncio.wait_for(entered.wait(), 2)
        await processor.queue_frame(frames.InterruptionFrame())
        await asyncio.wait_for(interrupted.wait(), 2)
        assert not any("timed out waiting for task to cancel" in line for line in logs)
        assert tts.spoken == []
        # The authorized model reply was committed before speech formatting.
        assert runtime.session_messages("s1")[-1].content == "**answer**"
        await processor.queue_frame(transcript("new"))
        await asyncio.wait_for(fresh.wait(), 2)
        assert tts.spoken == ["fresh"]
    finally:
        await processor.cleanup()
        await tts.cleanup()
        logger.remove(sink)
    assert setup.task_manager.current_tasks() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["2 * 3 = 6", "`a|b`", "`a**b`", "|1|2|", "## Math\n2 * 3 = 6", "[" * 4000 + "]" * 4000])
async def test_actual_synthesis_handoff_keeps_operators_code_and_cell_boundaries(source):
    async def responder(_): return source
    processor = create_pipecat_companion_processor(PipecatCompanionBridge(runtime_for(responder), session_id="literal"))
    tts = SynthesisTextProbe()
    processor.link(tts)
    setup = setup_for()
    await processor.setup(setup)
    await tts.setup(setup)
    ended = asyncio.Event()
    @tts.event_handler("on_after_process_frame")
    async def complete(_processor, frame):
        if isinstance(frame, frames.LLMFullResponseEndFrame): ended.set()
    try:
        await processor.queue_frame(frames.StartFrame())
        await processor.queue_frame(transcript("keep the meaning"))
        await asyncio.wait_for(ended.wait(), 2)
        assert "".join(tts.spoken) == source
    finally:
        await processor.cleanup()
        await tts.cleanup()
    assert setup.task_manager.current_tasks() == []


@pytest.mark.asyncio
async def test_actual_upstream_filter_runs_off_loop_and_interruption_discards_worker_result(monkeypatch):
    import threading
    from pipecat.utils.text.markdown_text_filter import MarkdownTextFilter
    original = MarkdownTextFilter.filter
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    observed_threads = []
    main_thread = threading.get_ident()
    async def delayed_filter(self, text):
        observed_threads.append(threading.get_ident())
        if len(observed_threads) == 1:
            entered.set()
            try:
                assert release.wait(3)
                return await original(self, text)
            finally:
                finished.set()
        return await original(self, text)
    monkeypatch.setattr(MarkdownTextFilter, "filter", delayed_filter)
    async def responder(_): return "## Heading\nlearn"
    processor = create_pipecat_companion_processor(PipecatCompanionBridge(runtime_for(responder), session_id="worker"))
    tts = SynthesisTextProbe()
    processor.link(tts)
    setup = setup_for()
    await processor.setup(setup)
    await tts.setup(setup)
    interrupted, fresh = asyncio.Event(), asyncio.Event()
    @tts.event_handler("on_after_process_frame")
    async def complete(_processor, frame):
        if isinstance(frame, frames.InterruptionFrame): interrupted.set()
        if isinstance(frame, frames.LLMFullResponseEndFrame): fresh.set()
    try:
        await processor.queue_frame(frames.StartFrame())
        await processor.queue_frame(transcript("old"))
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 2), 2.5)
        assert observed_threads[0] != main_thread
        await processor.queue_frame(frames.InterruptionFrame())
        await asyncio.wait_for(interrupted.wait(), 2)
        assert not finished.is_set() and tts.spoken == []
        release.set()
        assert await asyncio.wait_for(asyncio.to_thread(finished.wait, 2), 2.5)
        await processor.queue_frame(transcript("new"))
        await asyncio.wait_for(fresh.wait(), 2)
        assert " ".join("".join(tts.spoken).split()) == "Heading learn"
        assert all(thread != main_thread for thread in observed_threads)
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 2)
        await processor.cleanup()
        await tts.cleanup()
    assert setup.task_manager.current_tasks() == []
