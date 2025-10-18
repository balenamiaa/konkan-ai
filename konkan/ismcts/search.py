"""Search loop for the Konkan IS-MCTS implementation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .. import encoding, rules
from .. import state as state_module
from ..determinize import sample_world
from ..state import KonkanState, PublicState
from . import policy, rollout
from .node import Node


@dataclass(slots=True)
class SearchConfig:
    """Configuration values for IS-MCTS search."""

    simulations: int = 64
    exploration_constant: float = 1.2


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


def _legal_discards(hand_mask: int) -> list[int]:
    cards = encoding.cards_from_mask(hand_mask)
    cards.sort()
    return cards


def run_search(state: KonkanState, rng: object, config: SearchConfig) -> Node:
    """Run IS-MCTS rooted at ``state`` and return the populated root node."""

    public = state.public
    if not isinstance(public, PublicState):
        return Node(priors=[1.0], actions=[None])

    player_index = public.current_player_index
    player = state.players[player_index]
    if player.phase != state_module.TurnPhase.AWAITING_TRASH:
        return Node(priors=[1.0], actions=[None])

    actions = _legal_discards(player.hand_mask)
    if not actions:
        return Node(priors=[1.0], actions=[None])

    priors = policy.evaluate_actions(state, actions)
    node = Node(priors=priors, actions=actions)

    for _ in range(max(1, config.simulations)):
        action_index = _select_action(node, config.exploration_constant)
        action_card = actions[action_index]
        simulated_root = sample_world(state, rng)
        sim_state = simulated_root.clone_shallow()
        try:
            rules.trash_card(sim_state, player_index, action_card)
        except rules.IllegalTrash:
            value = -1.0
        else:
            value = rollout.simulate(sim_state, player_index)

        node.visits[action_index] += 1
        node.total_value[action_index] += value

    return node
