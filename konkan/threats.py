"""Threat evaluation helpers used by IS-MCTS heuristics."""

from __future__ import annotations

from . import encoding, rules
from .state import KonkanState


def _next_player_index(state: KonkanState, actor_index: int) -> int:
    players = state.players
    if not players:
        return actor_index
    return (actor_index + 1) % len(players)


def card_enables_sarf(state: KonkanState, player_index: int, card_id: int) -> bool:
    """Return True if ``player_index`` could sarf ``card_id`` immediately."""

    if player_index < 0 or player_index >= len(state.players):
        return False
    if not state.table:
        return False

    clone = state.clone_shallow()
    clone_player = clone.players[player_index]
    if not clone_player.has_come_down:
        return False
    if not encoding.has_card(clone_player.hand_mask, card_id):
        clone_player.hand_mask = encoding.add_card(clone_player.hand_mask, card_id)

    for meld_index in range(len(clone.table)):
        if rules.can_sarf_card(clone, player_index, meld_index, card_id):
            return True
    return False


def discard_feeds_next_player_sarf(state: KonkanState, actor_index: int, card_id: int) -> bool:
    """Return True when discarding ``card_id`` feeds the next player's sarf."""

    if not state.players:
        return False
    next_index = _next_player_index(state, actor_index)
    return card_enables_sarf(state, next_index, card_id)
