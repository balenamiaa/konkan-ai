from __future__ import annotations

from konkan import encoding, rules, state
from konkan._compat import np
from konkan.ismcts import rollout


def _base_state_for_rollout(hand_cards: list[int], *, trash: list[int], draw_pile: list[int], come_down_points: int = 15) -> state.KonkanState:
    config = state.KonkanConfig(num_players=2, dealer_index=0, hand_size=len(hand_cards), come_down_points=come_down_points)
    public = state.PublicState(
        draw_pile=list(draw_pile),
        trash_pile=list(trash),
        turn_index=5,
        dealer_index=0,
        current_player_index=0,
    )
    public.last_trash_by = 1

    player0 = state.PlayerState(hand_mask=encoding.mask_from_cards(hand_cards))
    player0.phase = state.TurnPhase.AWAITING_DRAW
    player1 = state.PlayerState()

    return state.KonkanState(
        player_to_act=0,
        turn_index=5,
        deck=np.array(draw_pile, dtype=np.uint16),
        deck_top=0,
        trash=list(trash),
        hands=[],
        table=[],
        public=public,
        highest_table_points=0,
        first_player_has_discarded=True,
        phase=rules.TurnPhase.PLAY,
        config=config,
        players=[player0, player1],
    )


def test_rollout_turn_draws_trash_to_complete_run() -> None:
    four_club = encoding.encode_standard_card(0, 3, 0)
    five_club = encoding.encode_standard_card(0, 4, 0)
    six_club = encoding.encode_standard_card(0, 5, 0)
    queen_diamond = encoding.encode_standard_card(2, 10, 0)

    game_state = _base_state_for_rollout(
        [five_club, six_club, queen_diamond],
        trash=[four_club],
        draw_pile=[encoding.encode_standard_card(1, 9, 0)],
        come_down_points=15,
    )

    clone = game_state.clone_shallow()
    rollout._simulate_turn(clone, 0)

    assert clone.players[0].has_come_down
    assert clone.public.trash_pile and clone.public.trash_pile[-1] == queen_diamond


def test_simulate_seed_turns_advances_value_when_trash_card_is_strong() -> None:
    four_club = encoding.encode_standard_card(0, 3, 0)
    five_club = encoding.encode_standard_card(0, 4, 0)
    six_club = encoding.encode_standard_card(0, 5, 0)
    queen_diamond = encoding.encode_standard_card(2, 10, 0)

    game_state = _base_state_for_rollout(
        [five_club, six_club, queen_diamond],
        trash=[four_club],
        draw_pile=[encoding.encode_standard_card(1, 9, 0)],
        come_down_points=15,
    )

    baseline = rollout._evaluate_state(game_state, 0)
    simulated = rollout.simulate(game_state, 0)

    assert simulated > baseline


def test_rollout_cascades_into_second_turn() -> None:
    low_card = encoding.encode_standard_card(1, 2, 0)
    high_card = encoding.encode_standard_card(3, 12, 0)
    trash_card = encoding.encode_standard_card(2, 6, 0)

    game_state = _base_state_for_rollout(
        [low_card, high_card],
        trash=[trash_card],
        draw_pile=[encoding.encode_standard_card(0, 3, 0), encoding.encode_standard_card(1, 4, 0)],
        come_down_points=40,
    )

    baseline = rollout._evaluate_state(game_state, 0)
    value_with_rollout = rollout.simulate(game_state, 0)

    assert abs(value_with_rollout - baseline) > 1e-6
