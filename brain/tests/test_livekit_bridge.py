import asyncio

from mygpt_brain.livekit_bridge import LiveKitAgentBridge
from mygpt_brain.turn_control import VoiceTurnController


class FakeSession:
    def __init__(self):
        self.started = None
        self.spoken = []

    async def start(self, *, agent, room):
        self.started = (agent, room)

    async def say(self, text, *, allow_interruptions=False):
        self.spoken.append((text, allow_interruptions))
        return "speech-handle"


class Gate:
    def __init__(self, ready):
        self.ready = ready

    def consume_ready(self):
        if not self.ready:
            return False
        self.ready = False
        return True


def test_livekit_bridge_starts_and_speaks():
    async def run():
        session = FakeSession()
        bridge = LiveKitAgentBridge(session)
        await bridge.start(agent="agent", room="room")
        assert bridge.started is True
        result = await bridge.say("你好", allow_interruptions=False)
        assert result == "speech-handle"
        assert session.started == ("agent", "room")
        assert session.spoken == [("你好", False)]
    asyncio.run(run())


def test_livekit_bridge_only_speaks_after_voice_gate_ready():
    async def run():
        session = FakeSession()
        bridge = LiveKitAgentBridge(session)
        await bridge.start(agent="agent", room="room")
        assert await bridge.say_when_ready(Gate(False), "忽略") is False
        assert session.spoken == []
        assert await bridge.say_when_ready(Gate(True), "回应") is True
        assert session.spoken == [("回应", False)]
    asyncio.run(run())



def test_livekit_bridge_skips_stale_turn_after_user_interrupt():
    async def run():
        turns = VoiceTurnController()
        session = FakeSession()
        bridge = LiveKitAgentBridge(session, turn_controller=turns)
        await bridge.start(agent="agent", room="room")

        stale = turns.begin_user_turn()
        assert turns.begin_assistant_turn(stale) is True
        current = turns.begin_user_turn()
        assert current.interrupted_previous is True

        assert await bridge.say_for_turn("旧回复", stale) is None
        assert session.spoken == []
        assert await bridge.say_for_turn("新回复", current) == "speech-handle"
        assert session.spoken == [("新回复", True)]

    asyncio.run(run())
