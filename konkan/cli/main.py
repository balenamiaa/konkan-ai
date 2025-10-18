"""Typer entry-point wiring for the Konkan CLI."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence, cast

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from .. import actions, encoding, rules, scoreboard, state
from ..ismcts.search import SearchConfig, run_search
from ..state import PublicState
from .render import format_card, render_state


@dataclass(slots=True)
class PlayerContext:
    """Runtime metadata describing each seated player."""

    label: str
    role: str  # "Human" or "AI"


app = typer.Typer(add_completion=False, rich_markup_mode="rich")
console = Console()


def _public_state(game_state: state.KonkanState) -> PublicState:
    public = game_state.public
    if not isinstance(public, PublicState):  # pragma: no cover - defensive guard
        raise RuntimeError("KonkanState public state is not initialised")
    return public


def _build_deck() -> list[int]:
    deck = list(range(106))
    return deck


def _ensure_stock(state_obj: state.KonkanState, rng: random.Random) -> None:
    public = _public_state(state_obj)
    if public.draw_pile:
        return
    if len(public.trash_pile) <= 1:
        return
    top_card = public.trash_pile.pop()
    pool = public.trash_pile[:]
    rng.shuffle(pool)
    public.draw_pile = pool
    public.trash_pile = [top_card]


def _prompt_draw_action(
    draw_actions: list[actions.DrawAction], public: PublicState
) -> actions.DrawAction:
    labels = []
    for idx, action in enumerate(draw_actions, start=1):
        if action.source == "deck":
            label = f"{idx}. Draw from deck"
        else:
            top = public.trash_pile[-1] if public.trash_pile else None
            label = (
                f"{idx}. Take trash ({format_card(top)})"
                if top is not None
                else f"{idx}. Take trash"
            )
        labels.append(label)
    console.print("\n".join(labels))
    while True:
        choice = typer.prompt("Select draw action", default="1").strip()
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(draw_actions):
                return draw_actions[index]
        console.print("[red]Invalid selection. Please try again.[/red]")


def _choose_ai_draw_action(draw_actions: list[actions.DrawAction]) -> actions.DrawAction:
    for action in draw_actions:
        if action.source == "trash":
            return action
    return draw_actions[0]


def _describe_play_action(action: actions.PlayAction) -> str:
    parts: list[str] = []
    if action.lay_down:
        parts.append("Lay down")
    for target, card_id in action.sarf_moves:
        parts.append(f"Sarf {format_card(card_id)} → meld {target}")
    parts.append(f"Discard {format_card(action.discard)}")
    return " & ".join(parts)


def _prompt_play_action(play_actions: list[actions.PlayAction]) -> actions.PlayAction:
    entries = [
        f"{idx + 1}. {_describe_play_action(action)}" for idx, action in enumerate(play_actions)
    ]
    console.print("\n".join(entries))
    while True:
        choice = typer.prompt("Select action", default="1").strip()
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(play_actions):
                return play_actions[index]
        console.print("[red]Invalid selection. Please try again.[/red]")


def _choose_ai_play_action(
    game_state: state.KonkanState,
    player_index: int,
    rng: random.Random,
    search_config: SearchConfig,
    play_actions: list[actions.PlayAction],
) -> actions.PlayAction:
    node = run_search(game_state, rng, search_config)
    candidate_discards = list(node.actions)
    chosen_discard: int
    if not candidate_discards or candidate_discards[0] is None:
        hand_cards = encoding.cards_from_mask(game_state.players[player_index].hand_mask)
        chosen_discard = hand_cards[0]
    else:
        chosen_index = node.best_action_index()
        chosen_discard = cast(int, candidate_discards[chosen_index])

    matching = [action for action in play_actions if action.discard == chosen_discard]
    if matching:
        for action in matching:
            if action.lay_down and action.sarf_moves:
                return action
        for action in matching:
            if action.sarf_moves:
                return action
        for action in matching:
            if action.lay_down:
                return action
        return matching[0]
    return play_actions[0]



def _render_round_summary(
    summary: scoreboard.RoundSummary,
    players_ctx: Sequence[PlayerContext],
    roles: Sequence[str],
) -> None:
    """Render a table describing the outcome of a round."""

    table = Table(title=f"Round {summary.round_number} Summary", box=box.SIMPLE_HEAVY)
    table.add_column("Player", justify="center")
    table.add_column("Role", justify="center")
    table.add_column("Result", justify="center")
    table.add_column("Laid", justify="right")
    table.add_column("Deadwood", justify="right")
    table.add_column("Net", justify="right")

    for entry in summary.scores:
        idx = entry.player_index
        ctx = players_ctx[idx]
        role = roles[idx] if idx < len(roles) else "AI"
        result = "[bold green]Win[/bold green]" if entry.won_round else "Loss"
        label = ctx.label
        if entry.won_round:
            label = f"[bold green]{label}[/bold green]"
            role = f"[bold]{role}[/bold]"
        table.add_row(
            label,
            role,
            result,
            str(entry.laid_points),
            str(entry.deadwood_points),
            str(entry.net_points),
        )

    console.print(table)


def _render_match_summary(
    history: scoreboard.MatchHistory,
    players_ctx: Sequence[PlayerContext],
    roles: Sequence[str],
) -> None:
    """Render the aggregated match summary."""

    totals = history.totals()
    table = Table(title="Match Summary", box=box.DOUBLE_EDGE)
    table.add_column("Player", justify="center")
    table.add_column("Role", justify="center")
    table.add_column("Wins", justify="right")
    table.add_column("Laid", justify="right")
    table.add_column("Deadwood", justify="right")
    table.add_column("Net", justify="right")

    best_net = max((total.net_points for total in totals), default=0)

    for total in totals:
        idx = total.player_index
        ctx = players_ctx[idx]
        role = roles[idx] if idx < len(roles) else "AI"
        net_str = str(total.net_points)
        label = ctx.label
        if total.net_points == best_net and history.rounds:
            label = f"[bold blue]{label}[/bold blue]"
            role = f"[bold]{role}[/bold]"
            net_str = f"[bold blue]{net_str}[/bold blue]"
        table.add_row(
            label,
            role,
            str(total.wins),
            str(total.laid_points),
            str(total.deadwood_points),
            net_str,
        )

    console.print(table)


@app.command()
def play(
    players: int = typer.Option(3, min=2, max=3, help="Number of seated players."),
    humans: int = typer.Option(1, min=0, help="Human-controlled seats starting from P0."),
    seed: int = typer.Option(42, help="Random seed used for shuffling and search."),
    simulations: int = typer.Option(128, min=1, help="MCTS simulations per AI discard."),
    rounds: int = typer.Option(1, min=1, help="Number of consecutive rounds to play."),
) -> None:
    """Play a Konkan match against AI opponents."""

    if humans > players:
        raise typer.BadParameter("Humans cannot exceed the total number of players.")

    rng = random.Random(seed)
    roles = ["Human" if idx < humans else "AI" for idx in range(players)]
    players_ctx = [PlayerContext(label=f"P{idx}", role=roles[idx]) for idx in range(players)]

    search_config = SearchConfig(simulations=simulations)
    history = scoreboard.MatchHistory(players)
    dealer_index = (players - 1) % players if players else 0

    for round_number in range(1, rounds + 1):
        deck = _build_deck()
        rng.shuffle(deck)

        config = state.KonkanConfig(
            num_players=players,
            hand_size=14,
            come_down_points=81,
            allow_trash_first_turn=False,
            dealer_index=dealer_index,
            first_player_hand_size=15,
        )

        game_state = state.deal_new_game(config, deck)
        if players:
            opener = _public_state(game_state).current_player_index
            game_state.players[opener].phase = state.TurnPhase.AWAITING_TRASH

        console.print(f"\n[magenta]Round {round_number}[/magenta]")
        console.print(render_state(game_state, roles, reveal_players=range(humans)))

        while True:
            public = _public_state(game_state)
            if public.winner_index is not None:
                break

            current = public.current_player_index
            ctx = players_ctx[current]
            player = game_state.players[current]

            if player.phase == state.TurnPhase.AWAITING_DRAW:
                _ensure_stock(game_state, rng)
                draw_options = actions.legal_draw_actions(game_state, current)
                if not draw_options:  # pragma: no cover - defensive guard
                    raise RuntimeError("No legal draw actions available")

                if ctx.role == "Human":
                    selected = _prompt_draw_action(draw_options, public)
                else:
                    selected = _choose_ai_draw_action(draw_options)
                    console.print(
                        f"[cyan]{ctx.label}[/cyan] drew from {'trash' if selected.source == 'trash' else 'deck'}"
                    )

                actions.apply_draw_action(game_state, current, selected)
                console.print(render_state(game_state, roles, reveal_players=range(humans)))
                continue

            hand_cards = encoding.cards_from_mask(player.hand_mask)
            if ctx.role == "Human":
                play_options = actions.legal_play_actions(
                    game_state, current, max_discards=min(5, len(hand_cards))
                )
            else:
                play_options = actions.legal_play_actions(
                    game_state, current, max_discards=len(hand_cards)
                )

            if not play_options:  # pragma: no cover - defensive guard
                raise RuntimeError("No legal play actions available")

            if ctx.role == "Human":
                selected_action = _prompt_play_action(play_options)
                actions.apply_play_action(game_state, current, selected_action)
                prefix = "Lay down & " if selected_action.lay_down else ""
                console.print(f"You {prefix}discarded {format_card(selected_action.discard)}")
            else:
                selected_action = _choose_ai_play_action(
                    game_state, current, rng, search_config, play_options
                )
                actions.apply_play_action(game_state, current, selected_action)
                prefix = "laying down & " if selected_action.lay_down else ""
                console.print(
                    f"[cyan]{ctx.label}[/cyan] {prefix}discarded [bold]{format_card(selected_action.discard)}[/bold]"
                )

            console.print(render_state(game_state, roles, reveal_players=range(humans)))

        winner = _public_state(game_state).winner_index
        if winner is not None:
            ctx = players_ctx[winner]
            if ctx.role == "Human":
                console.print("[bold green]You win the round![/bold green]")
            else:
                console.print(f"[bold red]{ctx.label} wins the round.[/bold red]")

        try:
            scores = rules.final_scores(game_state)
        except ValueError:
            scores = []

        if scores:
            summary = scoreboard.RoundSummary(
                round_number=round_number,
                winner_index=winner if winner is not None else -1,
                scores=scores,
            )
            history.record(summary)
            _render_round_summary(summary, players_ctx, roles)

        dealer_index = (dealer_index + 1) % players if players else 0

    if history.rounds:
        _render_match_summary(history, players_ctx, roles)


def main() -> None:
    """Entry-point for ``python -m konkan.cli``."""

    app()


if __name__ == "__main__":  # pragma: no cover - CLI invocation
    main()
