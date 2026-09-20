# AGENTS.md — mygpt

Any GPT / Claude / Codex / DeepSeek / local agent taking over this project must treat GitHub as the authority for source, governance, current state, decisions, and next steps. Google Drive is the vault for large files, generated artifacts, snapshots, and long-lived project files. Chat history is not authoritative project state.

## Mandatory start sequence

Before project work:

1. Read the Drive root `全项目` registry and every current root `全项目_*` baseline.
2. Read this repository's `SECURITY_POLICY.md` from the exact target branch.
3. Read `governance/project_state.json`, `docs/PROJECT_NORTH_STAR.md`, `docs/ARCHITECTURE_INVARIANTS.md`, `docs/CURRENT_STATE.md`, `docs/DECISION_LEDGER.md`, `docs/EVALUATION_LEDGER.md`, `docs/HANDOFF.md`, `docs/PRE_FLIGHT_CHECKLIST.md`, `governance/artifact_manifest.json`, and `governance/pending_sync.json` as applicable.
4. Read linked Book / StudyMate / ChatContextVault state only as needed for the current bounded task.
5. Do not rely only on chat memory or stale copied state.

## Product boundary

mygpt is the orchestration and companion layer. It may integrate with:
- Book for structured learning context and knowledge;
- StudyMate for low-cost study-session and device/activity signals;
- ChatContextVault for explicitly authorized relationship-history retrieval and optional Shadow mode.

Do not collapse these source systems into mygpt or silently duplicate their authoritative data.

## Safety

`SECURITY_POLICY.md` and the Drive global safety baseline are mandatory. `main` is treated as a protected stable branch for agent operations. Use non-default branches and reviewable PRs for ordinary changes. Do not automatically merge PRs.

Deletion, purge, history rewrite, force-push, branch/tag deletion, unusual bulk overwrite/rename/move, frozen-evidence replacement, access-control weakening, safeguard removal/bypass, and ambiguous high-impact destructive actions are `DESTRUCTIVE_LOCKED`.

## Privacy

- Screen understanding must be opt-in and session-scoped where capture is used.
- Prefer structured semantic context from Book over screenshot capture.
- Prefer Android/app-state sensors over raw screen capture when sufficient.
- Default-deny capture or upload of private messaging content, credentials, financial apps, password fields, and unrelated personal material.
- ChatContextVault content must remain behind its project access gate and must not be copied into mygpt as raw relationship data.
- Shadow output must be clearly identified as simulation, never represented as the real person.

## Artifact synchronization

When the user says `更新所有成果`, `同步所有成果`, `更新 GitHub 和 Drive`, or equivalent:

- inventory current GitHub / Drive / workspace artifacts first;
- classify candidates as `NEW`, `CHANGED`, `SKIP_IDENTICAL`, `HISTORICAL_DUPLICATE_PRESERVED`, or `CONFLICT_NEEDS_REVIEW`;
- skip identical content rather than creating duplicate files/commits;
- update changed logical Drive artifacts in place when safe;
- preserve historical/frozen evidence;
- use the minimum practical number of GitHub commits;
- verify the written state by read-back;
- report GitHub commit count plus Drive create/update counts.

A second sync with unchanged inputs should create zero GitHub commits and zero new Drive objects.
