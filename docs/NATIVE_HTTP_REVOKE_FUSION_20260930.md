# Pipecat-owned requests fused into native HTTP authorization

Base: wake/ASR PR #34, `5a652b62358e45eb2e4d4f3f66d2fe8ba4bb94e8`.

## Reproduced gap

The native `/api/v1/revoke` endpoint only changed a flag. An already-admitted
model request kept running: the reproduction returned revoke HTTP 200, then chat
HTTP 200, and stored the late assistant exchange. A client that explicitly ended
authorization could still receive the old model response.

## Direct mature-upstream reuse

Pipecat's owned-task registration, completion removal and snapshot cancellation
are adapted into the existing `_RuntimeExecutor`. The pinned source, 16,090-star
eligibility check, full BSD-2-Clause license and exact blobs are recorded in
`third_party/pipecat/`.

MyGPT uses cross-thread futures because the existing native HTTP service owns one
async runtime loop behind HTTP worker threads. This replaces no transport and
introduces no new server framework, listener, credential or dependency.

## Working behavior

- Track admitted request futures and remove them on completion
- Cancel a snapshot on explicit revoke, including calls waiting for the runtime
  lock; callbacks never run while the registry lock is held
- Revalidate authorization after registration to close the registration race
- Bound the model wait to the remaining authorization TTL
- Pass authorization into the existing pre-inference/precommit guard
- Use a shared authorization completion guard around the entire synchronous
  SQLite/cache mutation and successful HTTP response admission/write
- Map revoked/expired calls to HTTP 403 without private model output
- Close the existing Ollama async response stream when authorization is revoked

## Precise admission contract

Authorization and TTL are checked when a synchronous completion section is
admitted. A section already admitted may finish; successful revocation waits
for it before acknowledging. If revocation wins first, later commit and success
delivery admissions fail. This avoids the cross-thread check-then-write race
found during independent review.

Wall-clock expiry prevents later admissions and cancels provider waits. It does
not retroactively roll back an already-admitted synchronous commit/write. An
exchange committed while authorized can remain in history even when its later
HTTP delivery is denied after expiry. No historical deletion is performed, and
no claim is made about recalling bytes already admitted to a socket.

## Validation

- Full strict Brain: **623 passed, 0 failed, 0 skipped**, Python 3.12.14 and
  hash-installed Python 3.13.5
- Native HTTP tests: **17 passed**; real Pipecat tests: **8 passed**
- Independent review reran strict 623 and focused HTTP/real-SDK 25 cases
- Root Python 44 and JavaScript 66 tests pass; compile/diff checks pass
- Regressions cover cancel-resistant providers, expiry, lock-queued calls,
  registration races, actual Ollama adapter stream closure, blocked SQLite
  commits, blocked success writes, revocation-before-admission and
  expiry-before-delivery

Reproduce from `brain/`:

```sh
python scripts/verify_integrations.py --output /tmp/mygpt-native-revoke-acceptance
python -m pytest -q tests/test_companion_service.py realtime_tests
```

Tests use synthetic model replies and owned local services. No real model,
microphone, phone/tablet deployment or new external service is used. Actual
native/provider compute termination remains backend/device-specific. Hosted
exact-head acceptance must be verified after publication. No main update or merge.
