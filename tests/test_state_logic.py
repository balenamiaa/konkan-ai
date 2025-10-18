from __future__ import annotations

from typing import List

import pytest

from konkan import encoding, rules, state
from konkan.determinize import sample_world


def test_deal_new_game_assigns_hand_sizes() -> None:
    deck = list(range(106))
    config = state.KonkanConfig(
        num_players=3,
        hand_size=14,
        first_player_hand_size=15,
        dealer_index=1,
    )

    game_state = state.deal_new_game(config, deck)

    assert isinstance(game_state.public, state.PublicState)

    first_player = (config.dealer_index + 1) % config.num_players
    hand_sizes = [len(encoding.cards_from_mask(player.hand_mask)) for player in game_state.players]

    assert hand_sizes[first_player] == 15
    for idx, size in enumerate(hand_sizes):
        if idx == first_player:
            continue
        assert size == 14

    expected_draw = 106 - (15 + 14 * (config.num_players - 1))
    assert len(game_state.public.draw_pile) == expected_draw


def test_lay_down_uses_solver_threshold() -> None:
    card = encoding.encode_standard_card
    player = state.PlayerState()
    player.hand_mask = encoding.mask_from_cards([card(0, 0, 0), card(0, 1, 0), card(0, 2, 0)])

    config = state.KonkanConfig(num_players=1, come_down_points=15)
    public = state.PublicState(draw_pile=[], trash_pile=[], turn_index=0, dealer_index=0)
    game_state = state.KonkanState(config=config, players=[player], public=public)

    result = rules.lay_down(game_state, 0)

    assert result.deadwood_mask == 0
    assert player.hand_mask == 0
    assert player.has_come_down
    assert game_state.public.highest_table_points >= 15


def test_sample_world_shuffles_with_custom_rng() -> None:
    class ReverseShuffle:
        def shuffle(self, seq: List[int]) -> None:
            seq.reverse()

    config = state.KonkanConfig(num_players=1, hand_size=1, first_player_hand_size=1)
    deck = list(range(10))
    game_state = state.deal_new_game(config, deck)
    original_draw = list(game_state.public.draw_pile)

    determinized = sample_world(game_state, ReverseShuffle())

    assert determinized.public.draw_pile == list(reversed(original_draw))
    assert game_state.public.draw_pile == original_draw


def test_tools_run_test_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    from konkan import tools

    recorded: list[list[str]] = []

    def fake_run_command(command: list[str]) -> int:
        recorded.append(command)
        return 0

    monkeypatch.setattr(tools, "_run_command", fake_run_command)
    exit_code = tools.run_test()

    assert exit_code == 0
    assert len(recorded) == 3
