## 最新验收 · 2026-09-23（+08）· PR #5

代码 `95fd2846f5ec535b1241b4bb565fbca92eda626e` 已通过真实 SDK 集成；[GitHub run 35762870487](https://github.com/Jvust2/mygpt/actions/runs/35762870487) 在两个全新虚拟环境中分别 **113 passed / 0 skipped / 0 failed**。39 个依赖 wheel 已锁定哈希并验证重装；两次真实失败的原始证据保留。

这是程序式 TestModel 与进程内 MCP 的验收，未调用真实模型、未连接 Book、未验收 Android。Book CURRENT r6 原包已只读核对，发现版本号 `@` 与当前标识符规则不兼容，且缺少显式选段/宿主会话事件；详见 [Reader 映射](BOOK_READER_BRIDGE_MAPPING_20260923.md)。

[本轮 SDK 检查点](SDK_ACCEPTANCE_CHECKPOINT_20260923.md) 是最新验收与决策入口。恢复包 [mygpt-brain-sdk-acceptance-20260923.zip](https://drive.google.com/file/d/1kENqb7SLkEV6B4YK8BZ1rq9ceSiMR5Fs/view) 已归档并下载校验，SHA-256 `faf62347879a790f53826d43cb61f19a49a718a5faddf9987b36cf35ec3a98ba`。

**下一步只做：** mygpt 分支内的 ReaderSnapshot 离线映射候选、版本兼容和显式选段/来源层回归；不改 Book、不开放网络服务、不增加付费调用。独立审阅仍待完成，PR 保持草稿，main 不变。

---

以下全部内容为保留的历史快照。旧的 SDK 阻塞与旧 next_step 已由上方验收/下一步替代；其他未验证的生产能力限制继续有效。

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
