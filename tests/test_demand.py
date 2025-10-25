from __future__ import annotations

from konkan import encoding, rules, state
from konkan._compat import np
from konkan.demand import estimate_card_demand


def _three_player_state(hand_cards: list[int], opponent_cards: list[int], table_meld: list[int] | None = None) -> state.KonkanState:
    config = state.KonkanConfig(num_players=3, dealer_index=0, hand_size=len(hand_cards))
    public = state.PublicState(
        draw_pile=[],
        trash_pile=[],
        turn_index=12,
        dealer_index=0,
        current_player_index=0,
    )

    players = [
        state.PlayerState(hand_mask=encoding.mask_from_cards(hand_cards)),
        state.PlayerState(hand_mask=encoding.mask_from_cards(opponent_cards)),
        state.PlayerState(),
    ]
    players[1].phase = state.TurnPhase.AWAITING_DRAW

    game_state = state.KonkanState(
        player_to_act=0,
        turn_index=12,
        deck=np.zeros(0, dtype=np.uint16),
        deck_top=0,
        trash=[],
        hands=[],
        table=[],
        public=public,
        highest_table_points=0,
        first_player_has_discarded=True,
        phase=rules.TurnPhase.PLAY,
        config=config,
        players=players,
    )

    if table_meld:
        mask = encoding.mask_from_cards(table_meld)
        mask_hi, mask_lo = encoding.split_mask(mask)
        game_state.table.append(
            state.MeldOnTable(
                mask_hi=mask_hi,
                mask_lo=mask_lo,
                cards=list(table_meld),
                owner=1,
                kind=1,
                has_joker=False,
                points=encoding.points_from_mask(mask),
                is_four_set=False,
            )
        )
        players[1].has_come_down = True

    return game_state


def test_demand_estimate_detects_sarf_risk() -> None:
    ten_spade = encoding.encode_standard_card(0, 9, 0)
    table = [
        encoding.encode_standard_card(0, 6, 0),
        encoding.encode_standard_card(0, 7, 0),
        encoding.encode_standard_card(0, 8, 0),
    ]

    game_state = _three_player_state([ten_spade], [], table_meld=table)
    demand = estimate_card_demand(game_state, 0, ten_spade, samples=1)

    assert demand.sarf_risk >= 1.0


def test_demand_estimate_detects_come_down_risk() -> None:
    four_diamond = encoding.encode_standard_card(2, 3, 0)

    opponent_cards = [encoding.encode_standard_card(2, 1, 0), encoding.encode_standard_card(2, 2, 0)]
    game_state = _three_player_state([four_diamond], opponent_cards)
    game_state.config = state.KonkanConfig(num_players=3, come_down_points=6)

    demand = estimate_card_demand(game_state, 0, four_diamond, samples=4)

    assert demand.come_down_risk > 0.0
