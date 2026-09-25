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
