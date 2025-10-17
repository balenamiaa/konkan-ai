"""Composable view primitives for the Konkan CLI."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from ..state import KonkanState


@dataclass(slots=True)
class StateSummaryView:
    """Minimalist view summarizing the current state."""

    state: KonkanState

    def render(self) -> RenderableType:
        """Return a textual summary placeholder."""

        text = Text("Konkan engine scaffolding is in place.")
        text.stylize("bold cyan")
        return text
