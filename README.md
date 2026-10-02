# mygpt

Android 学习陪伴与编排层：Book 提供学习内容与语义上下文，Live 提供角色表现，mygpt 负责对话、记忆和陪伴决策。

## 当前入口

<!-- governance-checkpoint {"repository":"Jvust1/mygpt","branch":"fix/dependency-locks-dot-20261002","tested_commit":"68ea57e1aec5488b6ff24973f7ef2b781ca29bff","pr":61,"run_id":36973557038} -->

最后已验证源码 checkpoint：[Draft PR #61](https://github.com/Jvust1/mygpt/pull/61)，分支 `fix/dependency-locks-dot-20261002`，
提交 `68ea57e1aec5488b6ff24973f7ef2b781ca29bff`；[run 36973557038](https://github.com/Jvust1/mygpt/actions/runs/36973557038) 9 个 job 全部成功。
这是已验证输入源码的记录；本次文档/校验器 checkout 的身份和新 CI 必须另外取得，不能继承这次绿灯。

本次新的公开恢复 artifact 仅为 source-recovery-evidence 中的 JSON/hash 摘要，不含完整源码 ZIP 或原始日志。完整 build/恢复验收仍执行，但旧源码树含历史私有引用，暂不重新公开整包；#61 的 source ID/hash 只是历史验证记录，不能当成本次可下载源码交付。完整包仅可通过另行批准的私有交付取得。

main 仍是治理骨架；审阅栈仍未合并。源码候选不是已验收成品，也不是可公开分发的 APK/EXE。

- [当前状态与未验收门槛](docs/CURRENT_STATE.md)
- [最短启动、私有备份与恢复](START_HERE.md)
- [接手顺序](docs/HANDOFF.md)；[精确证据与治理校验](docs/GOVERNANCE_CHECKPOINT_20261002.md)
- [机器状态](governance/project_state.json)；[成果身份](governance/artifact_manifest.json)

## 已验证的边界

- 严格 Python 912、上游/组合 49、根目录 Python 103、JavaScript 70；套件有重叠，不相加
- Android host 实际构建、Java 8/17 与源码恢复通过；不代表 Companion V2/llama/sherpa 或真机全链验收
- Hosted Windows 31 tests + 147 subtests、5 native EXE checks、23 Edge checks；合成资料，0 外部浏览器请求、0 真实模型调用
- Windows artifact 仅含 17 份合成证据，不含 EXE/APK/个人数据库

## 当前仍需完成

用户 Windows/小米 14、真实 Book 签名及 SDK 接入、本机模型质量/性能、麦克风、可听 TTS 与角色/PiP 体验尚未验收。
回执磁盘增长已改善，但完整 ID 输出为 O(history)、累计 CPU 近二次；旧回执不缩小、nondurable 无界、无 TTL 清理。
不自动删除历史，也不自动写长期记忆；本轮未迁移真实用户数据库。

仓库整体许可未选定，Spine APK 分发许可未确认，Linux 85 包 / Windows 54 包 Python 哈希锁已原生安装验证；Android、Node、浏览器及工具链仍未全锁，不宣称 bit-identical。
main/分支保护、retention、安全联系人/SLA 都不由本次技术治理变更决定。

## 开发检查

```sh
python scripts/validate_governance.py
python -m unittest discover -s tests -p 'test_*.py' -v
```

严格 Brain/上游命令和实际测试环境见 [检查点](docs/GOVERNANCE_CHECKPOINT_20261002.md)。
[贡献指南](CONTRIBUTING.md)、[安全报告边界](SECURITY.md)、[应用边界](SECURITY_POLICY.md)继续适用。
[HISTORICAL 索引](docs/HISTORICAL_GOVERNANCE_LEDGER_20261002.md)只登记旧文件的公开不可变 GitHub commit/path/bytes/SHA；原文留在旧 Git 历史与私有原始包，不在此重新发布。
