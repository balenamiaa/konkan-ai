"""Benchmark harness for comparing Konkan IS-MCTS configurations."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from . import actions, encoding, rules, scoreboard, state
from .ismcts.search import SearchConfig, run_search
from .state import PublicState

__all__ = ["AgentBreakdown", "HeadToHeadReport", "run_head_to_head"]


@dataclass(frozen=True, slots=True)
class AgentBreakdown:
    """Aggregate statistics collected for a single agent across a benchmark."""

    wins: int
    laid_points: int
    deadwood_points: int
    net_points: int


@dataclass(frozen=True, slots=True)
class HeadToHeadReport:
    """Summary of a head-to-head benchmark between two agents."""

    history: scoreboard.MatchHistory
    baseline: AgentBreakdown
    challenger: AgentBreakdown


def _ensure_stock(game_state: state.KonkanState, rng: random.Random) -> None:
    public = game_state.public
    if not isinstance(public, PublicState):
        return
    if public.draw_pile:
        return
    if len(public.trash_pile) <= 1:
        return
    top_card = public.trash_pile.pop()
    pool = public.trash_pile[:]
    rng.shuffle(pool)
    public.draw_pile = pool
    public.trash_pile = [top_card]


def _choose_draw_action(
    draw_actions: Sequence[actions.DrawAction],
) -> actions.DrawAction:
    for action in draw_actions:
        if action.source == "trash":
            return action
    return draw_actions[0]


def _choose_play_action(
    game_state: state.KonkanState,
    player_index: int,
    rng: random.Random,
    search_config: SearchConfig,
    play_actions: Sequence[actions.PlayAction],
) -> actions.PlayAction:
    node = run_search(game_state, rng, search_config)
    candidate_actions = list(node.actions)
    if candidate_actions and candidate_actions[0] is not None:
        chosen_index = node.best_action_index()
        chosen = candidate_actions[chosen_index]
        if isinstance(chosen, actions.PlayAction):
            return chosen

    hand_cards = encoding.cards_from_mask(game_state.players[player_index].hand_mask)
    if not hand_cards:
        return play_actions[0]
    fallback_discard = hand_cards[0]
    for action in play_actions:
        if action.discard == fallback_discard:
            return action
    return play_actions[0]


def _play_round(
    round_number: int,
    search_configs: Sequence[SearchConfig],
    dealer_index: int,
    rng: random.Random,
) -> scoreboard.RoundSummary:
    num_players = len(search_configs)
    deck = list(range(106))
    rng.shuffle(deck)

    config = state.KonkanConfig(
        num_players=num_players,
        hand_size=14,
        come_down_points=81,
        allow_trash_first_turn=False,
        dealer_index=dealer_index,
        first_player_hand_size=15,
    )

    game_state = state.deal_new_game(config, deck)
    if num_players:
        opener = game_state.public.current_player_index
        game_state.players[opener].phase = state.TurnPhase.AWAITING_TRASH

    turn_limit = 400
    for _ in range(turn_limit):
        public = game_state.public
        if not isinstance(public, PublicState):
            raise RuntimeError("benchmark requires PublicState-backed game state")
        if public.winner_index is not None:
            break

        current = public.current_player_index
        player_state = game_state.players[current]

        if player_state.phase == state.TurnPhase.AWAITING_DRAW:
            _ensure_stock(game_state, rng)
            draw_options = actions.legal_draw_actions(game_state, current)
            if not draw_options:
                raise RuntimeError("No legal draw actions available during benchmark")
            selected_draw = _choose_draw_action(draw_options)
            actions.apply_draw_action(game_state, current, selected_draw)
            continue

        hand_cards = encoding.cards_from_mask(player_state.hand_mask)
        play_options = actions.legal_play_actions(
            game_state, current, max_discards=len(hand_cards)
        )
        if not play_options:
            raise RuntimeError("No legal play actions available during benchmark")

        selected_play = _choose_play_action(
            game_state, current, rng, search_configs[current], play_options
        )
        snapshot = game_state.clone_shallow()
        try:
            actions.apply_play_action(game_state, current, selected_play)
        except (rules.IllegalTrash, rules.IllegalDraw):
            game_state = snapshot
            player_state = game_state.players[current]
            fallback_cards = encoding.cards_from_mask(player_state.hand_mask)
            if not fallback_cards:
                raise
            fallback_action = actions.PlayAction(discard=fallback_cards[0])
            actions.apply_play_action(game_state, current, fallback_action)
    else:
        public = game_state.public
        if not isinstance(public, PublicState):
            raise RuntimeError("benchmark requires PublicState-backed game state")
        deadwood_totals = [
            encoding.points_from_mask(player.hand_mask) for player in game_state.players
        ]
        winner_index = min(range(num_players), key=deadwood_totals.__getitem__)
        public.winner_index = winner_index
        public.current_player_index = winner_index

    public = game_state.public
    winner_index = -1
    if isinstance(public, PublicState) and public.winner_index is not None:
        winner_index = public.winner_index
    scores = rules.final_scores(game_state)

    return scoreboard.RoundSummary(
        round_number=round_number,
        winner_index=winner_index,
        scores=scores,
    )


def run_head_to_head(
    rounds: int,
    baseline: SearchConfig,
    challenger: SearchConfig,
    *,
    seed: int = 123,
) -> HeadToHeadReport:
    """Run a two-player benchmark returning aggregate statistics."""

    if rounds <= 0:
        raise ValueError("rounds must be positive")

    rng = random.Random(seed)
    history = scoreboard.MatchHistory(num_players=2)

    baseline_stats = {"wins": 0, "laid": 0, "deadwood": 0, "net": 0}
    challenger_stats = {"wins": 0, "laid": 0, "deadwood": 0, "net": 0}

    dealer_index = 1

    for round_number in range(1, rounds + 1):
        if round_number % 2 == 1:
            configs = [baseline, challenger]
            labels = ("baseline", "challenger")
        else:
            configs = [challenger, baseline]
            labels = ("challenger", "baseline")

        summary = _play_round(round_number, configs, dealer_index, rng)
        history.record(summary)

        for entry in summary.scores:
            label = labels[entry.player_index]
            bucket = baseline_stats if label == "baseline" else challenger_stats
            bucket["laid"] += entry.laid_points
            bucket["deadwood"] += entry.deadwood_points
            bucket["net"] += entry.net_points
            if entry.won_round:
                bucket["wins"] += 1

        dealer_index = (dealer_index + 1) % 2

    baseline_breakdown = AgentBreakdown(
        wins=baseline_stats["wins"],
        laid_points=baseline_stats["laid"],
        deadwood_points=baseline_stats["deadwood"],
        net_points=baseline_stats["net"],
    )
    challenger_breakdown = AgentBreakdown(
        wins=challenger_stats["wins"],
        laid_points=challenger_stats["laid"],
        deadwood_points=challenger_stats["deadwood"],
        net_points=challenger_stats["net"],
    )

    return HeadToHeadReport(
        history=history,
        baseline=baseline_breakdown,
        challenger=challenger_breakdown,
    )
