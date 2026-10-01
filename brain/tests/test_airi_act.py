"""Pinned AIRI semantics plus MyGPT's bounded reply-boundary guarantees."""
import json

import pytest

from mygpt_brain.airi_act import (
    EMOTION_VALUES,
    MAX_MARKER_BYTES,
    MAX_REPLY_CHARS,
    parse_act_reply,
)
from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona, CompanionReply
from mygpt_brain.pipecat_bridge import PipecatCompanionBridge


@pytest.mark.parametrize("name", sorted(EMOTION_VALUES))
@pytest.mark.parametrize("object_form", [False, True])
def test_port_preserves_airi_string_object_name_normalization(name, object_form):
    emotion = {"name": " " + name.upper() + " ", "intensity": 0.4} if object_form else name.upper()
    result = parse_act_reply("继续。<|ACT:" + json.dumps({"emotion": emotion}) + "|>")
    assert result.text == "继续。"
    assert result.emotion == name
    assert result.intensity == (0.4 if object_form else 1.0)
    assert result.marker_found


@pytest.mark.parametrize("value,expected", [(-3, 0), (0, 0), (0.3, 0.3), (9, 1), (True, 1), ("0.2", 1), (None, 1)])
def test_port_preserves_airi_intensity_clamp_and_wrong_type_default(value, expected):
    payload = {"emotion": {"name": "happy", "intensity": value}}
    result = parse_act_reply("好。<|ACT:" + json.dumps(payload) + "|>")
    assert result.intensity == expected


@pytest.mark.parametrize("marker", [
    '<|act {"emotion":"happy"}|>',
    '<|AcT  :  {"emotion":"happy"}|>',
])
def test_port_preserves_case_insensitive_optional_colon(marker):
    assert parse_act_reply(marker + "好。").emotion == "happy"


@pytest.mark.parametrize("payload", [
    "not json", "[]", "null", '{"emotion":[]}', '{"emotion":true}',
    '{"emotion":"unknown"}', '{"emotion":{"name":1}}',
    '{"emotion":"happy","emotion":"angry"}',
    '{"emotion":{"name":"happy","intensity":NaN}}',
    '{"emotion":{"name":"happy","intensity":1e9999}}',
    '{"emotion":"happy", "action":"' + "x" * MAX_MARKER_BYTES + '"}',
    '{"action":{"emotion":"angry"}}',
    '{"emotion":"\\ud800"}',
])
def test_invalid_markers_are_removed_without_becoming_actions_or_emotions(payload):
    result = parse_act_reply("前。<|ACT:" + payload + "|>后。")
    assert result.text == "前。后。"
    assert result.emotion == "neutral"
    assert result.marker_found


def test_separate_envelopes_do_not_greedily_swallow_visible_text():
    result = parse_act_reply('前<|ACT:{"emotion":"happy"}|>中<|ACT:{"emotion":"sad"}|>后')
    assert result.text == "前中后"
    assert result.emotion == "sad"


def test_last_invalid_marker_does_not_overwrite_last_valid_emotion():
    result = parse_act_reply('好<|ACT:{"emotion":"happy"}|><|ACT:{"emotion":"other"}|>')
    assert result.text == "好"
    assert result.emotion == "happy"


@pytest.mark.parametrize("tail", ["<|", "<|A", "<|AC", "<|ACT", '<|ACT:{"emotion":', '<|ACT:{"emotion":"happy"}'])
def test_incomplete_control_tail_never_becomes_speech(tail):
    result = parse_act_reply("完整回答。" + tail)
    assert result.text == "完整回答。"
    assert result.emotion == "neutral"


def test_plain_text_and_similar_words_are_unchanged():
    text = "  中文\n数学 x={1, 2}，<|ACTUAL|> stays literal.  "
    result = parse_act_reply(text)
    assert result.text == text
    assert not result.marker_found


@pytest.mark.parametrize("payload,emotion", [
    ('{"emotion":"happy","note":"a|>b"}', "happy"),
    ('{"emotion":"a|>b"}', "neutral"),
    ('{"emotion":"happy","note":"a\\\"|>b"}', "happy"),
    ('{"emotion":"happy","note":"a\\\\|>b"}', "happy"),
])
def test_json_string_delimiters_and_escapes_do_not_leak_payload_tail(payload, emotion):
    result = parse_act_reply("Before.<|ACT:" + payload + "|>After.")
    assert result.text == "Before.After."
    assert result.emotion == emotion


def test_unterminated_quoted_payload_discards_control_tail():
    result = parse_act_reply('Before.<|ACT:{"emotion":"a|>b')
    assert result.text == "Before."


def test_input_budget_is_checked_before_scanning():
    with pytest.raises(ValueError, match="size"):
        parse_act_reply("a" * (MAX_REPLY_CHARS + 1))


def runtime_for(responder):
    return CompanionChatRuntime(
        persona=CompanionPersona(persona_id="p1", display_name="P", visual_skin_id="3714430278", instructions="Trusted."),
        responder=responder,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ['<|ACT:{"emotion":"happy"}|>', "<|ACT:broken", "x" * (MAX_REPLY_CHARS + 1)])
async def test_invalid_output_never_commits_an_exchange_and_request_can_retry(output):
    async def responder(_prompt):
        return output
    runtime = runtime_for(responder)
    request = dict(request_id="r1", session_id="s1", persona_id="p1", text="hello")
    with pytest.raises(RuntimeError, match="invalid or empty"):
        await runtime.send(request)
    assert runtime.session_messages("s1") == []
    async def recover(_prompt):
        return '恢复。<|ACT:{"emotion":"happy"}|>'
    runtime.responder = recover
    result = await runtime.send(request)
    assert result.assistant_message.content == "恢复。"
    assert result.presentation_emotion == "happy"
    assert not result.replayed


@pytest.mark.asyncio
async def test_structured_reply_emotion_wins_but_control_syntax_is_removed():
    async def responder(_prompt):
        return CompanionReply(text='收到。<|ACT:{"emotion":"angry"}|>', emotion="happy")
    result = await runtime_for(responder).send(dict(request_id="r1", session_id="s1", persona_id="p1", text="hi"))
    assert result.assistant_message.content == "收到。"
    assert result.presentation_emotion == "happy"


@pytest.mark.asyncio
async def test_quoted_delimiter_payload_never_reaches_history_or_replay():
    async def responder(_prompt):
        return 'Before.<|ACT:{"emotion":"happy","note":"a|>b"}|>After.'
    runtime = runtime_for(responder)
    request = dict(request_id="r1", session_id="s1", persona_id="p1", text="hi")
    first = await runtime.send(request)
    replay = await runtime.send(request)
    assert first.assistant_message.content == replay.assistant_message.content == "Before.After."
    assert replay.replayed
    assert runtime.session_messages("s1")[-1].content == "Before.After."


@pytest.mark.asyncio
async def test_rejected_first_reply_retry_persists_persona_for_process_restart(tmp_path):
    from mygpt_brain.session_store import ChatSessionStore
    async def invalid(_prompt):
        return '<|ACT:{"emotion":"happy"}|>'
    async def valid(prompt):
        assert prompt.provider_messages()[0].role == "system"
        assert prompt.provider_messages()[0].content == "Trusted."
        return "继续。"
    request = dict(request_id="r1", session_id="s1", persona_id="p1", text="hi")
    with ChatSessionStore(tmp_path / "chat.sqlite3") as store:
        runtime = runtime_for(invalid)
        runtime.session_store = store
        with pytest.raises(RuntimeError, match="invalid or empty"):
            await runtime.send(request)
        runtime.responder = valid
        await runtime.send(request)
        assert [m.role for m in store.load_messages("s1")] == ["system", "user", "assistant"]
    with ChatSessionStore(tmp_path / "chat.sqlite3") as store:
        restored = runtime_for(valid)
        restored.session_store = store
        await restored.send(dict(request, request_id="r2", text="again"))


@pytest.mark.asyncio
async def test_existing_pipecat_path_emits_only_visible_speech():
    async def responder(_prompt):
        return '继续，我在。<|ACT:{"emotion":{"name":"happy","intensity":0.8}}|>'
    bridge = PipecatCompanionBridge(runtime_for(responder), session_id="voice-1")
    reply = await bridge.respond("继续学习")
    assert reply.text == "继续，我在。"
    assert reply.emotion == "happy"

    from fixtures_pipecat import Frames, create_processor
    processor = create_processor(bridge)
    await processor.process_frame(Frames.TranscriptionFrame("继续学习"), "down")
    assert [frame.text for frame, _ in processor.pushed if isinstance(frame, Frames.LLMTextFrame)] == ["继续，我在。"]
