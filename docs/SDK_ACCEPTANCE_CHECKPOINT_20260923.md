# SDK 集成验收与 Book 接口调查 · 2026-09-23（+08）

状态：`SDK_ACCEPTANCE_PASS / BOOK_READER_MAPPING_RECORDED / REVIEW_PENDING`。
这是 PR #5 的续接检查点，不是生产聊天、真实 Book 联调或 APK 发布。

## 1. 当前成果与身份

- 仓库：Jvust2/mygpt；分支 `feat/book-context-brain-20260922`；[PR #5](https://github.com/Jvust2/mygpt/pull/5) 保持 Draft / OPEN / UNMERGED。
- 本轮起点：`cf998dbd797535b7e800cb20a2b71f6b5207f091`。
- 增加严格验收与 CI：`d8648dbde7715492dc642b543b4992cfb74b6c5c`。
- 第一轮实测修正与依赖锁：`1b4041831208a2de69f76100003f6eeed4fe2ac4`。
- **通过验收的精确代码：`95fd2846f5ec535b1241b4bb565fbca92eda626e`**。
- 该实现 tree：`903573a7bcb16d03b1989b58972ad5aebb886ee8`。
- 后续同分支状态/归档文件提交不改上述可执行代码；文档提交不能冒称重新跑过 exact-head CI。以实现 SHA 与运行证据关联判断。

## 2. E005 — 真正执行的测试，而非跳过或 README 声明

| 执行环境 / 阶段 | 结果 | 说明 |
| --- | --- | --- |
| 本地原始基线 | 95 passed，2 skipped | 与前批结果一致，源码 Git blob 相同 |
| 本地增加验收工具 | 111 passed，2 skipped | 16 项新确定性用例通过；缺 SDK 仍明确跳过 |
| 本地严格验收命令 | exit 2，BLOCKED_DEPENDENCIES | 没有将缺依赖算作成功 |
| 第一次真实 SDK CI | 112 passed，1 failed，0 skipped | TestModel 通过；MCP 列表结果类型错误 |
| 第二次真实 SDK CI | 112 passed，1 failed，0 skipped | 哈希锁安装通过；MCP 返回缺少 structured_content |
| 第三次 CI 首个干净环境 | **113 passed，0 failed，0 skipped，2.17s** | 两个真实 SDK 都执行通过 |
| 第三次 CI 第二个干净环境 | **113 passed，0 failed，0 skipped，1.36s** | 按同一哈希清单重新安装后再次通过 |

最终 CI：[run 35762870487](https://github.com/Jvust2/mygpt/actions/runs/35762870487)，job `106865005363`。checkout、安装、pip check、首次测试、全新 venv 重装与复测、演示、compileall 和证据上传均成功。

实际 CI 环境：Ubuntu 24.04 / CPython 3.13.15 x86_64；安装版本为 Pydantic 2.13.4、pydantic-ai-slim 2.46.0、MCP 2.2.0、pytest 9.0.2、pytest-asyncio 1.3.0。本地仍为 Python 3.13.5 且缺两个可选 SDK，不混用两种环境的执行结果。

最终 artifact `10711455709`，101,061 bytes，下载后 SHA-256 与 GitHub 返回的 digest 相同：
`b7cae531acefa9d648c85f83be83417914a161bac18876e2e9f457f846d04cd1`。
两个 `acceptance.json` 均 accepted=true，required cases 缺失数为 0，JUnit 与原始 pytest 输出一致。

## 3. D017 — 从运行错误修正接口，不放宽验收

第一次真实执行发现 `Client.list_tools()` 返回 `ListToolsResult`，不能直接遍历结果对象。修正为 `.tools`，继续断言仅存在三个只读工具。

第二次真实执行发现裸 `dict` 返回类型不能保证 MCP structured output，导致 `structured_content=None`。修正为参数化的字典/列表类型，并显式使用 `structured_output=True`。客户端同时验证 output schema、来源上下文、结构化决策列表及过期后 context=None。

来源：[MCP structured output 文档](https://py.sdk.modelcontextprotocol.io/servers/structured-output/)。最终兼容性结论主要来自上方固定版本实际测试，不从动态主分支 README 推定。

TestModel 仍仅返回程序式固定 fixture；`ALLOW_MODEL_REQUESTS=False`。MCP 使用 `Client(server)` 的进程内传输，没有监听端口或配置真实 Book 端点。测试 fixture 检测 Python 层网络 connect/bind/listen/sendto 等行为，OTEL 关闭；这不是对所有原生网络路径的安全证明，不等于操作系统沙盒认证。

## 4. 可复现依赖与有界 CI

`brain/requirements-linux-py313.lock` 来自第一次 CI 的真实 clean pip install report，记录 39 个分发包的精确版本及对应 wheel SHA-256。锁 SHA-256：
`78a05ef99a580964c73cc2944ec9a1df4252e0b16d352f99ae30ce02faeae8c2`。

锁是 Linux CPython 3.13 x86_64 的观察结果，不是 Windows/macOS/Android 通用锁。pip 自身、操作系统和解释器未声明位级可复现；wheel 固定只保证本次依赖集合与下载内容可核对。

严格脚本 `brain/scripts/verify_integrations.py` 检查顶层版本、两项必需用例、零跳过、零错误、退出码和 120 秒超时。输出目录必须新建，防止沿用旧通过证据。锁生成器只接受正常 PyPI HTTPS wheel、完整 SHA-256 和唯一分发名，拒绝凭据 URL、直接地址和源代码包。

CI 只监听本 Brain 开发分支及相关源码/测试/依赖路径；单 job 10 分钟，contents:read，checkout 精确 SHA，凭据不落 Git 配置，第三方 Action 固定 commit。不部署，不使用提供方秘密，不改计费设置。使用 GitHub Actions 现有资源，不对账单作“绝对免费”的承诺。

## 5. 失败证据保持不可变

| 运行 | 代码提交 | GitHub artifact | 原始 ZIP SHA-256 |
| --- | --- | --- | --- |
| [35762375554](https://github.com/Jvust2/mygpt/actions/runs/35762375554) | d8648db | 10711130327 | `de73da9f4fa12029a810302192b8b7906ae84e24f2e0a63efd1f8466a9952095` |
| [35762614414](https://github.com/Jvust2/mygpt/actions/runs/35762614414) | 1b40418 | 10710427186 | `b60850450dd5078d90c847c3ce3b2353abafc3ad77c11c2723079bedc6d73f4b` |
| [35762870487](https://github.com/Jvust2/mygpt/actions/runs/35762870487) | 95fd284 | 10711455709 | `b7cae531acefa9d648c85f83be83417914a161bac18876e2e9f457f846d04cd1` |

三份原始 artifact ZIP 均已下载、核对 digest，并收进本轮恢复包；不同运行不会因相似内容去重删除。GitHub 短期 artifact 保留不代替 Drive 长期归档。此前 `mygpt-brain-context-v0.1-20260922.zip` 保持原 ID/哈希，不覆盖。

## 6. Book 实际接口核验结果

取得并核对 Book CURRENT r6 源码原包，检查 Reader API、前端状态、两门课程 manifest 和内部身份清单。结果见 [Book Reader bridge mapping](BOOK_READER_BRIDGE_MAPPING_20260923.md)。

确认 r6 有独立 `/api/reader/...` API，不应直接采用旧 Web `/api/courses/...` / StudyRecord 作为当前手机阅读状态。发现真实 `book_version_id` 包含 `@`，不兼容当前 Brain Identifier；Reader 也没有对外暴露唯一选中记录、会话 ID 或可恢复事件序号。正文、校正、派生解答必须分层，PDF/转录哈希不能冒充本次选段文本哈希。

本轮只读源码与必要目录/课程身份，不运行 Book API、不读取实际笔记、不复制教材或 Book 源码进 mygpt，不修改任何 Book ref。这个调查关闭了“接口完全未知”的问题，不关闭“真实桥接未实现”的问题。

## 7. 恢复与唯一下一步

本批次恢复包名称：`mygpt-brain-sdk-acceptance-20260923.zip`。归档身份以 `governance/artifact_manifest.json` 的 `mygpt-brain-sdk-acceptance-20260923` 条目为准，避免 ZIP 内嵌自身 ID/哈希的循环身份。

包包含 Brain 源码、只读/无实时模型 CI、两份当前技术说明、原始失败与成功 artifacts、本地回归、Book 接口身份元数据、逐文件哈希和恢复说明。无第三方源码、Book 原文、字体、Jonah 重复图集、凭据、虚拟环境或缓存。它是 Brain 的增量恢复包，不是完整 mygpt App 或 APK。

**唯一下一步：** 在 mygpt 当前非默认分支实现 r6 `ReaderSnapshot` 的严格离线映射候选；先修正不透明版本字段兼容性，定义显式选段、来源层和正文序列化，再用合成 fixture 测试。当前不改 Book、不启用网络服务、不调用真实模型。之后才对 Book 宿主侧事件和认证提出独立 preflight。

独立代码审阅 PENDING，真实模型教学质量、生产 Book 连接、Jonah 联动、Android 宿主/真机、网络鉴权和外部动作 outbox 均未验收。继续保持 PR Draft；不自动合并、不直接写 main。
