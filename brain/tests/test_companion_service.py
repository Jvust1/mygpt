from __future__ import annotations

from datetime import datetime, timedelta, timezone
import http.client
import json

import pytest

from mygpt_brain.companion_chat import (
    CompanionChatRuntime,
    CompanionPersona,
    CompanionReply,
)
from mygpt_brain.companion_service import CLIENT_HEADER, create_companion_server
from mygpt_brain.session_store import ChatSessionStore

NOW = datetime(2026, 9, 29, 16, 10, tzinfo=timezone.utc)


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
