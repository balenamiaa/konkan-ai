"""Rule utilities and constants for Konkan."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Final, Iterable, Sequence, cast

from . import encoding, melds

SET_KIND = 0
RUN_KIND = 1

if TYPE_CHECKING:
    from .state import KonkanConfig, KonkanState, PlayerPublic, PlayerState, PublicState

__all__ = [
    "TurnPhase",
    "Thresholds",
    "DealPattern",
    "DEFAULT_THRESHOLDS",
    "DEFAULT_DEAL_PATTERN",
    "IllegalDraw",
    "IllegalTrash",
    "LayDownResult",
    "PlayerRoundScore",
    "effective_threshold",
    "someone_is_down",
    "can_draw_from_trash",
    "requires_opening_discard",
    "can_finish_via_sarf",
    "can_player_come_down",
    "lay_down",
    "draw_from_stock",
    "draw_from_trash",
    "trash_card",
    "sarf_card",
    "can_sarf_card",
    "final_scores",
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

class IllegalDraw(RuntimeError):
    """Raised when a player attempts to draw illegally."""


class IllegalTrash(RuntimeError):
    """Raised when a player attempts to trash illegally."""


@dataclass(slots=True)
class LayDownResult:
    """Result structure returned after a successful lay-down."""

    used_mask: int
    deadwood_mask: int


@dataclass(frozen=True, slots=True)
class PlayerRoundScore:
    """Per-player scoring breakdown captured at the end of a round."""

    player_index: int
    laid_points: int
    deadwood_points: int
    net_points: int
    won_round: bool


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


def _mask_with_card(mask_hi: int, mask_lo: int, card_identifier: int) -> tuple[int, int]:
    """Return masks updated to include ``card_identifier``."""

    if card_identifier < 64:
        mask_lo |= 1 << card_identifier
    else:
        mask_hi |= 1 << (card_identifier - 64)
    return mask_hi, mask_lo


def _can_draw_from_trash_kwargs(
    *,
    trash: Sequence[int],
    hand_mask: tuple[int, int],
    player_public: "PlayerPublic",
    public_state: Sequence["PlayerPublic"],
    highest_table_points: int,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    cover_to_threshold: Callable[
        [int, int, int], melds.CoverResultProtocol
    ] = melds.best_cover_to_threshold,
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


def _resolve_runtime_components(
    state: "KonkanState",
) -> tuple["KonkanConfig", Sequence["PlayerState"], "PublicState"]:
    """Return configuration, players, and public state for high-level helpers."""

    from . import state as state_module

    config = state.config
    if config is None:
        raise ValueError("KonkanState is missing configuration; use deal_new_game")
    if not state.players:
        raise ValueError("KonkanState is missing player data")
    public = state.public
    if not isinstance(public, state_module.PublicState):
        raise ValueError("KonkanState public state is not initialised for high-level play")
    if config.num_players != len(state.players):
        raise ValueError("configuration player count does not match player state list")
    return config, state.players, public


def can_draw_from_trash(*args, **kwargs) -> bool:
    """Determine whether a trash draw is legal.

    Maintains backwards compatibility with the keyword-oriented helper used in
    lower-level tests while also supporting the high-level ``KonkanState`` form.
    """

    if not args:
        return _can_draw_from_trash_kwargs(**kwargs)
    if len(args) != 2 or kwargs:
        raise TypeError("expected state and player index arguments")

    state, player_index = args
    from . import state as state_module

    if not isinstance(state, state_module.KonkanState):
        raise TypeError("first argument must be a KonkanState instance")

    try:
        config, players, public = _resolve_runtime_components(state)
    except ValueError:
        return False

    if player_index < 0 or player_index >= len(players):
        return False
    if public.winner_index is not None:
        return False
    if public.current_player_index != player_index:
        return False

    player = players[player_index]
    if player.phase != state_module.TurnPhase.AWAITING_DRAW:
        return False
    if public.last_trash_by == player_index:
        return False
    if not public.trash_pile:
        return False
    if not config.allow_trash_first_turn and public.turn_index == 0 and not player.has_come_down:
        return False
    if player.has_come_down:
        return True

    prospective_mask = encoding.add_card(player.hand_mask, public.trash_pile[-1])
    threshold = config.come_down_points
    if public.highest_table_points > 0:
        threshold = max(threshold, public.highest_table_points + 1)
    mask_hi, mask_lo = encoding.split_mask(prospective_mask)
    cover = melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)
    return cover.total_points >= threshold


def can_player_come_down(state: "KonkanState", player_index: int) -> bool:
    """Return ``True`` when the player satisfies the coming-down threshold."""

    try:
        config, players, public = _resolve_runtime_components(state)
    except ValueError:
        return False

    if player_index < 0 or player_index >= len(players):
        return False

    player = players[player_index]
    if player.has_come_down:
        return False

    threshold = config.come_down_points
    if public.highest_table_points > 0:
        threshold = max(threshold, public.highest_table_points + 1)
    mask_hi, mask_lo = encoding.split_mask(player.hand_mask)
    cover = melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)
    if cover.total_points >= threshold:
        return True
    return encoding.points_from_mask(player.hand_mask) >= threshold


def lay_down(state: "KonkanState", player_index: int) -> LayDownResult:
    """Mark the player as having come down and return the lay-down summary."""

    try:
        config, players, public = _resolve_runtime_components(state)
    except ValueError as exc:
        raise RuntimeError("cannot lay down without initialised table state") from exc

    if not can_player_come_down(state, player_index):
        raise RuntimeError("player does not meet the coming-down threshold")

    player = players[player_index]
    threshold = config.come_down_points
    if public.highest_table_points > 0:
        threshold = max(threshold, public.highest_table_points + 1)

    mask_hi, mask_lo = encoding.split_mask(player.hand_mask)
    cover = melds.best_cover_to_threshold(mask_hi, mask_lo, threshold)
    total_points = cover.total_points
    used_mask_int = 0
    if total_points >= threshold:
        for meld in cast(Iterable[Any], cover.melds):
            mask_hi = int(getattr(meld, "mask_hi", 0))
            mask_lo = int(getattr(meld, "mask_lo", 0))
            used_mask_int |= (mask_hi << 64) | mask_lo
    else:
        fallback_points = encoding.points_from_mask(player.hand_mask)
        if fallback_points < threshold:
            raise RuntimeError("player does not meet the coming-down threshold")
        used_mask_int = player.hand_mask
        total_points = fallback_points

    deadwood_mask = player.hand_mask & ~used_mask_int

    table_entries: list = []
    if total_points >= threshold and getattr(cover, "melds", None):
        for native_meld in cast(Iterable[Any], cover.melds):
            mask_hi_native = int(getattr(native_meld, "mask_hi", 0))
            mask_lo_native = int(getattr(native_meld, "mask_lo", 0))
            kind = int(getattr(native_meld, "kind", RUN_KIND))
            points = int(getattr(native_meld, "points", total_points))
            table_entries.append(
                _create_table_meld(
                    owner=player_index,
                    mask_hi=mask_hi_native,
                    mask_lo=mask_lo_native,
                    kind=kind,
                    points=points,
                )
            )
    elif used_mask_int:
        mask_hi_total, mask_lo_total = encoding.split_mask(used_mask_int)
        points = encoding.points_from_mask(used_mask_int)
        table_entries.append(
            _create_table_meld(
                owner=player_index,
                mask_hi=mask_hi_total,
                mask_lo=mask_lo_total,
                kind=RUN_KIND,
                points=points,
            )
        )

    player.has_come_down = True
    player.laid_mask |= used_mask_int
    player.hand_mask = deadwood_mask
    state.table.extend(table_entries)

    if total_points >= threshold and getattr(cover, "melds", None):
        laid_points_total = int(total_points)
    else:
        laid_points_total = encoding.points_from_mask(player.laid_mask)
    player.laid_points = laid_points_total

    laid_points = player.laid_points
    public.highest_table_points = max(public.highest_table_points, laid_points)

    return LayDownResult(used_mask=used_mask_int, deadwood_mask=deadwood_mask)


def draw_from_stock(state: "KonkanState", player_index: int) -> int:
    """Draw the next card from the stock (draw pile) for ``player_index``."""

    from . import state as state_module

    _, players, public = _resolve_runtime_components(state)
    if player_index < 0 or player_index >= len(players):
        raise IllegalDraw("invalid player index")
    if public.winner_index is not None:
        raise IllegalDraw("round already finished")
    if public.current_player_index != player_index:
        raise IllegalDraw("not this player's turn")

    player = players[player_index]
    if player.phase != state_module.TurnPhase.AWAITING_DRAW:
        raise IllegalDraw("player must be awaiting a draw")
    if not public.draw_pile:
        raise IllegalDraw("draw pile is empty")

    card_identifier = public.draw_pile.pop()
    player.hand_mask = encoding.add_card(player.hand_mask, card_identifier)
    player.phase = state_module.TurnPhase.AWAITING_TRASH
    player.last_action_was_trash = False
    return card_identifier


def draw_from_trash(state: "KonkanState", player_index: int) -> int:
    """Draw the top trash card for ``player_index``."""

    from . import state as state_module

    _config, players, public = _resolve_runtime_components(state)
    if player_index < 0 or player_index >= len(players):
        raise IllegalDraw("invalid player index")
    if public.winner_index is not None:
        raise IllegalDraw("round already finished")
    if public.current_player_index != player_index:
        raise IllegalDraw("not this player's turn")
    if not can_draw_from_trash(state, player_index):
        raise IllegalDraw("trash draw is not legal at this time")

    player = players[player_index]
    card_identifier = public.trash_pile.pop()
    player.hand_mask = encoding.add_card(player.hand_mask, card_identifier)
    player.phase = state_module.TurnPhase.AWAITING_TRASH
    player.last_action_was_trash = False
    public.last_trash_by = None
    return card_identifier


def trash_card(state: "KonkanState", player_index: int, card_identifier: int) -> None:
    """Discard ``card_identifier`` to the trash pile for ``player_index``."""

    from . import state as state_module

    config, players, public = _resolve_runtime_components(state)
    if player_index < 0 or player_index >= len(players):
        raise IllegalTrash("invalid player index")
    if public.winner_index is not None:
        raise IllegalTrash("round already finished")
    if public.current_player_index != player_index:
        raise IllegalTrash("not this player's turn to trash")

    player = players[player_index]
    if player.phase != state_module.TurnPhase.AWAITING_TRASH:
        raise IllegalTrash("player must draw before trashing")
    if not encoding.has_card(player.hand_mask, card_identifier):
        raise IllegalTrash("card not present in hand")

    player.hand_mask = encoding.remove_card(player.hand_mask, card_identifier)
    public.trash_pile.append(card_identifier)
    player.last_action_was_trash = True

    if player.hand_mask == 0 and player.has_come_down:
        public.winner_index = player_index
        player.phase = state_module.TurnPhase.COMPLETE
    else:
        player.phase = state_module.TurnPhase.AWAITING_DRAW

    public.last_trash_by = player_index
    public.turn_index += 1

    next_player = player_index
    if config.num_players > 0:
        next_player = (player_index + 1) % config.num_players

    public.current_player_index = next_player
    state.player_to_act = next_player
    state.turn_index = public.turn_index


def _hand_points(hand_mask: int) -> int:
    total = 0
    for card_id in encoding.cards_from_mask(hand_mask):
        decoded = encoding.decode_id(card_id)
        if decoded.is_joker:
            continue
        total += encoding.card_points(card_id)
    return total


def _create_table_meld(owner: int, mask_hi: int, mask_lo: int, kind: int, points: int):
    from . import state as state_module

    cards = encoding.cards_from_mask((mask_hi << 64) | mask_lo)
    has_joker = any(card in encoding.JOKER_IDS for card in cards)
    is_four_set = kind == SET_KIND and len(cards) == 4 and not has_joker
    return state_module.MeldOnTable(
        mask_hi=mask_hi,
        mask_lo=mask_lo,
        cards=cards,
        owner=owner,
        kind=kind,
        has_joker=has_joker,
        points=points,
        is_four_set=is_four_set,
    )


def _validate_meld(cards: list[int], expected_kind: int) -> bool:
    mask = encoding.mask_from_cards(cards)
    mask_hi, mask_lo = encoding.split_mask(mask)
    for candidate in melds.enumerate_melds(mask_hi, mask_lo):
        candidate_mask = (int(getattr(candidate, "mask_hi", 0)) << 64) | int(
            getattr(candidate, "mask_lo", 0)
        )
        if candidate_mask == mask and int(getattr(candidate, "kind", expected_kind)) == expected_kind:
            return True
    return False


def _assign_meld_cards(meld, cards: list[int]) -> None:
    mask = encoding.mask_from_cards(cards)
    mask_hi, mask_lo = encoding.split_mask(mask)
    meld.cards = list(cards)
    meld.mask_hi = mask_hi
    meld.mask_lo = mask_lo
    meld.has_joker = any(card in encoding.JOKER_IDS for card in cards)
    if cards:
        kind = meld.kind
        if kind == SET_KIND:
            base_rank = next(
                (encoding.decode_id(card).rank_idx for card in cards if card not in encoding.JOKER_IDS),
                None,
            )
            meld.points = len(cards) * (encoding.POINTS[base_rank] if base_rank is not None else 0)
        else:
            mask_hi_local, mask_lo_local = encoding.split_mask(mask)
            points = 0
            for candidate in melds.enumerate_melds(mask_hi_local, mask_lo_local):
                candidate_mask = (int(getattr(candidate, "mask_hi", 0)) << 64) | int(
                    getattr(candidate, "mask_lo", 0)
                )
                if candidate_mask == mask:
                    points = int(getattr(candidate, "points", 0))
                    break
            if points == 0:
                points = encoding.points_from_mask(mask)
            meld.points = points
    else:
        meld.points = 0
    meld.is_four_set = meld.kind == SET_KIND and len(cards) == 4 and not meld.has_joker


def final_scores(state: "KonkanState") -> list[PlayerRoundScore]:
    """Return post-round scoring breakdown for each player."""

    from . import state as state_module

    public = state.public
    if not isinstance(public, state_module.PublicState):
        raise ValueError("KonkanState public state is not initialised")
    if public.winner_index is None:
        raise ValueError("winner has not been determined")

    scores: list[PlayerRoundScore] = []
    for idx, player in enumerate(state.players):
        laid_points = int(getattr(player, "laid_points", 0))
        deadwood_points = _hand_points(player.hand_mask)
        won_round = idx == public.winner_index
        net_points = laid_points - deadwood_points
        scores.append(
            PlayerRoundScore(
                player_index=idx,
                laid_points=laid_points,
                deadwood_points=deadwood_points,
                net_points=net_points,
                won_round=won_round,
            )
        )
    return scores


def can_sarf_card(state: "KonkanState", player_index: int, target_meld_index: int, card_identifier: int) -> bool:
    """Return ``True`` if the player can legally sarf ``card_identifier`` onto the table."""

    clone = state.clone_shallow()
    try:
        sarf_card(clone, player_index, target_meld_index, card_identifier)
    except RuntimeError:
        return False
    return True


def sarf_card(
    state: "KonkanState",
    player_index: int,
    target_meld_index: int,
    card_identifier: int,
) -> None:
    """Add ``card_identifier`` to ``target_meld_index`` with Joker swap support."""

    _, players, public = _resolve_runtime_components(state)
    if public.winner_index is not None:
        raise RuntimeError("round already finished")
    if player_index < 0 or player_index >= len(players):
        raise RuntimeError("invalid player index")
    if target_meld_index < 0 or target_meld_index >= len(state.table):
        raise RuntimeError("invalid meld index")

    player = players[player_index]
    if not player.has_come_down:
        raise RuntimeError("player must come down before sarfing")
    if not encoding.has_card(player.hand_mask, card_identifier):
        raise RuntimeError("card not present in hand")

    meld = state.table[target_meld_index]
    if meld.is_four_set:
        raise RuntimeError("cannot modify sealed set")

    decoded = encoding.decode_id(card_identifier)
    if meld.kind == SET_KIND:
        if decoded.is_joker:
            raise RuntimeError("cannot sarf joker into set")
        base_ranks = [encoding.decode_id(card).rank_idx for card in meld.cards if card not in encoding.JOKER_IDS]
        if base_ranks and decoded.rank_idx not in base_ranks:
            raise RuntimeError("rank mismatch for set")
        existing_suits = {
            encoding.decode_id(card).suit_idx
            for card in meld.cards
            if card not in encoding.JOKER_IDS
        }
        if decoded.suit_idx in existing_suits:
            raise RuntimeError("duplicate suit not allowed in set")
    else:  # run
        base_suits = {
            encoding.decode_id(card).suit_idx
            for card in meld.cards
            if card not in encoding.JOKER_IDS
        }
        if base_suits and decoded.suit_idx not in base_suits:
            raise RuntimeError("suit mismatch for run")

    if decoded.is_joker:
        raise RuntimeError("cannot sarf joker without swap target")

    if any(card in encoding.JOKER_IDS for card in meld.cards):
        for index, table_card in enumerate(meld.cards):
            if table_card in encoding.JOKER_IDS:
                candidate_cards = list(meld.cards)
                candidate_cards[index] = card_identifier
                if _validate_meld(candidate_cards, meld.kind):
                    player.hand_mask = encoding.remove_card(player.hand_mask, card_identifier)
                    player.hand_mask = encoding.add_card(player.hand_mask, table_card)
                    _assign_meld_cards(meld, candidate_cards)
                    if not encoding.has_card(player.laid_mask, card_identifier):
                        player.laid_mask = encoding.add_card(player.laid_mask, card_identifier)
                        player.laid_points += encoding.card_points(card_identifier)
                    return

    candidate_cards = list(meld.cards) + [card_identifier]
    if not _validate_meld(candidate_cards, meld.kind):
        raise RuntimeError("card does not extend meld")

    player.hand_mask = encoding.remove_card(player.hand_mask, card_identifier)
    _assign_meld_cards(meld, candidate_cards)
    if not encoding.has_card(player.laid_mask, card_identifier):
        player.laid_mask = encoding.add_card(player.laid_mask, card_identifier)
        player.laid_points += encoding.card_points(card_identifier)
