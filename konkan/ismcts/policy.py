"""Policy heuristics for initializing IS-MCTS priors."""

from __future__ import annotations

from typing import Sequence

from ..state import KonkanState


def evaluate_actions(state: KonkanState, actions: Sequence[object]) -> list[float]:
    """Return uniform priors as an initial placeholder."""

    if not actions:
        return [1.0]
    return [1.0 for _ in actions]
