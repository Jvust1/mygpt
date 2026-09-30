"""Execute the unchanged pinned AIRI TypeScript source as a test-only oracle.

Requires Node 24 for built-in type stripping; no npm install or network calls.
This directory is separate from the production Python-only strict gate.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess

from mygpt_brain.conversation import ChatMessage, _keep_recent_history_turns, compact_conversation

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "third_party/airi/reference/compaction.ts"
SOURCE_BLOB = "59a76a9877086f66b5abc09b0f22802e4e27df7d"
NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def upstream(cases):
    raw = SOURCE.read_bytes()
    assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == SOURCE_BLOB
    script = """
import {readFileSync} from 'node:fs';
const {compactConversationEntries} = await import(process.argv[1]);
const cases = JSON.parse(readFileSync(0, 'utf8'));
const results = cases.map(({roles, limit}) => {
  const items = roles.map((role, i) => role === 'user'
    ? {type:'turn', turnType:'chat', turnIndex:i, actor:'player', action:{kind:'text', text:`m${i}`}, id:`m${i}`}
    : {type:'reaction', reactionType:'assistant-chat', text:`m${i}`, id:`m${i}`});
  const entries = [{id:'history',role:'user',segments:[{type:'history-block',compacted:false,items}]}];
  return compactConversationEntries({entries,recentTurnLimit:limit})[0].segments[0].items
    .filter(item => item.type !== 'summary').map(item => item.id);
});
process.stdout.write(JSON.stringify(results));
"""
    result = subprocess.run(["node", "--input-type=module", "-e", script, SOURCE.as_uri()],
                            input=json.dumps(cases), capture_output=True, text=True, check=True, timeout=15)
    return json.loads(result.stdout)


def messages(roles):
    return [ChatMessage(message_id=f"m{i}", session_id="s1", role=role,
                        content=f"message {i}", created_at=NOW) for i, role in enumerate(roles)]


def test_pinned_source_and_license_identity():
    assert upstream([{"roles": ["user", "assistant", "user"], "limit": 1}]) == [["m2"]]
    raw = (ROOT / "third_party/airi/LICENSE").read_bytes()
    assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == "1bd715572472cd766a5c1444a467f5f011b14aaa"


def test_reverse_scan_matches_actual_airi_on_randomized_turn_reaction_groups():
    rng = random.Random(20260930)
    cases = []
    for _ in range(100):
        groups = rng.randint(2, 30)
        roles = []
        for _ in range(groups):
            roles += ["user"] + ["assistant"] * rng.randint(0, 4)
        cases.append({"roles": roles, "limit": rng.randint(1, groups - 1)})
    for case, expected in zip(cases, upstream(cases)):
        actual = _keep_recent_history_turns(messages(case["roles"]), case["limit"])
        assert [m.message_id for m in actual] == expected


def test_legacy_message_budget_adapter_matches_upstream_pairs_without_expansion():
    cases = []
    budgets = []
    for pairs in range(2, 16):
        for pending_user in (False, True):
            roles = ["user", "assistant"] * pairs + (["user"] if pending_user else [])
            for budget in range(1, len(roles)):
                turn_limit = roles[-budget:].count("user")
                window = compact_conversation(messages(roles), recent_turn_limit=budget)
                assert len(window.history) <= budget
                if turn_limit == 0:
                    assert window.history == []
                else:
                    cases.append({"roles": roles, "limit": turn_limit})
                    budgets.append(budget)
    for case, budget, expected in zip(cases, budgets, upstream(cases)):
        actual = compact_conversation(messages(case["roles"]), recent_turn_limit=budget)
        assert [m.message_id for m in actual.history] == expected
        assert actual.history[0].role == "user"
