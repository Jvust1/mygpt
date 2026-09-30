## 2026-09-30 · Companion V2 multi-upstream direct adoption

PR #15 now contains bounded direct/pinned integration from:
- **AIRI / MIT** — authority-separated conversation, Character Card, emotion vocabulary and ACT control marker semantics.
- **Mem0 / Apache-2.0** — explicit correctable memory lifecycle and audit history; Android adds full-erasure `purge`.
- **llama.cpp / MIT** — full upstream git submodule pin plus real Android JNI bridge; no GGUF weights committed.
- **sherpa-onnx / Apache-2.0** — source submodule pin, explicit runtime binary pin, 16 kHz streaming ASR and local Melo TTS; no model weights committed.
- **EasyFloat / Apache-2.0** — only permission-free current-Activity drag/snap logic; no system overlay permission.
- **Apache Commons Compress 1.28.0 / Apache-2.0** — dependency for direct official ZIP/TAR.BZ2/TAR.GZ model archive ingestion.

The final candidate remains dependency-minimized: large model weights are user-selected inputs stored app-private, not vendored into Git. Book and Live repositories are not mutated.

---

## Additional direct adoption — Mem0 + sherpa-onnx + AIRI Character/Emotion (2026-09-29)

- `mem0ai/mem0@94c3fe9f...` (Apache-2.0): adapted update/delete/history audit semantics into `brain/mygpt_brain/memory_store.py`. MyGPT keeps memory creation explicit and local; no transcript-wide auto-capture was enabled.
- `k2-fsa/sherpa-onnx@040afe36...` (Apache-2.0): adapted the Android Java demo's 16 kHz mono AudioRecord/PCM normalization foundation. Recognizer/model weights are **not** bundled yet; microphone permission is not auto-requested.
- `moeru-ai/airi@b40e3e87...` (MIT): added Character Card fields and the shared renderer-neutral emotion vocabulary. Imported cards cannot self-promote to system authority; explicit approval is required.

Attribution and upstream licenses are stored under `third_party/airi`, `third_party/mem0`, and `third_party/sherpa-onnx`.

---

## Implemented bounded adoption — Project AIRI (2026-09-29)

AIRI is no longer only a research reference. Draft PR #15 directly adapts a bounded MIT-licensed subset from pinned upstream commit `b40e3e87b149ea5fb75d4944440493829e601411`.

Implemented in MyGPT:
- authority-separated chat/context contracts;
- stable stored/current message merge and deduplication;
- bounded recent-turn compaction;
- durable SQLite session persistence and idempotent request receipts;
- explicit local memory (MyGPT-original integration layer; transcripts are not auto-promoted);
- loopback-only Ollama provider adapter and local developer CLI.

Attribution is mandatory and lives in `third_party/airi/LICENSE` + `third_party/airi/NOTICE.md`. This does **not** vendor the whole AIRI monorepo. Android Pocket/Tamagotchi and richer agent modules remain later candidates and must be adopted only when they directly advance the final MyGPT product.

Verification at this checkpoint: local candidate tests 18/18 pass. GitHub Actions run 36590899728 failed twice before step 1 with runner_id=0, so remote code tests have not executed yet.

---

# mygpt Open-Source Adoption Plan

Date: 2026-09-27
Target branch: `codex/progress-mygpt-20260927`
Final product target: Book Android + mygpt companion brain + Live character skins.

## Policy

This registry brings external open-source work into **project planning, architecture and dependency evaluation**. It does **not** mean copying entire upstream repositories into mygpt.

Rules:
- Prefer a small adapter around an upstream dependency over vendoring a whole repository.
- No upstream source code is copied by this catalog commit.
- Before any direct code import or dependency pin, verify the exact current license, version/tag, Android compatibility, security posture and transitive dependencies.
- Custom/copyleft/restricted runtimes stay reference-only until an explicit license decision is recorded.
- Book remains the authority for learning context, Live remains the authority for character skins/assets, and mygpt owns conversation/supervision orchestration.
- Privacy-sensitive capabilities such as UsageStats, accessibility, overlays, microphone and notifications must be opt-in and purpose-bounded.

## Immediate adoption tracks

1. **Android host foundation** — Now in Android, Compose samples, Architecture Samples, coroutines, serialization, Koin, SQLDelight, Turbine, OkHttp.
2. **Persistent companion surface** — EasyFloat + Android foreground/lifecycle patterns; keep Shizuku optional and non-required.
3. **Book supervision signals** — Book semantic events first; ActivityWatch/UsageStats patterns only as secondary local signals.
4. **Local conversation** — benchmark llama.cpp as the primary GGUF candidate against ExecuTorch, MLC and ONNX paths.
5. **Voice** — whisper.cpp / sherpa-onnx / Silero VAD; add Oboe only when native low-latency audio is justified.
6. **Long-term memory** — keep current PydanticAI core; borrow memory architecture ideas from Mem0/Letta/LangGraph while keeping local data minimal.
7. **Live character adapter** — define a renderer-neutral `CharacterRuntime` contract; study Cubism Java/Native samples, Spine runtimes and Inochi2D without making a restricted SDK the project authority.

## Candidate registry

| # | Repository | Area | Priority | Adoption mode | Intended value |
|---:|---|---|---|---|---|
| 1 | `android/nowinandroid` | Android architecture | P0 | ADOPT_PATTERN | Production-grade Kotlin/Compose modularization, offline-first architecture, testing. |
| 2 | `android/compose-samples` | Android UI | P0 | ADOPT_PATTERN | Official Compose interaction, state, animation and chat UI patterns. |
| 3 | `android/architecture-samples` | Android architecture | P0 | ADOPT_PATTERN | Testable state/data/domain separation patterns. |
| 4 | `androidx/androidx` | Android platform | P1 | REFERENCE | Authoritative AndroidX implementation/reference for lifecycle, Room, WorkManager and Compose internals. |
| 5 | `android/ndk-samples` | Android native | P1 | ADOPT_PATTERN | JNI/NDK patterns for local inference/audio runtimes. |
| 6 | `termux/termux-app` | Android runtime | P2 | REFERENCE | Long-running Android process/service and native-runtime integration patterns. |
| 7 | `firebase/quickstart-android` | Android services | P3 | REFERENCE_ONLY | Reference for notifications/background integration only; cloud features are not default architecture. |
| 8 | `princekin-f/EasyFloat` | Floating companion | P0 | DEPENDENCY_CANDIDATE | Draggable system/app floating windows, lifecycle filtering and overlay permission flow. |
| 9 | `guolindev/PermissionX` | Permissions | P0 | DEPENDENCY_CANDIDATE | Runtime permission UX for microphone, notifications and related Android permissions. |
| 10 | `RikkaApps/Shizuku` | Advanced Android privileges | P2 | REFERENCE_ONLY | Optional advanced privilege architecture; final product must not require it by default. |
| 11 | `ActivityWatch/aw-android` | Supervision signals | P0 | ADOPT_PATTERN | UsageStats-based local activity observation for low-cost supervision signals. |
| 12 | `googlesamples/android-AppUsageStatistics` | Supervision signals | P1 | REFERENCE_ARCHIVED | Small authoritative UsageStatsManager sample; archived but still useful API reference. |
| 13 | `google/oboe` | Audio | P1 | DEPENDENCY_CANDIDATE | Low-latency Android audio path if voice mode needs native streaming. |
| 14 | `square/okhttp` | Networking | P0 | DEPENDENCY_CANDIDATE | Reliable Android HTTP/WebSocket transport for bounded Book/mygpt services. |
| 15 | `square/retrofit` | Networking | P1 | DEPENDENCY_CANDIDATE | Typed service interface option on top of OkHttp. |
| 16 | `sqldelight/sqldelight` | Local persistence | P0 | DEPENDENCY_CANDIDATE | Typed local SQL for companion state, receipts, memory indexes and offline data. |
| 17 | `Kotlin/kotlinx.coroutines` | Concurrency | P0 | DEPENDENCY_CANDIDATE | Structured concurrency and Flow for Book events, model tokens and character state. |
| 18 | `Kotlin/kotlinx.serialization` | Contracts | P0 | DEPENDENCY_CANDIDATE | Stable typed JSON contracts between Book, Live adapters and mygpt. |
| 19 | `InsertKoinIO/koin` | Dependency injection | P1 | DEPENDENCY_CANDIDATE | Lightweight DI for Android modules and runtime swaps. |
| 20 | `cashapp/turbine` | Testing | P0 | DEPENDENCY_CANDIDATE | Deterministic Flow testing for event-driven supervision and chat streams. |
| 21 | `coil-kt/coil` | Media/UI | P1 | DEPENDENCY_CANDIDATE | Compose-first image loading and cache patterns for companion assets. |
| 22 | `bumptech/glide` | Media/UI | P2 | REFERENCE | Mature image/GIF lifecycle and caching reference where Coil is insufficient. |
| 23 | `ktorio/ktor` | Networking/server | P2 | EVALUATE | Alternative local client/server stack for Kotlin-first loopback transport. |
| 24 | `airbnb/mavericks` | State management | P2 | REFERENCE | Unidirectional immutable UI state patterns for complex companion surfaces. |
| 25 | `ggml-org/llama.cpp` | On-device LLM | P0 | ENGINE_CANDIDATE | Primary GGUF local LLM candidate; current upstream includes Android bindings/examples. |
| 26 | `ggml-org/whisper.cpp` | Speech-to-text | P0 | ENGINE_CANDIDATE | Offline Android-capable speech recognition and streaming voice command path. |
| 27 | `k2-fsa/sherpa-onnx` | Speech stack | P0 | ENGINE_CANDIDATE | Cross-platform offline ASR/TTS/VAD options suitable for Android evaluation. |
| 28 | `pytorch/executorch` | On-device AI | P1 | ENGINE_EVALUATION | PyTorch-native Android runtime and AAR; benchmark against llama.cpp/ONNX paths. |
| 29 | `google-ai-edge/gallery` | On-device GenAI UX | P1 | ADOPT_PATTERN | Official Android on-device GenAI app patterns for model management and local chat. |
| 30 | `google-ai-edge/mediapipe` | On-device perception | P2 | ENGINE_EVALUATION | Optional local perception/signal processing; not a default surveillance path. |
| 31 | `microsoft/onnxruntime` | On-device AI | P1 | ENGINE_EVALUATION | Mature mobile inference runtime for non-LLM classifiers, embeddings and speech models. |
| 32 | `mlc-ai/mlc-llm` | On-device LLM | P1 | ENGINE_EVALUATION | Alternative optimized mobile LLM runtime for benchmarking. |
| 33 | `ollama/ollama` | Desktop/local model | P1 | ADOPT_PATTERN | Existing desktop/local-provider interoperability and model lifecycle reference. |
| 34 | `open-webui/open-webui` | Chat/provider UX | P2 | REFERENCE | Provider routing, chat UX and local model management ideas; not a mobile dependency. |
| 35 | `snakers4/silero-vad` | Voice activity detection | P1 | ENGINE_CANDIDATE | Lightweight VAD to avoid continuous ASR and reduce battery/compute. |
| 36 | `coqui-ai/TTS` | Text-to-speech | P2 | EVALUATE | TTS architecture/model reference; verify maintenance and model licenses before adoption. |
| 37 | `rhasspy/piper` | Text-to-speech | P3 | REFERENCE_ARCHIVED | Archived fast local TTS implementation; useful historical architecture reference. |
| 38 | `OHF-Voice/piper1-gpl` | Text-to-speech | P2 | LICENSE_GATED_REFERENCE | Current Piper continuation; GPL implications require explicit review before integration. |
| 39 | `mem0ai/mem0` | Long-term memory | P1 | ADOPT_PATTERN | Memory extraction/retrieval architecture useful for companion continuity. |
| 40 | `pydantic/pydantic-ai` | Agent runtime | P0 | CURRENT_CORE_AND_REFERENCE | Already aligned with current Brain/TestModel work; retain as typed agent/runtime reference. |
| 41 | `langchain-ai/langgraph` | Agent orchestration | P2 | REFERENCE | Durable state-machine/agent graph patterns for supervision workflows. |
| 42 | `letta-ai/letta` | Agent memory | P2 | REFERENCE | Stateful long-running agent memory patterns. |
| 43 | `chroma-core/chroma` | Retrieval | P2 | REFERENCE | Embedding/vector retrieval reference; Android final form should prefer lighter local storage unless needed. |
| 44 | `qdrant/qdrant` | Retrieval | P2 | REFERENCE | Vector retrieval and filtering architecture for optional desktop/server memory backends. |
| 45 | `Inochi2D/inochi2d` | Character runtime | P1 | ADOPT_PATTERN | Open real-time 2D puppet SDK; strong reference for renderer abstraction and parameter-driven animation. |
| 46 | `Inochi2D/inochi-session` | Character runtime | P2 | REFERENCE | Reference for driving 2D puppets in a long-running interactive session. |
| 47 | `Live2D/CubismNativeSamples` | Live2D character runtime | P0 | LICENSE_GATED_REFERENCE | Official native Cubism samples; use to design Live adapter, subject to Live2D SDK/Core licensing. |
| 48 | `Live2D/CubismJavaFramework` | Live2D character runtime | P0 | LICENSE_GATED_REFERENCE | Official Java framework relevant to Android character rendering; Cubism Core is separate. |
| 49 | `Live2D/CubismJavaSamples` | Live2D Android samples | P0 | LICENSE_GATED_REFERENCE | Official Android Studio-friendly sample path for Java/Cubism integration. |
| 50 | `EsotericSoftware/spine-runtimes` | Spine character runtime | P1 | LICENSE_GATED_REFERENCE | Relevant if Live skins include Spine assets; runtime terms require license review. |
| 51 | `guansss/pixi-live2d-display` | Live2D API design | P2 | REFERENCE | High-level Live2D interaction/motion API ideas useful for adapter design; web stack is not final Android runtime. |

## What “adopt” means

- `DEPENDENCY_CANDIDATE` / `ENGINE_CANDIDATE`: eligible to become a pinned dependency after a focused compatibility/license benchmark.
- `ADOPT_PATTERN`: copy the **idea/architecture/test pattern**, not upstream code wholesale.
- `CURRENT_CORE_AND_REFERENCE`: already aligned with current implementation and remains a first-class reference.
- `ENGINE_EVALUATION`: benchmark candidate; do not add multiple competing runtimes to the shipping APK without evidence.
- `REFERENCE` / `REFERENCE_ONLY` / `REFERENCE_ARCHIVED`: learn from it, but do not introduce it as a production dependency by default.
- `LICENSE_GATED_REFERENCE`: no code/assets are imported until the license decision is separately documented.

## First implementation sequence

The first Android integration spike should stay narrow:

`Book event contract -> companion state machine -> Live CharacterRuntime adapter -> local chat engine interface -> optional voice -> supervision signals`

The project should not start by merging all 50+ upstream codebases. The registry is deliberately broad so mygpt can reuse proven ideas while the shipping dependency set stays small, auditable and replaceable.
