import pytest

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.pipecat_bridge import (
    PipecatCompanionBridge,
    create_pipecat_companion_processor,
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

    class Base:
        def __init__(self):
            self.pushed = []

        async def process_frame(self, frame, direction):
            return None

        async def push_frame(self, frame, direction):
            self.pushed.append((frame, direction))

    class Transcription:
        def __init__(self, text, finalized=True):
            self.text = text
            self.finalized = finalized

    class Text:
        def __init__(self, text):
            self.text = text

    processor = create_pipecat_companion_processor(
        bridge,
        frame_processor_base=Base,
        transcription_frame_type=Transcription,
        text_frame_type=Text,
    )

    await processor.process_frame(Transcription("半句", finalized=False), "down")
    assert processor.pushed == []

    await processor.process_frame(Transcription("完整一句", finalized=True), "down")
    assert len(processor.pushed) == 1
    assert processor.pushed[0][0].text == "收到"
