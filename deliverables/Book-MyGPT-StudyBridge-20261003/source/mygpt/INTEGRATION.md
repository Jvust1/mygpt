# Book → mygpt → dot → mygpt → Live2D 联动检查点

日期：2026-10-02。状态：**本地源码样本通过；真实 dot、模型、Live2D 尚未接入。不是新版 EXE。**

## 1. 本轮目标与边界

按用户最新要求：Book 是阅读与学习进度的权威；mygpt 接收进度并反馈 dot；dot 判断是否需要互动，再给 mygpt 互动目标；mygpt 生成回复，由 Live2D 展示并承接用户回复。保留预习、学习、复习、刷题，不能让每次翻页直接触发模型或聊天。

绑定的 Book 对象是本工作区既有 document-reader.js 修改副本，不是其他同名安装程序。原始文件、已交付的 1.3.1 EXE、教材和 PDF 均未修改。

mygpt 主体复用 Jvust1/mygpt 的 chore/fusion-checkpoint-dot-20261001，固定源提交 1e766c00d7ccb857d7d5a858e7af776f66b611df。main@0776119ccae16deacbb92884860c75fd3f806aea 只有初始化文件和审计报告，不是此运行时。

## 2. 职责和链路

```mermaid
flowchart LR
  B[Book 位置与学习模式] -->|本机进度租约| M[mygpt 进度接收器]
  M -->|结构化反馈，无模型调用| D[dot 判断]
  D -->|保持安静或给出互动目标| C[mygpt 现有聊天运行时]
  C -->|文本、情绪、会话 ID| L[Live2D 实际宿主适配器]
  L -->|用户主动回复，同一会话| C
```

用户已经确认 dot 是 Codex 的 Your dot，Live 项目是 Jvust1/Live，运行在 Windows 电脑上。宿主适配器仍未接通。测试中的 TestDot、合成 responder、TestPresentation 不能冒充真实服务、真实 AI 或已显示的角色。真实 dot 接入路线已从官方资料核验为 MCP Events，详见第 9 节。

## 3. 已实现的源码改动

### Book

- 修改 savePosition()，在原有 CAS 学习记录保存成功后，发布 book-study-progress，并写入 settings.documentReaderLive。
- 设置面板增加“让 mygpt 了解本次阅读进度”；默认关闭，每次重开都清除旧租约，不自动继承备份中的共享状态。
- 共享书名、文档/章节、模式、源 SHA-256、正文块与字符位置、渲染页、字号、已作答题数、前台状态。
- 不共享正文、原 PDF 字节、笔记、书签、草稿或作答内容；不抓屏。
- 750ms 位置保存节流，5s 前台心跳，租约最长 15s。离开阅读页发送 stopped，关闭共享发送无上下文的 disabled。
- 后台、失焦、编辑/设置弹窗、输入时不允许主动打断。visible_seconds 仅表示可见时长，不代表专注或掌握；idle_seconds 不代表走神。
- position_fraction 是正文块序号比例，属于粗粒度位置，不是知识掌握率；准确定位仍用 block_id + content_offset。渲染页不是原 PDF 页码。

### Book 本机后端

- 在 main.go 副本中接入 GET /api/study-progress；保留原有 loopback、Host、Origin 和 CSP 边界。
- 只导出白名单进度字段，不让 mygpt 读取整个 /api/state。缺少记录返回 204；额外字段、嵌套标量和过大内容被拒绝。
- 新的 study_progress.go 与测试放在源码副本中。当前仅编译/测试该副本，没有覆盖原后端或重新打包 EXE。

### mygpt

- 新 book_progress.py 作为既有 brain/mygpt_brain/ 下的增量模块；复用 CompanionChatRuntime，不另建模型系统。
- BookProgressPoller 仅访问固定本机来源的 /api/study-progress，禁用环境代理和重定向；BookProgressRelay.watch() 默认每秒读取。
- 接收进度不会调用模型。dot 决策必须匹配当前会话、序号和有效期；stay_quiet 无模型调用。
- 默认 90s 主动互动冷却；乱序/重复事件、旧决定、后台/关闭共享、上下文切换、推理期间撤销，不能产生旧上下文的主动展示。
- 渲染器缺失不调用模型；展示 ACK 不确定时不自动重复说话。128 条小型决定回执上限，不保存进度历史或整个教材。
- 原有 mygpt 聊天历史/回执长期增长问题没有在本轮修复，不能据此宣称通过生产级长期运行验收。

## 4. 已观察的验证

| 验证 | 结果 | 范围 |
|---|---|---|
| BASELINE 同输入 | 4/13，通过原位置保存；无进度共享，exit 1 | 原始 JS 的隔离运行，不是源码文本推断 |
| 本轮改动前副本 | 同样 4/13，exit 1 | 保留原有排版修复的副本 |
| MODIFIED 同输入 | 22/22，exit 0 | 四种模式、隐私、暂停、开关、CAS 后事件 |
| ROLLBACK | 脚本 exit 0；同输入恢复 4/13、exit 1；原始哈希一致 | 独立副本，未破坏修改副本 |
| 原有字号回归 | 原始/回滚版均 9 项失败；修改版 19/19，exit 0 | 10–20px 控件、边界与持久化 |
| 真实浏览器 | 21/21，exit 0 | 一章、四模式、共享设置、心跳、10/12/15/20px、重开默认关闭；本机 CAS 为一次性夹具 |
| Go | 19 项通过，exit 0 | 原有 15 项与 4 项进度出口测试，使用 overlay 编译副本 |
| mygpt 链路 | 12 项通过，exit 0 | 固定源运行时 + 合成 dot/回复/显示端；本机 HTTP 实际请求与持续读取停止 |

原始 JS SHA-256：9c0942aa94d2a27954b1c975b50dd34719d96918a73a152ce93119874a6303b9。

原始 Book main.go SHA-256：f4feb216440101fb6158a18b154c84bac6f19e3d4018619d240aec4767ebef3e。

所有命令、输入哈希、字面 stdout/stderr、退出码及失败后修正，保存在既有 VERIFICATION.txt 与 evidence/integration、evidence/rebuild 中。没有用此前历史成绩冒充本轮运行。

**真实 dot 调用 = 0；真实 LLM 调用 = 0；Live2D 画面/可听语音验收 = 0。**

## 5. 决策与取舍（ADR，当前为候选）

选择小型本机进度适配器 + 现有 mygpt 运行时，不重做编排系统，不接入实时 AI 排版，不把 Book 的权威内容迁移进 mygpt。

优点：不改变排版，断开陪伴服务不妨碍阅读，安静与互动分开，容易核对事件来源。

代价：需要重新打包采用该接口的 Book，确定实际 dot 和 Live2D 入口，并处理宿主启动、来源发现、权限、语音和重连。

未选：浏览器跨域直连 dot/模型（凭据与 CSP 风险）；全量读取 Book 学习数据（不必要的隐私暴露）；每翻页调用模型（高成本、过度打断）；另写一个“dot 判断器”冒充用户说的 dot。

## 6. 下一步：只补真实宿主链路

1. 已完成 dot 身份确认与受支持路线查证；下一步实现、注册受认证的 MCP Events 插件并由真实 dot 创建订阅，验证回调与真实决定。不能用普通 Codex 聊天、自动化或本地自写判断器代替 Your dot。
2. 已确认 Jvust1/Live 与 Windows；其现有 Talk 是角色动作，不是聊天/TTS。需接入有界文本展示、消息回执与同会话用户输入，不能把 Spine 或静态图片当作 Live2D 已验收。
3. 将已验证增量模块接入实际 mygpt 宿主，提供 DotPort 与 PresentationPort，绑定用户实际使用的模型。凭据仅留本机，不写仓库/报告。
4. 重建并在用户使用环境跑一章：切换四模式/字号 → mygpt 收到新位置 → dot 回执 → dot 明确允许互动 → mygpt 回复 → 角色显示/说话 → 用户回复进入同一会话。
5. 验证关闭共享、后台、重复、掉线、导航期间推理、静音和冷却；有真实可观察回执后才能把状态改为 LIVE_CONNECTED。

## 7. 未解决/未验证

- 目前只有源码增量；已交付的旧 EXE 不包含本轮接口，GitHub/Drive 未写入或推送本轮改动。
- dot 身份、Live 项目与 Windows 使用端已由用户确认；真实模型、插件订阅、Live 文本/对话适配器仍未绑定。本轮没有建立一个可直接日常使用的完整产品。
- 真实浏览器截图仍能看到《当代中国经济》教材已有的 OCR 杂字。textEqual/排版指标通过只说明没有丢字、几何溢出或新增重叠，不证明正文校对完成，也不证明商业书宋字体已落实。
- PDF 的正文质量、12px 审计问题与后续 PDF 阅读路线仍属于此前问题清单；本轮不修改教材内容和 PDF。
- Android APK、同签名 Book AAR、真机、麦克风、TTS 与当前 mygpt 的发布阻断项，不由这个 Windows 源码样本替代。

## 8. 四角色与使用说明

沿用 outputs/MODIFIED_FILE/document-reader.js、outputs/DIFF_FILE.patch、outputs/VERIFICATION.txt、outputs/ROLLBACK.sh。新增的 book-desktop、mygpt 文件是这些角色的扩展，不替代它们。完整绝对路径和哈希在联动 manifest 中。

ROLLBACK.sh 接受一个目标副本文件或目录，依赖同目录的 BASELINE_*。目录回滚恢复三份阅读器文件、已有 book-desktop/main.go 与 mygpt/host-binding.json；不删除新增加的适配器源码。直接回滚 main.go、host-binding.json 也支持。先关闭共享再更换实际程序，修改副本保留待验证版本。

安装该 mygpt 模块时放入固定源的 brain/mygpt_brain/book_progress.py；宿主负责真实 dot 认证与 renderer 会话。测试可用 MYGPT_SOURCE_ROOT 和 BOOK_PROGRESS_FIXTURE 指向固定源与实际生产器样本，不需要修改测试输入。

补丁按 UTF-8/LF 生成。重构副本的命令使用 git -c core.autocrlf=false apply DIFF_FILE.patch，避免 Windows 全局 CRLF 设置改变字节哈希；不能只比较去掉换行差异后的文本。

## 9. 本次确认：Your dot / Jvust1/Live / Windows

用户回复“是，是，在电脑”，对应上轮三个身份/运行端问题。已写入同一修改副本的 host-binding.json：dot_kind=codex-your-dot、live2d_project=Jvust1/Live、runtime_host=windows-desktop。没有据此把任何连接标为成功，也没有读取或写入账号凭据。

### dot 的真实路线

[官方 MCP Events 文档](https://developers.openai.com/plugins/build/mcp-events) 明确支持 dots 使用已注册插件的事件订阅。协议为 MCP 2.0 / 2026-07-28，采用经验证、签名的 HTTPS webhook；接收 2xx 只表示事件已收，不表示 dot 已作决定。异步处理可能批量合并事件，所以不能承诺每次翻页都即时回应。

新增 dot_events.py 只实现严格事件结构与单槽准备队列：书/章/模式/暂停/关闭变化立即可发送；同一章节例行进度合并，默认最多每 30s 一个，mygpt 本机仍可每秒读取最新进度。重复重试保持事件 ID，旧回执不删除新事件，超时清空，关闭共享生成无上下文 tombstone。它**不发送网络请求、不是 MCP 服务、不创建订阅，也不能充当 DotPort**。相应 9 项单元测试通过，但测试的消费者是合成的。

15s 的 Book 租约仍有效。云端旧事件只能作为唤醒线索，实际决定前必须重新读当前进度；决定与展示仍受会话、序号、前台状态和撤销保护。不能通过延长旧租约或自动刷新旧决定来让迟到的回复强行显示。

[dot 的本机访问说明](https://learn.chatgpt.com/docs/dots/computers-and-apps) 要求在 dot 资料页单独连接电脑；这里仅确认用户运行端是电脑，尚未核验此权限。Codex 本机连接不等于 dot 已获本机访问。

### Live 的实际接口审计

- 插件读取 main@e31e8a040989e31573378e5fc821b87d5071010b，其完整树只有 README.md 与更新报告。
- 继续读取 feat/live-spine-2949027723-20261001@4baf39bf67a0ac28a2bb0e5e57c4ebb0f72887a8，完整树 114 项。读取 AGENTS、治理状态、North Star、约束、决策/评测记录、交接与 manifest；旧文档中的账号/分支标签未覆盖实际确认的仓库身份。
- pet-preload.js 暴露角色预览、Spine、动作、视觉资源读取、拖动与菜单 IPC。pet.js 的 Talk 调用 playNextTalk()，只是预制动画；不能当成接收模型文字或生成语音。
- inspected main.js 保持渲染器隔离与网络阻断。上述当前接口没有 mygpt 文本展示入口、带 message_id 的显示回执、同会话用户输入或 TTS。需要新增最小适配器，而不是填一个不存在的端口。
- 没有修改已安装 Live 或素材，没有启动角色画面。Drive 精确文件名检索未回读到 Live-win-294-fixed.zip，这不是文件不存在的证明，也未下载一个其他版本来冒充。

真实宿主检查已执行：确认前缺 6 个项，确认身份后缺 4 个项（Book origin、dot adapter、Live adapter、provider），均 exit 2。当前真实 dot/LLM/角色画面仍为 0。旧 EXE 不包含联动改动，不能用本次源码测试声称发布版已经连通。

机器可读接口审计保存在同一源码角色扩展中的 host-interface-audit.json。下一步只补认证插件/回调、Live 的对话适配器与实际模型绑定，然后重建 Book 跑真实一章链路，不回退为泛泛项目规划。

