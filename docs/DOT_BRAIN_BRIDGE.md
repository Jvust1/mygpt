# Dot Brain Bridge

## 目标

mygpt 不再尝试成为另一个完整“大脑”。职责拆分为：

- **OpenAI Dot**：长期大脑、目标、规划、长期上下文、主动判断。
- **mygpt**：神经系统；汇总用户状态，执行监督策略，发送/接收工具请求，桥接 Dot 与 Live/Book/本地工具。
- **Live**：身体与交流界面；负责人物、表情、动作、语音、嘴型和桌宠窗口。
- **Book**：学习内容与学习流程。

数据路径：

```text
User <-> Live <-> mygpt <-> Dot
                 |
                 +--> Book
                 +--> tools / screen context / GitHub / local actions
```

## 为什么是“间接连接”

当前实现不假定存在可供第三方程序直接调用的个人 Dot HTTP API。mygpt 使用一个显式的桥接协议：

1. mygpt 把请求写入 `runtime-spool/dot/inbox/<id>.json`。
2. Dot 侧、本地电脑代理或未来的官方连接器读取请求。
3. 响应写入 `runtime-spool/dot/outbox/<id>.json`。
4. mygpt 校验 `requestId` 后转换为 Live 事件。

因此未来出现更直接的 Dot transport 时，只需替换 transport，不需要重写监督逻辑或 Live 协议。

## 7:3 行为策略

`0.7 supervision / 0.3 companionship` 是**决策权重**，不是“10 句话里必须有 7 句催促”。

监督有四档：

1. `companion`：任务正常或没有活跃任务。
2. `light`：轻提醒。
3. `firm`：明确拉回当前目标。
4. `focus`：明显拖延/跑偏时进入短周期监督。

完成任务后自动回到 `companion`。批准的休息会显著降低监督分，避免把正常休息误判成拖延。

## Dot 请求协议

协议版本：`mygpt.dot.bridge.v1`

请求包含：

- 用户消息
- 当前任务
- 应用/活动状态
- 监督模式与分数
- 希望 Dot 使用的工具
- 期望响应字段

Dot 响应至少应包含：

```json
{
  "requestId": "<request id>",
  "text": "对用户说的话",
  "intent": "supervise",
  "emotion": "focused",
  "motion": "nudge",
  "nextCheckInMinutes": 15,
  "toolCalls": []
}
```

## Live 协议

mygpt 输出 `mygpt.live.v1` / `companion.message` 事件。Live 只负责展示，不需要理解 Dot 内部逻辑。

下一步应在 Live 侧增加正式 WebSocket sink，把该事件映射到：

- 文本气泡
- TTS
- Live2D/Spine 表情
- motion
- lip-sync
- 桌宠通知
