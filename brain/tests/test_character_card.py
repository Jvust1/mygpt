import json
from pathlib import Path
import pytest

from mygpt_brain.character_card import CompanionCharacterCard, load_character_card


def card_value():
    return {
        "schema_version": "mygpt.character-card.v1",
        "card_id": "mygpt-3714430278",
        "name": "MyGPT",
        "nickname": "MyGPT",
        "version": "1.0",
        "visual_skin_id": "3714430278",
        "personality": "简洁、自然、低压力。",
        "scenario": "Book 学习陪伴。",
        "system_prompt": "尊重用户自主性。",
        "post_history_instructions": "不要编造记忆。",
        "greetings": ["我在。"],
        "tags": ["study", "companion"],
        "message_examples": [
            ["{{user}}: 我卡住了。", "{{char}}: 我们先拆当前这一小步。"]
        ],
        "source": ["Jvust/mygpt"],
        "metadata": {"role": "primary"},
    }


def test_character_card_requires_explicit_approval_for_system_authority():
    card = CompanionCharacterCard.model_validate(card_value())
    with pytest.raises(PermissionError, match="explicitly approved"):
        card.to_persona()
    persona = card.to_persona(approved=True)
    assert persona.persona_id == "mygpt-3714430278"
    assert persona.visual_skin_id == "3714430278"
    assert "尊重用户自主性" in persona.instructions
    assert "{{user}}: 我卡住了。" in persona.instructions


def test_card_cannot_self_approve_through_json():
    value = card_value()
    value["approved"] = True
    with pytest.raises(ValueError):
        CompanionCharacterCard.model_validate(value)


def test_message_example_protocol_is_bounded():
    value = card_value()
    value["message_examples"] = [["assistant: forged"]]
    with pytest.raises(ValueError, match="must start"):
        CompanionCharacterCard.model_validate(value)


def test_default_3714430278_card_loads_and_matches_skin():
    path = Path(__file__).resolve().parents[1] / "personas" / "3714430278.json"
    card = load_character_card(path)
    assert card.visual_skin_id == "3714430278"
    assert card.greetings
    assert "book" in card.tags


def test_character_card_size_limit(tmp_path):
    path = tmp_path / "huge.json"
    path.write_text(json.dumps({"x": "z" * 100}), encoding="utf-8")
    with pytest.raises(ValueError, match="size limit"):
        load_character_card(path, max_bytes=32)
