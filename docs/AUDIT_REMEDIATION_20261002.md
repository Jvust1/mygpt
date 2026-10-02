# 2026-10-02 audit reconciliation: Android required build gate

## Scope and source identity

- Audit document: [`0776119ccae16deacbb92884860c75fd3f806aea`](https://github.com/Jvust1/mygpt/blob/0776119ccae16deacbb92884860c75fd3f806aea/docs/AUDIT_REPORT_20261002.md), committed 2026-10-02 03:57:20 UTC
- That report inspected older PR #48, `1e766c00d7ccb857d7d5a858e7af776f66b611df`
- This bounded fix starts from latest PR #57, `5bbc3a165e648327abe625b04590dbce33812178`
- New independent branch: `fix/android-required-gate-dot-20261002`
- Main, the existing review branches and product/runtime code are unchanged

The current release status remains **BLOCKED_FOR_RELEASE**. Test counts or a
successful source build do not establish device, distribution or product acceptance.

## Rechecked P1 findings

| Audit finding | Current evidence / treatment |
| --- | --- |
| MYGPT-001: APK host silently skipped by repository typo | Still present at #57. [Run 36810453422](https://github.com/Jvust1/mygpt/actions/runs/36810453422) has successful production, recovery and Java jobs, but `android-java-boundaries / android-debug-host` is skipped. Corrected and guarded by this draft; its actual hosted build remains to be checked. |
| MYGPT-002: unbounded runtime/history/receipts | Still reproduced at #57 with synthetic data under the exact Linux Python 3.13 lock. Not fixed here; no durable history is silently deleted. |
| MYGPT-003: main is not the implementation | Still true. Current main contains governance and the audit, not the product implementation. Merge/product-branch policy is a separate decision. |
| MYGPT-004: stale governance | Partly outdated: #57 already corrected `project_state.repository` and explicitly distinguished historical zero-runner failures. Its active branch, manifest owner and some candidate validation summaries were still stale. This draft corrects its own current branch/owner/entry points while preserving historical records. A complete governance consistency gate remains open. |

Long-run reproduction at 100 / 200 / 400 turns respectively:

- In-memory history: 201 / 401 / 801 messages; request cache: 100 / 200 / 400
- Sum of repeated compacted IDs across receipts: 8,190 / 36,290 / 152,490
- SQLite bytes after WAL close: 471,040 / 1,503,232 / 5,259,264
- Provider window stayed at most 20 messages; explicit memory remained empty
- Cold replay avoided another responder call, but the next new turn loaded full history
- Separate 100 / 200 / 400 single-turn sessions also grew the runtime session map

These are six synthetic reproduction cases, not real user data, performance
benchmarks or proof of a repaired retention policy. Existing replay/history
contracts must be preserved when addressing the growth issue.

## Change

1. Correct `android-debug-host` to `Jvust1/mygpt` and retain its actual
   `gradle -p android_spike :app:assembleDebug --no-daemon` command.
2. Add an always-evaluated Android gate requiring both Java matrix and APK jobs
   to report `success`. Add an aggregate gate requiring production, the entire
   reusable Android workflow, and source recovery to report `success`.
3. The shared gate script rejects missing, skipped, failed, cancelled, malformed
   or unexpected results. No continue-on-error or test bypass is added.
4. Inspect the real APK for unique nonempty `classes.dex`, arm64 `libgdx.so`,
   DEX/ELF headers and byte-identical tracked Spine license. Record exact source
   SHA, APK hash/size, and those three public payload hashes/sizes.
5. Preserve read-only workflow permissions, immutable action pins and exact-SHA
   checkout without credential persistence.

This uses GitHub's existing
[needs / always semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idneeds),
not a new CI framework. Force-cancellation or runner failure can prevent any
job from finishing; a missing terminal success is never acceptance. Naming a
job `required` does not enable GitHub branch protection, which remains unchanged.

## APK distribution boundary

The existing [Spine evaluation notice](../android_spike/SPINE_EVALUATION_NOTICE.md)
does not establish public APK redistribution entitlement. Enabling the old job
unchanged would also upload a runtime-containing APK to a public repository.
This draft therefore runs the build and payload validation on the runner but
uploads **only `apk-evidence.json`**, not the APK, models or private Live assets.
Normal Actions logs preserve the build steps. The JSON contains only commit,
status, hashes, sizes and the three allowlisted public entry names; it explicitly
sets APK publication, device acceptance and distribution-license verification false.

A successful JSON report is not a downloadable APK deliverable and does not
fulfil the audit's APK-distribution requirement. Distribution entitlement and an
authorized destination must be established separately. No private skin is fetched
or embedded, and no production or physical-device acceptance is claimed.

## Verification before publication

- Source recovery verified 456 files at exact #57; external ZIP SHA-256:
  `2680733bb2b4fd2b8905c59c64edbe67bc4b915ee61138ebafdfcc2a817d5ced`
- New 13 focused tests pass. Substituting the original two workflows makes the
  same suite fail five wiring assertions; restoring the fix passes.
- Independent review exercised all 80 child/aggregate combinations of
  success/failure/skipped/cancelled; only all-success passed. APK CLI round-trip
  verification confirmed correct hashes/sizes and no extra-content disclosure.
- Python 3.13.15, original `--require-hashes` lock: strict Brain **827 passed**,
  **83 root Python tests passed**, `pip check` passed
- JavaScript **70 passed**, zero failed/skipped
- Initial default Python 3.12 root run had seven missing-TestModel dependency
  errors; using the documented hash-locked 3.13 environment resolved them.
- Workflow wiring tests are static assertions; APK unit tests are synthetic ZIPs.
  Actual Gradle/Android execution is **not** inferred from them.

The draft PR records this candidate's exact head, final hosted run and artifact
identities after publication. Previous commits' green runs are not this draft's
acceptance. Actual Android/Windows devices, Book adoption/signing, real model
quality, microphone, audible TTS, and complete dependency-lock governance remain
outside this bounded correction.
