"""Optional OpenAI Agents SDK responder for the mygpt companion brain.

Upstream: openai/openai-agents-python @
acdbf289b498e9c10849debb5170aac540ac5828 (MIT).

mygpt remains authoritative for persona, bounded conversation history, local
memory, Book context and supervision policy. The Agents SDK is used only as an
optional execution layer for tools, handoffs and agent orchestration.
"""
from __future__ import annotations

from typing import Any, Mapping

from .companion_chat import ChatPrompt, CompanionReply


_FORBIDDEN_STATE_KEYS = {"session", "conversation_id", "previous_response_id"}


class OpenAIAgentsResponder:
    """Adapt a preconfigured Agents SDK Agent into CompanionChatRuntime."""

    def __init__(
        self,
        agent: Any,
        *,
        runner: Any,
        run_kwargs: Mapping[str, Any] | None = None,
    ) -> None:
        if not callable(getattr(runner, "run", None)):
            raise TypeError("runner must provide async run()")
        options = dict(run_kwargs or {})
        blocked = sorted(_FORBIDDEN_STATE_KEYS.intersection(options))
        if blocked:
            raise ValueError(
                "mygpt owns durable conversation state; forbidden Agents SDK state keys: "
                + ", ".join(blocked)
            )
        self.agent = agent
        self.runner = runner
        self.run_kwargs = options

    @staticmethod
    def _input_items(prompt: ChatPrompt) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for message in prompt.provider_messages():
            role = str(getattr(message, "role", "") or "").strip()
            content = str(getattr(message, "content", "") or "")
            if role not in {"system", "developer", "user", "assistant"}:
                raise ValueError(f"unsupported provider role for Agents SDK: {role!r}")
            if not content.strip():
                continue
            items.append({"role": role, "content": content})
        if not items:
            raise RuntimeError("companion prompt produced no Agents SDK input items")
        return items

    async def __call__(self, prompt: ChatPrompt) -> str | CompanionReply:
        result = await self.runner.run(
            self.agent,
            input=self._input_items(prompt),
            **self.run_kwargs,
        )
        if not hasattr(result, "final_output"):
            raise RuntimeError("Agents SDK result missing final_output")
        output = result.final_output

        if isinstance(output, str):
            text = output.strip()
            if not text:
                raise RuntimeError("Agents SDK returned empty final_output")
            return text

        if hasattr(output, "model_dump"):
            output = output.model_dump()
        if isinstance(output, Mapping):
            try:
                return CompanionReply.model_validate(dict(output))
            except Exception as exc:
                raise RuntimeError("Agents SDK structured final_output is not a CompanionReply") from exc

        raise RuntimeError(
            f"unsupported Agents SDK final_output type: {type(output).__name__}"
        )


def create_openai_agents_responder(
    agent: Any,
    **run_kwargs: Any,
) -> OpenAIAgentsResponder:
    """Create the optional responder lazily without selecting an Agent/model."""

    try:
        from agents import Runner
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI Agents SDK is optional; install brain[agents] before enabling it"
        ) from exc
    return OpenAIAgentsResponder(
        agent,
        runner=Runner,
        run_kwargs=run_kwargs,
    )
