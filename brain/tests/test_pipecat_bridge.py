import pytest
import asyncio

from fixtures_pipecat import Frames, create_processor

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.pipecat_bridge import (
    PipecatCompanionBridge,
)


@pytest.mark.asyncio
async def test_bridge_turns_transcript_into_companion_reply():
    async def responder(_prompt):
        return "继续学习，我在。"

    persona = CompanionPersona(
        persona_id="airi-3714430278",
        display_name="MyGPT",
        visual_skin_id="3714430278",
        instructions="7分监督，3分陪伴。",
    )
    runtime = CompanionChatRuntime(persona=persona, responder=responder)
    bridge = PipecatCompanionBridge(runtime, session_id="voice-session")

    reply = await bridge.respond("继续泛函分析")
    assert reply.session_id == "voice-session"
    assert reply.text == "继续学习，我在。"
    assert reply.request_id.startswith("pipecat-")


@pytest.mark.asyncio
async def test_pipecat_processor_handles_only_finalized_transcriptions():
    async def responder(_prompt):
        return "收到"

    persona = CompanionPersona(
        persona_id="p1",
        display_name="P",
        visual_skin_id="3714430278",
        instructions="陪伴。",
    )
    bridge = PipecatCompanionBridge(
        CompanionChatRuntime(persona=persona, responder=responder),
        session_id="s1",
    )

    processor = create_processor(bridge)

    await processor.process_frame(Frames.TranscriptionFrame("半句", finalized=False), "down")
    assert processor.pushed == []

    await processor.process_frame(Frames.TranscriptionFrame("完整一句", finalized=True), "down")
    assert [type(frame) for frame, _ in processor.pushed] == [
        Frames.LLMFullResponseStartFrame, Frames.LLMTextFrame, Frames.LLMFullResponseEndFrame,
    ]
    assert processor.pushed[1][0].text == "收到"
    assert processor.pushed[1][0].metadata["mygpt"]["presentation_emotion"] == "neutral"


def runtime_for(responder, store=None):
    return CompanionChatRuntime(
        persona=CompanionPersona(persona_id="p1", display_name="P", visual_skin_id="3714430278", instructions="Trusted."),
        responder=responder, session_store=store,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("frame_type", [Frames.InterruptionFrame, Frames.CancelFrame, Frames.EndFrame])
async def test_interrupt_and_shutdown_reject_late_reply_before_sqlite_commit(tmp_path, frame_type):
    from mygpt_brain.session_store import ChatSessionStore
    entered, release = asyncio.Event(), asyncio.Event()
    async def responder(_prompt):
        entered.set()
        await release.wait()
        return '旧回复<|ACT:{"emotion":"happy"}|>'
    with ChatSessionStore(tmp_path / "chat.sqlite3") as store:
        runtime = runtime_for(responder, store)
        bridge = PipecatCompanionBridge(runtime, session_id="s1")
        processor = create_processor(bridge)
        old = asyncio.create_task(processor.process_frame(Frames.TranscriptionFrame("旧问题"), "down"))
        await asyncio.wait_for(entered.wait(), 1)
        await processor.process_frame(frame_type(), "down")
        release.set()
        await old
        assert not any(isinstance(f, (Frames.LLMTextFrame, Frames.LLMFullResponseEndFrame)) for f, _ in processor.pushed)
        assert store.load_messages("s1") == []
        assert runtime.session_messages("s1") == []
        assert not bridge.turn_controller.assistant_active


@pytest.mark.asyncio
async def test_interrupted_turn_recovers_with_only_fresh_response():
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0
    async def responder(_prompt):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
            return "旧回复"
        return "新回复"
    runtime = runtime_for(responder)
    bridge = PipecatCompanionBridge(runtime, session_id="s1")
    processor = create_processor(bridge)
    old = asyncio.create_task(processor.process_frame(Frames.TranscriptionFrame("old"), "down"))
    await entered.wait()
    await processor.process_frame(Frames.InterruptionFrame(), "down")
    release.set()
    await old
    await processor.process_frame(Frames.TranscriptionFrame("new"), "down")
    assert [f.text for f, _ in processor.pushed if isinstance(f, Frames.LLMTextFrame)] == ["新回复"]
    assert [m.content for m in runtime.session_messages("s1")] == ["Trusted.", "new", "新回复"]


@pytest.mark.asyncio
async def test_upstream_transcription_is_forwarded_without_model_call():
    async def responder(_prompt): raise AssertionError("upstream input must not generate")
    processor = create_processor(PipecatCompanionBridge(runtime_for(responder), session_id="s1"))
    frame = Frames.TranscriptionFrame("upstream")
    await processor.process_frame(frame, "up")
    assert processor.pushed == [(frame, "up")]


@pytest.mark.asyncio
async def test_provider_error_closes_response_without_leaking_details():
    async def responder(_prompt): raise RuntimeError("private provider URL and prompt")
    bridge = PipecatCompanionBridge(runtime_for(responder), session_id="s1")
    processor = create_processor(bridge)
    await processor.process_frame(Frames.TranscriptionFrame("hello"), "down")
    assert [type(f) for f, _ in processor.pushed] == [Frames.LLMFullResponseStartFrame, Frames.LLMFullResponseEndFrame]
    assert processor.errors == ["MyGPT companion reply unavailable"]
    assert not bridge.turn_controller.assistant_active


@pytest.mark.asyncio
async def test_closed_processor_never_calls_model_and_cleanup_invalidates_bridge():
    async def responder(_prompt): raise AssertionError("closed session")
    bridge = PipecatCompanionBridge(runtime_for(responder), session_id="s1")
    processor = create_processor(bridge)
    await processor.cleanup()
    assert processor.cleaned and bridge.closed
    await processor.process_frame(Frames.TranscriptionFrame("late"), "down")
    with pytest.raises(RuntimeError, match="closed"):
        await bridge.respond("late")


@pytest.mark.asyncio
async def test_optional_transcription_forwarding_precedes_response_frames():
    async def responder(_prompt): return "ok"
    processor = create_processor(PipecatCompanionBridge(runtime_for(responder), session_id="s1"), forward_transcription=True)
    frame = Frames.TranscriptionFrame("hello")
    await processor.process_frame(frame, "down")
    assert [type(f) for f, _ in processor.pushed] == [Frames.TranscriptionFrame, Frames.LLMFullResponseStartFrame, Frames.LLMTextFrame, Frames.LLMFullResponseEndFrame]


@pytest.mark.asyncio
async def test_queued_superseded_turn_never_invokes_provider():
    from mygpt_brain.companion_chat import SupersededChatTurn
    called = False
    async def responder(_prompt):
        nonlocal called
        called = True
        return "must not run"
    runtime = runtime_for(responder)
    with pytest.raises(SupersededChatTurn):
        await runtime.send(dict(request_id="r1", session_id="s1", persona_id="p1", text="old"), is_current=lambda: False)
    assert not called
    assert runtime.session_messages("s1") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_after_cancel", [False, True])
async def test_provider_swallowing_cancel_cannot_resurrect_runtime_task(fail_after_cancel):
    entered = asyncio.Event()
    async def responder(_prompt):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            if fail_after_cancel:
                raise RuntimeError("obsolete provider failure")
            return "late"
    runtime = runtime_for(responder)
    task = asyncio.create_task(runtime.send(dict(request_id="r1", session_id="s1", persona_id="p1", text="old")))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
    assert runtime.session_messages("s1") == []


@pytest.mark.asyncio
async def test_speech_projection_leaves_original_reply_history_and_emotion_intact():
    async def responder(_): return '**学习**<|ACT:{"emotion":"happy"}|>'
    async def format_speech(text):
        assert text == "**学习**"
        return "学习"
    runtime = runtime_for(responder)
    processor = create_processor(PipecatCompanionBridge(runtime, session_id="s1"), speech_formatter=format_speech)
    await processor.process_frame(Frames.TranscriptionFrame("question"), "down")
    output = next(f for f, _ in processor.pushed if isinstance(f, Frames.LLMTextFrame))
    assert output.text == "学习" and output.metadata["mygpt"]["presentation_emotion"] == "happy"
    assert runtime.session_messages("s1")[-1].content == "**学习**"


@pytest.mark.asyncio
@pytest.mark.parametrize("result", ["", " \n "])
async def test_empty_speech_projection_still_completes_response_lifecycle(result):
    async def responder(_): return "![diagram](local-reference)"
    async def format_speech(_): return result
    runtime = runtime_for(responder)
    processor = create_processor(PipecatCompanionBridge(runtime, session_id="s1"), speech_formatter=format_speech)
    await processor.process_frame(Frames.TranscriptionFrame("question"), "down")
    assert [type(f) for f, _ in processor.pushed] == [Frames.LLMFullResponseStartFrame, Frames.LLMTextFrame, Frames.LLMFullResponseEndFrame]
    assert processor.pushed[1][0].text == result
    assert runtime.session_messages("s1")[-1].content == "![diagram](local-reference)"
    assert not processor.errors


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_after_cancel", [False, True])
async def test_formatter_cannot_swallow_queue_cancellation_even_after_uncancel(fail_after_cancel):
    entered = asyncio.Event()
    async def responder(_): return "**old**"
    async def stubborn_formatter(_):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            asyncio.current_task().uncancel()
            if fail_after_cancel:
                raise RuntimeError("private formatter details")
            return "stale speech"
    runtime = runtime_for(responder)
    processor = create_processor(PipecatCompanionBridge(runtime, session_id="s1"), speech_formatter=stubborn_formatter)
    task = asyncio.create_task(processor.process_frame(Frames.TranscriptionFrame("old"), "down"))
    await entered.wait()
    await processor.process_frame(Frames.InterruptionFrame(), "down")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not any(isinstance(f, (Frames.LLMTextFrame, Frames.LLMFullResponseEndFrame)) for f, _ in processor.pushed)
    assert not processor.errors
    # Inference already finished while authorized; interruption does not undo it.
    assert runtime.session_messages("s1")[-1].content == "**old**"


@pytest.mark.asyncio
async def test_formatter_failure_is_sanitized_and_fresh_turn_recovers():
    calls = 0
    async def responder(_): return "**answer**"
    async def formatter(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("private details")
        return "answer"
    processor = create_processor(PipecatCompanionBridge(runtime_for(responder), session_id="s1"), speech_formatter=formatter)
    await processor.process_frame(Frames.TranscriptionFrame("one"), "down")
    assert processor.errors == ["MyGPT companion reply unavailable"]
    assert not any(isinstance(f, Frames.LLMTextFrame) for f, _ in processor.pushed)
    await processor.process_frame(Frames.TranscriptionFrame("two"), "down")
    assert [f.text for f, _ in processor.pushed if isinstance(f, Frames.LLMTextFrame)] == ["answer"]


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "2 * 3 = 6", "`a|b`", "`a**b`", "|1|2|", "## Heading\n2 * 3 = 6",
    "先看 **定义**，再做 [练习](https://example.invalid/book)。",
    "[" * 4000 + "]" * 4000, "## Heading\n[[nested]]", "## Heading\n- 1",
    "## Heading\n1. first\n2. second", "## Heading\nx_1", "## Heading\n§12",
])
async def test_conservative_speech_gate_preserves_ambiguous_or_complex_content(monkeypatch, text):
    from mygpt_brain.pipecat_bridge import _format_speech_text
    def forbidden(_):
        raise AssertionError("Unsafe Markdown must not enter the upstream parser")
    monkeypatch.setattr("mygpt_brain.pipecat_bridge._filter_speech_blocking", forbidden)
    assert await _format_speech_text(text) == text
