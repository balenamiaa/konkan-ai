from __future__ import annotations

import numpy as np

from konkan import encoding, rules, state
from konkan.ismcts import rollout
from konkan.state import PublicState, TurnPhase


def _build_state(hand_cards: list[int], *, highest_table_points: int = 0) -> state.KonkanState:
    config = state.KonkanConfig(
        num_players=1,
        hand_size=len(hand_cards),
        come_down_points=20,
        dealer_index=0,
    )
    public = PublicState(
        draw_pile=[10, 11, 12],
        trash_pile=[],
        turn_index=1,
        dealer_index=0,
        current_player_index=0,
        highest_table_points=highest_table_points,
    )
    player = state.PlayerState(hand_mask=encoding.mask_from_cards(hand_cards))
    player.phase = TurnPhase.AWAITING_TRASH
    return state.KonkanState(
        player_to_act=0,
        turn_index=1,
        deck=np.zeros(0, dtype=np.uint16),
        deck_top=0,
        trash=[],
        hands=[],
        table=[],
        public=public,
        highest_table_points=highest_table_points,
        first_player_has_discarded=True,
        phase=rules.TurnPhase.PLAY,
        config=config,
        players=[player],
    )


def test_rollout_prefers_meldable_hand() -> None:
    run_cards = [
        encoding.encode_standard_card(0, 0, 0),
        encoding.encode_standard_card(0, 1, 0),
        encoding.encode_standard_card(0, 2, 0),
    ]
    junk_cards = [
        encoding.encode_standard_card(1, 10, 0),
        encoding.encode_standard_card(2, 9, 0),
        encoding.encode_standard_card(3, 8, 0),
    ]

    good_state = _build_state(run_cards)
    bad_state = _build_state(junk_cards)

    good_score = rollout.simulate(good_state, 0)
    bad_score = rollout.simulate(bad_state, 0)

    assert good_score > bad_score


def test_rollout_returns_terminal_reward() -> None:
    base = _build_state([])
    public = base.public
    assert isinstance(public, PublicState)

    public.winner_index = 0
    assert rollout.simulate(base, 0) == 1.0

    public.winner_index = 1
    assert rollout.simulate(base, 0) == -1.0
