"""Search loop scaffolding for IS-MCTS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..determinize import sample_world
from ..state import KonkanState
from .node import Node


@dataclass(slots=True)
class SearchConfig:
    """Configuration values for IS-MCTS search."""

    simulations: int = 1
    exploration_constant: float = 1.0


def run_search(state: KonkanState, rng: object, config: SearchConfig) -> Node:
    """Run a placeholder search returning an empty node."""

    determinized = sample_world(state, rng)
    priors = [1.0]
    node = Node(priors=priors, actions=[None])
    node.visits[0] = config.simulations
    node.total_value[0] = 0.0
    return node
