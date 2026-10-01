# PR #5 / #6 / #7 integration preflight — 2026-09-25

Status: **NON_DESTRUCTIVE_INTEGRATION_CANDIDATE / CI_REQUIRED / UNMERGED**.

Branch: `feat/integrate-pr6-book-bridge-20260925` from PR #6 head `8cce4bdaaaacf260e6e36f0462104d94afb1c326`.

## Read-only three-way findings

- PR #5 current head: `632b843c4e071a32b841caa7de8bdb0bbfebc059`.
- PR #6 at this preflight: `8cce4bdaaaacf260e6e36f0462104d94afb1c326`.
- PR #7 current head observed: `4e118054d9f3037a857d03c925f6d1641dd56979`.
- PR #6 and PR #5 diverge from merge base `95fd2846f5ec535b1241b4bb565fbca92eda626e`. The one PR #5-only commit after that merge base is documentation/governance work: Brain README, Reader bridge mapping, SDK checkpoint, CURRENT/HANDOFF and manifest/project_state. PR #6 independently changed the same state files, which explains the integration conflict without requiring a runtime rollback.
- PR #7 was created from older PR #6 head `ffa664a12b8bd65cd31fc7ef286722f8dea60937`. Since then PR #6 added the explicit local selection intake, lifecycle hardening and complete-source delivery. PR #7's runtime delta is mostly additive: `book_bridge.py`, its tests/assertion script and a scoped workflow.
- The dangerous overlap is PR #7's replacement-style `project_state/CURRENT_STATE/HANDOFF` diff. Those old state replacements are deliberately **not** copied into this branch. Their historical evidence remains in PR #7 and Drive.

## Integration rule for this branch

Only the following PR #7 runtime/test capability is transplanted onto the current PR #6 tree:

1. `brain/mygpt_brain/book_bridge.py`
2. `brain/tests/test_book_bridge.py`
3. `brain/scripts/assert_book_bridge_acceptance.py`
4. `.github/workflows/book-bridge-acceptance.yml`

Existing PR #6 Brain/intake/source-delivery code wins by construction. No state file, artifact manifest, CURRENT/HANDOFF, historical snapshot or prior checkpoint is overwritten by PR #7 content.

All existing acceptance workflows are extended only to run on this new review branch so the combined tree receives:
- strict Brain SDK regression;
- Jonah/replay/local-intake UI regression;
- clean source-delivery/recovery regression;
- Book bridge receiver regression.

## Boundaries

No PR is merged or rebased. No default branch is written. No historical branch/ref is moved. No Book repository mutation occurs. No real provider/model is enabled. No ChatContextVault data is accessed. This branch is disposable only by an authorized human; the agent will not delete it.

A green combined CI proves compatibility of these code paths on the tested environments; it does not authenticate the user's installed Book APK, validate teaching quality, or complete independent human review.
