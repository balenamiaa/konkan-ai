"""Opponent demand estimation utilities for discard heuristics."""

from __future__ import annotations

import random
from dataclasses import dataclass

from . import encoding, melds
from .determinize import sample_world
from .state import KonkanState, PublicState
from .threats import card_enables_sarf


@dataclass(slots=True)
class DemandEstimate:
    """Aggregated demand signals for a prospective discard."""

    sarf_risk: float
    come_down_risk: float
    exposure_pressure: float

    def total(self) -> float:
        return self.sarf_risk + self.come_down_risk + self.exposure_pressure


def _threshold_for_opponent(state: KonkanState, public: PublicState) -> int:
    threshold = 81
    if state.config is not None:
        threshold = state.config.come_down_points
    if public.highest_table_points > 0:
        threshold = max(threshold, public.highest_table_points + 1)
    return threshold


def _coming_down_probability(
    state: KonkanState,
    opponent_index: int,
    card_id: int,
    *,
    samples: int,
) -> float:
    public = state.public
    if not isinstance(public, PublicState):
        return 0.0

    threshold = _threshold_for_opponent(state, public)
    base_seed = (public.turn_index << 24) ^ (opponent_index << 12) ^ (card_id << 3)
    hits = 0
    total = 0

    for offset in range(samples):
        rng = random.Random(base_seed + offset)
        world = sample_world(state, rng, actor_index=opponent_index)
        opponent = world.players[opponent_index]
        opponent.hand_mask = encoding.add_card(opponent.hand_mask, card_id)
        mask_hi, mask_lo = encoding.split_mask(opponent.hand_mask)
        cover = melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)
        if cover.total_points >= threshold:
            hits += 1
        total += 1

    if total == 0:
        return 0.0
    return hits / total


def estimate_card_demand(
    state: KonkanState,
    actor_index: int,
    card_id: int,
    *,
    samples: int = 3,
) -> DemandEstimate:
    """Return opponents' demand pressure for ``card_id`` discarded by ``actor_index``."""

    public = state.public
    if not isinstance(public, PublicState):
        return DemandEstimate(0.0, 0.0, 0.0)

    sarf_risk = 0.0
    come_down_risk = 0.0

    players = state.players
    progress_denominator = max(8, len(public.draw_pile) + public.turn_index + len(public.trash_pile))
    progress = min(1.0, public.turn_index / progress_denominator)

    for opponent_index, opponent in enumerate(players):
        if opponent_index == actor_index:
            continue

        if opponent.has_come_down:
            if card_enables_sarf(state, opponent_index, card_id):
                sarf_risk += 1.0
            continue

        probability = _coming_down_probability(state, opponent_index, card_id, samples=samples)
        come_down_risk += probability

    card_points = encoding.card_points(card_id)
    exposure_pressure = progress * (card_points / 10.0)

    return DemandEstimate(sarf_risk=sarf_risk, come_down_risk=come_down_risk, exposure_pressure=exposure_pressure)
