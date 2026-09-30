# Pipecat-inspired voice turn control — 2026-09-30

Upstream reference: `pipecat-ai/pipecat`  
Revision inspected: `49dea682fb84bfc515d881d00dfeaaa9e9f1075f`  
License: BSD-2-Clause

mygpt does not vendor Pipecat. It absorbs the realtime conversation concept that new user speech invalidates an in-flight assistant turn. `VoiceTurnController` is fused into `VoiceActivationRuntime`, exposing whether a new activated utterance interrupted the previous assistant turn.
