# Pipecat realtime companion bridge — 2026-09-30

Upstream: `pipecat-ai/pipecat`  
Revision inspected: `49dea682fb84bfc515d881d00dfeaaa9e9f1075f`  
License: BSD-2-Clause

mygpt does not vendor Pipecat. The integration keeps a narrow boundary:

`Pipecat TranscriptionFrame -> PipecatCompanionBridge -> CompanionChatRuntime -> TextFrame -> downstream TTS/output`

Pipecat can own transport, STT, TTS and realtime frame scheduling. mygpt keeps persona, memory, Book context, supervision and companion policy authoritative. The dependency is optional and imported lazily.
