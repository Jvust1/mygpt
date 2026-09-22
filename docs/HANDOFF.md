# mygpt Handoff

## Start here

1. Read Drive root `全项目` and all current `全项目_*` baselines.
2. Read exact-target-branch `SECURITY_POLICY.md` and `AGENTS.md`.
3. Read `governance/project_state.json`.
4. Read North Star, Architecture Invariants, Current State, Decision Ledger, Evaluation Ledger, artifact manifest, pending sync, and Pre-flight Checklist.
5. Restore Book / StudyMate / ChatContextVault state from their own repositories only when needed.

Repository evidence outranks chat recollection.

## Current recovery point

The project foundation remains in PR #1 on `chore/security-bootstrap-and-project-foundation-20260921`.

The stacked feature branch `feat/jonah-companion-20260922` adds the first executable UI candidate: a local-only Jonah Web Component and mobile/desktop preview. It must not be described as a production mygpt app or Android APK.

The central architectural decision is:

`Book First → OS Sensor Second → User Context Third → Screen Vision Last`

The first engineering milestone is a small Book-to-mygpt semantic event contract, not full-device screen surveillance.

For the Jonah candidate, start with `docs/JONAH_COMPANION.md`. Its atlas hash, API, test evidence, Android boundary, external references, and integration steps are recorded there. The renderer exposes explicit state inputs and a chat-request event; the future host owns task truth and conversation behavior.

## Current product concept

mygpt should feel like a person who is present:
- usually quiet when the user is studying well;
- able to teach using current Book context;
- able to notice meaningful departures or likely distraction;
- able to ask whether the user is stuck rather than making brittle assumptions;
- able to switch naturally between learning, encouragement, ordinary conversation, and emotional support.

Shadow mode is optional and explicitly simulated.

## Next step

After review of the foundation and companion PRs, select the production host and produce the v0.1 interface/spec for:
- Book StudyContext snapshot;
- Book StudyEvent stream;
- Companion intervention state;
- local session state and privacy gates;
- minimal communication path between Book and mygpt.

Do not implement continuous screen capture before proving that Book semantic context plus low-cost device signals are insufficient.

If mobile delivery is selected, use Android Studio for the app/WebView host and physical-device validation. Treat an Android cross-app overlay as an optional separate milestone; do not confuse it with the current in-app fixed-position component.
