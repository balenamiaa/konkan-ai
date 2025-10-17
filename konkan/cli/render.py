<<<<<<< HEAD
"""Rendering helpers dedicated to the CLI experience."""

from __future__ import annotations

from rich.console import RenderableType

from ..state import KonkanState
from .views import StateSummaryView


def render_state_stub(state: KonkanState) -> RenderableType:
    """Return a renderable summarizing the current placeholder state."""

    return StateSummaryView(state).render()
=======
"""Utilities for rendering the temporary debug CLI."""
from __future__ import annotations

from typing import List

from .. import cards, encoding, state


def format_mask(mask: encoding.Mask) -> str:
    card_objs = list(cards.iter_cards(mask))
    if not card_objs:
        return "(empty)"
    return " ".join(card.code for card in cards.sort_by_rank(card_objs))


def render_player(player: state.PlayerState, index: int) -> str:
    lines: List[str] = []
    lines.append(f"Player {index} :: phase={player.phase.value} :: hand={format_mask(player.hand_mask)}")
    if player.has_come_down:
        lines.append(f"  laid={format_mask(player.laid_mask)} :: melds={player.melds}")
    if player.last_trash is not None:
        lines.append(f"  last trash: {cards.Card(player.last_trash).code}")
    if player.pending_sarf:
        lines.append("  sarf: armed")
    return "\n".join(lines)


def render_public(public: state.PublicState) -> str:
    draw_size = len(public.draw_pile)
    trash = "(empty)" if not public.trash_pile else cards.Card(public.trash_pile[-1]).code
    winner = "none" if public.winner_index is None else str(public.winner_index)
    return (
        f"turn={public.turn_index} dealer={public.dealer_index} draw={draw_size}"
        f" trash_top={trash} winner={winner} recycle_pending={public.pending_recycle}"
    )


def render_state(game_state: state.KonkanState) -> str:
    lines: List[str] = ["== PUBLIC ==", render_public(game_state.public), "== PLAYERS =="]
    for index, player in enumerate(game_state.players):
        lines.append(render_player(player, index))
    return "\n".join(lines)
>>>>>>> main
