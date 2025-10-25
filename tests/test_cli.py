from __future__ import annotations

import random

from konkan.cli.main import _build_deck, _ensure_stock
from konkan import state, encoding


def _fresh_state_with_trash(trash_cards: list[int]) -> state.KonkanState:
    config = state.KonkanConfig(num_players=2, hand_size=3, come_down_points=81)
    public = state.PublicState(
        draw_pile=[encoding.encode_standard_card(0, 0, 0), encoding.encode_standard_card(1, 0, 0)],
        trash_pile=list(trash_cards),
        turn_index=2,
        dealer_index=0,
        current_player_index=0,
    )
    players = [state.PlayerState(), state.PlayerState()]
    return state.KonkanState(public=public, players=players)


def test_build_deck_produces_shuffled_order() -> None:
    deck_one = _build_deck()
    deck_two = _build_deck()

    assert len(deck_one) == 106
    assert len(deck_two) == 106
    assert set(deck_one) == set(range(106))
    assert set(deck_two) == set(range(106))


def test_ensure_stock_shuffles_trash_without_top_card() -> None:
    base = list(range(10, 20))
    top_card = encoding.encode_standard_card(0, 7, 0)
    trash_cards = base + [top_card]
    game_state = _fresh_state_with_trash(trash_cards)
    game_state.public.draw_pile = []

    rng = random.Random(1234)
    _ensure_stock(game_state, rng)

    public = game_state.public
    assert public.trash_pile[-1] == top_card
    assert set(public.draw_pile) == set(base)
