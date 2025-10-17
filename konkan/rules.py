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
