# AIRI paired history fused into prompt compaction

Base: lexical recall PR #36, `2ed48166ed5388aa1b385284aa1e82f7e5a72711`.

## Reproduced gap

With `recent_turn_limit=2`, the second request projected:

```text
system: trusted persona
assistant: old answer
user: new question
```

The old question was removed but its answer remained as an orphan response.
This happened in the actual `CompanionChatRuntime.send` provider path, including
a session restored from SQLite.

## Direct mature source reuse

AIRI's `keepRecentHistoryItems` reverse scan preserves turn/reaction groups.
MyGPT now directly ports that scan and invokes it from existing prompt compaction.
The source pin is `b40e3e87b149ea5fb75d4944440493829e601411`; source blob, MIT
copyright and full license are recorded under `third_party/airi/`. Eligibility
was rechecked on 2026-09-30: **49,890 GitHub stars**.

User messages map to upstream turns; following assistant messages map to
reactions. The existing option remains a **maximum conversational-message count**,
not a new token or exchange count: count the user turns inside that row budget,
then use the upstream reverse scan to retain their complete reactions. The
retained window may be smaller, never larger. Pairing is positional; it does
not validate arbitrary reply-to graphs in corrupted or reordered imports. A reaction-only tail with no
fitting user turn is omitted. An untrimmed greeting/history remains unchanged.

For the reproduced two-row case, the provider now receives only trusted persona
instructions and the complete current user question. With a larger budget,
whole recent user/assistant groups remain in order.

## Preserved boundaries

- Current request text, trusted instructions and lower-authority Book context
- Existing maximum row budget and public contract names
- Complete durable SQLite transcript; compaction is a prompt projection only
- Accurate compacted IDs for the entire omitted group and durable replay
- Explicit memory policy: no automatic summaries or transcript-to-memory writes
- No new runtime dependencies or model/device/network access

## Verification

- Full strict Brain: **653 passed, 0 failed, 0 skipped**, Python 3.12.14 and independently on hash-installed Python 3.13.5
- Actual Pipecat queue/TTS regression: **8 passed**
- Root regression: **44 Python and 66 JavaScript tests passed**
- Independent review: strict 653, focused/oracle 43 and 22,528 exhaustive
  role-pattern/budget probes passed, with no blocking findings

- Focused conversation/runtime/native HTTP + actual AIRI source: **43 passed**
- Actual unchanged upstream TypeScript executes with Node 24's built-in type
  stripping; no npm package installation is needed
- Three oracle tests cover source/license identity, 100 randomized multi-reaction
  histories, and all message budgets for 2–15 paired exchanges with/without a
  pending user message
- SQLite close/reopen regression preserves all five original rows while the
  second provider prompt omits the orphan answer; replay makes no second call
- Actual native HTTP + Ollama adapter verifies the outgoing message roles/text
  with a synthetic local model endpoint

The upstream reference is test-only. Normal Python runtime and strict tests need
no Node. Hosted AIRI acceptance explicitly supplies Node 24 for this oracle.
Model response quality, microphone/audio output and device performance remain
unverified by these synthetic tests.

```sh
cd brain
python -m pytest -q tests/test_conversation.py tests/test_companion_chat.py tests/test_companion_service.py
# With Node 24 available:
python -m pytest -q history_tests
python scripts/verify_integrations.py --output /tmp/mygpt-paired-evidence
```
