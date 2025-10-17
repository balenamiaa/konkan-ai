"""Typer entry-point wiring for the Konkan CLI."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from ..state import new_game_state
from .render import render_state_stub

app = typer.Typer(add_completion=False, rich_markup_mode="rich")
console = Console()


@app.command()
def play(seed: int = typer.Option(42, help="Random seed used for deterministic scaffolding.")) -> None:
    """Run a placeholder game loop showcasing the CLI structure."""

    state = new_game_state(num_players=3)
    panel = Panel(render_state_stub(state), title="Konkan (Scaffolding)")
    console.print(panel)


def main() -> None:
    """Entry-point for ``python -m konkan.cli``."""

    app()


if __name__ == "__main__":  # pragma: no cover - CLI invocation
    main()
