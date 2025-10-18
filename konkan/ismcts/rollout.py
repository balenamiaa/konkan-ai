"""Rollout policies for IS-MCTS simulations."""

from __future__ import annotations

import numpy as np
from numba import njit

from .. import encoding, melds
from ..state import KonkanState, PublicState

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

    player = state.players[player_index]
    hand_cards_list = encoding.cards_from_mask(player.hand_mask)
    if not hand_cards_list:
        return 0.0

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

    return score / 100.0
