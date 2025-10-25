from __future__ import annotations

from konkan import actions, encoding, state
from konkan.ismcts.opponents import OpponentModel


def test_opponent_prior_adjustment_penalises_high_points() -> None:
    model = OpponentModel()
    game_state = state.new_game_state(1)

    low_card = encoding.encode_standard_card(0, 2, 0)  # 3 points
    high_card = encoding.encode_standard_card(0, 11, 0)  # Queen worth 10

    low_action = actions.PlayAction(discard=low_card)
    high_action = actions.PlayAction(discard=high_card)

    low_adjust = model.prior_adjustment(game_state, low_action)
    high_adjust = model.prior_adjustment(game_state, high_action)

    assert low_adjust > high_adjust


def test_opponent_prior_adjustment_rewards_laydown_and_sarf() -> None:
    model = OpponentModel(laydown_bonus=0.2, sarf_bonus=0.15)
    game_state = state.new_game_state(1)
    base_card = encoding.encode_standard_card(0, 5, 0)

    base_action = actions.PlayAction(discard=base_card)
    laydown_action = actions.PlayAction(discard=base_card, lay_down=True)
    sarf_action = actions.PlayAction(discard=base_card, sarf_moves=((0, base_card),))

    assert model.prior_adjustment(game_state, laydown_action) > model.prior_adjustment(
        game_state, base_action
    )
    assert model.prior_adjustment(game_state, sarf_action) > model.prior_adjustment(
        game_state, base_action
    )
