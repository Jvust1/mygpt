# mygpt 学习工作台 · 当前入口

当前优先入口是 **`/host/brain.html`**：浏览器实际通过 127.0.0.1 调用 Python Brain，再走 Pydantic AI TestModel 的固定合成回复。真实 Book 与真实模型仍未连接。

## 运行本机 Brain 模式

需要先安装 `brain/pyproject.toml` 固定的 Python 依赖。Linux CPython 3.13 x86_64 可使用现有 hash lock；其他平台不要直接套用该平台锁。

```sh
cd brain
python -m mygpt_brain.local_service --port 0
```

终端会打印类似：

```text
mygpt local brain: http://127.0.0.1:<随机端口>
scope=SYNTHETIC_LOCAL_PYTHON_BRAIN live_book_connected=false paid_model_calls=0
```

在同一浏览器打开打印地址的 `/host/brain.html`。服务只绑定 127.0.0.1，使用每次启动生成的内存授权 cookie；当前有限接口仅为 status / explain / cancel / revoke。它是开发期同机协议，不是生产多用户服务器或 Android IPC。

页面只发送有界的选择身份、来源引用/哈希、mode、revision 与选择有效期；Python 从固定合成目录重建正文，浏览器不会上传任意教材正文。只有明确点击“解释这段”才进入 Brain；取消、切段、暂停、过期或 revoke 都会使旧请求失效。

## 当前验收

- Python 固定 SDK：两个干净环境各 **332 passed / 0 failed / 0 skipped**。
- 最新宿主测试 head：**Node 54 pass**。
- 原 Jonah 浏览器回归：**49 checks pass**。
- 旧合成回放 host：**39 checks pass**。
- 新本机 Python host：**23 checks pass**。
- 真实/付费模型调用：**0**。
- 真实 Book feed：**未连接**。

完整安全边界、原始失败历史、CI run/artifact 身份见 [LOCAL_BRAIN_TRANSPORT_CHECKPOINT_20260923.md](../docs/LOCAL_BRAIN_TRANSPORT_CHECKPOINT_20260923.md)。

## 旧回放入口

`/host/reader.html` 仍保留，用来验证不依赖 Python 运行时的合成回放 UI。下面的旧说明作为历史/回放模式文档保留；其中“浏览器不会实时运行 Python Brain”只适用于 `reader.html`，不适用于当前 `brain.html`。

---

# mygpt 学习工作台 · 合成回放原型

这是可操作的 **Reader 选段 × Jonah** 界面，不是完整聊天产品、真实 Book 连接或 APK。页面始终显示模拟标识；示例和回复均为人工编写，不使用真实教材、私人聊天或付费模型。

## 在已有仓库中运行

使用包含本目录的 `feat/book-contract-audit-v1` 候选版本，保留同级 `companion/`、`demo/` 和 `scripts/`。运行需要 Node.js；该静态页面没有 npm 运行时依赖。

```sh
node scripts/serve.mjs
```

打开终端打印的本机地址，将路径改为 `/host/reader.html`。默认端口是 4173，实际地址以终端为准。只启动绑定 127.0.0.1 的开发预览；不是公网部署，也不是 Book 或模型服务器。结束后在终端按 Ctrl+C 停止。

不要双击 HTML 后把 file:// 环境的模块或 WebCrypto 限制当成产品错误。本轮不修改原预览服务器的访问控制，也不把它提升为生产服务。恢复包是增量文件，不能单独取出 host/ 后当成包含角色资源的完整应用。

## 操作

选择练习 A 或 B 的具体内容层，然后点“解释这段（演示）”。A 支持原文、校正、推导提示和推导解答；B 支持原文。查看来源身份可核对教材版本、层级和实际样本文字的哈希。

打开 Jonah 菜单或帮助面板不触发请求。明确选段也不触发请求；点击解释才开始回放。等待期间可以取消，取消后不会出现迟到回复。切换选段、切换模式、暂停、隐藏角色、离开页面会使当前请求或上下文失效。重新选择才继续，页面返回不隐式恢复。

“关闭本页演示”会禁止该页面实例继续选择或请求；刷新才能创建新的实例。这个功能不是未来服务器令牌撤销的实现。

默认角色停靠在阅读滚动区域之外，避免遮挡选择控件。用户仍可拖动已有角色组件。低高度窗口暂时隐藏并暂停角色动画，普通帮助入口仍保留。手动隐藏角色后停靠区缩小；系统减少动态效果设置继续生效。

## 技术边界

`brain/mygpt_brain/host_fixtures.py` 调用真正的 Reader 映射器和 Brain，生成带来源哈希和提案收据的合成样本；`host/fixtures.js` 是它的确定性导出。测试检查导出与当前 Python 结果逐字一致，并检查四模式的来源身份。

浏览器 **不会实时运行 Python Brain**。`controller.js` 管理界面选择及请求状态；`replay.js` 验证样本正文 SHA-256 后，回放预写回复。650 毫秒延迟只是可取消交互演示，不代表模型延迟。

浏览器的两分钟选择有效期是 UI 演示期限，不覆盖 Python 样本的固定捕获时间，也不能证明真实学习活动。有效性同时检查墙上时钟和单调时钟；异常回退或超时失效。八秒请求超时不会自动重试。每次回复必须匹配请求 ID、选择修订、模式、记录、来源和哈希；双击共享同一次待处理请求。

页面使用 `textContent` 展示文字和 LaTeX，不插入来源 HTML。公式当前展示原始 LaTeX，尚未引入数学排版器。CSP 不允许 connect-src；没有 fetch/WebSocket、凭据设置、上传或对外模型调用。浏览器不保存正文、回复或学习会话；只有既有 Jonah 的位置/显隐偏好可能保存在 localStorage。

这个静态候选不是接受任意不可信目录数据的生产网关。未来真实网络适配器必须另做身份授权、来源/会话版本、大小限制、取消与撤销测试，不可把样本标识改为 LIVE 就算接通。

## 验证命令

```sh
# 在仓库根目录，无需 Playwright 即可执行控制器/回放和图集单测。
node --test tests/atlas.test.mjs tests/host-controller.test.mjs

# 在已配置固定 Python 依赖的环境：
cd brain
python -m mygpt_brain.host_fixtures --check ../host/fixtures.js
python scripts/verify_integrations.py --output /path/to/new/evidence
```

严格 Python 验收的输出目录必须不存在。普通 pytest 在本地缺少 SDK 时会跳过；这不能代替严格验收。

浏览器验证使用 Playwright 1.62.0 及其 Chromium。采用独立工具目录，不向产品添加运行时依赖：

```sh
npm install --prefix /path/to/browser-tools --ignore-scripts --no-audit --no-fund --save-exact playwright@1.62.0
node /path/to/browser-tools/node_modules/playwright/cli.js install chromium
# 设置 NODE_PATH 为该工具目录的 node_modules 后，在仓库根目录运行：
node tests/browser.cjs
node tests/host-browser.cjs
```

首次安装需要允许的网络环境与对应系统浏览器依赖。CI 在 Ubuntu 上补齐依赖和中文字体；字体文件不进入成果包。两个 browser suite 各自拥有临时 loopback 服务，运行结束关闭。截图与报告写入 `MYGPT_TEST_OUTPUT` 指定目录或各自默认输出目录，不应提交缓存与测试临时产物。

本轮真实结果、第一次失败与修正、精确源码及剩余限制见 `docs/HOST_UI_CHECKPOINT_20260923.md`。浏览器模拟移动视口不等于 Android 真机或读屏器验收。
