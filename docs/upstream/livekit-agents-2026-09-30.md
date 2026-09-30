# LiveKit Agents integration — 2026-09-30

Upstream: `livekit/agents`  
Revision: `d251b89e61fe5f8ba78e0b39b501d91b0856a2d0`  
License: Apache-2.0

mygpt uses only the open-source AgentSession transport surface: `start(agent=..., room=...)` and `say(...)`. The adapter does not depend on LiveKit proprietary model weights or model-licensed turn detectors.

It can consume the existing mygpt VoiceTurnGate READY state before speaking, so the local pipeline can be:
`openWakeWord -> Silero VAD -> STT/brain -> LiveKit room/avatar transport`.
