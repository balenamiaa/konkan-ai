"""Typer entry-point wiring for the Konkan CLI."""

from __future__ import annotations

import random
import sys
import termios
import tty
from dataclasses import dataclass
from typing import Callable, Sequence, Set

import typer
from rich import box
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from .. import actions, benchmark, encoding, melds, scoreboard, state
from ..ismcts.opponents import OpponentModel
from ..ismcts.search import SearchConfig, run_search
from ..state import PublicState
from .render import format_card, render_state
from .textual import run_textual_app


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


MAX_EVENT_LOG = 12


def _append_event(log: list[str], message: str) -> None:
    """Append ``message`` to ``log`` maintaining a bounded log length."""

    log.append(message)
    excess = len(log) - MAX_EVENT_LOG
    if excess > 0:
        del log[:excess]


def _format_draw_entries(
    draw_actions: Sequence[actions.DrawAction],
    public: PublicState,
) -> list[str]:
    """Return formatted entries describing available draw actions."""

    entries: list[str] = []
    for idx, action in enumerate(draw_actions, start=1):
        if action.source == "deck":
            label = "Draw from deck"
        else:
            top = public.trash_pile[-1] if public.trash_pile else None
            label = "Take trash"
            if top is not None:
                label += f" ({format_card(top)})"
        entries.append(f"[bold]{idx}[/bold] {label}")
    return entries


def _format_play_entries(play_actions: Sequence[actions.PlayAction]) -> list[str]:
    """Return formatted entries describing discard-phase actions."""

    return [f"[bold]{idx}[/bold] {_describe_play_action(action)}" for idx, action in enumerate(play_actions, start=1)]


def _actor_label(ctx: PlayerContext) -> str:
    return "[yellow]You[/yellow]" if ctx.role == "Human" else f"[cyan]{ctx.label}[/cyan]"


def _event_panel(events: Sequence[str]) -> Panel:
    log_table = Table.grid(expand=True)
    log_table.add_column(justify="left")
    if events:
        for line in events[-MAX_EVENT_LOG:]:
            log_table.add_row(line)
    else:
        log_table.add_row("[dim]Event log will appear here[/dim]")
    return Panel(log_table, title="Event Log", border_style="magenta", box=box.SIMPLE)


def _build_layout(
    state_obj: state.KonkanState,
    roles: Sequence[str],
    reveal_players: Sequence[int],
    events: Sequence[str],
    *,
    status_message: str = "",
    footer_message: str | None = None,
    action_entries: Sequence[str] | None = None,
    selected_index: int | None = None,
    highlight_map: dict[int, Set[int]] | None = None,
    debug_stats: dict[int, dict[str, object]] | None = None,
    debug_panel: Panel | None = None,
    show_debug: bool = False,
) -> Layout:
    public = state_obj.public if isinstance(state_obj.public, PublicState) else None
    header_parts = ["[bold cyan]Konkan[/bold cyan]"]
    if public is not None:
        header_parts.append(f"Turn {public.turn_index}")
        header_parts.append(f"Active: [yellow]P{public.current_player_index}[/yellow]")
    if status_message:
        header_parts.append(status_message)
    header_text = " • ".join(header_parts)

    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=6 if action_entries else 4),
    )

    header_panel = Panel(
        Align.center(header_text, vertical="middle"),
        border_style="cyan",
        box=box.ROUNDED,
    )
    layout["header"].update(header_panel)

    body_layout = Layout()
    columns = [
        Layout(
            render_state(
                state_obj,
                roles,
                reveal_players=reveal_players,
                highlight_map=highlight_map or {},
                show_debug=show_debug,
                debug_stats=debug_stats or {},
                title="Table State",
            ),
            name="table",
            ratio=3,
        )
    ]
    if debug_panel is not None:
        columns.append(Layout(debug_panel, name="debug", ratio=2))
    columns.append(Layout(_event_panel(events), name="events", ratio=2))
    body_layout.split_row(*columns)
    layout["body"].update(body_layout)

    if action_entries:
        actions_table = Table.grid(expand=True)
        actions_table.add_column(justify="left")
        for idx, entry in enumerate(action_entries):
            pointer = "➤ " if selected_index is not None and idx == selected_index else "  "
            display = f"{pointer}{entry}"
            if selected_index is not None and idx == selected_index:
                actions_table.add_row(f"[reverse]{display}[/reverse]")
            else:
                actions_table.add_row(display)
        footer_panel = Panel(
            actions_table,
            title=footer_message or "Choose an option",
            border_style="yellow",
            box=box.ROUNDED,
        )
    else:
        footer_panel = Panel(
            Align.center(footer_message or "Awaiting next step", vertical="middle"),
            border_style="yellow",
            box=box.ROUNDED,
        )
    layout["footer"].update(footer_panel)
    return layout


def _refresh_layout(
    live: Live,
    game_state: state.KonkanState,
    roles: Sequence[str],
    reveal_players: Sequence[int],
    events: Sequence[str],
    *,
    status_message: str = "",
    footer_message: str | None = None,
    action_entries: Sequence[str] | None = None,
    selected_index: int | None = None,
    highlight_targets: Sequence[int] | None = None,
    debug: bool = False,
    search_config: SearchConfig | None = None,
    opponent_model: OpponentModel | None = None,
) -> None:
    highlight_map = _compute_highlights(game_state, highlight_targets or [])
    debug_stats = _collect_debug_stats(game_state) if debug else {}
    debug_panel = (
        _debug_info_panel(game_state, search_config, opponent_model) if debug else None
    )
    live.update(
        _build_layout(
            game_state,
            roles,
            reveal_players,
            events,
            status_message=status_message,
            footer_message=footer_message,
            action_entries=action_entries,
            selected_index=selected_index,
            highlight_map=highlight_map,
            debug_stats=debug_stats,
            debug_panel=debug_panel,
            show_debug=debug,
        )
    )


def _read_key() -> str:
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _interactive_select(
    entries: Sequence[str],
    update_fn: Callable[[int], None],
    *,
    initial_index: int = 0,
) -> int:
    if not entries:
        raise ValueError("interactive selection requires at least one entry")
    index = initial_index % len(entries)
    while True:
        update_fn(index)
        key = _read_key()
        if key in {"\r", "\n"}:
            return index
        if key == "\x03":  # Ctrl+C
            raise KeyboardInterrupt
        if key in {"\x1b[A", "k", "w"}:
            index = (index - 1) % len(entries)
            continue
        if key in {"\x1b[B", "j", "s"}:
            index = (index + 1) % len(entries)
            continue
        if key.isdigit() and key != "0":
            value = int(key) - 1
            if 0 <= value < len(entries):
                return value
        # ignore all other keys


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


def _choose_ai_play_action(
    game_state: state.KonkanState,
    player_index: int,
    rng: random.Random,
    search_config: SearchConfig,
    play_actions: list[actions.PlayAction],
) -> actions.PlayAction:
    node = run_search(game_state, rng, search_config)
    candidate_actions = list(node.actions)
    if candidate_actions and candidate_actions[0] is not None:
        chosen_index = node.best_action_index()
        chosen = candidate_actions[chosen_index]
        if isinstance(chosen, actions.PlayAction):
            return chosen

    hand_cards = encoding.cards_from_mask(game_state.players[player_index].hand_mask)
    fallback_discard = hand_cards[0] if hand_cards else play_actions[0].discard

    for action in play_actions:
        if action.discard == fallback_discard:
            return action
    return play_actions[0]



def _render_round_summary(
    summary: scoreboard.RoundSummary,
    players_ctx: Sequence[PlayerContext],
    roles: Sequence[str],
) -> Table:
    """Return a Rich table describing the outcome of a round."""

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

    return table


def _render_match_summary(
    history: scoreboard.MatchHistory,
    players_ctx: Sequence[PlayerContext],
    roles: Sequence[str],
) -> Table:
    """Return the aggregated match summary table."""

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

    return table


def _compute_highlights(game_state: state.KonkanState, players: Sequence[int]) -> dict[int, Set[int]]:
    highlights: dict[int, Set[int]] = {}
    if not players:
        return highlights
    public = _public_state(game_state)
    base_threshold = 81
    if game_state.config is not None:
        base_threshold = game_state.config.come_down_points
    if public.highest_table_points > 0:
        base_threshold = max(base_threshold, public.highest_table_points + 1)

    for idx in players:
        if idx < 0 or idx >= len(game_state.players):
            continue
        player = game_state.players[idx]
        mask_hi, mask_lo = encoding.split_mask(player.hand_mask)
        try:
            cover = melds.best_cover_to_threshold(mask_hi, mask_lo, base_threshold)
        except Exception:  # pragma: no cover - defensive guard
            continue
        highlight_cards: Set[int] = set()
        for meld_entry in cover.melds:
            entry_mask = encoding.combine_mask(
                int(getattr(meld_entry, "mask_hi", 0)),
                int(getattr(meld_entry, "mask_lo", 0)),
            )
            highlight_cards.update(encoding.cards_from_mask(entry_mask))
        highlights[idx] = highlight_cards
    return highlights


def _collect_debug_stats(game_state: state.KonkanState) -> dict[int, dict[str, object]]:
    stats: dict[int, dict[str, object]] = {}
    for idx, player in enumerate(game_state.players):
        hand_cards = encoding.cards_from_mask(player.hand_mask)
        stats[idx] = {
            "hand_size": len(hand_cards),
            "deadwood": encoding.points_from_mask(player.hand_mask),
            "laid_points": getattr(player, "laid_points", 0),
            "table_points": getattr(player, "laid_points", 0),
            "phase": player.phase.value if hasattr(player, "phase") else "?",
        }
    return stats


def _debug_info_panel(
    game_state: state.KonkanState,
    search_config: SearchConfig | None,
    opponent_model: OpponentModel | None,
) -> Panel:
    public = _public_state(game_state)
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    deck_size = len(public.draw_pile)
    trash_size = len(public.trash_pile)
    top_trash = format_card(public.trash_pile[-1]) if public.trash_pile else "—"
    threshold = 81
    if game_state.config is not None:
        threshold = game_state.config.come_down_points
    if public.highest_table_points > 0:
        threshold = max(threshold, public.highest_table_points + 1)

    grid.add_row(f"[cyan]Deck[/cyan]: {deck_size}")
    grid.add_row(f"[cyan]Trash[/cyan]: {trash_size} (top {top_trash})")
    grid.add_row(f"[cyan]Threshold[/cyan]: {threshold}")
    if search_config is not None and search_config.dirichlet_alpha:
        grid.add_row(
            f"Dirichlet α={search_config.dirichlet_alpha:.2f} w={search_config.dirichlet_weight:.2f}"
        )
    else:
        grid.add_row("Dirichlet: off")
    grid.add_row(f"Opponent priors: {'on' if opponent_model else 'off'}")

    return Panel(grid, title="Debug Info", border_style="green", box=box.SIMPLE)


def _assign_dealer(game_state: state.KonkanState, dealer_index: int) -> int:
    public = _public_state(game_state)
    if not public.draw_pile:
        raise RuntimeError("draw pile empty while assigning dealer")
    extra_card = public.draw_pile.pop()
    dealer_state = game_state.players[dealer_index]
    dealer_state.hand_mask = encoding.add_card(dealer_state.hand_mask, extra_card)
    dealer_state.phase = state.TurnPhase.AWAITING_TRASH
    dealer_state.last_action_was_trash = False

    for idx, player in enumerate(game_state.players):
        if idx == dealer_index:
            continue
        player.phase = state.TurnPhase.AWAITING_DRAW
        player.last_action_was_trash = False

    public.current_player_index = dealer_index
    public.turn_index = 0
    game_state.player_to_act = dealer_index
    game_state.first_player_has_discarded = False

    return extra_card

@app.command()
def play(
    players: int = typer.Option(3, min=2, max=3, help="Number of seated players."),
    humans: int = typer.Option(1, min=0, help="Human-controlled seats starting from P0."),
    seed: int | None = typer.Option(None, help="Random seed for reproducible games (omit for randomness)."),
    simulations: int = typer.Option(128, min=1, help="MCTS simulations per AI discard."),
    dirichlet_alpha: float = typer.Option(0.0, min=0.0, help="Root Dirichlet alpha (0 disables noise)."),
    dirichlet_weight: float = typer.Option(0.25, min=0.0, max=1.0, help="Mixture weight for Dirichlet noise."),
    opponent_priors: bool = typer.Option(
        True,
        "--opponent-priors/--no-opponent-priors",
        help="Enable heuristic opponent prior adjustments.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Reveal enemy hands, highlight melds, and show additional statistics.",
    ),
) -> None:
    if humans > players:
        raise typer.BadParameter("Humans cannot exceed the total number of players.")

    run_textual_app(
        players=players,
        humans=humans,
        seed=seed,
        simulations=simulations,
        dirichlet_alpha=dirichlet_alpha if dirichlet_alpha > 0 else None,
        dirichlet_weight=dirichlet_weight,
        opponent_priors=opponent_priors,
        debug=debug,
    )


@app.command("benchmark")
def benchmark_cli(
    rounds: int = typer.Option(10, min=1, help="Number of head-to-head rounds."),
    baseline_sims: int = typer.Option(128, min=1, help="Simulations per move for the baseline agent."),
    challenger_sims: int = typer.Option(256, min=1, help="Simulations per move for the challenger."),
    seed: int = typer.Option(123, help="Random seed for the benchmark."),
    dirichlet_alpha: float = typer.Option(0.0, min=0.0, help="Root Dirichlet alpha (0 disables noise)."),
    dirichlet_weight: float = typer.Option(0.25, min=0.0, max=1.0, help="Mixture weight for Dirichlet noise."),
    opponent_priors: bool = typer.Option(
        True,
        "--opponent-priors/--no-opponent-priors",
        help="Enable heuristic opponent prior adjustments for both agents.",
    ),
) -> None:
    """Run a baseline vs. challenger benchmark."""

    opponent_model = OpponentModel() if opponent_priors else None
    alpha = dirichlet_alpha if dirichlet_alpha > 0 else None

    baseline_config = SearchConfig(
        simulations=baseline_sims,
        dirichlet_alpha=alpha,
        dirichlet_weight=dirichlet_weight,
        opponent_model=opponent_model,
    )
    challenger_config = SearchConfig(
        simulations=challenger_sims,
        dirichlet_alpha=alpha,
        dirichlet_weight=dirichlet_weight,
        opponent_model=opponent_model,
    )

    report = benchmark.run_head_to_head(
        rounds=rounds,
        baseline=baseline_config,
        challenger=challenger_config,
        seed=seed,
    )

    table = Table(title="Head-to-Head Benchmark", box=box.SIMPLE_HEAVY)
    table.add_column("Agent", justify="center")
    table.add_column("Wins", justify="right")
    table.add_column("Laid", justify="right")
    table.add_column("Deadwood", justify="right")
    table.add_column("Net", justify="right")

    table.add_row(
        "Baseline",
        str(report.baseline.wins),
        str(report.baseline.laid_points),
        str(report.baseline.deadwood_points),
        str(report.baseline.net_points),
    )
    table.add_row(
        "Challenger",
        str(report.challenger.wins),
        str(report.challenger.laid_points),
        str(report.challenger.deadwood_points),
        str(report.challenger.net_points),
    )

    console.print(table)

    if report.history.rounds:
        console.print(f"[cyan]{len(report.history.rounds)} round(s) simulated.[/cyan]")


def main() -> None:
    """Entry-point for ``python -m konkan.cli``."""

    app()


if __name__ == "__main__":  # pragma: no cover - CLI invocation
    main()
