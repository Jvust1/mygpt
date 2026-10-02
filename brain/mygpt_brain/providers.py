"""Local-only, cancellable Ollama chat provider.

No adapter here accepts arbitrary remote URLs. The first real provider path is
Ollama on loopback, matching mygpt's local-first architecture.

The async request/context-managed stream lifecycle is adapted from the official
ollama/ollama-python client at 8785556559ec1d045d27a1ba9d9cc7330c3d3cb1.
Copyright (c) Ollama. MIT; see third_party/ollama-python/LICENSE.
"""
from __future__ import annotations

import asyncio

import httpx

from .companion_chat import ChatPrompt
from .airi_act import ACT_PRESENTATION_INSTRUCTION
from .json_boundary import BoundaryError, load_object

MAX_RESPONSE_BYTES = 1_000_000
_ASYNC_CLIENT = httpx.AsyncClient


class OllamaResponder:
    def __init__(
        self,
        model: str,
        *,
        endpoint: str = "http://127.0.0.1:11434/api/chat",
        timeout_seconds: float = 30.0,
        port: int = 11434,
        keep_alive: str | None = None,
        num_predict: int | None = None,
    ) -> None:
        if not isinstance(model, str) or not model.strip() or len(model) > 160:
            raise ValueError("model must contain 1..160 characters")
        if endpoint != "http://127.0.0.1:11434/api/chat":
            raise ValueError("prototype only permits the fixed loopback Ollama endpoint")
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be in (0, 60]")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("port must be an integer in 1..65535")
        if "cloud" in model.lower():
            raise ValueError("local model name required")
        if keep_alive is not None and (type(keep_alive) is not str or keep_alive != "0"):
            raise ValueError("keep_alive must be None or the explicit unload value '0'")
        if num_predict is not None and (type(num_predict) is not int or not 1 <= num_predict <= 2048):
            raise ValueError("num_predict must be None or an integer in 1..2048")
        self.keep_alive = keep_alive
        self.num_predict = num_predict
        self.model = model.strip()
        self.endpoint = f"http://127.0.0.1:{port}/api/chat"
        self.timeout_seconds = float(timeout_seconds)

    async def __call__(self, prompt: ChatPrompt) -> str:
        messages = [
            {"role": item.role, "content": item.content}
            for item in prompt.provider_messages()
        ]
        # Provider output is normalized by CompanionChatRuntime before it can
        # reach the native API, voice bridge, or persisted conversation.
        messages.insert(1, {"role": "system", "content": ACT_PRESENTATION_INSTRUCTION})
        payload = {
            "model": self.model,
            "stream": False,
            "messages": messages,
        }
        # Preserve the shared Companion/voice provider's existing defaults.
        # Only callers choosing an explicit policy add these wire fields.
        if self.keep_alive is not None:
            payload["keep_alive"] = self.keep_alive
        if self.num_predict is not None:
            payload["options"] = {"num_predict": self.num_predict}
        try:
            # Unlike to_thread(urlopen), cancellation exits these async
            # contexts and closes the in-flight HTTP connection. No provider
            # host/API key/proxy is inherited from the environment.
            async with asyncio.timeout(self.timeout_seconds):
                async with _ASYNC_CLIENT(
                    timeout=self.timeout_seconds,
                    follow_redirects=False,
                    trust_env=False,
                    headers={"Accept": "application/json", "Accept-Encoding": "identity"},
                ) as client:
                    # Keep Ollama's stream=False wire contract, while reading
                    # the HTTP body incrementally to enforce a hard byte cap.
                    async with client.stream("POST", self.endpoint, json=payload) as response:
                        if response.status_code != 200:
                            raise RuntimeError("ollama returned non-200")
                        if response.headers.get("content-encoding", "identity").lower() != "identity":
                            raise RuntimeError("unsupported ollama response encoding")
                        raw = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise RuntimeError("ollama response too large")
                            raw.extend(chunk)
        except (httpx.HTTPError, TimeoutError, OSError):
            raise RuntimeError("ollama unavailable") from None
        try:
            value = load_object(bytes(raw), max_bytes=MAX_RESPONSE_BYTES)
            if value.get("error"):
                raise RuntimeError("ollama returned an error")
            text = value["message"]["content"]
        except (BoundaryError, KeyError, TypeError):
            raise RuntimeError("invalid ollama response") from None
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("ollama returned empty reply")
        return text
