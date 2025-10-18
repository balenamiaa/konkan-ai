"""Determinization utilities for information-set MCTS."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, cast

from . import encoding
from .state import KonkanState, PublicState


@dataclass(slots=True)
class DeterminizationConfig:
    """Configuration values for determinization sampling."""

    seed: int
    max_samples: int = 1


def sample_world(state: KonkanState, rng: Any, *, actor_index: int | None = None) -> KonkanState:
    """Return a determinized world by shuffling hidden zones.

    When ``actor_index`` is provided, the returned state preserves that player's
    hand while reassigning all hidden zones from the perspective of the actor.
    """

    shuffled = state.clone_shallow()
    public = shuffled.public
    if not isinstance(public, PublicState):
        return shuffled

    shuffle_fn: Callable[[list[int]], None]
    if hasattr(rng, "shuffle") and callable(rng.shuffle):
        shuffle_fn = cast(Callable[[list[int]], None], rng.shuffle)
    else:  # pragma: no cover - fallback for generic RNGs
        random_source = random.Random(getattr(rng, "random", None) or None)

        def _shuffle(seq: list[int]) -> None:
            random_source.shuffle(seq)

        shuffle_fn = _shuffle

    if actor_index is None:
        actor_index = public.current_player_index
    available_cards: list[int] = []

    for idx, player in enumerate(shuffled.players):
        hand_cards = encoding.cards_from_mask(player.hand_mask)
        if idx != actor_index:
            available_cards.extend(hand_cards)

    available_cards.extend(public.draw_pile)
    shuffle_fn(available_cards)

    draw_length = len(public.draw_pile)

    for idx, player in enumerate(shuffled.players):
        if idx == actor_index:
            continue
        hand_size = len(encoding.cards_from_mask(player.hand_mask))
        if hand_size == 0:
            continue
        if hand_size > len(available_cards):  # pragma: no cover - defensive guard
            raise RuntimeError("insufficient cards to reassign opponent hand")
        new_cards = [available_cards.pop() for _ in range(hand_size)]
        player.hand_mask = encoding.mask_from_cards(new_cards)

    if draw_length > len(available_cards):  # pragma: no cover - defensive guard
        raise RuntimeError("not enough cards remaining to form draw pile")

    new_draw = available_cards[:draw_length]
    public.draw_pile = list(new_draw)

    return shuffled
