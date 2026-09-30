"""Optional openWakeWord gate for local voice activation.

Upstream: dscripka/openWakeWord @
368c03716d1e92591906a84949bc477f3a834455 (Apache-2.0).

This module does not download models and does not open a microphone. It only
adapts an already-configured openWakeWord Model-like object to mygpt's
deterministic local boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class WakeWordResult:
    triggered: bool
    label: str = ""
    score: float = 0.0


class OpenWakeWordGate:
    """Turn openWakeWord prediction mappings into a stable trigger contract."""

    def __init__(
        self,
        model: Any,
        *,
        threshold: float = 0.5,
        cooldown_frames: int = 4,
    ) -> None:
        if not callable(getattr(model, "predict", None)):
            raise TypeError("model must provide predict(frame)")
        if not 0.0 < float(threshold) <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        if not isinstance(cooldown_frames, int) or isinstance(cooldown_frames, bool) or cooldown_frames < 0:
            raise ValueError("cooldown_frames must be a non-negative integer")
        self._model = model
        self.threshold = float(threshold)
        self.cooldown_frames = cooldown_frames
        self._cooldown_remaining = 0

    def reset(self) -> None:
        self._cooldown_remaining = 0
        reset = getattr(self._model, "reset", None)
        if callable(reset):
            reset()

    def process(self, frame: Any) -> WakeWordResult:
        raw = self._model.predict(frame)
        if not isinstance(raw, Mapping):
            raise RuntimeError("openWakeWord predict() must return a mapping")

        best_label = ""
        best_score = 0.0
        for label, value in raw.items():
            try:
                score = float(value)
            except (TypeError, ValueError):
                continue
            if score > best_score:
                best_label = str(label)
                best_score = score

        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            return WakeWordResult(False, best_label, best_score)

        triggered = bool(best_label) and best_score >= self.threshold
        if triggered:
            self._cooldown_remaining = self.cooldown_frames
        return WakeWordResult(triggered, best_label, best_score)


def create_openwakeword_gate(
    *,
    wakeword_models: list[str] | None = None,
    threshold: float = 0.5,
    cooldown_frames: int = 4,
    **model_kwargs: Any,
) -> OpenWakeWordGate:
    """Create the optional upstream model lazily.

    Model downloads are intentionally excluded. The caller is responsible for
    placing approved local model files and passing their paths.
    """
    try:
        from openwakeword.model import Model
    except ImportError as exc:
        raise RuntimeError(
            "openWakeWord is optional; install brain[voice] before enabling wake-word mode"
        ) from exc

    kwargs = dict(model_kwargs)
    if wakeword_models is not None:
        kwargs["wakeword_models"] = list(wakeword_models)
    return OpenWakeWordGate(
        Model(**kwargs),
        threshold=threshold,
        cooldown_frames=cooldown_frames,
    )
