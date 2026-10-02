"""AIRI-inspired character-card contract for MyGPT.

The field layout is adapted from Project AIRI's MIT-licensed
`packages/ccc/src/define/card.ts`. A card is descriptive data until a caller
explicitly approves it for conversion into a trusted MyGPT persona.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator

from .core import Contract, Identifier


class CompanionCharacterCard(Contract):
    schema_version: Literal["mygpt.character-card.v1"] = "mygpt.character-card.v1"
    card_id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=80)]
    nickname: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    version: Annotated[str, Field(min_length=1, max_length=80)] = "1"
    visual_skin_id: Identifier
    personality: Annotated[str, Field(max_length=2000)] | None = None
    scenario: Annotated[str, Field(max_length=2000)] | None = None
    system_prompt: Annotated[str, Field(max_length=3000)] | None = None
    post_history_instructions: Annotated[str, Field(max_length=2000)] | None = None
    greetings: Annotated[list[str], Field(max_length=16)] = Field(default_factory=list)
    greetings_group_only: Annotated[list[str], Field(max_length=16)] = Field(default_factory=list)
    tags: Annotated[list[str], Field(max_length=32)] = Field(default_factory=list)
    message_examples: Annotated[list[list[str]], Field(max_length=16)] = Field(default_factory=list)
    source: Annotated[list[str], Field(max_length=16)] = Field(default_factory=list)
    metadata: dict[str, bool | int | float | str] = Field(default_factory=dict)

    @field_validator("personality", "scenario", "system_prompt", "post_history_instructions")
    @classmethod
    def optional_text_is_trimmed(cls, value: str | None) -> str | None:
        if value is not None and value != value.strip():
            raise ValueError("text fields must be trimmed")
        return value

    @field_validator("greetings", "greetings_group_only", "tags", "source")
    @classmethod
    def validate_string_lists(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip() or item != item.strip():
                raise ValueError("list entries must be non-blank trimmed strings")
            if len(item) > 1000:
                raise ValueError("list entry too long")
            if any(ord(ch) < 32 and ch != "\t" for ch in item):
                raise ValueError("list entries contain control characters")
            if item not in result:
                result.append(item)
        return result

    @field_validator("message_examples")
    @classmethod
    def validate_message_examples(cls, value: list[list[str]]) -> list[list[str]]:
        for conversation in value:
            if not 1 <= len(conversation) <= 16:
                raise ValueError("each message example must have 1..16 lines")
            for line in conversation:
                if not isinstance(line, str) or len(line) > 1000:
                    raise ValueError("invalid message example line")
                if not (line.startswith("{{char}}: ") or line.startswith("{{user}}: ")):
                    raise ValueError(
                        "message example lines must start with {{char}}: or {{user}}:"
                    )
        return value

    def render_instructions(self) -> str:
        """Render one bounded trusted persona prompt after explicit approval."""
        parts = [f"Character identity: {self.name}."]
        if self.nickname:
            parts.append(f"Nickname: {self.nickname}.")
        if self.system_prompt:
            parts.append(self.system_prompt)
        if self.personality:
            parts.append("Personality:\n" + self.personality)
        if self.scenario:
            parts.append("Scenario:\n" + self.scenario)
        if self.post_history_instructions:
            parts.append(
                "Conversation consistency guidance:\n" + self.post_history_instructions
            )
        if self.message_examples:
            examples = ["\n".join(group) for group in self.message_examples[:2]]
            parts.append("Approved behavior examples:\n" + "\n---\n".join(examples))
        rendered = "\n\n".join(parts)
        if len(rendered) > 4000:
            raise ValueError("rendered persona instructions exceed 4000 characters")
        return rendered

    def to_persona(self, *, approved: bool = False):
        """Convert descriptive card data into system authority only after approval."""
        if approved is not True:
            raise PermissionError(
                "character card must be explicitly approved before becoming system persona"
            )
        # Local import prevents the card schema from becoming a runtime dependency
        # cycle for the lower-level conversation contracts.
        from .companion_chat import CompanionPersona

        return CompanionPersona(
            persona_id=self.card_id,
            display_name=self.nickname or self.name,
            visual_skin_id=self.visual_skin_id,
            instructions=self.render_instructions(),
        )


def load_character_card(path: str | Path, *, max_bytes: int = 65536) -> CompanionCharacterCard:
    target = Path(path)
    raw = target.read_bytes()
    if len(raw) > max_bytes:
        raise ValueError("character card exceeds size limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("invalid UTF-8 character card JSON") from None
    return CompanionCharacterCard.model_validate(value)
