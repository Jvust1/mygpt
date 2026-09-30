"""Tiny Pipecat test doubles; real SDK coverage lives in realtime_tests/."""


class Frames:
    class TranscriptionFrame:
        def __init__(self, text, finalized=True):
            self.text, self.finalized = text, finalized

    class LLMTextFrame:
        def __init__(self, text):
            self.text, self.metadata = text, {}

    class LLMFullResponseStartFrame: pass
    class LLMFullResponseEndFrame: pass
    class InterruptionFrame: pass
    class CancelFrame: pass
    class EndFrame: pass


class Processor:
    def __init__(self):
        self.pushed, self.errors = [], []
        self.cleaned = False

    async def process_frame(self, frame, direction): pass
    async def push_frame(self, frame, direction): self.pushed.append((frame, direction))
    async def push_error(self, *, error_msg): self.errors.append(error_msg)
    async def cleanup(self): self.cleaned = True


def create_processor(bridge, **kwargs):
    from mygpt_brain.pipecat_bridge import create_pipecat_companion_processor
    return create_pipecat_companion_processor(
        bridge, frame_processor_base=Processor, frame_types=Frames,
        downstream_direction="down", **kwargs,
    )
