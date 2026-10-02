#!/usr/bin/env python3
"""Serve the approved MyGPT persona through a token-authenticated loopback API.

The model/persona/storage choices are process-start configuration. HTTP callers
cannot change them. The bearer token is handed off through a local owner-only
file and is never printed to stdout.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets

from mygpt_brain.character_card import load_character_card
from mygpt_brain.companion_chat import CompanionChatRuntime
from mygpt_brain.companion_service import create_companion_server
from mygpt_brain.memory_store import MemoryStore
from mygpt_brain.providers import OllamaResponder
from mygpt_brain.session_store import ChatSessionStore


def _write_token_file(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        os.write(descriptor, (token + "\n").encode("utf-8"))
    finally:
        os.close(descriptor)


def _remove_own_token_file(path: Path, token: str) -> None:
    try:
        current = path.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if secrets.compare_digest(current, token):
        try:
            path.unlink()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Installed Ollama model name")
    parser.add_argument("--data-dir", type=Path, default=Path(".mygpt-local"))
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--authorization-seconds", type=int, default=1800)
    parser.add_argument(
        "--card",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "personas" / "3714430278.json",
        help="Explicitly approved local MyGPT character-card JSON",
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=None,
        help="Owner-only bearer-token handoff file; defaults inside --data-dir",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    card = load_character_card(args.card.expanduser().resolve())
    # Supplying --card (or accepting the default in this explicit launcher) is
    # the user/developer approval boundary. Card JSON itself cannot self-approve.
    persona = card.to_persona(approved=True)
    token_file = (
        args.token_file.expanduser().resolve()
        if args.token_file is not None
        else data_dir / "companion.token"
    )

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
        server = create_companion_server(
            runtime,
            port=args.port,
            authorization_seconds=args.authorization_seconds,
        )
        _write_token_file(token_file, server.token)
        try:
            server.start()
            print(
                f"MyGPT companion service: {server.origin} "
                f"| persona={persona.persona_id} | skin={persona.visual_skin_id}",
                flush=True,
            )
            print(
                f"Bearer token handoff: {token_file} "
                "(token value is intentionally not printed)",
                flush=True,
            )
            print(
                "scope=LOOPBACK_ONLY provider=OLLAMA_LOCAL "
                "remote_bind=false auto_memory=false",
                flush=True,
            )
            while server.thread and server.thread.is_alive():
                server.thread.join(timeout=1)
        except KeyboardInterrupt:
            return 0
        finally:
            server.close()
            _remove_own_token_file(token_file, server.token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
