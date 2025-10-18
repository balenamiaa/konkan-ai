from __future__ import annotations

import random
from typing import cast

from konkan import actions, encoding, state
from konkan.ismcts.search import SearchConfig, run_search


def _simulate_game(seed: int) -> tuple[int | None, int]:
    rng = random.Random(seed)
    config = state.KonkanConfig(
        num_players=3,
        hand_size=6,
        first_player_hand_size=6,
        come_down_points=40,
        dealer_index=0,
    )
    deck = list(range(60))
    rng.shuffle(deck)
    game_state = state.deal_new_game(config, deck)
    search_config = SearchConfig(simulations=32)

    turns = 0
    while turns < 60:
        public = game_state.public
        if not isinstance(public, state.PublicState):
            break
        if public.winner_index is not None:
            break
        current = public.current_player_index
        player = game_state.players[current]

        if player.phase == state.TurnPhase.AWAITING_DRAW:
            draw_actions = actions.legal_draw_actions(game_state, current)
            if not draw_actions:
                break
            actions.apply_draw_action(game_state, current, draw_actions[0])
            continue

        hand_cards = encoding.cards_from_mask(player.hand_mask)
        if not hand_cards:
            break

        play_options = actions.legal_play_actions(
            game_state,
            current,
            max_discards=len(hand_cards),
        )
        node = run_search(game_state, rng, search_config)
        candidate_discards = list(node.actions)
        if not candidate_discards or candidate_discards[0] is None:
            chosen_discard = hand_cards[0]
        else:
            chosen_index = node.best_action_index()
            chosen_discard = cast(int, candidate_discards[chosen_index])

        selected_action = next(
            (action for action in play_options if action.discard == chosen_discard),
            play_options[0],
        )
        actions.apply_play_action(game_state, current, selected_action)
        turns += 1

    public = game_state.public
    winner = None
    if isinstance(public, state.PublicState):
        winner = public.winner_index
    return winner, turns


def test_mcts_simulation_is_deterministic() -> None:
    winner_one, turns_one = _simulate_game(123)
    winner_two, turns_two = _simulate_game(123)

    assert winner_one == winner_two
    assert turns_one == turns_two
    assert turns_one > 0
