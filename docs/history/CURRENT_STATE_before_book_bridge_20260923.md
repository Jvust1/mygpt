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
