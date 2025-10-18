from __future__ import annotations

import pytest

from konkan import actions, encoding, rules, state
from konkan._compat import np
from konkan.state import KonkanState


def _make_state_for_draw(
    trash_cards: list[int],
    hand_cards: list[int],
    *,
    come_down_points: int = 81,
    turn_index: int = 0,
) -> state.KonkanState:
    config = state.KonkanConfig(
        num_players=1,
        dealer_index=0,
        hand_size=len(hand_cards),
        come_down_points=come_down_points,
    )
    public = state.PublicState(
        draw_pile=[10, 11, 12],
        trash_pile=trash_cards,
        turn_index=turn_index,
        dealer_index=0,
        current_player_index=0,
    )
    player = state.PlayerState(hand_mask=encoding.mask_from_cards(hand_cards))
    player.phase = state.TurnPhase.AWAITING_DRAW
    game_state = state.KonkanState(
        player_to_act=0,
        turn_index=turn_index,
        deck=np.zeros(0, dtype=np.uint16),
        deck_top=0,
        trash=trash_cards.copy(),
        hands=[],
        table=[],
        public=public,
        highest_table_points=0,
        first_player_has_discarded=False,
        phase=rules.TurnPhase.DRAW,
        config=config,
        players=[player],
    )
    return game_state


def _make_state_for_discard(
    hand_cards: list[int], *, came_down: bool = False, come_down_points: int = 81
) -> state.KonkanState:
    config = state.KonkanConfig(
        num_players=1,
        dealer_index=0,
        hand_size=len(hand_cards),
        come_down_points=come_down_points,
    )
    public = state.PublicState(
        draw_pile=[10, 11, 12],
        trash_pile=[20],
        turn_index=1,
        dealer_index=0,
        current_player_index=0,
    )
    player = state.PlayerState(hand_mask=encoding.mask_from_cards(hand_cards))
    player.phase = state.TurnPhase.AWAITING_TRASH
    player.has_come_down = came_down
    game_state = state.KonkanState(
        player_to_act=0,
        turn_index=1,
        deck=np.zeros(0, dtype=np.uint16),
        deck_top=0,
        trash=[20],
        hands=[],
        table=[],
        public=public,
        highest_table_points=0,
        first_player_has_discarded=True,
        phase=rules.TurnPhase.PLAY,
        config=config,
        players=[player],
    )
    return game_state


def test_legal_draw_actions_includes_trash_when_allowed() -> None:
    top = encoding.encode_standard_card(0, 0, 0)
    hand_cards = [
        encoding.encode_standard_card(0, 1, 0),
        encoding.encode_standard_card(0, 2, 0),
    ]
    game_state = _make_state_for_draw([top], hand_cards, come_down_points=12, turn_index=1)

    actions_list = actions.legal_draw_actions(game_state, 0)
    sources = {action.source for action in actions_list}

    assert sources == {"deck", "trash"}


def test_legal_draw_actions_defaults_to_deck() -> None:
    hand_cards = [encoding.encode_standard_card(0, 1, 0)]
    game_state = _make_state_for_draw([], hand_cards)

    actions_list = actions.legal_draw_actions(game_state, 0)
    assert [action.source for action in actions_list] == ["deck"]


def test_legal_play_actions_returns_ranked_discards() -> None:
    cards = [
        encoding.encode_standard_card(0, 0, 0),
        encoding.encode_standard_card(0, 1, 0),
        encoding.encode_standard_card(0, 2, 0),
        encoding.encode_standard_card(1, 10, 0),
    ]
    game_state = _make_state_for_discard(cards)

    play_actions = actions.legal_play_actions(game_state, 0, max_discards=2)
    assert len(play_actions) == 2
    # The heuristic should prefer discarding the high-point outlier first (Q of hearts)
    assert play_actions[0].discard == encoding.encode_standard_card(1, 10, 0)


def test_legal_play_actions_include_lay_down_option() -> None:
    cards = [
        encoding.encode_standard_card(0, 0, 0),
        encoding.encode_standard_card(0, 1, 0),
        encoding.encode_standard_card(0, 2, 0),
        encoding.encode_standard_card(0, 3, 0),
    ]
    game_state = _make_state_for_discard(cards, come_down_points=10)

    play_actions = actions.legal_play_actions(game_state, 0, max_discards=1)
    laydown_flags = {action.lay_down for action in play_actions}
    assert laydown_flags == {False, True}


def test_legal_play_actions_include_sarf_option() -> None:
    cards = [
        encoding.encode_standard_card(0, 3, 0),
        encoding.encode_standard_card(0, 4, 0),
        encoding.encode_standard_card(1, 10, 0),
    ]
    game_state = _make_state_for_discard(cards, came_down=True)
    run_cards = [
        encoding.encode_standard_card(0, 0, 0),
        encoding.encode_standard_card(0, 1, 0),
        encoding.encode_standard_card(0, 2, 0),
    ]
    mask = encoding.mask_from_cards(run_cards)
    mask_hi, mask_lo = encoding.split_mask(mask)
    game_state.table.append(
        state.MeldOnTable(
            mask_hi=mask_hi,
            mask_lo=mask_lo,
            cards=list(run_cards),
            owner=1,
            kind=1,
            has_joker=False,
            points=encoding.points_from_mask(mask),
            is_four_set=False,
        )
    )

    play_actions = actions.legal_play_actions(game_state, 0, max_discards=3)
    assert any(action.sarf_moves for action in play_actions)


def test_apply_draw_action_executes_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    game_state = _make_state_for_draw([encoding.encode_standard_card(0, 0, 0)], [])
    draw_action = actions.DrawAction(source="deck")

    called = {}

    def mock_draw_from_stock(state: KonkanState, pid: int) -> None:
        called["stock"] = (state, pid)

    monkeypatch.setattr(rules, "draw_from_stock", mock_draw_from_stock)
    actions.apply_draw_action(game_state, 0, draw_action)
    assert "stock" in called


def test_apply_play_action_invokes_laydown(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = [encoding.encode_standard_card(0, 0, 0)]
    game_state = _make_state_for_discard(cards)
    play_action = actions.PlayAction(discard=cards[0], lay_down=True)

    called: dict[str, tuple[KonkanState, int]] = {}

    def mock_lay_down(state: KonkanState, pid: int) -> None:
        called["lay"] = (state, pid)

    def mock_trash(state: KonkanState, pid: int, card: int) -> None:
        called.setdefault("trash", (state, pid))

    monkeypatch.setattr(rules, "lay_down", mock_lay_down)
    monkeypatch.setattr(rules, "trash_card", mock_trash)

    actions.apply_play_action(game_state, 0, play_action)

    assert "lay" in called and "trash" in called
