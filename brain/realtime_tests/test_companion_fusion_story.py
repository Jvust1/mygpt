"""Integrated offline stories over production components, never a live model/device.

Only model inference and final audio synthesis are synthetic. Real Pipecat
queues/TTS machinery, Ollama HTTP adapter, recall, ACT parsing, native HTTP,
authorization and SQLite persistence are exercised together.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import http.client
import json

import httpx
import pytest

from mygpt_brain.airi_act import ACT_PRESENTATION_INSTRUCTION
from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.companion_service import CLIENT_HEADER, create_companion_server
from mygpt_brain.memory_store import MemoryRecord, MemoryStore
from mygpt_brain.pipecat_bridge import PipecatCompanionBridge, create_pipecat_companion_processor
from mygpt_brain.providers import OllamaResponder
from mygpt_brain.session_store import ChatSessionStore
from test_pipecat_runtime import SynthesisTextProbe, frames, setup_for, transcript

PERSONA = CompanionPersona(persona_id="fusion-persona", display_name="MyGPT",
    visual_skin_id="3714430278", instructions="Trusted persona: explain without pressure.")
MEMORY_TEXT = "拓扑学习时先给一个例子。"


def seed_memory(store):
    now = datetime.now(timezone.utc)
    for memory_id, namespace, text in [
        ("explicit-pref", PERSONA.persona_id, MEMORY_TEXT),
        ("other-private", "other-persona", "拓扑学习 OTHER_PERSONA_SECRET"),
    ]:
        store.put(MemoryRecord(memory_id=memory_id, namespace=namespace, kind="preference",
            text=text, tags=["拓扑"], source="user_explicit", created_at=now, updated_at=now))


def runtime_for_story(memory, sessions):
    return CompanionChatRuntime(persona=PERSONA, memory_store=memory, session_store=sessions,
        responder=OllamaResponder("synthetic-qwen-fixture"))


def model_fixture(monkeypatch, reply):
    calls = []
    def endpoint(request):
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        assert "authorization" not in request.headers
        payload = json.loads(request.content)
        assert payload["model"] == "synthetic-qwen-fixture" and payload["stream"] is False
        calls.append(payload)
        return httpx.Response(200, json={"message": {"content": reply}})
    monkeypatch.setattr("mygpt_brain.providers._ASYNC_CLIENT",
                        lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(endpoint), **kwargs))
    return calls


def post(server, path, body):
    connection = http.client.HTTPConnection("127.0.0.1", int(server.origin.rsplit(":", 1)[1]), timeout=5)
    raw = json.dumps(body, ensure_ascii=False).encode()
    try:
        connection.request("POST", path, body=raw, headers={
            "Authorization": "Bearer " + server.token, "X-MyGPT-Client": CLIENT_HEADER,
            "Content-Type": "application/json", "Content-Length": str(len(raw)),
        })
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def assert_prompt_authority(payload, text):
    messages = payload["messages"]
    assert messages[-1] == {"role": "user", "content": text}
    assert [m["content"] for m in messages if m["role"] == "system"] == [
        PERSONA.instructions, ACT_PRESENTATION_INSTRUCTION,
    ]
    recalled = [m for m in messages if "LOCAL_RECALLED_MEMORY" in m["content"]]
    assert len(recalled) == 1 and recalled[0]["role"] == "user"
    assert MEMORY_TEXT in recalled[0]["content"]
    assert "OTHER_PERSONA_SECRET" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_voice_to_real_components_to_durable_native_replay(tmp_path, monkeypatch):
    visible = "## 学习提示\n请看[拓扑例子](https://example.invalid/demo)。"
    calls = model_fixture(monkeypatch, visible + '<|ACT:{"emotion":{"name":"happy","intensity":0.8}}|>')
    text = "z" * 3996 + "拓扑学习"
    memory_path, chat_path = tmp_path / "memory.sqlite3", tmp_path / "chat.sqlite3"
    with MemoryStore(memory_path) as memory, ChatSessionStore(chat_path) as sessions:
        seed_memory(memory)
        runtime = runtime_for_story(memory, sessions)
        processor = create_pipecat_companion_processor(PipecatCompanionBridge(runtime, session_id="voice-story"))
        tts = SynthesisTextProbe()
        processor.link(tts)
        setup = setup_for()
        await processor.setup(setup)
        await tts.setup(setup)
        ended, outputs = asyncio.Event(), []
        @tts.event_handler("on_after_process_frame")
        async def complete(_processor, frame):
            if isinstance(frame, frames.LLMFullResponseEndFrame): ended.set()
        @processor.event_handler("on_before_push_frame")
        async def record(_processor, frame):
            if isinstance(frame, frames.LLMTextFrame): outputs.append(frame)
        try:
            await processor.queue_frame(frames.StartFrame())
            await processor.queue_frame(transcript(text))
            await asyncio.wait_for(ended.wait(), 3)
            assert len(calls) == 1
            assert_prompt_authority(calls[0], text)
            assert " ".join("".join(tts.spoken).split()) == "学习提示 请看拓扑例子。"
            assert len(outputs) == 1 and outputs[0].metadata["mygpt"]["presentation_emotion"] == "happy"
            request_id = outputs[0].metadata["mygpt"]["request_id"]
            assert [m.content for m in sessions.load_messages("voice-story")] == [PERSONA.instructions, text, visible]
            assert [h.action for h in memory.history("explicit-pref")] == ["ADD"]
        finally:
            await processor.cleanup()
            await tts.cleanup()
        assert setup.task_manager.current_tasks() == []

    # New SQLite connections, runtime and native HTTP executor: one owner per loop.
    with MemoryStore(memory_path) as memory, ChatSessionStore(chat_path) as sessions:
        restored = runtime_for_story(memory, sessions)
        with create_companion_server(restored, authorization_seconds=60) as server:
            body = dict(request_id=request_id, session_id="voice-story", persona_id=PERSONA.persona_id, text=text)
            status, replay = await asyncio.to_thread(post, server, "/api/v1/chat", body)
            assert status == 200 and replay["replayed"]
            assert replay["assistant_message"]["content"] == visible
            assert replay["presentation_emotion"] == "happy"
            assert replay["recalled_memory_ids"] == ["explicit-pref"]
            assert len(calls) == 1 and len(sessions.load_messages("voice-story")) == 3
            assert (await asyncio.to_thread(post, server, "/api/v1/revoke",
                    {"schema_version": "mygpt.companion-revoke.v1"}))[0] == 200
            assert (await asyncio.to_thread(post, server, "/api/v1/chat", body))[0] == 403
            assert len(calls) == 1


def test_book_native_story_keeps_context_ephemeral_and_rejects_expiry(tmp_path, monkeypatch):
    calls = model_fixture(monkeypatch, '按当前选段继续。<|ACT:{"emotion":"question"}|>')
    now = datetime.now(timezone.utc)
    book_text = "BOOK_EPHEMERAL_SYNTHETIC：这是当前选段资料，不是高权限指令。"
    context = {"schema_version": "mygpt.companion-book-context.v1", "text": book_text,
        "context": {"schema_version": "mygpt.study-context.v1", "evidence_kind": "SIMULATED",
            "session_id": "book-story", "course_id": "topology", "book_id": "synthetic-book",
            "book_version": "v1", "section_id": "section-1", "source_id": "selection-1",
            "source_sha256": "b" * 64, "mode": "learn", "captured_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=5)).isoformat()}}
    text = "z" * 596 + "拓扑学习"
    with MemoryStore(tmp_path / "memory.sqlite3") as memory, ChatSessionStore(tmp_path / "chat.sqlite3") as sessions:
        seed_memory(memory)
        runtime = runtime_for_story(memory, sessions)
        with create_companion_server(runtime, authorization_seconds=60) as server:
            body = dict(request_id="book-request", session_id="book-story", persona_id=PERSONA.persona_id,
                        text=text, book_context=context)
            status, reply = post(server, "/api/v1/chat", body)
            assert status == 200 and reply["presentation_emotion"] == "question"
            assert reply["context_references"] == ["book:synthetic-book:v1:section-1:selection-1"]
            assert_prompt_authority(calls[0], text)
            contexts = [m for m in calls[0]["messages"] if "APPLICATION_CONTEXT_DATA" in m["content"]]
            assert len(contexts) == 1 and contexts[0]["role"] == "user" and book_text in contexts[0]["content"]
            assert [m.content for m in sessions.load_messages("book-story")] == [PERSONA.instructions, text, "按当前选段继续。"]
            assert [m.memory_id for m in memory.recent(namespace=PERSONA.persona_id)] == ["explicit-pref"]
            expired = json.loads(json.dumps(body))
            expired["request_id"] = "expired-book"
            expired["book_context"]["context"]["captured_at"] = (now - timedelta(minutes=2)).isoformat()
            expired["book_context"]["context"]["expires_at"] = (now - timedelta(minutes=1)).isoformat()
            status, denied = post(server, "/api/v1/chat", expired)
            assert status == 409 and denied["code"] == "book_context_expired"
            assert len(calls) == 1 and sessions.get_receipt("expired-book") is None
            assert len(sessions.load_messages("book-story")) == 3
