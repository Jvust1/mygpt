# mygpt：5 本书与开源参考项目

书目查证：2026-09-22 至 2026-09-26；GitHub 元数据复核：2026-09-26（UTC，北京时间 9 月 27 日）。

已核对PR #9及最新North Star：Windows学习陪伴已有候选交付。本资源用于增强现有Brain和体验；Book实时桥、真实教学质量和系统级透明悬浮仍单独验收。

成长次序见[长期路线图](LONG_TERM_ROADMAP.md)。本清单包含 **5 本书、12 项 GitHub 参考**；按项目能力与使用范围扩大来选择，不按月份排课。

本次现状依据：[开发 PR #9](https://github.com/Jvust/mygpt/pull/9)、[读取时的固定版本](https://github.com/Jvust/mygpt/tree/10d55d33365ccc21f141f43aefdeb45257c73ba5)。这些是开发分支证据，不代表已经合并或完成用户设备验收。

## 先从哪里开始

先读两本的相关章节：[The Design of Everyday Things](https://www.hachettebookgroup.com/titles/don-norman/the-design-of-everyday-things/9780465050659/)；[Make It Stick: The Science of Successful Learning](https://www.makeitstick.com/about-make-it-stick)。

先看三个仓库：[statelyai/xstate](https://github.com/statelyai/xstate)、[pydantic/pydantic](https://github.com/pydantic/pydantic)、[microsoft/playwright](https://github.com/microsoft/playwright)。

第一项可评审产物：一次暂停、恢复、退出和撤销的任务走查。

| 成长环节 | 用户价值 |
|---|---|
| G1 宠物载体 | 有一个随时可呼出、隐藏且不打扰的入口 |
| G2 理解当前学习 | 不必反复解释当前章节即可提问 |
| G3 跨课程个人陪伴 | 换书和学习方式仍保持连续、克制的帮助 |
| G4 有限跨库编排 | 在明确任务中少做重复输入和切换 |

P0＝当前先学；P1＝能力深化时参考；P2＝需求成立后再评估。推荐指向学习或候选比较，没有承诺安装全部依赖。

## 五本书：用途与最小产物

### 1. The Design of Everyday Things

- 作者：Don Norman。
- 版本：Revised and Expanded Edition（官方书页明确）；语言：英语；本次未核验可明确对应本版的正版中文译本。
- [出版社／作者入口](https://www.hachettebookgroup.com/titles/don-norman/the-design-of-everyday-things/9780465050659/)。Hachette/Basic Books官方合法纸书、电子书、有声书入口；本次不核定地区库存、售价或中文对应版本。
- 对应成长：G1–G2：可理解陪伴。
- 解决的问题：让状态、暂停、授权与撤销容易理解；默认安静，不用动画抢夺注意力。
- 最小应用产物：一次暂停、恢复、退出和撤销的任务走查。

### 2. Make It Stick: The Science of Successful Learning

- 作者：Peter C. Brown / Henry L. Roediger III / Mark A. McDaniel。
- 版本：一手页面未明确版次；语言：英文原著；作者官网确认简体及繁体中文版本入口，译本版次未核验。
- [出版社／作者入口](https://www.makeitstick.com/about-make-it-stick)。作者官网提供正规购书、出版社和中文版本入口；仅节选公开，非全书免费
- 对应成长：G2–G3：学习效果。
- 解决的问题：把讲解后的回忆与反馈作为学习依据，避免将聊天轮数当掌握度。
- 最小应用产物：对一个Book选段设计可回溯来源的回忆检查。

### 3. Designing Bots

- 作者：Amir Shevat。
- 版本：2017；语言：英文；本轮未核验对应中译本。
- [出版社／作者入口](https://www.oreilly.com/library/view/designing-bots/9781491974810/)。官方目录/试读；全文通过正规购买或图书馆借阅。
- 对应成长：G1–G2：陪伴交互。
- 解决的问题：选读对话、人格边界、通知和人工介入；平台API章节较旧，实施时查现行文档。
- 最小应用产物：安静/轻陪伴/辅导/监督四类状态的语言和打断规则。

### 4. AI Engineering

- 作者：Chip Huyen。
- 版本：2025；语言：英文；本轮未核验对应中译本。
- [出版社／作者入口](https://huyenchip.com/books/)。官方目录/试读；全文通过正规购买或图书馆借阅。
- 对应成长：G2–G4：基于模型的学习帮助。
- 解决的问题：将模型选择、检索、评测、延迟和成本放在一个闭环中比较。
- 最小应用产物：固定学习任务集、简单基线、失败类型与延迟/成本报告。

### 5. Practical Data Privacy

- 作者：Katharine Jarmul。
- 版本：2023；语言：英文；未核验中译本。
- [出版社／作者入口](https://www.oreilly.com/library/view/practical-data-privacy/9781098129453/)。出版社目录与试读，完整书需合法购买或借阅
- 对应成长：G1–G4：最小上下文。
- 解决的问题：限定学习摘要与会话信号的收集、保存、撤销和共享范围。
- 最小应用产物：Book/StudyMate输入字段白名单与过期处理规则。

## GitHub 参考总览

许可摘要是本轮筛选依据；最近推送不等于稳定发行、可靠性或本项目兼容性。仓库代码的许可与模型权重、数据、字体、图片及角色素材的许可分别核对。

| 优先级 | 官方仓库 | 成长环节 | 许可摘要 | 已归档 | 最近推送（UTC） |
|---|---|---|---|---|---|
| P0 | [statelyai/xstate](https://github.com/statelyai/xstate) | G1–G2 | MIT | 否 | 2026-09-26T15:16:34Z |
| P0 | [pydantic/pydantic](https://github.com/pydantic/pydantic) | G2 | MIT | 否 | 2026-09-26T17:31:26Z |
| P0 | [microsoft/playwright](https://github.com/microsoft/playwright) | G1–G3 | Apache-2.0 | 否 | 2026-09-26T05:40:18Z |
| P1 | [electron/electron](https://github.com/electron/electron) | G1 | MIT | 否 | 2026-09-26T15:28:26Z |
| P2 | [tauri-apps/tauri](https://github.com/tauri-apps/tauri) | G1–G4 | MIT 或 MIT/Apache-2.0，按组件；Logo 为 CC-BY-NC-ND | 否 | 2026-09-26T17:46:10Z |
| P1 | [pixijs/pixijs](https://github.com/pixijs/pixijs) | G1 | MIT | 否 | 2026-09-25T20:33:05Z |
| P2 | [airbnb/lottie-web](https://github.com/airbnb/lottie-web) | G1 | MIT | 否 | 2025-09-01T09:01:31Z |
| P1 | [fastapi/fastapi](https://github.com/fastapi/fastapi) | G2–G4 | MIT | 否 | 2026-09-26T13:35:50Z |
| P2 | [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) | G2–G3 | MIT | 否 | 2026-09-26T16:39:55Z |
| P1 | [ollama/ollama](https://github.com/ollama/ollama) | G2–G3 | MIT | 否 | 2026-09-26T14:29:55Z |
| P2 | [open-spaced-repetition/ts-fsrs](https://github.com/open-spaced-repetition/ts-fsrs) | G3 | MIT | 否 | 2026-09-26T14:04:29Z |
| P2 | [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | G4 | MIT | 否 | 2026-09-25T09:25:15Z |

## 各仓库具体怎么用

### 1. statelyai/xstate · P0

- 使用方式：候选组件；接入前评估；适用阶段：G1–G2。
- 本项目用途：描述安静、辅导、暂停、撤销等状态及事件。
- 最小产物：中断与撤销时禁止再输出/采集的状态转移表。
- 适用限制：先对照当前Brain实现，只有状态复杂度需要时才接入。
- 查证：[官方仓库](https://github.com/statelyai/xstate) · [许可依据](https://api.github.com/repos/statelyai/xstate) · [维护元数据](https://api.github.com/repos/statelyai/xstate)。

### 2. pydantic/pydantic · P0

- 使用方式：候选组件；接入前评估；适用阶段：G2。
- 本项目用途：验证Book选段、会话租约与Brain请求/响应。
- 适用限制：不能用格式校验替代来源身份和授权校验。
- 查证：[官方仓库](https://github.com/pydantic/pydantic) · [许可依据](https://api.github.com/repos/pydantic/pydantic) · [维护元数据](https://api.github.com/repos/pydantic/pydantic)。

### 3. microsoft/playwright · P0

- 使用方式：候选组件；接入前评估；适用阶段：G1–G3。
- 本项目用途：验证用户暂停、关闭、模型失败和Book授权撤销后的界面行为。
- 适用限制：模拟通过不等于真实Book桥、系统透明悬浮或教学质量已验收。
- 查证：[官方仓库](https://github.com/microsoft/playwright) · [许可依据](https://api.github.com/repos/microsoft/playwright) · [维护元数据](https://api.github.com/repos/microsoft/playwright)。

### 4. electron/electron · P1

- 使用方式：桌面扩展参考；适用阶段：G1。
- 本项目用途：参考桌面托盘、窗口与进程隔离。
- 适用限制：需要真实桌面原生能力才评估；不改写已有Windows交付，不放宽renderer权限。
- 查证：[官方仓库](https://github.com/electron/electron) · [许可依据](https://api.github.com/repos/electron/electron) · [维护元数据](https://api.github.com/repos/electron/electron)。

### 5. tauri-apps/tauri · P2

- 使用方式：替代方案对照；适用阶段：G1–G4。
- 本项目用途：对比轻量桌面外壳和权限能力模型。
- 适用限制：与Electron是候选取舍，不同时引入两套；迁移须有可测收益。
- 查证：[官方仓库](https://github.com/tauri-apps/tauri) · [许可依据](https://github.com/tauri-apps/tauri/blob/dev/README.md) · [维护元数据](https://api.github.com/repos/tauri-apps/tauri)。

### 6. pixijs/pixijs · P1

- 使用方式：候选组件；接入前评估；适用阶段：G1。
- 本项目用途：绘制2D角色、表情和交互反馈。
- 适用限制：渲染器不提供模型授权，不等于Live2D Core兼容。
- 查证：[官方仓库](https://github.com/pixijs/pixijs) · [许可依据](https://api.github.com/repos/pixijs/pixijs) · [维护元数据](https://api.github.com/repos/pixijs/pixijs)。

### 7. airbnb/lottie-web · P2

- 使用方式：候选组件；接入前评估；适用阶段：G1。
- 本项目用途：作为轻量状态动画的替代展示。
- 适用限制：Lottie格式不能直接播放任意角色包；动画素材许可单独核对。
- 查证：[官方仓库](https://github.com/airbnb/lottie-web) · [许可依据](https://api.github.com/repos/airbnb/lottie-web) · [维护元数据](https://api.github.com/repos/airbnb/lottie-web)。

### 8. fastapi/fastapi · P1

- 使用方式：候选组件；接入前评估；适用阶段：G2–G4。
- 本项目用途：参考本地Brain API、类型契约与错误边界。
- 适用限制：已有服务够用时不重写；本地服务仍需来源校验和最小暴露范围。
- 查证：[官方仓库](https://github.com/fastapi/fastapi) · [许可依据](https://api.github.com/repos/fastapi/fastapi) · [维护元数据](https://api.github.com/repos/fastapi/fastapi)。

### 9. ggml-org/llama.cpp · P2

- 使用方式：候选组件；接入前评估；适用阶段：G2–G3。
- 本项目用途：CPU/GPU预算明确后比较本地推理延迟和内存。
- 适用限制：MIT不覆盖模型权重；不预设6GB显存可以运行任意模型，模型与缓存按设备规则存放。
- 查证：[官方仓库](https://github.com/ggml-org/llama.cpp) · [许可依据](https://api.github.com/repos/ggml-org/llama.cpp) · [维护元数据](https://api.github.com/repos/ggml-org/llama.cpp)。

### 10. ollama/ollama · P1

- 使用方式：候选组件；接入前评估；适用阶段：G2–G3。
- 本项目用途：研究本地模型管理与统一调用接口。
- 适用限制：与llama.cpp按部署需要择一；不自动下载模型、不默认调用云端。
- 查证：[官方仓库](https://github.com/ollama/ollama) · [许可依据](https://api.github.com/repos/ollama/ollama) · [维护元数据](https://api.github.com/repos/ollama/ollama)。

### 11. open-spaced-repetition/ts-fsrs · P2

- 使用方式：候选组件；接入前评估；适用阶段：G3。
- 本项目用途：研究复习间隔建议的可解释输入与输出。
- 适用限制：Book保留学习内容和记录权威；评分不足时不产生精确掌握度结论。
- 查证：[官方仓库](https://github.com/open-spaced-repetition/ts-fsrs) · [许可依据](https://api.github.com/repos/open-spaced-repetition/ts-fsrs) · [维护元数据](https://api.github.com/repos/open-spaced-repetition/ts-fsrs)。

### 12. modelcontextprotocol/python-sdk · P2

- 使用方式：候选组件；接入前评估；适用阶段：G4。
- 本项目用途：跨库真实调用需求成立后，研究窄工具接口。
- 适用限制：协议不自带用户权限；每项工具需独立允许范围，不能因此读取Vault原始聊天或扩大外部动作权限。
- 查证：[官方仓库](https://github.com/modelcontextprotocol/python-sdk) · [许可依据](https://api.github.com/repos/modelcontextprotocol/python-sdk) · [维护元数据](https://api.github.com/repos/modelcontextprotocol/python-sdk)。

## 检索覆盖与未采用项

本清单按以下环节筛选，不能穷尽 GitHub。成长适配、优先级和应用产物是结合本项目的建议；书目身份、许可和维护状态依据链接中的一手来源。

- 陪伴状态与低打扰交互
- 学习回忆与模型评测
- 受限Book语义上下文
- 可选本地推理
- 按需桌面角色
- 跨项目窄接口

以下未采用项的细节沿用初次筛选证据；不把未入选项目说成永久不可用。

- **Live2D Cubism SDK/Core整体**：官方区分开放组件与专有Core/发行许可；不把整个SDK或角色素材列为普通开源依赖。 [依据](https://www.live2d.com/en/sdk/license/)

## 使用这份清单的方式

每次从当前成长环节选一本书的一部分和一至三个相关仓库，先形成小产物，再决定是否接入。实际采用时固定版本，核对当前官方文档、许可证和项目已有实现。旧书中的 API 示例以现行官方文档为准。

本次交付是书目和公开项目研究：未购买或复制整书，未安装或运行候选项目，也没有把候选能力计作本项目的已验证成果。
