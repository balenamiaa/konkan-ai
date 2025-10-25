from __future__ import annotations

from typing import List

import numpy as np

from konkan import encoding, rules, state

SET_KIND = 0
RUN_KIND = 1


def _table_meld(cards: List[int], owner: int, kind: int) -> state.MeldOnTable:
    mask = encoding.mask_from_cards(cards)
    mask_hi, mask_lo = encoding.split_mask(mask)
    return state.MeldOnTable(
        mask_hi=mask_hi,
        mask_lo=mask_lo,
        cards=list(cards),
        owner=owner,
        kind=kind,
        has_joker=any(card in encoding.JOKER_IDS for card in cards),
        points=encoding.points_from_mask(mask),
        is_four_set=kind == SET_KIND and len(cards) == 4 and not any(card in encoding.JOKER_IDS for card in cards),
    )


def _base_state(hand_cards: List[int], current_player: int = 0) -> state.KonkanState:
    config = state.KonkanConfig(num_players=2, hand_size=len(hand_cards))
    public = state.PublicState(
        draw_pile=[],
        trash_pile=[],
        turn_index=1,
        dealer_index=0,
        current_player_index=current_player,
    )
    players = [state.PlayerState(hand_mask=encoding.mask_from_cards(hand_cards)), state.PlayerState()]
    players[0].has_come_down = True
    return state.KonkanState(
        player_to_act=current_player,
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
        players=players,
    )


def test_sarf_card_extends_run() -> None:
    hand = [encoding.encode_standard_card(0, 3, 0)]
    game_state = _base_state(hand)
    game_state.table.append(
        _table_meld(
            [
                encoding.encode_standard_card(0, 0, 0),
                encoding.encode_standard_card(0, 1, 0),
                encoding.encode_standard_card(0, 2, 0),
            ],
            owner=1,
            kind=RUN_KIND,
        )
    )

    card_to_sarf = hand[0]
    assert rules.can_sarf_card(game_state, 0, 0, card_to_sarf)
    rules.sarf_card(game_state, 0, 0, card_to_sarf)

    assert card_to_sarf not in encoding.cards_from_mask(game_state.players[0].hand_mask)
    assert card_to_sarf in game_state.table[0].cards
    assert encoding.has_card(game_state.players[0].laid_mask, card_to_sarf)
    assert game_state.players[0].laid_points == encoding.card_points(card_to_sarf)


def test_sarf_card_swaps_joker() -> None:
    seven_spade = encoding.encode_standard_card(0, 6, 0)
    seven_heart = encoding.encode_standard_card(1, 6, 0)
    seven_diamond = encoding.encode_standard_card(2, 6, 0)
    joker = encoding.JOKER_IDS[0]

    hand = [seven_diamond]
    game_state = _base_state(hand)
    game_state.table.append(_table_meld([seven_spade, seven_heart, joker], owner=1, kind=SET_KIND))

    rules.sarf_card(game_state, 0, 0, seven_diamond)

    player_hand = encoding.cards_from_mask(game_state.players[0].hand_mask)
    assert joker in player_hand
    assert seven_diamond in game_state.table[0].cards
    assert encoding.has_card(game_state.players[0].laid_mask, seven_diamond)
    assert game_state.players[0].laid_points == encoding.card_points(seven_diamond)


def test_can_sarf_card_rejects_invalid() -> None:
    hand = [encoding.encode_standard_card(0, 10, 0)]
    game_state = _base_state(hand)
    game_state.table.append(
        _table_meld(
            [
                encoding.encode_standard_card(0, 0, 0),
                encoding.encode_standard_card(0, 1, 0),
                encoding.encode_standard_card(0, 2, 0),
            ],
            owner=1,
            kind=RUN_KIND,
        )
    )

    assert not rules.can_sarf_card(game_state, 0, 0, hand[0])


def test_sarf_card_allows_joker_extension() -> None:
    joker = encoding.JOKER_IDS[0]
    hand = [joker]
    game_state = _base_state(hand)

    run_cards = [
        encoding.encode_standard_card(0, 4, 0),
        encoding.encode_standard_card(0, 5, 0),
        encoding.encode_standard_card(0, 6, 0),
    ]
    mask = encoding.mask_from_cards(run_cards)
    mask_hi, mask_lo = encoding.split_mask(mask)
    game_state.table.append(
        state.MeldOnTable(
            mask_hi=mask_hi,
            mask_lo=mask_lo,
            cards=list(run_cards),
            owner=1,
            kind=RUN_KIND,
            has_joker=False,
            points=encoding.points_from_mask(mask),
            is_four_set=False,
        )
    )

    assert rules.can_sarf_card(game_state, 0, 0, joker)
    rules.sarf_card(game_state, 0, 0, joker)

    assert joker not in encoding.cards_from_mask(game_state.players[0].hand_mask)
    assert joker in game_state.table[0].cards
