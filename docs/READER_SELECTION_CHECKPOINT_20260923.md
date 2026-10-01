# r6 明确选段 → Brain v2：实现与验收检查点

状态：**OFFLINE_READER_SELECTION_PASS / REVIEW_PENDING / LIVE_BOOK_NOT_CONNECTED**。
本轮日期：2026-09-23（+08）。当前开发仍在 `Jvust2/mygpt` 的 `feat/book-contract-audit-v1` / PR #6；不合并 PR，不修改 Book 或 main。

## 1. 这次真正完成的闭环

```text
合成的 r6 manifest + section response
      + 明确选择的 record / layer / hint-or-solution
      + 宿主模拟 session / epoch / captured_at / expires_at
                          ↓
                  map_reader_snapshot
                          ↓
         ReaderStudyContext v2 + transient EvidenceText
                          ↓
               Brain 会话 / 静默策略 / 显式求助
                          ↓
           TestModel 固定回复 / 内存 MCP 只读工具
```

实现提交：`86734b51024a4f0ae7c254835c9fe0178151bee3`；实现 tree：`4e08bdf159611fd11e07fa8210187e12a8ef7f6c`。
基线：PR #6 原 `41277d24498d1d2a122b100bb68a38cf30ca62dd`。这次复用了旧静态校验器，并实际在同一套测试中验证新旧组合；不是把多批测试数字相加。

`brain/mygpt_brain/reader_snapshot.py` 负责当前 r6 映射；原 `book_contract_audit.py` 继续仅用于旧 Web DTO 静态检查。两套输入不可混用。历史审计文档中的“先确认宿主”已推进为以下源码身份核验，但仍不代表用户手机实际安装身份已确认。

## 2. Book 宿主与原件身份

本轮重新核对 Book PR #33 的 CURRENT 检查点，完整取得 r6 源码 ZIP：

- Drive ID：`1UiVow02Huh3r8qKBH8v4bL3D9OfkQ8_R`。
- 文件：`Book-App-Source-CURRENT-r6-20260922.zip`，70,090,018 bytes，1,555 个成员。
- SHA-256：`19315e8aeebe2db5cf2f4b55e0a38f550967966af106491dfef67212b430adc1`。
- 参考 GitHub 检查点：`7283f2eef7610d67c6b92b2ef7c513e1225ad957`，`governance/two_courses_current_app_source_20260922_1054.json`。

选择性核对 7 个成员的大小及内部 manifest 哈希：Reader API、reader.js、课程 catalog、两门课程 manifest、AndroidManifest.xml 与 MainActivity.java。全部一致。Reader 使用 `/api/reader/course/{cid}` 与 `/api/reader/section/{cid}/{sid}`；Android 源码的 WebView 入口是 `http://127.0.0.1:8765/`，不是额外安装了 mygpt 插件的证明。

**核验边界：**确认的是当前正式登记的源码原件及宿主代码，不是手机已安装 APK 的实测身份；未下载/重新验签 APK，未运行 Book API、未读取用户笔记、未写 Book，未复制教材或 Book 源码到 mygpt。原 APK 检查点的离线重打包说明继续有效，不改称 clean Gradle rebuild。

## 3. 版本兼容而不改写历史

新增 `mygpt.reader-context.v2`，只有这个显式版本允许已观察到的 `@` 版本格式，最大 160 字符。原 v1 Identifier、`book:...` 引用和旧收据不变；不支持的版本字符明确拒绝，不删除字符、不截短、不把不透明版本猜解成日期。

v2 引用以 `reader:v2:` 开头，分别编码课程、书籍、版本、小节、记录类型、记录 ID、内容层、层 ID、序列化版本及正文 SHA-256。相同记录的原文、校正、推导或变更后的字节具有不同引用。上下文协议版本进入会话身份，因此同一会话不能悄悄从 v1 切到 v2。

SQLite 表结构仍为原方案，JSON 上下文根据显式版本解析；旧数据不迁移、不重算哈希。新代码能读旧上下文；旧代码不能读 v2，回滚应用版本前应使用新数据库或保留对应升级前快照，不能把旧程序拒绝新上下文理解成“可以清库”。

## 4. 明确选段规则

`ReaderSnapshot` 只接受 `SIMULATED / book-r6-demo`。调用者必须额外传入自己持有的当前 `expected_session_id` 与 `expected_epoch`，不能无条件从数据包复制这两个值充当可信当前状态。

`ReaderSelection` 要求课程、书籍、教材版本、小节、记录 ID 和层级。manifest、section response 与选择的版本必须一致；小节必须属于课程目录，记录必须属于小节，重复 ID 拒绝。没有选择时即使只有一条记录也不擅自选中。最多 4,096 项目录/记录身份；这是有界投影，不是完整 Reader DTO 验证。

快照时间必须带时区、规范化到 UTC，生命周期在 (0,300] 秒；当前时间不在窗口内、旧 session/epoch 均拒绝。宿主 epoch 只判断当前快照，**没有冒充 Brain 的持久事件序号**。

### 三个内容层

| 选择层 | 本轮实际行为 | 不会做什么 |
|---|---|---|
| `source` | 传递记录原始 title 和 parts | 不悄悄套用 render_text、render_latex、source_completion 或校正 |
| `correction` | 明确 correction ID；核对课程/小节/原记录/保留原文，以及唯一满足既有强证据展示条件的候选 | 不把 HIGH 当概率，不把 CHECKED_BY_ASSISTANT 当独立验收或官方勘误 |
| `derived` | 明确 practice group、锚点和 hint/solution；核对组内原记录、来源小节及非官方标记 | 不把推导写成教材原文，不自动抓取所引用的整章 |

校正的原文绑定依据包括 `original_title`、`original_parts` 与当前来源一致，以及 r6 已有展示条件。没有把未经重新校验的 `source_signature_sha256` 当成已验证签名。当前检查的是结构/来源绑定，不证明数学正确性。

`derived` 目前只支持已观察到的 practice_groups 下 guidance，且 source_record_ids 必须与组记录精确一致；不符合这个受限合同的变体直接拒绝。completion、候选 MEDIUM 校注、跨小节多段拼接和视觉选区不在本轮支持范围。

## 5. 正文序列化与隐私

正文不是随意拼接的字符串，而是 `reader-selected-json-v1` 的固定 JSON：保留 text 与 math 的顺序、LaTeX 和 display 标记，带层级标签、题目约定及来源元数据。使用 UTF-8、非 ASCII 原样输出、键排序和固定分隔符；不做 Unicode 归一化、截断或正文纠错。SHA-256 针对**实际交给 EvidenceText 的完整字节**，不是 PDF 哈希或 ZIP 哈希。

校正/推导还携带 `parent_sources`，记录相关原始记录投影的哈希，避免“上游原文变了、引用却沿用”这种错误。最多 32 个父记录、96,000 字节父来源投影；正文最多 512 个 text/math 片段，最终 JSON 最多 12,000 字符/48,000 UTF-8 字节。超限拒绝而不裁剪。

图片不上传、不识别；有文字且关联图片时标记 `IMAGES_NOT_INCLUDED`，只有图像/不支持片段时拒绝。原文若另有显示校正/补全，会标注 `DISPLAY_MAY_USE_ANOTHER_LAYER`；此版不能号称与屏幕最终渲染逐字相同。

额外笔记、密码字段和未白名单元数据不会被拷贝到结果。正文只在内存中传递，Brain 只持久化上下文引用、哈希和事件/决策，不把教材正文或私人笔记入库。自行把完整结果写日志仍是调用者应避免的行为；这不是自动识别任意秘密的 DLP 系统。

## 6. E006 — 本轮真实验证

[GitHub Actions run 35797671670](https://github.com/Jvust2/mygpt/actions/runs/35797671670)，job `106980616735`，检出精确实现提交 `86734b5`。

| 环境 | 结果 |
|---|---|
| 本地基线（已有 Brain + 旧 DTO 校验器） | 162 passed / 2 skipped |
| 本地最终代码 | 264 passed / 5 skipped；本机缺两个 SDK，不冒称通过 |
| 远端第一个干净环境 | **269 passed / 0 skipped / 0 failed，2.12s** |
| 同一哈希锁重装到第二个干净环境 | **269 passed / 0 skipped / 0 failed，1.55s** |

远端 Ubuntu 24.04 / CPython 3.13.15，沿用原 39 包 wheel 哈希锁及 Pydantic 2.13.4、pydantic-ai-slim 2.46.0、MCP 2.2.0。pip check、旧/新演示、compileall 和证据上传全部成功。CI 只新增 PR #6 的字面分支匹配及一条 Reader 演示命令；contents:read、固定 Action 提交、精确 checkout、十分钟上限、测试网络 guard 均保持。

三种内容层分别实测 TestModel 输出引用、MCP 结构化上下文、完整教材版本、层级和字节哈希。测试还覆盖旧 v1 默认字段/引用、跨协议会话拒绝、v2 落盘重启、旧证据失效、原始父来源变化、非法选段、过期、重复、静默与暂停。

本轮原始 CI artifact：`10724052652`，106,134 bytes；下载 SHA-256 与 GitHub digest 一致：
`a46aaa29d273fefe06017f2f6383d1c33e1c02797f78856b3359f5e4515ad193`。
逐项读取两份 acceptance.json、JUnit、pytest 原始输出和 source-commit.txt，结果一致。原始 ZIP 保存在本轮 Drive 恢复包中，不靠三天保留期维持长期证据。

**TestModel 是固定程序输出，不是真实教学回答。** 269 项是本次组合 Brain 套件，未重跑根目录 Jonah 浏览器/图集套件；没有 Android、真实 Book feed、HTTP 鉴权或独立代码审阅结果。

## 7. D018 — 路线对齐与当前限制

当前集成目标确定为 r6 Reader，而非 PR #6 初始核对的旧 ModeResponse/SourceResponse。这不是否定旧审计，而是明确它只作旧 Web 接口参考。本分支没有复制或覆盖 PR #5 正在维护的代码/文档；PR #5 的 SDK-green 事实通过继承代码与现有证据得到确认，本轮新状态在本分支独立落账。

明确完成：版本化来源映射、三层选择、数据契约与合成闭环。尚缺：Book 侧真实选择/事件导出、可信宿主握手与可撤销授权、真实调用预算、宿主 UI 与 Jonah 联动、设备生命周期和安卓实机。输入自报 SIMULATED 不证明现实已获授权，任何未来正式入口都需另做版本和认证合同，不能仅替换字符串启用。

## 8. 恢复与唯一下一步

```sh
cd brain
python -m mygpt_brain.reader_demo
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_asyncio.plugin -q
# 在与现有 Linux CPython 3.13 锁兼容且允许安装依赖的环境：
python scripts/verify_integrations.py --output /new/evidence/directory
```

演示、测试和 Schema 均使用合成文本，不需要用户上传教材。精确依赖安装参见 requirements-linux-py313.lock 和既有 CI；本地缺 SDK 时普通测试会跳过，严格脚本必须失败。

**唯一下一步：** 在 mygpt 自己的宿主演示中接入明确选择与“解释这段”操作，展示版本/层级/失效状态并与 Jonah 用户事件联动；先用合成事件做交互验收。Book 侧最小导出器、授权及真实联调在此后进行独立 preflight，不在本轮默认开放网络服务或修改 Book。

正式恢复入口：本文件和 governance/project_state.json；归档精确 ID/哈希在 governance/artifact_manifest.json。旧的 CURRENT/HANDOFF/Brain README 内容保留为历史，最新前置入口覆盖旧 SDK 阻塞和旧 next_step。独立审阅保持 PENDING，PR #6 保持 Draft / UNMERGED。

参考：Pydantic 官方配置说明 https://pydantic.dev/docs/validation/latest/api/pydantic/config/（嵌套模型需各自设置 revalidate_instances）。这里采用既有固定依赖的实际测试确认行为，不复制第三方源码、不以网页声明代替本项目验收。
