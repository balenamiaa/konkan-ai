from __future__ import annotations

import math

from konkan.ismcts import search
from konkan.ismcts.node import Node


def test_normalise_handles_zero_sum() -> None:
    values = [0.0, 0.0]
    normalised = search._normalise(values)

    assert normalised == [1.0, 1.0]


def test_select_action_prefers_high_ucb() -> None:
    node = Node(priors=[0.1, 0.1], actions=["a", "b"])
    node.visits = [10, 5]
    node.total_value = [6.0, 1.0]

    index = search._select_action(node, exploration_constant=0.5)

    assert index == 0


def test_select_action_chooses_unvisited_branch() -> None:
    node = Node(priors=[0.2, 0.2, 0.2], actions=["a", "b", "c"])
    node.visits = [3, 0, 2]
    node.total_value = [1.0, 0.0, 0.6]

    index = search._select_action(node, exploration_constant=1.0)

    assert index == 1
