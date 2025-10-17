"""Rule utilities and constants for Konkan."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TurnPhase(str, Enum):
    """High-level turn phases used by the rules engine."""

    DRAW = "draw"
    PLAY = "play"
    DISCARD = "discard"


@dataclass(slots=True)
class Thresholds:
    """Threshold values that regulate coming down to the table."""

    base: int = 81

    def next_for(self, highest_table_points: int) -> int:
        """Return the next required threshold given current table state."""

        if highest_table_points <= 0:
            return self.base
        return highest_table_points + 1
