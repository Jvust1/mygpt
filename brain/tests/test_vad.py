from mygpt_brain.vad import SileroVADDetector


class FakeIterator:
    def __init__(self):
        self.calls = 0
        self.reset_called = 0

    def reset_states(self):
        self.reset_called += 1

    def __call__(self, _frame):
        self.calls += 1
        if self.calls == 2:
            return {"start": 160}
        return None


def test_silero_vad_detector_stops_on_speech_start():
    upstream = FakeIterator()
    detector = SileroVADDetector(upstream)
    assert detector.has_speech([1, 2, 3]) is True
    assert upstream.calls == 2
    assert upstream.reset_called == 1
