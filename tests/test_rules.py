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
