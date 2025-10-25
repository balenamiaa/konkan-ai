"""Hand evaluation helpers for heuristic-guided search."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable

from . import encoding, melds
from .demand import DemandEstimate, estimate_card_demand


@dataclass(slots=True)
class CardMetrics:
    """High-level structural signals for a single card in a hand."""

    card_id: int
    points: int
    in_baseline_cover: bool
    cover_points_drop: int
    cover_cards_drop: int
    set_potential: int
    run_left: int
    run_right: int
    run_span: int
    needs_for_run: int
    gap_bridge: bool
    near_run: bool
    duplicates_same_suit: int
    exposure_penalty: float
    opponent_demand: DemandEstimate

    def keep_value(self) -> float:
        """Return a scalar that grows with the desire to keep the card."""

        value = 0.0
        if self.in_baseline_cover:
            value += 12.0
        value += self.cover_points_drop * 1.2
        value += self.cover_cards_drop * 2.5
        value += max(0, self.set_potential - 2) * 2.0
        value += (self.run_left + self.run_right) * 2.5
        if self.near_run:
            value += 3.5
        if self.gap_bridge:
            value += 4.5
        if self.needs_for_run == 1:
            value += 1.5
        if self.duplicates_same_suit > 0:
            value -= 1.0 * self.duplicates_same_suit
        value -= self.exposure_penalty * 1.2
        value -= self.opponent_demand.total() * 3.5
        return value


def _count_consecutive(ranks: set[int], start: int, step: int) -> int:
    count = 0
    current = start + step
    while 0 <= current < len(encoding.RANKS) and current in ranks:
        count += 1
        current += step
    return count


def _count_same_suit_duplicates(cards: Iterable[int], suit_idx: int, rank_idx: int) -> int:
    duplicates = 0
    for card_id in cards:
        decoded = encoding.decode_id(card_id)
        if decoded.is_joker:
            continue
        if decoded.suit_idx == suit_idx and decoded.rank_idx == rank_idx:
            duplicates += 1
    return max(0, duplicates - 1)


@lru_cache(maxsize=256)
def _best_cover(mask_hi: int, mask_lo: int, threshold: int) -> melds.CoverResultProtocol:
    return melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)


def analyze_hand(
    state,
    player_index: int,
    threshold: int | None = None,
    *,
    demand_samples: int = 1,
) -> Dict[int, CardMetrics]:
    """Return structural metrics for each card in ``player_index``'s hand."""

    player = state.players[player_index]
    hand_mask = player.hand_mask
    hand_cards = encoding.cards_from_mask(hand_mask)
    if threshold is None:
        threshold = 81
        if state.config is not None:
            threshold = state.config.come_down_points
    public = state.public
    if getattr(public, "highest_table_points", 0) > 0:
        threshold = max(threshold, public.highest_table_points + 1)

    mask_hi, mask_lo = encoding.split_mask(hand_mask)
    baseline_cover = _best_cover(mask_hi, mask_lo, threshold)
    baseline_points = baseline_cover.total_points
    baseline_used_mask = 0
    for meld in getattr(baseline_cover, "melds", []):
        mask = encoding.combine_mask(int(getattr(meld, "mask_hi", 0)), int(getattr(meld, "mask_lo", 0)))
        baseline_used_mask |= mask

    joker_count = sum(1 for card_id in hand_cards if encoding.decode_id(card_id).is_joker)

    progress_denominator = max(8, len(public.draw_pile) + public.turn_index + len(public.trash_pile))
    progress = min(1.0, public.turn_index / progress_denominator)
    opponents_down = any(
        idx != player_index and getattr(player, "has_come_down", False)
        for idx, player in enumerate(state.players)
    )

    rank_to_suits: dict[int, set[int]] = {}
    suit_to_ranks: dict[int, set[int]] = {}
    for card_id in hand_cards:
        decoded = encoding.decode_id(card_id)
        if decoded.is_joker:
            continue
        rank_to_suits.setdefault(decoded.rank_idx, set()).add(decoded.suit_idx)
        suit_to_ranks.setdefault(decoded.suit_idx, set()).add(decoded.rank_idx)

    metrics: Dict[int, CardMetrics] = {}
    for card_id in hand_cards:
        decoded = encoding.decode_id(card_id)
        points = encoding.card_points(card_id)
        in_baseline = (baseline_used_mask >> card_id) & 1 == 1

        mask_without = encoding.remove_card(hand_mask, card_id, ignore_missing=True)
        mask_hi_without, mask_lo_without = encoding.split_mask(mask_without)
        cover_without = _best_cover(mask_hi_without, mask_lo_without, threshold)
        cover_points_drop = max(0, baseline_points - cover_without.total_points)
        cover_cards_drop = max(0, getattr(baseline_cover, "covered_cards", 0) - getattr(cover_without, "covered_cards", 0))

        set_potential = 1
        duplicates_same_suit = 0
        run_left = 0
        run_right = 0
        gap_bridge = False
        near_run = False

        if not decoded.is_joker:
            suits_for_rank = rank_to_suits.get(decoded.rank_idx, set())
            set_potential = len(suits_for_rank) + joker_count
            duplicates_same_suit = _count_same_suit_duplicates(hand_cards, decoded.suit_idx, decoded.rank_idx)

            ranks_for_suit = suit_to_ranks.get(decoded.suit_idx, set())
            run_left = _count_consecutive(ranks_for_suit, decoded.rank_idx, -1)
            run_right = _count_consecutive(ranks_for_suit, decoded.rank_idx, 1)
            near_run = run_left > 0 or run_right > 0
            gap_bridge = run_left > 0 and run_right > 0
        else:
            set_potential = joker_count
            near_run = True

        run_span = run_left + run_right + 1
        needs_for_run = max(0, 3 - run_span)

        exposure_factor = 0.5 if near_run or in_baseline else 1.0
        exposure_penalty = points * progress * exposure_factor
        should_sample_demand = (
            opponents_down
            or progress > 0.35
            or getattr(public, "highest_table_points", 0) > 0
        )
        if should_sample_demand:
            demand_estimate = estimate_card_demand(
                state,
                player_index,
                card_id,
                samples=max(1, demand_samples),
            )
        else:
            demand_estimate = DemandEstimate(sarf_risk=0.0, come_down_risk=0.0, exposure_pressure=0.0)

        metrics[card_id] = CardMetrics(
            card_id=card_id,
            points=points,
            in_baseline_cover=in_baseline,
            cover_points_drop=cover_points_drop,
            cover_cards_drop=cover_cards_drop,
            set_potential=set_potential,
            run_left=run_left,
            run_right=run_right,
            run_span=run_span,
            needs_for_run=needs_for_run,
            gap_bridge=gap_bridge,
            near_run=near_run,
            duplicates_same_suit=duplicates_same_suit,
            exposure_penalty=exposure_penalty,
            opponent_demand=demand_estimate,
        )

    return metrics
