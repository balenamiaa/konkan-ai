"""Search loop for the Konkan IS-MCTS implementation."""

from __future__ import annotations

import math
import random as py_random
from dataclasses import dataclass
from typing import Sequence, cast

from .. import actions as actions_module
from .. import encoding, rules
from .. import state as state_module
from ..determinize import sample_world
from ..state import KonkanState, PublicState
from . import policy, rollout
from .node import Node
from .opponents import OpponentModel


@dataclass(slots=True)
class SearchConfig:
    """Configuration values for IS-MCTS search."""

    simulations: int = 64
    exploration_constant: float = 1.2
    dirichlet_alpha: float | None = None
    dirichlet_weight: float = 0.25
    opponent_model: OpponentModel | None = None


def _select_action(node: Node, exploration_constant: float) -> int:
    total_visits = sum(node.visits)
    log_term = math.log(total_visits + 1.0)
    best_index = 0
    best_score = float("-inf")

    for idx, prior in enumerate(node.priors):
        visits = node.visits[idx]
        if visits == 0:
            ucb = float("inf")
        else:
            mean_value = node.total_value[idx] / visits
            ucb = mean_value + exploration_constant * math.sqrt(log_term / visits)
        # Encourage exploration based on prior weight.
        ucb += prior
        if ucb > best_score:
            best_score = ucb
            best_index = idx

    return best_index


def _normalise(values: Sequence[float]) -> list[float]:
    total = sum(values)
    if total <= 0.0:
        return [1.0 for _ in values]
    return [max(1e-8, value / total) for value in values]


def _dirichlet_noise(rng: object, alpha: float, size: int) -> list[float]:
    if size <= 0:
        return []
    samples: list[float] = []
    for _ in range(size):
        if hasattr(rng, "gammavariate"):
            sample = cast(py_random.Random, rng).gammavariate(alpha, 1.0)
        else:
            helper = py_random.Random()
            sample = helper.gammavariate(alpha, 1.0)
        samples.append(max(sample, 1e-8))
    total = sum(samples)
    return [sample / total for sample in samples]


def _apply_opponent_model(
    state: KonkanState,
    actions: Sequence[actions_module.PlayAction],
    priors: Sequence[float],
    model: OpponentModel | None,
) -> list[float]:
    if model is None:
        return list(priors)
    adjusted: list[float] = []
    for prior, action in zip(priors, actions):
        weight = model.prior_adjustment(state, action)
        adjusted.append(max(1e-8, prior * weight))
    return adjusted


def run_search(state: KonkanState, rng: object, config: SearchConfig) -> Node:
    """Run IS-MCTS rooted at ``state`` and return the populated root node."""

    public = state.public
    if not isinstance(public, PublicState):
        return Node(priors=[1.0], actions=[None])

    player_index = public.current_player_index
    player = state.players[player_index]
    if player.phase != state_module.TurnPhase.AWAITING_TRASH:
        return Node(priors=[1.0], actions=[None])

    hand_cards = encoding.cards_from_mask(player.hand_mask)
    play_actions = actions_module.legal_play_actions(
        state, player_index, max_discards=len(hand_cards) if hand_cards else 1
    )
    if not play_actions:
        return Node(priors=[1.0], actions=[None])

    priors = policy.evaluate_actions(state, play_actions, demand_samples=1)
    priors = _apply_opponent_model(state, play_actions, priors, config.opponent_model)
    priors = _normalise(priors)

    if (
        config.dirichlet_alpha is not None
        and config.dirichlet_alpha > 0
        and len(priors) > 1
        and 0.0 < config.dirichlet_weight <= 1.0
    ):
        noise = _dirichlet_noise(rng, config.dirichlet_alpha, len(priors))
        priors = [
            (1.0 - config.dirichlet_weight) * prior + config.dirichlet_weight * noise_value
            for prior, noise_value in zip(priors, noise)
        ]
        priors = _normalise(priors)

    node = Node(priors=priors, actions=play_actions)
    root_player = player_index

    for _ in range(max(1, config.simulations)):
        action_index = _select_action(node, config.exploration_constant)
        action = play_actions[action_index]
        simulated_root = sample_world(state, rng, actor_index=root_player)
        sim_state = simulated_root.clone_shallow()
        try:
            actions_module.apply_play_action(sim_state, root_player, action)
        except (rules.IllegalTrash, rules.IllegalDraw, RuntimeError):
            value = -1.0
        else:
            public_sim = sim_state.public
            if isinstance(public_sim, PublicState):
                next_actor = public_sim.current_player_index
                sim_state = sample_world(sim_state, rng, actor_index=next_actor)
            value = rollout.simulate(sim_state, root_player)

        node.visits[action_index] += 1
        node.total_value[action_index] += value

    return node
