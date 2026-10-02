# mygpt · 启动、恢复与升级

<!-- governance-checkpoint {"repository":"Jvust1/mygpt","branch":"fix/dependency-locks-dot-20261002","tested_commit":"68ea57e1aec5488b6ff24973f7ef2b781ca29bff","pr":61,"run_id":36973557038} -->

最后已验证源码 checkpoint：[Draft PR #61](https://github.com/Jvust1/mygpt/pull/61)，分支 `fix/dependency-locks-dot-20261002`，
提交 `68ea57e1aec5488b6ff24973f7ef2b781ca29bff`；[run 36973557038](https://github.com/Jvust1/mygpt/actions/runs/36973557038) 9 个 job 全部成功。
这是已验证输入源码的记录；本次文档/校验器 checkout 的身份和新 CI 必须另外取得，不能继承这次绿灯。

本次新的公开恢复 artifact 仅为 source-recovery-evidence 中的 JSON/hash 摘要，不含完整源码 ZIP 或原始日志。完整 build/恢复验收仍执行，但旧源码树含历史私有引用，暂不重新公开整包；#61 的 source ID/hash 只是历史验证记录，不能当成本次可下载源码交付。完整包仅可通过另行批准的私有交付取得。

## 先保证数据安全

源码 ZIP、依赖、模型和私有皮肤是不同输入。源码包不包含离线依赖、外部 Gitlink 源码、模型或用户数据库。
恢复到新的目录，先比对可信外部 SHA-256；内部 SOURCE_MANIFEST 不是签名。
升级 schema 2 前先停止全部旧进程，并在本机私有位置备份完整旧数据目录；不要上传数据库。
禁止新旧进程混用同一数据库，也不要原地降级。旧回执保持原字节，本轮没有迁移真实用户数据。

```sh
python scripts/source_bundle.py verify /path/to/mygpt-source.zip --sha256 9e77a8f3f315f3a5abfc53d410f93721de857a3fc6a86964423ce0870b4c4949
```

上述哈希只属于 #61 的 472 源文件输入包，另有一个 SOURCE_MANIFEST 成员；本次修改后的源码需另行打包和验证。

## 最短本地合成演示

在新源码根目录创建独立环境。正式基线为 Linux CPython 3.13 x86_64；安装是使用者显式网络操作，启动器不会安装或下载模型。

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: --require-hashes -r brain/requirements-linux-py313.lock
.venv/bin/python run_mygpt.py doctor
.venv/bin/python run_mygpt.py start
```

在同一电脑打开控制台打印的 `http://127.0.0.1:<port>/host/brain.html`。TestModel 返回固定确认回复，不是真实模型讲解。
要明确开启本次的一条内容输入，改用 `run_mygpt.py start --enable-selection-intake`，再打开 `/host/selection.html`；必须预览、同意后才发送到本机。
内容标为 USER_SUPPLIED_UNVERIFIED，不能冒充真实 Book；授权过期/撤销后重新显式启动。Ctrl+C 停止。
数学预览已有 pinned KaTeX/MathML 与原始 LaTeX fallback；不保证数学正确性。

Windows PowerShell 的合成开发演示：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\brain[test,integrations]"
.\.venv\Scripts\python.exe run_mygpt.py doctor
.\.venv\Scripts\python.exe run_mygpt.py start
```

Hosted Windows #61 的 EXE/Edge 与原生 Python 哈希锁安装均已通过；上面的简短开发安装命令本身不是该完整锁流程，也不是用户设备验收。完整 Linux/Windows 锁流程见 #61 源码中的 docs/PYTHON_DEPENDENCY_LOCKS_20261002.md；勿将其 cross-target 生成报告冒充 native 安装证据。
不要将 Linux wheel 锁用于 Windows/macOS/Android。doctor READY 不是所有平台/功能通过。

已有自己选定并安装的 Ollama 聊天模型时，开发者可显式执行 `python brain/scripts/chat_local_ollama.py --model YOUR_INSTALLED_CHAT_MODEL`。
该路径的真实模型质量仍未验收；长期记忆只接受显式命令，`:forget` 删除活动记忆但保留审计，并非彻底清除。

## 故障与下一步

缺文件先恢复完整包，缺依赖在独立环境修复，不移除版本限制。loopback 只用于同一台电脑；手机的 127.0.0.1 不是电脑，不自动建隧道或开放防火墙。
Android/真机路线见 [Companion V2 验收](docs/COMPANION_V2_XIAOMI14_ACCEPTANCE.md)，执行前仍须确认设备、私有输入及许可权限。
当前状态与证据：[CURRENT_STATE](docs/CURRENT_STATE.md)、[检查点](docs/GOVERNANCE_CHECKPOINT_20261002.md)。
旧启动说明的公开不可变来源与 bytes/SHA 见 [HISTORICAL 索引](docs/HISTORICAL_GOVERNANCE_LEDGER_20261002.md)；索引不含原文。
