"""Book freshness is checked when a queued turn actually owns the runtime."""
from datetime import datetime, timedelta, timezone
import asyncio

import pytest

import mygpt_brain.companion_chat as chat
from mygpt_brain.memory_store import MemoryStore
from mygpt_brain.session_store import ChatSessionStore

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


class AdmissionClock(datetime):
    value = NOW
    reads = 0
    failure = None

    @classmethod
    def now(cls, tz=None):
        cls.reads += 1
        if cls.failure is not None:
            raise cls.failure
        return cls.value


def book_request(request_id="queued-book"):
    return {
        "request_id": request_id, "session_id": "s1", "persona_id": "p1", "text": "Explain this section",
        "book_context": {
            "context": {
                "schema_version": "mygpt.study-context.v1", "evidence_kind": "SIMULATED",
                "session_id": "s1", "course_id": "course", "book_id": "book", "book_version": "v1",
                "section_id": "section", "source_id": "source", "source_sha256": "a" * 64,
                "mode": "learn", "captured_at": NOW, "expires_at": NOW + timedelta(seconds=1),
            },
            "text": "EPHEMERAL_BOOK_INPUT",
        },
    }


@pytest.fixture
def setup_runtime(tmp_path, monkeypatch):
    AdmissionClock.value, AdmissionClock.reads, AdmissionClock.failure = NOW, 0, None
    monkeypatch.setattr(chat, "datetime", AdmissionClock)
    calls = []

    async def responder(prompt):
        calls.append(prompt.provider_messages())
        return "Fresh explanation."

    with MemoryStore() as memory, ChatSessionStore(tmp_path / "chat.db") as store:
        runtime = chat.CompanionChatRuntime(
            persona=chat.CompanionPersona(persona_id="p1", display_name="P", visual_skin_id="skin", instructions="Trusted."),
            responder=responder, memory_store=memory, session_store=store,
        )
        yield runtime, store, calls


async def queued(runtime, request, **kwargs):
    await runtime._lock.acquire()
    task = asyncio.create_task(runtime.send(request, **kwargs))
    # send has reached the contested runtime lock, without sleeping wall time.
    await asyncio.sleep(0)
    assert not task.done()
    return task


@pytest.mark.asyncio
@pytest.mark.parametrize("offset,error", [(0.5, None), (1, "expired"), (2, "expired"), (-1, "future")])
async def test_queued_book_uses_admission_clock_and_exact_freshness_boundary(setup_runtime, offset, error):
    runtime, store, calls = setup_runtime
    task = await queued(runtime, book_request())
    assert AdmissionClock.reads == 0
    AdmissionClock.value = NOW + timedelta(seconds=offset)
    runtime._lock.release()
    if error:
        with pytest.raises(ValueError, match=error):
            await task
        assert calls == []
        assert store.load_messages("s1") == runtime.session_messages("s1") == []
        assert store.get_receipt("queued-book") is None
    else:
        result = await task
        assert result.user_message.created_at == AdmissionClock.value
        assert any("EPHEMERAL_BOOK_INPUT" in message.content and message.role == "user" for message in calls[0])
        assert result.context_references == ["book:book:v1:section:source"]
        assert all("EPHEMERAL_BOOK_INPUT" not in message.content for message in store.load_messages("s1"))
    assert AdmissionClock.reads == 1
    assert runtime.memory_store.recent(namespace="p1") == []


@pytest.mark.asyncio
async def test_queued_book_preserves_existing_explicit_time_override(setup_runtime):
    runtime, store, calls = setup_runtime
    task = await queued(runtime, book_request(), now=NOW)
    AdmissionClock.value = NOW + timedelta(seconds=2)
    runtime._lock.release()
    result = await task
    assert result.user_message.created_at == NOW
    assert len(calls) == 1 and len(store.load_messages("s1")) == 3
    assert AdmissionClock.reads == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["cancel", "revoke"])
async def test_queued_book_cancellation_or_revocation_has_no_admission(setup_runtime, action):
    runtime, store, calls = setup_runtime
    authorized = True
    task = await queued(runtime, book_request(), is_current=lambda: authorized)
    AdmissionClock.value = NOW + timedelta(seconds=2)
    if action == "cancel":
        task.cancel()
        expected = asyncio.CancelledError
    else:
        authorized = False
        expected = chat.SupersededChatTurn
    runtime._lock.release()
    with pytest.raises(expected):
        await task
    assert AdmissionClock.reads == 0 and calls == []
    assert store.load_messages("s1") == runtime.session_messages("s1") == []
    assert store.get_receipt("queued-book") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["now", "timezone"])
async def test_admission_clock_failure_is_not_retried_or_cached(setup_runtime, failure):
    runtime, store, calls = setup_runtime

    class BrokenTime:
        def astimezone(self, _zone):
            raise RuntimeError("clock conversion failed")

    task = await queued(runtime, book_request())
    if failure == "now":
        AdmissionClock.failure = RuntimeError("clock read failed")
    else:
        AdmissionClock.value = BrokenTime()
    runtime._lock.release()
    with pytest.raises(RuntimeError, match="clock"):
        await task
    assert AdmissionClock.reads == 1 and calls == []
    assert runtime._sessions == runtime._requests == {}
    assert store.load_messages("s1") == [] and store.get_receipt("queued-book") is None
    AdmissionClock.value, AdmissionClock.failure = NOW, None
    result = await runtime.send(book_request())
    assert not result.replayed and len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("cold", [False, True])
async def test_book_receipt_replay_after_expiry_does_not_readmit_source(setup_runtime, cold):
    runtime, store, calls = setup_runtime
    first = await runtime.send(book_request())
    if cold:
        runtime = chat.CompanionChatRuntime(
            persona=runtime.persona, responder=runtime.responder,
            memory_store=runtime.memory_store, session_store=store,
        )
    AdmissionClock.value = NOW + timedelta(seconds=2)
    replay = await runtime.send(book_request())
    assert replay.replayed and replay.assistant_message == first.assistant_message
    assert replay.user_message.created_at == NOW and len(calls) == 1
    assert len(store.load_messages("s1")) == 3
    assert "EPHEMERAL_BOOK_INPUT" not in str(store.get_receipt("queued-book"))
    changed = book_request()
    changed["book_context"]["text"] = "DIFFERENT_BOOK_INPUT"
    with pytest.raises(ValueError, match="request_id conflict"):
        await runtime.send(changed)
    assert len(calls) == 1
