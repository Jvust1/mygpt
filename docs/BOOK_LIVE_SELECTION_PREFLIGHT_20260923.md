# Book read-only selection bridge — scoped preflight

Date: 2026-09-23. Status: IMPLEMENTATION_IN_PROGRESS; not a new acceptance claim.

## Authority and exact bases

- mygpt base: `ffa664a12b8bd65cd31fc7ef286722f8dea60937`, tree `5202bc90882a386811e24aded7a0cada3474ede0`, PR #6.
- This work uses `feat/book-live-selection-v1-20260923`, with a separate PR targeting `feat/book-contract-audit-v1`. PR #5/#6 integration conflicts are not resolved or bypassed.
- Book r6 archive authority: `Jvust2/Book` checkpoint `7283f2eef7610d67c6b92b2ef7c513e1225ad957`, `governance/two_courses_current_app_source_20260922_1054.json`.
- Source archive Drive ID `1UiVow02Huh3r8qKBH8v4bL3D9OfkQ8_R`, SHA-256 `19315e8aeebe2db5cf2f4b55e0a38f550967966af106491dfef67212b430adc1`, 70,090,018 bytes. This is not an attestation of the user's installed APK.

## Allowed scope

Build an optional read-only r6 selection exporter in Book's own additive integration directory, a bounded receiver in mygpt, and a local development host for explicit selection, verification, TestModel-only explanation, cancellation, expiry, and revocation. The Book work has its own exact-branch preflight and review branch. Do not replace the legacy Book app tree with the archived r6 tree.

The receiver must distinguish real archive-backed Book input from synthetic fixtures. Existing v1/v2 simulated protocols remain unchanged. A content hash alone does not authenticate a producer or revoke a snapshot; the proposed local authority must revalidate the active lease and current source at consumption and completion.

The normal dense r6 reading layout and hidden inline provenance remain intact. Any optional selection controls must be explicit, bounded, and removable. Source, completion, correction, and derived layers must not be silently substituted. Private notes and learner answers are excluded.

## Hard boundaries

No default-branch writes, automatic PR merge, history rewrite, deletion, safety weakening, raw Book corpus copied into mygpt, ChatContextVault access, StudyRecord write/migration, paid provider call, or Android production/physical-device claim. Existing immutable evidence is retained.

## Verification and recovery

Fresh global registry and root baselines, repository safety, current-state documents, pending sync, and relevant archive identities were read. Local archive hashes and CRC were checked. The sandbox lacks the Pydantic AI/MCP SDK and network DNS; skipped local SDK cases are not acceptance. A scoped read-only GitHub Actions job will restore the existing hash-locked wheels and archive the exact checkout for reproducible local integration. Dependency wheels are temporary execution inputs, not long-term project deliverables.

The first preparation CI validates the existing suite only. New bridge acceptance must report its own tests and source identity after implementation. Preserve initial failures, inspect the actual browser, publish code/evidence in minimal checkpoints, and verify remote writes by read-back. Independent review, real-model teaching quality, Android IPC/overlay, and user-device APK identity remain pending.
