# Handoff · verified source checkpoint and local candidate

<!-- governance-checkpoint {"repository":"Jvust1/mygpt","branch":"fix/dependency-locks-dot-20261002","tested_commit":"68ea57e1aec5488b6ff24973f7ef2b781ca29bff","pr":61,"run_id":36973557038} -->

最后已验证源码 checkpoint：[Draft PR #61](https://github.com/Jvust1/mygpt/pull/61)，分支 `fix/dependency-locks-dot-20261002`，
提交 `68ea57e1aec5488b6ff24973f7ef2b781ca29bff`；[run 36973557038](https://github.com/Jvust1/mygpt/actions/runs/36973557038) 9 个 job 全部成功。
这是已验证输入源码的记录；本次文档/校验器 checkout 的身份和新 CI 必须另外取得，不能继承这次绿灯。

本次新的公开恢复 artifact 仅为 source-recovery-evidence 中的 JSON/hash 摘要，不含完整源码 ZIP 或原始日志。完整 build/恢复验收仍执行，但旧源码树含历史私有引用，暂不重新公开整包；#61 的 source ID/hash 只是历史验证记录，不能当成本次可下载源码交付。完整包仅可通过另行批准的私有交付取得。

## 接手顺序

1. 按 AGENTS 完成已授权项目基线核对，并读 North Star、Architecture Invariants、Decision/Evaluation ledger；旧评估仅适用其标注的历史提交，当前评估见本次治理检查点，离线校验不冒充新远端查询
2. 读取 project_state、artifact_manifest、pending_sync 与 [当前状态](CURRENT_STATE.md)；当前 branch/PR 字段指最后已验证 checkpoint
3. 用 `python scripts/validate_governance.py` 检查当前文件一致性，并查看输出的 checkout_identity。无 .git 时用 SOURCE_MANIFEST 报告恢复输入，绝不猜 HEAD
4. [START_HERE](../START_HERE.md) 保留最短启动/恢复命令；schema 2 升级前停旧进程、私有备份，禁止 mixed-version/原地降级
5. 任何后续代码提交都要重新建立 exact-head CI；本次治理/校验器不继承 #61 hosted PASS

## 已知成功与未验收

#61 hosted 九个 job 成功，含实际 Android host build、Java 8/17、源码恢复、Windows EXE/Edge。
Linux 85 包 / Windows 54 包 Python 完整锁原生安装报告与 installed set 验证通过；锁工具66 tests零跳过。Android/Node/browser/toolchain 尚未全锁，不宣称bit-identical。
完整计数和 artifact hash 在 [治理检查点](GOVERNANCE_CHECKPOINT_20261002.md)。
Windows evidence 仅有 17 份合成资料；EXE/APK/个人数据库未发布。Artifacts 保留 3 天。

仍缺用户设备、Companion V2/llama/sherpa 独立整链证据、真实 Book 采用/签名、模型质量/性能、麦克风/可听 TTS、角色/PiP 真机体验。
回执存储只是无损改善，完整 ID 输出/累计 CPU、旧 receipt 体积、nondurable、retention 仍有边界；没有真实用户 DB 迁移。

## 允许推进的技术下一步

审阅本次治理和独立依赖锁修复，运行本地回归，按批准范围另建 Draft 并取得新 run。
本次不决定 main/branch protection、仓库许可、Spine 分发、retention、联系邮箱或 SLA。
Book/StudyMate/Live/ChatContextVault 仍是独立权威源，不能机械重写它们的 owner。

原接手历史仍在不可变 Git 历史和私有原始包；[HISTORICAL 索引](HISTORICAL_GOVERNANCE_LEDGER_20261002.md)仅列公开 commit/path/bytes/SHA，旧 “current/latest” 不作为当前指令。
