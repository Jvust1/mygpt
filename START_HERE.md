# mygpt · 从这里启动

当前交付是 **完整源码候选**，不是 APK，也不是已接入 GPT 的成品。包含 Jonah、浏览器界面、Python Brain、选段导入、测试和依赖清单，不再需要按顺序拼接旧增量 ZIP。第三方 Python/浏览器依赖、模型权重和 Git 历史不在包内。

## 现在可以实际使用的路径

浏览器明确选择或输入一段内容 → 用户预览并同意 → 127.0.0.1 本机 Python → 来源/时效/权限校验 → Brain → TestModel 固定确认回复。

**TestModel 不是大语言模型。** 它用于证明输入、来源身份、取消、过期和返回链路正确，不能依据固定确认回复认为已经得到真实讲解。真实 Book 自动读取和付费模型均未启用。自己导入的内容永远标为 `USER_SUPPLIED_UNVERIFIED`，不会冒充已认证的 Book 来源。

## 1. 验证并解压完整源码

从本批交付的正式清单取得 `mygpt-source.zip` 对应 SHA-256。Windows PowerShell 可执行 `Get-FileHash .\mygpt-source.zip -Algorithm SHA256`，Linux 可用 `sha256sum mygpt-source.zip`，先比较外部清单，再解压到一个**新的**目录，不覆盖旧项目。

源码包含 `SOURCE_MANIFEST.json`，逐项记录文件、Git blob、SHA-256 和固定 source commit。内部清单不能单独证明真实性，外部哈希也必须来自可信交付记录。代码内验证器支持 `python scripts/source_bundle.py verify <ZIP路径> --sha256 <正式哈希>`；验证器本身也应来自可信源码。

## 2. 创建隔离 Python 环境

需要 Python 3.11+；本项目固定 SDK 的正式回归环境是 Linux CPython 3.13 x86_64。安装是使用者显式执行的网络操作，启动器不会自行下载安装。以下命令在完整源码根目录执行。

Windows PowerShell（命令形式可用，当前没有 Windows 实机验收）：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\brain[test,integrations]"
.\.venv\Scripts\python.exe run_mygpt.py doctor
```

Linux CPython 3.13 x86_64，可使用已验证的哈希锁：

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: --require-hashes -r brain/requirements-linux-py313.lock
.venv/bin/python run_mygpt.py doctor
```

不要把 Linux 单平台 wheel 锁套到 Windows、macOS 或 Android。其他平台的顶层依赖安装不等于已经获得相同的可复现性或设备验收。`doctor` 是只读检查，报告缺失源码/角色资源、Python 版本以及固定顶层依赖是否匹配；READY 不等于所有传递依赖、浏览器或设备均已测试。

## 3. 启动

用同一虚拟环境解释器执行（以下用 `python` 表示它）：

```sh
# 只启动固定合成样例；默认不接收自选文件或文字
python run_mygpt.py start

# 明确启用本次服务的一条内容输入功能
python run_mygpt.py start --enable-selection-intake
```

服务打印 `http://127.0.0.1:<随机端口>`。在同一电脑浏览器打开：

- `/host/brain.html`：固定样例，已有 Jonah 入口；
- `/host/selection.html`：导入选段或手动输入；需要上方显式开启 intake。

只选择文件不会发送。先预览，再勾选同意，最后点击发送到本机；只有进一步明确请求才进入 Brain。可取消、清除选段、撤销本次授权。正文只在本机进程内存中暂存，不自动上传云端或保存到 GitHub/Drive；不要拿密码、私人聊天或金融账户内容作样例。

终端按 Ctrl+C 停止。撤销或授权超时后应停止并重新显式启动，刷新页面不能恢复已撤销的服务授权。服务只有 loopback 监听，不能在手机中把 `127.0.0.1` 当电脑地址；本批不开放局域网、不建隧道、不改防火墙。

## 常见阻塞

`BLOCKED`：按 doctor 的 missing_files/dependencies 处理。缺文件时恢复完整源码而不是只拷 host 目录；缺 SDK 或版本不符时先修复独立虚拟环境。不要为了通过检查删掉版本约束。

`selection intake disabled`：使用者必须显式以 `--enable-selection-intake` 启动，不通过更改前端标识绕过。

回复是固定文本：这是当前明确边界，并非模型账号风控或故障。当前还不提供真实智能讲解。

公式：输入合同保留 LaTeX，但界面仍以原始 LaTeX 展示，尚未完成正式数学排版。浏览器自动化视口通过也不是 Android APK、软键盘或跨 App 悬浮窗验收。

## 开发与恢复

代码/状态以 GitHub 当前非默认分支为权威，完整源码 ZIP 是固定版本恢复点。后续治理提交可能比包内状态更新，应先读最新 `governance/project_state.json`。旧增量包仍是历史证据，不删除。

打包器从指定 40 位 commit 的 Git blobs 读取，不读取未提交工作树；拒绝非白名单路径、链接、字体/密钥/缓存/模型文件和超限内容。它不是对普通源码中潜藏秘密的全面 DLP 审计。打包与校验不会改 Git ref，不安装依赖。详情见源码内脚本和测试。

开发用例：`python -m unittest discover -s tests -p 'test_*.py' -v`；Brain 严格集成用例使用 `brain/scripts/verify_integrations.py`，零跳过才可验收。正式 run、哈希和剩余问题以本批 checkpoint/PR 与成果清单为准。
