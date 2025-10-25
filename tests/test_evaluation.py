from __future__ import annotations

from konkan import encoding, rules, state
from konkan._compat import np
from konkan.evaluation import analyze_hand


def _state_with_hand(hand_cards: list[int]) -> state.KonkanState:
    config = state.KonkanConfig(num_players=1, dealer_index=0, hand_size=len(hand_cards))
    public = state.PublicState(
        draw_pile=[],
        trash_pile=[],
        turn_index=1,
        dealer_index=0,
        current_player_index=0,
    )
    player = state.PlayerState(hand_mask=encoding.mask_from_cards(hand_cards))
    player.phase = state.TurnPhase.AWAITING_TRASH
    return state.KonkanState(
        player_to_act=0,
        turn_index=1,
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
        players=[player],
    )


def test_analyze_hand_rewards_consecutive_suit_links() -> None:
    five_club_a = encoding.encode_standard_card(0, 4, 0)
    five_club_b = encoding.encode_standard_card(0, 4, 1)
    six_club = encoding.encode_standard_card(0, 5, 0)
    queen_diamond = encoding.encode_standard_card(2, 10, 0)

    game_state = _state_with_hand([five_club_a, five_club_b, six_club, queen_diamond])

    metrics = analyze_hand(game_state, 0, demand_samples=4)

    assert metrics[six_club].keep_value() > metrics[queen_diamond].keep_value()


def test_keep_value_penalises_high_cards_late() -> None:
    high_card = encoding.encode_standard_card(2, 10, 0)
    low_card = encoding.encode_standard_card(0, 2, 0)

    early_state = _state_with_hand([high_card, low_card])
    late_state = _state_with_hand([high_card, low_card])
    late_state.public.turn_index = 40
    late_state.public.trash_pile = list(range(10))

    early_metrics = analyze_hand(early_state, 0)
    late_metrics = analyze_hand(late_state, 0)

    assert late_metrics[high_card].keep_value() < early_metrics[high_card].keep_value()
    assert late_metrics[high_card].keep_value() < late_metrics[low_card].keep_value()


def test_metrics_capture_opponent_sarf_demand() -> None:
    seven_spade = encoding.encode_standard_card(0, 6, 0)
    eight_spade = encoding.encode_standard_card(0, 7, 0)
    nine_spade = encoding.encode_standard_card(0, 8, 0)
    ten_spade = encoding.encode_standard_card(0, 9, 0)

    config = state.KonkanConfig(num_players=2, dealer_index=0, hand_size=2, come_down_points=81)
    public = state.PublicState(
        draw_pile=[],
        trash_pile=[],
        turn_index=12,
        dealer_index=0,
        current_player_index=0,
    )
    player0 = state.PlayerState(hand_mask=encoding.mask_from_cards([ten_spade, encoding.encode_standard_card(1, 3, 0)]))
    player0.phase = state.TurnPhase.AWAITING_TRASH
    player1 = state.PlayerState()
    player1.has_come_down = True
    player1.phase = state.TurnPhase.AWAITING_DRAW

    meld_mask = encoding.mask_from_cards([seven_spade, eight_spade, nine_spade])
    mask_hi, mask_lo = encoding.split_mask(meld_mask)
    points = encoding.points_from_mask(meld_mask)
    meld = state.MeldOnTable(
        mask_hi=mask_hi,
        mask_lo=mask_lo,
        cards=[seven_spade, eight_spade, nine_spade],
        owner=1,
        kind=1,
        has_joker=False,
        points=points,
        is_four_set=False,
    )

    game_state = state.KonkanState(
        player_to_act=0,
        turn_index=12,
        deck=np.zeros(0, dtype=np.uint16),
        deck_top=0,
        trash=[],
        hands=[],
        table=[meld],
        public=public,
        highest_table_points=points,
        first_player_has_discarded=True,
        phase=rules.TurnPhase.PLAY,
        config=config,
        players=[player0, player1],
    )

    metrics = analyze_hand(game_state, 0, demand_samples=4)
    demand = metrics[ten_spade].opponent_demand

    assert demand.sarf_risk > 0.5


def test_metrics_capture_come_down_risk() -> None:
    card_to_test = encoding.encode_standard_card(2, 4, 0)
    helper_card = encoding.encode_standard_card(1, 9, 0)

    config = state.KonkanConfig(num_players=2, dealer_index=0, hand_size=2, come_down_points=10)
    public = state.PublicState(
        draw_pile=[],
        trash_pile=[],
        turn_index=6,
        dealer_index=0,
        current_player_index=0,
    )
    player0 = state.PlayerState(hand_mask=encoding.mask_from_cards([card_to_test, helper_card]))
    player0.phase = state.TurnPhase.AWAITING_TRASH
    player1 = state.PlayerState(hand_mask=encoding.mask_from_cards([encoding.encode_standard_card(2, 2, 0), encoding.encode_standard_card(2, 3, 0)]))
    player1.phase = state.TurnPhase.AWAITING_DRAW

    game_state = state.KonkanState(
        player_to_act=0,
        turn_index=6,
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
        players=[player0, player1],
    )

    metrics = analyze_hand(game_state, 0)
    demand = metrics[card_to_test].opponent_demand

    assert demand.come_down_risk > 0.0
