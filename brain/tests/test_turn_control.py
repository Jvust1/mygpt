from mygpt_brain.turn_control import VoiceTurnController


def test_new_user_turn_invalidates_inflight_assistant():
    turns = VoiceTurnController()
    first = turns.begin_user_turn()
    assert turns.begin_assistant_turn(first) is True
    second = turns.begin_user_turn()
    assert second.interrupted_previous is True
    assert turns.is_current(first) is False
    assert turns.finish_assistant_turn(first) is False
    assert turns.begin_assistant_turn(second) is True
