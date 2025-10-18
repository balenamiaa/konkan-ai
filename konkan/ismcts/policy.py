"""Policy heuristics for initializing IS-MCTS priors."""

from __future__ import annotations

from typing import Sequence

from .. import encoding, melds
from ..state import KonkanState, PublicState


def _threshold_for(state: KonkanState, public: PublicState) -> int:
    threshold = 81
    if state.config is not None:
        threshold = state.config.come_down_points
    if public.highest_table_points > 0:
        threshold = max(threshold, public.highest_table_points + 1)
    return threshold


def _synergy_score(card_identifier: int, hand_cards: Sequence[int]) -> int:
    decoded = encoding.decode_id(card_identifier)
    if decoded.is_joker:
        return 4

    duplicates = 0
    run_neighbors = 0
    for other in hand_cards:
        if other == card_identifier:
            continue
        info = encoding.decode_id(other)
        if info.is_joker:
            continue
        if info.rank_idx == decoded.rank_idx:
            duplicates += 1
        if info.suit_idx == decoded.suit_idx and abs(info.rank_idx - decoded.rank_idx) == 1:
            run_neighbors += 1
    return duplicates + run_neighbors


def evaluate_actions(state: KonkanState, actions: Sequence[object]) -> list[float]:
    """Return heuristic priors that prefer safe, low-deadwood discards."""

    if not actions:
        return [1.0]

    public = state.public
    if not isinstance(public, PublicState):
        return [1.0 for _ in actions]

    player_index = public.current_player_index
    player = state.players[player_index]
    if not player.hand_mask:
        return [1.0 for _ in actions]

    threshold = _threshold_for(state, public)
    hand_cards = encoding.cards_from_mask(player.hand_mask)
    baseline_hi, baseline_lo = encoding.split_mask(player.hand_mask)
    baseline_cover = melds.best_cover_to_threshold(baseline_hi, baseline_lo, threshold)
    baseline_used_mask = 0
    for meld in baseline_cover.melds:
        mask = encoding.combine_mask(
            int(getattr(meld, "mask_hi", 0)), int(getattr(meld, "mask_lo", 0))
        )
        baseline_used_mask |= mask

    scores: list[float] = []
    for action in actions:
        if not isinstance(action, int):
            scores.append(1.0)
            continue

        try:
            mask_after = encoding.remove_card(player.hand_mask, action)
        except ValueError:
            scores.append(0.5)
            continue

        mask_hi, mask_lo = encoding.split_mask(mask_after)
        cover = melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)

        used_mask = 0
        for meld in cover.melds:
            mask = encoding.combine_mask(
                int(getattr(meld, "mask_hi", 0)), int(getattr(meld, "mask_lo", 0))
            )
            used_mask |= mask

        deadwood_mask = mask_after & ~used_mask
        deadwood_points = encoding.points_from_mask(deadwood_mask)

        card_points = float(encoding.card_points(action))
        synergy = float(_synergy_score(action, hand_cards))
        card_in_baseline = (baseline_used_mask >> action) & 1 == 1
        laydown_ready = cover.total_points >= threshold

        score = -float(deadwood_points)
        score -= 0.6 * card_points
        if card_in_baseline:
            score -= 25.0
        score += 4.0 * synergy
        if laydown_ready:
            score += 8.0
        if player.has_come_down:
            score += 3.0

        decoded = encoding.decode_id(action)
        if decoded.is_joker:
            score -= 40.0

        scores.append(score)

    minimum = min(scores)
    adjusted = [score - minimum + 1.0 for score in scores]
    total = sum(adjusted)
    if total <= 0:
        return [1.0 for _ in actions]
    return adjusted
