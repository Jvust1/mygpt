from datetime import datetime, timedelta, timezone
import pytest
from mygpt_brain.companion_chat import (
    CompanionChatRuntime,
    CompanionPersona,
    CompanionReply,
)
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


@pytest.mark.asyncio
async def test_book_context_is_ephemeral_lower_authority_data(tmp_path):
    seen=[]
    async def responder(prompt):
        provider=prompt.provider_messages()
        seen.extend(provider)
        assert provider[0].role=="system"
        assert any(
            item.role=="user"
            and "APPLICATION_CONTEXT_DATA" in item.content
            and "泛函分析本节定义" in item.content
            for item in provider
        )
        return "按当前教材上下文解释。"

    persona=CompanionPersona(persona_id="p1",display_name="P",visual_skin_id="3714430278",
        instructions="Trusted persona instruction.")
    context={
        "schema_version":"mygpt.companion-book-context.v1",
        "context":{
            "schema_version":"mygpt.study-context.v1",
            "evidence_kind":"SIMULATED",
            "session_id":"s1",
            "course_id":"functional-analysis",
            "book_id":"jiang-ze-jian",
            "book_version":"v1",
            "section_id":"ch1-s1",
            "source_id":"source-1",
            "source_sha256":"a"*64,
            "mode":"learn",
            "captured_at":NOW,
            "expires_at":NOW+timedelta(seconds=300),
        },
        "text":"泛函分析本节定义：这是结构化教材语义上下文。",
    }
    from mygpt_brain.session_store import ChatSessionStore
    with ChatSessionStore(tmp_path/"chat.sqlite3") as sessions:
        runtime=CompanionChatRuntime(persona=persona,responder=responder,session_store=sessions)
        result=await runtime.send({
            "request_id":"book-r1","session_id":"s1","persona_id":"p1",
            "text":"解释这一节","book_context":context
        },now=NOW)
        assert result.context_references==["book:jiang-ze-jian:v1:ch1-s1:source-1"]
        durable=sessions.load_messages("s1")
        assert [m.role for m in durable]==["system","user","assistant"]
        assert all("BOOK_SEMANTIC_CONTEXT_V1" not in m.content for m in durable)


@pytest.mark.asyncio
async def test_expired_book_context_fails_before_provider_call():
    calls=0
    async def responder(_prompt):
        nonlocal calls
        calls+=1
        return "should not run"
    persona=CompanionPersona(persona_id="p1",display_name="P",visual_skin_id="3714430278",
        instructions="Trusted.")
    context={
        "schema_version":"mygpt.companion-book-context.v1",
        "context":{
            "schema_version":"mygpt.study-context.v1",
            "evidence_kind":"SIMULATED",
            "session_id":"s1",
            "course_id":"c","book_id":"b","book_version":"v1","section_id":"s","source_id":"src",
            "source_sha256":"b"*64,"mode":"learn",
            "captured_at":NOW-timedelta(seconds=300),"expires_at":NOW,
        },
        "text":"expired",
    }
    runtime=CompanionChatRuntime(persona=persona,responder=responder)
    with pytest.raises(ValueError,match="expired"):
        await runtime.send({
            "request_id":"book-r2","session_id":"s1","persona_id":"p1",
            "text":"explain","book_context":context
        },now=NOW)
    assert calls==0


@pytest.mark.asyncio
async def test_structured_reply_carries_renderer_neutral_emotion():
    async def responder(_prompt):
        return CompanionReply(text="做得不错，继续。", emotion="happy")
    persona=CompanionPersona(
        persona_id="p1",display_name="P",visual_skin_id="3714430278",
        instructions="Be helpful."
    )
    runtime=CompanionChatRuntime(persona=persona,responder=responder)
    result=await runtime.send({
        "request_id":"emotion-r1","session_id":"s1","persona_id":"p1","text":"我做完了"
    },now=NOW)
    assert result.presentation_emotion=="happy"
    replay=await runtime.send({
        "request_id":"emotion-r1","session_id":"s1","persona_id":"p1","text":"我做完了"
    },now=NOW)
    assert replay.presentation_emotion=="happy"
    assert replay.replayed is True
