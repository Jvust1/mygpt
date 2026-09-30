# mygpt

**Dot Brain Bridge + supervision-first companion runtime**

mygpt 的目标不是再造一个独立“大脑”，而是成为 **OpenAI Dot、Live、Book 与本地/云端工具之间的神经系统**。

## 最终形态

```text
你 <-> Live 人物 <-> mygpt <-> Dot
                     |
                     +--> Book
                     +--> GitHub / 本地工具 / 屏幕上下文
```

- **Dot**：长期大脑，负责目标、长期上下文、规划和主动判断。
- **mygpt**：桥梁、监督策略、工具调度、状态归一化。
- **Live**：人物身体和交流界面。
- **Book**：学习内容与学习流程。

默认人格策略为 **7 分监督、3 分陪伴**。这是决策权重，不是机械地每十句话提醒七次。

## 当前已实现

### mygpt 原生运行层

- `DotBrainBridge`：不依赖未公开 API 的间接 Dot inbox/outbox 协议。
- `SupervisionEngine`：companion / light / firm / focus 四档监督。
- `CompanionRuntime`：监督状态 -> Dot 请求 -> Live 事件的完整编排。
- `mygpt.live.v1`：Live 侧稳定事件格式。
- Dot 不可达时的本地 fallback，不让人物“失声”。
- Node 内置测试与可运行 demo。

### AIRI 能力库

`vendor/airi/` 保留并持续吸收 AIRI 的 MIT 许可模块，包括：

- character core / character card
- memory
- plugin SDK / protocol
- audio / transcription / TTS pipeline
- server runtime / SDK
- MCP bridge
- screen capture / web extension
- component calling

AIRI 原始 MIT LICENSE 保存在 `vendor/airi/LICENSE`。

## 运行

要求 Node.js 20+：

```bash
npm test
npm run demo
```

demo 会把一次“学习中出现注意力漂移”的状态转换成 Live 事件，并同时为 Dot 写入结构化请求。

## 目录

```text
src/
  brain/          # Dot bridge
  config/         # 7:3 策略
  supervision/    # 监督状态机
  live/           # Live 协议
  runtime/        # 总编排
config/
docs/
tests/
vendor/airi/      # 上游 AIRI 源码
```

详细协议见 [docs/DOT_BRAIN_BRIDGE.md](docs/DOT_BRAIN_BRIDGE.md)。

## 下一阶段

1. Live WebSocket sink：把 `mygpt.live.v1` 实际送进 Live。
2. Dot transport adapter：接本地电脑/连接器层，自动消费 inbox/outbox。
3. Book adapter：读学习计划、当前章节、完成情况和考试目标。
4. Activity adapter：结合 AIRI screen capture / Web Extension 形成监督信号。
5. Persistent memory：把短期事件汇总给 Dot，而不是无筛选永久记录。
6. Android runtime：让同一协议在 Book 安卓版和 Live 皮肤中工作。
