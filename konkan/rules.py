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
