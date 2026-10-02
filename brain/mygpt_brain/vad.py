"""Optional Silero VAD adapter for local utterance gating.

Upstream: snakers4/silero-vad @
1e261b036686cd0017d500ee96acd1c4ba572a9d (MIT).
"""
from __future__ import annotations

from typing import Any, Iterable


class SileroVADDetector:
    """Wrap a Silero VADIterator-like callable behind has_speech(frames)."""

    def __init__(self, iterator: Any) -> None:
        if not callable(iterator):
            raise TypeError("iterator must be callable")
        self._iterator = iterator

    def reset(self) -> None:
        reset = getattr(self._iterator, "reset_states", None)
        if callable(reset):
            reset()

    def has_speech(self, frames: Iterable[Any]) -> bool:
        self.reset()
        for frame in frames:
            event = self._iterator(frame)
            if isinstance(event, dict) and "start" in event:
                return True
        return False


def create_silero_vad_detector(model: Any, **iterator_kwargs: Any) -> SileroVADDetector:
    try:
        from silero_vad import VADIterator
    except ImportError as exc:
        raise RuntimeError(
            "Silero VAD is optional; install brain[voice] before enabling VAD"
        ) from exc
    return SileroVADDetector(VADIterator(model, **iterator_kwargs))
