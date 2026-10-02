# mygpt 再审计报告

- 审计日期：2026-10-02（UTC；按用户时区为 2026-10-02）
- 审计对象：`Jvust1/mygpt`
- 审计范围：默认分支 `main`、当前最完整候选分支 `chore/fusion-checkpoint-dot-20261001`、Brain/HTTP/SQLite/Provider 代码、Android/Windows CI、源码恢复链、治理文件和 Drive 项目基线
- 默认分支审计基线：`bb35f6d34e05ed1de7ac8b3ef71c76f0cbe9f258`
- 候选分支审计基线：`1e766c00d7ccb857d7d5a858e7af776f66b611df`
- 最新候选聚合验收：Actions run `36795208892`
- 结论状态：**BLOCKED_FOR_RELEASE**
- P0：0；P1：4；P2：6；P3：1

> 本报告只评估仓库证据能够证明的事实。合成模型、Java 边界、源码恢复和静态安全控制通过，不能替代真实 Android APK、真实设备、真实 Book APK、真实模型、麦克风和 TTS 验收。

## 一、执行摘要

当前仓库存在两个不同的现实：

1. `main` 仍是初始化/治理骨架，只包含基础 README、贡献说明、安全说明、忽略文件和一个基础验证工作流，没有 Brain、Android、桌面或测试实现。因此从 `main` 克隆出来的内容不是可运行的 mygpt 产品。
2. `chore/fusion-checkpoint-dot-20261001` 已经形成了一个规模较大的候选实现，包含 Brain、Loopback Companion Service、Ollama provider、Book bridge、SQLite session/memory、Android spike、Windows 交付脚本和源码恢复链。该候选的 Linux/Node/Java 边界/源码恢复检查较完整，但仍不能作为发布版本。

候选分支的最新聚合 run 显示：

- Brain 严格验收：724 passed；
- 上游/集成故事：48 passed；
- Python 根测试：65 tests；
- Node：66 pass；
- Java 8/17 边界：均成功；
- 源码包：428 个文件，确定性重复构建通过；
- **Android APK/Gradle host job 被 skipped**；
- 未证明真实 Android APK、Native payload、真实设备、Windows 当前候选分支、真实 Book APK、真实 LLM、真实麦克风和可听 TTS。

因此，当前最准确的产品定位是：**安全边界和本地编排能力较完整的工程原型/审查候选，不是可发布产品**。

## 二、范围与方法

本轮执行了以下检查：

- 对 `main` 和候选分支分别检查树、提交、默认分支、分支保护、Actions job 和 job log；
- 静态阅读 `brain/mygpt_brain` 核心模块、Android Manifest/receiver、第三方 notice、打包脚本和工作流；
- 检查 `AGENTS.md`、North Star、Architecture Invariants、Current State、Decision/Evaluation Ledger、Handoff、project state、artifact manifest 和 pending sync；
- 读取 Google Drive 根入口及所有 `全项目_*` 基线；基线明确 GitHub 是项目状态权威，Drive 是大文件和归档保险库；
- 本地运行 Node 测试和 Python 编译检查；
- 用合成 responder 对长期聊天运行做了 400 轮复现，观察内存、请求缓存和 SQLite 回执增长；
- 对候选工作流的安装命令、触发分支、仓库条件和是否存在 skipped job 做了交叉核对。

本地环境不是 CI 的正式 Python 3.13 锁定环境：本地 Python 3.12 缺少精确的 `pydantic-ai-slim==2.46.0`，所以完整 Python 回归不能据此判定候选 CI 失败。Node 66 pass、Python compileall pass；正式 Python 结果以候选 Actions run 为准。

## 三、基线对比

| 项目 | `main` | 候选分支 |
|---|---|---|
| 提交 | `bb35f6d` | `1e766c0` |
| 内容规模 | 7 个 tracked entries | 430 个 tracked files |
| Brain/Android/桌面实现 | 不存在 | 存在 |
| 默认 README | 初始化说明 | 仍残留多个历史检查点 |
| CI | 只做基础文件/常见敏感文件检查 | 多条候选验收链 |
| APK/Gradle host | 不适用 | job 被 skipped |
| 分支保护 | `protected=false` | main 保护仍关闭 |
| 发布判断 | 不可发布 | 仍被阻断 |

## 四、问题清单

### MYGPT-001 · P1 · Android APK/Gradle 构建门被仓库名拼写错误静默跳过

**证据**

`.github/workflows/android-spike.yml` 中：

- Java 8/17 job 使用 `github.repository == 'Jvust1/mygpt'`；
- `android-debug-host` 使用 `github.repository == 'Jvust/mygpt'`。

实际仓库是 `Jvust1/mygpt`。最新聚合 run `36795208892` 的 job 结果为：

- Java 8：success；
- Java 17：success；
- source recovery：success；
- production components：success；
- **android-debug-host：skipped**。

被跳过的 job 本来负责：

- 检查 Android SDK；
- 执行 `gradle -p android_spike :app:assembleDebug`；
- 检查 APK 中的 `lib/arm64-v8a/libgdx.so`；
- 检查 `classes.dex`；
- 检查 Spine license notice；
- 上传 APK artifact。

所以当前绿色 run 没有证明 APK 可以构建，也没有证明 native payload 存在。

**风险**

验收状态会出现“全绿但关键构建没有执行”的假阳性。任何依赖该 run 判断 Android 可交付性的流程都会被误导。

**修复要求**

1. 将条件统一为 `Jvust1/mygpt`，最好改成仓库级常量或删除不必要的 owner 条件；
2. 在聚合 workflow 增加必需 job 断言，禁止关键 job 被 skipped；
3. 增加一个检查：若 `android-debug-host` 不是 `success`，聚合验收直接失败；
4. 修复后重新跑 exact-head，必须保留 APK artifact、APK 内部清单和日志。

**验收标准**

Android debug host 必须显示 `success`，且日志同时出现 `assembleDebug`、`classes.dex`、`lib/arm64-v8a/libgdx.so` 和 Spine license 检查结果。

---

### MYGPT-002 · P1 · 长期聊天运行时和 SQLite 回执无保留上限，产生近二次方增长

**证据**

核心代码：

- `brain/mygpt_brain/companion_chat.py` 的 `_sessions` 保存完整会话消息；
- `_requests` 保存全部 request result；
- `session_store.py` 的 `chat_request_receipts` 永久保存每个请求；
- `compacted_message_ids` 会在每次新回执中重复保存此前被裁剪的消息 ID；
- 没有默认 TTL、LRU、最大 session 行数、receipt GC 或压缩策略；
- 仅提供显式 `delete_session`，没有运行时自动保留策略。

我用相同 persona、固定合成 responder、`recent_turn_limit=2` 做了 400 轮复现：

| 轮数 | 送给 provider 的历史行数 | 运行时历史行数 | request cache | 最近回执裁剪 ID | 所有回执裁剪 ID 总数 | SQLite 回执 JSON 合计 |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 1 | 201 | 100 | 198 | 9,900 | 约 366 KB |
| 200 | 1 | 401 | 200 | 398 | 39,800 | 约 1.31 MB |
| 400 | 1 | 801 | 400 | 798 | 159,600 | 约 4.94 MB |

模型实际只收到一行历史，但进程仍保留全部消息；回执还重复写入越来越长的裁剪 ID 列表。真实部署持续聊天数达到几千或几万轮时，内存、SQLite 文件和回执读写成本会持续增长，最终影响稳定性。

**风险**

这是本地服务的长期可用性问题，可能造成内存和磁盘增长、启动恢复变慢，以及请求回执查询/序列化成本上升。它还会让“历史已裁剪”与“历史已删除”混淆：模型窗口被裁剪了，但本地存储没有生命周期管理。

**修复要求**

1. 明确产品保留策略：例如最近 N 个 session、每 session 最近 M 个完整 turn、receipt 保留 T 天；
2. 将 `compacted_message_ids` 改为增量摘要/计数/外部压缩记录，不能在每个 receipt 中重复复制全部历史 ID；
3. 对 `_requests` 增加 LRU/TTL 上限；
4. 对 SQLite 增加可审计的 retention/compaction migration，并在删除前导出必要审计摘要；
5. 对长会话、重启恢复和 GC 增加 1k/10k turn 测试；
6. 明确用户数据删除接口和默认关闭的自动上传边界。

**验收标准**

连续 10,000 个合成 turn 后：

- provider window 仍受限；
- 内存和 SQLite 增长接近线性且有明确上限；
- receipt 查询不包含重复的全量历史 ID；
- 重启后只恢复保留窗口和必要摘要；
- 删除 session 后消息、receipt、索引全部按策略清理。

---

### MYGPT-003 · P1 · 默认分支不是当前审查实现

**证据**

`main` 基线 `bb35f6d` 的递归树只有：

- `.github/workflows/validate.yml`
- `.gitignore`
- `CONTRIBUTING.md`
- `README.md`
- `SECURITY.md`

没有 `brain/`、`android_*/`、`desktop_*.py`、`tests/` 或候选治理目录。main 的 README 仍写着：

- 仓库处于初始化阶段；
- 后续再加入 LLM、对话、Prompt、流式输出；
- “No application implementation is yet claimed”。

候选实现则集中在未合并分支 `chore/fusion-checkpoint-dot-20261001`。

**风险**

任何从默认分支构建、发布、打包或交接的人得到的都是空壳初始化仓库。候选分支的绿色结果不会自动保护 main，也不会自动改变默认分支的发布内容。

**修复要求**

二选一，但必须明确写进治理：

1. 将候选实现以经过审查的 PR 合并到 main，并让 main 成为可恢复、可测试的产品基线；或
2. 明确 main 是治理/空壳分支，另设受保护的产品分支，并让 README、发布脚本、CI 和交接入口全部指向该分支。

不应继续让 README、project state 和 Actions 使用不同的“当前分支”。

**验收标准**

默认分支的 README、治理文件、CI、source recovery 和实际代码必须指向同一个已审查 commit；从默认分支 clean clone 后可以按文档完成最小 smoke。

---

### MYGPT-004 · P1 · 治理文件仍指向旧 owner、旧分支和旧 runner 状态

**证据**

候选分支的 `governance/project_state.json` 仍包含：

- `repository: "Jvust/mygpt"`，少了 owner 中的数字 `1`；
- `active_branch: "feat/airi-chat-memory-brain-20260929"`，不是当前候选分支；
- 状态仍写着 hosted Actions `runner_id=0`、zero steps、runner allocation blocked；
- 多个 blocking item 仍是旧 exact-head Windows/Xiaomi 14/旧设备阶段。

`governance/artifact_manifest.json` 也使用 `Jvust/mygpt`。`README.md` 仍从 2026-09-25 PR #8 开始，包含“尚未声明应用实现”的旧结论。 `CURRENT_STATE.md` 和 `HANDOFF.md` 顶部虽有新段落，但保留大量旧 head、旧 run、旧阻塞原因和旧“尚未执行”结论，接手者容易把历史记录当成当前状态。候选分支的 `SECURITY_POLICY.md` 还是历史占位文本。

**风险**

这不是单纯文档问题。项目规定“GitHub 是状态权威”，但机器可读状态自身与实际仓库身份/分支/CI 事实不一致，会导致后续 AI、CI、发布或归档选择错误的源头。

**修复要求**

1. 用当前仓库全名 `Jvust1/mygpt`、当前审查分支和 exact SHA 更新 project state/manifest；
2. 将旧状态移入明确标记为 `HISTORICAL` 的 ledger，不要与当前状态混排；
3. 每次 candidate checkpoint 自动生成 README、CURRENT_STATE、HANDOFF 和 project_state 的同一组 commit/SHA；
4. 加离线治理校验：owner、active branch、head、run ID、status、artifact manifest 必须互相一致；
5. 将 `SECURITY_POLICY.md` 替换为可执行安全政策，或删掉这个与根目录 `SECURITY.md` 冲突的历史占位文件。

**验收标准**

全仓库搜索旧 owner、旧 active branch、旧 runner blocker 后，剩余内容只能位于显式历史章节；当前状态读取后无需依赖聊天记录即可得到准确的分支、commit、CI 和下一步。

---

### MYGPT-005 · P2 · 当前聚合 gate 不包含 Windows 桌面交付

**证据**

`.github/workflows/desktop-delivery.yml` 只在：

`feat/desktop-delivery-20260925`

的 push 上触发，或人工 `workflow_dispatch`。当前候选 `chore/fusion-checkpoint-dot-20261001` 的聚合 workflow 没有调用它，也没有等价 Windows job。

桌面 workflow 才包含：

- Windows runner；
- PyInstaller 构建；
- Desktop HTTP/persistence tests；
- Playwright/Chromium；
- native executable、browser 和 restart 测试；
- boot diagnostics artifact。

**风险**

最新候选绿色 run 没有证明 Windows 交付链在当前 exact head 可构建或可启动。旧分支通过不能证明当前融合分支没有回归。

**修复要求**

1. 把 desktop job 纳入当前 candidate aggregate workflow；或让 desktop workflow 触发当前受审查分支；
2. desktop job 必须是 required check，不能 skipped；
3. 固定 exact `github.sha` checkout；
4. 将 Windows artifact 与 source commit、依赖清单、启动日志绑定。

**验收标准**

当前候选 exact head 在 Windows runner 上完成 core tests、PyInstaller/native smoke、browser/restart smoke，并上传可追溯 artifact。

---

### MYGPT-006 · P2 · 可复现依赖安装没有贯穿整个交付链

**证据**

`brain/requirements-linux-py313.lock` 声明：

- 只适用于 Linux x86_64 CPython 3.13；
- 使用 `--require-hashes`。

但 `companion-fusion-acceptance.yml` 先安装 hash lock，随后执行：

`python -m pip install '.[realtime,lexical-test]'`

这一步没有 `--require-hashes`，也没有完整 constraints/hashes 覆盖可选依赖。Windows desktop workflow 还执行：

- `pip install -e "./brain[integrations,test]"`
- `pip install pyinstaller==6.22.3 playwright==1.63.0`

同样没有完整 hash lock。desktop workflow 的 actions 仍使用 `@v4/@v5` 标签，而当前较新的 workflow 多数使用 commit SHA。

**风险**

版本号固定不等于完整依赖树可复现。可选依赖、transitive dependency、PyInstaller、Playwright 和 action tag 可能随时间改变，从而出现“同一 commit 不同环境不同结果”。

**修复要求**

1. 为 Linux、Windows、Android host 分别生成平台锁文件或 constraints；
2. 可选 extras 也通过 hash-pinned lock 安装；
3. 对 build tool、browser revision 和 GitHub Actions 统一 pin SHA/版本；
4. 保存 `pip freeze`、Python/Node/Java/Gradle/Android SDK 版本到 artifact；
5. 在 CI 增加 `pip check`、lock drift 和 unexpected dependency 检查。

**验收标准**

同一 commit 在干净 runner 上重复安装，依赖解析结果和 hashes 一致；不依赖未锁定的 transitive dependency。

---

### MYGPT-007 · P2 · 当前验收是合成/源码级验收，真实产品门仍未打开

**证据**

候选文档、`START_HERE.md`、`FUSION_RECOVERY_CHECKPOINT_20261001.md` 和 `governance/project_state.json` 都明确保留以下边界：

- TestModel/合成 provider，不是真实 LLM 教学质量；
- 没有真实 Book APK/AAR 签名匹配；
- 没有 Xiaomi 14 或其他真实 Android 设备验收；
- 没有真实 Android Activity/系统级 PiP/跨应用边界验收；
- 没有真实 GGUF 默认模型；
- 没有真实麦克风 ASR；
- 没有可听 TTS 播放；
- 源码包不包含模型、凭据、私有皮肤和外部 submodule 源码；
- llama.cpp 和 sherpa-onnx 只保留外部 commit identity，不等于已打包其源码或二进制。

这不是代码缺陷，而是当前 release gate 的边界。

**风险**

如果只看“724 passed / 48 passed / 66 pass”，容易误以为产品已达到真实使用标准。

**修复要求**

将发布状态明确标为 `prototype` 或 `review candidate`。真实发布前必须逐项建立 evidence：

- Android exact-head APK/Native payload；
- Xiaomi 14 安装、重启、PiP、热/内存；
- Book 真实签名和 AAR；
- 固定候选 GGUF 的性能和质量样本；
- live microphone ASR；
- audible TTS；
- Windows exact-head build；
- 独立审阅和人工体验确认。

---

### MYGPT-008 · P2 · 候选分支的安全政策不可执行，且与根目录策略不一致

**证据**

候选 `SECURITY_POLICY.md` 内容只有：

> This file is retained for repository history only.

默认分支 `SECURITY.md` 虽然说明不要在公开 Issue 发布密钥和敏感漏洞，并建议私下联系维护者，但没有：

- 明确安全联系地址或 GitHub Security Advisories 入口；
- 支持版本/受影响版本范围；
- 响应时限；
- 临时缓解和披露流程；
- 该候选分支的实际安全边界。

**风险**

公开仓库出现漏洞时，研究者没有可靠的私下报告路径；候选分支又保留一个同名语义相反的历史文件，交接者可能误以为安全政策已被废弃。

**修复要求**

保留一个权威 `SECURITY.md`，写明报告入口、响应流程、支持版本、敏感数据清理和披露规则；把历史文件移入 ledger 或删除。

---

### MYGPT-009 · P2 · main 分支无保护、无 required checks

**证据**

GitHub branch API 返回：

- `main.protected=false`
- required status checks enforcement：`off`
- rulesets：空列表。

**风险**

即使候选实现后来合并到 main，也没有仓库级机制防止未通过 CI、被 skipped 的关键检查或未经审阅的提交进入默认分支。

**修复要求**

在确定产品基线后：

1. 打开 main branch protection；
2. 要求 PR review；
3. 将 production、source recovery、Android APK host、desktop 和治理一致性检查设为 required；
4. 禁止 required job 以 skipped 满足合并条件；
5. 限制直接 push。

---

### MYGPT-010 · P2 · 源码恢复 artifact 的外部真实性与保留期仍是运维责任

**证据**

source recovery 在候选 run 中证明：

- 归档来自 exact commit；
- 两次构建字节一致；
- 428 个 tracked files；
- 外部 llama.cpp/sherpa-onnx 只保留 pinned commit identity；
- 归档不包含模型、凭据、个人数据和外部 submodule 源码。

同时，artifact retention 只有短期保留，外部 SHA-256 需要由 Drive/artifact manifest 或其他独立位置维护。内部 manifest hash 能检测损坏，但不能独立证明下载者拿到的是哪一个可信 artifact。

**风险**

短期 artifact 过期或 GitHub 历史发生访问问题后，恢复者可能只有 commit/内部 hash，没有同一份外部归档可比对。

**修复要求**

将 source zip、外部 SHA-256、source commit、submodule identities 放入 Drive 项目归档并登记 manifest；对正式 checkpoint 使用更长保留期或不可变存储；恢复演练必须从下载的归档重新完成。

---

### MYGPT-011 · P3 · 文档入口和测试入口重复，降低接手效率

**证据**

README 顶部仍是 PR #8 和 2026-09-25 历史检查点，底部又保留旧的“无应用实现”结论；CURRENT_STATE/HANDOFF/EVALUATION_LEDGER 以追加方式保留多组互相冲突的 exact head 和 runner 状态。Brain 的正式环境是 Linux CPython 3.13，但本地说明和仓库多个入口仍交错使用旧测试计数。

**风险**

新 Agent 或开发者需要阅读大量旧 checkpoint 才能判断当前事实，容易误执行已经过期的命令。

**修复要求**

保留一份短的“当前状态”页；历史证据移入按日期命名的 ledger；README 只链接当前状态和当前恢复入口；每次 checkpoint 自动更新测试计数和 exact SHA。

## 五、已确认的安全和工程优点

本轮没有发现已提交的真实 API key、token、cookie 或密码。候选实现有多项值得保留的控制：

- `companion_service.py` 强制绑定 `127.0.0.1`，限制 loopback client、Host、Authorization、客户端标识、Content-Length 和 JSON 类型；
- Bearer token 使用进程级随机值和 constant-time compare，支持过期、撤销、并发连接上限和 completion guard；
- HTTP 不支持 CORS、Transfer-Encoding，不写请求日志；
- `providers.py` 只允许固定 loopback Ollama endpoint，禁止环境代理，限制 timeout、响应编码和最大响应字节数；
- Book context 有 session、expiry、capture time、source hash 和 bounded text，且不会自动成为持久 memory；
- MemoryStore 使用本地 SQLite、bounded candidate window 和显式 memory 生命周期；
- source bundle 检查 exact commit、tracked-only、路径安全、大小上限、symlink/case collision、submodule/license notice 和 deterministic rebuild；
- Spine/model installer 对文件名、大小、SHA/fingerprint 和临时文件安装有边界；
- Android manifest 不申请 INTERNET、SYSTEM_ALERT_WINDOW 或宽泛存储权限；音频只申请 `RECORD_AUDIO`；
- Book receiver 使用 signature permission；运行时不允许通过 HTTP 修改 provider、persona 或远程地址；
- 对话提交在 provider 完成后再次检查 cancellation/revoke，并把消息和 idempotency receipt 放在 SQLite 事务中；
- Java 8/17 边界、Node、source recovery 和 strict Brain CI 有清晰的可复现证据。

这些控制说明候选并非“完全不可用”；主要问题是 release gate、长期保留策略、治理一致性和真实设备证据尚未闭合。

## 六、修复优先级

### P1：先修再继续扩展

1. 修正 `Jvust/mygpt` → `Jvust1/mygpt`，让 Android APK/Gradle host 真正执行；
2. 给 Companion runtime/session receipts 增加 retention、LRU/TTL、压缩和删除策略，解决近二次方增长；
3. 决定候选实现是否合并到 main；若合并，必须以 exact-head PR 方式进行；
4. 同步 project_state、artifact_manifest、README、CURRENT_STATE、HANDOFF 和实际 branch/run 状态；
5. 将上述四项加入 required checks，并禁止 skipped 关键 job 被视为通过。

### P2：形成可交付候选

1. 把 Windows desktop delivery 纳入当前候选 aggregate；
2. 建立跨平台完整依赖锁和 hash 验证；
3. 建立真实 Android/Book/Xiaomi 14/GGUF/ASR/TTS/Windows 验收矩阵；
4. 统一 `SECURITY.md`，补全私下报告和披露流程；
5. 打开 main branch protection；
6. 将 source recovery artifact 和外部 SHA 持久归档到 Drive/manifest；
7. 重新整理当前状态文档和历史 ledger。

### P3：降低维护成本

1. 收敛 README、CURRENT_STATE、HANDOFF 的重复入口；
2. 对测试计数、commit、run ID 使用自动生成；
3. 在新开发者/新 Agent 的第一屏显示“当前 exact head、可运行命令、已知未完成 gate”。

## 七、发布前必须满足的验收矩阵

| 门 | 必须证明 |
|---|---|
| 默认分支 | clean clone 可按文档启动最小 smoke |
| Brain | strict tests、integration tests、compile、pip check |
| Long-run | 10k turn retention/GC/重启恢复 |
| Android | Gradle assembleDebug、APK classes.dex、native payload、license |
| Android device | Xiaomi 14 安装、重启、PiP、权限、内存/热 |
| Book | 真实 AAR、同签名、真实 bounded context |
| Model | 固定候选 GGUF 的延迟/RAM/质量证据 |
| Voice | live microphone ASR 和 audible TTS |
| Windows | exact-head PyInstaller/native/browser/restart |
| Source recovery | 外部 SHA、clean recovery、submodule identity |
| Governance | owner、branch、head、run、artifact manifest 一致 |
| Security | 可执行漏洞报告入口、无秘密泄露、required checks 生效 |

## 八、最终判定

- **代码质量：候选分支达到较强原型/审查候选水平。**
- **安全边界：loopback、token、输入大小、provider 固定地址、权限和 source recovery 控制较好。**
- **自动化验收：Linux/Node/Java/source recovery 证据较强，但 Android APK job 被静默跳过。**
- **长期运行：存在明确的 session/request/receipt 无上限增长问题，必须先修。**
- **仓库治理：main 与候选实现分裂，project state、README、manifest 和实际仓库身份存在漂移。**
- **发布结论：暂不允许把当前仓库称为生产版或完整可发布版。**

推荐下一轮只做一个 bounded checkpoint：**修正 Android 条件 + 实现 retention/receipt GC + 同步治理状态 + 重新跑 exact-head aggregate**。在这四项形成新证据前，不继续增加新的模型、语音或 UI 功能。

