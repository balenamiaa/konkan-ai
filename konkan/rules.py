"""Rule utilities and constants for Konkan."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

__all__ = [
    "TurnPhase",
    "Thresholds",
    "DealPattern",
    "DEFAULT_THRESHOLDS",
    "DEFAULT_DEAL_PATTERN",
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
