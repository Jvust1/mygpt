# Governance checkpoint · MYGPT-004 / MYGPT-011 · 2026-10-02

## Scope and source of truth

This is local technical governance reconciliation. Its initial worktree and eight
historical original identities came from #60 `765419ff740c6b4076dd818dc709bef6e46ada34`; the
last verified checkpoint has now advanced independently to #61. It changes entry documents, governance
metadata, an offline validator/test suite and a minimal source-recovery artifact
publication boundary. It does not change runtime code, dependency locks, main,
branch protection, licensing, retention policy or contact/SLA
commitments. The original audit at
[0776119 / AUDIT_REPORT_20261002.md](https://github.com/Jvust1/mygpt/blob/0776119ccae16deacbb92884860c75fd3f806aea/docs/AUDIT_REPORT_20261002.md)
reviewed the older #48 implementation and is left unchanged.

The last verified source checkpoint is [Draft PR #61](https://github.com/Jvust1/mygpt/pull/61),
branch `fix/dependency-locks-dot-20261002`, tested commit
`68ea57e1aec5488b6ff24973f7ef2b781ca29bff`, based on #60
(`fix/windows-exact-head-dot-20261002` at `765419ff740c6b4076dd818dc709bef6e46ada34`).
[Run 36973557038](https://github.com/Jvust1/mygpt/actions/runs/36973557038)
completed successfully with 9 successful jobs. Public metadata was retrieved
2026-10-02 06:35:25 UTC; the completed run ended at 06:34:42 UTC.
The retained public run/artifact fields are in
[`verified_checkpoint_evidence_20261002.json`](../governance/verified_checkpoint_evidence_20261002.json).
They are unsigned observations, not a signature or proof that the remote is unchanged.

This checkpoint is not the identity of this later edited checkout. The offline
validator reports the checkout independently. A future documentation or code
commit needs its own exact-head hosted CI; no future SHA or success is invented.

## Verified input evidence

- Strict Python 912, upstream/component 49, root Python 103, JavaScript 70; zero failures/skips
- Actual Android host APK build, Java 8/17 boundaries and source recovery passed
- Hosted Windows: 31 tests + 147 subtests, 5 native executable checks and 23 Microsoft Edge checks
- Lock-tool tests: 66 passed, zero skips; native Linux 85-package and Windows 54-package name/version/hash installation reports and complete installed sets matched exactly
- Zero external browser requests, JavaScript errors or live model calls; synthetic input/output
- Android host build does not establish Companion V2/llama/sherpa JNI or combined physical-device acceptance

Counts have overlapping scopes and must not be added into a unique test total.
#58 (`a5862faf8e976ca310bb4d743fea78c5c8211d01`, run `36964436329`) supplied the
Android required gate; #59 (`16a731c47aa4c03956745caa63b5fbe0610e6cba`,
run `36966318787`) supplied lossless receipt/storage changes. Neither older run
is used as #61 acceptance. #60 supplied the preceding native Windows checkpoint;
#61 actually executed the new native lock/install/report checks, PyInstaller,
EXE/restart/Edge and mandatory aggregate gates. Cross-target resolver reports
are not substituted for those native installation results.

### Exact artifacts and expiry

- [Source artifact 11212940613](https://github.com/Jvust1/mygpt/actions/runs/36973557038/artifacts/11212940613)
  - Downloaded outer artifact ZIP digest: `c1ff55b49537b30e3778f0e370cd1fd7c0a4458cbcbbdec8f7b2fb5c7c80eb28`
  - Inner `mygpt-source.zip`: 5,466,032 bytes; SHA-256 `9e77a8f3f315f3a5abfc53d410f93721de857a3fc6a86964423ce0870b4c4949`
  - 472 tracked source files plus one generated `SOURCE_MANIFEST.json` member
  - Recorded expiry: 2026-10-05 06:27:41 UTC
- [Windows evidence artifact 11212461882](https://github.com/Jvust1/mygpt/actions/runs/36973557038/artifacts/11212461882)
  - Downloaded artifact ZIP SHA-256: `c4cec4edd09bd9c1fda65ac6c9ab69d72d5a92fa3817b6215edd2455967f4afe`
  - 17 synthetic evidence files (including dependency reports/tests); no EXE, APK or personal database
  - Recorded expiry: 2026-10-05 06:33:47 UTC

Hosted retention is 3 days. These URLs are short-lived evidence, not a permanent
archive promise. The source package excludes dependencies, models, private skin
inputs and external submodule sources. Later edited source will have different
file counts and hashes; 472 refers only to the verified #61 input.

## New public recovery artifact is metadata only

The full legacy source tree still contains historical private vault references.
New source-recovery CI therefore does **not** upload the complete source ZIP,
raw build/recovery logs or the evidence directory. It still builds the exact
commit twice, compares both archives, strictly verifies all members, restores
the complete tree into a new directory and runs recovered Python, JavaScript,
strict Brain, launcher/HTTP and Java checks.

Only after those gates succeed, `scripts/build_public_recovery_evidence.py`
verifies archive/report/source identities, recovered source bytes, strict JUnit
and zero-failure/skip test evidence, then writes `public-recovery-summary.json`.
The `source-recovery-evidence` artifact uploads that one file. Its closed schema
contains only fixed enums, source commit/archive SHA, counts and booleans. No
arbitrary input keys, source paths, logs, archive members or private strings are
projected; failures emit one fixed error code without raw input or paths.

This JSON is evidence of recovery testing, **not a downloadable source delivery**.
The #61 source artifact/hash above is historical input evidence and cannot be
represented as a new candidate download. Complete bundles remain available only
through a separately authorized private delivery. The existing local bundler,
source format and original Git history are preserved.

## Reconciliation and compatibility

- README, START_HERE, CURRENT_STATE and HANDOFF now point to the same verified input and separate pending gates
- `active_branch` and `current_pr` identify that checkpoint, explicitly not the current checkout
- Old candidate objects were removed from the current state view; product/authority boundaries and existing schema names remain
- Repository-wide reference search found no runtime/test consumer of the moved candidate fields; external ad hoc consumers must follow the immutable source links in the historical index rather than assuming old fields are still current
- The current artifact list contains only the checkpoint source/evidence pair; all prior artifact identities/statuses remain in the immutable historical Git manifest and private original archive; they are not copied into the public index
- The old Jonah browser result is explicitly historical; the old skin maturity/required-next fields are historical planning labels, not a new evaluation
- `desktop_delivery_current.json` records current hosted verification without republishing the historical portable package
- SECURITY_POLICY links existing reporting guidance and technical boundaries without inventing an email, private channel availability or SLA

The [HISTORICAL ledger](HISTORICAL_GOVERNANCE_LEDGER_20261002.md) is now a
provenance-only index of eight immutable public GitHub commit/path references,
original byte counts and SHA-256 values. **It contains no original file text or
private vault references.** Original text remains in existing Git history and
the private original #60 source archive; neither is deleted or republished by
this change. Public current metadata contains no vault object identifiers.

The history source is independently bound to `historical_source_manifest` in
the evidence file, and need not equal the latest verified checkpoint. The local
SOURCE_MANIFEST still declares its original #60 recovery input, never the edited
checkout. EVALUATION_LEDGER is restored to its exact original bytes and excluded
from this change; current evaluation is recorded only in this checkpoint.

## Offline validator contract

```sh
python scripts/validate_governance.py
python -m unittest discover -s tests -p 'test_governance_checkpoint.py' -v
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.test.mjs
```

The validator compares current owner, branch, PR, tested commit, run, conclusion,
artifact/run repository and commit identities, inner/outer digest scopes, exact
artifact set, test counts and required desktop evidence keys. It checks visible
entry summaries as well as machine markers, and compares the public historical
index to its metadata. Its default result is `INDEX_CONSISTENCY_ONLY` with
`original_bytes_verified: false`: absent original text cannot be verified
offline. Book/Live and historical owners are not mechanically rewritten.

Negative coverage includes owner/branch/commit/run/artifact drift, wrong API
payload binding/digest, missing desktop evidence, changed file counts/sizes, old 12-file native evidence
being used for the 17-file checkpoint, historical-source identity drift,
wrong expiry scope, historical UI being promoted, altered historical indexes,
reintroduced private-vault metadata, optional archive byte/hash mismatches and
visible prose drifting behind a correct marker.

Git checkout identity is an observed HEAD/branch plus dirty flag, never CI
acceptance. Source-only recovery compares the present files/hashes and complete
file set to the manifest. A modified recovery tree reports
`DIRTY_OR_UNVERIFIED` and only `archive_declared_source`; an exact match reports
`MATCHES_UNSIGNED_MANIFEST`, still requiring an external trusted archive hash.
Missing/unreadable Git and absent/invalid manifest yield `UNAVAILABLE`, never a
fallback to the tested checkpoint. The validator does not fetch remote state,
prove authenticity, execute a model, or accept a device.

An optional local archive check reuses `source_bundle.py verify`, requires a
caller-supplied trusted external archive hash, and verifies the archive commit,
full source manifest and eight indexed original file bytes. It reads locally,
extracts or uploads nothing, and returns no private file contents:

```sh
python scripts/validate_governance.py --historical-source-zip /path/to/trusted-old-source.zip --historical-source-sha256 5465615f2a9f3a201df43be92183901fc3227dead1c1d435cf0c3a150ef300dd
```

A supplied archive can yield `VERIFIED_AGAINST_CALLER_SUPPLIED_ARCHIVE_HASH`;
authenticity still depends on trust in that external hash, not the internally
consistent index or a remote signature. With no supplied archive it does not
claim original-byte verification.

### Local verification for this change

Isolated governance worktree on the original #60 runtime, Linux/Python 3.13,
reused existing dependency environment read-only. These are distinct from the
#61 hosted 912/103 counts above and do not claim a local #61 integration pass:

- Governance suite refreshed for #61: 12 tests, including 43 identity/scope mutation subcases, passed
- Public recovery summary/workflow: 8 tests passed, covering closed output keys, extra/private input fields, commit/hash mismatch, missing/failed/skipped recovery and fixed redacted failures
- Full root suite with public recovery boundary: 118 tests passed, zero failures/skips
- Strict Brain: 862 passed, zero failures/skips
- Actual upstream/component: 49 passed, zero failures/skips
- JavaScript: 70 passed, zero failures/skips
- Optional trusted #60 local archive: 466 source files verified and all eight indexed originals matched, without adding their text to the public payload
- Trusted #61 source archive: existing `source_bundle.py verify` verified all 472 files, source commit and external SHA-256; the original #60 local manifest and existing original archive were not rewritten

Strict runners were invoked with new evidence directories using:

```sh
python brain/scripts/verify_integrations.py --output /new/private/evidence/strict
python brain/scripts/verify_fusion_upstreams.py --output /new/private/evidence/upstream
```

These are local tests of the edited files, not a new hosted run or a fresh
Windows/Android/device execution. This batch does not install dependencies or
run real models. Linux results cannot substitute for later exact-head hosted
Windows/Android gates.

## Remaining gates and safe next step

main remains a skeleton and the review stack remains unmerged. Review these
bounded governance changes on the verified #61 dependency-lock baseline, then establish
new exact-head hosted evidence for any published candidate.

Do not publish a Spine APK until distribution entitlement is verified. User
Windows/Xiaomi 14, Book SDK adoption/signing, Companion V2/llama/sherpa full
native behavior, model quality/performance, microphone, audible TTS and skin/PiP
experience remain unaccepted.

Receipt storage improved disk growth without deleting history: full ID output
is O(history), repeated cumulative CPU is near quadratic, old receipts are not
shrunk, nondurable mode remains unbounded, and no TTL/automatic cleanup is
implemented. Before schema 2, stop all old processes and keep a private complete
backup. No mixed-version use or in-place downgrade. No real user database was
migrated in this batch.

MYGPT-006 is only partially remediated: native Linux/Windows Python acquisition
and installation are hash-verified; Android/Node/browser/toolchain boundaries
remain, and bit-identical builds are not claimed.

Repository license, branch protection/main, retention and contact/SLA decisions
remain with the owner. This technical cleanup does not close those policy or
release questions.
