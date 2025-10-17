from __future__ import annotations

import pytest

from konkan import encoding, rules, state


def make_sequence(sequence: list[int]) -> list[int]:
    return list(reversed(sequence))


def test_cannot_take_own_last_trash() -> None:
    config = state.KonkanConfig(num_players=1, hand_size=2, allow_trash_first_turn=True)
    card = encoding.encode_standard_card
    pop_sequence = [
        card(0, 0, 0),
        card(0, 1, 0),
        card(1, 0, 0),
        card(1, 1, 0),
    ]
    deck = make_sequence(pop_sequence)
    game_state = state.deal_new_game(config, deck)

    rules.draw_from_stock(game_state, 0)
    rules.trash_card(game_state, 0, pop_sequence[0])

    assert not rules.can_draw_from_trash(game_state, 0)
    with pytest.raises(rules.IllegalDraw):
        rules.draw_from_trash(game_state, 0)


def test_first_turn_trash_blocked_when_disabled() -> None:
    config = state.KonkanConfig(num_players=2, hand_size=1, allow_trash_first_turn=False)
    card = encoding.encode_standard_card
    pop_sequence = [card(0, 0, 0), card(1, 0, 0), card(2, 0, 0)]
    deck = make_sequence(pop_sequence)
    game_state = state.deal_new_game(config, deck)

    assert not rules.can_draw_from_trash(game_state, 1)
    with pytest.raises(rules.IllegalDraw):
        rules.draw_from_trash(game_state, 1)
