<<<<<<< HEAD
"""Tests covering Konkan rule helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from konkan import rules
from konkan._compat import np
from konkan.state import PlayerPublic, hand_mask, new_game_state


@dataclass(slots=True)
class DummyCover:
    total_points: int
    melds: list[object] = field(default_factory=list)
    covered_cards: int = 0
    used_jokers: int = 0


@pytest.mark.parametrize(
    ("player_index", "expected"),
    [
        (0, 15),
        (1, 14),
        (5, 14),
    ],
)
def test_deal_pattern_hand_size(player_index: int, expected: int) -> None:
    assert rules.DEFAULT_DEAL_PATTERN.hand_size_for(player_index) == expected


@pytest.mark.parametrize(
    ("highest_table_points", "expected"),
    [
        (0, 81),
        (81, 82),
        (150, 151),
    ],
)
def test_thresholds_next_value(highest_table_points: int, expected: int) -> None:
    assert rules.DEFAULT_THRESHOLDS.next_for(highest_table_points) == expected


def test_effective_threshold_tracks_table_state() -> None:
    public = [PlayerPublic(False, 0) for _ in range(3)]
    assert rules.effective_threshold(public, highest_table_points=0) == 81

    public[1].came_down = True
    assert rules.effective_threshold(public, highest_table_points=100) == 101


def test_can_draw_from_trash_requires_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    hand = np.array([0, 1, 2], dtype=np.uint16)
    mask = hand_mask(hand)
    public = [PlayerPublic(False, 0) for _ in range(3)]
    top_card = 10
    trash = [top_card]

    def fake_cover(mask_hi: int, mask_lo: int, threshold: int) -> DummyCover:
        return DummyCover(total_points=threshold - 1)

    assert not rules.can_draw_from_trash(
        trash=trash,
        hand_mask=mask,
        player_public=public[0],
        public_state=public,
        highest_table_points=0,
        cover_to_threshold=fake_cover,
    )

    def successful_cover(mask_hi: int, mask_lo: int, threshold: int) -> DummyCover:
        return DummyCover(total_points=threshold)

    assert rules.can_draw_from_trash(
        trash=trash,
        hand_mask=mask,
        player_public=public[0],
        public_state=public,
        highest_table_points=0,
        cover_to_threshold=successful_cover,
    )


def test_can_draw_from_trash_always_true_after_coming_down() -> None:
    public = [PlayerPublic(False, 0) for _ in range(3)]
    public[0].came_down = True
    mask = hand_mask(np.array([], dtype=np.uint16))
    assert rules.can_draw_from_trash(
        trash=[1],
        hand_mask=mask,
        player_public=public[0],
        public_state=public,
        highest_table_points=90,
    )


def test_requires_opening_discard_flag() -> None:
    state = new_game_state(3)
    state.phase = rules.TurnPhase.DISCARD
    assert rules.requires_opening_discard(state)
    state.register_discard(0)
    assert not rules.requires_opening_discard(state)


@pytest.mark.parametrize(
    ("hand_card_count", "came_down", "expected"),
    [
        (3, True, False),
        (2, True, True),
        (1, True, True),
        (2, False, False),
    ],
)
def test_can_finish_via_sarf(hand_card_count: int, came_down: bool, expected: bool) -> None:
    public = PlayerPublic(came_down=came_down, table_points=0)
    assert rules.can_finish_via_sarf(hand_card_count, public) is expected
=======
from __future__ import annotations

import random

from konkan import encoding, rules, state


def make_sequence(sequence: list[int]) -> list[int]:
    """Produce a deck whose pop order matches ``sequence``."""
    return list(reversed(sequence))


def test_stock_draw_and_trash_advances_turn() -> None:
    config = state.KonkanConfig(num_players=2, hand_size=3, come_down_points=10, allow_trash_first_turn=True)
    card = encoding.encode_standard_card
    pop_sequence = [
        card(0, 0, 0),
        card(1, 0, 0),
        card(0, 1, 0),
        card(1, 1, 0),
        card(0, 2, 0),
        card(1, 2, 0),
        card(2, 0, 0),
        card(2, 1, 0),
        card(3, 0, 0),
    ]
    deck = make_sequence(pop_sequence)
    game_state = state.deal_new_game(config, deck)

    assert game_state.public.turn_index == 1

    draw = rules.draw_from_stock(game_state, 1)
    assert not draw.from_trash
    assert draw.card_id == pop_sequence[7]

    player = game_state.players[1]
    assert encoding.popcount(player.hand_mask) == 4

    rules.trash_card(game_state, 1, pop_sequence[1])
    assert game_state.public.turn_index == 0
    assert game_state.public.trash_pile[-1] == pop_sequence[1]
    assert player.last_trash == pop_sequence[1]
    assert game_state.players[0].phase is state.TurnPhase.AWAITING_DRAW
    assert player.phase is state.TurnPhase.COMPLETE


def test_recycle_draw_pile_when_empty() -> None:
    config = state.KonkanConfig(num_players=2, hand_size=1, allow_trash_first_turn=True, recycle_shuffle_seed=2)
    card = encoding.encode_standard_card
    pop_sequence = [
        card(0, 0, 0),
        card(1, 0, 0),
        card(2, 0, 0),
        card(3, 0, 0),
    ]
    deck = make_sequence(pop_sequence)
    game_state = state.deal_new_game(config, deck)

    # draw pile currently empty; seed two extra trash cards so recycle triggers
    extras = [encoding.encode_standard_card(0, 1, 0), encoding.encode_standard_card(0, 2, 0)]
    game_state.public.trash_pile.extend(extras)
    game_state.public.draw_pile.clear()
    game_state.public.turn_index = 1
    game_state.players[1].phase = state.TurnPhase.AWAITING_DRAW

    draw = rules.draw_from_stock(game_state, 1, random.Random(5))
    assert draw.card_id in extras
    assert encoding.has_card(game_state.players[1].hand_mask, draw.card_id)
    assert game_state.public.pending_recycle
    assert len(game_state.public.trash_pile) == 1
    assert len(game_state.public.draw_pile) == 1  # one card recycled back
>>>>>>> main
