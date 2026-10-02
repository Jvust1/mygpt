# Book Context Brain · 2026-09-22 checkpoint

状态：CORE_TESTS_PASS / SDK_INTEGRATION_BLOCKED / REVIEW_PENDING。

## 发布身份

- 仓库：Jvust2/mygpt。
- 当前候选分支：feat/book-context-brain-20260922。
- PR：[草稿 PR #5](https://github.com/Jvust2/mygpt/pull/5)，叠加在未合并 PR #3 上；#1–#4 不变。
- 基线：a8595c3ccaddcff5a6a95f8a37a963707f48c084。
- 实现 commit：68c351b85511ccdd625036a6917b4303646b6704。
- 实现 tree：923db3a1e689d6c0d20f12226d5a15346ed3fe94。
- 本实现 commit 仅新增 brain/ 的 10 个文件。GitHub 回读的 10 个 Git blob SHA 与本地测试源码逐一相同；原有子树保持不变。

## D016 — 本轮设计决定

保留 Jonah，不为引入框架重写宠物。第一批采用 Pydantic 强类型契约、Python 明确状态转移和 SQLite 事务；不同时加入 LangGraph、Letta、Mem0 或 Graphiti。Pydantic AI 仅保留 TestModel 接线候选，官方 MCP v2 仅保留不启动网络的只读工厂。

模型提案不等于执行。当前没有外部任务执行器，因此去重只保证收据不重复派发；未来要执行真实动作时必须增加 outbox、取消、结果确认和外部幂等。引用校验只验证身份，不证明回答语义正确。

Book 接口字段尚未实际联调；只接受 SIMULATED/book-demo，避免把合成输入伪装成生产 Book 数据。MCP 不是高频事件广播总线，生产事件入口及鉴权仍单独设计。没有隐式付费 provider、私信读取、视觉采集或跨 App 控制。

## E004 — 实际验收

环境：Python 3.13.5、Pydantic 2.13.4、pytest 9.0.2、pytest-asyncio 1.3.0。

- 初期核心：73 passed。
- 最终源码第一次：95 passed、2 skipped、0 failed，0.20s。
- 同一源码复跑：95 passed、2 skipped、0 failed，0.15s。
- `python -m mygpt_brain` 实际输出八条模拟结果；两次输出字节相同。
- `python -m compileall -q mygpt_brain tests` 通过。

覆盖：字段/版本/时间拒绝、UTC 等价去重、重复求助十次不重发、ID 冲突、乱序/缺口失效、跨书隔离、延迟旧会话阻止、暂停/恢复/结束、过期后持续 blocked、安静模式、文件数据库恢复、两个已初始化实例并发同一事件只接受一次、事务插入失败回滚、未知数据库保护、来源哈希与伪造引用拒绝。

两项 SKIPPED 是可选 SDK 未安装。沙盒 DNS 阻断依赖下载，不能宣称 Pydantic AI/MCP 运行成功。无独立审阅；无远端 CI；没有复跑旧 UI 测试。以上全为本地合成/回归结果，不是实机、不是真实学习实验、不证明教学质量。

## Drive 归档

[Brain 源码与原始测试证据包](https://drive.google.com/file/d/13YcH0j9VXd20LLWspZzDquRm-pe02OSJ/view)。

- 父目录：mygpt/02_Generated_Artifacts，ID 1aVb6MQTme7UAGhlcJ4V-Hgac8BhR3ouV。
- 名称：mygpt-brain-context-v0.1-20260922.zip。
- 大小：33,433 bytes；28 个成员。
- SHA-256：bf74c74dd2dd70cb6a8d99e62a76db3bbdd1a06d147dc42daeef99d1a3eddadb。
- 已核对元数据并下载回读，字节 SHA-256 与本地原包相同。
- 包含源码、说明、原始测试输出、演示、6 份导出 Schema、逐文件身份清单。不是完整 mygpt 快照，不重复上传 Jonah 图集，也不包含虚拟环境/缓存/第三方源码/私人数据。

## 仍未完成

SDK 实际兼容性及无付费集成测试、真实 Book 字段/源版本映射与鉴权、Jonah 桥、Android 宿主与真机、外部执行 outbox、独立代码审阅均待完成。初次建库由单一所有者运行；拒绝收据暂未持久审计。详细运行命令及边界见 [Brain README](../brain/README.md)。

## 唯一下一步

在已授权且能够安装依赖的环境完成 TestModel 与 MCP 内存客户端测试，保留失败证据并补齐传递依赖锁；通过后才推进 Book 真实接口映射。不得为绕过当前环境限制自动购买算力、调用付费模型或扩大权限。

## 同步口径

本轮 GitHub 预计最终为 11 NEW、4 CHANGED、22 SKIP_IDENTICAL；以最后一次远端 diff 回读为准。CHANGED 仅 project_state、artifact manifest、Current State 和 Handoff；两个旧文档保留原始正文，并前置最新恢复指针。旧决策/验收 ledger 原样保留，本检查点作为新条目由 project_state 索引。

Drive NEW=1、原位更新=0；原 Jonah archive 保留但未重新上传。没有删除、强推、main 写入或 PR 合并。本地源码测试与远端 blob 身份已验证，发布后的状态文档仍需按写后流程回读。
