# Combined local intake + Book lease receiver checkpoint

Date: 2026-09-25 (+08)

Status: **COMBINED_INTEGRATION_ACCEPTED / DRAFT_PR8 / INDEPENDENT_REVIEW_PENDING**.

Branch: `feat/integrate-pr6-book-bridge-20260925`.
PR: #8, base `feat/book-contract-audit-v1`.
Exact accepted implementation head: `e9e5fb0932c1830fa11e886beb2802191eea09c8`.

## 1. Why this branch exists

PR #6 and PR #7 had become structurally incompatible as review branches even though most runtime work was complementary. A read-only three-way audit found:

- PR #6 diverged from PR #5 at merge base `95fd2846...`; the single PR #5-only commit after that point is documentation/governance work, not a missing Brain runtime implementation.
- PR #7 was based on older PR #6 head `ffa664a...`. Since then PR #6 added local explicit intake, request lifecycle hardening and complete-source delivery.
- PR #7's useful runtime delta is mostly additive: the Book lease receiver plus tests/assertion/workflow.
- PR #7's large replacement-style edits to `project_state.json`, `CURRENT_STATE.md` and `HANDOFF.md` would overwrite newer PR #6 state if copied directly.

The integration branch therefore starts at the current PR #6 checkpoint and imports only PR #7's additive receiver/runtime test capability. No stale state file was transplanted.

## 2. Integrated capability

The combined tree contains both input paths:

1. **Explicit local input** — user chooses/previews/consents to one local text/Markdown record; evidence remains `USER_SUPPLIED_UNVERIFIED`; default-off intake.
2. **Book lease receiver** — a trusted local authority capability can supply a short-lived Book-owned selection lease; the receiver validates the exact selection/content identity and only then produces a fixed Pydantic AI TestModel integration reply.

Neither path activates a live/paid provider. The Book receiver is not exposed as an arbitrary HTTP source-body endpoint; the authority object supplies content and currentness. Legacy simulated Reader contracts remain unchanged.

## 3. Exact combined CI

All four exact-head workflows at `e9e5fb0` passed.

### Brain SDK — run 36088319906
- Two clean locked Ubuntu/Python environments.
- **446 passed / 0 failed / 0 skipped** in each.
- Selection HTTP smoke remains **32/32**.
- Artifact `10844484067`, SHA-256 `b18681b1d8390e20a64d91fb70afdb361089d4f56de7013097c40dffd7482acc`.

### Host UI — run 36088319915
- Node **66 pass**.
- Jonah browser **49 checks pass**.
- Legacy replay host **39 checks pass**.
- Local Python host **23 checks pass**.
- Explicit local-selection host **30 checks pass**.
- External browser requests 0; expected negative HTTP statuses remain classified rather than hidden.
- Artifact `10844723415`, SHA-256 `28377ebba304a25d9751b6b2f8417cb34ba4ec4aee40c900ccafae8aec2d992e`.

### Complete source delivery — run 36088319923
- Deterministic source bundle from immutable integration commit.
- **103 tracked source files**, source ZIP **2,298,335 bytes**, SHA-256 `4e3ef0e9f0e87c2decb3ee9c6b02a5684e78550c2a3fc9e8d47937314bda3466`.
- Clean-directory restore and locked install pass.
- Recovered Brain **446/0/0**.
- Launcher smoke **12/12**.
- Selection HTTP **32/32**.
- Artifact `10844851422`, SHA-256 `bd6b36f3f0598249479afe34a0fb267d3359fadbe1a2edc72e95a3084d077b2e`.

### Book bridge — run 36088319928
- Two clean locked environments, **446/0/0** each.
- **20 receiver cases**, all accepted in each environment.
- Actual TestModel SDK path is present.
- Artifact `10844841409`, SHA-256 `f7c6ddf254dc9cab8afa956ef15d1ec4bff1d0effe72bdc54f01b9f995af6529`.

## 4. Long-term Drive archive

`mygpt-integrated-book-bridge-v1-20260925.zip`

- Drive ID: `1G0lZ1A9EHNrUTFGEfxwwXTsfgSZPk4QK`
- 5,625,678 bytes
- SHA-256: `eec9e3266b7d4afbf789a962945e7f74b7defbf47463875bc374aea6f4321f09`
- 6 ZIP members, CRC PASS.
- Contains the four exact CI artifacts, a checkpoint and machine-readable manifest.
- The embedded source-delivery CI artifact contains the exact 103-file source ZIP and recovery evidence.

The Drive object was downloaded immediately after upload; size/hash/CRC and manifest source identity were rechecked.

## 5. What was deliberately not integrated

- PR #7's old replacement versions of `project_state.json`, `CURRENT_STATE.md`, and `HANDOFF.md`.
- Any merge/rebase of PR #5/#6/#7.
- Any Book repository mutation.
- Any real provider/model activation.
- Notes/answers/StudyRecord writes.
- ChatContextVault data.
- Android/Windows device behavior.
- Production multi-user network security.

## 6. Current interpretation

The compatibility question is answered: **the current local-intake/source-delivery line and the Book lease receiver can coexist and pass the combined regression suite without rolling back newer PR #6 work**.

This is not equivalent to saying that the old PR stack can be merged as-is. PR #5/#6 remain historically divergent, PR #7 remains a separate older review line, and independent review is still required.

## 7. Next safe work

Independent review should inspect the exact PR #8 diff and the corresponding Book-side authority implementation. After review, the next product-value milestone is a real end-to-end Book selection flow in an authorized localhost/browser or Android Studio host, still using TestModel before any live provider. Merge decisions remain PR-specific user gates.
