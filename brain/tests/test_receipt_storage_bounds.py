"""Lossless receipt representation and zero retained durable-runtime caches."""
import asyncio
from datetime import datetime, timezone
import itertools
import json
import sqlite3

import pytest

from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
from mygpt_brain.conversation import ChatMessage, compact_conversation
from mygpt_brain.session_store import ChatSessionStore

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)
PERSONA = CompanionPersona(persona_id="p", display_name="P", visual_skin_id="skin", instructions="Trusted.")


def message(index, role="user", session="s", authority=None):
    return ChatMessage(message_id=f"{session}-m{index}", session_id=session, role=role,
                       authority=authority, content=f"message {index}", created_at=NOW)


def body(index, session="s"):
    return dict(request_id=f"r{index}", session_id=session, persona_id="p", text=f"question {index}")


def commit(store, index, messages, result, **kwargs):
    store.commit_exchange(persona_id="p", messages=messages, request_id=f"r{index}",
                          fingerprint=f"f{index}", result=result, completed_at=NOW, **kwargs)


async def answer(_prompt):
    return "reply"


def test_prefix_encoding_exact_replay_append_and_duplicate(tmp_path):
    path = tmp_path / "prefix.sqlite3"
    first = [message(0, "system", authority="system"), message(1), message(2, "assistant")]
    result = {"schema_version": "arbitrary", "compacted_message_ids": ["s-m1", "s-m2"], "value": True}
    with ChatSessionStore(path) as store:
        commit(store, 1, first, result)
        row = store._db.execute("SELECT result_json,compacted_prefix_json FROM chat_request_receipts").fetchone()
        assert "compacted_message_ids" not in json.loads(row[0])
        ref = json.loads(row[1])
        assert ref["version"] == "conversation-prefix-v1" and ref["count"] == 2
        assert ref["through_ordinal"] == 3 and len(ref["sha256"]) == 64
        commit(store, 2, [message(3), message(4, "assistant")], {"ok": 2})
        assert store.get_receipt("r1") == ("f1", result)
        commit(store, 1, first, result)  # Exact public result, independent of representation.
        with pytest.raises(ValueError, match="result conflict"):
            commit(store, 1, first, dict(result, value=1))
        with pytest.raises(ValueError, match="another persona"):
            store.commit_exchange(persona_id="other", messages=first, request_id="r1", fingerprint="f1",
                                  result=result, completed_at=NOW)
        assert len(store.load_messages("s")) == 5
    with ChatSessionStore(path) as store:
        assert store.get_receipt("r1") == ("f1", result)


@pytest.mark.parametrize("ids", [[], ["s-m2"], ["s-m2", "s-m1"], ["s-m1", "s-m1"], ["unknown"], [True]])
def test_nonprefix_lists_preserved_literal_without_reserved_key_collision(ids):
    with ChatSessionStore() as store:
        result = {"compacted_message_ids": ids, "compacted_prefix_json": {"version": "arbitrary"}}
        commit(store, 1, [message(1), message(2, "assistant")], result)
        assert store.get_receipt("r1") == ("f1", result)
        assert store._db.execute("SELECT compacted_prefix_json FROM chat_request_receipts").fetchone()[0] is None


@pytest.mark.parametrize("damage", ["id", "missing", "count", "hash", "version", "extra", "bool_ordinal"])
def test_corrupt_reference_or_history_fails_closed(damage):
    with ChatSessionStore() as store:
        commit(store, 1, [message(1), message(2, "assistant")], {"compacted_message_ids": ["s-m1", "s-m2"]})
        with store._db:
            if damage == "id":
                store._db.execute("UPDATE chat_messages SET message_id='changed' WHERE message_id='s-m1'")
            elif damage == "missing":
                store._db.execute("DELETE FROM chat_messages WHERE message_id='s-m1'")
            else:
                ref = json.loads(store._db.execute("SELECT compacted_prefix_json FROM chat_request_receipts").fetchone()[0])
                key, value = {"count": ("count", 99), "hash": ("sha256", "0" * 64),
                              "version": ("version", "unknown"), "extra": ("extra", 1),
                              "bool_ordinal": ("through_ordinal", True)}[damage]
                ref[key] = value
                store._db.execute("UPDATE chat_request_receipts SET compacted_prefix_json=?", (json.dumps(ref),))
        with pytest.raises(RuntimeError, match="receipt"):
            store.get_receipt("r1")


def create_v1(path):
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE chat_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    INSERT INTO chat_meta VALUES('schema_version','1');
    CREATE TABLE chat_sessions(session_id TEXT PRIMARY KEY,persona_id TEXT NOT NULL,
                               created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
    CREATE TABLE chat_messages(message_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,ordinal INTEGER NOT NULL,
        role TEXT NOT NULL,authority TEXT,content TEXT NOT NULL,created_at TEXT NOT NULL,reply_to_message_id TEXT,
        FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,UNIQUE(session_id,ordinal));
    CREATE TABLE chat_request_receipts(request_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,fingerprint TEXT NOT NULL,
        result_json TEXT NOT NULL,completed_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE);
    """)
    now = NOW.isoformat()
    original = ' { "compacted_message_ids" : ["s-m1"], "ok": true } '
    db.execute("INSERT INTO chat_sessions VALUES('s','p',?,?)", (now, now))
    db.execute("INSERT INTO chat_messages VALUES('s-m1','s',1,'user',NULL,'message 1',?,NULL)", (now,))
    db.execute("INSERT INTO chat_request_receipts VALUES('r1','s','f1',?,?)", (original, now))
    db.commit()
    db.close()
    return original


def test_v1_upgrade_preserves_raw_receipt_bytes_and_history(tmp_path):
    path = tmp_path / "v1.sqlite3"
    original = create_v1(path)
    with ChatSessionStore(path) as store:
        assert store._db.execute("SELECT value FROM chat_meta").fetchone()[0] == "2"
        row = store._db.execute("SELECT result_json,compacted_prefix_json FROM chat_request_receipts").fetchone()
        assert tuple(row) == (original, None)
        assert store.get_receipt("r1") == ("f1", json.loads(original))
        commit(store, 1, [message(1)], json.loads(original))
        commit(store, 2, [message(2, "assistant")], {"compacted_message_ids": ["s-m1"]})
        assert len(store.load_messages("s")) == 2
        assert store._db.execute("SELECT result_json FROM chat_request_receipts WHERE request_id='r1'").fetchone()[0] == original
    with ChatSessionStore(path) as store:
        assert store.get_receipt("r1") == ("f1", json.loads(original))
        assert store.get_receipt("r2") == ("f2", {"compacted_message_ids": ["s-m1"]})


def test_unknown_schema_fails_without_rewriting(tmp_path):
    path = tmp_path / "future.sqlite3"
    create_v1(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE chat_meta SET value='999'")
    with pytest.raises(RuntimeError, match="unsupported"):
        ChatSessionStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM chat_meta").fetchone()[0] == "999"
        assert "compacted_prefix_json" not in [row[1] for row in db.execute("PRAGMA table_info(chat_request_receipts)")]


@pytest.mark.asyncio
async def test_no_retained_caches_across_long_and_many_sessions_replay_and_conflicts(tmp_path):
    calls = 0
    async def respond(prompt):
        nonlocal calls
        calls += 1
        assert len(prompt.window.history) <= 4
        return "reply"
    path = tmp_path / "bounded.sqlite3"
    with ChatSessionStore(path) as store:
        runtime = CompanionChatRuntime(persona=PERSONA, responder=respond, session_store=store, recent_turn_limit=4)
        for index in range(100):
            result = await runtime.send(body(index), now=NOW)
            assert runtime._sessions == runtime._requests == {}
        expected = result.model_dump(mode="json")
        for index in range(100, 200):
            await runtime.send(body(index, f"s{index}"), now=NOW)
        assert runtime._sessions == runtime._requests == {}
        assert len(runtime.session_messages("s")) == 201
        assert len(runtime.session_messages("s199")) == 3
        replay = await runtime.send(body(99), now=NOW)
        assert replay.model_dump(mode="json") == dict(expected, replayed=True)
        with pytest.raises(ValueError, match="request_id conflict"):
            await runtime.send(dict(body(0), text="changed"), now=NOW)
        assert calls == 200
        other = CompanionChatRuntime(persona=PERSONA.model_copy(update={"persona_id": "other"}), responder=respond, session_store=store)
        assert other.session_messages("s") == []
        with pytest.raises(ValueError, match="another persona"):
            await other.send(dict(body("other"), persona_id="other"), now=NOW)
    with ChatSessionStore(path) as store:
        runtime = CompanionChatRuntime(persona=PERSONA, responder=respond, session_store=store, recent_turn_limit=4)
        assert (await runtime.send(body(99), now=NOW)).model_dump(mode="json") == dict(expected, replayed=True)
        assert calls == 200
        assert runtime._sessions == runtime._requests == {}
        # Explicit deletion cascades receipts; there is no stale in-memory replay.
        assert store.delete_session("s")
        assert runtime.session_messages("s") == []
        assert store.get_receipt("r99") is None
        recreated = await runtime.send(body(99), now=NOW)
        assert not recreated.replayed and recreated.compacted_message_ids == []
        assert len(runtime.session_messages("s")) == 3 and calls == 201


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["delete", "delete_recreate", "append"])
async def test_inflight_history_change_from_another_connection_rejects_atomically(tmp_path, change):
    path = tmp_path / "race.sqlite3"
    with ChatSessionStore(path) as first, ChatSessionStore(path) as second:
        runtime = CompanionChatRuntime(persona=PERSONA, responder=answer, session_store=first)
        peer = CompanionChatRuntime(persona=PERSONA, responder=answer, session_store=second)
        await runtime.send(body(0), now=NOW)
        entered, resume = asyncio.Event(), asyncio.Event()
        async def slow(_):
            entered.set()
            await resume.wait()
            return "stale reply"
        runtime.responder = slow
        pending = asyncio.create_task(runtime.send(body(1), now=NOW))
        await entered.wait()
        if change in ("delete", "delete_recreate"):
            assert second.delete_session("s")
        if change in ("delete_recreate", "append"):
            await peer.send(body(2), now=NOW)
        before = first.load_messages("s")
        resume.set()
        with pytest.raises(ValueError, match="session changed"):
            await pending
        assert first.load_messages("s") == before
        assert first.get_receipt("r1") is None
        assert runtime._sessions == runtime._requests == {}
        runtime.responder = answer
        assert not (await runtime.send(body(1), now=NOW)).replayed


@pytest.mark.asyncio
async def test_same_runtime_concurrent_requests_and_duplicate_are_serialized(tmp_path):
    calls = 0
    async def respond(_):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return "reply"
    with ChatSessionStore(tmp_path / "serial.sqlite3") as store:
        runtime = CompanionChatRuntime(persona=PERSONA, responder=respond, session_store=store, recent_turn_limit=2)
        results = await asyncio.gather(*(runtime.send(body(i), now=NOW) for i in range(20)), runtime.send(body(0), now=NOW))
        assert sum(r.replayed for r in results) == 1 and calls == 20
        assert len(runtime.session_messages("s")) == 41
        assert runtime._sessions == runtime._requests == {}


def test_store_cross_connection_duplicate_and_stale_revision(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / "stores.sqlite3"
    with ChatSessionStore(path) as first, ChatSessionStore(path) as second:
        messages = [message(1), message(2, "assistant")]
        result = {"compacted_message_ids": ["s-m1"]}
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(commit, store, 1, messages, result, expected_revision=None) for store in (first, second)]
            for task in tasks:
                task.result()
        assert len(first.load_messages("s")) == 2
        assert first.get_receipt("r1") == second.get_receipt("r1") == ("f1", result)
        with pytest.raises(ValueError, match="session changed"):
            commit(second, 2, [message(3)], {}, expected_revision=None)
        assert second.get_receipt("r2") is None and len(second.load_messages("s")) == 2


@pytest.mark.parametrize("budget", [2, 3, 4, 5])
def test_sql_tail_compaction_matches_full_history_for_irregular_roles(budget):
    # Includes leading assistant greetings, consecutive users/reactions and
    # interleaved authority rows. Caller always appends a current user turn.
    for roles in itertools.product(("user", "assistant"), repeat=6):
        with ChatSessionStore() as store:
            messages = [message(0, "system", authority="system")]
            messages.extend(message(i + 1, role) for i, role in enumerate(roles))
            messages.insert(4, message("developer", "system", authority="developer"))
            messages.append(message("context", "system", authority="context"))
            commit(store, 1, messages, {})
            state = store.load_prompt_state("s", budget)
            user = message("new")
            expected = compact_conversation([*messages, user], recent_turn_limit=budget)
            actual = compact_conversation([*state.messages, user], recent_turn_limit=budget)
            actual.compacted_message_ids[:0] = state.compacted_message_ids
            assert actual == expected


@pytest.mark.asyncio
async def test_nondurable_mode_retains_full_history_and_old_replay_contract():
    runtime = CompanionChatRuntime(persona=PERSONA, responder=answer, recent_turn_limit=2)
    for i in range(80):
        await runtime.send(body(i), now=NOW)
    assert len(runtime.session_messages("s")) == 161
    assert len(runtime._requests) == 80
    assert (await runtime.send(body(0), now=NOW)).replayed
    with pytest.raises(ValueError, match="request_id conflict"):
        await runtime.send(dict(body(0), text="different"), now=NOW)


@pytest.mark.parametrize("error_type", [sqlite3.OperationalError, KeyboardInterrupt])
def test_v1_migration_failure_or_interruption_rolls_back_all_ddl(tmp_path, monkeypatch, error_type):
    path = tmp_path / "migration-failure.sqlite3"
    original = create_v1(path)
    real_connect = sqlite3.connect
    class InterruptedMigration(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            if sql.startswith("ALTER TABLE chat_request_receipts"):
                raise error_type("synthetic migration interruption")
            return super().execute(sql, parameters)
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: real_connect(*args, **kwargs, factory=InterruptedMigration))
    with pytest.raises(error_type, match="synthetic migration"):
        ChatSessionStore(path)
    with real_connect(path) as db:
        assert db.execute("SELECT value FROM chat_meta").fetchone()[0] == "1"
        assert "revision" not in [row[1] for row in db.execute("PRAGMA table_info(chat_sessions)")]
        assert "compacted_prefix_json" not in [row[1] for row in db.execute("PRAGMA table_info(chat_request_receipts)")]
        assert db.execute("SELECT result_json FROM chat_request_receipts").fetchone()[0] == original
        assert db.execute("SELECT message_id,content FROM chat_messages").fetchall() == [("s-m1", "message 1")]
    monkeypatch.setattr(sqlite3, "connect", real_connect)
    with ChatSessionStore(path) as store:
        assert store.get_receipt("r1") == ("f1", json.loads(original))


def test_receipt_insert_failure_rolls_back_messages_and_revision():
    with ChatSessionStore() as store:
        commit(store, 1, [message(1)], {"ok": 1})
        before = store.load_prompt_state("s", 2)
        with store._db:
            store._db.execute("""CREATE TRIGGER reject_receipt BEFORE INSERT ON chat_request_receipts
                BEGIN SELECT RAISE(ABORT, 'synthetic full disk'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="synthetic full disk"):
            commit(store, 2, [message(2)], {"compacted_message_ids": ["s-m1"]}, expected_revision=before.revision)
        after = store.load_prompt_state("s", 2)
        assert before == after and store.get_receipt("r2") is None


@pytest.mark.asyncio
async def test_caller_result_mutation_cannot_change_durable_replay(tmp_path):
    path = tmp_path / "mutation.sqlite3"
    with ChatSessionStore(path) as store:
        runtime = CompanionChatRuntime(persona=PERSONA, responder=answer, session_store=store, recent_turn_limit=2)
        await runtime.send(body(0), now=NOW)
        first = await runtime.send(body(1), now=NOW)
        expected = first.model_dump(mode="json")
        first.compacted_message_ids[:] = ["caller-overwrite"]
        with pytest.raises(ValueError, match="frozen"):
            first.assistant_message.content = "caller-overwrite"
        replay = await runtime.send(body(1), now=NOW)
        assert replay.model_dump(mode="json") == dict(expected, replayed=True)
    with ChatSessionStore(path) as store:
        runtime = CompanionChatRuntime(persona=PERSONA, responder=answer, session_store=store, recent_turn_limit=2)
        assert (await runtime.send(body(1), now=NOW)).model_dump(mode="json") == dict(expected, replayed=True)


def test_simultaneous_v1_openers_upgrade_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / "simultaneous.sqlite3"
    original = create_v1(path)
    # Existing deployment already uses WAL; opening/migrating must not apply an
    # ALTER twice when two supported v2 owners start together.
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
    def open_and_read(_):
        with ChatSessionStore(path) as store:
            return store.get_receipt("r1")
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(open_and_read, range(8))) == [("f1", json.loads(original))] * 8


@pytest.mark.asyncio
@pytest.mark.parametrize("deleted_session", ["s", "unrelated"])
async def test_absent_session_create_delete_aba_rejected_without_identifier_tombstone(tmp_path, deleted_session):
    path = tmp_path / "absence-aba.sqlite3"
    with ChatSessionStore(path) as first, ChatSessionStore(path) as second:
        entered, resume = asyncio.Event(), asyncio.Event()
        async def slow(_):
            entered.set()
            await resume.wait()
            return "stale first reply"
        runtime = CompanionChatRuntime(persona=PERSONA, responder=slow, session_store=first)
        peer = CompanionChatRuntime(persona=PERSONA, responder=answer, session_store=second)
        pending = asyncio.create_task(runtime.send(body(1), now=NOW))
        await entered.wait()
        await peer.send(body(2, deleted_session), now=NOW)
        assert second.delete_session(deleted_session)
        assert not second.delete_session(deleted_session)
        assert second._db.execute("SELECT value FROM chat_meta WHERE key='deletion_epoch'").fetchone()[0] == "1"
        resume.set()
        with pytest.raises(ValueError, match="session changed"):
            await pending
        assert first.load_messages("s") == [] and first.get_receipt("r1") is None
        assert first._db.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0] == 0
        assert first._db.execute("SELECT COUNT(*) FROM chat_request_receipts").fetchone()[0] == 0
        assert {row[0] for row in first._db.execute("SELECT key FROM chat_meta")} == {"schema_version", "deletion_epoch"}
        runtime.responder = answer
        assert not (await runtime.send(body(1), now=NOW)).replayed


def test_failed_delete_rolls_back_global_epoch_and_does_not_invalidate_existing_session():
    with ChatSessionStore() as store:
        commit(store, 1, [message(1)], {})
        before = store.load_prompt_state("s", 2)
        with store._db:
            store._db.execute("""CREATE TRIGGER reject_epoch BEFORE UPDATE ON chat_meta
                WHEN NEW.key='deletion_epoch' BEGIN SELECT RAISE(ABORT, 'epoch failure'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="epoch failure"):
            store.delete_session("s")
        assert store.load_prompt_state("s", 2) == before
        assert store.get_receipt("r1") == ("f1", {})
