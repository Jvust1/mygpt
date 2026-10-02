# MYGPT-006: bounded Python dependency reproducibility

## Scope and input

This local candidate starts from PR #60 source commit
`765419ff740c6b4076dd818dc709bef6e46ada34`, externally verified source ZIP SHA-256
`5465615f2a9f3a201df43be92183901fc3227dead1c1d435cf0c3a150ef300dd`.
It changes the integrated Linux Python acceptance environment and Windows Python
build environment. It does not close all of MYGPT-006 or imply release readiness.
Existing core-only `requirements-linux-py313.lock` remains unchanged for its
historical/standalone workflows.

- `brain/requirements-linux-py313-full.lock`: 85 exact public PyPI artifacts,
  including all transitive dependencies of the existing `test`, `integrations`,
  `realtime`, and `lexical-test` extras, plus explicit pip/build tooling
- `brain/requirements-windows-py313-build.lock`: 54 exact public PyPI wheels,
  including the successful #60 Windows integration/test/PyInstaller/Playwright
  package closure and explicit pip tooling
- Existing product versions are preserved independently per platform. Windows
  and Linux already had different transitive versions; this does not silently
  unify or upgrade them
- pip is explicitly pinned to 26.2.1 and setuptools to 84.0.0. The latter is
  already present in the successful Windows freeze and is now the explicit
  Linux source-build backend, rather than an unbounded isolated-build download

## Evidence labels and target checks

`lock_from_report.py` reads actual pip JSON reports. It does not resolve versions
or invent Windows environment fields. Windows candidate generation uses a real
Linux pip cross-target dry run with every package from the successful native
Windows freeze explicitly pinned, including colorama and pywin32. pip's
`--platform` alone does not provide a native Windows marker environment.
The lock metadata retains the actual Linux resolver environment and labels the
result `cross-target-dry-run`; it is not a Windows installation report.

The verifier checks the target before installation: GIL-enabled 64-bit CPython
3.13, Linux x86_64/glibc >= 2.34 or Windows AMD64 as appropriate. It binds the lock
to exact `pyproject.toml` bytes and required extras. Another OS, architecture,
Python minor, free-threaded build, source manifest change, missing root pin,
malformed lock or changed bootstrap pin fails closed.

After installation, the verifier compares the complete installed distribution
name/version set, rejects duplicates, missing/extra/changed packages, and checks
that the one local source distribution is noneditable and originated from the
exact checked source directory. pip and setuptools are locked normal entries,
not broadly ignored exceptions. The full native pip installation report must
also match the lock's target and complete name/version/SHA-256 set. A report
alone cannot establish whether pip actually installed anything; native CI's
install command, installed-set verification, and tests provide that evidence.

## One narrow source exception, not an all-wheel Linux lock

The existing Pipecat -> num2words dependency requires `docopt==0.6.2`. Official
PyPI provides no compatible wheel for this exact version; a real all-wheel
resolution fails. Upgrading/removing a product dependency is outside this fix.
The only accepted source archive is:

- Name/version: `docopt==0.6.2`
- URL: `https://files.pythonhosted.org/packages/a2/55/8f8cab2afd404cf578136ef2cc5dfb50baa1761b68c9da1fb1e4eed343c9/docopt-0.6.2.tar.gz`
- SHA-256: `49b3a825280bd66b3aa83585ef59c4a8c82f2c8a522dbe754a8bc8d08c85c491`

The generator requires that complete tuple; the verifier requires the exact
name/version/hash and Linux target. All other registry packages must be wheels.
Hash-locked pip/setuptools are installed first, then artifact acquisition uses
`--only-binary=:all: --no-binary=docopt --no-build-isolation --require-hashes`.
Installation is from that local artifact directory with `--no-index`,
`--no-cache-dir`, and `--no-build-isolation`; the tested setuptools version builds
docopt without another wheel package or hidden build-dependency resolution.
The project itself is installed from the exact checkout with `--no-index
--no-build-isolation --no-deps`, avoiding a second dependency resolution.

## Actual local verification

On CPython 3.13.15/Linux x86_64:

- Two separate clean virtual environments rebuilt all 85 locked artifacts from
  the local artifact directory using no index and no pip cache; both actually
  built the exact docopt source archive and passed `pip check`
- Both native installation reports matched all 85 version/hash tuples, and
  the full installed set was exactly those 85 plus the checked local project
- Actual pip hash enforcement rejected a deliberately wrong aiofiles digest
  before installation
- Lock tests cover platform/interpreter/libc mismatch, exact source exception,
  source-manifest drift, missing/extra/version-changed distributions, wrong
  native artifact hashes, duplicate entries and incorrect local-source origins
- Both clean environments pass strict Brain **912 passed / 0 skipped** and
  all **49 upstream/story cases / 0 skipped**; root Python **103 passed**,
  Node **70 passed / 0 skipped**, lock-tool tests **66 passed / 0 skipped**,
  compilation and both edited workflow YAML parses pass
- All 54 Windows wheel candidates were actually downloaded and SHA-256 checked
  using the explicit win_amd64/cp313 target

Native Windows install/report verification, PyInstaller build, EXE/restart/math
browser acceptance remain **not run for this local candidate**. The reusable
Windows CI now performs those steps plus the lock-tool tests (requiring zero
skips) in its own clean environment and fails the existing required gate if any step is missing or fails. A successful #60 build
is the version input, not proof that this changed workflow passed.

## Reproduction

The complete commands are in the installation steps of
`.github/workflows/companion-fusion-acceptance.yml` and
`.github/workflows/desktop-delivery.yml`. Keep the download and offline install
phases distinct. Preserve the report and source commit from the exact native
run. Do not regenerate a lock from a partial install report in an already-filled
environment, and do not turn a cross-target report into a claimed native report.
To update dependencies, first establish the intentional version change,
resolve the full target closure with official PyPI, regenerate the lock with
explicit target/evidence-kind/pyproject arguments, then repeat clean native
installation, artifact-set checks, strict tests, and applicable native build.

## Remaining boundaries

This proves a bounded package acquisition/install contract, not bit-identical
built wheels or Windows executables. Runner OS, Python patch distribution,
MSVC/system libraries, Android SDK/Gradle/Maven inputs, Node packages, and
browser binaries retain their separate provenance/locking boundaries.
Playwright's Python wheel is hash-locked; `playwright install chromium` still
uses the pinned package's browser revision and is not a separately SHA-locked
Chromium binary. No new browser CDN/download system is introduced. Existing
standalone older workflows are not all migrated by this bounded change.

No action-SHA repair is credited here: those pins were already repaired in #60.
No public binary distribution, merge, deployment, paid provider call, private
user-data upload, automatic retention/deletion, policy or license change is
included. Original runtime tests and the 49 actual-upstream/story cases remain
mandatory; physical-device and real-provider gates remain separate.
