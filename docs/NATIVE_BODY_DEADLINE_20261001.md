# Bounded native request-body receipt

Base: [PR #49](https://github.com/Jvust1/mygpt/pull/49),
`5523550c390cd8f33aa35da92e7dab8f16923d23`.

## Reproduced gap

The native loopback handler's five-second socket timeout measured idle time,
not total receipt time. A valid body sent one byte every 250 ms occupied a
connection for 6.011 seconds, then returned 200, invoked the provider and
persisted three chat rows. A progressing sender could hold one of the sixteen
connection slots for much longer without exceeding the existing 16 KiB cap.

## Actual runtime change

After existing header and body-size validation, the handler now uses a fixed
five-second monotonic body deadline. Each buffered `read1` requests at most the
remaining Content-Length and uses the remaining time as its socket timeout.
Unlike `read(length)`, `read1` performs at most one underlying raw read, allowing
the total budget to be rechecked between chunks. Time is also checked after a
read; equality with the deadline rejects instead of admitting late bytes.

Timeout returns 408 `request_body_timeout` and closes the connection. Early EOF
still returns 400 `incomplete_body`; body-size rules and JSON validation remain.
The handler restores the existing five-second socket I/O timeout on both success
and failure. Body receipt does not shorten the separate responder deadline or
leave a tiny residual timeout on the response write.

No extra timer, thread, background task or dependency is introduced. The existing
connection semaphore still releases in its handler-thread `finally` block.
Expired/incomplete bodies do not reach the runtime, provider, memory or SQLite.

## Evidence and scope

- Deterministic production-handler tests cover just-before/equal/after deadline,
  progressing chunks with a decreasing budget, already-exhausted time, stalled
  socket errors, EOF/truncation and exact/over 16 KiB limits
- A buffered suffix representing the next request remains unread; read lengths
  never exceed the declared body remainder
- Two actual loopback socket cases cover stalled and progressing senders using
  a shortened test budget, 408/connection close and no provider call, history,
  receipt or implicit memory. Each occupies one slot and verifies availability
  returns to sixteen afterward; they are not concurrent saturation tests
- Each socket case then sends a normal fast body whose synthetic responder runs
  longer than the receipt budget; it succeeds and commits one exchange
- Existing aggregate CI also reuses exact-head source recovery and Java gates

This is specifically a request-body deadline after validated headers. It does
not establish a total header/connection deadline, immediate client-disconnect
cancellation, a hard kill for noncooperative model callbacks, or Android/device
acceptance. Normal inference and authorization admission contracts are unchanged.

This hardens the existing Pipecat-owned native HTTP → companion → Ollama path;
it is not another upstream adoption. All existing upstream pins, licenses and
the production dependency lock remain unchanged. Models and user data are not
downloaded or published.
