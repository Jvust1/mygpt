# mygpt

Android 学习陪伴与编排层：Book 提供学习内容与语义上下文，Live 提供角色表现，mygpt 负责对话、记忆和陪伴决策。

## 当前候选：面向 main 的统一审阅快照

这是未合并的 Draft 候选，不是已交付的 Android 应用。它把已审阅的实现栈整理到一棵可复现的源码树，同时保留当前 main 的贡献指南、安全策略、忽略规则和基础 CI。

- 实现来源：[PR #55](https://github.com/Jvust1/mygpt/pull/55)，`1eac69dc03548b5c6926fc5c7eb23d98d55853e5`
- main 基线：`bb35f6d34e05ed1de7ac8b3ef71c76f0cbe9f258`；本候选不修改 main，也不合并原有 PR
- [统一范围、复现与审阅说明](docs/FUSION_MAIN_REVIEW_20261001.md)
- [当前状态](docs/CURRENT_STATE.md)、[交接](docs/HANDOFF.md)、[机器可读状态](governance/project_state.json)

## 已接入的完整路径

- 显式输入 → 命名空间内词法记忆 → 受限提示 → 本机 Ollama 适配器 → AIRI 文本/情绪解析 → SQLite 历史与重试回执
- Pipecat 转录 → 回复帧/TTS 队列 → 中断与过期输出抑制；测试中的模型回复、ASR 和音频合成为合成数据
- Book 短期语义上下文 → 长度预算与新鲜度检查；Book 正文不写入聊天/长期记忆
- Android 共享 Java 路径：Gson 严格解析、AIRI 历史预算、词法记忆评分、Unicode 边界和过期 TTS 回调所有权
- 显式记忆增改删/审计、重启回执恢复、CLI 输入错误恢复，以及受限的本机 HTTP 请求生命周期

### 本轮直接融合/调用的成熟项目

GitHub 数据核对：2026-10-01 02:16 UTC。完整固定版本、修改说明与原始许可保留在对应 `third_party` 目录和 Android 资产中。

| 上游 | 核对星数 | 许可 | 实际路径 |
| --- | ---: | --- | --- |
| [AIRI](https://github.com/moeru-ai/airi) | 49,896 | MIT | ACT 情绪/文本分离与成组历史 |
| [Pipecat](https://github.com/pipecat-ai/pipecat) | 16,101 | BSD-2-Clause | 实际帧队列、TTS 收尾、中断与语音文本 |
| [ollama-python](https://github.com/ollama/ollama-python) | 10,562 | MIT | 可取消的本机异步 HTTP 生命周期 |
| [scikit-learn](https://github.com/scikit-learn/scikit-learn) | 67,435 | BSD-3-Clause | Python/Java 词法 TF-IDF 检索及实际上游数值对照 |
| [Gson](https://github.com/google/gson) | 24,236 | Apache-2.0 | Android 回复路径中的严格 JSON 解码 |

其他既有组件不因此被算作本轮新增上游。例如可选 openWakeWord 适配器只是加固了原有置信度边界，没有新增 SDK、模型或源代码导入。

## 验证与运行

[实现来源的精确提交 CI](https://github.com/Jvust1/mygpt/actions/runs/36804686015) 已通过：826 项严格 Python、49 项实际上游/兼容性/组合测试、65 项根目录 Python、66 项 JavaScript，以及 Java 8/17 各 22 个入口。该证据属于实现来源提交；统一快照自己的最终 CI 与源码哈希记录在对应 PR 中。

已验证的锁文件环境是 Ubuntu 24.04 x86_64 / Python 3.13，不是通用 Windows/Android 锁文件。以下验证不调用真实模型：

```bash
cd brain
python -m pip install --only-binary=:all: --require-hashes -r requirements-linux-py313.lock
python -m pip install '.[realtime,lexical-test]'
python scripts/verify_integrations.py --output ../test-output/core-new
python scripts/verify_fusion_upstreams.py --output ../test-output/upstream-new
```

输出目录必须是新的。Java 边界、源码恢复和设备路线见 [统一审阅说明](docs/FUSION_MAIN_REVIEW_20261001.md) 与 [START_HERE.md](START_HERE.md)。

如果已经自行安装并选择了本机聊天模型，可以显式运行开发者 CLI；请替换占位模型名，程序不会下载模型：

```bash
python scripts/chat_local_ollama.py --model "YOUR_INSTALLED_CHAT_MODEL"
```

长期记忆仅由显式命令写入。`:forget` 删除活动记忆但保留审计；它不是彻底清除。默认数据目录已由 `.gitignore` 排除；选择其他数据目录时也不得把私有数据提交到 Git。

## 尚未完成的验收

- Android Activity/Kotlin/APK/JNI、Windows 与 Xiaomi 14 真机
- 真实 Book 签名/接入、真实本机模型质量与性能
- 麦克风、真实唤醒模型、可听 TTS 与角色视觉连续性
- 物理音频的 exactly-once 播放；回执只能证明数据恢复

不应把 Java 边界测试或合成模型/音频测试称为整机验收。源码包不含模型、私有皮肤、录音、个人聊天数据库、凭据或外部 Gitlink 源码，也不是离线依赖齐全的安装包。

## 开发与安全约定

- 使用清晰、可维护的目录结构组织代码
- API 密钥等敏感信息只通过环境变量提供，不提交私有数据或本地配置
- 新功能应补充可运行示例和测试
- 提交使用明确的动词前缀，例如 `feat:`、`fix:`、`docs:`
- 贡献流程：[CONTRIBUTING.md](CONTRIBUTING.md)；安全问题：[SECURITY.md](SECURITY.md)；应用边界：[SECURITY_POLICY.md](SECURITY_POLICY.md)

仓库整体授权尚未选定；第三方组件仍受各自 LICENSE/NOTICE 约束。本检查点不替代许可审查。

旧版 [main 初始化 README](docs/README_MAIN_BASELINE_20261001.md) 和 [功能分支 README](docs/README_FEATURE_HISTORY_20261001.md) 原文保留为历史记录，不代表当前验收状态。
