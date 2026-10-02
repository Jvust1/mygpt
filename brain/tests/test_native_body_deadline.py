"""Total native body-receipt budget, separate from headers and inference."""
from email.message import Message
import asyncio
import http.client
import io
import json
import socket
import time
from types import SimpleNamespace

import pytest

import mygpt_brain.companion_service as service
from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.memory_store import MemoryStore
from mygpt_brain.session_store import ChatSessionStore


class Clock:
    value = 0.0
    reads = 0

    def monotonic(self):
        self.reads += 1
        return self.value


class Connection:
    def __init__(self):
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)


class Reader:
    def __init__(self, data, clock, *, delays=(), chunk_size=None, error=None):
        self.buffer = io.BytesIO(data)
        self.clock = clock
        self.delays = iter(delays)
        self.chunk_size = chunk_size
        self.error = error
        self.requests = []

    def read1(self, size):
        self.requests.append(size)
        self.clock.value += next(self.delays, 0)
        if self.error is not None:
            raise self.error
        return self.buffer.read1(min(size, self.chunk_size or size))


def handler(monkeypatch, data, *, declared=None, **kwargs):
    clock = Clock()
    monkeypatch.setattr(service, "time", SimpleNamespace(monotonic=clock.monotonic))
    result = object.__new__(service.CompanionServiceHandler)
    result.connection = Connection()
    result.rfile = Reader(data, clock, **kwargs)
    result.headers = Message()
    if declared is not None:
        result.headers["Content-Length"] = str(declared)
    return result, clock


@pytest.mark.parametrize("delay,status", [(4.999, None), (5.0, 408), (5.001, 408)])
def test_body_receipt_exact_and_near_budget(monkeypatch, delay, status):
    h, _ = handler(monkeypatch, b'{}NEXT', declared=2, delays=[delay])
    if status:
        with pytest.raises(service.CompanionServiceError) as error:
            h._read_json()
        assert error.value.status == status and error.value.code == "request_body_timeout"
    else:
        assert h._read_json() == {}
    assert h.rfile.requests == [2]
    assert h.rfile.buffer.read() == b'NEXT'
    assert h.connection.timeouts == [5.0, service.SOCKET_IO_TIMEOUT_SECONDS]


def test_progressing_body_recalculates_remaining_budget_without_reset(monkeypatch):
    h, _ = handler(monkeypatch, b'{"a":1}', declared=7, delays=[2, 2, 1], chunk_size=2)
    with pytest.raises(service.CompanionServiceError, match="request_body_timeout"):
        h._read_json()
    assert h.connection.timeouts == [5, 3, 1, service.SOCKET_IO_TIMEOUT_SECONDS]
    assert h.rfile.requests == [7, 5, 3]
    assert h.rfile.buffer.read() == b'}'


def test_already_exhausted_budget_does_not_read(monkeypatch):
    h, _ = handler(monkeypatch, b'{}', declared=2)
    values = iter([0.0, 5.0])
    monkeypatch.setattr(service, "time", SimpleNamespace(monotonic=lambda: next(values)))
    with pytest.raises(service.CompanionServiceError, match="request_body_timeout"):
        h._read_json()
    assert h.rfile.requests == []
    assert h.connection.timeouts == [service.SOCKET_IO_TIMEOUT_SECONDS]


@pytest.mark.parametrize("data,declared", [(b'', 2), (b'{', 2), (b'{"a":', 7)])
def test_body_eof_is_incomplete_and_restores_socket_budget(monkeypatch, data, declared):
    h, _ = handler(monkeypatch, data, declared=declared, chunk_size=2)
    with pytest.raises(service.CompanionServiceError) as error:
        h._read_json()
    assert error.value.code == "incomplete_body" and error.value.status == 400
    assert h.connection.timeouts[-1] == service.SOCKET_IO_TIMEOUT_SECONDS
    assert all(0 < n <= declared for n in h.rfile.requests)


def test_socket_timeout_is_not_retried_and_restores_budget(monkeypatch):
    h, _ = handler(monkeypatch, b'{}', declared=2, error=TimeoutError("socket stalled"))
    with pytest.raises(service.CompanionServiceError, match="request_body_timeout") as error:
        h._read_json()
    assert error.value.status == 408 and h.rfile.requests == [2]
    assert h.connection.timeouts[-1] == service.SOCKET_IO_TIMEOUT_SECONDS


@pytest.mark.parametrize("declared,status", [(None, 411), (0, 413), (service.MAX_BODY + 1, 413), ("-1", 400)])
def test_body_size_validation_precedes_reads(monkeypatch, declared, status):
    h, clock = handler(monkeypatch, b'{}', declared=declared)
    with pytest.raises(service.CompanionServiceError) as error:
        h._read_json()
    assert error.value.status == status
    assert clock.reads == 0 and h.rfile.requests == [] and h.connection.timeouts == []


def test_exact_byte_cap_and_buffered_next_request_are_preserved(monkeypatch):
    data = b'{"x":"' + b'x' * (service.MAX_BODY - 8) + b'"}'
    following = b'POST /api/v1/chat HTTP/1.1\r\n'
    h, _ = handler(monkeypatch, data + following, declared=len(data), chunk_size=4096)
    assert len(data) == service.MAX_BODY
    assert len(h._read_json()["x"]) == service.MAX_BODY - 8
    assert h.rfile.requests == [16384, 12288, 8192, 4096]
    assert h.rfile.buffer.read() == following
    assert h.connection.timeouts[-1] == service.SOCKET_IO_TIMEOUT_SECONDS


@pytest.mark.parametrize("progress", [False, True])
def test_real_socket_body_deadline_releases_slot_without_provider_or_history(tmp_path, monkeypatch, progress):
    # Keep this real-socket regression quick; production uses five seconds.
    monkeypatch.setattr(service, "BODY_READ_TIMEOUT_SECONDS", 0.2)
    calls = []

    async def responder(prompt):
        calls.append(prompt)
        await asyncio.sleep(0.3)  # legitimate inference exceeds body budget
        return "Fresh response."

    persona = CompanionPersona(persona_id="p1", display_name="P", visual_skin_id="skin", instructions="Trusted.")
    with MemoryStore() as memory, ChatSessionStore(tmp_path / "chat.db") as store:
        runtime = CompanionChatRuntime(persona=persona, responder=responder, memory_store=memory,
                                       session_store=store, request_timeout_seconds=2)
        with service.create_companion_server(runtime) as server:
            port = int(server.origin.rsplit(":", 1)[1])
            body = json.dumps(dict(request_id="partial", session_id="s1", persona_id="p1", text="hello")).encode()
            headers = (
                f"POST /api/v1/chat HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                f"Authorization: Bearer {server.token}\r\nX-MyGPT-Client: {service.CLIENT_HEADER}\r\n"
                f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
            ).encode()
            with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
                started = time.monotonic()
                connection.sendall(headers + body[:1])
                if progress:
                    for index in range(1, 4):
                        time.sleep(0.04)
                        connection.sendall(body[index:index + 1])
                response = http.client.HTTPResponse(connection)
                response.begin()
                value = json.loads(response.read())
                elapsed = time.monotonic() - started
                assert response.status == 408 and value["code"] == "request_body_timeout"
                assert response.getheader("Connection") == "close"
                assert 0.15 <= elapsed < 1.5
            assert calls == [] and store.load_messages("s1") == []
            assert store.get_receipt("partial") is None and runtime._sessions == {}
            assert memory.recent(namespace="p1") == []
            deadline = time.monotonic() + 1
            while server.httpd._connection_slots._value != 16 and time.monotonic() < deadline:
                time.sleep(0.001)
            assert server.httpd._connection_slots._value == 16

            # A new fast request retains its independent, longer model timeout.
            body = json.dumps(dict(request_id="fresh", session_id="s1", persona_id="p1", text="hello")).encode()
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            try:
                connection.request("POST", "/api/v1/chat", body=body, headers={
                    "Authorization": "Bearer " + server.token, "X-MyGPT-Client": service.CLIENT_HEADER,
                    "Content-Type": "application/json",
                })
                response = connection.getresponse()
                value = json.loads(response.read())
                assert response.status == 200 and value["assistant_message"]["content"] == "Fresh response."
            finally:
                connection.close()
            assert len(calls) == 1 and len(store.load_messages("s1")) == 3
