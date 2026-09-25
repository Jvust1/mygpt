# mygpt

## 当前检查点 · PR #8 组合链路全绿（2026-09-25）

`feat/integrate-pr6-book-bridge-20260925` / Draft PR #8 把当前 PR #6 的显式本地选段/完整源码恢复与 PR #7 的 **Book lease receiver 运行能力**放到同一棵树中，并刻意保留新的治理状态而不是覆盖回旧版。

Exact head `e9e5fb0`：Brain SDK 双环境各 **446/0/0**；Book receiver **20 cases**；Node **66 pass**；浏览器 Jonah 49 / replay 39 / Python host 23 / selection host 30；clean recovery 后 Brain **446/0/0**、launcher **12/12**、HTTP **32/32**。

Drive 集成证据：`1G0lZ1A9EHNrUTFGEfxwwXTsfgSZPk4QK`，SHA-256 `eec9e3266b7d4afbf789a962945e7f74b7defbf47463875bc374aea6f4321f09`。详见 [integration checkpoint](docs/INTEGRATION_CHECKPOINT_20260925.md)。

真实模型、Android/Windows 真机、用户实际 Book APK 和独立审阅仍未完成；PR #8 不自动合并。

---

## 当前检查点 · 本地选段与完整源码恢复（2026-09-25）

PR #6 已支持显式本地单条内容输入，来源固定为 `USER_SUPPLIED_UNVERIFIED`；`318c3ef` 的固定 SDK 双环境各 **426/0/0**，selection 浏览器 **30 checks**。随后 `65c8d6b` 增加完整源码恢复与显式启动器：delivery run `36019467569` 完成 97 个 tracked source files 的确定性源码包、fresh restore、Brain **426/0/0**、HTTP **32/32**、launcher **12/12**。

当前长期恢复包：`mygpt-source-delivery-v1-20260925.zip`，Drive ID `1b-YQbKedJSfRwQ5ZMHmWTaXjiQE2yo5m`，SHA-256 `c70ba62ac0cc42dcbd9981f5fe025d6f242e2de19e6b8c64e208957648a68dbd`。完整使用入口见 [START_HERE.md](START_HERE.md)，验收边界见 [source delivery checkpoint](docs/SOURCE_DELIVERY_CHECKPOINT_20260925.md)。

真实 Book 接收能力仍在并行 PR #7；没有在 PR #6 内自动解决 PR #5/#6/#7 冲突。真实/付费模型、Android/Windows 实机与独立审阅仍未完成。

---

## 当前检查点 · 浏览器 → 本机 Python Brain 已接通（2026-09-23）

当前开发候选：`feat/book-contract-audit-v1` / PR #6，仍为 Draft、未合并。最新治理/归档 head 为 `6937d1c3b8d186e9b7b53a4c5e416793be7d4477`；实际运行链从 `56b39522` 开始，最新已验收测试 head 为 `2c23fa5d`。

现在的合成链路是：

```text
host/brain.html
  → same-origin 127.0.0.1
  → Python LocalBrainEngine
  → ReaderStudyContext v2
  → Brain SESSION_STARTED / HELP_REQUESTED
  → Pydantic AI TestModel
```

它已经不是纯浏览器预写回放，但仍然 **没有连接真实 Book，也没有调用真实/付费模型**。当前远端验收：固定 SDK 环境中两次各 **332 passed / 0 skipped / 0 failed**；最新 UI head 为 **Node 54 pass、Jonah 49 checks、旧回放 host 39 checks、本机 Python host 23 checks**。

恢复入口：
- [当前状态](docs/CURRENT_STATE.md)
- [本机 Brain 链路检查点](docs/LOCAL_BRAIN_TRANSPORT_CHECKPOINT_20260923.md)
- [宿主运行说明](host/README.md)
- [Brain 运行说明](brain/README.md)
- [artifact manifest](governance/artifact_manifest.json)

下一阶段转入 Book r6 自己的独立 preflight：只做“用户明确选中 record/layer → 只读短期快照”的最小导出器候选；默认不导出笔记/作答、不写 StudyRecord、不启用付费模型。

---

Long-term companion and learning orchestrator.

## Current review branches

- Project foundation: `chore/security-bootstrap-and-project-foundation-20260921` / PR #1.
- Jonah companion UI: `feat/jonah-companion-20260922`, based on the foundation branch.

The Jonah integration is a framework-neutral, mobile-friendly Web Component and interactive preview. See [`docs/JONAH_COMPANION.md`](docs/JONAH_COMPANION.md) for scope, API, validation evidence, and the Android boundary.

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
