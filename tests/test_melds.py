from __future__ import annotations

from typing import Iterable

import pytest

from konkan import encoding
from konkan.melds import (
    HAVE_NATIVE_SOLVER,
    best_cover_for_go_out,
    best_cover_to_threshold,
    enumerate_melds,
)

pytestmark = pytest.mark.skipif(not HAVE_NATIVE_SOLVER, reason="Rust meld solver not available")


def _cards_from_meld(mask_hi: int, mask_lo: int) -> set[int]:
    cards: set[int] = set()
    for cid in range(106):
        if cid < 64:
            if (mask_lo >> cid) & 1:
                cards.add(cid)
        else:
            bit = cid - 64
            if (mask_hi >> bit) & 1:
                cards.add(cid)
    return cards


def _mask_from_cards(cards: Iterable[int]) -> tuple[int, int]:
    mask = encoding.mask_from_cards(cards)
    return encoding.split_mask(mask)


def test_enumerate_melds_detects_runs_and_sets() -> None:
    # Run: hearts A-2-3, Set: three 7s, all in copy 0
    run_cards = [
        encoding.encode_standard_card(1, 0, 0),
        encoding.encode_standard_card(1, 1, 0),
        encoding.encode_standard_card(1, 2, 0),
    ]
    set_cards = [encoding.encode_standard_card(suit, 5, 0) for suit in (0, 1, 2)]
    mask_hi, mask_lo = _mask_from_cards(run_cards + set_cards)
    melds = enumerate_melds(mask_hi, mask_lo)
    meld_sets = [_cards_from_meld(m.mask_hi, m.mask_lo) for m in melds]

    assert set(run_cards) in meld_sets
    assert set(set_cards) in meld_sets


def test_best_cover_uses_joker_to_reach_threshold() -> None:
    # Two physical 7s plus a Joker should form a set worth 21 points
    spade_seven = encoding.encode_standard_card(0, 6, 0)
    heart_seven = encoding.encode_standard_card(1, 6, 0)
    joker = encoding.JOKER_IDS[0]
    mask_hi, mask_lo = _mask_from_cards([spade_seven, heart_seven, joker])

    cover = best_cover_to_threshold(mask_hi, mask_lo, threshold=21)
    assert cover.total_points >= 21
    assert cover.used_jokers == 1


def test_best_cover_for_go_out_covers_fourteen_cards() -> None:
    # Two 5-card runs plus a set of four distinct suits (total 14 cards)
    run_spades = [encoding.encode_standard_card(0, rank, 0) for rank in range(0, 5)]  # A-5
    run_hearts = [encoding.encode_standard_card(1, rank, 0) for rank in range(5, 10)]  # 6-10
    set_kings = [encoding.encode_standard_card(suit, 12, 0) for suit in range(4)]  # Kings
    mask_hi, mask_lo = _mask_from_cards(run_spades + run_hearts + set_kings)

    cover = best_cover_for_go_out(mask_hi, mask_lo)
    assert cover.covered_cards >= 14
    total_points = cover.total_points
    # 5-card straight twice (10+2+3+4+5 = 24 points each) + kings (10 each)
    expected_points = (10 + 2 + 3 + 4 + 5) + (6 + 7 + 8 + 9 + 10) + (10 * 4)
    assert total_points == expected_points
