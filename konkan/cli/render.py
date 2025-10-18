"""Rendering helpers dedicated to the CLI experience."""

from __future__ import annotations

from typing import Iterable, Sequence

from rich.console import RenderableType
from rich.panel import Panel

from .. import encoding
from ..state import KonkanState
from .views import StateSummaryView

_SUIT_SYMBOLS = {
    "S": ("♠", "cyan"),
    "H": ("♥", "red"),
    "D": ("♦", "magenta"),
    "C": ("♣", "green"),
}


def format_card(card_id: int) -> str:
    """Return a Rich-rendered label for ``card_id``."""

    decoded = encoding.decode_id(card_id)
    if decoded.is_joker:
        return "[magenta]🃏[/magenta]"
    suit_code = encoding.SUITS[decoded.suit_idx]
    rank = encoding.RANKS[decoded.rank_idx]
    symbol, color = _SUIT_SYMBOLS.get(suit_code, (suit_code, "white"))
    suffix = "′" if decoded.copy == 1 else ""
    return f"[{color}]{rank}{symbol}{suffix}[/{color}]"


def render_state(
    state: KonkanState,
    roles: Sequence[str],
    *,
    reveal_players: Iterable[int] | None = None,
    title: str = "Konkan",
) -> RenderableType:
    """Return a Rich panel describing the current table state."""

    view = StateSummaryView(
        state=state,
        roles=roles,
        reveal_players=set(reveal_players or set()),
        card_formatter=format_card,
    )
    return Panel(view.render(), title=title, padding=(0, 1), border_style="cyan")
