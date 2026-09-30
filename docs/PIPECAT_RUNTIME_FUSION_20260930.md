# Pipecat response and interruption lifecycle fusion

Base: AIRI runtime fusion PR #31, commit
`12e51e11ca91eb192a360712a93da76ff78f9bde`.

## Direct upstream reuse

Pipecat had **16,090 stars** at the live GitHub API check on 2026-09-30 18:28 UTC.
Its BSD-2-Clause response-start / try / response-end implementation is adapted
from `BaseOpenAILLMService.process_frame` at source revision
`49dea682fb84bfc515d881d00dfeaaa9e9f1075f` into the existing MyGPT processor.
Exact source blobs, copyright and complete license are retained in
`third_party/pipecat/`. The optional runtime dependency is now reproducibly pinned
to the separately tested PyPI release `pipecat-ai==1.12.0`.

## Reproduced functional gap

The old bridge produced only a `TextFrame`. Real Pipecat `TTSService` buffers a
short response without terminal punctuation until the end-of-response frame
arrives. The regression test proves that the old shape leaves `继续学这一节`
buffered, while the fused response lifecycle flushes exactly that text.

## Runtime changes

`TranscriptionFrame(finalized=True)` flowing downstream now invokes:

`LLMFullResponseStartFrame → CompanionChatRuntime → LLMTextFrame → LLMFullResponseEndFrame`

- The existing AIRI normalization still removes ACT syntax before speech
- `LLMTextFrame.metadata["mygpt"]` carries the request ID and renderer-neutral
  presentation emotion separately from spoken text
- The real Pipecat `FrameProcessor` continues owning its queues and cancellation
- Interruption invalidates MyGPT's generation lease **before** awaiting the
  superclass handler; cancellation-resistant late providers cannot commit stale
  SQLite history or emit stale speech/end frames
- A fresh final transcription works after interruption; cancel/cleanup invalidate
  in-flight work. `EndFrame` gracefully drains earlier queued work, then closes
  the bridge. Closed bridges reject later work
- Upstream transcriptions pass through without starting a model call
- Non-interruption provider failures emit a sanitized error and close the
  response lifecycle without exposing provider details or transcript content
- Providers that swallow cancellation and then return or raise still propagate
  the owning task's cancellation; this avoids the upstream cancellation-timeout
  fallback and prevents obsolete provider errors during interruption

Only explicitly finalized transcriptions are accepted. The factory's previous
individual test-class arguments are replaced by a frame-module test seam;
normal production construction remains `create_pipecat_companion_processor(bridge)`.

## Validation and reproduction

In a clean environment, install from `brain/` using:

```sh
python -m pip install '.[test,integrations,realtime]'
python scripts/verify_integrations.py --output /tmp/mygpt-pipecat-acceptance
python -m pytest -q realtime_tests
```

Local CPython 3.12.14 results:

- Full strict Brain acceptance: **574 passed, 0 failed, 0 skipped**
- Real installed Pipecat tests: **7 passed**, covering TTS flush, clean ACT speech,
  urgent interruption/cancel and graceful end-of-pipeline draining
- Dependency consistency and runtime compilation: pass

Real-SDK tests use production factory, real queues/frame classes, real
interruption/cancel task handling and real TTS text aggregation. The model and
final synthesis boundary are deterministic probes. Network use is explicitly
blocked; no audio devices, paid providers, model weights or user content are
used. Cancellation tests deliberately make the model swallow cancellation and
try to return late, then verify no stale speech or persisted exchange.

The dedicated `pipecat-runtime-acceptance.yml` runs the full strict Brain suite
and real-SDK tests on hosted Python 3.13 for the exact published head.

This is a working pipeline component and offline integration proof, not a new
microphone/transport launcher or phone/tablet deployment. Audible speech,
microphone/ASR, real-model quality, Qwen on the phone, Book signing/transport and
character/device acceptance remain separate gates. No merge or deployment.
