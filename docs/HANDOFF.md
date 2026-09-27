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
