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
