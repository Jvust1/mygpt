## 最新检查点 · 2026-09-22 · PR #5

当前开发分支：`feat/book-context-brain-20260922`，基于 PR #3 的 `a8595c3ccaddcff5a6a95f8a37a963707f48c084`。
实现提交：`68c351b85511ccdd625036a6917b4303646b6704`。新增可运行的 `brain/`，不是正式 Book/模型/Android 集成。
本地两次最终源码回归均为 **95 passed, 2 skipped**；2 项跳过是 Pydantic AI / MCP SDK 未安装，不是通过。真实模型调用为 0，独立审阅待完成。
源码/原始测试证据包已在 Drive 归档并下载回读验证：`13YcH0j9VXd20LLWspZzDquRm-pe02OSJ`。
最新验收、设计决定和边界见 [Brain checkpoint](BOOK_CONTEXT_BRAIN_CHECKPOINT.md)；运行见 [brain/README.md](../brain/README.md)。
下一步：先补齐无付费调用的 SDK 集成验证，再核对 Book 实际字段/版本并设计真实事件适配器。不要直接改 main 或自动合并。

---

以下正文保留此前阶段的原始快照。旧的“未发布/尚未开始后端”表述不再代表本分支最新原型状态；以本节和 project_state 为准。

# Current State

Date: 2026-09-22

## Project status

- Repository: `Jvust2/mygpt`
- Default branch: `main`
- Foundation branch: `chore/security-bootstrap-and-project-foundation-20260921`
- Project classification: formal long-term project
- Drive mapping: `mygpt`
- Security bootstrap files are present on the non-default foundation branch.
- The Drive global safety baseline and branch `SECURITY_POLICY.md` have been re-read successfully after bootstrap.
- No merge is authorized by this synchronization.

## Jonah companion UI candidate

- Feature branch: `feat/jonah-companion-20260922`, based on the unmerged foundation head so its governance remains visible in the review diff.
- Added a framework-neutral `<mygpt-pet>` Web Component and a runnable mobile/desktop preview.
- Reused the verified Jonah sprite atlas: SHA-256 `828b0fb468382f37aaf0d62a3e86cb33e5fcad5dbde8aeb091d6778b32a77790`.
- Implemented nine animation states, sixteen look directions, bottom-right anchoring, touch dragging, keyboard movement, hide/restore, size controls, reduced-motion support, and local preference fallback.
- The component emits a chat-request event and accepts explicit host task states. It does not infer distraction, read other apps, capture screens, or claim that a model/Book bridge exists.
- Deterministic atlas tests: 3/3 pass.
- Headless Chromium interaction checks: 45/45 pass, including real touch events, reload persistence, narrow/landscape/desktop viewports, reduced motion, disconnected cleanup, disabled storage, runtime errors, and external requests.
- Visual screenshots were inspected. The test runtime lacked a CJK font, so Chinese labels rendered as fallback squares in those screenshots; the component uses system fonts and does not download a web font.
- Not yet verified: Android physical device, Android soft keyboard, native Android overlay, production mygpt host integration, production chat/Book bridge, and independent human review.
- This candidate appears inside a mygpt web/app surface. Cross-application Android floating UI requires a separate Android Studio implementation and system overlay permission.

## 2026-09-22 interaction reliability candidate

- Prepared from `feat/jonah-companion-20260922` at `64e73b257a79ec09787e2a96a43816b5864f9a1c`; the existing feature PR and foundation PR remain unmerged.
- Corrected keyboard activation after touch cancellation, unrelated pointer events interrupting a drag, and missing focus transfer into the action panel.
- The browser suite now creates its own preview on an available loopback port and cleans up even if Chromium cannot launch.
- Validation at this local candidate: 3/3 deterministic checks and 49/49 Chromium checks; a deliberately occupied default port still permits the suite to pass, and a missing browser exits promptly with a failure status.
- Remote publication is pending the all-repository preflight confirmation. Proposed review branch: `fix/companion-input-and-test-isolation-20260922`, targeting the existing feature branch. See E003 in `docs/EVALUATION_LEDGER.md` for reproduction evidence and remaining device limits.

## Product direction

mygpt is the user's primary companion surface.

It combines:
- **Book**: what the user is learning, exact course/chapter/section/mode/source references, and later concept-level learning state;
- **StudyMate**: study-session lifecycle, low-cost device/app/idle signals, and optional sensor bridge;
- **ChatContextVault**: protected relationship-history retrieval and optional Shadow mode;
- **mygpt Brain**: live conversation, activity interpretation, learning coaching, emotional-support conversation, intervention policy, and cross-session project state.

## Preferred perception strategy

`Book First → OS Sensor Second → User Context Third → Screen Vision Last`

The initial product should not depend on continuous screen capture.

When the user studies inside Book, Book should emit structured context such as:
- course / book / chapter / section
- Preview / Learn / Review / Practice mode
- current source or active item
- scroll position / active source / expanded source state
- dwell time and relevant navigation events
- practice/review outcomes when available

StudyMate or an Android sensor bridge may add:
- current foreground app
- screen on/off
- idle / return events
- study-session boundaries
- time away from Book

Vision remains a fallback for PDF/image/canvas/unsupported external content and should be session-scoped and explicitly authorized.

## Companion behavior

Default state is Silent Presence.

The system may escalate to:
1. Light Companion
2. Study Coach
3. Active Supervisor

Examples of useful behavior:
- stay silent while learning is going well;
- ask whether the user is stuck after repeated back-and-forth behavior;
- use Book context to answer "这里为什么这样" without requiring a new screenshot;
- ask a recall question after a meaningful learning segment;
- distinguish a short break from likely distraction;
- ask rather than accuse when screen/device evidence is ambiguous;
- switch to ordinary companionship or emotional-support conversation when learning is not the immediate need.

## Shadow boundary

ChatContextVault is not the default personality of mygpt.

Shadow mode is optional, explicit, and clearly labeled. It should prioritize:
1. retrieved facts,
2. observed long-term interaction patterns,
3. communication style.

It must not invent romantic intent, relationship progress, or the real person's current thoughts.

## Immediate next milestone

Design and implement the minimum event contract between Book and mygpt so mygpt can know where the user is in Book without screen recognition.

A first acceptance target:

> During a 30-minute Book study session, mygpt can know the current learning location and mode, detect meaningful study transitions, stay quiet by default, answer context-dependent questions, and selectively prompt for clarification or recall without continuous screen capture.

No production backend, Book event bridge, or Android application has been started in this repository yet. The Jonah companion is the first executable UI candidate and remains unmerged.
