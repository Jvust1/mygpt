# BRIDGE-D001 / BRIDGE-E001 — Book 只读选段桥 · 2026-09-23

## 决策

保留两个项目的权威边界：Book 提供真实版本绑定的选段和短期授权，mygpt 只接收受信任同机能力接口，正文不长期复制。HMAC 身份不等于可撤销授权，因此消费、缓存和最终完成都回到 Book 核验；递增序号防止迟到选择复活。新 `mygpt.book-lease-context.v1` 不改变旧 v1/v2 的 SIMULATED 限制。

来源层级不混合：原始转录、补录、AI 校正、AI 思路提示与参考推导明确选择；raw/display 身份各自计算。保留实际公式编号撇号与合法跨小节引用；不修改源教材来适应代码。图片、笔记、答案和任意 provider/prompt 均不进入该接口。

## BRIDGE-E001 实际验证

精确提交：Book `bf7aa490639bc2b2fcf382623b915d54f6cecf07`，mygpt `fa9f17a0eb4fb015d76b419865f1b49a2d325f0e`。Book CI run 35828253594：68 Python、18 Node pass；有一条 pytest 缓存权限 warning，原日志保留。mygpt run 35826642389：相同 39-wheel lock 的两个新环境各 352 pass / 0 skipped / 0 failed，新 20 receiver cases 必须实际出现。

Book artifact 10736546209 的 SHA-256 为 `4214e74934bf6aaf63fc0e9e862c35ea750bca2d8b1bf657885076c910197755`；16 个代码/测试/说明/工作流文件与本地逐字节相同。mygpt artifact 10735138372 的 SHA-256 为 `f0ee3d7da7df19a4dca2abc7e61860e1fa1e4178ef468efae48841a699b349d2`；4 个实现/测试/工作流文件回读一致。

固定 r6 归档的 95 小节经独立 JS/Python 投影得到 19,174 个向量、0 mismatch，其中 17,330 个有效正文、1,844 个预期 EMPTY_BODY 拒绝。实际 Book HTTP 验收 56 项通过：5 类选段经实际 TestModel，重复请求不多调用，错误身份/私密字段/旧序号/撤销均拒绝，unexpected server errors=0、paid calls=0、不导入 StudyRecord。以上是身份/传输/策略验收，不是内容正确性或教学质量验收。

原始失败包括缺模块 TDD、Pydantic alias 再验证、HTTP 测试定位与错误码假设；全部保留，未抹除为 unseen。JS 末尾换行标识符新增回归后通过；最终 19,174 向量已重跑。

## UI 边界与下一步

可选 Reader 控件已实现，原密集正文没有持久化改写。浏览器因托管导航策略返回 ERR_BLOCKED_BY_ADMINISTRATOR，未绕过策略，无浏览器验收或截图。下一步为允许 localhost 的受信任环境中完整 UI 验收和独立审阅；不能用 HTTP/Node 的通过替代。Android 真机/APK 身份/IPC/overlay、真实教学 provider、生产多用户安全、独立审阅与旧 PR #5/#6 整合仍待完成。

## 保存与恢复

两份新增量 ZIP 分别归入 Book 与 mygpt 既有 Generated 目录。完整 SHA、Drive ID、内部成员数与整包回读校验记录在 `governance/book_selection_bridge_artifact_manifest_20260923.json`；旧 manifest 通过 includes 保留，旧 artifact 不重复上传。包内 CHECKPOINT.md 保存更详细的验证、错误及重现说明。

状态同步将 pre-bridge 三份入口按完全相同的 Git blob 保存在 history，新入口只描述当前评审分支；不会覆盖历史证据或取消任何旧门禁。后续修改必须沿普通分支/审阅流程进行，不直接写 main，不自动合并。
