# mygpt

Long-term companion and learning orchestrator.

## Current review branches

- Project foundation: `chore/security-bootstrap-and-project-foundation-20260921` / PR #1.
- Jonah companion UI: `feat/jonah-companion-20260922`, based on the foundation branch.

The Jonah integration is a framework-neutral, mobile-friendly Web Component and interactive preview. See [`docs/JONAH_COMPANION.md`](docs/JONAH_COMPANION.md) for scope, API, validation evidence, and the Android boundary.

mygpt is a long-term companion and learning orchestrator.

It is designed around a simple idea: **presence without pressure**.

The system should know enough context to understand what the user is learning, when help is useful, when distraction is likely, when emotional support matters, and when the best action is to stay quiet.

## Architecture

mygpt integrates, but does not replace:

- **Book** — structured learning content and semantic study context.
- **StudyMate** — study-session and low-cost device/activity signals.
- **ChatContextVault** — password-gated relationship-history retrieval and optional Shadow grounding.

Preferred perception order:

`Book semantic context → OS/App signals → user-declared context → opt-in screen vision`

## Start here

- [AGENTS.md](AGENTS.md)
- [SECURITY_POLICY.md](SECURITY_POLICY.md)
- [Project North Star](docs/PROJECT_NORTH_STAR.md)
- [Architecture Invariants](docs/ARCHITECTURE_INVARIANTS.md)
- [Current State](docs/CURRENT_STATE.md)
- [v0.1 Product Architecture](docs/MYGPT_V0_1_PRODUCT_ARCHITECTURE.md)
- [Decision Ledger](docs/DECISION_LEDGER.md)
- [Evaluation Ledger](docs/EVALUATION_LEDGER.md)
- [Handoff](docs/HANDOFF.md)
- [Pre-Flight Checklist](docs/PRE_FLIGHT_CHECKLIST.md)
- [Machine-readable project state](governance/project_state.json)

## Current milestone

Define and validate the Book-to-mygpt semantic StudyContext / StudyEvent contract before adding broad continuous screen capture.

No application implementation is yet claimed.
