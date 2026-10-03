# Book / mygpt 本机 MCP 试验版

**这是可运行的本机 MCP 2.0 服务，不是真正 Your dot 已接通的证明。** 不改 Book EXE、不改阅读字号或预习/学习/复习/刷题流程；没有公网端口、自动启动、模型调用、语音或 Live 展示。

## 启动

在当前已核验的 Windows 工作区，用 PowerShell 执行本文件同目录的 `Start-MCP.ps1`。默认 `http://127.0.0.1:8766/mcp`；端口占用时传 `-Port 其他端口`。Ctrl+C 停止。

脚本使用现有 `work/mygpt-progress-venv` 和固定提交的 mygpt brain；首次启动在 `work/mcp-prototype/runtime` 创建两个独立随机令牌，仅当前用户与 SYSTEM 获得该目录权限。不把令牌打印、写进源码、提交 GitHub 或上传 Drive。`-PrepareOnly` 只准备运行目录，不启动服务。

本目录是 mygpt 的增量源代码，不是完整发行包。迁移到另一台电脑时应把增量放入现有 mygpt 项目，设置 `MYGPT_SOURCE_ROOT` 到其 brain 目录，并在独立虚拟环境安装 `requirements-mcp.txt`。不要把测试用令牌暴露到公网。

## 已实现的接口

- `POST /mcp`：协议 `2026-07-28`，只有两个窄权限工具：
  - `get_study_progress({})`：读取尚未过期的最小进度与服务器时间。
  - `submit_study_decision({decision_id,producer_session,progress_sequence,action,objective})`：`action` 为 `stay_quiet` 或 `speak`；安静时 objective 必须 null；排队而不启动模型或 Live。
- `POST /local/progress`：mygpt 提交既有 `BookProgress` wire 对象，不接受正文/笔记/答案等额外字段。
- `POST /local/decisions/take`：mygpt 取一次当前有效的决策候选；再次校验会话、序号和有效期。
- `POST /local/disconnect`：清空进度与待执行决策。
- `GET /health`：鉴权后仅返回本机状态，不含正文、进度详情或令牌。

`/mcp` 和 `/health` 使用 `MCP_BRIDGE_TOKEN`；`/local/*` 只接受另一个 `MYGPT_INGEST_TOKEN`。JSON 连接描述 `mcp-connection.example.json` 仅供本地客户端使用，不是 Codex/ChatGPT 插件注册配置。

`LocalMcpBridgeClient.report()` 的成功只表示本地接收。不要把它直接冒充真实 `DotPort`，否则旧 relay 的 `reported_to_dot` 标签会误导。模型与 Live 适配器仍未绑定；取出的决策必须由未来真实主机认证来源，再交现有 relay 复验。

## 事件试验

仅在启动时显式指定 `-AllowLocalTestCallback http://127.0.0.1:接收器端口/hook` 才开启 Events 能力。实现 `events/list`、`events/subscribe`、`events/unsubscribe`；过滤当前 `producer_session`，单订阅、有限 TTL、订阅落盘、签名 challenge、Standard Webhooks 签名、最多三次重试和密钥轮换。

它只向这一条明确允许的本地地址发送，不接受任意主机、代理或重定向。HTTP 回调是 **本地试验例外**，不满足真实 dot 要求的公网 HTTPS/OAuth。阅读进度和决策只保存在内存，进程重启不复活旧进度；磁盘订阅包含本地测试签名密钥，不要共享运行目录。

进度有效期最多 15 秒。异步收到事件后，要先用 `get_study_progress` 读取当前状态，再提交对应的新决策，不能延长旧进度来骗过时效验证。重复 decision_id 不重复入队；关闭、失效或切换会话后拒绝旧决定。退役会话只保存最多 128 个摘要，达到限制后须显式重启桥接，不自动淘汰重放防护信息。

## 验证范围

验证使用独立真实 HTTP 子进程、测试回调接收器和官方 `@modelcontextprotocol/client@2.2.0`；SDK 明确 pin `2026-07-28` modern 模式。测试账户/输入是明确标记的合成数据，不是 dot、真实模型或 Live2D。

当前工作区的测试入口为 `work/mcp-prototype/probe-mcp-capability.cjs`，核心/客户端测试在同目录 `test_mcp_bridge_core.py`、`test_mcp_bridge_client.py`。最终实际命令、输出、退出码和失败修复记录统一追加至原 `outputs/VERIFICATION.txt`。基线没有这些 MCP 文件；回滚删除新增 MCP 文件并恢复原 Book 字节。四角色文件保持同一组。

## 真正接入 Your dot 还差什么

1. 有用户授权的 OAuth 与稳定 HTTPS 事件服务/插件注册，而非本地 bearer 冒充 dot。
2. 观察真实订阅、签名回调接收以及真实 dot 的工具决策；HTTP 2xx 不是 dot 已回复。
3. 绑定实际 mygpt 模型与现有 Live 的文字展示/ACK/回复接口，完成一次真实使用链路。

参考：[OpenAI MCP Events](https://developers.openai.com/plugins/build/mcp-events)、[MCP 2.0 HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)、[官方 SDK](https://github.com/modelcontextprotocol/typescript-sdk)、[Standard Webhooks](https://github.com/standard-webhooks/standard-webhooks)。上一轮查到的小型 starter 仅用于协议实现思路比较，未将其 demo 宣称为 dot 连接器。

