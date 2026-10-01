# Coherent companion fusion: main-targeted review snapshot

This is a separate draft snapshot for review against `main`, not a merge,
deployment or device-acceptance decision. The original review branches remain.

## Immutable inputs

- Current main baseline: `bb35f6d34e05ed1de7ac8b3ef71c76f0cbe9f258`
- Reviewed implementation tree: [PR #55](https://github.com/Jvust1/mygpt/pull/55),
  `1eac69dc03548b5c6926fc5c7eb23d98d55853e5`
- Implementation evidence: [run 36804686015](https://github.com/Jvust1/mygpt/actions/runs/36804686015)
- Proposed aggregate branch: `feat/companion-fusion-main-dot-20261001`

The snapshot commit is parented to the current main baseline and contains the
reviewed implementation tree plus the bounded reconciliation described below.
No main ref is changed, no existing PR is merged/closed, and no parent-history
merge is performed. The implementation's original source/license provenance
remains available in its review stack and in `third_party/`.

## Runtime equivalence and main preservation

Runtime, Android, provider, UI, upstream and Brain test files are unchanged from
the reviewed implementation tree. Aggregate-only changes are:

- Preserve main's `CONTRIBUTING.md` and `SECURITY.md` verbatim
- Combine all main ignore patterns with feature test-output rules and exclude
  the existing CLI's default private `.mygpt-local/` database/token directory
- Keep main's validation workflow/actions/permissions and repair its intended
  filename scan, with fail-closed command failure handling and synthetic tests
- Admit only the two exact retained root documents in source packaging; do not
  broaden allowed root filenames, forbidden paths/extensions or binary exceptions
- Reconcile README/handoff/governance and retain both old README versions verbatim
- Add this branch to the existing combined acceptance/source-recovery workflow

The filename check reads names, not secret contents. Its intended `.env`,
`.env.*` (except `.env.example`), `.pem` and `.key` matching and `.git` exclusion
remain. Synthetic prohibited/allowed-path tests exercise the actual workflow
script; there is no actual secret material in fixtures or logs.

The source builder still verifies historical v1/v2 bundles. The only root-scope
additions are `CONTRIBUTING.md` and `SECURITY.md`. The tracked Gradle wrapper
remains the sole hash-checked bootstrap-jar exception; external llama.cpp/sherpa
Gitlinks remain exact metadata references without fetched/bundled source trees.

## Functional paths and evidence

The actual code composes AIRI ACT/history semantics, Pipecat frame/TTS ownership,
Ollama async requests, sklearn-derived retrieval, Gson Android parsing, explicit
memory/audit and SQLite receipt recovery. The tests cover invalid/long input,
interruption/cancellation, replay/restart, revoked/expired authorization, Book
freshness/budget boundaries, Unicode preservation and persistent-memory edits.

The immutable implementation run passed 826 strict Python and 49 actual-upstream/
compatibility/story cases without failures/skips, 65 root Python and 66 JavaScript
cases, and 22 entrypoints each on Java 8 and Java 17 `--release 8`. Its recovered
source passed 826/65/66/22 plus 12 launcher and 32 input-boundary checks.
These are implementation-input results. The aggregate's own final head, root
test count, terminal run and source hash belong in its PR evidence, not a
self-referential assertion inside this source snapshot.

### Reproduce supported source-level checks

For the hash-locked Linux/Python 3.13 environment, follow README and:

```bash
python -m unittest discover -s tests -p 'test_*.py' -q
node --test tests/*.test.mjs
```

From `brain/`, run `scripts/verify_integrations.py` and
`scripts/verify_fusion_upstreams.py` into new output directories. Both gates fail
on missing required dependencies/cases, failures or skips. The optional gate
executes actual pinned Pipecat/sklearn and unchanged AIRI source oracles.

For Java, use the verified Gson 2.14.0 jar and
`android_spike/tools/run_boundary_smoke.sh` on Java 8 or Java 17. The hosted gate
does not permit the local source/target-only fallback. It verifies 327 Gson,
109 sklearn, 128 AIRI, 3520 history-budget and 1288 Book Unicode cases/projections,
plus lifecycle and native-boundary smoke entrypoints. It does not compile an APK.

For source-only recovery, see [FUSION_SOURCE_RECOVERY_20260930.md](FUSION_SOURCE_RECOVERY_20260930.md).
Verify the trusted external SHA-256 before extraction. Member hashes detect
damage; the manifest is not an authenticity signature. Dependencies are external,
and hosted source artifacts expire after three days.

## Remaining gates and explicit limits

Actual Android Activity/Kotlin/APK/JNI, Windows/Xiaomi 14, real Book signing and
adoption, live model performance/teaching quality, microphones, audible TTS and
Live character/device visuals remain unaccepted. Synthetic model responses and
audio generation do not replace these gates. No default model is selected.

Receipt replay is data recovery, not proof of audible delivery. Android output
leases guard callbacks, not native backend lifetime. Noncooperative Python
callbacks can exceed deadlines while stale results are rejected. The native
body budget does not bound total header receipt. Memory edit serialization is
per instance, not across processes. Lexical recall remains candidate-bounded.

No models, private skin/source archives, recordings, personal chat databases or
credentials are added. The current five qualifying upstream integrations are
listed with current star/license evidence in README; hardening legacy optional
components is not counted as new adoption.
