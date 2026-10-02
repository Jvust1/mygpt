# Windows exact-head verification and frozen KaTeX resources

## Review scope

Independent candidate `fix/windows-exact-head-dot-20261002`, based on
[PR #59](https://github.com/Jvust1/mygpt/pull/59) at
`16a731c47aa4c03956745caa63b5fbe0610e6cba`. The input's seven-job aggregate,
including 1k/10k receipt-growth, Android host and source recovery, passed in
[run 36966318787](https://github.com/Jvust1/mygpt/actions/runs/36966318787).
That evidence does not establish a Windows build of this candidate.

The audit's MYGPT-005 is still valid at the input: Windows delivery only
triggered on the older `feat/desktop-delivery-20260925` branch. This change
introduces a mandatory Windows native check for the current aggregate.

## Reproduced packaging defect

The existing PyInstaller command copied `desktop_ui`, `host`, `companion` and
the Brain package metadata, but omitted `third_party/katex/katex.mjs` imported
by the newer math preview. Reconstructing exactly those static data roots and
starting the real HTTP service produced:

- `/host/brain.js`: 200
- `/host/math-preview.js`: 200
- `/third_party/katex/katex.mjs`: **404**

The new artifact-root test uses the actual builder's `--add-data` arguments,
not a second test-only resource list. It proves the old omission and verifies
the fixed service from an isolated `_internal` directory.

## Minimal resource fix

Package the three existing public, pinned MIT KaTeX files explicitly: runtime,
complete `LICENSE`, and `NOTICE.md`. Compare every required frozen static asset
to the source bytes, and verify the three immutable KaTeX hashes before boot.
Reject missing/changed assets, symlinks and unexpected files in the KaTeX directory.

No font, CDN, model, private Live skin or broad third-party directory is added.
Legal notices are verified on the frozen filesystem; their HTTP routes remain
404. The existing static allowlist and runtime request authority are unchanged.

## Actual Windows gate

`desktop-delivery.yml` becomes a reusable native-verification workflow. The old
standalone 9/25 push/dispatch publication path is retired in this candidate.
The aggregate calls Windows only after `production-components` succeeds, then
requires production, Android, recovery **and Windows** to report success.
An always-evaluated child gate also requires the native Windows job itself.
Skipped, cancelled or failed jobs cannot count as successful acceptance.

Linux keeps its full AF_UNIX/offline/POSIX tests. Windows runs the appropriate
HTTP/persistence/artifact-root tests, PyInstaller, the actual EXE, Edge or
Chromium, and restart checks. Checkout and evidence bind to the exact Git SHA;
action versions are immutable SHA pins. This does not configure branch protection.

The native browser test covers:

- Pinned renderer bytes served by the frozen executable's own HTTP server
- Visible native MathML and nonzero layout bounds
- Exact raw LaTeX and source hash preserved before/after actual TestModel response
- Malformed/hostile/over-budget formulas remain raw; replace/clear and view budgets
- Notes, timers, idempotent backup import and native restart persistence
- Math rendering after restart, no JavaScript errors or external page requests
- Existing model/intake consent defaults and zero live model calls

Only the EXE subprocess gets an isolated temporary synthetic `LOCALAPPDATA`.
Startup diagnostics come from that test-owned profile, never a user's/default
profile. One synthetic native-math screenshot permits independent visual review.

## Publication and local packaging

CI uploads an explicit allowlist of synthetic test metadata, hashes, logs and
the one screenshot. It does **not** upload the EXE, a portable distribution ZIP,
private data, models or user profile logs. Existing source-only recovery remains
unchanged. A successful runner test is not distribution-license verification or
acceptance on the user's Windows computer.

Local packaging is preserved as an explicit option, after native checks pass:

```powershell
python tools/build_windows_delivery.py --source-commit (git rev-parse HEAD) --evidence-dir "$env:TEMP/mygpt-native-evidence" --local-package-dir "$env:TEMP/mygpt-private-local-review-new"
```

Choose a new local output directory appropriate to the machine; the sample path
is not a model-storage location. The optional output contains portable/source/
verification ZIPs, `PACKAGE_MANIFEST.json` and checksums. The output must not
already exist or be inside package/evidence directories; this prevents recursive
self-inclusion. Creating local files does not authorize uploading or distributing
them. CI never passes `--local-package-dir`.

## Local verification and limits

- Isolated artifact-root tests exercise every static route and exact renderer/
  license/notice bytes; old omission and changed/missing-resource failures are tested
- Workflow tests require exact checkout, four-component aggregate and explicit
  evidence upload paths; every unsuccessful/missing required component fails
- Real temporary Git/ZIP tests preserve optional local packaging and hashes
- Linux root regression, strict Brain, existing pinned-upstream checks, JavaScript
  tests, compilation and YAML parsing were run; final counts are recorded in the PR
- **Actual Windows EXE and browser execution is pending until the new exact-head
  hosted run completes. Linux tests cannot substitute for that proof**

MYGPT-006 remains open: existing package versions are pinned, but the Windows
transitive dependency tree is not a complete platform hash lock. Browser/runtime
versions and installed dependencies are retained as evidence. User-device testing,
real Book adoption/signing, model quality, microphone/TTS, main policy and binary
distribution entitlement remain separate gates. No real user data is used here.
