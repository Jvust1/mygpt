# Dot Brain Bridge

## 目标架构

```text
User <-> Live <-> mygpt <-> Dot
                 |
                 +--> Book
                 +--> screen context / tools / GitHub
```

- **Dot**：长期大脑、规划、长期上下文、主动判断。
- **mygpt**：神经系统；监督、上下文归一化、工具调度和桥接。
- **Live**：人物身体；表情、动作、语音、嘴型和桌宠窗口。
- **Book**：学习内容、当前章节、任务与完成状态。

## 运行接口

默认启动：

```bash
npm install
npm start
```

默认端口：

- mygpt HTTP：`http://127.0.0.1:8787`
- Live WebSocket：`ws://127.0.0.1:8765`

Live 当前 AIRI bridge 默认正是连接 `ws://localhost:8765`，因此 mygpt 现在可以直接充当该 bridge server。

### POST /signal

输入示例：

```json
{
  "userMessage": "我有点想去刷视频",
  "book": {
    "taskActive": true,
    "currentTask": "泛函分析：第 2 章复习",
    "progress": 0.4,
    "idleMinutes": 12,
    "missedCheckIns": 1
  },
  "screen": {
    "app": "Browser",
    "windowTitle": "Video",
    "category": "entertainment",
    "distractionScore": 0.8
  }
}
```

mygpt 会：

1. 归一化 Book + screen 信号。
2. 用 7:3 监督策略判定 companion/light/firm/focus。
3. 写 Dot 请求到 `runtime-spool/dot/inbox`。
4. 若已有 Dot 回复则采用；否则使用本地 fallback。
5. 通过 WebSocket 把 text/emotion/status 发给 Live。

### POST /live/idle

TTS 播放结束后调用该接口，Live 会收到 `status=idle`。

## Dot 间接协议

当前实现故意不假定存在个人 Dot 的公开 HTTP API。

- inbox：`runtime-spool/dot/inbox/<id>.json`
- outbox：`runtime-spool/dot/outbox/<id>.json`

Dot、本地电脑代理或后续官方连接层都可以作为消费者。未来只替换 transport，不需要重写监督与 Live 层。

## 7:3 策略

7:3 是**决策权重**，不是机械的消息比例。

- companion：正常推进/无任务。
- light：轻提醒。
- firm：明确拉回当前目标。
- focus：明显拖延、持续跑偏、错过检查点。
- completed：完成后立即回 companion。
- approved break：降低监督分，避免把正常休息当拖延。

## 与 AIRI 的关系

`vendor/airi/` 是能力库；mygpt 原生 `src/` 才是产品逻辑。

AIRI 提供：

- character core
- plugin SDK / tool protocol
- screen capture
- audio / speech pipelines
- server runtime
- MCP bridge

mygpt 负责把这些能力围绕 **Dot brain + 监督优先 companion** 组合起来。
