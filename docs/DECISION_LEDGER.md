# Decision Ledger

## D001 — mygpt is the companion/orchestrator
mygpt is the user-facing long-term companion. Book, StudyMate, and ChatContextVault remain separate authoritative systems with clear boundaries.

## D002 — companionship outranks check-in gamification
The product is not primarily a streak tracker. Quiet presence, useful intervention, teaching, encouragement, and conversation are the core experience.

## D003 — Book-first perception
For Book-based learning, structured Book state is superior to screen recognition and is the default input to mygpt.

## D004 — screen vision is fallback, not foundation
Screen capture is reserved for unsupported external learning contexts and requires explicit session-scoped permission.

## D005 — event-driven awareness
Local state changes and semantic events should trigger reasoning. The system should not stream every screen frame to a cloud model.

## D006 — learning evidence hierarchy
Time-on-page is weak evidence. Recall, explanation, practice behavior, and repeated concept interactions should carry more weight in learning-state estimates.

## D007 — ambiguity must be conversationally resolved
When signals cannot distinguish paper study, deep thinking, and distraction, mygpt asks the user rather than asserting a hidden state.

## D008 — Shadow is explicit simulation
ChatContextVault may ground an optional Shadow mode, but the system must not impersonate the real person or imply simulated messages are authentic.

## D009 — mygpt keeps its own identity
Ordinary emotional support and companionship are delivered by mygpt itself, not by continuously roleplaying the Shadow persona.

## D010 — no autonomous UI control in v0.1
The first version focuses on perception, understanding, and conversation. Arbitrary UI automation is deliberately deferred.

## D011 — privacy exclusion zones
Private messages, credentials, financial screens, password fields, and unrelated personal information are excluded by default from capture/upload.

## D012 — affordable continuous presence
Continuous presence should mostly be local and event-driven; expensive cloud reasoning or real-time voice sessions are invoked only when useful.

## D013 — real relationships are not competitors
The product must not frame itself as the only entity that understands the user or push the user away from real-world relationships.

## D014 — Jonah is the first companion surface candidate
Use the already validated Jonah sprite as mygpt's initial visual companion. Keep the renderer framework-neutral until a production host is selected. The component accepts explicit states and emits user actions; product logic remains outside the visual layer.

## D015 — mobile app surface before system overlay
First validate Jonah inside the mygpt mobile surface with touch, safe-area, reduced-motion, and hide/restore behavior. Treat an Android cross-application floating window as a separate Android Studio milestone with explicit OS permission and physical-device acceptance evidence.

## D016 — imported local content remains explicitly unverified
Local files/manual text can be useful before a production Book/Android bridge is available, but user-supplied bytes must never be silently promoted to authenticated Book facts. Intake is default-off, one-record/bounded, preview-and-consent driven, and uses a separate `USER_SUPPLIED_UNVERIFIED` context/reference namespace.

## D017 — recovery is an explicit product requirement
A runnable candidate is not considered recoverable only because GitHub contains files. Checkpoints should provide a deterministic source-only bundle from an immutable commit, an externally recorded SHA-256, a read-only environment doctor, an explicit launcher, and clean-directory recovery evidence. Launchers must not auto-install dependencies, inherit provider credentials, or silently enable intake/provider capabilities.

## D018 — integrate stale review lines by capability, not by state-file overwrite
When an older review branch contains useful additive runtime capability but also replaces newer project-state documents, create a fresh non-default integration branch from the newer accepted baseline and transplant only the bounded runtime/test capability. Preserve the old branch as provenance; do not resolve review-stack conflicts by overwriting current state or rewriting history.

## D019 — final mobile product pairs mygpt with Book Android
The final product target is an Android companion that works alongside the Book Android app. Book remains the learning surface and authoritative structured study-context source; mygpt consumes bounded Book context/events to understand the current learning situation.

## D020 — Live is the authoritative character-skin source
The final visible companion should use character skins and presentation assets from the separate Live project. The current Jonah component is retained as a validated interaction prototype, not as the final character-content authority. mygpt must not silently fork or duplicate Live's authoritative skin collection.

## D021 — mygpt owns conversation and supervision behavior
mygpt is responsible for conversation, teaching assistance, encouragement, supervision and intervention policy. Character appearance comes from Live and learning truth comes from Book. Supervision should be evidence-driven and graduated from silent presence to reminders or active supervision; ambiguous states should be resolved conversationally rather than by asserting that the user is distracted.

## D022 — upstream adoption is broad in research and narrow in shipping dependencies
mygpt maintains a broad upstream registry across Android, local AI, voice, supervision, memory and character runtimes so mature open-source work is continuously reused. “Adopt” does not mean bulk-vendoring every repository. Production dependencies must remain small, replaceable and explicitly version/license/security checked; restricted/copyleft projects remain reference-only until a separate decision permits their integration. The canonical registry is `governance/open_source_sources.json` and the adoption plan is `docs/OPEN_SOURCE_ADOPTION.md`.

## D023 — skin integration must maximize authored package capabilities
A skin is not considered fully integrated merely because one skeleton, atlas, texture or idle animation renders. Live must first inventory and classify the complete package, including alternate forms, skeletons, atlases, textures, animations, expressions, transitions, effects, audio references and configuration-driven state changes. mygpt consumes a normalized capability contract from Live and maps semantic companion states to those capabilities. Unknown or intentionally unsupported resources must be explicitly recorded. The canonical implementation plan is `docs/SKIN_FULL_UTILIZATION_PLAN.md`. For skin `3714430278`, default / aim / cover resources and their authored transitions must be treated as one multi-state skin rather than discarding opaque `misc_*` resources.

## D024 — skin audio is out of scope
Skin integration in mygpt/Live is visual and interaction focused. Voice, BGM and SFX packaged with skins are not loaded, played, mapped or counted toward skin utilization/completion. Full-utilization requirements cover visual forms, animations, expressions, transitions, effects, layout and interaction only.


## D025 — companion chat authority and memory are explicit/local
MyGPT directly adapts AIRI's MIT-licensed authority-separated conversation, merge/deduplication, bounded-history and local-first session persistence patterns from pinned upstream commit `b40e3e87b149ea5fb75d4944440493829e601411`. Trusted persona/developer instructions remain distinct from application context and recalled memory; context/memory is projected as data, not silently upgraded to system authority. Long-term memory is explicit/reviewed local state rather than automatic transcript ingestion. The first real provider adapter is deliberately loopback-only Ollama; arbitrary remote provider URLs are outside this candidate. Full attribution is retained in `third_party/airi/`.

## D026 — long-term memory must be correctable and auditable
MyGPT memory is not append-only truth. Following Mem0-style lifecycle semantics, explicit memories support update, delete and history. Updates preserve memory identity fields and append an audit event; deletes remove the active memory while preserving the audit event. Raw conversation is not automatically promoted into long-term memory.

## D027 — voice capture is explicit and engine-neutral
The first Android voice layer is a 16 kHz mono PCM capture foundation adapted from sherpa-onnx. It does not request RECORD_AUDIO permission automatically, persist raw audio, or commit to one ASR engine. Permission must follow an explicit user action; sherpa-onnx, whisper.cpp or another local engine can be benchmarked behind the same frame interface.

## D028 — brain-to-character emotion uses a renderer-neutral protocol
MyGPT adopts AIRI's renderer-neutral emotion vocabulary so chat/voice logic does not depend on one skin. A specific skin may play only authored semantically matching animations. For 3714430278, happy/sad/surprised map to smile/sad/surprise; unsupported emotions fall back to idle rather than guessing with unrelated combat/action animations.

## D029 — Android local model stacks stay isolated until device acceptance
llama.cpp's current Android binding requires a newer Android/Java/native toolchain than the accepted Java-8 Spine host. MyGPT therefore keeps `android_llm_spike` isolated (minSdk 33, Java/Kotlin 17) and pins the complete upstream llama.cpp source as a submodule. The existing Java-8/minSdk24 Spine artifact is not silently upgraded. Merge/consolidation waits for exact-head build and Xiaomi 14 acceptance.

## D030 — voice input/output is explicit, local and model-weight external
Microphone capture starts only after an explicit user action and RECORD_AUDIO grant. Raw audio is not persisted. ASR/TTS weights are external user-selected model packages stored app-private; sherpa source and runtime identities are recorded separately. TTS is default-off and streams generated samples to AudioTrack without writing audio files.

## D031 — long-term Android memory is explicit and erasable
Companion V2 does not auto-capture chat transcripts. Relevant explicit memories may be recalled as application data, never system authority. Updates retain audit history. Android additionally exposes a purge path used by explicit forget commands to remove both active memory content and its audit history.

## D032 — official model archives are parsed through a strict allowlist
MyGPT accepts ZIP, TAR.BZ2 and TAR.GZ model packages through Apache Commons Compress 1.28.0. Archive paths are never materialized directly: ASR/TTS installers select known basenames only, enforce per-file and total decompressed-size limits, and preserve README/LICENSE when present.

## D033 — Book Android context requires same-signature explicit delivery
Companion V2 exposes a custom Android signature permission for Book semantic context. The receiver also requires explicit targeting to the MyGPT package/component, validates TTL, monotonic sequence, session identity and source SHA-256, and stores accepted Book text in process memory only. Every llama user turn explicitly declares current Book state as fresh or unavailable; prior Book blocks retained by llama KV history are historical data only.

## D034 — recent conversation persistence is not long-term memory
Visible user/assistant text may be kept in a bounded local conversation store solely to recover conversational continuity after model reload/process restart. It excludes Book blocks, recalled-memory blocks, raw audio, TTS audio, system prompt and ACT markers. Explicit long-term memory remains a separate user-controlled store and policy.

## D035 — Activity lifecycle must not destroy llama.cpp's process singleton
The pinned llama.cpp Android AiChat implementation retains a process-wide static InferenceEngine singleton. MyGPT therefore unloads models on Activity-level close/replacement and leaves final native backend destruction to process termination. Destroying the singleton inside Activity lifecycle is prohibited because later Activity recreation would reuse a destroyed singleton reference.

## D036 — default on-device GGUF is benchmark-gated
MyGPT does not name a default Xiaomi 14 GGUF before device evidence exists. Candidate models must be compared using the local llama benchmark plus real-chat first-token latency, sustained memory/thermal behavior, crash/OOM behavior and reply quality. Benchmark reports stay app-private unless the user explicitly collects the local evidence directory.

## D037 — native PiP is the first cross-app companion surface
Companion V2 uses Android Picture-in-Picture as the first cross-application 3714430278 surface. PiP requires explicit user entry, shows only the character render shell, does not auto-enter, and does not require SYSTEM_ALERT_WINDOW, Accessibility, screen capture or a background overlay service. System-overlay approaches remain a later separately permission-gated option.

## D038 — supervision is explicit Book signal + local MyGPT consent
MyGPT does not infer attention, motivation or failure from inactivity, screen observation or time spent. Supervision cues are driven only by same-signature explicit Book study events plus MyGPT-local per-session user consent. Book cannot enable supervision. PRACTICE_REPEATED_ERROR stays QUIET without opt-in and can yield GENTLE_CHECK_IN only after local opt-in and the cooldown gate. End/revoke clears consent.
