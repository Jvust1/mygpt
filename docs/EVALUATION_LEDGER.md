## E-FUSION-20261001 — coherent draft stack hosted acceptance

**Checked:** 2026-10-01 01:12:45 UTC. **Implementation:** draft [PR #51](https://github.com/Jvust1/mygpt/pull/51),
`8e9c430b4416154560da00e4faeefe999edf25e6`, public `Jvust1/mygpt`.
Main and the original PR #15 product/device track remain unchanged; no adoption,
merge or deployment follows from these checks.

**Exact-head run:** [36799362430](https://github.com/Jvust1/mygpt/actions/runs/36799362430),
success. Production job `110170011091`, Java 8 `110170011455`, Java 17
`110170011485`, source recovery `110170011480`; all had nonzero runners and
executed steps.

- Strict Python: 764 passed, zero failures/skips
- Actual upstream/component stories: 48 passed, zero failures/skips
- Root Python: 65; JavaScript: 66
- Java 8/17: 22 entrypoints each, including 327 Gson, 109 sklearn, 128 AIRI,
  3520 history-budget and 1288 Book Unicode projections
- Fresh source recovery: 764 strict, 65 root Python, 66 JavaScript, 22 Java17
  entrypoints, 12 loopback-launcher and 32 input-boundary checks
- Android APK job: skipped and not counted as acceptance

**Source:** artifact `11134538649`, 434 source files, 4,581,958-byte source ZIP,
SHA-256 `10c121a6351346b4efb749778dada8f57f74c835e82241a85dca2eafc7769981`.
Two hosted builds were byte-identical; recovery used a new directory. Models,
private assets and pinned external submodule sources are excluded. The archive
is source-only and not offline dependency-complete.

**Limits:** synthetic model/audio generation; no live teaching-quality, actual
APK/JNI/Windows/device, Book signing/adoption, microphone or audible-playback
acceptance. No physical exactly-once speech or forced termination of arbitrary
callbacks is established. Memory serialization is per instance. Native request
body deadlines do not cover total header receipt.

Earlier zero-runner results below remain valid observations of their earlier
commits/runs. They are not the current status of this separate draft stack.

---

## E021 — fixed LLM quality samples + sherpa native loopback code-ready (2026-09-30)

**Implementation checkpoint:** `9920d53800ad1aec741630300283d385825fd986`

### Added evidence paths
- fixed 5-case Chinese LLM sample suite per pinned candidate;
- strict execution gate (5/5 cases, no runtime error, non-empty visible reply);
- no automatic quality score/rank/winner;
- side-by-side `llm-quality-comparison.md`;
- coupled system/user-turn character budget (7200 combined, 5200 hard turn max);
- sherpa core-file fingerprint verify-on-restore;
- in-memory Melo TTS -> 16 kHz resample -> streaming ASR native loopback;
- final collector cross-checks loopback PASS JSON and audio non-persistence.

### Not accepted yet
No current-head Android artifact or device gate has executed. Hosted jobs still fail before checkout/runner allocation (runner_id=0, zero steps). The loopback gate, GGUF matrix and qualitative outputs are **code-ready, not PASS**.

Physical-device gates still required:
- exact-head Windows build;
- Xiaomi 14 local GGUF inference/benchmark;
- live microphone ASR;
- audible TTS playback;
- 3714430278/PiP visual continuity;
- human comparison of the three candidate outputs;
- real Jvust/Book AAR adoption/signing.

---

## E021 — verified private-skin build injection checkpoint (2026-09-30)

**Exact head:** `90e5a8dc2528951fa664412a8ae66ec45a018e01`

**Drive source verified**
- file id `1B6AL3_3ymbOPSowiX-tGK-2QRXL_7Ozt`
- 12,342,220 bytes
- SHA-256 `eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f`
- exact match to `SpinePackageLayout.EXPECTED_ARCHIVE_SHA256`.

**Implemented**
- no skin binary added to Git;
- optional Windows private build-input discovery;
- stale generated asset removed before each build;
- exact input size/SHA gate;
- optional generated APK asset;
- post-build APK entry SHA gate;
- first-run bundled skin auto-install through production package validation;
- manual SAF fallback remains;
- bundled Windows path automatically invokes PiP acceptance;
- one evidence directory carries build + later device evidence.

**Not accepted yet**
No exact-head Windows build or Xiaomi 14 run has executed. Hosted Actions remain a runner-allocation blocker and provide no code result.

---

## E021 — Companion V2 pre-device hardening checkpoint (2026-09-30)

**Exact head:** `4efd70b716ab35f94af7556ee7ed5149e77d60a9`  
**Status:** CODE_HARDENED / EXACT_HEAD_NOT_EXECUTED / XIAOMI14_PENDING

### New hardening
- 5600-character deterministic pre-JNI prompt budget;
- current user message never silently truncated by MyGPT;
- Book/memory/history priority and bounded JSON/data rendering;
- content-free prompt-budget evidence report;
- ASR/TTS core-file SHA-256 fingerprint generation + restore verification;
- one-time fingerprint migration for older app-private model installs;
- large sherpa restore hashes moved off main thread;
- signed Book/supervision TTL ticker while foreground/PiP;
- microphone stopped before PiP entry;
- interrupted llama generation marks native session dirty and reloads before reuse.

### Exact-head remote evidence
- run 36667831029: Companion V2, runner_id=0, 0 steps.
- run 36667831060: sherpa voice, runner_id=0, 0 steps.
- run 36667831014: Android boundary, both jobs runner_id=0, 0 steps.

No checkout/compiler/Gradle/test code executed.

### Independent execution attempt
A direct exact-commit clone was attempted in the isolated execution environment but failed at DNS resolution for github.com. No local test result is claimed.

### Still required
Windows exact-head build, APK/AAR generation, same-signature SDK gates, PiP gate, GGUF benchmark, ASR/TTS model restore verification, prompt-budget report, memory/chat behavior and Xiaomi 14 thermal/reopen evidence.

---

## E020 — reusable Book producer SDK checkpoint (2026-09-30)

**Exact head:** `2e687fd348edfe1e787cb6634f272df69c05e0cf`

**Implemented**
- `android_llm_spike/book-client-sdk` Android library, minSdk 21 / Java 8.
- `BookCompanionSession`: context/study sequence and epoch state.
- `BookContextPayload`: sender-side contract validation.
- `BookCompanionClient`: context/clear/study/revoke ordered broadcasts.
- synthetic device sender now exercises the SDK.
- Windows acceptance builds and hashes the SDK AAR.

**Important semantic guarantee**
A reserved sequence is committed only when the protected Companion receiver returns `Activity.RESULT_OK`. Rejected delivery keeps the previous sequence so a retry can use the same expected next value.

**Not accepted yet**
- hosted exact-head compilation: blocked before runner allocation;
- Windows exact-head build: not run;
- Xiaomi 14 Book SDK positive/negative gate: not run;
- Jvust/Book AAR adoption: not performed;
- real Book/Companion signing identity: not verified.

This closes the code-design gap for the producer but not the real-app/device gate.

---

## E019 — shared persona + supervision agency automation (2026-09-30)

**Status:** CODE_READY / DEVICE_GATE_AUTOMATED / DEVICE_NOT_RUN

**Exact head:** `907208ac0db090635fcf1fc342223ad51f97fdaa`

### Added
- single shared Character Card for Python + Android;
- Android card schema/card/skin validation;
- deterministic, non-LLM supervision messages;
- lower-authority STUDY_SUPERVISION_STATE_JSON on later chats;
- ADB same-signature study lifecycle sender;
- physical local-button opt-in automation;
- persisted supervision PASS marker for evidence collection.

### Core agency assertion
For the same signed PRACTICE_REPEATED_ERROR event:
- before MyGPT-local user opt-in => QUIET;
- after the device test physically taps MyGPT's local supervision button => GENTLE_CHECK_IN.

Book cannot set the opt-in flag.

### Validation limit
This is code + automated gate preparation. The current head has not built/run on Xiaomi 14 yet. Hosted Actions still execute zero steps.

---

## E018 — PiP + signed Book quiet-supervision device gate (2026-09-30)

**Status:** CODE_READY / AUTOMATED_LOCAL_GATE_READY / REMOTE_RUNNER_UNAVAILABLE / DEVICE_NOT_RUN

**Exact head:** `4d26563d8c03453f27c9a31186a484004d6d1535`

### New executable acceptance surfaces
- PiP character mode with no overlay permission.
- signature-protected live Book context updates.
- signature-protected explicit study events.
- user-local per-session supervision opt-in.
- 10-minute repeated-error gentle-check cooldown.
- same-signature synthetic sender actions for study lifecycle.
- Windows supervision script that checks:
  1. adb-shell study event is not accepted;
  2. SESSION_STARTED => QUIET, opt-in false;
  3. repeated error before local opt-in => QUIET;
  4. ADB UI automation taps the MyGPT-local supervision button;
  5. repeated error after opt-in => GENTLE_CHECK_IN;
  6. HELP => NEEDS_INPUT;
  7. PAUSE => PAUSED;
  8. RESUME => QUIET;
  9. END => QUIET and opt-in false.

### Remote evidence
Current exact-head hosted jobs never executed repository code:
- 36665189835: Companion V2, runner_id=0, 0 steps.
- 36665189915: Android boundary, both jobs runner_id=0, 0 steps.
- 36665189892: sherpa voice, runner_id=0, 0 steps.

### Still required
Run the Windows exact-head/device path, then collect Xiaomi 14 evidence for PiP, 3714430278, GGUF load/benchmark/chat, ASR/TTS, memory, Book context and supervision.

---

## E017 — Companion V2 signed Book/local-device acceptance path (2026-09-30)

**Status:** CODE_READY_FOR_LOCAL_BUILD / REMOTE_RUNNER_UNAVAILABLE / DEVICE_NOT_RUN

**Exact head:** `5b932e6f1bbe1ca7db645802475d50b322c32ec4`

### Added evidence mechanisms
- signature-protected Book receiver + pure-Java mailbox contract;
- same-build debug Book sender to exercise Android signature permission;
- fresh/unavailable Book state marker on every llama user turn;
- bounded recent visible conversation persistence, separated from explicit long-term memory;
- llama process-singleton lifecycle hardening;
- on-device llama benchmark with local PSS/heap/thermal report;
- pinned Gradle 8.14.3 wrapper;
- Windows exact-head build/install/signature-check script;
- post-run ADB evidence collector.

### Current remote status
Representative exact-head jobs still never received a runner:
- run 36662638935: Companion V2, runner_id=0, 0 steps;
- run 36662638952: sherpa voice, runner_id=0, 0 steps;
- run 36662638973: Android boundary jobs, runner_id=0, 0 steps.

No checkout, compiler, Gradle task or test assertion ran in those jobs.

### Acceptance still required
- local exact-head Gradle build;
- same-signature APK verification;
- Xiaomi 14 install/reopen;
- positive synthetic Book delivery and negative shell/non-signature probe;
- 3714430278 rendering/reactions;
- GGUF load/chat/benchmark/thermal behavior;
- streaming ASR and optional TTS;
- memory/history/forget and recent-chat reset;
- final ADB/log/screenshot evidence package.

---

## E016 — Companion V2 all-local stack exact-head checkpoint (2026-09-30)

**Status:** CODE_INTEGRATED / EXACT_HEAD_REMOTE_EXECUTION_BLOCKED / DEVICE_PENDING

**Exact head:** `a83680c1810242d541941b6c2b1a361c8d00bf71`

### Integrated code paths
- `third_party/llama.cpp/upstream` -> pinned full source -> isolated Android JNI bridge -> GGUF local chat.
- `third_party/sherpa-onnx/upstream` + runtime v1.13.8 -> streaming microphone ASR + Melo local TTS.
- explicit Android SQLite memory with relevant recall, update, history and purge.
- AIRI ACT emotion marker -> renderer-neutral emotion -> conservative 3714430278 Spine action.
- model packages imported through SAF into app-private storage; ZIP/TAR.BZ2/TAR.GZ supported.
- no network permission is required by the Companion V2 manifest; no system-overlay or broad-storage permission is added.

### Existing accepted/local evidence
- initial AIRI Python focused candidate: 18 passed / 0 failed (earlier scope).
- independent Java-8 smokes previously passed for PCM normalization, AIRI emotion/skin mapping and serialized local-LLM lifecycle.

### Exact-head CI evidence
- llama.cpp Android run `36659174083`: runner_id=0, 0 steps.
- sherpa voice run `36659174123`: runner_id=0, 0 steps.
- Android boundary run `36659174091`: both jobs runner_id=0, 0 steps.

These red runs are infrastructure/provisioning failures before checkout or compilation. They provide **no exact-head code test result**.

### Not yet accepted
- Companion V2 APK build.
- Voice Spike APK build.
- llama JNI bridge AAR build at current head.
- real GGUF inference on Xiaomi 14.
- real microphone ASR on Xiaomi 14.
- real Melo TTS playback on Xiaomi 14.
- combined voice -> LLM -> emotion -> Spine device path.
- authenticated real Book Android semantic context.

---

## E015 — PR #15 expanded companion runtime partial validation (2026-09-29)

**Status:** PARTIAL_LOCAL_VALIDATION / GITHUB_RUNNER_INFRA_BLOCKED / DEVICE_AND_LIVE_MODEL_PENDING

**Exact head:** `741c70b2b8102b4f8a5f3eeb0fe7a73442675dd5`

### Implemented since E014
- ephemeral Book semantic chat context, lower-authority and non-persistent;
- approved AIRI-derived Character Card contract + `3714430278` MyGPT persona;
- Mem0-style memory update/delete/history audit lifecycle;
- sherpa-derived Android PCM capture foundation;
- AIRI emotion wire protocol and conservative 3714430278 mapping.

### Evidence
- earlier initial Python candidate remained 18/18 in its isolated local suite;
- independent local Java-8 smoke compiled with `javac --release 8` and executed successfully for PCM normalization, emotion wire parsing and conservative skin mapping;
- GitHub Brain run `36594289643`: job had `runner_id=0`, 0 steps;
- GitHub Android run `36594581646`: both jobs had `runner_id=0`, 0 steps.

### Interpretation
Those GitHub failures occurred before a runner executed any repository code and are classified as infrastructure/provisioning failures, not code-test failures. The newer exact-head Python suite has not yet executed remotely. Live Ollama inference, Android microphone capture, chat-to-Spine device behavior and Xiaomi 14 acceptance are still pending.

---

## E014 — AIRI-derived local companion chat/memory candidate (2026-09-29)

**Status:** LOCAL_TEST_PASS / REMOTE_RUNNER_INFRA_BLOCKED / LIVE_MODEL_NOT_RUN

**Source:** draft PR #15 on `feat/airi-chat-memory-brain-20260929`; implementation commit `226c477ddb2ea07bd1646361896320007d28f2a2`, hardening/CI commit `6438752db7a2c67b14f632f871739e7a3266edca`.

### Evidence
- isolated candidate suite: **18 passed / 0 failed**;
- tests cover explicit authority boundaries, AIRI-style merge/dedupe, bounded history, Chinese memory retrieval, persistence across process restart, idempotent request replay, multi-session system-ID isolation, persistence failure rollback behavior, and loopback-only Ollama request projection;
- AIRI source pinned to `b40e3e87b149ea5fb75d4944440493829e601411`, MIT license reproduced in-repo;
- GitHub Actions run `36590899728` attempts 1 and 2 both ended before step 1 with `runner_id=0`, so no remote test assertion executed.

### Limits
This does not prove a real Ollama model response, Android embedding, Book-to-chat context injection, voice, or Xiaomi 14 behavior. Long-term memories are explicit local records; no automatic transcript-to-memory policy is accepted here. Remote CI remains unverified until GitHub allocates a runner and executes the suite.

---

## E013 — Spine 4.1 renderer exact-head CI pass (2026-09-29)

**Status:** ACCEPTED_EXACT_HEAD_CI / DEVICE_PENDING

**Source:** Draft PR #10, `a076be06e2e4c3eeecdab3f1860143771bfef0d3` on `feat/android-companion-boundary-20260928`.

### Evidence

- Workflow run [36449517394](https://github.com/Jvust/mygpt/actions/runs/36449517394) completed with conclusion `success`.
- `java8-boundary` job `109020458878`: Java 8 compile and `SpinePackageLayoutSmoke`/coordinator smoke passed.
- `android-debug-host` job `109020458429`: hosted Android SDK check, `:app:assembleDebug`, and native payload check passed.
- Artifact `10983131261`, `mygpt-spine-3714430278-android-spike`: 1,256,529 bytes; SHA-256 `1de222d0ef784a4fd5ab32970f5deb9772fcf12074a3fe2a2bc0108e7f896411`; expires 2026-10-01.
- The exact-head source path remains `3714430278.zip -> SAF URI grant -> bounded/validated extraction -> SpinePackageLayout -> SpineSkinApplication -> SpineCharacterRuntime -> CompanionCoordinator cue`.

### Interpretation

This is the first accepted exact-head CI evidence for the real Spine renderer implementation. It confirms the package-validation contract, Java 8 boundary, Android APK assembly and native payload presence. It does not prove a physical Android render or real Book producer.

### Limits and next gate

No Xiaomi 14 installation, SAF import, first-frame check, cue-transition check or background-reopen check has been performed. Book events remain synthetic; paid provider calls remain zero; the Spine Runtime license gate still blocks any production/public redistribution claim. Next gate is a user-device validation record, followed by the genuine trusted Book Android study-event producer.

---

## E012 — Current GitHub and Drive handoff alignment

Synchronized the current state and handoff to include the CI-passing synthetic Android lifecycle host, APK, changed-files review bundle, complete 131-file source snapshot, latest Drive IDs and checksums. The source snapshot is explicitly tied to source commit `bf996e6e64c3f4d078102d337be31480dedf2f88`; GitHub branch head subsequently advances through documentation-only synchronization commits. The Drive sync receipt receives a top addendum superseding the earlier no-APK statement. Earlier APK and source archives remain historical; no PR merge or main update.

---

## E010 — Drive and Library delivery sync

The lifecycle source changes are in GitHub branch `feat/android-companion-boundary-20260928` at `986b7b39cf0eda54e74e096f701d4b132c5bbdd9`; Draft PR #10 remains open and unmerged. Current Android debug APK Drive ID `1dyBqjFz9IIc0_IXY1_YGtKTpvIdKm3BG`, 14,913 bytes, SHA-256 `78e174567100487746a4d37330ed9caafed5da0ddb414752d3d172781345c5ed`. Changed-files review bundle Drive ID `16ROvan1oWIe_vST8ZWxRfdVJEUcnChNq`, 21,323 bytes, SHA-256 `c9533e98ec3ee691b6202e1efd4d57090550027cfd2825f9320619679be8192a`; it is not a complete source snapshot. Prior APKs and the September 27 source snapshot remain preserved as historical artifacts. The Google Drive sync receipt has an addendum that supersedes its earlier “no APK/test artifact” status. No main-branch change or PR merge was performed.

---

## E009 — Synthetic host lifecycle and expiry (2026-09-28)

Source: `feat/android-companion-boundary-20260928@eef4d8e1eba7b1ac09c68b3a8eac48874a5c814b`, Draft PR #10. The pure Java coordinator now clears session-scoped supervision consent at revocation, end, expiry and a new session; a deadline check clears a visible cue without waiting for another event. The Android Activity clears its synthetic session on `onStop` and schedules expiry for the last accepted event. Push run [`36369308484`](https://github.com/Jvust/mygpt/actions/runs/36369308484) and PR run [`36369310978`](https://github.com/Jvust/mygpt/actions/runs/36369310978) succeeded; PR jobs `108762033636` (Java 8 smoke including revocation/expiry and consent reset) and `108762033792` (`:app:assembleDebug`) succeeded. Artifact `10948049229` ZIP digest SHA-256 `464ba406dc5704042473bc11e4932a984eeed09554b2dd1655aa2b80a588c5ea`, downloaded ZIP CRC passed. Extracted APK 14,913 bytes, SHA-256 `78e174567100487746a4d37330ed9caafed5da0ddb414752d3d172781345c5ed`, APK ZIP CRC passed; Drive file `1dyBqjFz9IIc0_IXY1_YGtKTpvIdKm3BG` metadata read-back matches name, size and folder. CI compiles Activity but does not exercise physical-device lifecycle, screen lock, timing, or UI behavior; those remain pending. No real Book Android producer, Live renderer, model or voice is connected.

---

## E008 — Synthetic Android debug host CI (2026-09-28)

Source: `feat/android-companion-boundary-20260928@332e9a29578428b56048ac3851ee29cb74dc3492`, Draft PR #10. Initial push run `36368130257` failed before build in `android-actions/setup-android@v3` while requesting the removed SDK `tools` package; Java 8 smoke passed. The workflow changed to the hosted runner's preinstalled Android SDK. Push run [`36368235878`](https://github.com/Jvust/mygpt/actions/runs/36368235878) then passed both Java 8 boundary smoke (job `108758839963`) and Android `:app:assembleDebug` (job `108758840189`). GitHub artifact `10947829161` ZIP SHA-256 `6e6f490df0ce0b6e166123446b95a9dafb954c74f80f258cb00a2cce95bff98f`; downloaded ZIP CRC passed. Extracted APK 14,033 bytes, SHA-256 `2a80adbb5bab0187f2b42eba22a044f79552eb13336468cef9b176b9b2bced78`; Drive file `1HXRW8XBmHyG0lJtfP6FX3KvZ-SOCM8rY` metadata read-back confirms APK name, size and artifact parent. The host uses explicit synthetic Book event buttons, a test-double authority, and a text cue placeholder. This is build verification, not installation or lifecycle validation on a physical device; genuine Book Android events, Live-owned renderer, model, voice and production permissions are pending.

---

## E007 — Android companion boundary spike (2026-09-28)

Source: `feat/android-companion-boundary-20260928@8e8c93b11cef54cefa133abfda7ffe4df0bd0685`, Draft PR #10. GitHub push run 36367251552 and PR run 36367267599 succeeded. PR job 108756041802 compiled with `javac --release 8` and ran `CompanionCoordinatorSmoke` successfully. Local javac was unavailable. The checks cover quiet default, explicit supervision opt-in/out, prompt, replay/gap, expiry, rejected Book authority, pause/resume, epoch identity, opaque source reference and session end. This verifies a synthetic JVM boundary only, not an Android APK, Book producer, Live renderer, model teaching, permission flow or physical device. No upstream source/assets or paid provider were used.

---

# Evaluation Ledger

## E001 — Foundation architecture review

Date: 2026-09-21
Status: DESIGN_ACCEPTED_FOR_V0_1_PLANNING

### Question
Can mygpt provide useful real-time study companionship without continuous screen recognition?

### Current conclusion
Yes, for Book-centered learning the preferred route is structured semantic context from Book, augmented by low-cost Android/app activity signals. Screen vision should be a fallback rather than the default.

### Evidence available
- Book already exposes structured learning concepts such as course/chapter/section, learning modes, route/session state, and durable StudyRecord-related behavior in its current project.
- StudyMate already establishes a pattern of Android-side session/activity observation and companion behavior.
- ChatContextVault demonstrates a privacy-gated retrieval model for relationship history and a clear separation between stored evidence and interpretation.
- External mobile-agent research confirms that Android UI/accessibility/screen-perception stacks exist, so vision fallback is technically plausible; detailed adoption decisions remain future work.

### Not yet proven
- Latency and UX of a production Book→mygpt event bridge.
- Intervention quality over a real 30-minute study session.
- Battery impact of optional Android sensors.
- Cost of cloud reasoning at realistic usage.
- Reliability of screen-vision fallback for PDFs, math formulas, and external apps.

### Next evaluation
Prototype the semantic event contract and run a real study-session simulation before implementing broad screen capture.

## E002 — Jonah companion component candidate

Date: 2026-09-22
Status: IMPLEMENTED_TESTS_PASS_REVIEW_PENDING

### Question
Can the existing Jonah character become a low-cost, controllable companion surface in mygpt before the final host stack is selected?

### Result
Yes, at the reusable UI-component level. The candidate uses one local sprite atlas, native browser APIs, and no runtime dependency or external network request. It supports touch and keyboard input, preserves the user's chosen location/visibility when storage is available, handles unavailable storage, and stops animation work when hidden, backgrounded, disconnected, paused, or reduced motion is requested.

### Evidence
- `npm test`: 3/3 deterministic atlas/mapping checks passed.
- `npm run test:browser`: 45/45 Chromium interaction checks passed at the implementation checkpoint.
- Verified behaviors include real emulated touch events, drag/tap separation, reload persistence, five host states, all sixteen look directions, narrow/landscape/desktop fitting, reduced motion, disconnect cleanup, storage-denied fallback, zero runtime exceptions, and zero external requests.
- Mobile and desktop screenshots received visual inspection.

### Limits
- Headless Chromium is not Android physical-device validation.
- Test screenshots showed missing CJK font glyphs in the Linux browser runtime; no layout failure was observed.
- The demo chat panel is an event-wiring proof, not a production model connection.
- Cross-app Android overlay, native app lifecycle, soft keyboard, Book semantics, and notification behavior remain unproven.

### Next evaluation
Select the production host, integrate the component with explicit mygpt/Book state, then test on Xiaomi 14 through the Android Studio workflow. Evaluate a system overlay only as a separate optional feature.

## E003 — Input recovery and isolated browser validation

Date: 2026-09-22
Status: LOCAL_VALIDATED_PENDING_PREFLIGHT_CONFIRMATION
Base: `feat/jonah-companion-20260922` at `64e73b257a79ec09787e2a96a43816b5864f9a1c`
Proposed branch: `fix/companion-input-and-test-isolation-20260922`

### Reproduced defects

1. Opening the panel with Enter left focus on the avatar even though the panel precedes it in tab order. The first action was not the next keyboard target.
2. An unrelated `pointerup`, `pointercancel`, or `lostpointercapture` event ended the active drag because the end handler did not check pointer identity.
3. A cancelled touch did not emit a click, leaving drag-click suppression armed. A later Enter activation was swallowed.
4. The browser suite used a fixed port and could connect to another preview. Chromium launch occurred before the cleanup block, so launch failure could leave the child server running.

### Change and evidence

- Move focus into an opened action panel and restore avatar focus on close; keep normal host chat event handling.
- End only the matching active pointer; ignore additional pointer-down attempts during a drag; preserve keyboard clicks after cancellation.
- Start one test-owned server with `PORT=0`, read its actual listening address, and clean up startup/launch failures.
- Baseline recovery verified all 26 Git blob identities against the exact upstream tree, including the unchanged sprite PNG.
- Before the component changes, an independent Chromium reproduction returned false for all three input checks; after the changes, all three returned true.
- `npm test`: 3/3 pass. `npm run test:browser`: 49/49 pass, including the original 45 checks plus keyboard focus, Escape recovery, pointer identity, and cancelled-touch keyboard recovery.
- With an unrelated HTTP 500 server deliberately occupying port 4173, the updated browser suite still passed all 49 checks on its own port.
- With an invalid Chromium executable path, the suite exited with code 1 in under one second instead of hanging on a leftover server.
- Runtime errors: 0. External browser requests: 0. Runtime dependencies and sprite bytes unchanged.

### Scope and limits

This is a locally validated review candidate, not a published or merged change. No GitHub or Drive mutation was performed by this audit. The remote publication preflight must verify the base head again, use the proposed new branch, and preserve existing PRs. Physical Android hardware, native overlay, soft keyboard, production Book/chat integration, and independent human review remain unverified.


## E004 — explicit local selection intake
Date: 2026-09-24
Status: ACCEPTED_SYNTHETIC_LOCAL_INPUT / REVIEW_PENDING

### Question
Can a user explicitly bring one local text selection into the existing loopback Brain without pretending it is Book data or creating an implicit provider call?

### Result
Yes for the bounded local-input contract. Exact head `318c3ef0874b6903320d7ccfa0ce63d33f862bd0` passed two clean locked Python environments at 426/0/0 each, 32 loopback HTTP checks, 66 Node tests, and browser suites including 30 explicit-selection checks. The UI requires preview/consent; import alone does not explain; provenance remains `USER_SUPPLIED_UNVERIFIED`; reload/revoke/cancel/expiry paths fail closed.

### Limits
This does not authenticate Book, validate mathematical truth, activate a real model, support arbitrary documents, or prove Windows/Android behavior. Independent review remains pending.

## E005 — deterministic source delivery and clean recovery
Date: 2026-09-25
Status: ACCEPTED_LINUX_CLEAN_RECOVERY / WINDOWS_ANDROID_PENDING

### Question
Can a fresh environment recover one exact PR #6 source state without relying on a dirty workspace, old incremental ZIP order, or hidden credentials?

### Result
Yes on the accepted Linux CI environment. Exact head `65c8d6b0493432c16d83174aeff22b415583a703`, run `36019467569`, passed 26 delivery unit tests; produced byte-identical source bundles from the immutable commit; verified 97 tracked source files; restored into a fresh directory; installed the existing hash lock; reported doctor READY; passed actual launcher start/status/Ctrl+C shutdown 12/12; and reran Brain 426/0/0 plus selection HTTP 32/32.

The exact source ZIP is 2,246,013 bytes with SHA-256 `eb9404fbfd9a4d9fc22db57c0518ecb65510a192b7500277885f2747219bb6df`. The long-term Drive evidence/archive is indexed in the artifact manifest.

### Limits
The internal source manifest is not a signature; authenticity depends on the separately recorded outer SHA-256 and trusted Git/Drive provenance. Windows launcher, Android packaging/device behavior and independent review are not accepted by this evaluation.


## E006 — combined local-intake + Book lease receiver compatibility
Date: 2026-09-25
Status: ACCEPTED_COMBINED_CI / INDEPENDENT_REVIEW_PENDING

### Question
Can the current PR #6 local-selection/lifecycle/source-delivery code coexist with the additive PR #7 Book lease receiver without restoring stale project-state files?

### Result
Yes on the exact integration head `e9e5fb0932c1830fa11e886beb2802191eea09c8`. Four workflows all passed: Brain SDK two clean environments at 446/0/0 each; Book receiver 20/20 cases with the same 446/0/0 suite; UI regressions at Node 66 plus Jonah 49/replay 39/Python host 23/selection host 30; and complete-source recovery with 103 tracked files, recovered Brain 446/0/0, launcher 12/12 and selection HTTP 32/32.

The integration was capability-selective: PR #7's replacement-style project_state/CURRENT_STATE/HANDOFF changes were not copied.

### Limits
This validates code compatibility and recovery on the tested Linux/browser environments. It does not authenticate the user's installed Book APK, prove the Book-side authority transport on a physical device, validate live model teaching quality, or satisfy independent review/merge gates.
