## Latest handoff · Xiaomi 14 full matrix + native voice loopback ready · 2026-09-30

Implementation checkpoint: `9920d53800ad1aec741630300283d385825fd986`; Draft PR #15; main untouched.

Do not add more default-model guesses. Run the existing Windows acceptance route. For the broadest automatic gate, use the verified 3714430278 local source plus `-LlmMatrix -SherpaModels`. That path now exercises signed Book/supervision/PiP, three fixed GGUF performance runs, five fixed Chinese output samples per candidate, sherpa import/integrity, and an in-memory TTS->ASR native loopback. The final collector gathers all of those into one evidence directory.

Important corrections:
- prompt hard turn limit is 5200 chars; combined system+turn character guard is 7200;
- LLM qualitative execution PASS does not mean “best model”;
- synthetic voice loopback PASS does not replace live microphone or audible TTS testing;
- GitHub hosted red runs are still zero-step runner-provisioning failures.

Do not merge until Xiaomi 14 evidence exists.

---

## Latest handoff · verified 3714430278 auto-bundle path · 2026-09-30

Branch/head: `feat/airi-chat-memory-brain-20260929` @ `90e5a8dc2528951fa664412a8ae66ec45a018e01`; Draft PR #15; main untouched.

Use `android_llm_spike/scripts/build_and_install_companion_v2.ps1`. If Google Drive Desktop exposes the verified `Live/skin/workshop/3714430278/3714430278.zip`, the script should find it automatically. You can also pass `-SkinZip` or `MYGPT_SKIN_ZIP`.

A skin is never bundled by filename alone: exact 12,342,220-byte size and fixed SHA-256 are required before copying, and the APK entry is SHA-verified again after build. The binary stays outside Git.

With a bundled skin, Companion V2 auto-installs it at first launch and the Windows acceptance route automatically exercises PiP above the Book test sender. If no local verified ZIP is available, the APK remains valid and exposes the manual picker.

Next unresolved device inputs are a benchmark candidate **chat** GGUF and sherpa ASR/optional TTS model packages. Do not use the Drive Qwen-Image GGUF as the conversation brain.

Do not merge PR #15 before Xiaomi 14 evidence.

---

## Latest handoff · pre-device hardening complete · 2026-09-30

Current exact head: `4efd70b716ab35f94af7556ee7ed5149e77d60a9`; Draft PR #15; main untouched.

Before adding more product features, run the existing Windows/Xiaomi 14 path. Current code now includes prompt budgeting, verified sherpa fingerprints, off-main model restore verification, active signed-state expiry, PiP microphone stop, and interrupted-llama session recovery.

Use:
`android_llm_spike/scripts/build_and_install_companion_v2.ps1`

After 3714430278 is loaded, run:
`android_llm_spike/scripts/test_companion_pip.ps1`

Then import a candidate GGUF + sherpa ASR/TTS, run the in-app benchmark and local chat/voice/memory checks, then:
`android_llm_spike/scripts/collect_companion_v2_evidence.ps1`

Do not claim the current head builds yet: hosted jobs still receive no runner and execute zero steps. Do not merge PR #15.

---

## Latest handoff · Book client SDK ready · 2026-09-30

Current branch/head: `feat/airi-chat-memory-brain-20260929` @ `2e687fd348edfe1e787cb6634f272df69c05e0cf`; Draft PR #15; main untouched.

The future real Book Android producer no longer needs to reimplement the broadcast protocol. Use `android_llm_spike/book-client-sdk` / `book-client-sdk-release.aar`. The synthetic same-signature device sender now uses the same SDK, so the Xiaomi 14 acceptance route validates the intended producer API rather than a separate hand-written intent path.

Do not describe Book as connected yet. Remaining Book-side gates are:
1. build the AAR at this exact head;
2. pass the same-signature synthetic sender gates on Xiaomi 14;
3. adopt the AAR in Jvust/Book;
4. verify Book and Companion signing identities;
5. replace synthetic inputs with bounded real structured Book projections.

GitHub Actions remains infrastructure-blocked before step 1 (runner_id=0). Do not merge PR #15.

---

## Latest handoff · PR #15 · exact head 907208ac0db090635fcf1fc342223ad51f97fdaa

The current branch has a unified 3714430278 persona source and an automated
quiet-supervision agency gate. Do not duplicate the persona in Android or weaken
the signature permission.

Next command on Windows:

`powershell -ExecutionPolicy Bypass -File .\android_llm_spike\scripts\build_and_install_companion_v2.ps1`

The script invokes the supervision gate automatically. After manual skin/model/
voice/PiP checks and the in-app llama benchmark, run:

`powershell -ExecutionPolicy Bypass -File .\android_llm_spike\scripts\collect_companion_v2_evidence.ps1`

Do not merge until the exact-head local/device evidence exists.

---

## Latest handoff · PR #15 · PiP + quiet-first supervision gate ready

Current exact head: `4d26563d8c03453f27c9a31186a484004d6d1535`.

Do not wait for hosted Actions; they still fail before runner allocation. Run:

`android_llm_spike/scripts/build_and_install_companion_v2.ps1`

The Windows script now automatically checks same-signature Book context and invokes:

`android_llm_spike/scripts/test_companion_supervision.ps1`

That supervision gate proves Book cannot independently turn on proactive supervision: the same signed repeated-error event remains QUIET before the MyGPT-local opt-in tap and becomes GENTLE_CHECK_IN only after that tap.

After installing/importing the real skin/models, validate PiP above Book, run the local llama benchmark, test ASR/TTS/memory, then run:

`android_llm_spike/scripts/collect_companion_v2_evidence.ps1`

Main remains untouched; PR #15 remains Draft; Book/Live repositories are not modified.

---

## Latest handoff · PR #15 · local-device gate ready

Current head: `5b932e6f1bbe1ca7db645802475d50b322c32ec4`.

The next operator should **not wait on GitHub hosted runners**. Use the pinned Windows wrapper path:

`android_llm_spike/scripts/build_and_install_companion_v2.ps1`

Then follow:

`docs/COMPANION_V2_XIAOMI14_ACCEPTANCE.md`

After manual Book/skin/GGUF/ASR/TTS/memory/benchmark checks, collect final evidence with:

`android_llm_spike/scripts/collect_companion_v2_evidence.ps1`

Important boundaries remain:
- main untouched; PR #15 Draft;
- Book/Live repositories untouched;
- real Book producer not yet connected;
- synthetic Book sender is test-only;
- Companion V2 has no INTERNET, SYSTEM_ALERT_WINDOW or broad-storage permission;
- Book context stays process-memory only;
- recent conversation is not semantic long-term memory;
- model weights remain external user inputs.

Do not mark Companion V2 accepted until the exact-head local build and Xiaomi 14 evidence package exist.

---

## Latest handoff · 2026-09-30 · PR #15 Companion V2 all-local candidate

Current branch/head: `feat/airi-chat-memory-brain-20260929` @ `a83680c1810242d541941b6c2b1a361c8d00bf71`; Draft PR #15; base `feat/spine-3714430278-runtime-refresh-20260929`; main untouched.

Current candidate is no longer just an AIRI chat experiment. The isolated Companion V2 code now combines:
`3714430278 Spine + app-private GGUF + llama.cpp JNI + sherpa streaming ASR + optional Melo TTS + explicit Android memory + AIRI ACT emotion`.

Runtime intent is fully local after models/skin are imported. Companion V2 requests only RECORD_AUDIO; it does not request INTERNET, SYSTEM_ALERT_WINDOW or broad storage access. Model weights remain external inputs and are not committed.

Do **not** claim the new APKs/AARs build successfully yet. GitHub hosted Actions still fail before runner allocation; exact-head runs `36659174083`, `36659174123`, and `36659174091` all show runner_id=0 and zero steps. Earlier accepted PR #13 / v0.0.6 skin evidence remains historical and must not be overwritten.

Highest-value next step: execute the exact-head llama/sherpa/Companion V2 builds on a functioning runner, then install on Xiaomi 14 and test model load, typed chat, mic ASR, TTS, memory and 3714430278 reactions. After that, connect real authenticated Book context. Do not auto-merge.

---

## Latest parallel checkpoint · PR #15 companion runtime expansion

Draft PR #15 is now at `741c70b2b8102b4f8a5f3eeb0fe7a73442675dd5`, stacked on the current PR #13 skin branch. It contains direct, attributed code adoption from AIRI (MIT), Mem0 (Apache-2.0) and sherpa-onnx (Apache-2.0).

The current added layers are:
`Book ephemeral context -> authority-aware chat -> explicit/auditable memory -> local Ollama interface -> renderer-neutral emotion`, plus an Android PCM capture foundation for future offline ASR.

Important limits:
- Book/Live repositories were not modified;
- no raw Book context is persisted by the chat candidate;
- no chat transcript is auto-promoted to memory;
- no real Ollama call accepted yet;
- microphone permission is not automatically requested;
- raw audio is not stored;
- GitHub Actions is presently failing before runner allocation (`runner_id=0`, zero steps), so do not report remote CI as passed or as a code assertion failure;
- Android physical-device acceptance remains pending.

Use `third_party/*/NOTICE.md` and `governance/open_source_sources.json` before further direct code copying. Do not auto-merge PR #15.

---

## Parallel candidate · PR #15 · AIRI chat/memory brain

A stacked draft PR #15 (`feat/airi-chat-memory-brain-20260929` → `feat/spine-3714430278-runtime-refresh-20260929`) now contains the first bounded direct AIRI adoption: authority-aware chat contracts, durable local sessions/request receipts, explicit SQLite memory, and a loopback-only Ollama adapter. AIRI is pinned at `b40e3e87b149ea5fb75d4944440493829e601411` under MIT with in-repo attribution. Local isolated tests are 18/18; GitHub run `36590899728` failed twice before allocating a runner, so remote tests remain pending. Do not describe this as live-model or Android acceptance yet. Do not auto-merge.

The Android/skin Xiaomi 14 gate below remains valid and independent; PR #15 must not overwrite that historical/device state.

---

## 当前接手点 · Spine exact-head CI 通过，进入小米 14 真机门

- 分支：`feat/android-companion-boundary-20260928`；Draft PR #10；精确 head `a076be06e2e4c3eeecdab3f1860143771bfef0d3`；未合并，main 未修改。
- CI：run [36449517394](https://github.com/Jvust/mygpt/actions/runs/36449517394) 成功；Java 8 job `109020458878`、Android host job `109020458429` 成功。
- 产物：GitHub artifact `10983131261` / `mygpt-spine-3714430278-android-spike`，1,256,529 bytes，SHA-256 `1de222d0ef784a4fd5ab32970f5deb9772fcf12074a3fe2a2bc0108e7f896411`，2026-10-01 到期。该产物未复制到 Drive；manifest 只登记 GitHub artifact 身份。
- 已验证：`3714430278.zip` 的 Spine 4.1.20 包布局与安全解压边界、Java 8 coordinator/package-layout smoke、Android debug 构建、`lib/arm64-v8a/libgdx.so` 与 `classes.dex`。
- 尚待：小米 14 安装、SAF 选择已解密包、首帧与 idle/cue/background-reopen、真实 Book Android producer。Book 事件仍为 synthetic test double；Spine Runtime 仍限私有调试评估。

接手后先保存真机日志和截图，再修改状态文件；不要把 CI 通过写成 device acceptance，也不要 merge PR #10。

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

## 2026-09-25 最新交付接手点

- Windows 发布源码：`0fc965263b42b8a12e0cb7b006f4b1bdcd137596`。
- Drive 完整交付文件 ID：`15aYdyKH15Oakj1iuYblGxYScFQf8xx2A`。
- Draft PR：#9；未合并、不得自动合并。
- 用户本人 Windows 设备验收仍未完成；发布包的自动验收环境为 GitHub hosted Windows / Microsoft Edge。

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

# mygpt Handoff

## Start here

1. Read Drive root `全项目` and all current `全项目_*` baselines.
2. Read exact-target-branch `SECURITY_POLICY.md` and `AGENTS.md`.
3. Read `governance/project_state.json`.
4. Read North Star, Architecture Invariants, Current State, Decision Ledger, Evaluation Ledger, artifact manifest, and pending sync.
5. Restore Book / StudyMate / ChatContextVault state from their own repositories only when needed.

Repository evidence outranks chat recollection.

## Current recovery point

The project foundation remains in PR #1 on `chore/security-bootstrap-and-project-foundation-20260921`.

The stacked feature branch `feat/jonah-companion-20260922` adds the first executable UI candidate: a local-only Jonah Web Component and mobile/desktop preview. It must not be described as a production mygpt app or Android APK.

The central architectural decision is:

`Book First → OS Sensor Second → User Context Third → Screen Vision Last`

The first engineering milestone is a small Book-to-mygpt semantic event contract, not full-device screen surveillance.

For the Jonah candidate, start with `docs/JONAH_COMPANION.md`. Its atlas hash, API, test evidence, Android boundary, external references, and integration steps are recorded there. The renderer exposes explicit state inputs and a chat-request event; the future host owns task truth and conversation behavior.

## Current product concept

mygpt should feel like a person who is present:
- usually quiet when the user is studying well;
- able to teach using current Book context;
- able to notice meaningful departures or likely distraction;
- able to ask whether the user is stuck rather than making brittle assumptions;
- able to switch naturally between learning, encouragement, ordinary conversation, and emotional support.

Shadow mode is optional and explicitly simulated.

## Next step

After review of the foundation and companion PRs, select the production host and produce the v0.1 interface/spec for:
- Book StudyContext snapshot;
- Book StudyEvent stream;
- Companion intervention state;
- local session state and privacy gates;
- minimal communication path between Book and mygpt.

Do not implement continuous screen capture before proving that Book semantic context plus low-cost device signals are insufficient.

If mobile delivery is selected, use Android Studio for the app/WebView host and physical-device validation. Treat an Android cross-app overlay as an optional separate milestone; do not confuse it with the current in-app fixed-position component.
