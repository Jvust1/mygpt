# Actual Book formula preview with KaTeX

The accepted-source preview previously showed every math part as raw LaTeX.
It now invokes pinned KaTeX 0.18.10 to construct native MathML DOM for fractions,
roots, matrices and other supported notation in the selection, Brain and static
reader pages. The original LaTeX remains available in an expandable raw view.
Text parts continue to use textContent, and source packets/hashes, provenance,
prompt copying, replies and model behavior are unchanged.

The official MIT distribution is retained unmodified in `third_party/katex/`.
The upstream had 20,414 stars when checked on 2026-10-01. Exact release/commit,
package integrity, file hashes and license are recorded in its NOTICE.
No KaTeX fonts or stylesheet, CDN, model, package-time script or runtime network
service is used. MathML relies on the browser's native layout and fonts.

## Untrusted input and fallback

The helper accepts at most 1000 UTF-16 units, 32 brace levels and 80 backslashes
per parsed formula, and at most 16 parsed formulas / 8000 input units per view.
Macro-definition, expansion-programming, URL and HTML-extension commands remain
raw text; TeX double-caret escapes also remain raw. KaTeX receives trust=false,
strict errors, maxExpand=200, maxSize=10 and a fresh macro object each time.
Unsupported, malformed, over-budget or oversized output falls back to the exact
source text. The helper uses KaTeX's DOM API, never an HTML-parser injection.

These are bounded preview rules, not a general TeX sandbox or a hard real-time
deadline. Complex unsupported formulas remain readable as LaTeX. Rendering is
presentation, not proof that the formula is correct, that Book is connected, or
that the source is authoritative.

## Verification

`node --test tests/math-preview.test.mjs` executes the actual pinned renderer,
source/license hash checks, budget boundaries and production entrypoint checks.
`tests/math-preview-browser.cjs` drives real Chromium and a test-owned Python
HTTP service: accepted synthetic source -> MathML -> unchanged Brain/TestModel
receipt, malicious/unsupported/oversized fallback, raw source/hash preservation,
mobile layout, per-view budgets, clear/replacement and no external requests.
It records a screenshot and measured render time. The combined acceptance
workflow runs it with Playwright 1.62.1 and hosted Chrome.

Local core and root/JavaScript checks pass; the local Chromium process could not
open its IPC socket in this execution environment, so local browser assertions
have not run. The draft's exact-head hosted run must establish browser success
before this slice can be called accepted. Device/APK/live-model/audio acceptance
remains outside this presentation change.
