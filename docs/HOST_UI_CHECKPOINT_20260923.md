# Reader × Jonah 宿主界面检查点 · 2026-09-23

状态：**SYNTHETIC_HOST_UI_ACCEPTED / REAL_TRANSPORT_NOT_CONNECTED / REVIEW_PENDING**。
当前候选：`Jvust2/mygpt`，`feat/book-contract-audit-v1`，PR #6。此阶段没有修改 Book、StudyMate、ChatContextVault 或 main，没有合并任何 PR。

## 1. 当前身份与实际产品边界

本轮起点 `070747683ebce299531c2d95d7aa9deb79b266cb`。
首个实现 `d24802d9906c559f2099d44eedbb7d58b9148d3f`；移动布局/异步测试修正 `b688943fe710537ff0e7807361a303bd7b7aa04e`，tree `5ee71987fffa6f0f9aafa7bd39b01a17bca310ea`。
后续检查点提交只添加使用说明、验收记录和更新状态索引，不改变已验收的运行代码。

已有 Python Reader 映射器与 Brain 在构建样本时真实执行，生成带版本、来源层、正文哈希及提案收据的合成目录；浏览器验证样本文字 SHA-256 并回放预写回复。**浏览器没有实时连接 Python Brain，也没有连接真实 Book 或模型。** 页面始终显示模拟标识，不能将“测试通过”解释成已经有生产对话能力。

该宿主采用既有 Jonah Web Component，不重写或替换角色图集。角色的状态来源是当前 UI 请求生命周期；working 不意味着云端模型正在思考，ready 也不代表回答通过教学质量验收。

## 2. D019 — 明确选择、界面状态与推理层分开

新增宿主文件 `host/reader.html`、`reader.css`、`reader.js`、`controller.js`、`replay.js` 和由 Python 生成的 `fixtures.js`。无前端运行时框架依赖，没有为了原型同时引入多个 Agent 框架。

支持两条合成记录、五个明确选择：A 原文、A 校正、A 推导提示、A 推导解答、B 原文。预习/学习/复习/刷题四种模式均有验证。没有选择时禁止求助；打开角色菜单或帮助面板不会默认发请求。切换模式后清空选择，防止旧上下文被当成新模式输入。

每次回放绑定 request_id、选择 revision、mode、entry_id、source_ref、source_sha256 和合成 scope。双击共用一个待处理 Promise，不重复调用适配器。回复中的任何身份不一致、model_called 非 false、空文本或超限文本都拒绝。

取消、换选段、暂停、隐藏角色、离开页面立即使当前请求失效。即便旧适配器忽略 AbortSignal 后才返回，也不能覆盖新选择或取消状态。超时只显示错误，不隐式重试。控制器对外只返回通用失败原因，不显示异常内的任意私密字符串。

两分钟选择期限是**浏览器 UI 演示期限**，不是将固定 Python 样本时间改成“真实现在”。墙上时钟与单调时钟均参与判断，检测到回退或期限已过即失效；不依赖后台 setTimeout 一定及时触发。八秒等待预算只是原型设置，650 毫秒回放延迟不是推理性能指标。

## 3. 界面与生命周期

显示当前所选内容层、完整含 @ 的版本号、演示选择失效时刻、实际文本哈希与来源引用。原文、非官方校正、AI 派生解答都保留区别。正文由 textContent 渲染，公式显示原始 LaTeX；当前没有数学排版器，也不展示教材图片。

Jonah 的 pet-chat-request 只打开帮助入口并转移焦点；关闭/ESC 恢复原触发控件。取消后回到可操作按钮。页面隐藏或 pagehide 暂停；pageshow 不自动恢复。BFCache 测试使用合成 PageTransitionEvent，不能称为跨浏览器真实缓存恢复验收。

移动截图暴露了原版默认角色遮挡选择控件的问题，后续加入独立停靠区，将阅读内容放进单独滚动区域。默认位置下角色不会压在内容选择框上；保留用户主动拖动能力，不保证拖到任意位置都不遮挡。低高度窗口隐藏并暂停角色动画，普通帮助面板保留；隐藏角色后底部区域缩小。

已实际观察最终 393×852 手机尺寸截图和 1280×900 桌面截图：中文正常、角色图正常、默认停靠与阅读区域分开；长来源信息换行，正文可在滚动区继续阅读。截图是 Chromium 模拟视口，不是手机真机拍摄。

## 4. E007 — 按精确源码分别记录验收

| 阶段 | 精确代码 / 环境 | 实际结果 |
| --- | --- | --- |
| 本地 Python 基线 | 本轮起点；Python 3.13.5 | 264 passed / 5 skipped |
| 本地 Python 新样本与组合 | d24802d 对应源码；缺可选 SDK | 285 passed / 5 skipped |
| Python 远端首个干净环境 | d24802d；Ubuntu 24.04 / CPython 3.13.15 | **290 passed / 0 failed / 0 skipped，2.19s** |
| 同一哈希锁第二个干净环境 | 同一 d24802d | **290 passed / 0 failed / 0 skipped，1.41s** |
| 最终 Node 单测 | b688943；Node v22.23.2 | **49 passed / 0 skipped**：46 个新控制器/回放 + 3 个旧图集检查 |
| 最终原 Jonah 浏览器回归 | b688943；Playwright 1.62.0 / Chromium 151.0.7922.34 | **49 项检查全部通过** |
| 最终新宿主浏览器验收 | 同一 b688943 浏览器环境 | **39 项检查全部通过**，运行/CSP 错误 0、外部请求 0 |

Python run：[35806749551](https://github.com/Jvust2/mygpt/actions/runs/35806749551)，job `107009207839`。两份 acceptance.json、JUnit、pytest 原始输出和 source-commit.txt 均已实际读取并核对。沿用原 39 个 wheel 哈希锁；TestModel/内存 MCP 仍为无实时模型测试。

UI run：[35807425272](https://github.com/Jvust2/mygpt/actions/runs/35807425272)，job `107011254871`。Node 原始 TAP、旧/新浏览器报告、截图、环境版本及 source-commit.txt 均已读回。不能把 290、49、49、39 混加成同一套精确执行，也不能把各环境重复运行算新用例。

b688943 相对 d24802d 仅改三个宿主文件和新浏览器脚本，Python/生成器/样本/SDK 工作流完全相同；因此保留对应 d24802d 的 Python 验收证据，不声称 Python 工作流在 b688943 上又运行过。后续文档检查点亦不伪称重新跑过 CI。

## 5. 第一次失败与修复不能抹掉

第一次 UI run [35806749602](https://github.com/Jvust2/mygpt/actions/runs/35806749602)，job `107009208035`，d24802d：Node 49 项和原 Jonah 49 项已通过，新宿主完成前 27 个检查点后在减少动态效果断言处停止。原因是测试在 emulateMedia 后马上检查计时器，未等待实际 matchMedia 回调。

修复增加等待“计时器已停止”的真实条件，原断言保留；另增加默认停靠不与阅读区域相交的检查。没有用强制 PASS、删除断言或屏蔽 CSP 错误来验收。失败 artifact 保留为独立历史，与成功 artifact 不互相替换。

本地受管理 Chromium 对导航返回 ERR_BLOCKED_BY_ADMINISTRATOR。未修改管理策略、未绕过 URLBlocklist，而是在已有授权的 GitHub Actions 环境完成浏览器验收。本地浏览器失败不能称为本地通过；也不能把本地限制当成界面产品缺陷。

## 6. 原始证据与源码一致性

| 类型 | artifact ID | bytes | 下载 SHA-256 |
| --- | --- | --- | --- |
| Python 双环境通过 | 10727024882 | 106487 | `7b1dc26b80098af1687897ad0e2adc964b956b1f6b85e2acef84082003ef78c1` |
| 第一次 UI 失败 | 10728255659 | 1326401 | `9a71b9197810a675d5caf0de98b18e9879ff5db6f4670c023be6159c90f16cb5` |
| 最终 UI 通过 | 10727898973 | 1347417 | `20f6591c22b802d1fd956f58cca6719503c1dbf13bcf673e0467a5df8657df5f` |

三份 ZIP 均已核对 GitHub digest、实际下载哈希和 ZIP CRC。它们以原始字节归档，不只保存摘要。短期 GitHub artifact 保留不能替代 Drive 长期索引。

初始 12 个新增/修改源文件与后续四个修正文件均按 Git blob 身份核对本地源码与远端树。Python 样本生成测试按字节比较 host/fixtures.js；Node 回放还检查实际 UTF-8 正文哈希。现有 Brain 核心、Reader 映射器、Jonah 组件及图集、安全文件均未改动。

恢复包名 `mygpt-host-ui-v1-20260923.zip`，稳定 artifact_id 为 `mygpt-host-ui-v1-20260923`；正式 Drive ID 和外层哈希在 artifact_manifest 中，避免包内自引用。包是本轮增量源码/文档/证据，不含旧 Brain 全量源码、Jonah 重复图集、Book 原文、第三方源码、字体文件、凭据、缓存或虚拟环境。运行需对应仓库基线；直接使用说明见 [host/README.md](../host/README.md)。

## 7. 权限、成本与剩余缺口

新增 UI workflow 只监听当前候选分支和相关源码路径，十分钟单 job 上限，contents:read，固定 Action commit、精确 SHA checkout，不保留 Git 凭据，不部署、不读取模型秘密。Playwright 顶层版本固定，并保留真实安装产生的 npm lock 作为证据；未声明浏览器二进制/系统包和所有平台完全位级可复现。使用现有 Actions 资源，未变更计费设置，也不承诺运行额度绝对免费。

CSP connect-src 为 none，页面没有 fetch、WebSocket、网络模型调用或上传。测试阻止非本机 origin 请求。该浏览器检查不是通用渗透测试，静态目录验证也不是面向不可信远端数据的生产安全边界。已有预览服务器只用于本机开发，不提升为可信网络 API。

未验收：真实 Book 选择/会话导出、真实 UI↔Python 请求链、网络身份与撤销、生产聊天/教学质量、Android APK/真机/软键盘、原生跨 App 悬浮窗、读屏器、独立代码审阅。

PR #6 仍 Draft/未合并，GitHub 仍报告与 PR #5 的整合冲突；具体冲突尚未逐项解决。本轮不覆盖另一分支、不 rebase、不合并。测试通过不意味着可以直接合入 main。

## 8. 唯一下一步

在 mygpt 仓库内设计并验证“宿主 → 真正 Python Brain”的最小同机请求合同，继续只用合成资料和 TestModel。先明确请求身份、当前选择/来源版本、取消、过期、超时、许可撤销及错误语义；网络实现前另列 loopback 限定、Origin/Host 验证、临时授权和有限接口清单的 preflight。

下一批不自动连接真实 Book、不启用付费模型、不读取私人资料。Book 侧导出器、Android 宿主和真实端点各自后续授权。先把静态回放替换为真实受控调用，而不是继续添加更多动画或模拟聊天功能。

参考的官方 API 说明：
- https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal
- https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API
- https://playwright.dev/docs/ci
- https://github.com/microsoft/playwright/releases/tag/v1.62.0

本轮没有复制第三方源码。API 说明用于实现，验收结论来自上述固定源码的实际测试。
