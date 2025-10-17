"""Tree node definitions used by IS-MCTS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence


@dataclass(slots=True)
class Node:
    """A search node storing statistics for each explored action."""

    priors: Sequence[float]
    actions: Sequence[object]
    visits: List[int] = field(init=False)
    total_value: List[float] = field(init=False)

    def __post_init__(self) -> None:
        self.visits = [0 for _ in self.priors]
        self.total_value = [0.0 for _ in self.priors]

    def best_action_index(self) -> int:
        """Return the index of the best action according to visit count."""

        return int(max(range(len(self.visits)), key=self.visits.__getitem__, default=0))
