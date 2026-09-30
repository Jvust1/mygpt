from __future__ import annotations

from datetime import datetime, timedelta, timezone
import http.client
import json
import httpx
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from mygpt_brain.companion_chat import (
    CompanionChatRuntime,
    CompanionPersona,
    CompanionReply,
)
from mygpt_brain.companion_service import CLIENT_HEADER, CompanionServiceHandler, create_companion_server
from mygpt_brain.session_store import ChatSessionStore
from mygpt_brain.providers import OllamaResponder
from mygpt_brain.airi_act import ACT_PRESENTATION_INSTRUCTION

NOW = datetime(2026, 9, 29, 16, 10, tzinfo=timezone.utc)


def test_ollama_act_roundtrip_separates_voice_and_emotion_before_durable_replay(tmp_path, monkeypatch):
    """Real companion HTTP + actual Ollama adapter; model endpoint is stubbed."""
    calls = []
    def model_endpoint(req):
        calls.append(json.loads(req.content))
        assert str(req.url) == "http://127.0.0.1:11434/api/chat"
        return httpx.Response(200, json={"message": {"content": '继续学这节。<|ACT:{"emotion":"happy"}|>'}})
    def client_factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(model_endpoint), **kwargs)
    monkeypatch.setattr("mygpt_brain.providers._ASYNC_CLIENT", client_factory)
    body = dict(request_id="airi-http", session_id="s1", persona_id="mygpt-3714430278", text="继续学习")
    runtime, store = make_runtime(tmp_path, responder=OllamaResponder("synthetic-test-model"))
    try:
        with create_companion_server(runtime) as server:
            status, value = call(server, "POST", "/api/v1/chat", token=server.token, body=body)
            assert status == 200
            assert value["assistant_message"]["content"] == "继续学这节。"
            assert value["presentation_emotion"] == "happy"
        assert calls[0]["messages"][1] == {"role": "system", "content": ACT_PRESENTATION_INSTRUCTION}
        assert all("<|ACT" not in m.content for m in store.load_messages("s1"))
        assert runtime.memory_store.recent(namespace=runtime.persona.persona_id) == []
    finally:
        store.close()
    # Reopen SQLite and the HTTP service: no second model call or raw marker.
    restored, store = make_runtime(tmp_path, responder=OllamaResponder("synthetic-test-model"))
    try:
        with create_companion_server(restored) as server:
            status, replay = call(server, "POST", "/api/v1/chat", token=server.token, body=body)
            assert status == 200 and replay["replayed"]
            assert replay["presentation_emotion"] == "happy"
            assert replay["assistant_message"]["content"] == "继续学这节。"
            assert len(calls) == 1
    finally:
        store.close()


def call(server, method, path, *, token=None, body=None, client=True, content_type="application/json"):
    port = int(server.origin.rsplit(":", 1)[1])
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    raw = None if body is None else json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    headers = {}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if client:
        headers["X-MyGPT-Client"] = CLIENT_HEADER
    if raw is not None:
        headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(raw))
    connection.request(method, path, body=raw, headers=headers)
    response = connection.getresponse()
    payload = response.read()
    value = json.loads(payload) if payload else None
    result = response.status, value
    connection.close()
    return result


def make_runtime(tmp_path, *, responder=None):
    async def default_responder(_prompt):
        return CompanionReply(text="本机回复", emotion="happy")
    persona = CompanionPersona(
        persona_id="mygpt-3714430278",
        display_name="MyGPT",
        visual_skin_id="3714430278",
        instructions="Trusted persona.",
    )
    store = ChatSessionStore(tmp_path / "chat.sqlite3")
    return CompanionChatRuntime(
        persona=persona,
        responder=responder or default_responder,
        session_store=store,
        request_timeout_seconds=3,
    ), store


def test_status_requires_native_token_and_does_not_echo_secret(tmp_path):
    runtime, store = make_runtime(tmp_path)
    try:
        with create_companion_server(runtime, authorization_seconds=60) as server:
            assert call(server, "GET", "/api/v1/status")[0] == 403
            assert call(server, "GET", "/api/v1/status", token=server.token, client=False)[0] == 403
            status, value = call(server, "GET", "/api/v1/status", token=server.token)
            assert status == 200
            assert value["transport"] == "LOOPBACK_NATIVE_TOKEN"
            assert value["persona_id"] == "mygpt-3714430278"
            assert value["visual_skin_id"] == "3714430278"
            assert value["provider_configurable_over_http"] is False
            assert server.token not in json.dumps(value)
    finally:
        store.close()


def test_chat_roundtrip_replay_and_conflict_over_actual_loopback(tmp_path):
    calls = 0
    async def responder(_prompt):
        nonlocal calls
        calls += 1
        return CompanionReply(text="继续，我在。", emotion="happy")

    runtime, store = make_runtime(tmp_path, responder=responder)
    body = {
        "schema_version": "mygpt.companion-chat.v1",
        "request_id": "req-http-1",
        "session_id": "session-1",
        "persona_id": "mygpt-3714430278",
        "text": "陪我继续学习",
    }
    try:
        with create_companion_server(runtime, authorization_seconds=60) as server:
            status, first = call(server, "POST", "/api/v1/chat", token=server.token, body=body)
            assert status == 200
            assert first["assistant_message"]["content"] == "继续，我在。"
            assert first["presentation_emotion"] == "happy"
            assert first["replayed"] is False

            status, replay = call(server, "POST", "/api/v1/chat", token=server.token, body=body)
            assert status == 200 and replay["replayed"] is True
            assert calls == 1

            changed = dict(body, text="different")
            status, error = call(server, "POST", "/api/v1/chat", token=server.token, body=changed)
            assert status == 409
            assert error["code"] == "request_id_conflict"
    finally:
        store.close()


def test_book_context_stays_ephemeral_through_http(tmp_path):
    runtime, store = make_runtime(tmp_path)
    body = {
        "schema_version": "mygpt.companion-chat.v1",
        "request_id": "book-http-1",
        "session_id": "session-book",
        "persona_id": "mygpt-3714430278",
        "text": "解释这一段",
        "book_context": {
            "schema_version": "mygpt.companion-book-context.v1",
            "context": {
                "schema_version": "mygpt.study-context.v1",
                "evidence_kind": "SIMULATED",
                "session_id": "session-book",
                "course_id": "functional-analysis",
                "book_id": "jiang-ze-jian",
                "book_version": "v1",
                "section_id": "ch1-s1",
                "source_id": "source-1",
                "source_sha256": "a" * 64,
                "mode": "learn",
                "captured_at": NOW.isoformat(),
                "expires_at": (NOW + timedelta(seconds=300)).isoformat(),
            },
            "text": "教材结构化语义上下文",
        },
    }
    try:
        with create_companion_server(runtime, authorization_seconds=60) as server:
            # Runtime clock is real UTC, so use a fresh lease for the HTTP path.
            fresh = datetime.now(timezone.utc)
            body["book_context"]["context"]["captured_at"] = fresh.isoformat()
            body["book_context"]["context"]["expires_at"] = (fresh + timedelta(seconds=300)).isoformat()
            status, value = call(server, "POST", "/api/v1/chat", token=server.token, body=body)
            assert status == 200
            assert value["context_references"] == ["book:jiang-ze-jian:v1:ch1-s1:source-1"]
            durable = store.load_messages("session-book")
            assert [message.role for message in durable] == ["system", "user", "assistant"]
            assert all("BOOK_SEMANTIC_CONTEXT_V1" not in message.content for message in durable)
    finally:
        store.close()


def test_revoke_invalidates_token_without_stopping_process(tmp_path):
    runtime, store = make_runtime(tmp_path)
    try:
        with create_companion_server(runtime, authorization_seconds=60) as server:
            status, result = call(
                server,
                "POST",
                "/api/v1/revoke",
                token=server.token,
                body={"schema_version": "mygpt.companion-revoke.v1"},
            )
            assert status == 200 and result["status"] == "revoked"
            status, error = call(server, "GET", "/api/v1/status", token=server.token)
            assert status == 403
            assert error["code"] == "authorization_revoked_or_expired"
    finally:
        store.close()


def test_http_boundary_rejects_cors_wrong_content_type_and_unknown_method(tmp_path):
    runtime, store = make_runtime(tmp_path)
    try:
        with create_companion_server(runtime, authorization_seconds=60) as server:
            assert call(server, "OPTIONS", "/api/v1/chat", token=server.token)[0] == 405
            body = {
                "request_id": "r1",
                "session_id": "s1",
                "persona_id": "mygpt-3714430278",
                "text": "hi",
            }
            status, error = call(
                server,
                "POST",
                "/api/v1/chat",
                token=server.token,
                body=body,
                content_type="text/plain",
            )
            assert status == 415 and error["code"] == "json_content_type_required"
            assert call(server, "PUT", "/api/v1/chat", token=server.token, body=body)[0] == 405
    finally:
        store.close()


def chat_body(runtime, request_id="pending"):
    return dict(request_id=request_id, session_id="s1", persona_id=runtime.persona.persona_id, text="synthetic input")


def wait_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline: raise AssertionError("condition did not become ready")
        time.sleep(0.005)


@pytest.mark.parametrize("after_cancel", ["raise", "return", "uncancel"])
def test_revoke_cancels_admitted_chat_and_never_commits_late_reply(tmp_path, after_cancel):
    entered, cancelled = threading.Event(), threading.Event()
    async def responder(_prompt):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            if after_cancel == "raise": raise
            if after_cancel == "uncancel": asyncio.current_task().uncancel()
            return "obsolete reply"
    runtime, store = make_runtime(tmp_path, responder=responder)
    try:
        with create_companion_server(runtime) as server, ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(call, server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime))
            assert entered.wait(2)
            status, _ = call(server, "POST", "/api/v1/revoke", token=server.token, body={"schema_version":"mygpt.companion-revoke.v1"})
            assert status == 200
            status, error = pending.result(2)
            assert status == 403 and error["code"] == "authorization_revoked_or_expired"
            assert cancelled.wait(2)
            assert store.load_messages("s1") == []
            assert store.get_receipt("pending") is None
            assert not server.httpd.executor._pending
    finally:
        store.close()


def test_authorization_expiry_cancels_provider_without_waiting_for_model_timeout(tmp_path):
    cancelled = threading.Event()
    async def responder(_prompt):
        try: await asyncio.Event().wait()
        finally: cancelled.set()
    runtime, store = make_runtime(tmp_path, responder=responder)
    try:
        with create_companion_server(runtime, authorization_seconds=1) as server:
            status, error = call(server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime))
            assert status == 403 and error["code"] == "authorization_revoked_or_expired"
            assert cancelled.wait(2)
            assert store.load_messages("s1") == []
            assert store.get_receipt("pending") is None
    finally:
        store.close()


def test_revoke_cancels_running_and_lock_queued_requests(tmp_path):
    entered = threading.Event()
    calls = []
    async def responder(prompt):
        calls.append(prompt)
        entered.set()
        await asyncio.Event().wait()
    runtime, store = make_runtime(tmp_path, responder=responder)
    try:
        with create_companion_server(runtime) as server, ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(call, server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime, "first"))
            assert entered.wait(2)
            second = pool.submit(call, server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime, "second"))
            def registered():
                with server.httpd.executor._pending_lock:
                    return len(server.httpd.executor._pending) == 2
            wait_until(registered)
            call(server, "POST", "/api/v1/revoke", token=server.token, body={"schema_version":"mygpt.companion-revoke.v1"})
            assert first.result(2)[0] == second.result(2)[0] == 403
            assert len(calls) == 1
            assert store.load_messages("s1") == []
    finally:
        store.close()


def test_native_http_revoke_closes_actual_ollama_adapter_stream(tmp_path, monkeypatch):
    entered, closed = threading.Event(), threading.Event()
    class PendingReply(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b"unreachable"
        async def aclose(self): closed.set()
    def factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=PendingReply())), **kwargs)
    monkeypatch.setattr("mygpt_brain.providers._ASYNC_CLIENT", factory)
    runtime, store = make_runtime(tmp_path, responder=OllamaResponder("synthetic-test-model"))
    try:
        with create_companion_server(runtime) as server, ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(call, server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime))
            assert entered.wait(2)
            call(server, "POST", "/api/v1/revoke", token=server.token, body={"schema_version":"mygpt.companion-revoke.v1"})
            assert pending.result(2)[0] == 403
            assert closed.wait(2)
            assert store.load_messages("s1") == []
    finally:
        store.close()


def test_revoke_racing_future_registration_cannot_start_a_provider(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []
    async def responder(_prompt):
        calls.append(True)
        return "must not run"
    runtime, store = make_runtime(tmp_path, responder=responder)
    original = asyncio.run_coroutine_threadsafe
    blocked = False
    def hold_first_submission(coroutine, loop):
        nonlocal blocked
        if not blocked:
            blocked = True
            entered.set()
            assert release.wait(2)
        return original(coroutine, loop)
    try:
        with create_companion_server(runtime) as server, ThreadPoolExecutor(max_workers=2) as pool:
            monkeypatch.setattr("mygpt_brain.companion_service.asyncio.run_coroutine_threadsafe", hold_first_submission)
            pending = pool.submit(call, server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime))
            assert entered.wait(2)
            revoke = pool.submit(call, server, "POST", "/api/v1/revoke", token=server.token, body={"schema_version":"mygpt.companion-revoke.v1"})
            wait_until(lambda: not server.httpd.is_authorized())
            release.set()
            assert revoke.result(2)[0] == 200
            assert pending.result(2)[0] == 403
            assert calls == []
            assert store.load_messages("s1") == []
    finally:
        release.set()
        store.close()


def observe_revoke_arrival(monkeypatch):
    arrived = threading.Event()
    original = CompanionServiceHandler.do_POST
    def handle(handler):
        if handler.path == "/api/v1/revoke": arrived.set()
        return original(handler)
    monkeypatch.setattr(CompanionServiceHandler, "do_POST", handle)
    return arrived


def test_revoke_waits_for_already_admitted_sqlite_commit_before_ack(tmp_path, monkeypatch):
    entered, release, committed = threading.Event(), threading.Event(), threading.Event()
    revoke_arrived = observe_revoke_arrival(monkeypatch)
    runtime, store = make_runtime(tmp_path)
    original_commit = store.commit_exchange
    def paused_commit(**kwargs):
        entered.set()
        assert release.wait(2)
        result = original_commit(**kwargs)
        committed.set()
        return result
    monkeypatch.setattr(store, "commit_exchange", paused_commit)
    try:
        with create_companion_server(runtime) as server, ThreadPoolExecutor(max_workers=2) as pool:
            chat = pool.submit(call, server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime))
            assert entered.wait(2)
            revoke = pool.submit(call, server, "POST", "/api/v1/revoke", token=server.token, body={"schema_version":"mygpt.companion-revoke.v1"})
            assert revoke_arrived.wait(2)
            assert not revoke.done() and not committed.is_set()
            release.set()
            assert revoke.result(2)[0] == 200 and committed.is_set()
            assert chat.result(2)[0] in (200, 403)  # Depending on which delivery admission wins.
            assert [m.role for m in store.load_messages("s1")] == ["system", "user", "assistant"]
            assert call(server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime, "later"))[0] == 403
            assert store.get_receipt("later") is None
    finally:
        release.set()
        store.close()


def test_revoke_winning_before_commit_admission_leaves_no_sqlite_exchange(tmp_path):
    from contextlib import contextmanager
    entered, release, exited = threading.Event(), threading.Event(), threading.Event()
    runtime, store = make_runtime(tmp_path)
    try:
        with create_companion_server(runtime) as server, ThreadPoolExecutor(max_workers=1) as pool:
            original_guard = server.httpd.completion_guard
            @contextmanager
            def paused_before_guard():
                entered.set()
                assert release.wait(2)
                try:
                    with original_guard(): yield
                finally:
                    exited.set()
            server.httpd.executor._completion_guard = paused_before_guard
            chat = pool.submit(call, server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime))
            assert entered.wait(2)
            assert call(server, "POST", "/api/v1/revoke", token=server.token, body={"schema_version":"mygpt.companion-revoke.v1"})[0] == 200
            assert chat.result(2)[0] == 403
            release.set()
            assert exited.wait(2)
            assert store.load_messages("s1") == []
            assert store.get_receipt("pending") is None
    finally:
        release.set()
        store.close()


def test_revoke_waits_for_admitted_success_delivery_before_ack(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    revoke_arrived = observe_revoke_arrival(monkeypatch)
    original_json = CompanionServiceHandler._json
    def paused_json(handler, status, value):
        if value.get("schema_version") == "mygpt.companion-chat-result.v1":
            entered.set()
            assert release.wait(2)
        return original_json(handler, status, value)
    monkeypatch.setattr(CompanionServiceHandler, "_json", paused_json)
    runtime, store = make_runtime(tmp_path)
    try:
        with create_companion_server(runtime) as server, ThreadPoolExecutor(max_workers=2) as pool:
            chat = pool.submit(call, server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime))
            assert entered.wait(2)
            revoke = pool.submit(call, server, "POST", "/api/v1/revoke", token=server.token, body={"schema_version":"mygpt.companion-revoke.v1"})
            assert revoke_arrived.wait(2)
            assert not revoke.done()
            release.set()
            assert chat.result(2)[0] == 200
            assert revoke.result(2)[0] == 200
    finally:
        release.set()
        store.close()


def test_expiry_before_success_delivery_admission_suppresses_completed_reply(tmp_path):
    runtime, store = make_runtime(tmp_path)
    try:
        with create_companion_server(runtime) as server:
            original_chat = server.httpd.executor.chat
            def expire_before_delivery(value):
                result = original_chat(value)
                with server.httpd._auth_lock:
                    server.httpd.authorization_deadline = time.monotonic() - 1
                return result
            server.httpd.executor.chat = expire_before_delivery
            status, error = call(server, "POST", "/api/v1/chat", token=server.token, body=chat_body(runtime))
            assert status == 403 and error["code"] == "authorization_revoked_or_expired"
            assert "assistant_message" not in error
            # Completion was authorized before the deadline changed; no erase.
            assert store.get_receipt("pending") is not None
    finally:
        store.close()


@pytest.mark.parametrize("size", [600, 4000])
def test_full_length_chat_retrieves_memory_and_preserves_native_prompt(tmp_path, size):
    from mygpt_brain.memory_store import MemoryRecord
    observed = []
    async def responder(prompt):
        observed.append(prompt)
        return "用这个例子继续学习。"
    runtime, store = make_runtime(tmp_path, responder=responder)
    text = "z" * (size - 4) + "拓扑学习"
    memory = MemoryRecord(memory_id="long-target", namespace=runtime.persona.persona_id,
        kind="preference", text="拓扑学习时先举例", tags=["拓扑"], source="user_explicit",
        created_at=NOW, updated_at=NOW)
    runtime.memory_store.put(memory)
    body = dict(request_id="long-query", session_id="s-long", persona_id=runtime.persona.persona_id, text=text)
    try:
        with create_companion_server(runtime) as server:
            status, reply = call(server, "POST", "/api/v1/chat", token=server.token, body=body)
            assert status == 200
            assert reply["recalled_memory_ids"] == ["long-target"]
            assert observed[0].provider_messages()[-1].content == text
            assert observed[0].memories == (memory,)
            recalled = [m for m in observed[0].provider_messages() if "LOCAL_RECALLED_MEMORY" in m.content]
            assert len(recalled) == 1 and recalled[0].role == "user"
            assert [m.content for m in store.load_messages("s-long") if m.role == "user"] == [text]
            status, replay = call(server, "POST", "/api/v1/chat", token=server.token, body=body)
            assert status == 200 and replay["replayed"]
            assert len(observed) == 1
        assert runtime.memory_store.get("long-target") == memory
        assert len(runtime.memory_store.history("long-target")) == 1
    finally:
        store.close()
