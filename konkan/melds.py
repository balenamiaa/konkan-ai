"""Placeholder meld solver used by the Python prototype."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from . import encoding


@dataclass(frozen=True)
class MeldSolution:
    used_mask: encoding.Mask
    deadwood_mask: encoding.Mask
    melds: Sequence[Sequence[encoding.CardId]]
    points: int


def evaluate_simple(hand_mask: encoding.Mask) -> MeldSolution:
    """Naïve scorer that assumes every card can be melded independently."""
    melds: List[Sequence[int]] = [[card_id] for card_id in encoding.iter_cards(hand_mask)]
    return MeldSolution(used_mask=hand_mask, deadwood_mask=encoding.empty_mask(), melds=melds, points=encoding.points_for_mask(hand_mask))


def solve_for_laydown(hand_mask: encoding.Mask) -> MeldSolution:
    """Entry point invoked by the rules engine.

    The future Rust solver will replace this heuristic. For now, treat every card
    as an independent meld so that come-down checks can reason about point totals.
    """

    return evaluate_simple(hand_mask)
