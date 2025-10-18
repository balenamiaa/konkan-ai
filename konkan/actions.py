"""Legal action generation utilities for Konkan gameplay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from . import encoding, rules
from .state import KonkanState, PublicState, TurnPhase

MAX_DISCARD_CHOICES = 5


@dataclass(frozen=True)
class DrawAction:
    """Action describing how a player draws a card."""

    source: str  # "deck" or "trash"


@dataclass(frozen=True)
class PlayAction:
    """Action describing optional table operations and the discard."""

    discard: int
    lay_down: bool = False
    sarf_moves: tuple[tuple[int, int], ...] = ()


def legal_draw_actions(state: KonkanState, player_index: int) -> list[DrawAction]:
    """Return draw actions available to ``player_index``."""

    player = state.players[player_index]
    if player.phase != TurnPhase.AWAITING_DRAW:
        return []

    public = state.public
    if not isinstance(public, PublicState):
        return []

    actions: list[DrawAction] = []
    if public.draw_pile:
        actions.append(DrawAction(source="deck"))
    if rules.can_draw_from_trash(state, player_index):
        actions.append(DrawAction(source="trash"))
    return actions


def _rank_discard_candidates(cards: List[int]) -> list[int]:
    """Return discard candidates sorted by a heuristic preference."""

    def score(card_id: int) -> tuple[int, int]:
        decoded = encoding.decode_id(card_id)
        if decoded.is_joker:
            return (-5, card_id)
        points = encoding.card_points(card_id)
        same_rank = sum(
            1 for c in cards if c != card_id and encoding.decode_id(c).rank_idx == decoded.rank_idx
        )
        same_suit_neighbors = 0
        for delta in (-1, 1):
            neighbor_rank = decoded.rank_idx + delta
            if 0 <= neighbor_rank < len(encoding.RANKS):
                for other in cards:
                    if other == card_id:
                        continue
                    info = encoding.decode_id(other)
                    if info.suit_idx == decoded.suit_idx and info.rank_idx == neighbor_rank:
                        same_suit_neighbors += 1
                        break
        heuristic = points
        heuristic -= same_rank * 3
        heuristic -= same_suit_neighbors * 2
        return heuristic, card_id

    sorted_cards = sorted(cards, key=score, reverse=True)
    return sorted_cards


def legal_play_actions(
    state: KonkanState,
    player_index: int,
    *,
    max_discards: int = MAX_DISCARD_CHOICES,
) -> list[PlayAction]:
    """Return discard-phase actions available to ``player_index``."""

    player = state.players[player_index]
    if player.phase != TurnPhase.AWAITING_TRASH:
        return []

    candidate_cards = encoding.cards_from_mask(player.hand_mask)
    if not candidate_cards:
        return []

    ranked_cards = _rank_discard_candidates(candidate_cards)[:max_discards]
    actions: list[PlayAction] = [PlayAction(discard=card_id) for card_id in ranked_cards]

    if rules.can_player_come_down(state, player_index):
        actions.extend(PlayAction(discard=card_id, lay_down=True) for card_id in ranked_cards)

    player = state.players[player_index]
    if player.has_come_down and state.table:
        sarf_candidates: set[tuple[int, int, int]] = set()
        for meld_index, _meld in enumerate(state.table):
            for card_id in candidate_cards:
                if rules.can_sarf_card(state, player_index, meld_index, card_id):
                    remaining = [card for card in candidate_cards if card != card_id]
                    if not remaining:
                        continue
                    ranked_remaining = _rank_discard_candidates(remaining)
                    discard_card = ranked_remaining[0] if ranked_remaining else remaining[0]
                    key = (meld_index, card_id, discard_card)
                    if key in sarf_candidates:
                        continue
                    sarf_candidates.add(key)
                    actions.append(
                        PlayAction(
                            discard=discard_card,
                            sarf_moves=((meld_index, card_id),),
                        )
                    )
                    if len(sarf_candidates) >= max_discards:
                        break
            if len(actions) >= max_discards * 2:
                break

    return actions


def apply_draw_action(state: KonkanState, player_index: int, action: DrawAction) -> None:
    """Apply the provided draw action using the rules engine."""

    if action.source == "trash":
        rules.draw_from_trash(state, player_index)
    elif action.source == "deck":
        rules.draw_from_stock(state, player_index)
    else:  # pragma: no cover - defensive branch
        raise ValueError(f"Unknown draw source {action.source}")


def apply_play_action(state: KonkanState, player_index: int, action: PlayAction) -> None:
    """Apply the provided play action using the rules engine."""

    if action.lay_down:
        rules.lay_down(state, player_index)
    for target_index, card_id in action.sarf_moves:
        rules.sarf_card(state, player_index, target_index, card_id)
    rules.trash_card(state, player_index, action.discard)
