# Silero VAD integration — 2026-09-30

Upstream: `snakers4/silero-vad`  
Revision inspected: `1e261b036686cd0017d500ee96acd1c4ba572a9d`  
License: MIT

mygpt uses the upstream `VADIterator` only behind a small local boundary. The adapter consumes caller-supplied frames, detects the first speech-start event, resets iterator state between utterances, and never opens a microphone or downloads a model by itself.

Intended local pipeline:

`openWakeWord -> Silero VAD -> Sherpa/STT -> mygpt brain -> Live companion`.
