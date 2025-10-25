"""Legal action generation utilities for Konkan gameplay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from . import encoding, rules
from .evaluation import analyze_hand, CardMetrics
from .rules import IllegalTrash
from .state import KonkanState, PublicState, TurnPhase
from .threats import discard_feeds_next_player_sarf

MAX_DISCARD_CHOICES = 16


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


def _rank_discard_candidates(
    cards: List[int],
    *,
    state: KonkanState | None = None,
    player_index: int | None = None,
    metrics_by_card: dict[int, CardMetrics] | None = None,
    demand_samples: int = 1,
) -> list[int]:
    """Return discard candidates sorted by a heuristic preference."""

    if metrics_by_card is None and state is not None and player_index is not None:
        try:
            metrics_by_card = analyze_hand(state, player_index, demand_samples=demand_samples)
        except Exception:  # pragma: no cover - protect against solver failures
            metrics_by_card = None

    def score(card_id: int) -> tuple[float, int]:
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
        heuristic = float(points)
        heuristic -= same_rank * 1.5
        heuristic -= same_suit_neighbors * 3.0

        if metrics_by_card is not None and card_id in metrics_by_card:
            heuristic -= metrics_by_card[card_id].keep_value()

        if state is not None and player_index is not None:
            try:
                feeds_next = discard_feeds_next_player_sarf(state, player_index, card_id)
            except Exception:  # pragma: no cover - safety net
                feeds_next = False
            if feeds_next:
                heuristic -= 1000
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

    hand_metrics = None
    try:
        hand_metrics = analyze_hand(state, player_index, demand_samples=1)
    except Exception:  # pragma: no cover - analysis is best-effort
        hand_metrics = None

    ranked_cards_all = _rank_discard_candidates(
        candidate_cards,
        state=state,
        player_index=player_index,
        metrics_by_card=hand_metrics,
        demand_samples=1,
    )
    ranked_cards = ranked_cards_all[:max_discards]
    candidate_actions: list[PlayAction] = [PlayAction(discard=card_id) for card_id in ranked_cards]

    if rules.can_player_come_down(state, player_index):
        laydown_actions_added = 0
        for card_id in ranked_cards_all:
            candidate = _build_laydown_action(state, player_index, card_id)
            if candidate is not None:
                candidate_actions.append(candidate)
                laydown_actions_added += 1
            if laydown_actions_added >= max_discards:
                break

    player = state.players[player_index]
    if player.has_come_down and state.table:
        sarf_candidates: set[tuple[int, int, int]] = set()
        for meld_index, _meld in enumerate(state.table):
            for card_id in candidate_cards:
                if rules.can_sarf_card(state, player_index, meld_index, card_id):
                    remaining = [card for card in candidate_cards if card != card_id]
                    if not remaining:
                        continue
                    ranked_remaining = _rank_discard_candidates(
                        remaining,
                        state=state,
                        player_index=player_index,
                        metrics_by_card=hand_metrics,
                        demand_samples=1,
                    )
                    discard_card = ranked_remaining[0] if ranked_remaining else remaining[0]
                    key = (meld_index, card_id, discard_card)
                    if key in sarf_candidates:
                        continue
                    candidate = PlayAction(
                        discard=discard_card,
                        sarf_moves=((meld_index, card_id),),
                    )
                    if not _is_valid_play_action(state, player_index, candidate):
                        continue
                    sarf_candidates.add(key)
                    candidate_actions.append(candidate)
                    if len(sarf_candidates) >= max_discards:
                        break
            if len(candidate_actions) >= max_discards * 2:
                break

    actions: list[PlayAction] = []
    for action in candidate_actions:
        if _is_valid_play_action(state, player_index, action):
            actions.append(action)
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
        try:
            rules.lay_down(state, player_index, reserve_card=action.discard)
        except TypeError:
            # Backwards compatibility with patched call sites lacking the keyword.
            rules.lay_down(state, player_index)
    for target_index, card_id in action.sarf_moves:
        rules.sarf_card(state, player_index, target_index, card_id)
    rules.trash_card(state, player_index, action.discard)


def _is_valid_play_action(state: KonkanState, player_index: int, action: PlayAction) -> bool:
    """Return True if applying ``action`` succeeds without rule violations."""

    clone = state.clone_shallow()
    try:
        if action.lay_down:
            try:
                rules.lay_down(clone, player_index, reserve_card=action.discard)
            except TypeError:
                rules.lay_down(clone, player_index)
        for target_index, card_id in action.sarf_moves:
            rules.sarf_card(clone, player_index, target_index, card_id)
        rules.trash_card(clone, player_index, action.discard)
    except (IllegalTrash, RuntimeError, ValueError):
        return False
    return True


def _build_laydown_action(state: KonkanState, player_index: int, discard_candidate: int) -> PlayAction | None:
    """Return a lay-down action that retains a discard card if possible."""

    clone = state.clone_shallow()
    try:
        rules.lay_down(clone, player_index, reserve_card=discard_candidate)
    except TypeError:
        rules.lay_down(clone, player_index)
    except RuntimeError:
        return None

    remaining_mask = clone.players[player_index].hand_mask
    remaining_cards = encoding.cards_from_mask(remaining_mask)
    if not remaining_cards:
        return None

    discard = discard_candidate
    if not encoding.has_card(remaining_mask, discard_candidate):
        try:
            metrics = analyze_hand(clone, player_index, demand_samples=1)
        except Exception:
            metrics = None
        ranked_remaining = _rank_discard_candidates(
            remaining_cards,
            state=clone,
            player_index=player_index,
            metrics_by_card=metrics,
            demand_samples=1,
        )
        discard = ranked_remaining[0] if ranked_remaining else remaining_cards[0]

    action = PlayAction(discard=discard, lay_down=True)
    if not _is_valid_play_action(state, player_index, action):
        return None
    return action
