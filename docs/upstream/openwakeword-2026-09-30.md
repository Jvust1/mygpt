# openWakeWord integration — 2026-09-30

Upstream: `dscripka/openWakeWord`  
Revision inspected: `368c03716d1e92591906a84949bc477f3a834455`  
License: Apache-2.0

mygpt absorbs only a small wake-word boundary:
- `OpenWakeWordGate.process(frame)` accepts caller-supplied local PCM frames.
- The upstream model remains optional and lazily imported.
- No microphone access, model download, or network access happens in this adapter.
- Trigger cooldown prevents repeated activation from one spoken wake phrase.

This is intended to sit before the existing local voice / Sherpa path:
`wake word -> speech recognition -> mygpt brain -> companion response`.
