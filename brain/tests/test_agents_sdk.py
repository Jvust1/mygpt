from types import SimpleNamespace

import pytest

from mygpt_brain.agents_sdk import OpenAIAgentsResponder
from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona


class FakeRunner:
    def __init__(self, final_output):
        self.final_output = final_output
        self.calls = []

    async def run(self, agent, *, input, **kwargs):
        self.calls.append({"agent": agent, "input": input, "kwargs": kwargs})
        return SimpleNamespace(final_output=self.final_output)


@pytest.mark.asyncio
async def test_agents_sdk_responder_preserves_mygpt_prompt_authority():
    runner = FakeRunner("继续，我会监督你完成这一节。")
    responder = OpenAIAgentsResponder(
        agent=object(),
        runner=runner,
        run_kwargs={"max_turns": 4},
    )
    persona = CompanionPersona(
        persona_id="airi-3714430278",
        display_name="MyGPT",
        visual_skin_id="3714430278",
        instructions="7分监督，3分陪伴。",
    )
    runtime = CompanionChatRuntime(persona=persona, responder=responder)

    result = await runtime.send(
        {
            "request_id": "agents-r1",
            "session_id": "study-1",
            "persona_id": persona.persona_id,
            "text": "继续学习泛函分析",
        }
    )

    assert result.assistant_message.content == "继续，我会监督你完成这一节。"
    call = runner.calls[0]
    assert call["input"][0]["role"] == "system"
    assert "7分监督" in call["input"][0]["content"]
    assert call["input"][-1]["role"] == "user"
    assert call["input"][-1]["content"] == "继续学习泛函分析"
    assert call["kwargs"]["max_turns"] == 4


@pytest.mark.asyncio
async def test_agents_sdk_responder_accepts_structured_companion_reply():
    runner = FakeRunner({"text": "做得不错。", "emotion": "happy"})
    responder = OpenAIAgentsResponder(agent=object(), runner=runner)
    persona = CompanionPersona(
        persona_id="p1",
        display_name="P",
        visual_skin_id="3714430278",
        instructions="陪伴。",
    )
    result = await CompanionChatRuntime(
        persona=persona,
        responder=responder,
    ).send(
        {
            "request_id": "agents-r2",
            "session_id": "s1",
            "persona_id": "p1",
            "text": "我完成了",
        }
    )
    assert result.assistant_message.content == "做得不错。"
    assert result.presentation_emotion == "happy"


def test_agents_sdk_responder_rejects_sdk_owned_durable_session_state():
    with pytest.raises(ValueError, match="durable conversation state"):
        OpenAIAgentsResponder(
            agent=object(),
            runner=FakeRunner("x"),
            run_kwargs={"session": object()},
        )
