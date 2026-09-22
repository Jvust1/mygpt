# Book → mygpt：真实字段核对与只读接入准备 v1

状态：**STATIC_CONTRACT_AUDIT_CANDIDATE**。这是接口核对、纯函数校验器及测试，不是实时 Book 桥，也不是 Android 成品。

候选分支：`feat/book-contract-audit-v1`。基础代码采用 mygpt `95fd2846f5ec535b1241b4bb565fbca92eda626e`。该提交的 SDK 验证已在远端实际通过；本分支不回写正在并行更新的 PR #5 分支，也不改 Book。

## 1. 已验证的 SDK 基础与证据边界

本轮实际读取了 [run 35762870487](https://github.com/Jvust2/mygpt/actions/runs/35762870487) 的 job `106865005363` 完整日志，并确认检出精确提交 `95fd2846f5ec535b1241b4bb565fbca92eda626e`。

| 验证环境 | 结果 | 能证明什么 |
| --- | --- | --- |
| Ubuntu 24.04、Python 3.13.15，第一个隔离环境 | 113 passed，0 skipped，2.17s | 两个真实 SDK 与已有 Brain 测试一起通过 |
| 按 39 包 wheel 哈希锁安装的第二个干净环境 | 113 passed，0 skipped，1.36s | 本次 Linux/Python 3.13 依赖组合可重复安装并通过 |
| 两个环境的 pip check | 均无依赖冲突 | 安装依赖关系通过检查 |
| 演示与 compileall | 成功 | 对应模拟演示和语法检查通过 |

Pydantic AI 使用程序式 TestModel；MCP 使用内存 Client/Server。以上不证明真实模型回答正确、Book 实时事件已接入、Android 实机可用、HTTP 鉴权有效，也不是当前新增校验器的全仓库回归结果。

前两次失败没有抹去：`1b40418` 的提交说明记录了第一次 ListToolsResult 迭代错误；本轮另行读回 run `35762614414` 的原始日志，确认第二次是 `structured_content=None`，112 passed / 1 failed。`95fd284` 改为类型明确的 `dict[str, Any]` / `list[dict[str, Any]]` 并强制 `structured_output=True`，没有用文本回退掩盖错误。对应 [修复提交](https://github.com/Jvust2/mygpt/commit/95fd2846f5ec535b1241b4bb565fbca92eda626e)。

远端成功证据 artifact ID `10711455709`，101061 bytes，GitHub 日志报告 ZIP SHA-256 为 `b7cae531acefa9d648c85f83be83417914a161bac18876e2e9f457f846d04cd1`。本核对包只保存日志关键行摘录与结构化核验记录，**没有把摘录冒充完整的 Actions ZIP，也未自行下载验证该 ZIP 的字节哈希**。该工作流只保留 artifact 三天，正式归档以项目后续 manifest 的真实 Drive 回读为准。

## 2. 本次读取的 Book 代码身份

Book 参考分支：`data/two-courses-r3-checkpoint-20260921`；本轮固定读取提交 `7283f2eef7610d67c6b92b2ef7c513e1225ad957`，而不是跟随变化的分支名读取混合版本。

**这是已读取的 GitHub 接口代码快照，不是对手机当前安装的 r6 APK 或全部分支的最新性认证。** 默认分支治理仍含旧阶段记录，候选分支状态文件也保留了历史章节；因此本轮不把某一条旧状态当作所有 Book 交付物的当前状态。真正联调前必须核对目标宿主的构建身份和这组接口是否同源。

| 文件 | Git blob SHA | 本轮用途 |
| --- | --- | --- |
| [app/api/models.py](https://github.com/Jvust2/Book/blob/7283f2eef7610d67c6b92b2ef7c513e1225ad957/app/api/models.py) | `70a54b22ea55cd1b75b1a35cc756349ff033eac8` | 读取至 SourceResponse 的 DTO 定义，核对实际字段 |
| [app/web/src/api/client.ts](https://github.com/Jvust2/Book/blob/7283f2eef7610d67c6b92b2ef7c513e1225ad957/app/web/src/api/client.ts) | `e6f6fd0ee20249c4c6dcb0d1a78cf7c624e86b47` | 客户端真实方法、路由和 GET/POST 边界 |
| [app/web/src/state/sectionViewState.ts](https://github.com/Jvust2/Book/blob/7283f2eef7610d67c6b92b2ef7c513e1225ad957/app/web/src/state/sectionViewState.ts) | `4388f81fb71fab5349596025399df9eb6193c67c` | 页面恢复状态四字段与 course/section/mode 键 |
| governance/project_state.json | `3cc0a24361b486f4a7d7f3d36f6708d0777fed5f` | 确认冻结字段与独立 Human Gate，不据此假称当前手机版本 |

这些材料通过 GitHub 连接器实际读取；没有调用 Book 运行中的 API，没有读取用户手机的 sessionStorage，没有复制教材正文到 mygpt。

## 3. 字段映射：已经有的和不能凭空补的

| Brain 所需信息 | 已看到的 Book 字段 | 核对结论 |
| --- | --- | --- |
| course_id | ModeResponse.course_id；SourceResponse.course_id | 可做精确一致性检查 |
| book_id | ModeResponse.book_id；SourceResponse.book_id | 可做精确一致性检查 |
| section_id | ModeResponse.section_id；SourceResponse.section_id | 后者允许 null；未知时不能从另一个响应猜填 |
| mode | LearningMode / ModeResponse.mode | 四种实际值为 preview、learn、review、practice |
| 来源身份 | SourceRef(kind, source_id)；ModeItem；SourceResponse | **必须保留 kind 和 source_id 两部分** |
| 章节展示版本 | presentation.schema_version = learning_slice_v1 | 这是展示契约版本，不是教材版本 |
| 教材版本 book_version | 上述 ModeResponse/SourceResponse 无对应字段 | 必须由可验证的内容版本/manifest 提供；不拿 App 版本或任意 Git SHA 顶替 |
| source_sha256 | 上述 DTO 未直接提供 | 先确定正文/公式/翻译的序列化与来源身份，再核验；不能随意拼接后称原件哈希 |
| session_id、event_id、sequence | 上述 DTO / 页面恢复状态无对应事件信封 | 需要宿主与 Brain 单独约定，不改 StudyRecord 的冻结结构 |
| captured_at、expires_at | 上述 DTO / 页面恢复状态未提供这组语义 | API 响应被读取不等于用户当前正在看；必须有会话边界、有效期和断开规则 |
| 当前选中的来源 | 页面恢复状态 activeSourceId | 只有 ID，不能在 kind 不明确时直接选中第一条匹配项 |
| 当前是否专注 | 无此事实字段 | 不根据停留、后台或静止推断心理状态 |

Brain v1 使用受限 ASCII Identifier，并且 `reference` 不含 source_kind。Book DTO 则声明普通字符串。校验器保留 Book 的原始 Unicode/分隔符，不偷偷改 ID，同时报告不能直接放入 Brain v1 的字段。解决这些差异需要一个显式的新契约版本或可逆映射，不能修改旧收据含义。

## 4. 已存在的读取接口与禁止混用的写操作

已读取客户端实现中的只读方法：

```text
getSection(courseId, sectionId)
GET /api/courses/{courseId}/sections/{sectionId}

getMode(courseId, sectionId, mode)
GET /api/courses/{courseId}/sections/{sectionId}/{mode}

getSource(courseId, kind, sourceId)
GET /api/courses/{courseId}/sources/{kind}/{sourceId}
```

每个路径段由 encodeURIComponent 编码。未来适配器必须保留分段和 kind，不直接拼接未经编码的 ID。

`touchStudy`、`completeStudy`、`importStudy` 和 `askCourse` 都使用 POST。不能为“获取上下文”自动调用它们；尤其不能因为 mygpt 查询一章，就制造一次用户学习记录或模型问答。`getRecentStudy` 只是最近记录，不足以证明当前章节。

页面恢复合同只有 `route / scrollY / expandedSourceIds / activeSourceId`。本轮不增加字段、不重写历史数据，不把这个页面缓存当成可靠事件流。

## 5. 本轮新增的可执行部分

`brain/mygpt_brain/book_contract_audit.py` 提供：

```python
report = audit_book_identity(mode_response, source_response, selected_source)
```

输入为**调用方显式提供的 JSON 对象**。selected_source 必须含 kind 和 source_id。函数检查课程/书籍/小节一致、四种模式和 learning_slice_v1 一致、选中来源同时属于 items/source_refs、重复来源对和大小/类型边界；只返回允许的身份元数据，不返回教材正文、公式或额外私密字段。

输出中的 `identities_match=True` 仅表示选中的身份相符；`live_ready` **始终为 false**。它不做完整 Book DTO 校验、来源真实性证明、全列表引用闭包验证或权限判断，不连接实时 Book，也不创建 StudyContext。网络/模型调用均为零。

尚未确认的接入能力固定列出：认证与授权的生产方、明确的当前视图选择、会话及有序事件、教材版本、约定来源字节/哈希、时间/断开协议，以及 Brain 来源引用保留 kind。传入 `authenticated=true` 等额外字段不能绕过这些缺口。

最小运行测试：

```sh
cd brain
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_book_contract_audit.py -q
```

Windows 可先设置同名环境变量再执行 Python 命令。测试只需 pytest；没有自动安装依赖的行为。

## 6. 真实验证结果，不能相加冒充全量结果

新增校验器的本地测试：**51 passed，0 skipped，0 failed**。案例是按已读取 DTO 制作的合成子集，不是录制的用户学习会话，也不是调用真实 API 得到的响应。覆盖四模式、跨课程/书籍/章节、空章节、显式选择、kind 碰撞、重复来源对、缺失引用、错误版本、异常类型、Unicode/分隔符、额外权限声明、正文最小化和输入不变性。

它与基础提交的远端 113 项结果分开报告。**本轮没有在新组合提交上执行 164 项完整测试，没有在新分支触发远端 CI，也没有进行独立代码审阅或安卓真机验收。** 继承的工作流目前只监听原 PR #5 分支；没有为了取得绿勾扩大工作流权限或触发额外计算。

## 7. 并行更新处理

本会话最初基于旧提交 cf998db 编写了另一套 SDK gate，并得到 169 passed / 2 skipped（新增 74 项 verifier 测试）。创建 Git commit 对象 `9f803155df061c9b1d02598c713387c773ab20ac` 后、更新 ref 之前，检测到远端已前进，且相同脚本路径已被并行实现。

因此没有把这个旧 tree 推入任何分支，没有覆盖并行实现。上述 169 项不计为当前 PR #5 验收，也不计为本校验器验收；本轮留有标明 UNADOPTED 的候选证据供选择性参考。已采纳的基础始终是有真实 SDK 日志的 95fd284，而不是测试数量更多但缺少 SDK 的旧候选。

这个新增候选只放到独立分支和独立 Draft PR。PR #5 的 body、共享 project_state 和现有 gate 不被本候选覆盖。`governance/book_contract_audit_v1.json` 记录本候选恢复入口和 artifact 身份；它不是对全项目主线的单方改道。

## 8. 下一步：只选一个真实宿主，先打通显式取上下文

下一项建议是核对目标 Book APK/Web 宿主的构建身份，确认与本次 DTO 同源，然后设计其最小、显式触发的只读上下文输出。优先验证“用户选中这一条来源 → 身份/正文版本校验 → mygpt 展示当前来源”，不抢先做后台常驻、全局截图或自动监督。

联调准备必须确定：

1. 版本来源：目标 Book 构建、内容 manifest 和所选条目的身份绑定。
2. 选择语义：明确 kind/source_id；activeSourceId 歧义时询问或拒绝，不默认取第一条。
3. 事件生命周期：新会话、序号、更新有效期、断开及恢复；旧上下文不能当当前内容。
4. 字节合同：正文、公式、翻译分别如何引用/序列化；哈希验证针对同一份字节。
5. 传输与授权：同宿主/本地适配器优先；不自动开放监听端口，不复制提供方凭据。
6. 验收：重复/乱序、跨书同 ID、过期、关闭权限和切换章节后的回调均须有测试；接入前仍只接受模拟测试。

如需实际修改 Book，先按 Book 的独立治理做精确 preflight，并在其非默认分支进行；本 mygpt PR 不替 Book 授予写入、内容迁移或合并权限。没有 API 预算时继续保持真实付费模型调用为零。
