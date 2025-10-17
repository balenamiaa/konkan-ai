"""Determinization utilities for information-set MCTS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .state import KonkanState


@dataclass(slots=True)
class DeterminizationConfig:
    """Configuration values for determinization sampling."""

    seed: int
    max_samples: int = 1


def sample_world(state: KonkanState, rng: Any) -> KonkanState:
    """Return a placeholder determinized world (no-op for the initial scaffolding)."""

    return state.clone_shallow()
