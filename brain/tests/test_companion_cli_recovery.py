"""Actual CLI -> stores -> Ollama adapter, with synthetic model HTTP only."""
import builtins
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import httpx
import pytest

from mygpt_brain.memory_store import MemoryStore
from mygpt_brain.session_store import ChatSessionStore

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "chat_local_ollama.py"
PERSONA = "mygpt-3714430278"


@pytest.fixture
def cli(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mygpt_cli_recovery_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    def endpoint(request):
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": 'Recovered.<|ACT:{"emotion":"happy"}|>'}})

    monkeypatch.setattr("mygpt_brain.providers._ASYNC_CLIENT", lambda **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(endpoint), **kwargs))
    monkeypatch.setattr(module, "_memory_id", lambda: "mem-test")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--model", "synthetic-test-model", "--data-dir", str(tmp_path), "--session-id", "s1"])

    def run(commands, *, terminal=EOFError):
        items = iter(commands)
        consumed = []

        def read(_prompt):
            try:
                value = next(items)
            except StopIteration:
                raise terminal()
            consumed.append(value)
            return value

        monkeypatch.setattr(builtins, "input", read)
        result = module.main()
        assert len(consumed) == len(commands)
        return result

    return module, run, calls, tmp_path


@pytest.mark.parametrize("bad", [":remember " + "x" * 2001, ":remember \ud800", ":remember   "],
                         ids=["over-limit", "invalid-unicode", "empty"])
def test_invalid_remember_then_valid_command_uses_real_persistence(cli, capsys, bad):
    _, run, calls, path = cli
    assert run([bad, ":remember quantum preference", ":memories", ":quit"]) == 0
    output = capsys.readouterr().out
    assert output.count("remembered> mem-test") == 1
    assert bad not in output and calls == []
    with MemoryStore(path / "memory.sqlite3") as memory, ChatSessionStore(path / "chat.sqlite3") as sessions:
        rows = memory.recent(namespace=PERSONA)
        assert len(rows) == 1 and rows[0].text == "quantum preference"
        assert memory.recent(namespace="other") == []
        assert [event.action for event in memory.history("mem-test")] == ["ADD"]
        assert sessions.load_messages("s1") == []


@pytest.mark.parametrize("bad", ["x" * 4001, "\ud800"], ids=["over-limit", "invalid-unicode"])
def test_invalid_chat_then_valid_chat_reaches_actual_ollama_only_once(cli, capsys, bad):
    _, run, calls, path = cli
    assert run([bad, "quantum", ":quit"]) == 0
    output = capsys.readouterr().out
    assert "input error>" in output and "Recovered." in output
    assert bad not in output and "<|ACT" not in output
    assert len(calls) == 1 and calls[0]["messages"][-1]["content"] == "quantum"
    with MemoryStore(path / "memory.sqlite3") as memory, ChatSessionStore(path / "chat.sqlite3") as sessions:
        assert memory.recent(namespace=PERSONA) == []
        assert [(m.role, m.content) for m in sessions.load_messages("s1")][1:] == [
            ("user", "quantum"), ("assistant", "Recovered.")]


@pytest.mark.parametrize("kind,size", [("remember", 2000), ("chat", 4000)])
def test_exact_existing_cli_limits_remain_accepted(cli, capsys, kind, size):
    _, run, calls, path = cli
    value = "q" * size
    command = ":remember " + value if kind == "remember" else value
    assert run([command, ":quit"]) == 0
    output = capsys.readouterr().out
    assert "error>" not in output
    with MemoryStore(path / "memory.sqlite3") as memory, ChatSessionStore(path / "chat.sqlite3") as sessions:
        if kind == "remember":
            assert memory.get("mem-test").text == value and calls == []
            assert sessions.load_messages("s1") == []
        else:
            assert len(calls) == 1 and calls[0]["messages"][-1]["content"] == value
            assert sessions.load_messages("s1")[-2].content == value


@pytest.mark.parametrize("terminal", [EOFError, KeyboardInterrupt])
def test_prompt_eof_or_interrupt_exits_without_losing_prior_memory(cli, capsys, terminal):
    _, run, calls, path = cli
    assert run([":remember retained note"], terminal=terminal) == 0
    assert capsys.readouterr().out.count("remembered> mem-test") == 1 and calls == []
    with MemoryStore(path / "memory.sqlite3") as memory:
        assert memory.get("mem-test").text == "retained note"


def test_recovered_cli_keeps_explicit_delete_audit_and_drops_active_recall(cli, capsys):
    _, run, calls, path = cli
    assert run([
        ":remember " + "x" * 2001, ":remember quantum preference", "quantum",
        ":update mem-test revised quantum preference", ":forget mem-test", ":history mem-test",
        "quantum again", ":quit",
    ]) == 0
    output = capsys.readouterr().out
    assert output.count("remembered> mem-test") == 1
    assert "updated> mem-test" in output and "forgotten> mem-test" in output
    assert len(calls) == 2
    assert any("LOCAL_RECALLED_MEMORY" in m["content"] for m in calls[0]["messages"])
    assert all("LOCAL_RECALLED_MEMORY" not in m["content"] for m in calls[1]["messages"])
    with MemoryStore(path / "memory.sqlite3") as memory, ChatSessionStore(path / "chat.sqlite3") as sessions:
        assert memory.get("mem-test") is None
        assert [e.action for e in memory.history("mem-test")] == ["DELETE", "UPDATE", "ADD"]
        assert memory.history("mem-test")[0].previous_value == "revised quantum preference"
        assert all("preference" not in m.content for m in sessions.load_messages("s1"))


def test_sqlite_failure_is_not_reported_as_input_error_or_success(cli, capsys):
    _, run, calls, path = cli
    with MemoryStore(path / "memory.sqlite3") as memory:
        memory._db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON memory_history "
                           "BEGIN SELECT RAISE(ABORT, 'synthetic storage failure'); END")
        memory._db.commit()
    with pytest.raises(sqlite3.IntegrityError, match="synthetic storage failure"):
        run([":remember do not falsely confirm"])
    output = capsys.readouterr().out
    assert "remembered>" not in output and "memory error>" not in output and calls == []
    with MemoryStore(path / "memory.sqlite3") as memory:
        assert memory.get("mem-test") is None and memory.history("mem-test") == []


@pytest.mark.parametrize("failure", [KeyboardInterrupt, SystemExit, OSError])
def test_non_input_failure_during_write_is_not_swallowed(cli, monkeypatch, capsys, failure):
    module, run, calls, path = cli

    def fail_put(*_args, **_kwargs):
        raise failure("synthetic non-input failure")

    monkeypatch.setattr(module.MemoryStore, "put", fail_put)
    with pytest.raises(failure, match="synthetic non-input failure"):
        run([":remember no success"])
    output = capsys.readouterr().out
    assert "remembered>" not in output and "memory error>" not in output and calls == []
    with MemoryStore(path / "memory.sqlite3") as memory:
        assert memory.get("mem-test") is None and memory.history("mem-test") == []
