## 2026-09-30 · scikit-learn recall closes the long-question gap

The existing companion memory search now directly uses a bounded scikit-learn
TF-IDF/cosine port. Valid 600–4000-character questions reach the model unchanged;
namespace-scoped candidates are ranked by lexical evidence rather than recency
alone. Strict Brain passes 643/0/0 on Python 3.12/3.13, and nine real upstream
oracle tests pass. See [source, behavior and limits](LEXICAL_MEMORY_FUSION_20260930.md).

---

## 2026-09-30 · native HTTP authorization owns in-flight requests

The actual native API now applies Pipecat-derived owned-request cancellation to
revoke/expiry. A shared authorization completion guard serializes synchronous
commit and success-response admission against revoke, closing the late-response
and cross-thread check/write gaps. Strict Brain passes 623/0/0 on Python 3.12/3.13.
See [admission semantics and evidence](NATIVE_HTTP_REVOKE_FUSION_20260930.md).

---

## 2026-09-30 · Pipecat task ownership completes wake/ASR path

The existing wake/ASR entry now directly uses Pipecat-derived cancellation
ownership and always-enforced generation guards. New qualified utterances
supersede old ASR/model work; close joins retiring tasks; external cancellation
and failure recovery preserve correct state. Strict Brain acceptance passes
612/0/0 on Python 3.12/3.13. See [scope and reproduction](WAKE_TURN_FUSION_20260930.md).

---

## 2026-09-30 · official Ollama async HTTP runtime fusion candidate

The existing Ollama responder now directly uses the official async lifecycle
instead of a blocking worker-thread request. Actual Pipecat interruption closes
the local HTTP connection, with no stale speech or history. Strict Brain tests
pass 595/0/0 on Python 3.12 and in two clean Python 3.13 environments; real
Pipecat tests pass 8/8. The fixed loopback destination and no-credential boundary
are preserved. See [source, tests and limits](OLLAMA_ASYNC_FUSION_20260930.md).

---

## 2026-09-30 · Pipecat speech lifecycle fusion review candidate

The existing Pipecat processor now directly incorporates upstream response
start/end framing, flushing short text through real Pipecat TTS aggregation.
Interruption/cancel invalidates the companion turn before queue cancellation,
preventing late speech and SQLite commits. Full strict Brain acceptance is
574 passed / 0 skipped; seven real Pipecat 1.12.0 integration tests pass locally.
See [scope, attribution and reproduction](PIPECAT_RUNTIME_FUSION_20260930.md).
This stacks on AIRI runtime PR #31 and does not claim device/audio acceptance.

---

## 2026-09-30 · AIRI ACT Python runtime fusion review candidate

The existing Python/Ollama reply path now directly calls the pinned MIT AIRI ACT
emotion parser before persistence and native HTTP/Pipecat output. Visible speech
and renderer-neutral emotion remain separate. Local strict Brain acceptance is
563 passed / 0 skipped; root Python 44 and JS 66 also pass. This is a separate
review branch on PR #15's current code, not Android/device completion. See
[exact scope and reproduction](AIRI_ACT_RUNTIME_FUSION_20260930.md).

---

## 2026-09-30 · LLM quality matrix + sherpa native loopback checkpoint · PR #15

Implementation checkpoint: `9920d53800ad1aec741630300283d385825fd986` (this governance-only commit follows it).

The Xiaomi 14 gate now covers more than file/import checks:

- **LLM matrix:** speed / balanced / quality fixed GGUF identities run the same local benchmark.
- **Fixed Chinese qualitative suite:** every candidate runs the same five synthetic companion/Book/authority cases with the exact production Character Card, shared system prompt, and prompt budget. A candidate gate requires all 5 cases to execute and return visible text, but **no automatic score/rank/winner is produced**.
- **Human comparison:** `run_llm_matrix.ps1` writes `llm-quality-comparison.md`, grouping the three candidates side-by-side by case with wall time, AIRI emotion and visible reply.
- **Prompt budget:** current hard user-turn ceiling is **5200 chars**, not the older 5600 value. The production shared system prompt is coupled through a conservative 7200-character combined guard; current 3714430278 system prompt measured 1506 chars, so the turn stays capped at 5200. This is a character guard, not a tokenizer claim.
- **Sherpa integrity:** imported core ASR/TTS files are fingerprinted and re-verified on restore; large hashing runs off the UI thread.
- **Native voice execution:** when both fixed sherpa packages are present, a debug-only gate synthesizes `你好，今天一起学习。` through production Melo config, keeps PCM in memory, resamples to 16 kHz, feeds the production streaming ASR, and requires a non-empty transcript. No microphone/speaker/audio file is used by this gate.

Latest hosted runs `36681413185`, `36681413136`, and `36681413222` again have runner_id=0 and zero executed steps. They remain infrastructure failures and provide no code result.

The remaining decisive gate is the Windows/Xiaomi 14 path. Real microphone input, audible TTS, visual Spine/PiP behavior and final model choice remain physical-device decisions.

---

## 2026-09-30 · verified 3714430278 self-contained local build path · PR #15

Exact head: `90e5a8dc2528951fa664412a8ae66ec45a018e01`.

The primary skin no longer has to be manually selected on a Windows/Xiaomi 14 acceptance build.

The authenticated Drive source was verified as:
- Drive file id: `1B6AL3_3ymbOPSowiX-tGK-2QRXL_7Ozt`
- hierarchy: `My Drive/Live/skin/workshop/3714430278/3714430278.zip`
- bytes: `12342220`
- SHA-256: `eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f`

The ZIP is **not committed to Git**. The Windows build optionally discovers it from an explicit `-SkinZip`, `MYGPT_SKIN_ZIP`, or allowlisted Google Drive Desktop paths. It is copied only into the module build directory after exact size+SHA verification. The built APK is then reopened and `assets/3714430278.zip` is independently SHA-verified again.

At runtime Companion V2 validates any already-installed app-private 3714430278 first; otherwise it attempts to install the bundled asset through the same production `SpinePackageLayout.install()` gates. An unbundled build retains the manual SAF picker.

When a verified skin is bundled, the Windows acceptance route automatically runs the PiP-over-Book gate. Final evidence now stays in the same build evidence directory.

Remaining large external inputs are the chat GGUF and sherpa ASR/optional TTS. Drive search found image-oriented Qwen-Image GGUF but no accepted conversational default, and no matching sherpa model packages; these remain benchmark/import gates rather than guessed defaults.

---

## 2026-09-30 · pre-device hardening checkpoint · PR #15

Exact head: `4efd70b716ab35f94af7556ee7ed5149e77d60a9`.

The code path is now hardened specifically for long-running Xiaomi 14 use before the first exact-head device build:

- **Prompt budget:** `CompanionPromptBudget` caps the pre-JNI user-turn prompt at 5600 characters. It always preserves the complete current user message (<=4000 chars), then prioritizes current signed Book data, supervision state, relevant explicit memory, and finally recent conversation. Book text/memory/history are rendered in bounded data blocks; no content is written to the budget evidence report.
- **Sherpa model integrity:** ASR/TTS imports create deterministic core-file SHA-256 manifests. Restore recomputes and verifies them; legacy app-private installs without a manifest receive a one-time migration. Large hashing now runs off the Android UI thread.
- **Signed-state TTL:** a 1-second in-memory ticker runs only while Companion is foregrounded or visibly in PiP. Book expiry becomes unavailable; supervision expiry clears session/opt-in and returns the character to QUIET. There is no network polling, service, wake lock or screen inspection.
- **PiP privacy:** entering PiP explicitly stops microphone capture.
- **Interrupted llama recovery:** cancellation/native generation failure is treated as potentially inconsistent KV state. The interrupted exchange is not persisted; the local model is reloaded and only completed visible conversation is re-primed.

Validation remains deliberately unresolved at this head. Latest hosted runs `36667831029`, `36667831060`, and `36667831014` all have `runner_id=0` and 0 executed steps. They are infrastructure failures, not code results. Independent execution also could not clone GitHub because the execution environment DNS could not resolve github.com.

Next real gate: exact-head Windows build + Xiaomi 14 evidence. PR #15 remains Draft and main remains untouched.

---

## 2026-09-30 · Book client SDK producer gap closed in mygpt · PR #15

Exact head: `2e687fd348edfe1e787cb6634f272df69c05e0cf`.

The real Book repository is still untouched, but the **producer implementation is no longer missing**. PR #15 now contains `android_llm_spike/book-client-sdk`, an Android library that builds `book-client-sdk-release.aar`.

The SDK provides:
- receiver-compatible context validation;
- explicit-package ordered delivery;
- context clear;
- study start/context-change/pause/resume/end/help/repeated-error/revoke;
- independent context/study sequence state;
- study epoch state;
- sequence/epoch commit **only after Companion returns `Activity.RESULT_OK`**;
- rejected deliveries do not advance the local sequence and therefore do not create a permanent receiver gap;
- a merged `uses-permission` request for the Companion signature permission.

The same-signature synthetic Book sender now calls this SDK for automated context and supervision acceptance; it no longer hand-builds those protected Companion broadcasts. The Windows build route also builds the SDK AAR and records its SHA-256 in the evidence directory.

Boundary unchanged: this does **not** mean the real Book APK is connected. Jvust/Book must still adopt the AAR and be signed with a certificate accepted by Companion V2. Xiaomi 14 execution remains pending. Exact-head hosted runs still show runner_id=0 / zero executed steps and therefore provide no code result.

---

## 2026-09-30 · shared persona + deterministic supervision presentation · PR #15

Exact head: `907208ac0db090635fcf1fc342223ad51f97fdaa`.

Additional hardening after the PiP/supervision checkpoint:

- Python Brain and Android Companion V2 now consume the **same authoritative** `brain/personas/3714430278.json` AIRI-style Character Card. Android validates the bundled asset and derives identity/personality/scenario/consistency/examples from it; only Android authority/freshness rules remain platform-local.
- Accepted signed supervision events do **not** automatically call the LLM. Companion V2 renders deterministic low-pressure local copy for QUIET/PAUSED/NEEDS_INPUT/GENTLE_CHECK_IN and sends current supervision state to later chat only as `STUDY_SUPERVISION_STATE_JSON` application data.
- The same-signature test sender now has automated study lifecycle actions, and the Xiaomi 14 supervision script verifies user agency: repeated error is QUIET before local opt-in and GENTLE_CHECK_IN only after ADB physically taps the MyGPT-local supervision control.
- Device automation scrolls back to a stable Book status position after supervision checks; Book status and supervision controls expose ASCII accessibility markers for PowerShell/UIAutomator evidence.
- The final evidence collector records the persisted test-only supervision PASS marker in addition to permission/audio/benchmark/Book evidence.

Hosted Actions remain non-evidence at this head because jobs receive no runner and execute zero steps. PR #15 remains Draft.

---

## 2026-09-30 · Companion V2 PiP + signed Book quiet-supervision checkpoint · PR #15

Exact head: `4d26563d8c03453f27c9a31186a484004d6d1535`.

New since the prior local-device checkpoint:

- **Android native PiP companion mode**: explicit button, 1:1 render-only character surface, skin-ready gate, no auto-enter, no SYSTEM_ALERT_WINDOW/Accessibility/screen-capture requirement. This is the first cross-App 3714430278 companion surface intended to sit above Book.
- **live in-process Book updates**: the process-memory Book mailbox now notifies Companion V2 immediately when same-signature context changes/clears, including while PiP remains visible.
- **signed Book study-event receiver**: Book may explicitly send start/context/pause/resume/end/help/repeated-error/revoke events; it cannot inject source_ref/body into the supervisor.
- **quiet-first supervision**: repeated practice errors produce no prompt until the user explicitly turns on supervision inside MyGPT for the current session. Opt-in resets on end/revoke/new session; gentle prompts have a 10-minute cooldown.
- **same-signature automated study sender** plus Xiaomi 14 script: the device gate proves shell-origin study events are rejected, sender-origin events are accepted, and the same repeated-error signal stays QUIET before a real local button tap but becomes GENTLE_CHECK_IN after that tap.
- Windows acceptance now records exact source identity, requires JDK17/Android 36 native toolchain, verifies APK signing and runs automated Book context + supervision gates before manual model/voice/PiP testing.
- Final evidence collection records permission boundary, audio non-persistence, benchmark presence and supervision gate status.

Remote CI remains unavailable, not failing assertions. Exact-head runs `36665189835`, `36665189915` and `36665189892` all show `runner_id=0` and zero steps.

Real Book/Live repositories remain untouched; real Book producer integration is still pending.

---

## 2026-09-30 · Book signed bridge + durable conversation + local acceptance path · PR #15

Exact head: `5b932e6f1bbe1ca7db645802475d50b322c32ec4`.

Since the prior Companion V2 checkpoint, the candidate now also includes:

- a **signature-permission-protected Book Android context bridge**. Valid context is explicit-package only, TTL-bounded, sequence-checked, process-memory only, and is rendered as lower-authority model data. Every turn marks Book as `fresh` or `unavailable` so stale context retained in llama KV history cannot silently stay current;
- a **same-signature synthetic Book sender APK** built beside Companion V2 for physical-device validation without weakening the production receiver permission;
- a separate bounded **recent conversation SQLite store**. It contains visible user/assistant text only, primes at most 10 turns after model reload, and remains distinct from explicit Mem0-style long-term memory;
- a llama.cpp lifecycle fix for the upstream **process-wide AiChat singleton**: Activity-level close now unloads the model instead of destroying the process singleton;
- an in-app **local llama benchmark** that records model hash/bytes, wall-clock, PSS/native/Java heap and Android thermal status to app-private `benchmark-last.txt`;
- a pinned Gradle 8.14.3 wrapper plus Windows scripts for exact-head build/install, same-signature verification, Xiaomi 14 installation and post-run evidence collection.

The preferred next validation path is now local Windows + Xiaomi 14 because GitHub hosted Actions remain unavailable. Exact-head runs `36662638935`, `36662638952` and `36662638973` all terminated before step 1 with `runner_id=0` and zero steps. This remains an infrastructure failure, not a code test result.

Real Book is **not connected yet**. The synthetic sender proves only the receiver contract/signature boundary once device-tested; the real Book APK must later use the same signing certificate and producer contract.

---

## 2026-09-30 · Companion V2 全本地栈代码集成 checkpoint · PR #15

当前精确 head：`a83680c1810242d541941b6c2b1a361c8d00bf71`。PR #15 仍为 Draft，base 为 `feat/spine-3714430278-runtime-refresh-20260929`，main 未修改。

本轮已把候选从“聊天 Brain + PCM 基础”推进成同一 Android Companion V2 里的全本地链路：

```text
文字输入 ─────────────────────────────┐
麦克风 -> sherpa streaming ASR ─────┤
                                    ↓
                         显式相关长期记忆召回
                                    ↓
                         llama.cpp Android JNI / GGUF
                                    ↓
                    可见文本 + AIRI <|ACT:{...}|> 情绪
                         ↓                     ↓
                 sherpa Melo TTS         3714430278 Spine
                 （可选、默认关闭）        （保守动作映射）
```

关键实现：
- 完整 `llama.cpp` 上游以 git submodule 固定到 `ba0ba54d...`；独立 `android_llm_spike` 使用上游 JNI，而不是残缺复制。
- GGUF 通过 SAF 导入 App 私有目录；先校验 GGUF header，再做有界流式复制、SHA-256 地址化和重复检测。
- Companion V2 同一应用内同时包含 3714430278 Spine、llama JNI、sherpa JNI、显式 Android SQLite 长期记忆。
- sherpa 源码 submodule 固定 `040afe36...`；运行时二进制明确固定 `v1.13.8 / 11afbd00...`，两种身份不混写。
- ASR：用户点击语音按钮才申请 `RECORD_AUDIO`；16 kHz mono；raw audio 不落盘；识别 endpoint 后自动送入本地 LLM。
- TTS：Melo 中英模型外置导入；默认关闭；开启后将去除 ACT 标记后的可见回复直接流式写入 AudioTrack，不保存 wav。
- 模型导入支持 ZIP / TAR.BZ2 / TAR.GZ；只提取白名单文件，并保留 README/LICENSE（如归档包含）。
- Android 长期记忆采用 Mem0 风格 add/search/update/delete/history；聊天不自动进入长期记忆；`:forget` 使用 purge 同时删除活动内容与审计历史。
- AIRI ACT 情绪白名单为 happy/sad/angry/think/surprised/awkward/question/curious/neutral；3714430278 只对 smile/sad/surprise 做精确语义映射，其余回 idle。
- Companion V2 Manifest 当前仅新增 `RECORD_AUDIO`；没有 INTERNET、SYSTEM_ALERT_WINDOW 或广泛存储权限。

验证边界：
- 早期 AIRI Python 候选 18/18 本地测试通过；若干纯 Java 8 协议 smoke 曾独立 PASS。
- **当前精确 head 的 Android/llama/sherpa workflow 没有真正执行代码**：run `36659174083`、`36659174123`、`36659174091` 均为 `runner_id=0`、0 steps。
- 因此 Companion V2 APK、Voice Spike APK、llama JNI bridge 的 exact-head build 仍是 **NOT EXECUTED**，不能写成 PASS 或代码 FAIL。
- 小米 14 本地 GGUF/ASR/TTS/Spine 全链实机仍待验收；真实 Book Android producer 仍未连接。

---

## 2026-09-29 · PR #15 expanded companion runtime checkpoint

PR #15 has advanced from the initial AIRI chat/session candidate into a broader companion runtime stack.

Direct bounded upstream adoption now includes:
- **Project AIRI (MIT):** authority-aware conversation, stored/current message merge/dedupe, bounded history, Character Card fields, and renderer-neutral emotion vocabulary;
- **Mem0 (Apache-2.0):** explicit memory update/delete/history lifecycle with auditable local change records;
- **sherpa-onnx (Apache-2.0):** Android 16 kHz mono AudioRecord capture pattern and PCM16 normalization foundation.

MyGPT-specific integration added:
- ephemeral Book semantic context enters chat only as lower-authority application data and is not persisted in chat history or memory;
- skin `3714430278` now has an approved MyGPT character card with persona/scenario/greeting/example-dialogue fields;
- memory CLI supports `:remember`, `:update`, `:forget`, `:history`;
- Android voice capture does not request microphone permission automatically and does not write raw audio to disk;
- chat replies can carry AIRI-compatible `happy/sad/angry/think/surprised/awkward/question/curious/neutral` presentation emotions;
- 3714430278 only maps exact authored matches (`smile/sad/surprise`); unsupported emotions fail safe to the current form's idle.

Validation:
- initial Python companion candidate: **18/18 local tests passed** before the later Book/card/memory-history/voice/emotion expansion;
- independent local Java-8 smoke for PCM + emotion protocol: **PASS**;
- GitHub Actions remains infrastructure-blocked: representative Brain run `36594289643` and Android run `36594581646` have `runner_id=0` and zero executed steps. These are not assertion/test failures;
- exact-head full Python suite, live Ollama inference, microphone device capture and Xiaomi 14 chat/voice integration remain unaccepted.

Current exact branch head at this checkpoint: `741c70b2b8102b4f8a5f3eeb0fe7a73442675dd5`. Main remains untouched and PR #15 stays Draft.

---

## 2026-09-29 · AIRI-derived companion brain candidate · PR #15

A new stacked draft branch `feat/airi-chat-memory-brain-20260929` now sits on top of the current PR #13 skin/Android line. This is the first bounded direct AIRI code adoption for MyGPT rather than a reference-only registry entry.

Implemented:
- chat message authority separation: system/developer vs application context;
- AIRI-style durable/current merge and message dedupe;
- bounded recent conversation compaction without silently converting old raw chat into semantic memory;
- explicit SQLite long-term memory with Chinese tag/query support;
- durable SQLite sessions and request receipts, including replay across process restarts;
- loopback-only Ollama adapter at `127.0.0.1:11434/api/chat`;
- runnable `brain/scripts/chat_local_ollama.py`, where long-term memory is created only through explicit `:remember`;
- pinned AIRI MIT license and adaptation notice.

Verification:
- isolated local candidate suite: **18 passed / 0 failed**;
- GitHub Actions run `36590899728` attempted twice but both ended before step 1 with `runner_id=0` and no steps, so remote code tests are **not executed**, not failed assertions;
- no live Ollama model call has been accepted as evidence yet.

Commits: `226c477d` (implementation) + `6438752d` (persistence hardening / CI branch enablement). Draft PR: #15. Main remains untouched. The existing Xiaomi 14 multi-form skin acceptance gate remains independently pending.

---

## 2026-09-29 · 0.0.6 安装修复 + 三形态

上一份 0.0.5 自包含 APK 在 Android 真机出现“解析软件包时出现问题”。复核确认 ZIP 本体和内置皮肤没有损坏；问题来自本地重签名步骤生成了结构错误的 APK v2 signer framing。0.0.5 设备包因此降级为不可用历史证据。

当前修正版：
- `0.0.6-multiform-3714430278`
- 源码 head：`327638d084d46d565b5a833ac064810ef8d1b124`
- CI run：`36525176168`，Java8 full-package smoke / Android assembleDebug / native payload 全部 PASS
- APK：`mygpt-3714430278-v0.0.6-multiform-fixed-20260929.apk`
- APK SHA-256：`638f48511dc00a52dcde78bdc13a9d17a3fd673c3c3636eb96ff031b56b66a71`
- Drive ID：`1NoYIaXGgFdMtgxcOw9MCI84wxI07U4DR`
- 内置皮肤 SHA-256：`eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f`
- APK v2 signer 结构 / RSA 签名 / signed content digest：PASS
- ZIP 完整性：PASS
- arm64 `libgdx.so` 16K 对齐：PASS

3714430278 已从 default-only 推进到 L4 代码实现：
- 完整提取并校验 13/13 文件
- DEFAULT：`skeleton.bin + c610_00.atlas + c610_00.png`
- AIM：`misc_01.bin + misc_02.atlas + misc_04.png`
- COVER：`misc_08.bin + misc_03.atlas + misc_05.png`
- AIM → COVER：先播放 `to_cover`，完成后切换 COVER
- COVER → AIM：先播放 `to_aim`，完成后切换 AIM
- 其他无原生过渡的路径采用直接 form swap，并明确记录为 direct switch
- 一次性动作结束自动回当前形态 idle
- 页面新增 DEFAULT / AIM / COVER 和“待机 / 主要动作 / 反应动作 / 下一个动作”控制，可循环验收完整动作集合
- 音频继续完全关闭
- 已新增 `skin_inventory.json`、`skin_capabilities.json`、`skin_state_graph.json`

下一门槛是 L6：小米 14 真机安装 + 三形态首帧/动作/切换/后台恢复验收。

## 2026-09-29 · MyGPT 0.0.5 页面美化版

PR #13 已完成 Android 页面第一轮产品化美化，并通过最新 exact-head CI。

- App 名称：`MyGPT`
- 版本：`0.0.5-companion-ui-3714430278`
- 页面结构：品牌区 → 人物卡片 → 当前状态 → 学习陪伴操作 → 角色设置 → 开发说明
- 人物区域改为圆角卡片并与 Spine 背景统一。
- 学习按钮按用途重新分组，不再是测试工具式纵向按钮堆叠。
- 换皮入口降级为“角色设置”里的可选功能。
- 皮肤音频保持完全关闭。
- exact-head CI run `36523316210`：Java8 PASS、Android assembleDebug PASS、arm64 native payload PASS。
- 新自包含 APK：`mygpt-3714430278-ui-v0.0.5-20260929.apk`
- APK SHA-256：`d53c9c0e9bda17fcfaf5fe607690449154a1089c5289e2571f4702460765a34b`
- Drive ID：`1qQ7BJNmN6qh900Qo8rRfAeft6gBH9eN5`
- 内置皮肤 SHA-256：`eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f`
- 与上一版自包含 APK 使用相同签名证书，可作为覆盖升级候选。
- 当前仍待小米 14 真机视觉/交互验收。

## 2026-09-29 · 自包含 3714430278 APK

用户真机反馈上一版仍要求手动选择 ZIP，且所选文件 SHA-256 为 `578b...`，与 Live 权威包 `eb6edd...` 不一致。当前源码已具备“优先自动加载 APK 内置 `3714430278.zip`”逻辑；在此基础上已生成一份真正自包含的私有测试 APK：

- 内置资产：`assets/3714430278.zip`
- 资产 SHA-256：`eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f`
- APK：13,724,357 bytes
- APK SHA-256：`fe694d9b7ce24a6dae5018b0f5711082b632308343bdd0c27dea0d52aadf9c01`
- Drive 长期归档：`19TBASO7hsyRRA8RTyjCL7wVHEIxHZaT6`（`mygpt/02_Generated_Artifacts/mygpt-3714430278-selfcontained-20260929.apk`）
- APK Signature Scheme v2：本地密码学结构验证 PASS
- ZIP 完整性：PASS
- `lib/arm64-v8a/libgdx.so`：16K 对齐保持 PASS
- 启动行为：首次启动直接从 APK assets 自动安装并加载主皮肤；“更换皮肤包”只作为可选入口。
- 因本次本地私有测试 APK 重新签名，若与已安装测试版签名不同，需要先卸载旧 `dev.mygpt.spike` 再安装。
- 仍未宣称真机显示已通过；需要用户安装后确认首帧、idle、cue 与后台/恢复。

## 2026-09-29 · PR #13 刷新验收

- PR #13 从 PR #10 最新 head `3ad7d14a5446a3c0c6f23aa7e00703a3535f4e7e` 派生，保留 PR #10 当天新增的 CURRENT_STATE / EVALUATION_LEDGER / HANDOFF 状态。
- refresh 测试 head：`b48268e66633f6b1d1230d392afa450ebb0c3ab4`。
- workflow run `36511143238`：Java8 boundary PASS、Android assembleDebug PASS、`lib/arm64-v8a/libgdx.so` payload PASS。
- APK：1,381,959 bytes，SHA-256 `9963bacfaf0c2d7221bf6637cc155fdc7f9918a0c328a233edd0ebe7da89d593`；Spine runtime license notice 已包含。
- 长期 Drive artifact：`1mN2EpoCWCYQKiQaWjEhuOulRE2ToUbUa`。
- PR #12 作为旧对账线被 PR #13 取代；主动态皮肤仍为 `3714430278`，静态备选仍为 `backup_skin_image_01`。
- 下一门槛仍是小米 14 真机显示验收；真实 Book Android 学习事件尚未接入。

## 2026-09-29 · Live 主/备皮肤同步

- 主动态皮肤继续为 Live `3714430278`：Spine 4.1.20，Android CI 已通过，真机待验。
- CI APK SHA-256：`44bb4863c944c05e0acb30a7be9df6b9751b3600fc144e05812f4ee74d68fae2`；长期 Drive artifact ID：`1keutv3dGtexS2mMYoV8ptF7sOpq5f-7H`。
- 新增静态备选皮肤 `backup_skin_image_01`，Live Drive ID：`1adRumPFELRvB_4d7ORfnvUZRPhUTOLDW`，SHA-256：`9d03cf43b5d60a8ae486c17979e72bd294e479fc58732971aaa205df7e3f5cff`。
- 备选图当前仅作为静态 fallback / 人物视觉参考，不宣称具有 Spine/Live2D 动态能力。
- 新增 `android_spike/skin_candidates.json` 记录主/备关系；Live 继续是皮肤资产权威源。
- 本节现已重放到 PR #10 最新 head；PR #10 在 2026-09-29 新增的状态/评估/交接内容全部保留。

## 当前 Android Spine 渲染 exact-head CI 已通过（真机待验）

截至 2026-09-29，Draft PR #10 的精确头提交 `a076be06e2e4c3eeecdab3f1860143771bfef0d3` 已通过 Android companion boundary workflow run [36449517394](https://github.com/Jvust/mygpt/actions/runs/36449517394)。Java 8 package-layout smoke job `109020458878` 与 Android `assembleDebug`/Spine native payload job `109020458429` 均成功。GitHub Actions artifact `10983131261`（`mygpt-spine-3714430278-android-spike`，1,256,529 bytes，SHA-256 `1de222d0ef784a4fd5ab32970f5deb9772fcf12074a3fe2a2bc0108e7f896411`，保留至 2026-10-01）是当前 CI 证据；它是短期可重建产物，不是 Drive 长期归档。

这一步把状态从“renderer coded / CI pending”推进到“renderer exact-head CI pass / device pending”。已验证的是包布局校验、Spine 4.1.20 资源路径、Java 8 边界 smoke、Android 构建和 APK native payload；仍未验证小米 14 真机上的 SAF 导入、首帧、idle/cue 切换、后台恢复，以及真实 Book Android study-event producer。Spine Runtime 许可证仍是任何可分发构建的独立门槛；PR #10 保持 Draft，main 未修改。

下一步：在小米 14 安装该 exact-head debug APK，选择已解密 `3714430278.zip`，逐项记录首帧、`QUIET/PAUSED/NEEDS_INPUT/GENTLE_CHECK_IN`、后台重开和失败恢复，再接入真实且可撤销的 Book 事件源。

---

## 当前 Android 生命周期成果与源码快照

项目分支 `feat/android-companion-boundary-20260928` 持续保持 Draft PR #10。最新代码验证：push run `36369308484` 与 PR run `36369310978` 的 Java 8 smoke、Android debug 构建通过。当前 debug APK Drive ID `1dyBqjFz9IIc0_IXY1_YGtKTpvIdKm3BG`（SHA-256 `78e174567100487746a4d37330ed9caafed5da0ddb414752d3d172781345c5ed`）；完整源码快照 Drive ID `1WnYNLGb1lypDsqGl9xg2ejZaviGrrzVy`（commit `bf996e6e64c3f4d078102d337be31480dedf2f88`，131 tracked files，SHA-256 `006a000f88f11906d012decd3f4c6f3dd3484e660dfb266016dfa56f13afb4fc`）；变更文件评审包 Drive ID `16ROvan1oWIe_vST8ZWxRfdVJEUcnChNq`（SHA-256 `c9533e98ec3ee691b6202e1efd4d57090550027cfd2825f9320619679be8192a`）。真机生命周期验证及真实 Book/Live 接入仍待完成。

---

## Android 生命周期成果归档补充

当前 GitHub 分支头：`986b7b39cf0eda54e74e096f701d4b132c5bbdd9`，Draft PR #10 保持未合并。

- 最新合成 Android debug APK：Drive 文件 ID `1dyBqjFz9IIc0_IXY1_YGtKTpvIdKm3BG`，14,913 bytes，SHA-256 `78e174567100487746a4d37330ed9caafed5da0ddb414752d3d172781345c5ed`。
- 变更文件评审包：Drive 文件 ID `16ROvan1oWIe_vST8ZWxRfdVJEUcnChNq`，21,323 bytes，SHA-256 `c9533e98ec3ee691b6202e1efd4d57090550027cfd2825f9320619679be8192a`。它包含 Android 测试宿主变更和 APK，不是完整仓库快照；完整源码以 GitHub 分支为准。
- Java 8 smoke 与 Android `:app:assembleDebug` 已通过 push run `36369308484` 和 PR run `36369310978`。
- 离开前台、撤销、结束或到期时清除合成会话；本次提醒授权须重新开启。
- 真机生命周期验收、Book 真实学习事件和 Live 角色渲染仍待完成。

此补充更新本收据上一次同步时“没有 APK 或测试产物”的状态描述；上文作为当时同步记录保留。

---

## 2026-09-28 Android 宿主生命周期修复（CI 通过，真机待验）

`feat/android-companion-boundary-20260928@eef4d8e`、Draft PR #10：离开前台或锁屏即清除合成会话，到期后无需后续事件也收起提示；撤销、结束或新会话均需重新开启本次提醒。push run [`36369308484`](https://github.com/Jvust/mygpt/actions/runs/36369308484) 与 PR run [`36369310978`](https://github.com/Jvust/mygpt/actions/runs/36369310978) 的 Java 8 smoke、Android debug 构建成功。当前 APK 14,913 bytes，SHA-256 `78e174567100487746a4d37330ed9caafed5da0ddb414752d3d172781345c5ed`，Drive 文件 ID `1dyBqjFz9IIc0_IXY1_YGtKTpvIdKm3BG`；上一版保留为历史候选。仍未在真机上安装操作，Book 真实学习事件与 Live 角色均未接入。

---

## 2026-09-28 Android 合成测试宿主 APK（CI 通过，真机待验）

`feat/android-companion-boundary-20260928@332e9a2`、Draft PR #10：独立 Android debug 宿主的按钮产生明确标注的合成 Book 事件，驱动 Java 状态机和文字 cue；撤销立即清除会话。push run [`36368235878`](https://github.com/Jvust/mygpt/actions/runs/36368235878) 的 Java 8 smoke 与 `assembleDebug` 均成功。APK 14,033 bytes，SHA-256 `2a80adbb5bab0187f2b42eba22a044f79552eb13336468cef9b176b9b2bced78`，Drive 文件 ID `1HXRW8XBmHyG0lJtfP6FX3KvZ-SOCM8rY`。首次 run `36368130257` 因 setup-android 请求已移除的 SDK tools 包失败，改用 runner 预装 SDK 后通过。Manifest 不请求网络、麦克风或悬浮窗权限。Book 真实学习事件、Live 角色渲染、模型、语音和用户真机验收仍未完成。

---

## 2026-09-28 Android 集成边界原型（CI 通过）

`feat/android-companion-boundary-20260928@8e8c93b`、Draft PR #10：Java 8 状态机与 Live 中立 cue 接口已提交。推送 run `36367251552` 和 PR run `36367267599` 均成功；后者 `java8-boundary` job `108756041802` 的编译与 smoke 步骤成功。本地环境无 javac，所以本地编译未执行。Book Android 事件生产者、Live 实际渲染、APK 与真机验收仍未实现。下一步是以 Book 的真实授权事件接入测试宿主并绑定 Live 运行时；不直接启用模型或权限敏感功能。

---

## 2026-09-25 Windows 学习陪伴交付更新

- 新增 Windows 本机学习工作台：约拿陪伴、学习目标/计时、本地笔记、修订冲突保护、备份合并、本机 Ollama 明示调用入口。
- 发布源码固定为 `0fc965263b42b8a12e0cb7b006f4b1bdcd137596`；不修改 Book / StudyMate / ChatContextVault，不改 main。
- Windows delivery run `36149636550` 成功。
- 同源码 Linux 全套 490 pytest PASS；Windows 桌面专项 18 pytest PASS；JavaScript 66 项在两端通过（平台套件有重叠，不相加）。
- 原生 EXE 自检 5 项；Microsoft Edge 界面/退出/重启检查 13 项；包内 1,644 个文件逐项清单验证通过。
- 便携包：`mygpt-Windows-Portable.zip`，34,199,210 bytes，SHA-256 `37ebfa7158af866a19de48d9680054816b4fcbea006e73050ab2eab99211cd79`。
- Drive 完整交付归档：`mygpt-Windows-完整交付-20260925.zip`，文件 ID `15aYdyKH15Oakj1iuYblGxYScFQf8xx2A`。
- Draft PR #9 已创建，未合并。
- 边界保持：约拿仍是应用内陪伴而非系统级透明悬浮；不自动抓屏、不自动云同步；Book 实时桥和真实模型教学质量仍待用户设备验收。

## 当前入口 · PR #8 组合链路已全绿 · 2026-09-25

新的整合 review branch `feat/integrate-pr6-book-bridge-20260925` 以最新 PR #6 为基线，只移植 PR #7 的 Book lease receiver 运行/测试能力，**没有复制 PR #7 旧的 project_state/CURRENT_STATE/HANDOFF 替换内容**。当前 Draft PR #8 的实际运行 head `e9e5fb0` 已完成四套 exact-head CI：Brain SDK 双环境各 **446/0/0**，Book receiver 20 cases，Node **66 pass**，Jonah 49、replay 39、Python host 23、selection host 30，clean recovery 后 Brain **446/0/0**，launcher **12/12**，selection HTTP **32/32**。

长期 Drive 归档 `mygpt-integrated-book-bridge-v1-20260925.zip`（ID `1G0lZ1A9EHNrUTFGEfxwwXTsfgSZPk4QK`）已上传并下载回读：5,625,678 bytes，SHA-256 `eec9e3266b7d4afbf789a962945e7f74b7defbf47463875bc374aea6f4321f09`，ZIP CRC PASS。详细见 [INTEGRATION_CHECKPOINT_20260925.md](INTEGRATION_CHECKPOINT_20260925.md)。

**边界不变：**真实/付费模型为 0；未改 Book 仓库；未验证用户手机 Book APK、Windows/Android 真机、生产网络或独立审阅；没有自动 merge。

**下一步：** 对 PR #8 与配套 Book authority 做独立审阅；通过后再做真实 Book 选段 → mygpt 的授权 localhost/Android Studio 端到端 TestModel 验收。

---

## 当前入口 · 本地选段 + 可恢复完整源码已验收 · 2026-09-25

当前 PR #6 运行能力已经从固定合成样本推进到**显式本地选段**：只有用户预览并同意后才把一条本地内容送入 127.0.0.1 Python Brain；来源始终标记为 `USER_SUPPLIED_UNVERIFIED`，不会冒充 Book。精确 intake head `318c3ef` 的固定 SDK 两个干净环境各 **426 passed / 0 skipped**；浏览器 selection host **30 checks**、Node **66 pass**。完整结果见 [SOURCE_DELIVERY_CHECKPOINT_20260925.md](SOURCE_DELIVERY_CHECKPOINT_20260925.md)。

当前完整源码恢复 head `65c8d6b` 的 run `36019467569` 已通过：26 个 delivery tests、97 个 tracked source files 的确定性 ZIP、fresh restore、doctor READY、实际 launcher **12/12**、恢复后 Brain **426/0/0**、selection HTTP **32/32**。Drive 长期包 `mygpt-source-delivery-v1-20260925.zip`（ID `1b-YQbKedJSfRwQ5ZMHmWTaXjiQE2yo5m`）已下载回读，SHA-256 `c70ba62ac0cc42dcbd9981f5fe025d6f242e2de19e6b8c64e208957648a68dbd`。

并行 PR #7 的真实 Book 选段接收线继续独立保留，不在本分支自动合并；PR #5/#6/#7 需要三方冲突图与独立审阅。真实/付费模型、Windows/Android 实机、生产网络安全和独立代码审阅仍未验收。

**下一步：** 先做 PR #5/#6/#7 的只读三方冲突/依赖审查；然后在不覆盖历史的前提下决定新的整合 review branch。任何 merge 仍需具体 PR 的明确授权。

---

## 当前入口 · 浏览器已接通本机 Python Brain · 2026-09-23

当前分支 `feat/book-contract-audit-v1` / PR #6。运行代码从 `56b39522bb81aa71699548d2d93b060eb87dad6d` 开始；SDK 验收修正到 `ef31c36986ca0134c9c62bcdcdf2ebcdf155c431`，最新 UI 合同测试 head 为 `2c23fa5dec2fac17ce4d06aa083374007225d2f1`。

现在 `host/brain.html` 已不再只是浏览器预写回放：浏览器通过 **127.0.0.1 同源服务**实际进入 Python，Python 重建 ReaderContext v2、执行 Brain `SESSION_STARTED / HELP_REQUESTED`，再通过 Pydantic AI TestModel 返回固定合成样本。**真实 Book 仍未连接，真实/付费模型调用仍为 0。**

远端固定依赖验收：两个干净 Python 环境各 **332 passed / 0 skipped / 0 failed**（run 35816679199）；最新 host run 35817053593：**Node 54 pass、Jonah 49 checks、回放 host 39 checks、本机 Python host 23 checks**，运行/CSP errors 0、外部请求 0。首次 SDK/host 失败证据均保留，没有通过删除断言制造绿灯。

最新合同、安全边界、失败历史和恢复说明见 [本机 Brain 链路检查点](LOCAL_BRAIN_TRANSPORT_CHECKPOINT_20260923.md)。Drive 恢复包 `mygpt-local-brain-transport-v1-20260923.zip`：ID `1bMzAIh4vRpOxo4y_5WKZQWqt3_vm-CIo`，3,389,070 bytes，SHA-256 `5d5a2ba2e9ff7789c25384505e6274cc470b55b29daea48cfea5576f7aef2b58`，已完整下载回读和 CRC 校验。

**下一步：** 转到 Book r6 自己的非默认分支，先做“明确选中 record/layer → 只读短期快照”的最小导出器候选；重新执行 Book 的独立 preflight。默认不导出笔记/作答、不写 StudyRecord、不调用模型。Android、生产多用户网络、真实教学质量和独立审阅仍待完成；PR #5/#6 冲突不自动处理。

---

## 当前入口 · Reader × Jonah 宿主界面验收 · 2026-09-23

当前分支 `feat/book-contract-audit-v1` / PR #6。宿主运行代码 `b688943fe710537ff0e7807361a303bd7b7aa04e`：远端 Node **49 项通过**，原 Jonah 浏览器 **49 项通过**，新宿主浏览器 **39 项通过**。Python/样本源码 `d24802d9906c559f2099d44eedbb7d58b9148d3f` 在两个干净环境分别 **290 passed / 0 skipped**；后续 UI 修正未改 Python 代码或样本。

打开 `host/reader.html` 可操作选段、查看原文/校正/推导层、回放预写回复、取消、暂停和检验过期状态；Jonah 只显示实际界面请求状态。**仍是合成回放，不是浏览器已连接 Python Brain、真实 Book 或模型。**

最新验收、第一次失败及修正、D019/E007 和恢复边界见 [宿主 UI 检查点](HOST_UI_CHECKPOINT_20260923.md)；运行命令见 [host/README.md](../host/README.md)。原始失败/成功 artifacts 进入 `mygpt-host-ui-v1-20260923` 恢复包，精确 Drive 身份以 artifact_manifest 为准。

下一步：在 mygpt 内设计宿主到真正 Python Brain 的最小同机请求合同，继续使用合成资料/TestModel；网络实现前先明确 loopback、Origin/Host、临时授权、来源身份、取消及撤销边界。当前不改 Book、不增加付费调用、不写 main、不自动合并；PR #6 与 #5 的整合冲突及独立审阅继续待处理。

---

以下原始内容保留为历史。旧 next_step 和“未重跑 UI”以本节替代，未验收的真实网络/Book/Android 限制仍有效。

## 当前入口 · r6 明确选段已通过组合验收 · 2026-09-23

当前分支 `feat/book-contract-audit-v1` / PR #6；精确通过代码 `86734b51024a4f0ae7c254835c9fe0178151bee3`。
GitHub run `35797671670`：两个干净环境分别 **269 passed / 0 skipped / 0 failed**；包含三种选段内容层经过 TestModel/MCP 的验证。

最新说明、D018/E006、限制和恢复命令见 [Reader 选段检查点](READER_SELECTION_CHECKPOINT_20260923.md)。当前目标是 r6 `/api/reader/...`，旧 Web DTO 校验器仅作参考，不与 r6 混用。

下一步：在 mygpt 自己的宿主演示接入明确选择与“解释这段”，显示版本/层级/失效状态并与 Jonah 用户事件联动，先用合成事件验证。尚未连接真实 Book、调用真实模型或验收 Android；独立审阅 PENDING，PR 不合并。
归档身份以 `governance/artifact_manifest.json` 的 `mygpt-reader-selection-v1-20260923` 为准。以下旧正文逐字保留为历史，其 SDK 阻塞、旧目标分支和旧 next_step 不作为当前状态。

---

## 最新检查点 · 2026-09-22 · PR #5

当前开发分支：`feat/book-context-brain-20260922`，基于 PR #3 的 `a8595c3ccaddcff5a6a95f8a37a963707f48c084`。
实现提交：`68c351b85511ccdd625036a6917b4303646b6704`。新增可运行的 `brain/`，不是正式 Book/模型/Android 集成。
本地两次最终源码回归均为 **95 passed, 2 skipped**；2 项跳过是 Pydantic AI / MCP SDK 未安装，不是通过。真实模型调用为 0，独立审阅待完成。
源码/原始测试证据包已在 Drive 归档并下载回读验证：`13YcH0j9VXd20LLWspZzDquRm-pe02OSJ`。
最新验收、设计决定和边界见 [Brain checkpoint](BOOK_CONTEXT_BRAIN_CHECKPOINT.md)；运行见 [brain/README.md](../brain/README.md)。
下一步：先补齐无付费调用的 SDK 集成验证，再核对 Book 实际字段/版本并设计真实事件适配器。不要直接改 main 或自动合并。

---

以下正文保留此前阶段的原始快照。旧的“未发布/尚未开始后端”表述不再代表本分支最新原型状态；以本节和 project_state 为准。

# Current State

Date: 2026-09-22

## Project status

- Repository: `Jvust2/mygpt`
- Default branch: `main`
- Foundation branch: `chore/security-bootstrap-and-project-foundation-20260921`
- Project classification: formal long-term project
- Drive mapping: `mygpt`
- Security bootstrap files are present on the non-default foundation branch.
- The Drive global safety baseline and branch `SECURITY_POLICY.md` have been re-read successfully after bootstrap.
- No merge is authorized by this synchronization.

## Jonah companion UI candidate

- Feature branch: `feat/jonah-companion-20260922`, based on the unmerged foundation head so its governance remains visible in the review diff.
- Added a framework-neutral `<mygpt-pet>` Web Component and a runnable mobile/desktop preview.
- Reused the verified Jonah sprite atlas: SHA-256 `828b0fb468382f37aaf0d62a3e86cb33e5fcad5dbde8aeb091d6778b32a77790`.
- Implemented nine animation states, sixteen look directions, bottom-right anchoring, touch dragging, keyboard movement, hide/restore, size controls, reduced-motion support, and local preference fallback.
- The component emits a chat-request event and accepts explicit host task states. It does not infer distraction, read other apps, capture screens, or claim that a model/Book bridge exists.
- Deterministic atlas tests: 3/3 pass.
- Headless Chromium interaction checks: 45/45 pass, including real touch events, reload persistence, narrow/landscape/desktop viewports, reduced motion, disconnected cleanup, disabled storage, runtime errors, and external requests.
- Visual screenshots were inspected. The test runtime lacked a CJK font, so Chinese labels rendered as fallback squares in those screenshots; the component uses system fonts and does not download a web font.
- Not yet verified: Android physical device, Android soft keyboard, native Android overlay, production mygpt host integration, production chat/Book bridge, and independent human review.
- This candidate appears inside a mygpt web/app surface. Cross-application Android floating UI requires a separate Android Studio implementation and system overlay permission.

## 2026-09-22 interaction reliability candidate

- Prepared from `feat/jonah-companion-20260922` at `64e73b257a79ec09787e2a96a43816b5864f9a1c`; the existing feature PR and foundation PR remain unmerged.
- Corrected keyboard activation after touch cancellation, unrelated pointer events interrupting a drag, and missing focus transfer into the action panel.
- The browser suite now creates its own preview on an available loopback port and cleans up even if Chromium cannot launch.
- Validation at this local candidate: 3/3 deterministic checks and 49/49 Chromium checks; a deliberately occupied default port still permits the suite to pass, and a missing browser exits promptly with a failure status.
- Remote publication is pending the all-repository preflight confirmation. Proposed review branch: `fix/companion-input-and-test-isolation-20260922`, targeting the existing feature branch. See E003 in `docs/EVALUATION_LEDGER.md` for reproduction evidence and remaining device limits.

## Product direction

mygpt is the user's primary companion surface.

It combines:
- **Book**: what the user is learning, exact course/chapter/section/mode/source references, and later concept-level learning state;
- **StudyMate**: study-session lifecycle, low-cost device/app/idle signals, and optional sensor bridge;
- **ChatContextVault**: protected relationship-history retrieval and optional Shadow mode;
- **mygpt Brain**: live conversation, activity interpretation, learning coaching, emotional-support conversation, intervention policy, and cross-session project state.

## Preferred perception strategy

`Book First → OS Sensor Second → User Context Third → Screen Vision Last`

The initial product should not depend on continuous screen capture.

When the user studies inside Book, Book should emit structured context such as:
- course / book / chapter / section
- Preview / Learn / Review / Practice mode
- current source or active item
- scroll position / active source / expanded source state
- dwell time and relevant navigation events
- practice/review outcomes when available

StudyMate or an Android sensor bridge may add:
- current foreground app
- screen on/off
- idle / return events
- study-session boundaries
- time away from Book

Vision remains a fallback for PDF/image/canvas/unsupported external content and should be session-scoped and explicitly authorized.

## Companion behavior

Default state is Silent Presence.

The system may escalate to:
1. Light Companion
2. Study Coach
3. Active Supervisor

Examples of useful behavior:
- stay silent while learning is going well;
- ask whether the user is stuck after repeated back-and-forth behavior;
- use Book context to answer "这里为什么这样" without requiring a new screenshot;
- ask a recall question after a meaningful learning segment;
- distinguish a short break from likely distraction;
- ask rather than accuse when screen/device evidence is ambiguous;
- switch to ordinary companionship or emotional-support conversation when learning is not the immediate need.

## Shadow boundary

ChatContextVault is not the default personality of mygpt.

Shadow mode is optional, explicit, and clearly labeled. It should prioritize:
1. retrieved facts,
2. observed long-term interaction patterns,
3. communication style.

It must not invent romantic intent, relationship progress, or the real person's current thoughts.

## Immediate next milestone

Design and implement the minimum event contract between Book and mygpt so mygpt can know where the user is in Book without screen recognition.

A first acceptance target:

> During a 30-minute Book study session, mygpt can know the current learning location and mode, detect meaningful study transitions, stay quiet by default, answer context-dependent questions, and selectively prompt for clarification or recall without continuous screen capture.

No production backend, Book event bridge, or Android application has been started in this repository yet. The Jonah companion is the first executable UI candidate and remains unmerged.
## 2026-09-27 独立审查更新

- PR #9 桌面交付与 PR #8 / Book authority 边界已完成独立审查，未发现需要阻止继续推进的 Critical/Major 问题。
- 实际 Book `Authority` → mygpt `BookReceiver` TestModel 联调通过；重复收据、内容摘要和撤销语义通过。
- `tools/desktop_browser_test.py` 新增 Windows `/host/brain.html` loopback TestModel 回归；用户本人 Windows 设备、Android/真实 Book APK 和真实模型质量仍未验收。
- 详细审查记录见 [INDEPENDENT_REVIEW_20260927.md](INDEPENDENT_REVIEW_20260927.md)。
