# Current State

Date: 2026-09-21

## Project status

- Repository: `Jvust2/mygpt`
- Default branch: `main`
- Foundation branch: `chore/security-bootstrap-and-project-foundation-20260921`
- Project classification: formal long-term project
- Drive mapping: `mygpt`
- Security bootstrap files are present on the non-default foundation branch.
- The Drive global safety baseline and branch `SECURITY_POLICY.md` have been re-read successfully after bootstrap.
- No merge is authorized by this synchronization.

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

No production implementation has been started in this repository yet.
