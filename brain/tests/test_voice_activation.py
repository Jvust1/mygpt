import pytest
import asyncio

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.voice_activation import VoiceActivationRuntime
from mygpt_brain.wakeword import OpenWakeWordGate


class WakeModel:
    def __init__(self, score):
        self.score = score

    def predict(self, _frame):
        return {"hey_mygpt": self.score}


async def responder(prompt):
    last = prompt.window.history[-1]
    return "收到：" + last.content


@pytest.mark.asyncio
async def test_voice_activation_runs_wake_asr_and_chat():
    persona = CompanionPersona(
        persona_id="persona_local",
        display_name="伙伴",
        visual_skin_id="3714430278",
        instructions="陪伴并监督学习。",
    )
    companion = CompanionChatRuntime(persona=persona, responder=responder)

    async def transcriber(audio):
        assert audio == b"utterance"
        return "开始学习泛函分析"

    runtime = VoiceActivationRuntime(
        gate=OpenWakeWordGate(WakeModel(0.9), threshold=0.5),
        transcriber=transcriber,
        companion=companion,
    )
    result = await runtime.process(
        wake_frame=b"wake",
        utterance_audio=b"utterance",
        request_id="req_voice_1",
        session_id="session_voice_1",
    )
    assert result.wakeword.triggered is True
    assert result.transcript == "开始学习泛函分析"
    assert result.chat is not None
    assert result.chat.assistant_message.content == "收到：开始学习泛函分析"


@pytest.mark.asyncio
async def test_voice_activation_stops_before_asr_when_not_triggered():
    called = False

    async def transcriber(_audio):
        nonlocal called
        called = True
        return "不应调用"

    persona = CompanionPersona(
        persona_id="persona_local",
        display_name="伙伴",
        visual_skin_id="3714430278",
        instructions="陪伴并监督学习。",
    )
    runtime = VoiceActivationRuntime(
        gate=OpenWakeWordGate(WakeModel(0.1), threshold=0.5),
        transcriber=transcriber,
        companion=CompanionChatRuntime(persona=persona, responder=responder),
    )
    result = await runtime.process(
        wake_frame=b"wake",
        utterance_audio=b"utterance",
        request_id="req_voice_2",
        session_id="session_voice_2",
    )
    assert result.chat is None
    assert result.transcript == ""
    assert called is False


def make_runtime(transcriber, model_responder=responder, **kwargs):
    persona = CompanionPersona(persona_id="p1", display_name="P", visual_skin_id="3714430278", instructions="Trusted.")
    return VoiceActivationRuntime(
        gate=OpenWakeWordGate(WakeModel(0.9), cooldown_frames=0),
        transcriber=transcriber,
        companion=CompanionChatRuntime(persona=persona, responder=model_responder),
        **kwargs,
    )


async def process(runtime, text="old"):
    return await runtime.process(wake_frame=b"wake", utterance_audio=text.encode(), request_id=text, session_id="s1")


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_after_cancel", [False, True])
async def test_new_wake_cancels_slow_asr_and_rejects_late_result(fail_after_cancel):
    entered = asyncio.Event()
    async def transcribe(audio):
        if audio == b"old":
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                if fail_after_cancel:
                    raise RuntimeError("obsolete ASR error")
                return "late old transcription"
        return "new transcript"
    runtime = make_runtime(transcribe)
    old = asyncio.create_task(process(runtime))
    await entered.wait()
    latest = await process(runtime, "new")
    stale = await old
    assert stale.superseded and stale.chat is None and stale.transcript == ""
    assert latest.interrupted_previous and not latest.superseded
    assert latest.chat.assistant_message.content == "收到：new transcript"
    assert [m.content for m in runtime.companion.session_messages("s1")] == ["Trusted.", "new transcript", "收到：new transcript"]
    assert not runtime.turn_controller.assistant_active
    assert not runtime._owned_tasks


@pytest.mark.asyncio
async def test_new_wake_cancels_inflight_model_before_committing_old_exchange(tmp_path):
    from mygpt_brain.session_store import ChatSessionStore
    entered = asyncio.Event()
    async def transcribe(audio): return audio.decode()
    async def model(prompt):
        text = prompt.window.history[-1].content
        if text == "old":
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return "obsolete reply"
        return "fresh reply"
    runtime = make_runtime(transcribe, model)
    with ChatSessionStore(tmp_path / "chat.sqlite3") as store:
        runtime.companion.session_store = store
        old = asyncio.create_task(process(runtime))
        await entered.wait()
        latest = await process(runtime, "new")
        assert (await old).superseded
        assert latest.chat.assistant_message.content == "fresh reply"
        assert [m.content for m in store.load_messages("s1")] == ["Trusted.", "new", "fresh reply"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["asr", "model", "empty"])
async def test_failure_releases_active_state_and_allows_next_turn(failure_stage):
    async def transcribe(audio):
        if audio == b"old":
            if failure_stage == "asr": raise RuntimeError("ASR failed")
            if failure_stage == "empty": return " "
        return audio.decode()
    async def model(prompt):
        if prompt.window.history[-1].content == "old": raise RuntimeError("model failed")
        return "ok"
    runtime = make_runtime(transcribe, model)
    with pytest.raises(RuntimeError): await process(runtime)
    assert not runtime.turn_controller.assistant_active
    assert not runtime._owned_tasks
    assert (await process(runtime, "new")).chat.assistant_message.content == "ok"


@pytest.mark.asyncio
async def test_external_caller_cancellation_is_not_swallowed():
    entered = asyncio.Event()
    async def transcribe(_audio):
        entered.set()
        try: await asyncio.Event().wait()
        except asyncio.CancelledError: return "ignored cancel"
    runtime = make_runtime(transcribe)
    caller = asyncio.create_task(process(runtime))
    await entered.wait()
    caller.cancel()
    with pytest.raises(asyncio.CancelledError): await caller
    assert caller.cancelled()
    assert runtime.companion.session_messages("s1") == []
    assert not runtime._owned_tasks


@pytest.mark.asyncio
async def test_asr_uncancel_cannot_override_external_owner_cancellation(tmp_path):
    from mygpt_brain.session_store import ChatSessionStore
    entered = asyncio.Event()
    calls = 0
    async def transcribe(_audio):
        entered.set()
        try: await asyncio.Event().wait()
        except asyncio.CancelledError:
            asyncio.current_task().uncancel()
            return "cancelled transcript"
    async def model(_prompt):
        nonlocal calls
        calls += 1
        return "must not run"
    runtime = make_runtime(transcribe, model)
    with ChatSessionStore(tmp_path / "chat.sqlite3") as store:
        runtime.companion.session_store = store
        caller = asyncio.create_task(process(runtime))
        await entered.wait()
        caller.cancel()
        with pytest.raises(asyncio.CancelledError): await caller
        assert caller.cancelled() and calls == 0
        assert store.load_messages("s1") == []
    assert not runtime.turn_controller.assistant_active
    assert not runtime._owned_tasks


@pytest.mark.asyncio
async def test_caller_cancel_while_waiting_for_previous_asr_cleanup_stays_cancelled():
    entered, cleaning = asyncio.Event(), asyncio.Event()
    async def transcribe(_audio):
        entered.set()
        try: await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleaning.set()
            await asyncio.Event().wait()
    runtime = make_runtime(transcribe)
    old = asyncio.create_task(process(runtime))
    await entered.wait()
    new = asyncio.create_task(process(runtime, "new"))
    await cleaning.wait()
    new.cancel()
    with pytest.raises(asyncio.CancelledError): await new
    assert (await old).superseded
    assert not runtime._owned_tasks


@pytest.mark.asyncio
async def test_close_joins_retiring_asr_and_prevents_restart():
    entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def transcribe(_audio):
        entered.set()
        try: await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleaning.set()
            await release.wait()
            return "late"
    runtime = make_runtime(transcribe)
    old = asyncio.create_task(process(runtime))
    await entered.wait()
    new = asyncio.create_task(process(runtime, "new"))
    await cleaning.wait()
    closed = asyncio.create_task(runtime.close())
    await asyncio.sleep(0)
    assert not closed.done()
    release.set()
    await closed
    assert (await old).superseded and (await new).superseded
    assert not runtime._owned_tasks
    with pytest.raises(RuntimeError, match="closed"): await process(runtime, "later")


@pytest.mark.asyncio
async def test_reentrant_close_during_asr_never_awaits_itself():
    async def transcribe(_audio):
        await runtime.close()
        return "late"
    runtime = make_runtime(transcribe)
    result = await asyncio.wait_for(process(runtime), 1)
    assert result.superseded and result.chat is None
    assert not runtime._owned_tasks


@pytest.mark.asyncio
async def test_close_from_asr_helper_task_does_not_join_its_owner():
    async def transcribe(_audio):
        await asyncio.create_task(runtime.close())
        return "late"
    runtime = make_runtime(transcribe)
    result = await asyncio.wait_for(process(runtime), 1)
    assert result.superseded and result.chat is None
    await runtime.close()
    assert not runtime._owned_tasks


@pytest.mark.asyncio
async def test_two_owned_asr_tasks_reentrantly_closing_never_wait_on_each_other():
    entered, cleaning, third_entered, release = (asyncio.Event() for _ in range(4))
    async def transcribe(audio):
        if audio == b"old":
            entered.set()
            try: await asyncio.Event().wait()
            except asyncio.CancelledError:
                cleaning.set()
                await release.wait()
                await runtime.close()
                return "late old"
        if audio == b"third":
            third_entered.set()
            await runtime.close()
            return "late third"
        raise AssertionError("middle turn must not reach ASR")
    runtime = make_runtime(transcribe)
    first = asyncio.create_task(process(runtime))
    await entered.wait()
    middle = asyncio.create_task(process(runtime, "middle"))
    await cleaning.wait()
    third = asyncio.create_task(process(runtime, "third"))
    await third_entered.wait()
    release.set()
    results = await asyncio.wait_for(asyncio.gather(first, middle, third), 1)
    assert all(result.superseded and result.chat is None for result in results)
    await runtime.close()  # External idempotent close joins anything retiring.
    assert not runtime._owned_tasks


@pytest.mark.asyncio
async def test_untriggered_frame_does_not_interrupt_existing_turn():
    entered, release = asyncio.Event(), asyncio.Event()
    async def transcribe(_audio):
        entered.set()
        await release.wait()
        return "active"
    runtime = make_runtime(transcribe)
    active = asyncio.create_task(process(runtime))
    await entered.wait()
    runtime.gate._model.score = 0.1
    quiet = await process(runtime, "noise")
    assert quiet.chat is None and not quiet.superseded
    release.set()
    assert (await active).chat.assistant_message.content == "收到：active"


@pytest.mark.asyncio
async def test_asr_uncancelling_then_failing_does_not_poison_new_turn():
    entered = asyncio.Event()
    async def transcribe(audio):
        if audio == b"old":
            entered.set()
            try: await asyncio.Event().wait()
            except asyncio.CancelledError:
                asyncio.current_task().uncancel()
                raise RuntimeError("obsolete ASR failure")
        return "new"
    runtime = make_runtime(transcribe)
    old = asyncio.create_task(process(runtime))
    await entered.wait()
    assert (await process(runtime, "new")).chat.assistant_message.content == "收到：new"
    assert (await old).superseded


@pytest.mark.asyncio
async def test_new_generation_before_caller_delivery_suppresses_completed_result():
    async def transcribe(_audio): return "old"
    async def model(_prompt): return "completed but not yet delivered"
    runtime = make_runtime(transcribe, model)
    original_send = runtime.companion.send
    async def deliver_after_commit(*args, **kwargs):
        result = await original_send(*args, **kwargs)
        # Queued after actual commit, before the owned task schedules its
        # process() caller continuation: completion and delivery are distinct.
        asyncio.get_running_loop().call_soon(runtime.turn_controller.begin_user_turn)
        return result
    runtime.companion.send = deliver_after_commit
    result = await process(runtime)
    assert result.superseded and result.chat is None
    assert runtime.companion.session_messages("s1")[-1].content == "completed but not yet delivered"


@pytest.mark.asyncio
async def test_wake_barge_in_closes_real_ollama_adapter_stream(monkeypatch):
    import httpx
    import json
    from mygpt_brain.providers import OllamaResponder
    entered = asyncio.Event()
    class OldReply(httpx.AsyncByteStream):
        closed = False
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b"unreachable"
        async def aclose(self): self.closed = True
    old_stream = OldReply()
    def handler(request):
        text = json.loads(request.content)["messages"][-1]["content"]
        if text == "old": return httpx.Response(200, stream=old_stream)
        return httpx.Response(200, json={"message":{"content":'新回复<|ACT:{"emotion":"happy"}|>'}})
    def client_factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr("mygpt_brain.providers._ASYNC_CLIENT", client_factory)
    async def transcribe(audio): return audio.decode()
    runtime = make_runtime(transcribe, OllamaResponder("synthetic-test-model"))
    old = asyncio.create_task(process(runtime))
    await entered.wait()
    latest = await process(runtime, "new")
    assert old_stream.closed and (await old).superseded
    assert latest.chat.assistant_message.content == "新回复"
    assert latest.chat.presentation_emotion == "happy"
    assert [m.content for m in runtime.companion.session_messages("s1")] == ["Trusted.", "new", "新回复"]
