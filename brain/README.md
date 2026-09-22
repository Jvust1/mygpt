## 当前能力 · r6 Reader 选段 v1 / Brain context v2

实际通过代码 `86734b51024a4f0ae7c254835c9fe0178151bee3`，GitHub run `35797671670`：两个干净环境分别 **269 passed / 0 skipped / 0 failed**。本地缺 SDK 时仍是 264 passed / 5 skipped；不混用两类结果。

新增 `reader_snapshot.map_reader_snapshot`：明确选择原文、来源绑定的校正或 AI 推导；保留含 @ 的版本号，校验时效与宿主快照，按固定 JSON/UTF-8 计算实际正文及父来源哈希。原 v1 引用和旧数据不迁移。

```sh
cd brain
python -m mygpt_brain.reader_demo
# 已安装固定 SDK 时，使用已有严格验收脚本；输出目录必须为新目录。
python scripts/verify_integrations.py --output ./acceptance-new
```

数据和宿主事件仍全部为 SIMULATED；TestModel 只返回固定程序内容。原文选择不是屏幕渲染复刻，不静默应用 render_text/render_latex/source_completion，不处理图片。未连接真实 Book、未开放网络监听、未调用真实模型、未验收 Android。

完整合同、运行证据、回滚限制和下一步见 [Reader 检查点](../docs/READER_SELECTION_CHECKPOINT_20260923.md)。以下旧说明逐字保留为历史，SDK 阻塞及旧 next_step 以本节替代。

---

# mygpt Brain · Book 上下文原型 v0.1

**状态：可运行的本地模拟原型；不是正式 Book 联调、聊天服务或 Android APK。**

## 本批次解决什么

保留既有 Jonah 渲染组件，用独立 Python 模块验证学习上下文及事件的最小契约。正常事件保持安静，只有显式 `HELP_REQUESTED` / `RECALL_REQUESTED` 产生讲解/回忆检查**提案**，不代表已经调用模型或给出了正确答案。

```text
合成 StudyEvent → Pydantic 校验 → SQLite 事务/去重 → 当前上下文投影
                                                  ↓
                                  安静优先策略 → Decision/Receipt
                                                  ↓
                       可选只读 MCP 接口 / TestModel 接线验证
```

## 运行

需要 Python 3.11+。核心固定使用 Pydantic 2.13.4；下列命令在联网且允许安装包的环境执行：

```sh
cd brain
python -m venv .venv
# Windows: .venv\Scripts\activate
# POSIX: source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
python -m mygpt_brain
```

最后一条命令只在内存中执行八条模拟演示输出，无网络、无凭据读取、无数据库文件写入。合成时钟固定以方便复跑，不代表用户真实学习时间。第 4 条是重复求助，结果必须为 `duplicate / stay_silent`；最后结束会话并清空上下文。

可选集成依赖：

```sh
python -m pip install -e '.[test,integrations]'
python -m pytest tests/test_integrations.py -q
```

依赖候选：`pydantic-ai-slim==2.46.0`、`mcp==2.2.0`。这是顶层依赖固定，不是完整传递依赖锁。当前环境依赖下载被 DNS 阻断，两项集成测试明确跳过，**不宣称这组 SDK 的实际兼容性已通过**。

## 契约与状态规则

`StudyContext` 保存会话、课程、书籍、版本、章节、来源 ID、来源 SHA-256、学习模式及捕获/失效时间。模式为 `preview / learn / review / practice`。ID 为 1–96 个受限 ASCII 字符，禁止 URL/路径及冒号分隔歧义。时间必须有时区并规范化为 UTC，快照有效期最多 300 秒。

`StudyEvent` 为 `mygpt.study-event.v1`，序号从 1 开始逐一递增，上限为 JavaScript 安全整数；布尔、浮点数及字符串序号被拒绝。所有契约拒绝额外字段。输入只承认 `book-demo` 和 `SIMULATED`，不把任意调用者自报来源当作 Book 身份认证。

| 事件 | 必须携带新快照 | 效果 |
| --- | --- | --- |
| SESSION_STARTED | 是 | 创建唯一新会话；迟到旧会话不能盖过较新的活动会话 |
| CONTEXT_CHANGED | 是 | 切换章节/模式，课程/书籍/版本不能跨会话混用 |
| SESSION_PAUSED | 否 | 暂停，清空活动上下文 |
| SESSION_RESUMED | 是 | 仅从暂停/断开恢复，必须重新给出有效快照 |
| SESSION_ENDED | 否 | 结束，禁止以同一会话 ID 重启 |
| DISCONNECTED | 否 | 断开并清空上下文 |
| QUIET_REQUESTED | 否 | 本会话安静标记持续有效；显式求助仍可使用 |
| HELP_REQUESTED | 否 | 仅有效活动上下文下提出 explain |
| RECALL_REQUESTED | 否 | 仅有效活动上下文下提出 recall_check |

同一事件 ID 与内容重复时返回静默收据，不再次派发提案；ID 相同内容不同为冲突。乱序拒绝；序号缺口会使上下文失效、状态变为 disconnected，但不消耗未接收的序号。恢复时需要生产方协调，以最后接受序号 + 1 提交明确的 SESSION_RESUMED，或创建新会话。**不能把原始生产流的序号任意重写后继续**；真实 Book 适配器必须设计自己的重同步协议。

过期/缺失上下文显示 blocked，不猜测用户正在看的章节。静止、停留时间、离开页面都不被解释成分心。本版本根本不产生自动催促。

## 持久化与可靠性边界

`Brain(path)` 使用 SQLite WAL 和 `BEGIN IMMEDIATE`；接受的事件元数据、决策和当前投影同一事务提交。`Brain()` 使用内存数据库。支持重开后去重与安静标记恢复；测试覆盖两个已初始化实例并发提交同一事件、事务失败回滚。初次数据库初始化仍应由单个所有者执行；这不是分布式数据库或多用户服务。

未知数据库版本/非空未识别数据库拒绝自动迁移。只存来源引用、哈希、时间和决策，不存教材正文/问题正文/私人聊天。`recent_decisions` 最多返回 50 条已接受事件；拒绝事件与序号缺口失效当前通过返回收据观察，尚无持久的拒绝审计表。

去重保证的是本地提案不会重复发出，**不是外部操作 exactly-once**。进程若在提交后、消费收据前退出，提案可能未交付；未来执行层需要 outbox、交付确认及取消/重试协议。本版不执行任何外部动作。

## 来源校验与可选接口

`EvidenceText` 检查 UTF-8 正文 SHA-256，且使用时要求与当前完整快照相同。`GroundedReply` 的引用必须精确匹配这份来源。校验引用正确不等于答案论述正确；本版不声称验证了教学质量。

`run_test_model` 仅构造 Pydantic AI 的程序式 TestModel，返回 `[SIMULATED]` 固定内容；不接受真实模型选择。`make_mcp_server` 使用官方 MCP v2 的 MCPServer，导出三个只读工具：`get_study_status / get_current_context / get_recent_decisions`。工厂不监听端口、不建立外部连接、不导出写工具。跨进程/HTTP 发布前必须另做认证、授权、资源限额及安全测试；不能直接暴露到公网。

## 当前验收与下一步

本地核心/来源/演示测试通过；SDK 集成、远端 CI、独立审阅、真实 Book 事件来源、Jonah 联动及 Android 实机均未验收。精确测试记录在相邻 GitHub checkpoint 和 Drive 归档证据中。

下一步先补齐无付费调用的 SDK 集成验证，再读取 Book 实际接口/版本并形成字段映射与双向契约。此批次没有修改 Book、StudyMate、其他项目、现有 UI、工作流、安全策略或既有 PR。

## 采用依据

- Pydantic AI v2.46.0 官方 release：https://github.com/pydantic/pydantic-ai/releases/tag/v2.46.0
- TestModel 官方 API：https://pydantic.dev/docs/ai/api/models/test/
- MCP Python SDK v2.2.0 官方 release：https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0
- MCPServer / Client 官方入门：https://py.sdk.modelcontextprotocol.io/get-started/

本轮只核验官方发布和公开 API 文档，没有系统研究第三方源码、复制上游源码或下载完整源码快照。后续源码级研究按全项目固定版本/许可证/Drive 快照规则执行。未把旧聊天中的宣传性比较、星数或未复测能力作为验收结论。
