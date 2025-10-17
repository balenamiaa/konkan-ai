"""Opponent modeling hooks for IS-MCTS."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OpponentModel:
    """Placeholder structure describing opponent behavior."""

    name: str = "baseline"

    def estimate_response(self) -> float:
        """Return a neutral estimate awaiting implementation."""

        return 0.0
