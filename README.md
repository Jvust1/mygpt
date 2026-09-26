# mygpt

mygpt is a long-term companion and learning orchestrator.

It is designed around a simple idea: **presence without pressure**.

The system should know enough context to understand what the user is learning, when help is useful, when distraction is likely, when emotional support matters, and when the best action is to stay quiet.

## Architecture

mygpt integrates, but does not replace:

- **Book** — structured learning content and semantic study context.
- **StudyMate** — study-session and low-cost device/activity signals.
- **ChatContextVault** — password-gated relationship-history retrieval and optional Shadow grounding.

Preferred perception order:

`Book semantic context → OS/App signals → user-declared context → opt-in screen vision`

## Start here

- [AGENTS.md](AGENTS.md)
- [SECURITY_POLICY.md](SECURITY_POLICY.md)
- [Project North Star](docs/PROJECT_NORTH_STAR.md)
- [Architecture Invariants](docs/ARCHITECTURE_INVARIANTS.md)
- [Current State](docs/CURRENT_STATE.md)
- [v0.1 Product Architecture](docs/MYGPT_V0_1_PRODUCT_ARCHITECTURE.md)
- [Decision Ledger](docs/DECISION_LEDGER.md)
- [Evaluation Ledger](docs/EVALUATION_LEDGER.md)
- [Handoff](docs/HANDOFF.md)
- [Pre-Flight Checklist](docs/PRE_FLIGHT_CHECKLIST.md)
- [Machine-readable project state](governance/project_state.json)

## Current milestone

Define and validate the Book-to-mygpt semantic StudyContext / StudyEvent contract before adding broad continuous screen capture.

No application implementation is yet claimed.


## 长期成长计划

[长期成长路线图（2026-09-22）](docs/LONG_TERM_ROADMAP.md)：当前起点、能力与规模的成长路径、进入下一层级的条件、优先任务及跨项目边界。规划目标与已完成功能分别标注。

## 书籍与开源参考

[学习资源清单](docs/LEARNING_RESOURCES.md)：5 本书、12 项 GitHub 参考，按项目成长环节说明用途、优先级、许可与最小应用产物。书目查证至 2026-09-26（UTC），仓库维护元数据已复核。
