"""Textual-powered interactive Konkan interface."""

from __future__ import annotations

import random
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from rich import box
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from ... import actions, encoding, melds, rules, scoreboard, state
from ...ismcts.node import Node
from ...ismcts.opponents import OpponentModel
from ...ismcts.search import SearchConfig, run_search
from ...state import PublicState
from ..render import format_card

MAX_EVENT_LINES = 18


@dataclass(slots=True)
class PlayerContext:
    """Cached metadata for each seat."""

    label: str
    role: str


def _public_state(game_state: state.KonkanState) -> PublicState:
    public = game_state.public
    if not isinstance(public, PublicState):  # pragma: no cover - defensive guard
        raise RuntimeError("KonkanState public state not initialised")
    return public


class EventLog(Static):
    """Simple rolling log rendered inside a panel."""

    lines: reactive[tuple[str, ...]] = reactive((), init=False)

    def on_mount(self) -> None:  # pragma: no cover - widget lifecycle glue
        self._refresh()

    def add(self, message: str) -> None:
        log = list(self.lines)
        log.append(message)
        self.lines = tuple(log[-MAX_EVENT_LINES:])

    def clear(self) -> None:
        self.lines = ()

    def watch_lines(self, value: tuple[str, ...]) -> None:
        self._refresh(value)

    def _refresh(self, lines: tuple[str, ...] | None = None) -> None:
        content = Table.grid(padding=(0, 1))
        content.expand = True
        content.add_column(justify="left")
        rows = lines if lines is not None else self.lines
        if rows:
            for line in rows:
                content.add_row(Text.from_markup(line))
        else:
            content.add_row(Text.from_markup("[dim]Event log will appear here[/dim]"))
        self.update(Panel(content, title="Events", border_style="magenta"))


class InfoPanel(Static):
    """Reusable wrapper that expects ``update_panel`` calls with Rich renderables."""

    def update_panel(self, title: str, body) -> None:
        self.update(Panel(body, title=title, border_style="cyan"))


class ScorePanel(Static):
    """Displays rolling match summaries."""

    def update_scores(self, history: scoreboard.MatchHistory) -> None:
        totals = history.totals()
        table = Table(box=box.SIMPLE_HEAVY, expand=True)
        table.add_column("Player", justify="left")
        table.add_column("Wins", justify="right")
        table.add_column("Laid", justify="right")
        table.add_column("Deadwood", justify="right")
        table.add_column("Net", justify="right")
        best_net = max((entry.net_points for entry in totals), default=0)
        for entry in totals:
            label = f"P{entry.player_index}"
            if entry.net_points == best_net and history.rounds:
                label = f"[bold blue]{label}[/bold blue]"
            table.add_row(
                label,
                str(entry.wins),
                str(entry.laid_points),
                str(entry.deadwood_points),
                str(entry.net_points),
            )
        if not totals:
            table.add_row(Text.from_markup("[dim]No results yet[/dim]"), "-", "-", "-", "-")
        self.update(Panel(table, title="Match Totals", border_style="bright_blue"))


class DebugPanel(Static):
    """Shows live debug statistics when enabled."""

    def update_debug(self, lines: Sequence[str]) -> None:
        grid = Table.grid(padding=(0, 1))
        grid.add_column(justify="left")
        if lines:
            for line in lines:
                grid.add_row(Text.from_markup(line))
        else:
            grid.add_row(Text.from_markup("[dim]Debug data hidden (press D)[/dim]"))
        self.update(Panel(grid, title="Debug", border_style="yellow"))


class StatusStrip(Static):
    """Single line status helper."""

    message: reactive[str] = reactive("", init=False)

    def watch_message(self, value: str) -> None:
        self.update(Panel(Text.from_markup(value or "[dim]Ready[/dim]"), border_style="green"))


class ActionPalette(OptionList):
    """Interactive list used for draw / discard selection."""

    class Choice(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(self, prompt: str, entries: Sequence[str]) -> None:
        self.prompt = prompt
        options = [
            Option(f"[bold]{idx + 1}[/bold] {entry}", id=str(idx))
            for idx, entry in enumerate(entries)
        ]
        super().__init__(*options)
        if options:
            self.index = 0

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:  # pragma: no cover - Textual glue
        event.stop()
        option_id = event.option.id
        if option_id is None:
            return
        selected = int(option_id)
        self.post_message(self.Choice(selected))

    def on_key(self, event: events.Key) -> None:  # pragma: no cover - driven by UI interaction
        if event.key.isdigit() and event.key != "0":
            index = int(event.key) - 1
            if 0 <= index < len(self.options):
                self.index = index
                self.post_message(self.Choice(index))
                event.stop()


class KonkanTextualApp(App):
    """Textual Konkan game UI."""

    CSS = """
    Screen {
        layout: vertical;
        height: 100%;
    }

    #main {
        layout: horizontal;
        height: 1fr;
        width: 1fr;
    }

    #left, #right {
        layout: vertical;
        width: 1fr;
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }

    #actions {
        layout: vertical;
        min-height: 6;
    }

    ActionPalette {
        border: heavy $accent;
        padding: 1 1;
        width: 100%;
        height: auto;
        max-height: 16;
    }

    StatusStrip {
        width: 100%;
    }

    DebugPanel {
        min-height: 6;
    }

    InfoPanel, EventLog, ScorePanel {
        width: 100%;
        min-height: 6;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("d", "toggle_debug", "Debug overlay"),
        Binding("h", "toggle_reveal", "Reveal hands"),
        Binding("n", "next_round", "Next round", show=False),
    ]

    def __init__(
        self,
        *,
        players: int,
        humans: int,
        seed: int | None,
        simulations: int,
        dirichlet_alpha: float | None,
        dirichlet_weight: float,
        opponent_priors: bool,
        start_debug: bool,
    ) -> None:
        super().__init__()
        if players <= 0:
            raise ValueError("players must be positive")
        if humans < 0 or humans > players:
            raise ValueError("humans must be within [0, players]")
        self.players = players
        self.humans = humans
        if seed is None:
            seed = random.SystemRandom().randrange(0, 2**63)
        self.seed = seed
        self.rng = random.Random(seed)
        self.roles = ["Human" if idx < humans else "AI" for idx in range(players)]
        self.contexts = [PlayerContext(label=f"P{idx}", role=self.roles[idx]) for idx in range(players)]

        opponent_model = OpponentModel() if opponent_priors else None
        self.search_config = SearchConfig(
            simulations=simulations,
            dirichlet_alpha=dirichlet_alpha,
            dirichlet_weight=dirichlet_weight,
            opponent_model=opponent_model,
        )

        self.debug_enabled = start_debug
        self.reveal_enabled = start_debug
        self.awaiting_next_round = False
        self.round_number = 1
        self.dealer_index = 0
        self.match_history = scoreboard.MatchHistory(players)

        self.game_state: state.KonkanState | None = None
        self._active_palette: ActionPalette | None = None
        self._pending_kind: str | None = None
        self._pending_actor: int | None = None
        self._pending_actions: list[object] | None = None

        # Widgets initialised in compose
        self.status_strip: StatusStrip | None = None
        self.table_panel: InfoPanel | None = None
        self.hand_panel: InfoPanel | None = None
        self.meld_panel: InfoPanel | None = None
        self.recommend_panel: InfoPanel | None = None
        self.event_log: EventLog | None = None
        self.score_panel: ScorePanel | None = None
        self.debug_panel: DebugPanel | None = None
        self.actions_container: Vertical | None = None
        self.action_prompt: Static | None = None
        self.last_search_stats: dict[str, object] | None = None
        self.player_stats: dict[int, dict[str, object]] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        self.status_strip = StatusStrip(id="status")
        yield self.status_strip

        self.table_panel = InfoPanel(id="table")
        self.hand_panel = InfoPanel(id="hand")
        self.recommend_panel = InfoPanel(id="recommend")
        self.table_panel.update_panel("Table", Text.from_markup("[dim]Loading table…[/dim]"))
        self.hand_panel.update_panel("Your Hand", Text.from_markup("[dim]Waiting…[/dim]"))
        self.recommend_panel.update_panel("Suggested Melds", Text.from_markup("[dim]Waiting…[/dim]"))

        self.action_prompt = Static(Text.from_markup("[dim]Waiting for turn…[/dim]"), id="actions-prompt")
        self.actions_container = Vertical(self.action_prompt, id="actions")

        left = Vertical(
            self.table_panel,
            self.hand_panel,
            self.recommend_panel,
            self.actions_container,
            id="left",
        )

        self.meld_panel = InfoPanel(id="melds")
        self.event_log = EventLog(id="events")
        self.score_panel = ScorePanel(id="scores")
        self.debug_panel = DebugPanel(id="debug")
        self.meld_panel.update_panel("Table Melds", Text.from_markup("[dim]None yet[/dim]"))
        if self.score_panel:
            self.score_panel.update_scores(self.match_history)
        if self.debug_panel and not self.debug_enabled:
            self.debug_panel.update_debug([])

        right = Vertical(
            self.meld_panel,
            self.event_log,
            self.score_panel,
            self.debug_panel,
            id="right",
        )

        yield Horizontal(left, right, id="main")
        yield Footer()

    async def on_mount(self) -> None:
        await self._start_round()

    async def action_toggle_debug(self) -> None:
        self.debug_enabled = not self.debug_enabled
        if self.debug_panel and self.game_state:
            self.debug_panel.update_debug(
                _debug_lines(self.search_config, self.game_state, self.last_search_stats)
                if self.debug_enabled
                else []
            )

    async def action_toggle_reveal(self) -> None:
        self.reveal_enabled = not self.reveal_enabled
        if self.game_state:
            await self._refresh_ui()

    async def action_next_round(self) -> None:
        if not self.awaiting_next_round:
            return
        self.awaiting_next_round = False
        self.round_number += 1
        self.dealer_index = (self.dealer_index + 1) % self.players
        await self._start_round()

    async def _start_round(self) -> None:
        await self._dismiss_palette(self._active_palette)
        self._clear_pending()
        self.last_search_stats = None
        deck = list(range(encoding.DECK_CARD_COUNT))
        self.rng.shuffle(deck)
        config = state.KonkanConfig(
            num_players=self.players,
            hand_size=14,
            come_down_points=81,
            allow_trash_first_turn=False,
            dealer_index=self.dealer_index,
            first_player_hand_size=14,
        )
        self.game_state = state.deal_new_game(config, deck)
        extra_card = _assign_dealer(self.game_state, self.dealer_index)
        if self.event_log:
            label = self.contexts[self.dealer_index].label
            card_text = format_card(extra_card)
            self.event_log.add(f"[bold cyan]Round {self.round_number}[/bold cyan] dealer {label} receives {card_text}")
        await self._refresh_ui()
        await self._process_turn()

    async def _process_turn(self) -> None:
        if self.game_state is None or self.awaiting_next_round:
            return

        public = _public_state(self.game_state)
        actor_idx = public.current_player_index

        if public.winner_index is not None:
            await self._handle_round_end(public.winner_index)
            return

        actor_ctx = self.contexts[actor_idx]
        self._set_status(f"[yellow]{actor_ctx.label}[/yellow] to act ({actor_ctx.role})")

        player_state = self.game_state.players[actor_idx]
        if actor_idx < self.humans:
            if player_state.phase == state.TurnPhase.AWAITING_DRAW:
                await self._prompt_draw(actor_idx)
            else:
                await self._prompt_play(actor_idx)
        else:
            await self._perform_ai_turn(actor_idx, player_state)
            await self._refresh_ui()
            await self._process_turn()

    async def _prompt_draw(self, actor_idx: int) -> None:
        assert self.game_state is not None
        public = _public_state(self.game_state)
        draw_actions = actions.legal_draw_actions(self.game_state, actor_idx)
        if not draw_actions:
            raise RuntimeError("No draw actions available")

        entries = _draw_entries(draw_actions, public)
        palette = ActionPalette("Select draw action", entries)
        await self._mount_palette(palette, "Select draw action")
        self._pending_kind = "draw"
        self._pending_actor = actor_idx
        self._pending_actions = list(draw_actions)

    async def _prompt_play(self, actor_idx: int) -> None:
        assert self.game_state is not None
        if rules.can_player_come_down(self.game_state, actor_idx):
            came_down = await self._offer_come_down(actor_idx)
            if came_down:
                await self._refresh_ui()

        hand_cards = encoding.cards_from_mask(self.game_state.players[actor_idx].hand_mask)
        play_actions = actions.legal_play_actions(
            self.game_state,
            actor_idx,
            max_discards=len(hand_cards) if hand_cards else _MAX_DISCARD_CHOICES(self.game_state, actor_idx),
        )
        if not play_actions:
            raise RuntimeError("No discard actions available")

        play_actions = [action for action in play_actions if not action.lay_down]
        if not play_actions:
            play_actions = actions.legal_play_actions(
                self.game_state,
                actor_idx,
                max_discards=len(hand_cards) if hand_cards else _MAX_DISCARD_CHOICES(self.game_state, actor_idx),
            )

        entries = [_describe_play_action(action) for action in play_actions]
        palette = ActionPalette("Select discard action", entries)
        await self._mount_palette(palette, "Select discard action")
        self._pending_kind = "play"
        self._pending_actor = actor_idx
        self._pending_actions = list(play_actions)

    async def _perform_ai_turn(self, actor_idx: int, player_state: state.PlayerState) -> None:
        assert self.game_state is not None
        if player_state.phase == state.TurnPhase.AWAITING_DRAW:
            draw_action = _choose_ai_draw_action(self.game_state, actor_idx)
            public = _public_state(self.game_state)
            top_before = public.trash_pile[-1] if public.trash_pile else None
            actions.apply_draw_action(self.game_state, actor_idx, draw_action)
            if self.event_log:
                actor_label = self.contexts[actor_idx].label
                if draw_action.source == "trash" and top_before is not None:
                    self.event_log.add(f"{actor_label} drew {_format_card_highlight(top_before)} from trash")
                else:
                    self.event_log.add(f"{actor_label} drew from deck")
        else:
            play_action, diagnostics = _choose_ai_play_action(
                self.game_state,
                actor_idx,
                self.rng,
                self.search_config,
            )
            self.last_search_stats = diagnostics
            actions.apply_play_action(self.game_state, actor_idx, play_action)
            if self.event_log:
                self.event_log.add(f"{self.contexts[actor_idx].label} → {_describe_play_action(play_action)}")

    async def _handle_round_end(self, winner_index: int) -> None:
        assert self.game_state is not None
        await self._dismiss_palette(self._active_palette)
        self._clear_pending()
        scores = rules.final_scores(self.game_state)
        summary = scoreboard.RoundSummary(
            round_number=self.round_number,
            winner_index=winner_index,
            scores=scores,
        )
        self.match_history.record(summary)
        if self.event_log:
            winner_label = self.contexts[winner_index].label
            self.event_log.add(f"[bold green]{winner_label} wins round {self.round_number}![/bold green]")
        if self.score_panel:
            self.score_panel.update_scores(self.match_history)

        self.awaiting_next_round = True
        self._set_status(
            "[green]Round complete.[/green] Press [bold]N[/bold] for the next round or [bold]Q[/bold] to quit."
        )

    async def _refresh_ui(self) -> None:
        if self.game_state is None:
            return

        public = _public_state(self.game_state)
        actor_idx = public.current_player_index
        reveal_players = set(range(self.humans))
        if self.reveal_enabled:
            reveal_players = set(range(self.players))

        player_stats = _player_statistics(self.game_state)
        self.player_stats = player_stats

        highlight_map = _highlight_cards(self.game_state, range(self.players))
        recommended = highlight_map.get(actor_idx, set())

        if self.table_panel:
            table_renderable = _render_table_summary(
                self.game_state,
                self.contexts,
                reveal_players,
                self.reveal_enabled,
                highlight_map,
                player_stats,
            )
            self.table_panel.update_panel("Table", table_renderable)

        if self.hand_panel:
            hand_renderable = _render_hand(self.game_state, actor_idx, recommended)
            self.hand_panel.update_panel("Your Hand", hand_renderable)

        if self.recommend_panel:
            recommend_renderable = _render_recommendations(self.game_state, actor_idx, recommended)
            self.recommend_panel.update_panel("Suggested Melds", recommend_renderable)

        if self.meld_panel:
            meld_renderable = _render_table_melds(self.game_state)
            self.meld_panel.update_panel("Table Melds", meld_renderable)

        if self.debug_panel:
            lines = (
                _debug_lines(self.search_config, self.game_state, self.last_search_stats)
                if self.debug_enabled
                else []
            )
            self.debug_panel.update_debug(lines)

        if self.score_panel:
            self.score_panel.update_scores(self.match_history)

        self.title = (
            f"Konkan • Round {self.round_number} • Turn {public.turn_index} • {self.contexts[actor_idx].label}"
        )

    async def _mount_palette(self, palette: ActionPalette, prompt: str) -> None:
        await self._dismiss_palette(self._active_palette)
        self._active_palette = palette
        if self.actions_container is not None:
            if self.action_prompt:
                header_text = Text.from_markup(f"[bold]{prompt}[/bold] — use arrows or number keys")
                self.action_prompt.update(header_text)
            existing = [child for child in self.actions_container.children if isinstance(child, ActionPalette)]
            for child in existing:
                await child.remove()
            await self.actions_container.mount(palette)
            palette.focus()

    @on(ActionPalette.Choice)
    def _on_palette_choice(self, message: ActionPalette.Choice) -> None:
        message.stop()
        if self._pending_kind is None or self._pending_actions is None or self._pending_actor is None:
            return
        if message.index < 0 or message.index >= len(self._pending_actions):
            return
        if self._pending_kind == "draw":
            self.run_worker(self._handle_draw_choice(message.index), group="input", exclusive=True)
        elif self._pending_kind == "play":
            self.run_worker(self._handle_play_choice(message.index), group="input", exclusive=True)

    async def _dismiss_palette(self, palette: ActionPalette | None) -> None:
        if palette is None:
            return
        with suppress(Exception):  # pragma: no cover - defensive cleanup
            await palette.remove()
        if self.action_prompt:
            self.action_prompt.update(Text.from_markup("[dim]Waiting for turn…[/dim]"))
        if self._active_palette is palette:
            self._active_palette = None

    def _clear_pending(self) -> None:
        self._pending_kind = None
        self._pending_actor = None
        self._pending_actions = None

    async def _handle_draw_choice(self, index: int) -> None:
        if self.game_state is None:
            return
        if self._pending_kind != "draw" or self._pending_actions is None or self._pending_actor is None:
            return
        if not (0 <= index < len(self._pending_actions)):
            return
        draw_actions = list(self._pending_actions)
        actor_idx = self._pending_actor
        await self._dismiss_palette(self._active_palette)
        self._clear_pending()
        public = _public_state(self.game_state)
        top_before = public.trash_pile[-1] if public.trash_pile else None
        selected = draw_actions[index]
        if not isinstance(selected, actions.DrawAction):
            return
        actions.apply_draw_action(self.game_state, actor_idx, selected)
        if self.event_log:
            actor_label = self.contexts[actor_idx].label
            if selected.source == "trash" and top_before is not None:
                self.event_log.add(f"{actor_label} took {_format_card_highlight(top_before)} from trash")
            else:
                self.event_log.add(f"{actor_label} drew from the deck")
        await self._refresh_ui()
        await self._process_turn()

    async def _handle_play_choice(self, index: int) -> None:
        if self.game_state is None:
            return
        if self._pending_kind != "play" or self._pending_actions is None or self._pending_actor is None:
            return
        if not (0 <= index < len(self._pending_actions)):
            return
        play_actions = list(self._pending_actions)
        actor_idx = self._pending_actor
        await self._dismiss_palette(self._active_palette)
        self._clear_pending()
        chosen = play_actions[index]
        if not isinstance(chosen, actions.PlayAction):
            return
        actions.apply_play_action(self.game_state, actor_idx, chosen)
        if self.event_log:
            self.event_log.add(f"{self.contexts[actor_idx].label} → {_describe_play_action(chosen)}")
        await self._refresh_ui()
        await self._process_turn()

    async def _prompt_simple_choice(
        self,
        prompt: str,
        entries: Sequence[str],
        description: str | None = None,
    ) -> int:
        palette = ActionPalette(prompt, entries)
        await self._dismiss_palette(self._active_palette)
        self._clear_pending()
        self._active_palette = palette
        if self.actions_container is not None:
            if self.action_prompt:
                message = f"[bold]{prompt}[/bold] — use arrows or number keys"
                if description:
                    message += f"\n[dim]{description}[/dim]"
                self.action_prompt.update(Text.from_markup(message))
            await self.actions_container.mount(palette)
            palette.focus()
        message = await self.wait_for_message(ActionPalette.Choice, sender=palette)
        choice_index = int(getattr(message, "index", 0))
        await self._dismiss_palette(palette)
        return choice_index

    async def _offer_come_down(self, actor_idx: int) -> bool:
        if self.game_state is None:
            return False
        summary = _cover_summary(self.game_state, actor_idx)
        if summary is None:
            return False
        melds_list = summary.get("melds")
        details_text = ""
        if isinstance(melds_list, list):
            details_text = "\n".join(str(item) for item in melds_list if item)
        choice = await self._prompt_simple_choice(
            "Come down?",
            [
                "Keep building (skip coming down)",
                f"Come down — {summary['points']} pts across {summary['meld_count']} melds",
            ],
            description=details_text,
        )
        if choice != 1:
            return False

        before = len(self.game_state.table)
        rules.lay_down(self.game_state, actor_idx)
        new_melds = self.game_state.table[before:]
        if self.event_log:
            label = self.contexts[actor_idx].label
            points = summary["points"]
            self.event_log.add(f"{label} comes down for {points} pts")
            for meld in new_melds:
                kind = "Set" if meld.kind == rules.SET_KIND else "Run"
                cards = " ".join(format_card(card) for card in meld.cards)
                self.event_log.add(f"  {kind}: {cards}")
        return True

    def _set_status(self, message: str) -> None:
        if self.status_strip:
            self.status_strip.message = message


def _draw_entries(options: Sequence[actions.DrawAction], public: PublicState) -> list[str]:
    entries: list[str] = []
    top = public.trash_pile[-1] if public.trash_pile else None
    for action in options:
        if action.source == "deck":
            entries.append("Draw from deck")
        else:
            label = "Take trash"
            if top is not None:
                label += f" ({format_card(top)})"
            entries.append(label)
    return entries


def _describe_play_action(action: actions.PlayAction) -> str:
    parts: list[str] = []
    if action.lay_down:
        parts.append("[bold green]Come down[/bold green]")
    for target, card_id in action.sarf_moves:
        parts.append(f"Sarf {format_card(card_id)} → meld {target}")
    parts.append(f"Discard {format_card(action.discard)}")
    return " • ".join(parts)


def _format_card_highlight(card_id: int) -> str:
    return f"[bright_green]{format_card(card_id)}[/bright_green]"


def _render_table_summary(
    game_state: state.KonkanState,
    contexts: Sequence[PlayerContext],
    reveal_players: Iterable[int],
    reveal_enabled: bool,
    highlight_map: Mapping[int, set[int]],
    player_stats: Mapping[int, dict[str, object]],
):
    public = _public_state(game_state)
    threshold = max(81, public.highest_table_points + 1 if public.highest_table_points else 81)
    actor_idx = public.current_player_index

    show_set = set(reveal_players)
    player_panels: list[Panel] = []
    for idx, player_state in enumerate(game_state.players):
        ctx = contexts[idx]
        phase = player_state.phase.value.replace("_", " ").title()
        cards = encoding.cards_from_mask(player_state.hand_mask)
        highlight_cards = highlight_map.get(idx, set())
        border_style = "bright_green" if idx == actor_idx else ("cyan" if ctx.role == "Human" else "magenta")
        title = f"{ctx.label} • {ctx.role}"

        info_table = Table.grid(padding=(0, 0), expand=True)
        info_table.add_column(justify="left")
        stats = player_stats.get(idx, {})
        info_table.add_row(Text.from_markup(f"[dim]Phase:[/] {phase}"))
        info_table.add_row(Text.from_markup(f"[dim]Cards:[/] {len(cards)}"))
        deadwood = stats.get("deadwood", 0)
        laid_points = stats.get("laid_points", 0)
        if idx in show_set:
            info_table.add_row(Text.from_markup(f"[dim]Deadwood:[/] {deadwood}"))
            info_table.add_row(Text.from_markup(f"[dim]Laid:[/] {laid_points}"))
            cover_points = stats.get("cover_points", 0)
            covered = stats.get("covered_cards", 0)
            info_table.add_row(
                Text.from_markup(f"[dim]Cover:[/] {cover_points} pts / {covered} cards")
            )
            info_table.add_row(
                Text.from_markup(
                    f"[dim]Melds:[/] {stats.get('run_count', 0)} runs • {stats.get('set_count', 0)} sets"
                )
            )
        else:
            info_table.add_row(Text.from_markup("[dim]Deadwood:[/] —"))
            info_table.add_row(Text.from_markup(f"[dim]Laid:[/] {laid_points}"))
            info_table.add_row(Text.from_markup("[dim]Cover:[/] —"))
            info_table.add_row(Text.from_markup("[dim]Melds:[/] —"))

        if idx in show_set:
            body = _render_card_grid(cards, highlight_cards, columns=min(6, len(cards)))
            panel_body: RenderableType = Group(info_table, body) if cards else info_table
        else:
            hidden_text = Text.from_markup(
                f"[dim]{len(cards)} card(s) hidden[/dim]" if cards else "[dim]Empty hand[/dim]"
            )
            panel_body = Group(info_table, hidden_text)

        if idx != actor_idx or len(game_state.players) == 1:
            player_panels.append(
                Panel(
                    panel_body,
                    title=title,
                    border_style=border_style,
                    padding=(0, 1),
                )
            )

    header = Text.from_markup(
        f"[cyan]Deck[/cyan]: {len(public.draw_pile)}  •  "
        f"[magenta]Trash[/magenta]: {len(public.trash_pile)}  •  "
        f"Threshold: {threshold}  •  Dealer: P{public.dealer_index}"
        + ("  •  [yellow]Reveal ON[/yellow]" if reveal_enabled else "")
    )
    if not player_panels:
        player_panels.append(Panel(Text.from_markup("[dim]No opponent hands[/dim]"), border_style="cyan"))
    columns = Columns(player_panels, expand=True, equal=True, column_first=True, padding=(0, 0))
    return Group(header, columns)


_SUIT_ORDER = {"H": 0, "D": 1, "C": 2, "S": 3}


def _sorted_cards(cards: Sequence[int], highlight: set[int]) -> list[int]:
    def key(card_id: int) -> tuple[int, int, int, int]:
        decoded = encoding.decode_id(card_id)
        if decoded.is_joker:
            return (len(_SUIT_ORDER), len(encoding.RANKS), 2, card_id)
        suit_code = encoding.SUITS[decoded.suit_idx]
        suit_order = _SUIT_ORDER.get(suit_code, len(_SUIT_ORDER))
        rank_order = decoded.rank_idx if decoded.rank_idx >= 0 else len(encoding.RANKS)
        duplicate = decoded.copy if decoded.copy >= 0 else 0
        return (suit_order, rank_order, duplicate, card_id)

    return sorted(cards, key=key)


def _render_hand(game_state: state.KonkanState, player_index: int, highlight: set[int]):
    player = game_state.players[player_index]
    cards = encoding.cards_from_mask(player.hand_mask)
    ordered = _sorted_cards(cards, highlight)
    if not ordered:
        return Text.from_markup("[dim]Empty hand[/dim]")
    grid = _render_card_grid(ordered, highlight, columns=min(10, len(ordered)))
    return grid


def _render_card_grid(cards: Sequence[int], highlight: set[int], *, columns: int = 7) -> RenderableType:
    if not cards:
        return Text.from_markup("[dim]No cards[/dim]")

    columns = max(1, columns)
    grid = Table.grid(expand=True, padding=(0, 0))
    grid.add_column(justify="left")

    for start in range(0, len(cards), columns):
        row_cards = cards[start : start + columns]
        parts: list[str] = []
        for card_id in row_cards:
            label = format_card(card_id)
            if card_id in highlight:
                label = f"[bold bright_green]{label}[/bold bright_green]"
            parts.append(label)
        grid.add_row("  ".join(parts))

    return grid


def _render_recommendations(game_state: state.KonkanState, player_index: int, highlight: set[int]):
    if not highlight:
        return Text.from_markup("[dim]No qualifying meld cover yet[/dim]")
    threshold = _target_threshold(game_state)
    mask_hi, mask_lo = encoding.split_mask(game_state.players[player_index].hand_mask)
    cover = melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)
    rows: list[str] = []
    for meld_entry in getattr(cover, "melds", []):
        meld_mask = encoding.combine_mask(int(getattr(meld_entry, "mask_hi", 0)), int(getattr(meld_entry, "mask_lo", 0)))
        cards = encoding.cards_from_mask(meld_mask)
        labels = " ".join(_format_card_highlight(card) if card in highlight else format_card(card) for card in cards)
        kind = "Set" if int(getattr(meld_entry, "kind", 0)) == 0 else "Run"
        rows.append(f"[bold]{kind}[/bold] ({int(getattr(meld_entry, 'points', 0))} pts): {labels}")
    if not rows:
        return Text.from_markup("[dim]Highlight derived from solver fallback[/dim]")
    grid = Table.grid(padding=(0, 1))
    grid.add_column(justify="left")
    for line in rows:
        grid.add_row(Text.from_markup(line))
    return grid


def _player_statistics(game_state: state.KonkanState) -> dict[int, dict[str, object]]:
    stats: dict[int, dict[str, object]] = {}
    threshold = _target_threshold(game_state)
    for idx, player in enumerate(game_state.players):
        hand_mask = player.hand_mask
        deadwood = encoding.points_from_mask(hand_mask)
        laid_points = getattr(player, "laid_points", 0)
        cover_points = 0
        covered_cards = 0
        set_count = 0
        run_count = 0
        mask_hi, mask_lo = encoding.split_mask(hand_mask)
        try:
            cover = melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)
        except Exception:
            cover = None
        if cover is not None:
            cover_points = int(getattr(cover, "total_points", 0))
            covered_cards = int(getattr(cover, "covered_cards", 0))
            for entry in getattr(cover, "melds", []):
                kind = int(getattr(entry, "kind", 1))
                if kind == 0:
                    set_count += 1
                else:
                    run_count += 1
        stats[idx] = {
            "deadwood": deadwood,
            "laid_points": laid_points,
            "cover_points": cover_points,
            "covered_cards": covered_cards,
            "set_count": set_count,
            "run_count": run_count,
        }
    return stats


def _cover_summary(game_state: state.KonkanState, player_index: int) -> dict[str, object] | None:
    threshold = _target_threshold(game_state)
    mask_hi, mask_lo = encoding.split_mask(game_state.players[player_index].hand_mask)
    try:
        cover = melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)
    except Exception:
        return None
    total_points = int(getattr(cover, "total_points", 0))
    if total_points < threshold:
        return None
    meld_details: list[str] = []
    for entry in getattr(cover, "melds", []):
        combined = encoding.combine_mask(
            int(getattr(entry, "mask_hi", 0)),
            int(getattr(entry, "mask_lo", 0)),
        )
        cards = " ".join(format_card(card) for card in encoding.cards_from_mask(combined))
        kind = "Set" if int(getattr(entry, "kind", 1)) == 0 else "Run"
        meld_details.append(f"{kind}: {cards}")
    return {
        "points": total_points,
        "meld_count": len(meld_details),
        "melds": meld_details,
    }


def _render_table_melds(game_state: state.KonkanState):
    if not game_state.table:
        return Text.from_markup("[dim]No melds on the table[/dim]")
    table = Table(box=box.SIMPLE, expand=True)
    table.add_column("Owner", justify="left")
    table.add_column("Kind", justify="center")
    table.add_column("Cards", justify="left")
    table.add_column("Notes", justify="left")
    for meld_entry in game_state.table:
        owner = f"P{meld_entry.owner}"
        kind = "Set" if meld_entry.kind == 0 else "Run"
        cards = " ".join(format_card(card) for card in meld_entry.cards)
        notes: list[str] = []
        if meld_entry.has_joker:
            notes.append("Joker")
        if meld_entry.is_four_set:
            notes.append("Sealed")
        table.add_row(owner, kind, cards, ", ".join(notes) if notes else "")
    return table


def _highlight_cards(game_state: state.KonkanState, players: Iterable[int]) -> dict[int, set[int]]:
    highlights: dict[int, set[int]] = {}
    threshold = _target_threshold(game_state)
    for idx in players:
        if idx < 0 or idx >= len(game_state.players):
            continue
        player_state = game_state.players[idx]
        mask_hi, mask_lo = encoding.split_mask(player_state.hand_mask)
        try:
            cover = melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)
        except Exception:
            continue
        highlight_cards: set[int] = set()
        for entry in getattr(cover, "melds", []):
            combined = encoding.combine_mask(int(getattr(entry, "mask_hi", 0)), int(getattr(entry, "mask_lo", 0)))
            highlight_cards.update(encoding.cards_from_mask(combined))
        if highlight_cards:
            highlights[idx] = highlight_cards
    return highlights


def _target_threshold(game_state: state.KonkanState) -> int:
    base = 81
    public = _public_state(game_state)
    if public.highest_table_points > 0:
        base = max(base, public.highest_table_points + 1)
    return base


def _summarise_search_node(node: Node) -> dict[str, Any]:
    total_sims = int(sum(node.visits))
    summaries: list[dict[str, Any]] = []
    for idx, action in enumerate(node.actions):
        if not isinstance(action, actions.PlayAction):
            continue
        visits = int(node.visits[idx]) if idx < len(node.visits) else 0
        prior = float(node.priors[idx]) if idx < len(node.priors) else 0.0
        mean_value = 0.0
        if visits and idx < len(node.total_value):
            mean_value = node.total_value[idx] / visits
        summaries.append(
            {
                "desc": _describe_play_action(action),
                "visits": visits,
                "prior": prior,
                "value": mean_value,
            }
        )
    summaries.sort(key=lambda entry: int(entry["visits"]), reverse=True)
    return {
        "total_sims": total_sims,
        "candidate_count": len(summaries),
        "candidates": summaries,
    }


def _debug_lines(
    config: SearchConfig,
    game_state: state.KonkanState,
    search_stats: dict[str, object] | None,
) -> list[str]:
    public = _public_state(game_state)
    lines = [
        f"Simulations: {config.simulations}",
        f"Dirichlet α: {config.dirichlet_alpha or 0:.2f} • weight {config.dirichlet_weight:.2f}",
        f"Current player: P{public.current_player_index}",
        f"Highest table points: {public.highest_table_points}",
        f"Deck size: {len(public.draw_pile)}",
        f"Trash size: {len(public.trash_pile)}",
    ]
    if config.opponent_model is not None:
        lines.append("Opponent priors: enabled")
    if search_stats:
        lines.append("[bold]Last search[/bold]:")
        total = search_stats.get("total_sims", 0)
        lines.append(f" sims={total} candidates={search_stats.get('candidate_count', 0)}")
        candidates_obj = search_stats.get("candidates", [])
        if isinstance(candidates_obj, list):
            for entry in candidates_obj[:3]:
                if not isinstance(entry, dict):
                    continue
                desc = entry.get("desc", "?")
                visits = int(entry.get("visits", 0))
                value = float(entry.get("value", 0.0))
                prior = float(entry.get("prior", 0.0))
                lines.append(f"  {visits:>3}v {value:>5.2f} val {prior:>4.2f} p • {desc}")
    return lines


def _assign_dealer(game_state: state.KonkanState, dealer_index: int) -> int:
    public = _public_state(game_state)
    if not public.draw_pile:
        raise RuntimeError("draw pile exhausted before dealer assignment")
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


def _choose_ai_draw_action(game_state: state.KonkanState, actor_idx: int) -> actions.DrawAction:
    options = actions.legal_draw_actions(game_state, actor_idx)
    for option in options:
        if option.source == "trash":
            return option
    return options[0]


def _choose_ai_play_action(
    game_state: state.KonkanState,
    actor_idx: int,
    rng: random.Random,
    search_config: SearchConfig,
) -> tuple[actions.PlayAction, dict[str, object]]:
    node = run_search(game_state, rng, search_config)
    diagnostics = _summarise_search_node(node)
    candidates = list(node.actions)
    if candidates and candidates[0] is not None:
        index = node.best_action_index()
        chosen = candidates[index]
        if isinstance(chosen, actions.PlayAction):
            return chosen, diagnostics

    hand_cards = encoding.cards_from_mask(game_state.players[actor_idx].hand_mask)
    fallback = hand_cards[0]
    play_options = actions.legal_play_actions(game_state, actor_idx, max_discards=len(hand_cards))
    for option in play_options:
        if option.discard == fallback:
            return option, diagnostics
    return play_options[0], diagnostics


def _MAX_DISCARD_CHOICES(game_state: state.KonkanState, actor_idx: int) -> int:
    cards = encoding.cards_from_mask(game_state.players[actor_idx].hand_mask)
    return max(8, min(12, len(cards)))


def run_textual_app(
    *,
    players: int,
    humans: int,
    seed: int | None,
    simulations: int,
    dirichlet_alpha: float | None,
    dirichlet_weight: float,
    opponent_priors: bool,
    debug: bool,
) -> None:
    """Launch the Textual UI."""

    app = KonkanTextualApp(
        players=players,
        humans=humans,
        seed=seed,
        simulations=simulations,
        dirichlet_alpha=dirichlet_alpha,
        dirichlet_weight=dirichlet_weight,
        opponent_priors=opponent_priors,
        start_debug=debug,
    )
    app.run()
