"""Rollout policies for IS-MCTS simulations."""

from __future__ import annotations

import numpy as np
from numba import njit

from .. import actions, encoding
from ..evaluation import analyze_hand
from ..ismcts import policy
from ..state import KonkanState, PublicState, TurnPhase
from ..threats import card_enables_sarf
from .. import melds

_NUM_RANKS = len(encoding.RANKS)
_RANK_POINTS = np.array(encoding.POINTS, dtype=np.int16)
_CARD_RANKS = np.empty(encoding.DECK_CARD_COUNT, dtype=np.int8)
_CARD_SUITS = np.empty(encoding.DECK_CARD_COUNT, dtype=np.int8)
for card_id in range(encoding.DECK_CARD_COUNT):
    decoded = encoding.decode_id(card_id)
    _CARD_RANKS[card_id] = decoded.rank_idx
    _CARD_SUITS[card_id] = decoded.suit_idx


@njit(cache=True)
def _deadwood_points(
    hand_cards: np.ndarray,
    mask_hi: np.uint64,
    mask_lo: np.uint64,
    rank_points: np.ndarray,
    card_ranks: np.ndarray,
) -> int:
    total = 0
    for cid in hand_cards:
        if cid < 64:
            bit = np.uint64(1) << np.uint64(cid)
            if (mask_lo & bit) == 0:
                rank = card_ranks[cid]
                if rank >= 0:
                    total += int(rank_points[rank])
        else:
            bit = np.uint64(1) << np.uint64(cid - 64)
            if (mask_hi & bit) == 0:
                rank = card_ranks[cid]
                if rank >= 0:
                    total += int(rank_points[rank])
    return total


@njit(cache=True)
def _count_extenders(hand_cards: np.ndarray, card_ranks: np.ndarray, card_suits: np.ndarray) -> int:
    total = 0
    size = hand_cards.size
    for i in range(size):
        cid = hand_cards[i]
        rank = card_ranks[cid]
        suit = card_suits[cid]
        if rank < 0:
            continue
        duplicate = 0
        run_neighbor = 0
        for j in range(size):
            if i == j:
                continue
            other = hand_cards[j]
            other_rank = card_ranks[other]
            if other_rank == rank:
                duplicate = 1
            if (
                suit >= 0
                and card_suits[other] == suit
                and (other_rank == rank - 1 or other_rank == rank + 1)
            ):
                run_neighbor = 1
            if duplicate and run_neighbor:
                break
        total += duplicate + run_neighbor
    return total


def simulate(state: KonkanState, player_index: int) -> float:
    """Return a scalar reward estimate for ``player_index``."""

    public = state.public
    if not isinstance(public, PublicState):  # pragma: no cover - defensive guard
        return 0.0

    if public.winner_index is not None:
        if public.winner_index == player_index:
            return 1.0
        return -1.0

    if public.trash_pile:
        top_card = public.trash_pile[-1]
        actor_index = public.current_player_index
        if card_enables_sarf(state, actor_index, top_card):
            return 0.85 if actor_index == player_index else -0.85

    rollout_state = state.clone_shallow()
    start_turn = rollout_state.public.turn_index
    turns_advanced = 0
    max_turns = max(1, len(rollout_state.players)) * _ROLLOUT_TURNS
    for _ in range(max_turns * 2):
        if rollout_state.public.winner_index is not None:
            break
        current_player = rollout_state.public.current_player_index
        previous_turn = rollout_state.public.turn_index
        _simulate_turn(rollout_state, current_player)
        if rollout_state.public.turn_index == previous_turn:
            # Defensive guard against no-progress situations.
            break
        if rollout_state.public.turn_index != previous_turn:
            turns_advanced += 1
        if turns_advanced >= max_turns:
            break
        if rollout_state.public.turn_index >= start_turn + max_turns:
            break

    return _evaluate_state(rollout_state, player_index)
_ROLLOUT_TURNS = 1


def _static_heuristic_value(state: KonkanState, player_index: int, threshold: int | None = None) -> float:
    public = state.public
    if not isinstance(public, PublicState):  # pragma: no cover - defensive guard
        return 0.0

    player = state.players[player_index]
    hand_cards_list = encoding.cards_from_mask(player.hand_mask)
    if not hand_cards_list:
        return 0.0

    if threshold is None:
        threshold = 81
        if state.config is not None:
            threshold = state.config.come_down_points
    if public.highest_table_points > 0:
        threshold = max(threshold, public.highest_table_points + 1)

    mask_hi, mask_lo = encoding.split_mask(player.hand_mask)
    cover = melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)

    used_hi = np.uint64(0)
    used_lo = np.uint64(0)
    for meld in cover.melds:
        used_hi |= np.uint64(getattr(meld, "mask_hi", 0))
        used_lo |= np.uint64(getattr(meld, "mask_lo", 0))

    hand_array = np.array(hand_cards_list, dtype=np.int16)

    deadwood = _deadwood_points(hand_array, used_hi, used_lo, _RANK_POINTS, _CARD_RANKS)
    extenders = _count_extenders(hand_array, _CARD_RANKS, _CARD_SUITS)

    score = -float(deadwood)
    score += 0.35 * float(extenders)
    if player.has_come_down:
        score += 5.0
    score -= float(hand_array.size)

    metrics = analyze_hand(state, player_index, threshold, demand_samples=1)
    if metrics:
        avg_keep = sum(metric.keep_value() for metric in metrics.values()) / float(len(metrics))
        score += 3.0 * avg_keep

    return score


def _evaluate_state(state: KonkanState, player_index: int, threshold: int | None = None) -> float:
    public = state.public
    if not isinstance(public, PublicState):  # pragma: no cover - defensive guard
        return 0.0
    if public.winner_index is not None:
        return 1.0 if public.winner_index == player_index else -1.0
    return _static_heuristic_value(state, player_index, threshold) / 100.0


def _apply_best_draw_action(state: KonkanState, player_index: int) -> None:
    draw_actions = actions.legal_draw_actions(state, player_index)
    if not draw_actions:
        return

    if len(draw_actions) == 1:
        actions.apply_draw_action(state, player_index, draw_actions[0])
        return

    best_score = -1e9
    best_action = draw_actions[0]
    for action in draw_actions:
        clone = state.clone_shallow()
        actions.apply_draw_action(clone, player_index, action)
        value = _evaluate_state(clone, player_index)
        if value > best_score:
            best_score = value
            best_action = action

    actions.apply_draw_action(state, player_index, best_action)


def _apply_best_play_action(state: KonkanState, player_index: int) -> None:
    play_actions = actions.legal_play_actions(state, player_index)
    if not play_actions:
        return

    scores = policy.evaluate_actions(state, play_actions, demand_samples=1)
    if not scores:
        actions.apply_play_action(state, player_index, play_actions[0])
        return

    best_idx = 0
    best_score = scores[0]
    for idx, score in enumerate(scores[1:], start=1):
        if score > best_score:
            best_idx = idx
            best_score = score

    actions.apply_play_action(state, player_index, play_actions[best_idx])


def _simulate_turn(state: KonkanState, player_index: int) -> None:
    player = state.players[player_index]

    if player.phase == TurnPhase.AWAITING_DRAW:
        _apply_best_draw_action(state, player_index)

    if state.public.current_player_index != player_index:
        return

    player = state.players[player_index]
    if player.phase == TurnPhase.AWAITING_TRASH:
        _apply_best_play_action(state, player_index)
