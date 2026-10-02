# Pipecat direct response-lifecycle code adoption

Upstream: https://github.com/pipecat-ai/pipecat

Pinned source revision: `49dea682fb84bfc515d881d00dfeaaa9e9f1075f`

License: BSD-2-Clause. Copyright (c) 2024–2026, Daily.
The complete license is retained in `LICENSE` (upstream Git blob
`88cf66570d9c1e77bcb44f9eeacfa051d840267c`).

GitHub API eligibility checked 2026-09-30 18:28 UTC: **16,090 stars**,
BSD-2-Clause, source repository `pipecat-ai/pipecat`.

## Source and local derived code

- `src/pipecat/services/openai/base_llm.py`,
  Git blob `3758eaceba18e97a21289f29c43ac09a0385ea57`
  - `BaseOpenAILLMService.process_frame` response-start / try / response-end
    lifecycle is adapted directly into MyGPT's existing companion processor
- `src/pipecat/processors/frame_processor.py`,
  Git blob `1d380a04060d80acaef322f95058f0700840ca2f`
  - upstream interruption/cleanup behavior is delegated to the real
    `FrameProcessor`, not reimplemented as a competing queue
- `src/pipecat/frames/frames.py`,
  Git blob `bd2bde1f592d18e60f0faf8c98052c7cce90aa6b`
  - response and interruption frame contract used by the actual runtime
- `src/pipecat/utils/asyncio/task_manager.py`,
  Git blob `35bdec122c78829d45412dbe8ae8637891269ebd`
  - `TaskManager.cancel_task` ownership distinction between a cancelled child
    and a newly cancelled caller is directly adapted into
    `brain/mygpt_brain/voice_activation.py`
  - owned task registration / completion removal / cancellation snapshots are
    also adapted into `brain/mygpt_brain/companion_service.py` for the existing
    threaded native HTTP entry point

Derived/adapted local file: `brain/mygpt_brain/pipecat_bridge.py`.
Runtime verification uses the separately version-pinned PyPI release
`pipecat-ai==1.12.0`; the release is not claimed to be the source revision above.

MyGPT modifications: finalized downstream transcription replaces OpenAI context
frames; the existing companion runtime supplies the response; local generation
leases are invalidated before upstream cancellation is awaited; a stale reply
is rejected before SQLite commit; stale response-end frames are suppressed after
interruption; only cleaned visible text and presentation metadata go downstream.
Provider errors are sanitized. No OpenAI backend, cloud transport, model or audio
device is enabled by this integration.

## Wake/ASR entry-path completion

The existing `VoiceActivationRuntime` now owns and cancels its active asynchronous
ASR/model task when a newer wake-qualified utterance supersedes it. The port keeps
the self-await guard and cancellation-count check; MyGPT additionally suppresses
obsolete child errors without logging source text, preserves external caller
cancellation across all teardown outcomes, and keeps retiring tasks owned until
completion. Generation guards run after transcription, before chat commit and
before caller delivery. No Pipecat SDK import is needed by this local path.

## Native HTTP authorization lifecycle

The existing native HTTP executor now tracks its cross-thread request futures,
removes them on completion, and cancels a snapshot when local authorization is
revoked. MyGPT adaptations use a short threading lock rather than Pipecat's
single-loop task dictionary; callbacks run outside that lock. The same runtime
generation guard checks authorization before inference/commit, and response
delivery checks it again. A MyGPT authorization completion guard additionally
serializes the synchronous SQLite/cache commit and successful HTTP write
admission with revoke. Already-admitted sections may finish before revoke can
acknowledge; expiry blocks later admission, rather than retroactively deleting
completed history. Authorization TTL bounds the future wait. This closes
the native API's admitted-request gap without replacing its loopback/token/Host
security boundary or introducing another web framework.

## 2026-09-30: existing Markdown filter wired into actual speech output

The production companion processor invokes the installed, pinned upstream
`MarkdownTextFilter.filter` only for short, flat heading/link presentation.
Source: `src/pipecat/utils/text/markdown_text_filter.py`, Git blob
`08b2a1f743d8cf7d2faa937915e97f52e3997d04` at the same immutable commit above.
The installed 1.12.0 bytes are asserted against this blob in real-SDK tests.
Full BSD-2-Clause copyright/license remains in this directory.
Eligibility rechecked 2026-09-30 20:25 UTC: **16,093 stars**, not archived.

No duplicate Markdown implementation or new dependency is vendored. Independent
review found unrestricted upstream filtering destructive to learning operators,
code and table cell boundaries, and expensive on nested brackets. MyGPT therefore
preserves ambiguous/operator/code/table/list/image replies verbatim, parses only
a flat recognized subset of at most 1200 characters and 16 delimiters, and runs
eligible conversion off the event loop in a worker. Repeated-sequence deletion
is disabled. A new filter per response avoids cross-turn state. Native/durable
replies remain unchanged. Running thread work cannot be forcibly stopped, but
interruption discards its output and the input/grammar gates bound parser work.

The existing task-ownership adaptation is completed around both responder and
speech formatter callbacks with explicit child futures. A callback's `uncancel()`
cannot clear the calling transport task's cancellation. Late provider output
is rejected if the monotonic response deadline passed, including a callback
that swallows timeout cancellation or briefly blocks the event loop. This does
not claim preemptive interruption of synchronous CPU work or a hard deadline
against a callback that never finishes cancellation. A model exchange committed
before a later speech interruption remains in history; obsolete speech is
suppressed rather than retrospectively deleting valid history.


## Voice receipt recovery hardening (2026-09-30)

The existing MyGPT bridge adds ephemeral per-instance correlation randomness to
its automatic request IDs, preventing deterministic counter/text collisions
against durable receipts after restart. This is MyGPT integration code, not a
new upstream feature or an authentication identity. Explicit request IDs retain
the existing SQLite idempotency/fingerprint checks.

The Pipecat processor accepts optional `mygpt.request_id` frame metadata, carries
the trusted receipt replay flag into response-end metadata, and suppresses repeat
LLM text/formatting/TTS output for completed receipt retrieval. Start/end lifecycle
framing remains based on the same pinned BaseOpenAILLMService pattern. Actual SDK
queue/TTS plus close/reopen/cancellation tests verify recovery; no exactly-once
physical-audio delivery or new persisted playback acknowledgment is claimed.


## Android completion ownership (2026-10-01)

`android_spike/src/main/java/dev/mygpt/spike/VoiceOutputCompletion.java` carries
the already-used turn invalidation/lease concept into the actual Companion V2
TTS completion callbacks. This is MyGPT integration code, not a literal upstream
class or another dependency. It uses fresh object leases, guards both callback
kinds, invalidates on stop/toggle and closes on destroy. JVM callback tests and
production-source wiring checks cover the helper; AudioTrack/JNI admission and
physical cancellation remain separate boundaries. Full BSD-2-Clause license and
pin notices are bundled with every Android shared-source consumer.
