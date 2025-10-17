<<<<<<< HEAD
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
=======
"""Temporary debug CLI for the Konkan prototype."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .. import rules, state
from . import render

STATE_PATH = Path(".konkan_state.json")


def _load_state(path: Path) -> state.KonkanState:
    if not path.exists():
        raise SystemExit("no saved state found; run `konkan-cli deal` first")
    payload = json.loads(path.read_text())
    return state.deserialize_state(payload)


def _save_state(path: Path, game_state: state.KonkanState) -> None:
    payload = state.serialize_state(game_state)
    path.write_text(json.dumps(payload, indent=2))


def cmd_deal(args: argparse.Namespace) -> None:
    config = state.KonkanConfig(
        num_players=args.players,
        hand_size=args.hand_size,
        come_down_points=args.come_down,
        allow_trash_first_turn=args.allow_trash_first_turn,
        recycle_shuffle_seed=args.recycle_seed,
        dealer_index=args.dealer,
    )
    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    game_state = rules.start_game(config, rng)
    _save_state(args.state, game_state)
    print(render.render_state(game_state))


def cmd_status(args: argparse.Namespace) -> None:
    game_state = _load_state(args.state)
    print(render.render_state(game_state))


def cmd_draw(args: argparse.Namespace) -> None:
    game_state = _load_state(args.state)
    if args.source == "stock":
        rules.draw_from_stock(game_state, args.player, random.Random(args.seed) if args.seed is not None else None)
    else:
        rules.draw_from_trash(game_state, args.player)
    _save_state(args.state, game_state)
    print(render.render_state(game_state))


def cmd_trash(args: argparse.Namespace) -> None:
    game_state = _load_state(args.state)
    rules.trash_card(game_state, args.player, args.card)
    _save_state(args.state, game_state)
    print(render.render_state(game_state))


def cmd_come_down(args: argparse.Namespace) -> None:
    game_state = _load_state(args.state)
    solution = rules.lay_down(game_state, args.player)
    _save_state(args.state, game_state)
    print("Melds:", solution.melds)
    print(render.render_state(game_state))


def cmd_swap(args: argparse.Namespace) -> None:
    game_state = _load_state(args.state)
    # Debug command: replacement card is provided as a raw integer identifier so the
    # CLI can stay decoupled from eventual UI assets.
    rules.perform_joker_swap(game_state, args.actor, args.target, args.card)
    _save_state(args.state, game_state)
    print(render.render_state(game_state))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="konkan-cli", description="Konkan debug harness")
    parser.add_argument("--state", type=Path, default=STATE_PATH, help="Path to the serialized debug state")
    sub = parser.add_subparsers(dest="command", required=True)

    deal = sub.add_parser("deal", help="Start a new game")
    deal.add_argument("--players", type=int, default=2)
    deal.add_argument("--hand-size", dest="hand_size", type=int, default=13)
    deal.add_argument("--come-down", dest="come_down", type=int, default=51)
    deal.add_argument("--allow-trash-first-turn", action="store_true")
    deal.add_argument("--recycle-seed", dest="recycle_seed", type=int, default=None)
    deal.add_argument("--dealer", type=int, default=0)
    deal.add_argument("--seed", type=int, default=None)
    deal.set_defaults(func=cmd_deal)

    status = sub.add_parser("status", help="Show the current state")
    status.set_defaults(func=cmd_status)

    draw = sub.add_parser("draw", help="Draw a card for a player")
    draw.add_argument("player", type=int)
    draw.add_argument("source", choices=["stock", "trash"])
    draw.add_argument("--seed", type=int, default=None)
    draw.set_defaults(func=cmd_draw)

    trash = sub.add_parser("trash", help="Discard a card from the active player")
    trash.add_argument("player", type=int)
    trash.add_argument("card", type=int, help="Raw card identifier")
    trash.set_defaults(func=cmd_trash)

    come_down = sub.add_parser("come-down", help="Force the player to lay their melds")
    come_down.add_argument("player", type=int)
    come_down.set_defaults(func=cmd_come_down)

    swap = sub.add_parser("swap", help="Perform a printed joker swap")
    swap.add_argument("actor", type=int)
    swap.add_argument("target", type=int)
    swap.add_argument("card", type=int)
    swap.set_defaults(func=cmd_swap)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
>>>>>>> main
    main()
