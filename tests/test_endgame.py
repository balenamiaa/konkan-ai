from __future__ import annotations

from konkan import encoding, rules, state


def test_come_down_threshold_and_laydown() -> None:
    config = state.KonkanConfig(num_players=1, come_down_points=15)
    player = state.PlayerState()
    public = state.PublicState(draw_pile=[], trash_pile=[encoding.encode_standard_card(0, 0, 0)], turn_index=0, dealer_index=0)
    game_state = state.KonkanState(config=config, players=[player], public=public)

    card = encoding.encode_standard_card
    player.hand_mask = encoding.mask_from_cards([
        card(0, 2, 0),  # 3 points
        card(0, 3, 0),  # 4 points
        card(0, 4, 0),  # 5 points -> total 12
    ])

    assert not rules.can_player_come_down(game_state, 0)

    player.hand_mask = encoding.add_card(player.hand_mask, card(0, 0, 0))  # Ace worth 10
    assert rules.can_player_come_down(game_state, 0)

    solution = rules.lay_down(game_state, 0)
    assert player.has_come_down
    assert player.hand_mask == solution.deadwood_mask == 0
    assert player.laid_mask == solution.used_mask
    assert not rules.can_player_come_down(game_state, 0)


def test_winner_declared_after_final_trash() -> None:
    config = state.KonkanConfig(num_players=2, hand_size=1)
    player0 = state.PlayerState()
    player1 = state.PlayerState()
    player0.hand_mask = encoding.add_card(0, encoding.encode_standard_card(0, 1, 0))
    player0.has_come_down = True
    player0.phase = state.TurnPhase.AWAITING_TRASH
    player1.phase = state.TurnPhase.COMPLETE

    public = state.PublicState(
        draw_pile=[],
        trash_pile=[encoding.encode_standard_card(0, 0, 0)],
        turn_index=0,
        dealer_index=1,
    )
    game_state = state.KonkanState(config=config, players=[player0, player1], public=public)

    card_id = encoding.encode_standard_card(0, 1, 0)
    rules.trash_card(game_state, 0, card_id)
    assert game_state.public.winner_index == 0
