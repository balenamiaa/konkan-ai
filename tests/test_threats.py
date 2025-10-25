from __future__ import annotations

from konkan import encoding, rules, state
from konkan._compat import np
from konkan.threats import card_enables_sarf, discard_feeds_next_player_sarf


def _state_with_table(meld_cards: list[int]) -> state.KonkanState:
    config = state.KonkanConfig(num_players=3, hand_size=3)
    public = state.PublicState(
        draw_pile=[],
        trash_pile=[],
        turn_index=10,
        dealer_index=0,
        current_player_index=0,
    )
    players = [state.PlayerState(), state.PlayerState(), state.PlayerState()]
    players[1].has_come_down = True
    players[1].phase = state.TurnPhase.AWAITING_TRASH
    players[0].phase = state.TurnPhase.AWAITING_TRASH

    mask = encoding.mask_from_cards(meld_cards)
    mask_hi, mask_lo = encoding.split_mask(mask)
    table_meld = state.MeldOnTable(
        mask_hi=mask_hi,
        mask_lo=mask_lo,
        cards=list(meld_cards),
        owner=1,
        kind=1,
        has_joker=False,
        points=encoding.points_from_mask(mask),
        is_four_set=False,
    )

    return state.KonkanState(
        player_to_act=0,
        turn_index=10,
        deck=np.zeros(0, dtype=np.uint16),
        deck_top=0,
        trash=[],
        hands=[],
        table=[table_meld],
        public=public,
        highest_table_points=encoding.points_from_mask(mask),
        first_player_has_discarded=True,
        phase=rules.TurnPhase.PLAY,
        config=config,
        players=players,
    )


def test_card_enables_sarf_detects_extension() -> None:
    ten_spade = encoding.encode_standard_card(0, 9, 0)
    meld = [
        encoding.encode_standard_card(0, 6, 0),
        encoding.encode_standard_card(0, 7, 0),
        encoding.encode_standard_card(0, 8, 0),
    ]

    game_state = _state_with_table(meld)

    assert card_enables_sarf(game_state, 1, ten_spade)


def test_discard_feeds_next_player_sarf_true_when_next_player_has_run() -> None:
    ten_spade = encoding.encode_standard_card(0, 9, 0)
    meld = [
        encoding.encode_standard_card(0, 6, 0),
        encoding.encode_standard_card(0, 7, 0),
        encoding.encode_standard_card(0, 8, 0),
    ]

    game_state = _state_with_table(meld)

    assert discard_feeds_next_player_sarf(game_state, 0, ten_spade)


def test_discard_feeds_next_player_sarf_false_when_no_meld() -> None:
    game_state = _state_with_table([
        encoding.encode_standard_card(0, 2, 0),
        encoding.encode_standard_card(0, 3, 0),
        encoding.encode_standard_card(0, 4, 0),
    ])

    eight_heart = encoding.encode_standard_card(1, 7, 0)

    assert not discard_feeds_next_player_sarf(game_state, 0, eight_heart)
