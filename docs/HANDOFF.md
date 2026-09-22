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
4. Read North Star, Architecture Invariants, Current State, Decision Ledger, Evaluation Ledger, artifact manifest, pending sync, and Pre-flight Checklist.
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
