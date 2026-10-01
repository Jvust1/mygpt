from mygpt_brain.wakeword import OpenWakeWordGate


class FakeModel:
    def __init__(self, rows):
        self.rows = list(rows)
        self.reset_called = False

    def predict(self, frame):
        assert frame == b"pcm"
        return self.rows.pop(0)

    def reset(self):
        self.reset_called = True


def test_gate_triggers_on_best_score_and_respects_cooldown():
    model = FakeModel(
        [
            {"hey_mygpt": 0.72, "other": 0.1},
            {"hey_mygpt": 0.99},
            {"hey_mygpt": 0.99},
            {"hey_mygpt": 0.99},
        ]
    )
    gate = OpenWakeWordGate(model, threshold=0.7, cooldown_frames=2)

    first = gate.process(b"pcm")
    assert first.triggered is True
    assert first.label == "hey_mygpt"
    assert first.score == 0.72

    assert gate.process(b"pcm").triggered is False
    assert gate.process(b"pcm").triggered is False
    assert gate.process(b"pcm").triggered is True


def test_gate_ignores_invalid_scores_and_can_reset_upstream_model():
    model = FakeModel([{"bad": object(), "wake": 0.4}])
    gate = OpenWakeWordGate(model, threshold=0.5)
    result = gate.process(b"pcm")
    assert result.triggered is False
    assert result.label == "wake"
    gate.reset()
    assert model.reset_called is True
