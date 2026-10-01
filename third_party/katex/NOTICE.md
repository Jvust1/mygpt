# KaTeX 0.18.10: bounded Book formula preview

- Upstream: https://github.com/KaTeX/KaTeX
- Verified 2026-10-01: 20,414 GitHub stars, MIT license
- Release/tag and npm gitHead: `411da7029f5c095943c2805ce6db16c2be5f214d` (`v0.18.10`)
- Official package: https://registry.npmjs.org/katex/-/katex-0.18.10.tgz
- npm SHA-512 integrity: `sha512-/B6p9eY9DX7aHBfpkHdpirDTZ5QH9xTwL9y837PWuzuv41O5jFdqNQwVQEQsimY0/iVNkwBY4+4hMfhQ7d4Dbw==`
- `katex.mjs`: unchanged `package/dist/katex.mjs`, 603020 bytes, SHA-256 `694a531495903e374957e9a9c904a402e2f413762635df486c4cf6163320d1aa`
- `LICENSE`: unchanged upstream/package MIT license, Git blob `37c6433e3bedca7a97e08fe35d98582a5f7bac0c`, SHA-256 `766ccc1f306c885aa45542a9846bbd0a505b27a0374f146778171c2254ce18e3`

Copyright (c) 2013-2020 Khan Academy and other contributors. The complete MIT
license is retained beside the runtime. No upstream source modification.

Inspected source at the exact commit: `katex.ts` (public DOM `render` and
MathML output), `src/Settings.ts` (trust/strict/expansion/size settings), and
`src/functions/href.ts` / `src/functions/html.ts` (untrusted extension handling).

mygpt imports this module directly in `host/math-preview.js`. Existing accepted
Book/selection math parts reach that helper through `host/selection.js`,
`host/brain.js` and `host/reader.js`. The application requests native MathML
only: no KaTeX stylesheet, bundled fonts, CDN or network service is used.
The source packet, LaTeX, source hash, layer and prompt remain unchanged.

The application restricts input before parsing, forbids user macro definitions
and external/HTML commands, passes `trust:false`, fresh macros, finite expansion
and size limits, and falls back to exact raw text on unsupported/over-budget
formulae. Native MathML layout still depends on browser support. This is a local
presentation integration, not mathematical verification or Book device adoption.
