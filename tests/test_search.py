from __future__ import annotations

import random

import pytest

from konkan import encoding, rules, state
from konkan._compat import np
from konkan.ismcts import policy, rollout, search


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


def test_run_search_applies_dirichlet_noise(monkeypatch) -> None:
    card0 = encoding.encode_standard_card(0, 0, 0)
    card1 = encoding.encode_standard_card(0, 1, 0)

    config_obj = state.KonkanConfig(num_players=1, hand_size=2)
    public = state.PublicState(
        draw_pile=[],
        trash_pile=[],
        turn_index=0,
        dealer_index=0,
        current_player_index=0,
    )

    player = state.PlayerState(
        hand_mask=encoding.mask_from_cards([card0, card1]),
        phase=state.TurnPhase.AWAITING_TRASH,
        has_come_down=True,
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
        config=config_obj,
        players=[player],
    )

    monkeypatch.setattr(search, "_dirichlet_noise", lambda _rng, _alpha, size: [0.8, 0.2][:size])
    monkeypatch.setattr(
        policy,
        "evaluate_actions",
        lambda _state, actions, **kwargs: [1.0] * len(actions),
    )
    monkeypatch.setattr(search, "sample_world", lambda state_arg, _rng, *, actor_index=None: state_arg)
    monkeypatch.setattr(rollout, "simulate", lambda _state, _root: 0.0)

    rng = random.Random(1)
    search_config = search.SearchConfig(
        simulations=1,
        dirichlet_alpha=0.3,
        dirichlet_weight=1.0,
    )
    node = search.run_search(game_state, rng, search_config)

    assert node.priors[0] == pytest.approx(0.8)
    assert node.priors[1] == pytest.approx(0.2)
