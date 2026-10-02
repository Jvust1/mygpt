# UI → 本机 Python Brain 受控链路检查点 · 2026-09-23

状态：**SYNTHETIC_LOOPBACK_BRAIN_ACCEPTED / REAL_BOOK_NOT_CONNECTED / PAID_MODEL_CALLS_0 / REVIEW_PENDING**。

当前候选仍为 `Jvust2/mygpt` 的 `feat/book-contract-audit-v1` / PR #6。这个里程碑把浏览器“预写回放”推进成浏览器实际通过 127.0.0.1 调用 Python 服务，再由 Python 重建 ReaderContext v2、执行真实 Brain 事件/策略路径，并通过 Pydantic AI TestModel 返回固定合成回复。它不是生产 Book 桥、不是在线模型聊天、不是 Android APK。

## 1. 精确代码身份

- 上一检查点 head：`b4634e482b5b72b92f4c3961a1a68d1e198ec6ee`。
- 主要实现：`56b39522bb81aa71699548d2d93b060eb87dad6d`。
- SDK 验收自测修正：`ef31c36986ca0134c9c62bcdcdf2ebcdf155c431`。
- 浏览器负向 HTTP 日志分类修正：`0c6e30906e0333d40e1dbf928c571928fecfcf10`。
- 直接控制器合同测试补齐：`2c23fa5dec2fac17ce4d06aa083374007225d2f1`。

后两个提交只改验收/测试，不放宽服务端安全规则。真正服务和浏览器适配器来自 56b39522；后续验收必须按精确源码区分，不能把不同 head 的数字机械相加。

## 2. D020 — 本机链路的安全边界

`brain/mygpt_brain/local_service.py` 只绑定 `127.0.0.1`，端口可随机分配。当前授权是每次服务启动生成的内存随机值，只通过 HttpOnly、SameSite=Strict cookie 交给浏览器；令牌不回显到 HTML/JavaScript，不落盘。

API 只允许固定 Host、同源 Origin/Referer 或可验证的 same-origin Fetch Metadata、固定 `X-MyGPT-Client`，并且不提供 CORS 预检。POST 必须精确 Origin。静态文件使用固定 allowlist，不把仓库当通用静态目录。请求体最大 8192 bytes，请求收据最多 128 条；授权 60–3600 秒，选段有效期最多 300 秒。

当前 HTTP 接口仅：

- `GET /api/v1/status`
- `POST /api/v1/explain`
- `POST /api/v1/cancel`
- `POST /api/v1/revoke`

浏览器发给 Python 的不是教材正文，而是有界身份：request id、revision、entry id、mode、source ref、source SHA-256、当前 UI lease 截止时间及固定 synthetic scope。Python 只从项目内固定合成 catalogue 重新取得正文，并再次校验 context/reference/hash。

这不是防本机恶意进程的系统安全边界：本机程序可以直接访问 loopback；也不是多用户网络服务、TLS 服务或 Android IPC。它只证明一个受约束的开发期同机协议可行。

## 3. 真正执行的 Brain 路径

每次 explain：

1. 校验固定合成目录与请求身份。
2. 按请求 mode 重建新的 `ReaderStudyContext v2`，上下文有效期受服务器限制。
3. 建立独立内存 `Brain()`。
4. 实际执行 `SESSION_STARTED`。
5. 实际执行 `HELP_REQUESTED`。
6. 只有 Brain decision 为 `explain` 且 source_ref 精确一致才继续。
7. 默认 responder 实际调用 Pydantic AI 2.46.0 的程序式 TestModel，`ALLOW_MODEL_REQUESTS=false` 验收。
8. await 后再次校验证据和取消状态，再返回固定 fixture。

因此 “Python Brain 已连接”现在是事实；“真实 Book 已连接”仍为 false，“真实/付费模型已调用”仍为 false。

同 request_id + 同内容只返回缓存收据，不重复执行；同 request_id + 不同内容返回 409。取消或撤销会设置当前请求 cancel 标志，迟到的 responder 结果不能成为完成回复。撤销后当前实例的后续 API 被 403 拒绝。

## 4. 浏览器侧链路

`host/brain.html` 是独立入口，明显显示：本机 Python Brain、Book 未连接、TestModel 固定样本、付费模型调用 0。

`host/brain-adapter.js` 只用 same-origin fetch 和固定客户端头；没有 API key/provider 设置。AbortSignal 会触发有限 `/cancel` 请求。`host/controller.js` 继续负责明确选择、lease、timeout、迟到回复抑制，并把 `selection_expires_at_ms` 与 identifier-safe request id 一起送给 Python。

浏览器打开 Jonah 或选段不会调用 Python explain；只有“解释这段”才发请求。取消、切段、切模式、暂停、隐藏、页面离开和过期仍会使旧结果失效。

## 5. E008 — 本轮真实验收

### 本地环境

- Node v22.16.0：`54 passed / 0 failed / 0 skipped`（3 atlas + 既有 host/controller/replay + 新 loopback adapter 合同及 lease/id 测试）。
- Python 3.13.5：`326 passed / 0 failed / 6 skipped`。6 skip 全是本机缺 pydantic_ai/mcp；不得当成 SDK 通过。
- `HOST_FIXTURE_EXACT_MATCH`。
- `compileall` 通过。
- 实际启动 loopback HTTP 的 smoke：17/17，通过 Host、cookie、Origin/Fetch Metadata、allowlist、真实 Brain policy、dedupe、409 conflict、cancel、revoke 等；external requests=0，model calls=0。

### 远端固定依赖 / SDK

第一次 run `35816530437` 在真正安装 SDK 后得到 `331 passed / 1 failed`。失败不是产品路径：严格 verifier 新增第三个必需集成用例后，旧的 verifier 自测仍断言缺 2 个而不是 3 个。原失败 artifact `10731473320` 保留，不删除。

修正自测后 run `35816679199` / job `107039579688` 成功：

- Ubuntu 24.04 / CPython 3.13.15。
- Pydantic 2.13.4、pydantic-ai-slim 2.46.0、MCP 2.2.0，仍用既有 39-wheel hash lock。
- 第一个干净环境：**332 passed / 0 failed / 0 skipped**。
- 同一 hash lock 第二个全新环境：**332 passed / 0 failed / 0 skipped**。
- 三个必需 SDK cases 都实际出现：旧 TestModel、旧 MCP、默认 LocalBrainEngine TestModel。
- loopback HTTP smoke 17/17、fixture exact、旧 demo / Reader demo、compileall 均通过。
- success artifact `10732155955`，109,049 bytes，下载 SHA-256 `3973492a40347cbf029463ec589f5a74e9d97b07c297b7509456e19aaf3b7e2a`。

CI 日志中可见若干测试连接被主动断开后 stdlib HTTP server 打出的 BrokenPipe traceback；job 与收据仍通过。它说明当前开发服务器日志还不够整洁，不等于外部请求或模型错误；未来服务包装可单独收敛日志，但本轮不隐藏失败结果。

### 真实浏览器 + Python loopback

第一次 run `35816530520`：Node 53、旧 Jonah 49、回放 host 39 和 Python loopback 的所有功能检查已经完成，但 Chromium 把故意测试的 409 forged request 与 403 post-revoke 请求写成 console resource error，导致最后“console errors=0”断言失败。原失败 artifact `10731292451` 保留。

修正只做错误分类：要求 console 中**恰好**出现这两个预期非 2xx，其他 runtime/CSP error 仍为失败。run `35816778853` / `0c6e309` 成功：

- Node 53 pass（后续补齐一条 controller lease/id 测试到最新 head）。
- 原 Jonah browser：49 checks PASS。
- 合成回放 host browser：39 checks PASS。
- **真实 loopback Python host：23 checks PASS**。
- 23 项包括：127.0.0.1 随机端口、可见边界、HttpOnly cookie、TestModel-only status、选择不自动解释、真实 pending 请求、browser abort→Python cancel、取消结果不迟到、实际 TestModel fixture、5 个内容选择路径、伪造 source identity 409、显式 revoke、revoke 后 403、API allowlist、外部请求 0、付费模型计数 0、除两项刻意负向 HTTP 外 runtime/CSP errors 0。
- Playwright 1.62.0 / Chromium 151.0.7922.34 / Node v22.23.2。
- success artifact `10732245592`，1,516,828 bytes，下载 SHA-256 `bd1ba9e74045d6ddd4de3cb2f4c43967cb5297106e160a5675a89da5b5d076e1`。

最新 test-only head `2c23fa5dec2fac17ce4d06aa083374007225d2f1` 增加一条直接 controller 合同断言：request id 字符集可被 Brain Identifier 接受，`selection_expires_at_ms` 必须等于 UI 活跃 lease。其 scoped host run `35817053593` / job `107040710718` 已成功：**Node 54 pass、Jonah 49 checks、回放 host 39 checks、本机 Python host 23 checks**。runtime 与 0c6e309 相同；最新 success artifact `10731589161`，1,516,804 bytes，下载 SHA-256 `1fee99805b6e2c70d22f55a06f617e10c1fc03b3df25ef5ba6ba4598ef672ba2`。

## 6. 当前尚未完成

- 真实 Book 当前选段导出：**NOT CONNECTED**。
- 用户手机已安装 Book APK 身份：**NOT VERIFIED**。
- 生产网络身份、TLS、多用户授权：**NOT IMPLEMENTED**。
- 实际 GPT/Claude/其他 provider：**0 calls / NOT ENABLED**。
- 教学质量验收：**NOT RUN**。
- Android 宿主/真机/软键盘/跨 App overlay：**NOT RUN**。
- 独立代码审阅：**PENDING**。
- PR #5/#6 三方整合冲突：**PENDING / 不自动解决**。

## 7. 唯一下一步

本机 UI→Python Brain 链路通过后，下一阶段才轮到 **Book r6 侧的最小只读显式导出器候选**：用户明确选中 record/layer 后，Book 生成带 book_version_id、section、record、layer、epoch/session/freshness 的短期快照，交给同机 mygpt 适配器；默认不导出笔记/作答、不写 StudyRecord、不调用模型。

Book 是独立项目，任何写入必须先重新读取其当前治理、安全策略和目标分支状态，并在 Book 非默认分支做独立 preflight。mygpt 本轮通过不替 Book 授权，也不自动开启真实数据链路。