# MYGPT-006: Linux browser-tool npm content lock

## Scope and reproduced gap

This bounded local candidate starts from [PR #64](https://github.com/Jvust1/mygpt/pull/64)
source commit `f08c1d9695b34e40fb735159a12b3a53b71686de`.
It does not inherit that commit's hosted acceptance.

The existing Linux math-preview step installs exact `playwright@1.62.1` into a
temporary prefix. Its official dependency is exact `playwright-core@1.62.1`,
which has no further dependencies. The optional `fsevents@2.3.2` is Darwin-only.
We did not reproduce floating transitive versions on Linux. npm already checks
registry-supplied integrity metadata; the gap is the absence of a checked-in,
reviewable and reusable resolved-tarball/SRI baseline.

## Minimal change

- `tools/browser/package.json` is private and requests only the already-used
  exact Playwright version. The dependency-free root package is unchanged.
- npm 11.9.0 generated `tools/browser/package-lock.json` (lockfile v3) from the
  official registry. It preserves full optional-platform metadata. All three
  registry entries have canonical `https://registry.npmjs.org/` tarball URLs and
  SHA-512 SRI values. Linux installs only Playwright and Playwright Core.
- The existing workflow copies both inputs into the original temporary prefix
  and runs `npm ci --ignore-scripts --no-audit --no-fund` with the explicit
  official registry. `NODE_PATH`, the runner's `google-chrome` selection and the
  actual math-preview browser test remain unchanged.
- `tools/browser/**` changes trigger the aggregate workflow on the bounded
  `fix/browser-tool-lock-dot-20261002` branch. Existing required jobs remain.

This uses npm's native locked-install behavior, including manifest/lock mismatch
rejection and unchanged input files, rather than a new resolver. See the official
[npm ci documentation](https://docs.npmjs.com/cli/v11/commands/npm-ci/) and
[lockfile format](https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/).

## Actual local verification

Linux, Node v24.19.0, npm 11.9.0; local candidate only. The compact
[evidence record](../governance/browser_tool_lock_evidence_20261002.json)
contains only fixed test statuses, versions, counts and input hashes.

1. Two real `npm ci` installs used separate initially empty prefixes and
   independent initially empty caches, each fetching from the official registry.
   Both yielded exactly `playwright@1.62.1` and `playwright-core@1.62.1`.
   A recursive package-root inventory, npm's installed lock and successful
   `npm ls --all --json` agreed; package and lock input bytes were unchanged.
2. A third isolated install used a temporary lock with one decoded digest byte
   flipped in Playwright Core's SRI. Real npm rejected it with `EINTEGRITY` and
   the SHA-512 checksum diagnostic; the corrupted input lock was not rewritten.
3. A fourth isolated install changed the temporary manifest's Playwright version
   to `1.62.0` but retained the original lock. Real npm rejected it with `EUSAGE`
   and explicitly reported that locked `1.62.1` does not satisfy `1.62.0`.
   The input lock was not rewritten. Arbitrary failure/network errors do not
   count as either negative acceptance result.
4. Root Python **204**, strict Brain **912**, upstream/component **49**,
   JavaScript **70** passed, with no failures/skips. Suite scopes overlap and
   must not be added together. Root includes **7** new offline structure and
   workflow-wiring tests; these seven are not actual npm-install experiments.

The real install experiments used empty npm user/global configuration files,
an isolated home and the environment's existing proxy/CA configuration. No user
npm credentials were loaded. Initial DNS/TLS configuration failures occurred
before the successful experiments and are not recorded as passing checks.
Downloads, node_modules, raw logs and the private full source archive are not
public deliverables. The repository contains no new runtime functionality.

## Reproduction and remaining boundaries

For a normal install, copy the two files to a new directory and run the exact
workflow's `npm ci` command there with a fresh cache. Preserve both source files
and compare their bytes before/after. Each negative experiment needs its own
temporary copy and cache; require the specific diagnostics above, then discard
the experiment without changing the committed inputs. Future intentional lock
updates should use npm's `--package-lock-only` generation and rerun these checks.

The existing hosted workflow now performs the locked install before its actual
browser test. Hosted acceptance for the new exact commit is still required and
must be recorded separately. No browser was launched during this local task.
The Chrome executable, runner image, Node/npm toolchain, other JavaScript or
Android dependency paths and Windows Python locks are not newly content-locked.
No bit-identical-build claim follows. MYGPT-006 remains partially addressed;
physical devices, models, licenses, merging and release decisions remain their
own gates.
