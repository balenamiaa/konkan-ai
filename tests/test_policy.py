from __future__ import annotations

from konkan import actions, encoding, rules, state
from konkan._compat import np
from konkan.ismcts import policy


def test_policy_prefers_discarding_deadwood() -> None:
    config = state.KonkanConfig(num_players=1, hand_size=4, come_down_points=0)
    public = state.PublicState(
        draw_pile=[],
        trash_pile=[],
        turn_index=0,
        dealer_index=0,
        current_player_index=0,
    )

    run_cards = [
        encoding.encode_standard_card(0, 0, 0),
        encoding.encode_standard_card(0, 1, 0),
        encoding.encode_standard_card(0, 2, 0),
    ]
    deadwood_card = encoding.encode_standard_card(1, 9, 0)

    player = state.PlayerState(
        hand_mask=encoding.mask_from_cards(run_cards + [deadwood_card]),
        phase=state.TurnPhase.AWAITING_TRASH,
    )

    game_state = state.KonkanState(
        player_to_act=0,
        turn_index=0,
        deck=np.zeros(0, dtype=np.uint16),
        deck_top=0,
        trash=[],
        hands=[],
        table=[],
        public=public,
        highest_table_points=0,
        first_player_has_discarded=False,
        phase=rules.TurnPhase.PLAY,
        config=config,
        players=[player],
    )

    deadwood_action = actions.PlayAction(discard=deadwood_card)
    keeper_action = actions.PlayAction(discard=run_cards[0])

    priors = policy.evaluate_actions(game_state, [deadwood_action, keeper_action])
    assert priors[0] > priors[1]
