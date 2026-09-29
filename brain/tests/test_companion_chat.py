from datetime import datetime, timezone
import pytest
from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.memory_store import MemoryRecord, MemoryStore

NOW=datetime(2026,9,29,14,0,tzinfo=timezone.utc)

@pytest.mark.asyncio
async def test_chat_runtime_uses_persona_memory_and_replays_request():
    seen=[]
    async def responder(prompt):
        seen.append(prompt)
        roles=[m.role for m in prompt.provider_messages()]
        assert roles[0]=="system"
        return "收到，我会陪你继续。"
    persona=CompanionPersona(persona_id="airi-3714430278",display_name="MyGPT",
        visual_skin_id="3714430278",instructions="陪伴、简洁、不过度打扰。")
    with MemoryStore() as memory:
        memory.put(MemoryRecord(memory_id="pref-1",namespace=persona.persona_id,kind="preference",
            text="用户喜欢简洁回答",tags=["简洁"],source="user_explicit",created_at=NOW,updated_at=NOW))
        runtime=CompanionChatRuntime(persona=persona,responder=responder,memory_store=memory,recent_turn_limit=4)
        body={"request_id":"req-1","session_id":"s1","persona_id":persona.persona_id,
              "text":"请简洁一点陪我学习"}
        first=await runtime.send(body,now=NOW)
        second=await runtime.send(body,now=NOW)
        assert first.assistant_message.content=="收到，我会陪你继续。"
        assert first.recalled_memory_ids==["pref-1"]
        assert second.replayed is True
        assert len(seen)==1
        assert len(runtime.session_messages("s1"))==3

@pytest.mark.asyncio
async def test_request_id_conflict_fails_closed():
    async def responder(_prompt): return "ok"
    persona=CompanionPersona(persona_id="p1",display_name="P",visual_skin_id="3714430278",
        instructions="Be helpful.")
    runtime=CompanionChatRuntime(persona=persona,responder=responder)
    await runtime.send({"request_id":"r1","session_id":"s1","persona_id":"p1","text":"one"},now=NOW)
    with pytest.raises(ValueError,match="conflict"):
        await runtime.send({"request_id":"r1","session_id":"s1","persona_id":"p1","text":"two"},now=NOW)

@pytest.mark.asyncio
async def test_long_session_returns_compaction_ids_without_auto_memory():
    async def responder(_prompt): return "ok"
    persona=CompanionPersona(persona_id="p1",display_name="P",visual_skin_id="3714430278",
        instructions="Be helpful.")
    runtime=CompanionChatRuntime(persona=persona,responder=responder,recent_turn_limit=2)
    await runtime.send({"request_id":"r1","session_id":"s1","persona_id":"p1","text":"one"},now=NOW)
    result=await runtime.send({"request_id":"r2","session_id":"s1","persona_id":"p1","text":"two"},now=NOW)
    assert result.compacted_message_ids
    assert runtime.memory_store.recent(namespace="p1")==[]
