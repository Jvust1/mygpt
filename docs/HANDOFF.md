# mygpt Handoff · Book 只读选段桥

先动态恢复 Drive 全局入口与全部当前根目录基线，再读目标分支 `AGENTS.md`、`SECURITY_POLICY.md`、project_state、North Star、Architecture Invariants、Current State、原 Ledger、本次独立决策/验收 checkpoint、pending_sync 和 Pre-flight。GitHub 高于聊天记忆；切换项目或分支重新检查安全门。

当前：`feat/book-live-selection-v1-20260923` / PR #7。实现身份、CI、原 r6 ZIP、Drive 增量包及哈希见 `governance/book_selection_bridge_checkpoint_20260923.json` 和 `governance/book_selection_bridge_artifact_manifest_20260923.json`。后者 includes 的旧总 artifact 清单继续有效，不能漏掉旧成果。

Book 运行目录必须来自固定 SHA 的 r6 归档；旧 Book `app/` 不是 r6，不能用它替代，也不能把归档整树覆盖进仓库。配套使用 Book PR #37 与 mygpt PR #7，原 r6 文件、数据库和教材不改。完整运行/验收命令在 Book `integrations/mygpt_selection/README.md`；mygpt 的新接收端是 `brain/mygpt_brain/book_bridge.py`。固定 SDK 输出不是模型教学。

下一步只做受信任浏览器环境的精确候选验收和独立审阅。重点覆盖两阶段明确选段、来源层级、raw/display、导航/隐藏/过期失效、授权和撤销竞态、取消和迟到结果、移动布局/字号/LaTeX。当前浏览器受到管理策略限制，不能通过修改策略或换路径来绕过。任何成功结论必须有实际浏览器证据；Node/HTTP 通过不能替代浏览器。

保持 main 不动、PR 不自动合并、原 PR #5/#6 冲突不自动解决。禁止付费 provider、ChatContextVault 读取、笔记/作答导出、StudyRecord 写入/迁移、生产多用户传输、未授权 Android/overlay 扩展。Book 原 H3b/B4b/B5、Lecture、multi-book consumer migration、持久化答案和每个 PR merge 的独立门禁仍有效；mygpt 继续安静陪伴默认、优先结构化感知、截图仅显式授权、Shadow 默认关闭。

原 project_state / Current State / Handoff 的精确 blobs 已另存 `governance/history/`、`docs/history/`；处理任何旧工作流时必须读取这些历史入口并重新核验其 live 分支，不能把本桥接检查点当成旧发布全量重验。原 `governance/pending_sync.json` 未被清空；本桥接成果同步无新增阻塞，既有 non-blocking 债务仍待独立证据。
