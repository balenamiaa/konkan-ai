<<<<<<< HEAD
"""Rule utilities and constants for Konkan."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable, Final, Sequence

from ._compat import np
from . import melds

if TYPE_CHECKING:
    from .state import KonkanState, PlayerPublic

__all__ = [
    "TurnPhase",
    "Thresholds",
    "DealPattern",
    "DEFAULT_THRESHOLDS",
    "DEFAULT_DEAL_PATTERN",
    "effective_threshold",
    "someone_is_down",
    "can_draw_from_trash",
    "requires_opening_discard",
    "can_finish_via_sarf",
]


class TurnPhase(str, Enum):
    """High-level turn phases used by the rules engine."""

    DRAW = "draw"
    PLAY = "play"
    DISCARD = "discard"


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Threshold values that regulate coming down to the table."""

    base: int = 81

    def next_for(self, highest_table_points: int) -> int:
        """Return the next required threshold given current table state."""

        if highest_table_points <= 0:
            return self.base
        return highest_table_points + 1


@dataclass(frozen=True, slots=True)
class DealPattern:
    """Initial hand sizes for the opening deal."""

    first_player_cards: int = 15
    other_player_cards: int = 14

    def hand_size_for(self, player_index: int) -> int:
        """Return the number of cards dealt to the given player index."""

        return self.first_player_cards if player_index == 0 else self.other_player_cards


DEFAULT_THRESHOLDS: Final[Thresholds] = Thresholds()
DEFAULT_DEAL_PATTERN: Final[DealPattern] = DealPattern()


def someone_is_down(public: Sequence["PlayerPublic"]) -> bool:
    """Return ``True`` when at least one player has already come down."""

    return any(player.came_down for player in public)


def effective_threshold(
    public: Sequence["PlayerPublic"],
    highest_table_points: int,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> int:
    """Compute the active points threshold for coming down."""

    if someone_is_down(public):
        return thresholds.next_for(highest_table_points)
    return thresholds.base


def _mask_with_card(mask_hi: np.uint64, mask_lo: np.uint64, card_identifier: int) -> tuple[int, int]:
    """Return masks updated to include ``card_identifier``."""

    if card_identifier < 64:
        mask_lo |= np.uint64(1) << np.uint64(card_identifier)
    else:
        mask_hi |= np.uint64(1) << np.uint64(card_identifier - 64)
    return int(mask_hi), int(mask_lo)


def can_draw_from_trash(
    *,
    trash: Sequence[int],
    hand_mask: tuple[np.uint64, np.uint64],
    player_public: "PlayerPublic",
    public_state: Sequence["PlayerPublic"],
    highest_table_points: int,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    cover_to_threshold: Callable[[int, int, int], melds.CoverResultProtocol] = melds.best_cover_to_threshold,
) -> bool:
    """Determine whether the player may take the top trash card this turn."""

    if not trash:
        return False
    if player_public.came_down:
        return True

    threshold = effective_threshold(public_state, highest_table_points, thresholds)
    mask_hi, mask_lo = hand_mask
    updated_hi, updated_lo = _mask_with_card(mask_hi, mask_lo, trash[-1])
    cover = cover_to_threshold(updated_hi, updated_lo, threshold)
    return cover.total_points >= threshold


def requires_opening_discard(state: "KonkanState") -> bool:
    """Return ``True`` if the opening player must still make their forced discard."""

    return (
        state.turn_index == 0
        and state.player_to_act == 0
        and not state.first_player_has_discarded
        and state.phase == TurnPhase.DISCARD
    )


def can_finish_via_sarf(hand_card_count: int, player_public: "PlayerPublic") -> bool:
    """Return whether the player may legally finish the round via sarf-only play."""

    return player_public.came_down and hand_card_count <= 2
=======
"""Core turn logic for the Konkan prototype rules engine."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass

from . import cards, encoding, melds, state


class RuleViolation(RuntimeError):
    """Base class for illegal game transitions."""


class IllegalDraw(RuleViolation):
    pass


class IllegalTrash(RuleViolation):
    pass


class IllegalSwap(RuleViolation):
    pass


@dataclass
class DrawResult:
    card_id: encoding.CardId
    from_trash: bool


def _rng(seed: int | None) -> random.Random:
    return random.Random(seed) if seed is not None else random.Random()


def start_game(config: state.KonkanConfig, rng: random.Random | None = None) -> state.KonkanState:
    """Shuffle a fresh deck and deal a new game."""
    rng = rng or _rng(None)
    deck = cards.full_deck()
    rng.shuffle(deck)
    # NOTE: The blueprint assumes two physical decks with printed jokers; ``full_deck``
    # mirrors that layout exactly so downstream systems can rely on deterministic ids.
    return state.deal_new_game(config, deck)


def recycle_discard_pile(game_state: state.KonkanState, rng: random.Random | None = None) -> None:
    """Move all but the latest trash card back into the draw pile and shuffle."""
    if len(game_state.public.trash_pile) <= 1:
        raise IllegalDraw("cannot recycle draw pile without at least two cards in trash")
    rng = rng or _rng(game_state.config.recycle_shuffle_seed)
    top_card = game_state.public.trash_pile.pop()
    recycle_cards = game_state.public.trash_pile
    rng.shuffle(recycle_cards)
    game_state.public.draw_pile = recycle_cards + game_state.public.draw_pile
    game_state.public.trash_pile = [top_card]
    game_state.public.pending_recycle = False


def _ensure_can_draw(game_state: state.KonkanState, player_index: int) -> state.PlayerState:
    player = game_state.players[player_index]
    if player.phase is not state.TurnPhase.AWAITING_DRAW:
        raise IllegalDraw("player must be awaiting draw")
    if game_state.public.turn_index != player_index:
        raise IllegalDraw("not this player's turn")
    return player


def can_draw_from_trash(game_state: state.KonkanState, player_index: int) -> bool:
    top_card = game_state.public.top_trash()
    if top_card is None:
        return False
    player = game_state.players[player_index]
    if player.phase is not state.TurnPhase.AWAITING_DRAW:
        return False
    if player.last_trash == top_card:
        # Assumption: players cannot reclaim the card they just released without
        # another player intervening.
        return False
    if not game_state.config.allow_trash_first_turn and not player.has_come_down and player.last_trash is None:
        # First action of the game uses stock draw to keep tempo balanced.
        return False
    return True


def draw_from_trash(game_state: state.KonkanState, player_index: int) -> DrawResult:
    player = _ensure_can_draw(game_state, player_index)
    if not can_draw_from_trash(game_state, player_index):
        raise IllegalDraw("trash card not eligible")
    card_id = game_state.public.trash_pile.pop()
    player.hand_mask = encoding.add_card(player.hand_mask, card_id)
    player.phase = state.TurnPhase.AWAITING_TRASH
    player.pending_sarf = encoding.decode_card(card_id).is_joker
    return DrawResult(card_id=card_id, from_trash=True)


def draw_from_stock(game_state: state.KonkanState, player_index: int, rng: random.Random | None = None) -> DrawResult:
    player = _ensure_can_draw(game_state, player_index)
    game_state.public.pending_recycle = False
    if not game_state.public.draw_pile:
        if len(game_state.public.trash_pile) <= 1:
            raise IllegalDraw("stock empty and trash too small to recycle")
        recycle_discard_pile(game_state, rng)
        game_state.public.pending_recycle = True
    card_id = game_state.public.draw_pile.pop()
    player.hand_mask = encoding.add_card(player.hand_mask, card_id)
    player.phase = state.TurnPhase.AWAITING_TRASH
    player.pending_sarf = encoding.decode_card(card_id).is_joker
    return DrawResult(card_id=card_id, from_trash=False)


def _advance_turn(game_state: state.KonkanState) -> None:
    game_state.public.turn_index = (game_state.public.turn_index + 1) % len(game_state.players)
    for index, player in enumerate(game_state.players):
        player.phase = state.TurnPhase.AWAITING_DRAW if index == game_state.public.turn_index else state.TurnPhase.COMPLETE


def trash_card(game_state: state.KonkanState, player_index: int, card_id: int) -> None:
    player = game_state.players[player_index]
    if player.phase is not state.TurnPhase.AWAITING_TRASH:
        raise IllegalTrash("player must draw before trashing")
    if not encoding.has_card(player.hand_mask, card_id):
        raise IllegalTrash("player does not hold selected card")
    player.hand_mask = encoding.remove_card(player.hand_mask, card_id)
    player.last_trash = card_id
    player.phase = state.TurnPhase.COMPLETE
    game_state.public.trash_pile.append(card_id)
    player.pending_sarf = False
    if player.has_come_down and encoding.popcount(player.hand_mask) == 0:
        game_state.public.winner_index = player_index
    _advance_turn(game_state)


def can_player_come_down(game_state: state.KonkanState, player_index: int) -> bool:
    player = game_state.players[player_index]
    if player.has_come_down:
        return False
    solution = melds.solve_for_laydown(player.hand_mask)
    return solution.points >= game_state.config.come_down_points


def lay_down(game_state: state.KonkanState, player_index: int) -> melds.MeldSolution:
    if not can_player_come_down(game_state, player_index):
        raise RuleViolation("player does not meet come-down threshold")
    player = game_state.players[player_index]
    solution = melds.solve_for_laydown(player.hand_mask)
    player.has_come_down = True
    player.laid_mask = solution.used_mask
    player.melds = [tuple(meld) for meld in solution.melds]
    player.hand_mask = solution.deadwood_mask
    player.pending_sarf = False
    return solution


def perform_joker_swap(
    game_state: state.KonkanState,
    actor_index: int,
    target_index: int,
    replacement_card_id: int,
) -> None:
    """Swap a printed joker from another player's meld."""
    actor = game_state.players[actor_index]
    target = game_state.players[target_index]
    if actor_index == target_index:
        raise IllegalSwap("actor cannot target themselves")
    if not actor.pending_sarf:
        raise IllegalSwap("actor is not in joker swap mode")
    if not encoding.has_card(actor.hand_mask, replacement_card_id):
        raise IllegalSwap("replacement card not in actor hand")
    if not target.has_come_down:
        raise IllegalSwap("target has not laid down melds yet")
    joker_cards = [card_id for card_id in encoding.iter_cards(target.laid_mask) if encoding.decode_card(card_id).is_joker]
    if not joker_cards:
        raise IllegalSwap("target melds do not expose a printed joker")
    joker_card = joker_cards[0]
    target.laid_mask = encoding.remove_card(target.laid_mask, joker_card)
    target.laid_mask = encoding.add_card(target.laid_mask, replacement_card_id)
    actor.hand_mask = encoding.remove_card(actor.hand_mask, replacement_card_id)
    actor.hand_mask = encoding.add_card(actor.hand_mask, joker_card)
    actor.pending_sarf = False
    # TODO: once the meld solver knows about joker locations, update structural metadata instead of performing a linear scan.
    _relabel_melds(target, joker_card, replacement_card_id)


def _relabel_melds(target: state.PlayerState, joker_card: int, replacement_card: int) -> None:
    new_melds = []
    for meld_cards in target.melds:
        meld_list = list(meld_cards)
        for index, card_id in enumerate(meld_list):
            if card_id == joker_card:
                meld_list[index] = replacement_card
                break
        new_melds.append(tuple(meld_list))
    target.melds = new_melds


def to_json(game_state: state.KonkanState) -> str:
    return json.dumps(state.serialize_state(game_state), indent=2)
>>>>>>> main
