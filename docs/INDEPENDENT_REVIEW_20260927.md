# PR #9 / PR #8 / Book authority 独立审查

日期：2026-09-27（+08）  
审查基线：`9004cac1f00700d879987e2d00299ce9a659fa51`（PR #9 当前精确 head）  
PR #9 基线：`feat/integrate-pr6-book-bridge-20260925`  
Book authority：`bf7aa490639bc2b2fcf382623b915d54f6cecf07`

## 结论

**未发现需要阻止继续评审的 Critical 或 Major 问题。** PR #9 的 Windows 工作台保持本地数据、显式模型请求和现有 Brain/Book 边界；PR #8 的 lease receiver 与 Book authority 的实际接口可以在同一进程中完成一次 TestModel 联调，并在撤销后拒绝缓存回复。

这不是合并批准，也不代表用户 Windows 设备、Android、真实 Book APK 或真实模型质量已经验收。PR 仍保持 Draft/未合并。

## 审查范围

- PR #9 新增的 `desktop_state.py`、`desktop_workspace.py`、`desktop_runtime.py`、`desktop_adapter.py`、桌面 UI 和 Windows 打包/浏览器验收脚本。
- PR #8 的 `brain/mygpt_brain/book_bridge.py` 以及对应的 lease、内容摘要、收据、取消和撤销语义。
- Book authority 的 `Authority.grant/resolve/commit_current`、会话 epoch、短 lease 和源摘要校验。
- loopback Host/Origin/Cookie/客户端头、模型请求显式同意、重定向拒绝和本地持久化冲突保护。

## 验证证据

- Windows 桌面专项：18 个 pytest 用例通过；状态测试另有 6 个参数化子用例通过。
- Node 宿主回归：66 项通过。
- 代码语法与 Git diff 检查通过。
- 使用 Book authority 实际实现和 mygpt receiver 完成接口级联调：
  - Book authority 签发短期 lease；
  - mygpt 校验选择身份和内容摘要并得到 `PYDANTIC_AI_TESTMODEL` 回复；
  - 相同 request ID 复用已完成收据；
  - authority revoke 后，缓存回复被拒绝；
  - 付费 provider 调用为 0。
- PR #8 已有 exact-head CI 证据：Brain SDK 两环境各 446/0/0、Book receiver 20 cases、Node 66、Jonah 49、回放 host 39、本机 Python host 23、selection host 30、完整源码恢复 446/0/0。

## 发现与处理

1. **Windows 回归覆盖缺口（已补充）**：原桌面浏览器脚本只验证工作台、笔记和默认无同意模型请求，没有真正打开固定 Brain 页面。本次在 `tools/desktop_browser_test.py` 增加 `/host/brain.html` 的 loopback TestModel 流程：选择合成 record、发送一次解释请求、等待 `ready`、确认回复框可见且付费模型计数为 0，再回到工作台继续重启持久化检查。
2. **未发现授权绕过**：桌面 API 继续要求随机 HttpOnly cookie、精确 Host、固定客户端头和同源 POST；Book receiver 继续把当前性检查交回 authority，未把本地输入提升为 Book 身份。
3. **未发现数据覆盖问题**：SQLite 保存使用 revision 冲突拒绝；备份合并保留冲突副本，不恢复另一设备的 active timer；草稿和回复不会自动写入笔记。

## 已知限制

- 本机默认 Python 3.14 的 Windows asyncio 在离线网络守卫下会为 `asyncio` 自身的 `socketpair` 使用 127.0.0.1；这使本地完整 Brain pytest 不能作为本次 Windows 证据。项目正式 SDK 证据仍以 Linux CPython 3.13 锁定环境为准，Windows 桌面专项不宣称完整 Brain SDK 回归。
- 用户本人 Windows 设备、Android Studio/真机、用户已安装 Book APK 身份、直接浏览器 localhost 策略和生产多用户传输仍待单独验收。
- TestModel 和本机 Ollama 入口都不代表真实教学质量；没有启用付费 provider。

## 审查判定

**Review status：ACCEPTED_FOR_USER_DEVICE_VALIDATION**  
后续步骤是用户设备验收，以及在允许 localhost 的受信任环境中完成真实 Book 选段 → mygpt TestModel 端到端；不自动合并、不启用真实 provider。

## 2026-09-27 follow-up validation

- `brain/tests/conftest.py` now permits only loopback targets for the offline test guard, which allows Windows asyncio self-pipes while continuing to reject non-loopback network access.
- With the fix, `tests/test_book_bridge.py` passes 20/20 and the TestModel integration case passes on Windows Python 3.14.
- The full Windows suite reaches 445 passed; two parameterized JSON-boundary cases still hit Windows' 32K environment-variable limit while pytest restores the oversized case name. Formal SDK acceptance remains the Linux CPython 3.13 CI result recorded above.
