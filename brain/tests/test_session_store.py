from datetime import datetime, timedelta, timezone
import pytest

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.conversation import ChatMessage
from mygpt_brain.session_store import ChatSessionStore

NOW = datetime(2026, 9, 29, 14, 30, tzinfo=timezone.utc)


def msg(mid, role, content, *, session="s1", authority=None, seconds=0, reply=None):
    return ChatMessage(
        message_id=mid,
        session_id=session,
        role=role,
        authority=authority,
        content=content,
        created_at=NOW + timedelta(seconds=seconds),
        reply_to_message_id=reply,
    )


def test_session_store_roundtrip_and_atomic_receipt(tmp_path):
    path=tmp_path/"chat.sqlite3"
    result={"schema_version":"x","answer":"ok"}
    with ChatSessionStore(path) as store:
        messages=[
            msg("sys","system","persona",authority="system"),
            msg("u1","user","hi",seconds=1),
            msg("a1","assistant","hello",seconds=2,reply="u1"),
        ]
        store.commit_exchange(persona_id="p1",messages=messages,request_id="r1",
            fingerprint="abc",result=result,completed_at=NOW+timedelta(seconds=2))
        assert [m.message_id for m in store.load_messages("s1")]==["sys","u1","a1"]
        assert store.get_receipt("r1")==("abc",result)
        store.commit_exchange(persona_id="p1",messages=messages,request_id="r1",
            fingerprint="abc",result=result,completed_at=NOW+timedelta(seconds=2))
        assert len(store.load_messages("s1"))==3


def test_session_store_rejects_conflicting_receipt(tmp_path):
    with ChatSessionStore(tmp_path/"chat.sqlite3") as store:
        messages=[msg("sys","system","persona",authority="system")]
        store.commit_exchange(persona_id="p1",messages=messages,request_id="r1",
            fingerprint="abc",result={"ok":1},completed_at=NOW)
        with pytest.raises(ValueError,match="request_id conflict"):
            store.commit_exchange(persona_id="p1",messages=messages,request_id="r1",
                fingerprint="xyz",result={"ok":1},completed_at=NOW)


@pytest.mark.asyncio
async def test_runtime_restarts_without_recalling_provider(tmp_path):
    calls=0
    async def responder(_prompt):
        nonlocal calls
        calls+=1
        return "持久化回复"
    persona=CompanionPersona(persona_id="p1",display_name="P",visual_skin_id="3714430278",
        instructions="Stay helpful and concise.")
    path=tmp_path/"chat.sqlite3"
    body={"request_id":"r1","session_id":"s1","persona_id":"p1","text":"hello"}

    with ChatSessionStore(path) as store:
        first_runtime=CompanionChatRuntime(persona=persona,responder=responder,session_store=store)
        first=await first_runtime.send(body,now=NOW)
        assert first.replayed is False
        assert calls==1

    with ChatSessionStore(path) as store:
        second_runtime=CompanionChatRuntime(persona=persona,responder=responder,session_store=store)
        replay=await second_runtime.send(body,now=NOW)
        assert replay.replayed is True
        assert replay.assistant_message.content=="持久化回复"
        assert calls==1
        assert len(store.load_messages("s1"))==3


@pytest.mark.asyncio
async def test_two_sessions_get_distinct_system_message_ids(tmp_path):
    async def responder(_prompt): return "ok"
    persona=CompanionPersona(persona_id="p1",display_name="P",visual_skin_id="3714430278",
        instructions="Stay helpful.")
    with ChatSessionStore(tmp_path/"chat.sqlite3") as store:
        runtime=CompanionChatRuntime(persona=persona,responder=responder,session_store=store)
        await runtime.send({"request_id":"r1","session_id":"s1","persona_id":"p1","text":"one"},now=NOW)
        await runtime.send({"request_id":"r2","session_id":"s2","persona_id":"p1","text":"two"},now=NOW)
        first=store.load_messages("s1")[0]
        second=store.load_messages("s2")[0]
        assert first.message_id != second.message_id


@pytest.mark.asyncio
async def test_persistence_failure_does_not_append_exchange_to_memory():
    async def responder(_prompt): return "ok"
    class FailingStore:
        def get_receipt(self,_request_id): return None
        def load_messages(self,_session_id): return []
        def session_persona(self,_session_id): return None
        def commit_exchange(self,**_kwargs): raise RuntimeError("disk failed")
    persona=CompanionPersona(persona_id="p1",display_name="P",visual_skin_id="3714430278",
        instructions="Stay helpful.")
    runtime=CompanionChatRuntime(persona=persona,responder=responder,session_store=FailingStore())
    with pytest.raises(RuntimeError,match="disk failed"):
        await runtime.send({"request_id":"r1","session_id":"s1","persona_id":"p1","text":"one"},now=NOW)
    messages=runtime.session_messages("s1")
    assert len(messages)==1
    assert messages[0].role=="system"
