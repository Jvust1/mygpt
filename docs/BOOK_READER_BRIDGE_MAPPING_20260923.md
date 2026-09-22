# Book r6 → mygpt 接口映射与缺口

状态：`SOURCE_INSPECTED / CONTRACT_DESIGN_ONLY / LIVE_NOT_CONNECTED`。
日期：2026-09-23（+08）；本轮只读 Book，不改代码、不调用服务、不读取实际学习笔记。

## 1. 先明确目标，不把三条版本线混在一起

Book 默认分支的 `governance/project_state.json` 仍描述较早的 Phase 1H 准备状态。本轮从开放 PR 重新定位到 [PR #33](https://github.com/Jvust2/Book/pull/33)，其 `data/two-courses-r3-checkpoint-20260921` 在本次观察时为 `7283f2eef7610d67c6b92b2ef7c513e1225ad957`。

该提交的 [CURRENT 源码检查点](https://github.com/Jvust2/Book/blob/7283f2eef7610d67c6b92b2ef7c513e1225ad957/governance/two_courses_current_app_source_20260922_1054.json) 指向：

- Drive CURRENT：`1UiVow02Huh3r8qKBH8v4bL3D9OfkQ8_R`。
- 文件：`Book-App-Source-CURRENT-r6-20260922.zip`。
- 整包 70,090,018 bytes，1,555 个 ZIP 成员。
- SHA-256：`19315e8aeebe2db5cf2f4b55e0a38f550967966af106491dfef67212b430adc1`。
- 内容基线 r6-batch5，界面修订 `continuous_dense_no_inline_provenance`。

本轮通过 Drive 完整取得字节，整包 SHA-256 与该检查点相同。只展开必要接口文件；7 个选定接口/目录/课程清单成员与内部 manifest 的大小、SHA-256 均一致。没有重新全量校对教材，没有复跑 Book/Android 测试，不将检查点记录的旧测试当成本轮结果。

**关键区别：** GitHub 可读的 `app/api/models.py` / Web API client 与 r6 源码包里的独立 `app/reader/api.py` 不是同一个消费者契约。r6 Reader 自己声明不迁移原 `/api/library`、Golden 数据或 StudyRecord。第一条真实桥接应面对 r6 Reader，不应以旧 `/api/study/recent` 冒充当前阅读位置。

## 2. 真实 Reader 已有的读取端点

下表直接来自本轮已验证的 `app/reader/api.py`，不是已经部署到 mygpt 的服务：

| 实际路径 | 实际用途 | 第一版是否需要 |
| --- | --- | --- |
| `GET /api/reader/catalog` | 课程目录，schema 为 `reader_catalog_v1` | 是，读取允许课程 |
| `GET /api/reader/course/{cid}` | 课程 manifest，含 `book_id`、`book_version_id`、小节目录和质量标记 | 是，版本与身份绑定 |
| `GET /api/reader/section/{cid}/{sid}` | 小节、`records`、分组；服务附加 `book_version_id` | 是，按需取当前小节 |
| `GET /api/reader/search/{cid}` | 在已有转录正文中搜索，返回小节与 `record_id` | 可选；不是当前活动状态 |
| `GET /api/reader/state/{cid}/{sid}/{mode}` | 本机笔记、答案、自评、完成标记及修订 | 初始默认不接入 |
| `GET /api/reader/export` | 新阅读器全部笔记导出 | 不作为上下文读取入口 |

`read_state` 和 `export_notes` 会调用 `db()`，其中存在目录创建、数据库表初始化；HTTP GET 标签不等于实现上无副作用。更重要的是这些端点包含私人笔记/作答，不能为了获取章节而无差别读取。

`POST /api/reader/state/...` 要求 `X-Book-Reader: 1`、检查 Origin，并按 `book_version_id + expected_revision` 防止覆盖。**这不是跨进程用户认证方案**；不能把一个固定 header 当成 mygpt 的访问凭据，也不能绕过已有写入检查。初版桥只提供明确允许的读取，不替用户保存笔记或改完成状态。

## 3. StudyContext 字段对应表

| mygpt 字段 | r6 已确认的来源 | 处理决定 / 尚缺什么 |
| --- | --- | --- |
| `course_id` | `state.course.course_id` / manifest `course_id` | 可精确映射，不从标题猜测 |
| `book_id` | manifest `book_id` | 可精确映射 |
| `book_version` | manifest 与 section response 的 `book_version_id` | 必须保留原始版本身份；当前 Brain 标识符规则不兼容，见下节 |
| `section_id` | `state.section.id` / section `id` | 可精确映射；必须已属于该课程目录 |
| `mode` | `state.mode` | 四个值恰好对应 preview/learn/review/practice |
| `source_id` | 当前**明确选择**的 `record.id`；分组含 `record_ids` / `anchor_id` | Reader 没有对外暴露唯一当前选中记录。连续正文同时有很多记录，不能从第 1 条或第 1 个可见元素猜“这里” |
| `source_sha256` | 尚无统一、直接可用的“本次传给模型的文本字节哈希”字段 | 原 PDF 哈希、转录文件哈希、整包哈希均不能替代它。先定义文字/LaTeX 序列化与 source/correction/derived 分层，再计算实际 UTF-8 字节 |
| `session_id` | 当前 Reader `state` 没有会话 UUID | 由批准的宿主桥创建并绑定设备/页面实例，不从最近笔记时间猜 |
| `captured_at` / `expires_at` | 现有 Reader 未输出这组采样时间 | 由桥的实际快照捕获时钟产生；静态包生成时间不是当前阅读时间 |
| `producer_id` | 当前仅有原型 `book-demo` | 正式入口需要可信宿主身份/认证，不能只改成字符串 `book` |

### 真实版本号暴露出的兼容问题

从两本课程 manifest 实际读到：

```text
mathematical_physics_equations_4e@dd824886902c6082
functional_analysis_2e_jiang_sun@146e613d41bdc0b4
```

mygpt 目前将 `book_version` 复用受限 Identifier，正则不允许 `@`，长度也只到 96；Reader 的笔记版本字段则允许最长 160。**所以目前原型不能直接吃这两条真实版本号。**

下一步应为版本定义独立、保留不透明原值的类型，明确长度及允许字符，并回归分隔符、碰撞、序列化和来源引用。不能简单删除 `@`、截短、只留下 hash 尾部，不能用通用“清洗 ID”让两个不同版本合并。该修改尚未实现；本轮 green 仍是原模拟契约的 SDK 验收。

### 来源与显示层不能混淆

Reader 支持来源 `parts`、分层 `corrections`、`derived_guidance` 等结构。`reader.js` 对符合指定证据条件的 correction 可以优先展示，但保留原始记录。某些记录上的 `source_pdf_identity_sha256` 标识 PDF，`transcription_sha256` 标识转录文件，并非当前选段。

候选桥应携带 `layer = source | correction | derived`、`record_id`、实际传输正文 SHA-256 和关联证据，不应把 AI 推导标成教材原文。显示层隐藏 provenance 标签也不意味着来源数据可以丢弃。语义正确性仍需教学验收，引用/哈希通过不能替代它。

## 4. 宿主事件的真实接入点与限制

本轮已读取 `reader_assets/reader.js` 中这些实现：

| 实际代码位置 | 已有行为 | 候选桥接点（尚未实现） |
| --- | --- | --- |
| `openCourse` | 获取 manifest，选择课程和模式，然后加载小节 | 完整加载成功后建立/替换会话；不能在请求尚未完成时声称已切换 |
| `loadSection` | `state.epoch` 递增；取 section 与笔记；忽略过期请求；成功才更新 `state.section` | 使用同一成功分支发上下文事件，绑定 epoch，拒绝迟到响应 |
| `switchMode` | 先保存，再修改 mode 并加载小节 | 只在新模式加载成功且上下文一致后发事件 |
| `jumpTo(id)` | 查找记录，切页并聚焦 | 可成为明确选段候选之一，但仍应区分导航与用户求助 |
| `back-courses` | 隐藏工作区并切回目录 | 结束/断开上下文，不沿用上一节 |
| `beforeunload` | 当前只处理未保存修改提示 | 后续宿主结束/暂停机制单独设计，不强行假设卸载事件一定送达 |

当前 `state` 位于闭包，已有 `epoch` 解决的是页面请求竞争，**不是可持久重放的 StudyEvent 序号**。现有代码没有专用 mygpt 事件流、会话 UUID、签名/鉴权、跨进程重同步合同。不能把 `epoch`、笔记 `revision` 或历史更新时间挪用为消息序号。

页面一次可显示多条正文，所以第一版最小产品建议是：**明确选择一条记录 → 点击“解释这一段” → 在有效上下文内只读传递这一段。** 不先做高频滚动追踪、摄像头/屏幕识别或自动推断卡住。

## 5. 下一实现批次的最小范围

仅在 mygpt 非默认分支新增 `ReaderSnapshot` 候选契约、严格映射器和合成 fixture；不改 Book、不开模型预算、不自动运行服务。先做版本兼容修正和层级/身份绑定；再用已知结构的合成记录回放，不复制真实书籍正文。

预期至少覆盖：真实格式含 @ 的版本号、版本不一致、小节/课程不匹配、未选择记录、多个候选记录、选择的记录不存在、空正文/只有图像、来源/修正/派生混用、过期快照、迟到 epoch、重复事件、暂停/关页、权限撤销、未经批准的 URL/路径和旧 StudyRecord 混入。

这一批通过后，才另做 Book 宿主侧发事件设计与非默认分支 preflight。mygpt 侧字段准备好不代表 Book 一方已批准变更。第一条真实链还需要实际端点地址、可信宿主握手、可撤销授权和实体设备证据。没有这些就继续标 `SIMULATED`，不把源码读通说成已接通。

## 6. 可恢复的证据身份

原件仍在 Book 自己的 Drive 目录，不复制进 mygpt。

| 原包内文件 | SHA-256 |
| --- | --- |
| `app/reader/api.py` | `b1a63c7ca635336a05dbbfa0bd570556d015cb988a4d691c7ffdb5e4c60bfe30` |
| `reader_assets/reader.js` | `26d17fa12ba00ffbc6d9536d10fc4f478f4640543c4e09026c13788b1aab55f8` |
| `app/api/models.py` | `cf18ecaf9b0ea81dabdb6b186635382bf5ec896364306921f0b09795512c8a00` |
| `app/api/main.py` | `879777458ecac3c4a4af1e8dac262c4ec7930d3c853b2da94251e9258e084724` |

完整的 7 项选择性校验元数据在本轮 SDK 证据包 `evidence/book-interface-evidence.json`。这不是全库源码审查、Book 运行验收或权限审计。没有修改原包、教材、用户笔记、安全策略或任何 Book ref。
