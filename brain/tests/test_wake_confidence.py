"""Quiet-first admission for the pre-existing optional wake backend."""
import asyncio
from fractions import Fraction
import math
from types import MappingProxyType

import pytest

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.memory_store import MemoryStore
from mygpt_brain.session_store import ChatSessionStore
from mygpt_brain.voice_activation import VoiceActivationRuntime
from mygpt_brain.wakeword import OpenWakeWordGate


class Model:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.reset_count = 0

    def predict(self, _frame):
        return next(self.rows)

    def reset(self):
        self.reset_count += 1


INVALID = [float("inf"), float("-inf"), float("nan"), -0.1, math.nextafter(1.0, math.inf),
           True, False, "1", b"1", None, [0.9], object(), 10 ** 4000, Fraction(2**54 + 1, 2**54)]
IDS = ["inf", "negative-inf", "nan", "negative", "above-one", "true", "false", "numeric-text",
       "bytes", "none", "array", "object", "overflow", "rounded-above-one"]


@pytest.mark.parametrize("value", INVALID, ids=IDS)
def test_invalid_confidence_cannot_trigger_or_start_cooldown(value):
    gate = OpenWakeWordGate(Model([{"bad": value}, {"wake": 0.5}]), threshold=0.5, cooldown_frames=4)
    result = gate.process(b"pcm")
    assert not result.triggered and result.label == "" and result.score == 0.0
    assert gate.process(b"pcm").triggered  # rejection did not start cooldown


@pytest.mark.parametrize("score,threshold,triggered", [(0, 0.5, False), (1, 1, True),
    (Fraction(1, 2), 0.5, True), (math.nextafter(0.5, 0.0), 0.5, False),
    (0.5, 0.5, True), (math.nextafter(0.5, 1.0), 0.5, True)])
def test_valid_real_scores_keep_exact_threshold_behavior(score, threshold, triggered):
    result = OpenWakeWordGate(Model([{"wake": score}]), threshold=threshold).process(b"pcm")
    assert result.triggered is triggered and result.score == float(score)


def test_mixed_readonly_score_map_selects_best_valid_candidate_without_mutation():
    raw = MappingProxyType({"invalid": float("inf"), "bool": True, "low": 0.6, "best": 0.8, "tie": 0.8})
    result = OpenWakeWordGate(Model([raw]), threshold=0.7).process(b"pcm")
    assert result.triggered and result.label == "best" and result.score == 0.8
    assert list(raw) == ["invalid", "bool", "low", "best", "tie"] and math.isinf(raw["invalid"])


def test_valid_cooldown_and_reset_semantics_are_unchanged():
    model = Model([{"wake": 1}, {"bad": float("inf")}, {"wake": 1}, {"wake": 1}, {"wake": 1}])
    gate = OpenWakeWordGate(model, cooldown_frames=2)
    assert gate.process(b"pcm").triggered
    assert not gate.process(b"pcm").triggered
    assert not gate.process(b"pcm").triggered
    assert gate.process(b"pcm").triggered
    gate.reset()
    assert model.reset_count == 1 and gate.process(b"pcm").triggered


@pytest.mark.parametrize("error", [ValueError("backend failure"), OverflowError("backend failure"),
                                    RuntimeError("backend failure"), KeyboardInterrupt("backend failure")])
def test_predict_errors_are_not_reclassified_as_quiet_scores(error):
    class BrokenModel:
        def predict(self, _frame):
            raise error

    with pytest.raises(type(error)) as caught:
        OpenWakeWordGate(BrokenModel()).process(b"pcm")
    assert caught.value is error


def test_unexpected_real_scalar_conversion_error_still_propagates():
    class BrokenFloat(float):
        def __float__(self):
            raise RuntimeError("scalar backend failure")

    with pytest.raises(RuntimeError, match="scalar backend failure"):
        OpenWakeWordGate(Model([{"wake": BrokenFloat(0.5)}])).process(b"pcm")


@pytest.mark.parametrize("raw", [None, [], ("wake", 1)])
def test_non_mapping_prediction_retains_existing_error(raw):
    with pytest.raises(RuntimeError, match="must return a mapping"):
        OpenWakeWordGate(Model([raw])).process(b"pcm")


@pytest.mark.asyncio
async def test_invalid_predictions_stay_quiet_before_actual_asr_chat_and_sqlite(tmp_path):
    calls = []

    async def transcribe(audio):
        calls.append("asr")
        return "hello"

    async def responder(prompt):
        calls.append("model")
        return "reply"

    persona = CompanionPersona(persona_id="p1", display_name="P", visual_skin_id="skin", instructions="Trusted.")
    with MemoryStore() as memory, ChatSessionStore(tmp_path / "chat.db") as sessions:
        companion = CompanionChatRuntime(persona=persona, responder=responder, memory_store=memory, session_store=sessions)
        runtime = VoiceActivationRuntime(gate=OpenWakeWordGate(Model([{"bad": v} for v in INVALID] + [{"wake": 0.5}])),
                                         transcriber=transcribe, companion=companion)
        try:
            for index in range(len(INVALID)):
                result = await runtime.process(wake_frame=b"pcm", utterance_audio=b"\0\0",
                                               request_id=f"bad-{index}", session_id="s1")
                assert not result.wakeword.triggered and result.chat is None and not result.transcript
                assert sessions.get_receipt(f"bad-{index}") is None
            assert calls == [] and sessions.load_messages("s1") == []
            assert memory.recent(namespace="p1") == [] and not runtime._owned_tasks
            fresh = await runtime.process(wake_frame=b"pcm", utterance_audio=b"\0\0", request_id="good", session_id="s1")
            assert fresh.wakeword.triggered and fresh.chat.assistant_message.content == "reply"
            assert calls == ["asr", "model"] and len(sessions.load_messages("s1")) == 3
        finally:
            await runtime.close()


@pytest.mark.asyncio
async def test_invalid_prediction_does_not_supersede_a_valid_inflight_turn():
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def transcribe(_audio):
        calls.append("asr")
        entered.set()
        await release.wait()
        return "hello"

    async def responder(_prompt):
        calls.append("model")
        return "reply"

    with MemoryStore() as memory:
        companion = CompanionChatRuntime(
            persona=CompanionPersona(persona_id="p1", display_name="P", visual_skin_id="skin", instructions="Trusted."),
            responder=responder, memory_store=memory)
        runtime = VoiceActivationRuntime(gate=OpenWakeWordGate(Model([{"wake": 1}, {"bad": float("inf")}]), cooldown_frames=0),
                                         transcriber=transcribe, companion=companion)
        task = asyncio.create_task(runtime.process(wake_frame=b"pcm", utterance_audio=b"\0\0", request_id="good", session_id="s1"))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            ignored = await runtime.process(wake_frame=b"pcm", utterance_audio=b"\0\0", request_id="bad", session_id="s1")
            assert not ignored.wakeword.triggered and not ignored.interrupted_previous
            assert not task.done() and calls == ["asr"]
            release.set()
            completed = await asyncio.wait_for(task, 1)
            assert not completed.superseded and completed.chat.assistant_message.content == "reply"
            assert calls == ["asr", "model"] and len(companion.session_messages("s1")) == 3
        finally:
            release.set()
            await runtime.close()
            await asyncio.gather(task, return_exceptions=True)
