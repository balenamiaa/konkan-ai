"""Card abstractions and helpers for Konkan."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Suit(str, Enum):
    """Enumeration of the four suits in a Konkan deck."""

    SPADES = "S"
    HEARTS = "H"
    DIAMONDS = "D"
    CLUBS = "C"


class Rank(str, Enum):
    """Enumeration of ranks ordered according to Konkan rules."""

    ACE = "A"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"

    @classmethod
    def ordered(cls) -> tuple["Rank", ...]:
        """Return ranks in rule order for scoring and run validation."""

        return (
            cls.ACE,
            cls.TWO,
            cls.THREE,
            cls.FOUR,
            cls.FIVE,
            cls.SIX,
            cls.SEVEN,
            cls.EIGHT,
            cls.NINE,
            cls.TEN,
            cls.JACK,
            cls.QUEEN,
            cls.KING,
        )


@dataclass(frozen=True, slots=True)
class Card:
    """Value object describing a physical Konkan card."""

    rank: Rank | None
    suit: Suit | None
    copy: int

    @property
    def is_joker(self) -> bool:
        """Return ``True`` when the card represents a Joker."""

        return self.rank is None and self.suit is None

    def label(self) -> str:
        """Create a display label suitable for CLI representations."""

        if self.is_joker:
            return "🃏"
        return f"{self.rank.value}{self.suit.value}"


def iter_full_deck() -> Iterable[Card]:
    """Yield all physical cards in a fresh Konkan deck."""

    for copy in (0, 1):
        for suit in Suit:
            for rank in Rank.ordered():
                yield Card(rank=rank, suit=suit, copy=copy)
    yield Card(rank=None, suit=None, copy=0)
    yield Card(rank=None, suit=None, copy=1)
