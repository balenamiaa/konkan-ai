from __future__ import annotations

from konkan.ismcts.node import Node


def test_node_initialises_visit_and_value_arrays() -> None:
    priors = [0.2, 0.8, 0.5]
    node = Node(priors=priors, actions=[None, None, None])

    assert node.visits == [0, 0, 0]
    assert node.total_value == [0.0, 0.0, 0.0]


def test_best_action_index_returns_most_visited() -> None:
    node = Node(priors=[0.4, 0.6], actions=["a", "b"])
    node.visits = [3, 5]

    assert node.best_action_index() == 1


def test_best_action_index_defaults_to_zero_when_equal() -> None:
    node = Node(priors=[0.5, 0.5], actions=["a", "b"])
    node.visits = [2, 2]

    assert node.best_action_index() == 0
