"""Rendering helpers dedicated to the CLI experience."""

from __future__ import annotations

from rich.console import RenderableType

from ..state import KonkanState
from .views import StateSummaryView


def render_state_stub(state: KonkanState) -> RenderableType:
    """Return a renderable summarizing the current placeholder state."""

    return StateSummaryView(state).render()
