"""Local-only chat provider adapters.

No adapter here accepts arbitrary remote URLs. The first real provider path is
Ollama on loopback, matching mygpt's local-first architecture.
"""
from __future__ import annotations

import asyncio
import json
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from .companion_chat import ChatPrompt
from .airi_act import ACT_PRESENTATION_INSTRUCTION


class OllamaResponder:
    def __init__(
        self,
        model: str,
        *,
        endpoint: str = "http://127.0.0.1:11434/api/chat",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not isinstance(model, str) or not model.strip() or len(model) > 160:
            raise ValueError("model must contain 1..160 characters")
        if endpoint != "http://127.0.0.1:11434/api/chat":
            raise ValueError("prototype only permits the fixed loopback Ollama endpoint")
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be in (0, 60]")
        self.model = model.strip()
        self.endpoint = endpoint
        self.timeout_seconds = float(timeout_seconds)

    async def __call__(self, prompt: ChatPrompt) -> str:
        return await asyncio.to_thread(self._call_sync, prompt)

    def _call_sync(self, prompt: ChatPrompt) -> str:
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
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        req = urllib_request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    raise RuntimeError("ollama returned non-200")
                raw = response.read(1_000_001)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise RuntimeError("ollama unavailable") from error
        if len(raw) > 1_000_000:
            raise RuntimeError("ollama response too large")
        try:
            value = json.loads(raw.decode("utf-8"))
            text = value["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            raise RuntimeError("invalid ollama response") from None
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("ollama returned empty reply")
        return text
