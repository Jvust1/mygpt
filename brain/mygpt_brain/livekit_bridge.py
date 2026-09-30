"""Optional LiveKit Agents transport for mygpt companion sessions.

Upstream: livekit/agents @
d251b89e61fe5f8ba78e0b39b501d91b0856a2d0 (Apache-2.0).

This adapter uses only the open-source Agents framework API. It does not use
LiveKit proprietary model weights or model-licensed turn detectors.
"""
from __future__ import annotations

from typing import Any


class LiveKitAgentBridge:
    """Wrap AgentSession.start()/say() behind a narrow mygpt transport boundary."""

    def __init__(self, session: Any) -> None:
        if not callable(getattr(session, "start", None)):
            raise TypeError("session must provide async start()")
        if not callable(getattr(session, "say", None)):
            raise TypeError("session must provide say()")
        self._session = session
        self._started = False

    @property
    def started(self) -> bool:
        return self._started

    async def start(self, *, agent: Any, room: Any) -> None:
        await self._session.start(agent=agent, room=room)
        self._started = True

    async def say(self, text: str, *, allow_interruptions: bool = False) -> Any:
        if not self._started:
            raise RuntimeError("LiveKit session has not been started")
        content = str(text).strip()
        if not content:
            raise ValueError("text cannot be blank")
        result = self._session.say(
            content,
            allow_interruptions=allow_interruptions,
        )
        if hasattr(result, "__await__"):
            return await result
        return result

    async def say_when_ready(
        self,
        voice_gate: Any,
        text: str,
        *,
        allow_interruptions: bool = False,
    ) -> bool:
        consume_ready = getattr(voice_gate, "consume_ready", None)
        if not callable(consume_ready):
            raise TypeError("voice_gate must provide consume_ready()")
        if not consume_ready():
            return False
        await self.say(text, allow_interruptions=allow_interruptions)
        return True


def create_livekit_agent_bridge(**session_kwargs: Any) -> LiveKitAgentBridge:
    """Create AgentSession lazily; no LiveKit model package is required."""
    try:
        from livekit.agents import AgentSession
    except ImportError as exc:
        raise RuntimeError(
            "LiveKit Agents is optional; install brain[livekit] before enabling realtime transport"
        ) from exc
    return LiveKitAgentBridge(AgentSession(**session_kwargs))
