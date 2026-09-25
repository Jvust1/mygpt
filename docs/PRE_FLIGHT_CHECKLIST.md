# mygpt Pre-Flight Checklist

Before substantive development or synchronization:

## Global
- Confirm target repository and branch.
- Read Drive root `全项目`.
- Dynamically read every current root `全项目_*` baseline.
- Read exact-target-branch `SECURITY_POLICY.md`.
- Missing/conflicting safety source => `READ_ONLY_LOCKED`.

## Repository
- Read `AGENTS.md`.
- Read `governance/project_state.json`.
- Read North Star, Architecture Invariants, Current State, Decision Ledger, Evaluation Ledger, artifact manifest, pending sync, and Handoff.
- Confirm target is a non-default review branch for ordinary writes.

## Cross-project boundaries
- Book facts/state come from Book.
- StudyMate device/session facts come from StudyMate.
- ChatContextVault access must pass its own current-session gate before reading protected content.
- Do not persist ChatContextVault plaintext secrets or raw relationship data in mygpt.

## Privacy
- Prefer semantic events to screenshots.
- Require explicit session permission before screen capture.
- Exclude credentials, financial screens, password fields, private-message content, and unrelated personal material by default.
- Shadow output must be labeled simulation.

## Product
- Do not treat time-on-page as proof of learning.
- Ask when observed behavior is ambiguous.
- Default companion state is quiet presence.
- Avoid notification spam and gamification-first behavior.
- No arbitrary UI control in v0.1.

## Completion
- Verify changed files by read-back.
- Confirm no direct `main` write.
- Confirm no automatic PR merge.
- Update current state / project_state when the milestone materially changes.
- Report NEW / CHANGED / SKIP_IDENTICAL / HISTORICAL_DUPLICATE_PRESERVED / CONFLICT_NEEDS_REVIEW for synchronization work.
