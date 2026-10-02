# Explicit local selection + complete source delivery checkpoint

Date: 2026-09-25 (+08)

Status: **LOCAL_UNVERIFIED_SELECTION_ACCEPTED / COMPLETE_SOURCE_RECOVERY_ACCEPTED / REAL_BOOK_PARALLEL_REVIEW_PENDING**.

Authoritative review branch: `feat/book-contract-audit-v1` / PR #6. Runtime intake implementation: `318c3ef0874b6903320d7ccfa0ce63d33f862bd0`. Exact source-delivery acceptance head: `65c8d6b0493432c16d83174aeff22b415583a703`. This checkpoint changes governance/docs only after those exact-code runs.

## 1. Product capability actually accepted

The local service can remain fixed-sample-only, or the user can explicitly start it with `--enable-selection-intake`. In intake mode the user selects a single local text/Markdown item or manually enters one paragraph, previews it, explicitly consents, and only then sends it to the loopback Python service.

Imported content is always `USER_SUPPLIED_UNVERIFIED` under `mygpt.imported-reader-context.v1`. It never becomes authenticated Book state, never inherits a real Book version, and does not silently become a paid/provider prompt. The browser does not persist imported text across reload, and the service keeps source text in memory only.

The intake and request lifecycle now fail closed on duplicate JSON keys, non-finite numbers, invalid UTF-8/surrogates, oversized/deep objects, source/hash mismatches, stale leases, request-id conflicts, cancellation, authorization expiry, and revocation. Cancel-before-arrival tombstones and terminal error receipts prevent late work from being treated as a valid completion.

## 2. Exact intake acceptance

GitHub Actions exact head `318c3ef0874b6903320d7ccfa0ce63d33f862bd0`:

- Brain SDK run `36013336912`: two clean locked Python environments, each **426 passed / 0 failed / 0 skipped**.
- Selection HTTP smoke: **32/32** checks; external requests 0; paid model calls 0.
- Host UI run `36013337122`: **Node 66 pass**, Jonah **49 checks pass**, legacy replay host **39 checks pass**, local Python host **23 checks pass**, explicit selection host **30 checks pass**.
- Selection browser acceptance covers visible opt-in, HttpOnly cookie, preview-before-consent, import-without-explain, unverified provenance, cancel/late-result suppression, real Brain fixed TestModel receipt, XSS-safe text rendering, invalid UTF-8/oversize/hash/expiry rejection, reload non-persistence, revocation, zero external requests, and allowlisted API paths.
- SDK artifact `10812724745`: downloaded SHA-256 `3acfa625592960d1aedd53187c6db59ff7faecfcbdf9f2cc0f450ed8986414d8`.
- UI artifact `10812944362`: downloaded SHA-256 `0860f8cac52c9124bb72af2025fb019daa52380b1ecf3d9dea432863fa523dfa`.

Long-term Drive bundle already exists and was re-downloaded in this checkpoint:

- `mygpt-selection-intake-v1-20260924.zip`
- Drive ID `1BT34bsIPxgzorSftSeGht-GTsNtXsVDG`
- 1,952,992 bytes
- SHA-256 `774c1aa7e6f304838d07e30fc32b59092c985feffd0063033fc5f9bdc8dff09e`
- 43 ZIP members; the internal manifest records the two exact CI artifacts above.

## 3. Complete source delivery and recovery

`run_mygpt.py` provides a read-only `doctor` and an explicit `start`. The launcher does not install packages, open a browser, inherit API keys/proxies/PYTHONPATH, select a provider, or enable intake unless the flag is supplied.

`scripts/source_bundle.py` creates a deterministic source-only ZIP from one immutable 40-character Git commit, not from a dirty working tree. It refuses unsafe/unsupported tracked paths, fonts, keys, SQLite/pickle/model/cache/archive payloads, symlinks, oversized members, output-inside-repo, mutable refs, and overwrite. Verification requires an externally supplied archive SHA-256 and checks every member SHA-256, Git blob identity, mode, size and exact member set.

Exact source-delivery run `36019467569` at `65c8d6b0493432c16d83174aeff22b415583a703` completed successfully:

- stdlib delivery tests: **26 passed**;
- two independently built source ZIPs were byte-identical;
- source ZIP: **2,246,013 bytes**, **97 tracked source files** plus `SOURCE_MANIFEST.json`, SHA-256 `eb9404fbfd9a4d9fc22db57c0518ecb65510a192b7500277885f2747219bb6df`;
- fresh-directory restore + 39-wheel hash-lock install + `pip check`: PASS;
- launcher `doctor`: READY;
- actual launcher/start/shutdown smoke: **12/12** across intake-off and intake-on; real loopback status, no implicit inference/Book, Ctrl+C exit, listener closed;
- recovered Brain strict suite: **426 passed / 0 failed / 0 skipped**;
- recovered selection HTTP smoke: **32/32**;
- paid provider calls 0.

GitHub artifact `10816450623` downloaded SHA-256 `c70ba62ac0cc42dcbd9981f5fe025d6f242e2de19e6b8c64e208957648a68dbd`.

Long-term Drive archive created and immediately downloaded/read back:

- `mygpt-source-delivery-v1-20260925.zip`
- Drive ID `1b-YQbKedJSfRwQ5ZMHmWTaXjiQE2yo5m`
- 1,843,538 bytes
- SHA-256 `c70ba62ac0cc42dcbd9981f5fe025d6f242e2de19e6b8c64e208957648a68dbd`
- 13 members, ZIP CRC PASS; contains the exact source ZIP plus delivery/recovery evidence.

## 4. Parallel real-Book branch preserved, not merged here

PR #7 (`feat/book-live-selection-v1-20260923`) remains a separate Draft review line and is **not** silently merged into PR #6. Its existing Drive bundle is indexed here for recovery only:

- `mygpt-book-live-selection-v1-20260923.zip`
- Drive ID `1JLrTiZnRWLlN9WlZPO3tczop49ipyTjP`
- 43,805 bytes
- SHA-256 `656a93710cd48b7414c9742208ab3872abcda7cc0607cf497663329b38b2d58c`
- current PR #7 head observed at checkpoint time: `4e118054d9f3037a857d03c925f6d1641dd56979`.

The bundle contains the earlier Book lease receiver evidence; indexing it here does not resolve PR #5/#6/#7 conflicts, authenticate the user's installed Book APK, or authorize a merge.

## 5. Current limits

Still not accepted: Windows launcher/device execution, Android Studio app/APK/physical device, native overlay/soft keyboard, production multi-user transport, real provider teaching quality, arbitrary-document ingestion, Book notes/answers export, StudyRecord writes, or independent human/code review.

No ChatContextVault content was read. No screen capture was added. No paid model/provider call was made. No main write, force-push, history rewrite, delete, PR merge or destructive cleanup occurred.

## 6. Recovery

Start from `START_HERE.md`. The full source-delivery archive is the preferred current recovery artifact for PR #6 because it contains one exact source bundle and its clean-recovery evidence. GitHub remains authoritative for later commits/governance; Drive is the long-lived artifact vault.

## 7. Next safe work

Before combining PR #6 with the older parallel Book bridge, perform an independent review and a three-way conflict map across PR #5 / #6 / #7. Do not resolve conflicts by overwrite, rebase-away history, or automatic merge. In parallel, Windows/Android delivery can be prepared only through the project's Android Studio/device rules; real provider activation remains a separate explicit design/authorization milestone.
