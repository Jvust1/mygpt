#!/usr/bin/env python3
"""Run a local MyGPT companion chat against loopback Ollama.

This is an explicit developer entry point. It never auto-starts a cloud provider
and never converts chat text into long-term memory unless the user uses
`:remember`.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import uuid

from mygpt_brain.companion_chat import CompanionChatRequest, CompanionChatRuntime
from mygpt_brain.character_card import load_character_card
from mygpt_brain.memory_store import MemoryRecord, MemoryStore
from mygpt_brain.providers import OllamaResponder
from mygpt_brain.session_store import ChatSessionStore


def _memory_id() -> str:
    return "mem-" + uuid.uuid4().hex[:24]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Installed Ollama model name")
    parser.add_argument("--data-dir", type=Path, default=Path(".mygpt-local"))
    parser.add_argument("--session-id", default=None)
    parser.add_argument(
        "--card",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "personas" / "3714430278.json",
        help="Explicitly approved local MyGPT character-card JSON",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    session_id = args.session_id or ("chat-" + uuid.uuid4().hex[:20])
    card = load_character_card(args.card.expanduser().resolve())
    # --card is an explicit developer/user choice at process launch. The card
    # cannot self-approve through its JSON fields because extra fields are rejected.
    persona = card.to_persona(approved=True)

    with (
        MemoryStore(data_dir / "memory.sqlite3") as memory,
        ChatSessionStore(data_dir / "chat.sqlite3") as sessions,
    ):
        runtime = CompanionChatRuntime(
            persona=persona,
            responder=OllamaResponder(args.model),
            memory_store=memory,
            session_store=sessions,
            recent_turn_limit=24,
            request_timeout_seconds=45,
        )
        print(
            f"MyGPT local chat | model={args.model} | session={session_id} "
            f"| persona={persona.persona_id} | skin={persona.visual_skin_id}"
        )
        if sessions.session_persona(session_id) is None and card.greetings:
            print(f"{persona.display_name}> {card.greetings[0]}")
        print("Commands: :remember <text> | :memories | :quit")
        while True:
            try:
                raw = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not raw:
                continue
            if raw == ":quit":
                return 0
            if raw == ":memories":
                rows = memory.recent(namespace=persona.persona_id, limit=20)
                if not rows:
                    print("(no explicit memories)")
                for item in rows:
                    print(f"- {item.memory_id}: [{item.kind}] {item.text}")
                continue
            if raw.startswith(":remember "):
                text = raw[len(":remember "):].strip()
                if not text:
                    print("memory text is empty")
                    continue
                now = datetime.now(timezone.utc)
                record = MemoryRecord(
                    memory_id=_memory_id(),
                    namespace=persona.persona_id,
                    kind="user_instruction",
                    text=text,
                    source="user_explicit",
                    created_at=now,
                    updated_at=now,
                )
                memory.put(record)
                print(f"remembered> {record.memory_id}")
                continue

            request = CompanionChatRequest(
                request_id="req-" + uuid.uuid4().hex[:24],
                session_id=session_id,
                persona_id=persona.persona_id,
                text=raw,
            )
            try:
                result = __import__("asyncio").run(runtime.send(request))
            except RuntimeError as error:
                print(f"error> {error}")
                continue
            print(f"{persona.display_name}> {result.assistant_message.content}")


if __name__ == "__main__":
    raise SystemExit(main())
