"""Local voice turn-control ideas adapted from Pipecat's realtime pipeline model.

Upstream reference: pipecat-ai/pipecat @
49dea682fb84bfc515d881d00dfeaaa9e9f1075f (BSD-2-Clause).

This module does not import Pipecat. It absorbs the small, stable idea that
new user speech invalidates an in-flight assistant turn.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnLease:
    generation: int
    interrupted_previous: bool


class VoiceTurnController:
    def __init__(self) -> None:
        self._generation = 0
        self._assistant_active = False

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def assistant_active(self) -> bool:
        return self._assistant_active

    def begin_user_turn(self) -> TurnLease:
        interrupted = self._assistant_active
        self._generation += 1
        self._assistant_active = False
        return TurnLease(self._generation, interrupted)

    def begin_assistant_turn(self, lease: TurnLease) -> bool:
        if lease.generation != self._generation:
            return False
        self._assistant_active = True
        return True

    def finish_assistant_turn(self, lease: TurnLease) -> bool:
        if lease.generation != self._generation:
            return False
        self._assistant_active = False
        return True

    def is_current(self, lease: TurnLease) -> bool:
        return lease.generation == self._generation
