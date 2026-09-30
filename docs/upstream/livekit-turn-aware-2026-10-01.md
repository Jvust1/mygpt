# LiveKit Agents turn-aware transport — 2026-10-01

Upstream: `livekit/agents`  
Revision inspected: `d251b89e61fe5f8ba78e0b39b501d91b0856a2d0`  
License: Apache-2.0

mygpt already had a narrow AgentSession bridge. This fusion connects it to `VoiceTurnController`: a stale assistant lease is never spoken after a newer user turn has interrupted it. LiveKit remains an optional transport; persona, memory, supervision policy and Book context remain owned by mygpt.
