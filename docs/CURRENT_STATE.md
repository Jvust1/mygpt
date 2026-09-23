# mygpt 当前状态 · 2026-09-23 只读选段桥候选

当前分支 `feat/book-live-selection-v1-20260923`，PR #7，Draft / Open / 未合并。此入口只更新本评审分支的 Book × mygpt 工作流，不替代其他分支的实时状态。原状态、原 Handoff 已按完全相同的 Git blob 保存在 `history/`，原安全规则、独立 Human Gate、不可变证据和 pending_sync 均继续有效。

## 已经完成

真实 r6 归档选段 → Book 内存授权器 → mygpt 严格接收端 → 本机 HTTP / Pydantic AI TestModel 已通过。原始转录、补录、AI 校正、思路提示、参考推导明确区分；raw/display 独立校验；取消、撤销、过期、重复请求和迟到回复受控。它不再只是合成正文演示，但仍不是手机联通或真实模型教学。

- Book：本地与远端各 68 项 Python、18 项 Node 投影测试通过。
- mygpt：两个远端干净环境各 352 项通过、0 失败、0 跳过。
- 实际 r6：95 小节，19,174 个 JS/Python 投影向量，0 差异；17,330 个有效正文、1,844 个预期空正文拒绝。不是全书数学正确性验收。
- 实际 HTTP：56 项通过，5 种实际选段路径通过 TestModel，付费模型调用 0。
- 两仓发布代码已从 CI 源归档回读一致；两个新 Drive 增量包均已完成整包及内部 manifest 校验。

## 配套 Book 明确内容层选择回归

Book PR #37 已前进到运行提交 `114be2a40f9e3ef364aca2e02492361ebf46e4b6`：当同一 record 同时存在原文/补录/AI 校正等多个候选层时，不再默认选最后一层；必须用户自己选择并核对预览，之后分享按钮才启用。预览本身仍不会产生 `/select` 授权。run 35834149129 的 68 Python、18 projection Node、1 DOM state regression 通过；这不是实际浏览器 E2E。Book 新增量归档 Drive `1T_PGQxLQJgaq5BkYzlO_tAC1SXr1_arz` 已完成整包哈希/CRC/内部 manifest 回读验证。

## 未完成与下一步

托管浏览器以 `ERR_BLOCKED_BY_ADMINISTRATOR` 阻止 localhost 导航，未更改或绕过策略，因此 UI 端到端验收仍未完成。Android APK 身份、IPC/overlay、真机软键盘、真实教学模型、生产多用户安全和独立审阅未验收。旧 mygpt PR #5/#6 整合冲突未处理。

唯一下一步：在允许 localhost 的受信任浏览器环境，对两个 PR 的精确实现做完整 UI 验收与独立审阅；不自动合并、不启用付费模型、不修改学习记录。

## 恢复入口

- [机器检查点](../governance/book_selection_bridge_checkpoint_20260923.json)
- [决策与验收检查点](BOOK_SELECTION_BRIDGE_CHECKPOINT_20260923.md)
- [当前增量 artifact 索引](../governance/book_selection_bridge_artifact_manifest_20260923.json)，须连同其 includes 指向的既有 artifact_manifest 读取。
- [原完整状态](history/CURRENT_STATE_before_book_bridge_20260923.md)与 [原完整交接](history/HANDOFF_before_book_bridge_20260923.md)。原文件仅作历史与继承约束依据，不能把其旧“下一步”当成本候选的新下一步。
