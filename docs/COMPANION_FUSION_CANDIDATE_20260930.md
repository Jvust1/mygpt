# Integrated companion fusion candidate

Base checkpoint: Android/Gson PR #39, `487d62f237bfccc6b524cdf6d0662c4a1a856d87`.
This candidate consolidates acceptance of the existing integration stack; it adds
no framework, model, runtime dependency, listener, permission or private asset.

## Working stories

### Voice reply through persistence and native replay

The new production-component story exercises:

1. A finalized real Pipecat transcription frame containing a 4000-character question
2. Namespace-scoped SQLite memory recall through the scikit-learn-derived scorer
3. The existing Ollama async adapter and fixed local chat wire contract
4. AIRI output normalization into visible text and separate character emotion
5. Conservative heading/link speech projection through actual Pipecat TTS machinery
6. SQLite commit, shutdown, new store/runtime instances and native HTTP idempotent replay
7. Explicit authorization revoke, followed by denied replay without another model call

The original full question and formatted visible reply remain in durable history.
Only the speech presentation is simplified. Another persona's synthetic private
memory never enters the prompt. Recall remains user-level data and creates no
implicit memory write. A fresh runtime is used after restart so separate event
loops do not share one live asyncio owner.

### Book semantic context through the native API

A second story combines a 600-character question, explicit memory and a bounded
**SIMULATED** Book semantic context. The real native HTTP server, runtime, Ollama
adapter, ACT parser and SQLite store are used. Trusted persona/ACT instructions
remain separate from user-level memory/Book data. The Book reference is returned,
but the raw Book context is not silently added as a transcript or memory record.
An expired new request receives the existing `409 book_context_expired` contract
without a model call, receipt or additional history.

## What is real and what is synthetic

Real components include the installed upstream SDKs, Pipecat queues and TTS
aggregation/context processing, model request serialization, native loopback HTTP,
SQLite durability/replay, authorization checks and Java/Gson decoding.

Both new stories use HTTPX `MockTransport` for the Ollama endpoint response; final
`run_tts` audio generation is also a test double. The real synthetic TCP socket
and connection-cancellation proof is a separate existing Pipecat test.
The voice story begins with a finalized transcription rather than a microphone
or ASR model. Book data is explicitly simulated, not a live app certificate/IPC
acceptance test. No inference-quality, pronunciation, physical device, APK/JNI,
phone-to-tablet networking, private skin or model-asset acceptance is claimed.

## One top-of-stack acceptance workflow

`Integrated companion fusion acceptance` checks one exact candidate commit:

- Hash-locked Python core installation, then the already-pinned real upstream test extras
- Full strict Brain gate, rejecting missing SDKs and all skipped tests
- A new fail-closed upstream gate requiring both stories and named real-source
  oracles; absent dependencies, skipped/missing cases, failures and timeout reject acceptance
- Existing root Python/JavaScript regressions and Python compilation
- Reused Android Java 8/17 matrix, including the true `--release 8` compile on Java 17

The Java compile/run manifest is now shared by local and hosted runs in
`android_spike/tools/run_boundary_smoke.sh`; its **41 source files and 18 smoke
entrypoints are unchanged**. The explicit local stripped-JRE fallback still
reports that `-source 8 -target 8` alone is not Java 8 API/runtime proof. The fallback is rejected in GitHub Actions, so hosted acceptance cannot silently
downgrade to source/target-only compilation. The APK job remains outside the
enabled scope.

## Local evidence

- Strict Brain: **686 passed, 0 failed, 0 skipped**
- Integrated/actual-upstream gate: **37 passed, 0 failed, 0 skipped**
  (25 real-Pipecat/stories, 9 actual sklearn oracles, 3 actual AIRI source oracles)
- Java: **18 smoke entrypoints**, including **327 Python/Gson parity cases**
- Root Python/JavaScript regressions are included in the aggregate workflow

No new runtime code is needed for these stories. Their purpose is to prove that
the previously fused capabilities compose, rather than merely pass isolated
adapter tests. Exact-head hosted results belong in the pull request evidence.

## Reproduction with existing pinned environments

```sh
cd brain
python scripts/verify_integrations.py --output /tmp/companion-core-evidence
python scripts/verify_fusion_upstreams.py --output /tmp/companion-upstream-evidence
cd ..
GSON_JAR=/path/to/gson-2.14.0.jar bash android_spike/tools/run_boundary_smoke.sh
python -m unittest discover -s tests -p 'test_*.py' -q
node --test tests/*.test.mjs
```

The upstream gate needs the existing `realtime` and `lexical-test` extras plus
Node 24; it fails rather than treating missing components as successful skips.
The Java script verifies the exact jar and notices before compiling. Neither
script installs packages, downloads a model or starts an external service.

## Reviewed integration history

- [#31](https://github.com/Jvust1/mygpt/pull/31): AIRI ACT emotion parsing in the actual reply path
- [#32](https://github.com/Jvust1/mygpt/pull/32): Pipecat response framing and interruption
- [#33](https://github.com/Jvust1/mygpt/pull/33): official Ollama async HTTP lifecycle
- [#34](https://github.com/Jvust1/mygpt/pull/34): wake/ASR task ownership
- [#35](https://github.com/Jvust1/mygpt/pull/35): native authorization/commit/delivery admission
- [#36](https://github.com/Jvust1/mygpt/pull/36): full-length lexical memory recall
- [#37](https://github.com/Jvust1/mygpt/pull/37): AIRI paired-history projection
- [#38](https://github.com/Jvust1/mygpt/pull/38): conservative speech presentation and owned callbacks
- [#39](https://github.com/Jvust1/mygpt/pull/39): actual Android/Gson parser and current-owner Java gates

These reuse AIRI, Pipecat, official ollama-python, scikit-learn and Gson, each
verified above 10,000 stars at adoption. Immutable sources/licenses remain under
`third_party/`; no duplicate vendor tree or whole application import was added.

## Remaining acceptance limits

A responder that refuses to finish cancellation can still retain the Python
runtime lock past its deadline; eventual late output is rejected, but hard
compute cancellation is not promised. Bounded lexical recall can miss candidates.
Speech formatting deliberately preserves ambiguous math/code/table syntax.
Already-admitted synchronous commits/writes can finish before revoke acknowledges.
Actual model/device and app-distribution acceptance remain separate from this
source-level candidate. The reviewed PRs remain drafts; nothing here merges or
deploys them.
