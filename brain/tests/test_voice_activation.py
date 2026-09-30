import pytest

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
