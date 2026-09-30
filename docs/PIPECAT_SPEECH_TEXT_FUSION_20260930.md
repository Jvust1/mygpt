# Pipecat speech presentation and owned response callbacks

Base: paired-history PR #37, `b1be392c065eb38410751445a7a445785e2bf148`.

## Reproduced gaps

The actual Pipecat queue and `TTSService.run_tts` handoff received raw Markdown:
`先看 **定义**，再做 [练习](https://example.invalid/book)。`. The upstream TTS
service supports filters, but this companion pipeline did not apply one.

While testing the added asynchronous presentation step, a direct runtime gap
was also reproduced: on supported Python versions, `wait_for(coroutine)` can
execute the callback in the caller task. A responder calling `uncancel()` could
clear that cancellation and persist a cancelled exchange. Existing voice/HTTP
admission guards prevented some transport cases, but direct runtime calls still
needed explicit child-task ownership.

## Actual upstream capability, invoked by default

The production Pipecat processor now calls its already-installed
`MarkdownTextFilter` only for a conservative subset of short, flat heading/link
replies before emitting speech frames. Other replies remain verbatim. Upstream
had **16,093 stars**, BSD-2-Clause, verified 2026-09-30. The pinned 1.12.0 source
file matches Git blob `08b2a1f743d8cf7d2faa937915e97f52e3997d04`; full provenance
and license are retained under `third_party/pipecat/`.

This reuses the real upstream implementation rather than adding another Markdown
parser or optional application adapter. No new runtime dependency is introduced.

- Strip simple heading markers and link syntax while retaining labels/prose
- Preserve asterisks/operators, backticks/code, table pipes/cell boundaries,
  underscores, images, escaped syntax, list numbering and ambiguous content
  verbatim instead of guessing its mathematical meaning
- Parse only replies of at most 1200 characters, with at most 16 bracket/parenthesis
  delimiters and a flat recognized-link structure; longer/nested inputs bypass
  the parser without truncation
- Run eligible upstream parsing in a worker thread, never on the event loop;
  use a new filter instance per response and disable repeated-sequence deletion
- Keep native HTTP text, SQLite history and replay content unchanged
- Retain start/text/end framing and separate presentation emotion metadata

Independent review found that unrestricted upstream filtering removed `*` from
`2 * 3`, changed inline `a|b`/`a**b`, collapsed table cells, and blocked the event
loop for about four seconds on a valid 8000-character nested-bracket response.
The narrow gate preserves those values verbatim; actual TTS regressions cover
all of them. Bold/italic formatting is intentionally left unchanged because its
asterisks may be mathematical operators. This is not a general Markdown/math
normalizer or a pronunciation guarantee.

Thread cancellation discards a result; it cannot stop already-running CPU work.
The input/grammar gates bound what enters that worker. An interruption can move
on before the worker finishes, and its obsolete result cannot reach synthesis.

## Task ownership and interruption

Both responder and formatter are awaited as explicit child futures. A callback
may clear its own cancellation count without altering the transport owner's
count. Caller cancellation is propagated before obsolete errors or speech can
be emitted. The reply's turn lease is checked again after formatting.

The provider response deadline uses monotonic time and rejects late output even
when the provider catches timeout cancellation, clears its own count, returns
normally, raises an ordinary error, or briefly blocks the event loop. This is a
late-result rejection guarantee, not preemptive cancellation of synchronous CPU
work or proof that a model server stops computing. A pre-existing limitation
remains: a responder that catches cancellation and then waits forever can retain
the runtime lock past the deadline. This batch rejects its eventual late result
but does not promise a hard wall-clock return against a non-cooperative callback.

An authorized model exchange may already have committed when speech formatting
starts. A later interruption suppresses that speech; it does not delete the
already-valid history. Tests explicitly distinguish this from cancellation
before the model reply, which must persist nothing.

## Validation

- Independent re-review: **66 selected tests passed**, including actual synthesis
  preservation of all reported operator/code/table cases and 8000 nested brackets;
  the bracket handoff took about 2.8 ms and blocked-worker interruption about
  0.2 ms in that host probe (not device-performance acceptance)

- Full strict Brain: **676 passed, 0 failed, 0 skipped**, Python 3.12.14

- Actual Pipecat queue/TTS suite: **23 passed**
- New synthesis probes preserve the real TTS aggregation/filter/context machinery
  and replace only `run_tts` audio generation; no microphone, model or audio device
- Safe links/headings, repeated numbers, literal math/code/table boundaries,
  8000-character nested brackets and off-loop interruption covered
- Real interruption tests include a formatter that calls `uncancel()` and either
  returns or raises; no one-second upstream cancellation-timeout fallback,
  no stale speech, successful fresh-turn recovery, no remaining tasks
- Direct runtime cancellation/deadline regressions verify no SQLite history or
  replay receipt from rejected output and successful retry with persona intact
- Installed filter source bytes match the declared pinned Git blob
- Production hash lock and package dependencies unchanged

```sh
cd brain
python scripts/verify_integrations.py --output /tmp/mygpt-speech-evidence
# With the already-pinned realtime extra installed:
python -m pytest -q realtime_tests
```
