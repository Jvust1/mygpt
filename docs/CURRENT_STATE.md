# Current state · 2026-10-02

<!-- governance-checkpoint {"repository":"Jvust1/mygpt","branch":"fix/dependency-locks-dot-20261002","tested_commit":"68ea57e1aec5488b6ff24973f7ef2b781ca29bff","pr":61,"run_id":36973557038} -->

最后已验证源码 checkpoint：[Draft PR #61](https://github.com/Jvust1/mygpt/pull/61)，分支 `fix/dependency-locks-dot-20261002`，
提交 `68ea57e1aec5488b6ff24973f7ef2b781ca29bff`；[run 36973557038](https://github.com/Jvust1/mygpt/actions/runs/36973557038) 9 个 job 全部成功。
这是已验证输入源码的记录；本次文档/校验器 checkout 的身份和新 CI 必须另外取得，不能继承这次绿灯。

本次新的公开恢复 artifact 仅为 source-recovery-evidence 中的 JSON/hash 摘要，不含完整源码 ZIP 或原始日志。完整 build/恢复验收仍执行，但旧源码树含历史私有引用，暂不重新公开整包；#61 的 source ID/hash 只是历史验证记录，不能当成本次可下载源码交付。完整包仅可通过另行批准的私有交付取得。

## 验证结论与范围

- Strict Python 912 / upstream 49 / root Python 103 / JavaScript 70；失败与跳过均为 0，重叠套件不相加
- Android host 实际构建、Java 8/17、source recovery 成功
- Windows 31 tests + 147 subtests；5 EXE、23 Edge checks；0 外部浏览器请求、0 live model calls
- Native evidence 17 files，仅合成证据；没有公开 EXE/APK/个人数据库
- #58 的 Android required gate 与 #59 的无损回执改进已包含在这个源码 checkpoint

Linux 85 包 / Windows 54 包的原生 name/version/hash 安装报告与完整 installed set 已精确通过，锁工具66 tests零跳过；006仅部分关闭，不宣称bit-identical。

GitHub Actions artifacts 保留 3 天。完整 source/artifact SHA、恢复口径和验证命令见 [检查点](GOVERNANCE_CHECKPOINT_20261002.md)。

## 保留的阻塞

1. Hosted Windows 成功不等于用户 Windows 或 Xiaomi 14 通过
2. Android host 构建不代替 Companion V2/llama/sherpa APK/JNI、真实模型/音频/皮肤/PiP 验收
3. Book SDK 实际采用和真实 APK 签名未确认；模型质量/性能及默认 GGUF 由设备与人工决定
4. 回执完整 ID 输出 O(history)、累计 CPU 近二次，旧回执不缩小，nondurable 无界，尚无 TTL/自动清理
5. 许可/Spine 分发、main/分支保护、Android/Node/browser/toolchain 锁、retention、安全联系人/SLA 仍有独立门槛

main 仍是骨架，所有相关 PR 未合并。没有迁移真实用户数据库或删除历史。
Jonah 旧 49-check browser 结果保留为历史，不冒充 #61 新的独立 UI 验收。

## 下一步

先审阅本次治理变更和独立依赖修复；任何新发布代码必须获得新 exact-head CI。
数据升级先停止旧进程并保留私有完整备份，禁止 mixed-version 与原地降级。
随后按明确授权安排真实设备/Book/模型验收；不自动 merge、公开分发或替用户设定策略。

[启动](../START_HERE.md) · [交接](HANDOFF.md) · [机器状态](../governance/project_state.json)

八份旧文件的公开不可变 commit/path/bytes/SHA 登记在 [HISTORICAL 索引](HISTORICAL_GOVERNANCE_LEDGER_20261002.md)，
原文仍留在旧 Git 历史和私有原始包；索引不重新刊登原文或私有引用。旧审计报告保持不变，它审的是 #48 输入。
