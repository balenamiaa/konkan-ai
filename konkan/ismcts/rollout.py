"""Rollout policies for IS-MCTS simulations."""

from __future__ import annotations

from ..state import KonkanState


def simulate(state: KonkanState, rng: np.random.Generator) -> float:
    """Return a neutral rollout value as scaffolding."""

    return 0.0
