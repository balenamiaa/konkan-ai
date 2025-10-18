"""Composable view primitives for the Konkan CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence, Set

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .. import encoding
from ..state import KonkanState, PublicState


@dataclass(slots=True)
class StateSummaryView:
    """Renderable summarising the current table state."""

    state: KonkanState
    roles: Sequence[str]
    reveal_players: Set[int]
    card_formatter: Callable[[int], str]

    def _hand_markup(self, cards: list[int], visible: bool) -> str:
        if not visible:
            return f"{len(cards)} cards"
        if not cards:
            return "—"
        return " ".join(self.card_formatter(card) for card in cards)

    def _metadata_panel(self, public: PublicState, threshold: int) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_row(f"[cyan]Turn[/cyan]: {public.turn_index}")
        grid.add_row(f"[cyan]Deck[/cyan]: {len(public.draw_pile)} card(s)")
        if public.trash_pile:
            top_card = self.card_formatter(public.trash_pile[-1])
            grid.add_row(f"[cyan]Trash[/cyan]: {top_card} ({len(public.trash_pile)} card(s))")
        else:
            grid.add_row("[cyan]Trash[/cyan]: —")
        grid.add_row(f"[cyan]Threshold[/cyan]: {threshold}")
        return Panel(grid, title="Table State", box=box.SQUARE, border_style="blue")

    def render(self) -> RenderableType:
        public = self.state.public
        if not isinstance(public, PublicState):  # pragma: no cover - defensive guard
            return Text("State unavailable", style="red")

        table = Table(box=box.ROUNDED, expand=True)
        table.add_column("Player", justify="left", style="bold")
        table.add_column("Role", justify="left")
        table.add_column("Hand", justify="left")
        table.add_column("Laid", justify="left")
        table.add_column("Status", justify="left")
        table.add_column("Phase", justify="left")

        winner_index = public.winner_index
        threshold = 81
        if self.state.config is not None:
            threshold = self.state.config.come_down_points
        if public.highest_table_points > 0:
            threshold = max(threshold, public.highest_table_points + 1)

        for idx, player in enumerate(self.state.players):
            role = self.roles[idx] if idx < len(self.roles) else "AI"
            hand_cards = encoding.cards_from_mask(player.hand_mask)
            laid_cards = encoding.cards_from_mask(player.laid_mask)
            visible = idx in self.reveal_players
            hand_display = self._hand_markup(hand_cards, visible)
            laid_display = self._hand_markup(laid_cards, True)

            status_text = "Down" if player.has_come_down else "Up"
            if winner_index == idx:
                status_text = "[bold green]Winner[/bold green]"
            phase_text = player.phase.value.replace("_", " ").title()

            name = f"P{idx}"
            if idx == public.current_player_index:
                name = f"[bold yellow]{name}[/bold yellow]"

            table.add_row(name, role, hand_display, laid_display, status_text, phase_text)

        meta = self._metadata_panel(public, threshold)

        components: list[RenderableType] = [table, meta]

        if self.state.table:
            meld_table = Table(box=box.MINIMAL, expand=True)
            meld_table.add_column("Meld", justify="left", style="bold")
            meld_table.add_column("Owner", justify="left")
            meld_table.add_column("Kind", justify="left")
            meld_table.add_column("Cards", justify="left")
            meld_table.add_column("Notes", justify="left")

            for idx, meld in enumerate(self.state.table):
                owner = f"P{meld.owner}"
                kind_label = "Set" if meld.kind == 0 else "Run"
                cards_display = " ".join(self.card_formatter(card) for card in meld.cards)
                notes = []
                if meld.has_joker:
                    notes.append("Joker")
                if meld.is_four_set:
                    notes.append("Sealed")
                meld_table.add_row(f"M{idx}", owner, kind_label, cards_display, ", ".join(notes))

            components.append(Panel(meld_table, title="Table Melds", box=box.SQUARE, border_style="green"))

        return Group(*components)
