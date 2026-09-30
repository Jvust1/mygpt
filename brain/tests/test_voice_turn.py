from types import SimpleNamespace

from mygpt_brain.voice_turn import VoiceGateState, VoiceTurnGate


class Wake:
    def __init__(self, triggered=True):
        self.triggered = triggered
        self.reset_called = 0
    def process(self, _frame):
        return SimpleNamespace(triggered=self.triggered, label="hey_mygpt", score=0.9)
    def reset(self):
        self.reset_called += 1


class VAD:
    def __init__(self, speech=True):
        self.speech = speech
        self.reset_called = 0
    def has_speech(self, frames):
        assert list(frames)
        return self.speech
    def reset(self):
        self.reset_called += 1


def test_wake_then_speech_reaches_ready_state():
    gate = VoiceTurnGate(Wake(True), VAD(True))
    wake = gate.process_wake_frame(b"wake")
    assert wake.activated is True
    assert wake.state is VoiceGateState.WAIT_SPEECH
    speech = gate.confirm_speech([b"pcm"])
    assert speech.speech_detected is True
    assert speech.state is VoiceGateState.READY
    assert gate.consume_ready() is True
    assert gate.state is VoiceGateState.WAIT_WAKE


def test_false_vad_returns_to_wait_wake():
    gate = VoiceTurnGate(Wake(True), VAD(False))
    gate.process_wake_frame(b"wake")
    result = gate.confirm_speech([b"noise"])
    assert result.speech_detected is False
    assert gate.state is VoiceGateState.WAIT_WAKE


def test_gate_ignores_vad_before_wake():
    gate = VoiceTurnGate(Wake(False), VAD(True))
    assert gate.confirm_speech([b"pcm"]).state is VoiceGateState.WAIT_WAKE
