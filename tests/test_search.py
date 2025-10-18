from __future__ import annotations

import random

from konkan import encoding, rules, state
from konkan._compat import np
from konkan.ismcts import search


def test_run_search_uses_ris_monkeypatch(monkeypatch) -> None:
    card0 = encoding.encode_standard_card(0, 0, 0)
    card1 = encoding.encode_standard_card(1, 0, 0)

    config = state.KonkanConfig(num_players=2, hand_size=1)
    public = state.PublicState(
        draw_pile=[],
        trash_pile=[],
        turn_index=0,
        dealer_index=0,
        current_player_index=0,
    )

    player0 = state.PlayerState(
        hand_mask=encoding.mask_from_cards([card0]),
        phase=state.TurnPhase.AWAITING_TRASH,
        has_come_down=True,
    )
    player1 = state.PlayerState(
        hand_mask=encoding.mask_from_cards([card1]),
        phase=state.TurnPhase.AWAITING_DRAW,
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
        players=[player0, player1],
    )

    calls: list[int | None] = []

    def fake_sample_world(state_arg, rng_arg, *, actor_index=None):
        calls.append(actor_index)
        return state_arg

    monkeypatch.setattr(search, "sample_world", fake_sample_world)

    rng = random.Random(0)
    search_config = search.SearchConfig(simulations=3)
    search.run_search(game_state, rng, search_config)

    assert calls
    assert calls[0] == 0
    assert any(call == 1 for call in calls[1:])
