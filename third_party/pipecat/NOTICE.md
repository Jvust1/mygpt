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
