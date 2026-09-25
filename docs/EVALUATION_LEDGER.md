# Evaluation Ledger

## E001 — Foundation architecture review

Date: 2026-09-21
Status: DESIGN_ACCEPTED_FOR_V0_1_PLANNING

### Question
Can mygpt provide useful real-time study companionship without continuous screen recognition?

### Current conclusion
Yes, for Book-centered learning the preferred route is structured semantic context from Book, augmented by low-cost Android/app activity signals. Screen vision should be a fallback rather than the default.

### Evidence available
- Book already exposes structured learning concepts such as course/chapter/section, learning modes, route/session state, and durable StudyRecord-related behavior in its current project.
- StudyMate already establishes a pattern of Android-side session/activity observation and companion behavior.
- ChatContextVault demonstrates a privacy-gated retrieval model for relationship history and a clear separation between stored evidence and interpretation.
- External mobile-agent research confirms that Android UI/accessibility/screen-perception stacks exist, so vision fallback is technically plausible; detailed adoption decisions remain future work.

### Not yet proven
- Latency and UX of a production Book→mygpt event bridge.
- Intervention quality over a real 30-minute study session.
- Battery impact of optional Android sensors.
- Cost of cloud reasoning at realistic usage.
- Reliability of screen-vision fallback for PDFs, math formulas, and external apps.

### Next evaluation
Prototype the semantic event contract and run a real study-session simulation before implementing broad screen capture.

## E002 — Jonah companion component candidate

Date: 2026-09-22
Status: IMPLEMENTED_TESTS_PASS_REVIEW_PENDING

### Question
Can the existing Jonah character become a low-cost, controllable companion surface in mygpt before the final host stack is selected?

### Result
Yes, at the reusable UI-component level. The candidate uses one local sprite atlas, native browser APIs, and no runtime dependency or external network request. It supports touch and keyboard input, preserves the user's chosen location/visibility when storage is available, handles unavailable storage, and stops animation work when hidden, backgrounded, disconnected, paused, or reduced motion is requested.

### Evidence
- `npm test`: 3/3 deterministic atlas/mapping checks passed.
- `npm run test:browser`: 45/45 Chromium interaction checks passed at the implementation checkpoint.
- Verified behaviors include real emulated touch events, drag/tap separation, reload persistence, five host states, all sixteen look directions, narrow/landscape/desktop fitting, reduced motion, disconnect cleanup, storage-denied fallback, zero runtime exceptions, and zero external requests.
- Mobile and desktop screenshots received visual inspection.

### Limits
- Headless Chromium is not Android physical-device validation.
- Test screenshots showed missing CJK font glyphs in the Linux browser runtime; no layout failure was observed.
- The demo chat panel is an event-wiring proof, not a production model connection.
- Cross-app Android overlay, native app lifecycle, soft keyboard, Book semantics, and notification behavior remain unproven.

### Next evaluation
Select the production host, integrate the component with explicit mygpt/Book state, then test on Xiaomi 14 through the Android Studio workflow. Evaluate a system overlay only as a separate optional feature.

## E003 — Input recovery and isolated browser validation

Date: 2026-09-22
Status: LOCAL_VALIDATED_PENDING_PREFLIGHT_CONFIRMATION
Base: `feat/jonah-companion-20260922` at `64e73b257a79ec09787e2a96a43816b5864f9a1c`
Proposed branch: `fix/companion-input-and-test-isolation-20260922`

### Reproduced defects

1. Opening the panel with Enter left focus on the avatar even though the panel precedes it in tab order. The first action was not the next keyboard target.
2. An unrelated `pointerup`, `pointercancel`, or `lostpointercapture` event ended the active drag because the end handler did not check pointer identity.
3. A cancelled touch did not emit a click, leaving drag-click suppression armed. A later Enter activation was swallowed.
4. The browser suite used a fixed port and could connect to another preview. Chromium launch occurred before the cleanup block, so launch failure could leave the child server running.

### Change and evidence

- Move focus into an opened action panel and restore avatar focus on close; keep normal host chat event handling.
- End only the matching active pointer; ignore additional pointer-down attempts during a drag; preserve keyboard clicks after cancellation.
- Start one test-owned server with `PORT=0`, read its actual listening address, and clean up startup/launch failures.
- Baseline recovery verified all 26 Git blob identities against the exact upstream tree, including the unchanged sprite PNG.
- Before the component changes, an independent Chromium reproduction returned false for all three input checks; after the changes, all three returned true.
- `npm test`: 3/3 pass. `npm run test:browser`: 49/49 pass, including the original 45 checks plus keyboard focus, Escape recovery, pointer identity, and cancelled-touch keyboard recovery.
- With an unrelated HTTP 500 server deliberately occupying port 4173, the updated browser suite still passed all 49 checks on its own port.
- With an invalid Chromium executable path, the suite exited with code 1 in under one second instead of hanging on a leftover server.
- Runtime errors: 0. External browser requests: 0. Runtime dependencies and sprite bytes unchanged.

### Scope and limits

This is a locally validated review candidate, not a published or merged change. No GitHub or Drive mutation was performed by this audit. The remote publication preflight must verify the base head again, use the proposed new branch, and preserve existing PRs. Physical Android hardware, native overlay, soft keyboard, production Book/chat integration, and independent human review remain unverified.


## E004 — explicit local selection intake
Date: 2026-09-24
Status: ACCEPTED_SYNTHETIC_LOCAL_INPUT / REVIEW_PENDING

### Question
Can a user explicitly bring one local text selection into the existing loopback Brain without pretending it is Book data or creating an implicit provider call?

### Result
Yes for the bounded local-input contract. Exact head `318c3ef0874b6903320d7ccfa0ce63d33f862bd0` passed two clean locked Python environments at 426/0/0 each, 32 loopback HTTP checks, 66 Node tests, and browser suites including 30 explicit-selection checks. The UI requires preview/consent; import alone does not explain; provenance remains `USER_SUPPLIED_UNVERIFIED`; reload/revoke/cancel/expiry paths fail closed.

### Limits
This does not authenticate Book, validate mathematical truth, activate a real model, support arbitrary documents, or prove Windows/Android behavior. Independent review remains pending.

## E005 — deterministic source delivery and clean recovery
Date: 2026-09-25
Status: ACCEPTED_LINUX_CLEAN_RECOVERY / WINDOWS_ANDROID_PENDING

### Question
Can a fresh environment recover one exact PR #6 source state without relying on a dirty workspace, old incremental ZIP order, or hidden credentials?

### Result
Yes on the accepted Linux CI environment. Exact head `65c8d6b0493432c16d83174aeff22b415583a703`, run `36019467569`, passed 26 delivery unit tests; produced byte-identical source bundles from the immutable commit; verified 97 tracked source files; restored into a fresh directory; installed the existing hash lock; reported doctor READY; passed actual launcher start/status/Ctrl+C shutdown 12/12; and reran Brain 426/0/0 plus selection HTTP 32/32.

The exact source ZIP is 2,246,013 bytes with SHA-256 `eb9404fbfd9a4d9fc22db57c0518ecb65510a192b7500277885f2747219bb6df`. The long-term Drive evidence/archive is indexed in the artifact manifest.

### Limits
The internal source manifest is not a signature; authenticity depends on the separately recorded outer SHA-256 and trusted Git/Drive provenance. Windows launcher, Android packaging/device behavior and independent review are not accepted by this evaluation.
