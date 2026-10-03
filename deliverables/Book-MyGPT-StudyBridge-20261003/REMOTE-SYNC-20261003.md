# Book StudyBridge 远端同步记录（2026-10-03）

- Book 草稿 PR（未合并）：https://github.com/Jvust1/Book/pull/79
- mygpt 草稿 PR（未合并）：https://github.com/Jvust1/mygpt/pull/67
- 本次提交只新增同步记录，不更改已审查源码。公开 PR 不包含本机身份/来源配置。

## Drive 交付物
归档目录：https://drive.google.com/drive/folders/1p1tWtiXKOhce6SBGJ-VnNmNsq5GSwhVz

- 源码包： [Book-MyGPT-StudyBridge-Source-20261003.zip](https://drive.google.com/file/d/1I72KZ-mk4V-HDZeQHZgTWb0a02RZ2EtN/view?usp=drivesdk)
- 补丁、验证记录、回滚脚本、联动清单、SelfCheck 及两份 Markdown 报告均已作为原始文件上传至此目录。
- EXE 原文件为 371,769,344 字节，SHA-256 `9ac0a760504100c8d1a01818168a5249c118a4c68914fd802e71828862d69fdb`。单文件上传超时；已上传全部 12 个分卷、分卷清单和重组脚本：
  https://drive.google.com/drive/folders/1Mx8fY7Fo8ZvppX2m_oHjjYY30pzFXvCU
  下载全部 `.part001`–`.part012` 文件及 `Join-Book-StudyBridge-EXE.ps1`，在同一目录运行脚本，完成后会校验完整文件大小与 SHA-256。分卷本地重组检查已通过。

## 行为复核
同一输入：BASELINE 4/13 项通过（退出码 1）；MODIFIED 22/22 项通过（退出码 0）；ROLLBACK 4/13 项通过（退出码 1），恢复哈希等于 BASELINE。均为合成输入测试，不代表线上真实模型或 dot 已连接。真实模型调用 0 次，真实 dot 调用 0 次。
