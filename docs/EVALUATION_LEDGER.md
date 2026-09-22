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
