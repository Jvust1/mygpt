# AIRI integration

Upstream: https://github.com/SEKAI-OS/AIRI
Imported: 2026-09-30
Target: Jvust/mygpt

Initial vendored modules support character state, memory, plugins and voice-related integration.

License: MIT. See LICENSE.

## Continued integration — 2026-09-30

Source repository: https://github.com/SEKAI-OS/AIRI

Reference upstream work:
- https://github.com/SEKAI-OS/AIRI/commit/3c6817244227051df1b4b03aadf16a59a4231298

This batch extends the voice/audio side with AIRI's stream-kit packaging plus speech-intent bus/runtime code. The queue and pipeline-runtime files are minimally adapted for isolated vendoring while retaining the upstream design and MIT attribution. Existing mygpt code outside vendor/airi is untouched.
