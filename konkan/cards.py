<<<<<<< HEAD
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
=======
"""High-level card helpers and deck assembly utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, List, Sequence

from . import encoding


@dataclass(frozen=True)
class Card:
    """Convenience wrapper for the low-level card identifier."""

    id: encoding.CardId

    @classmethod
    def from_components(cls, suit: str, rank: str, copy_index: int) -> "Card":
        suit_index = encoding.SUITS.index(suit)
        rank_index = encoding.RANKS.index(rank)
        return cls(encoding.encode_standard_card(suit_index, rank_index, copy_index))

    @classmethod
    def joker(cls, copy_index: int, variant: str) -> "Card":
        variant_index = encoding.JOKER_VARIANTS.index(variant)
        return cls(encoding.encode_joker(copy_index, variant_index))

    @classmethod
    def from_code(cls, code: str) -> "Card":
        parts = code.split("#")
        if len(parts) != 2:
            raise ValueError(f"invalid card code '{code}'")
        face, copy_str = parts
        copy_index = int(copy_str)
        if face.startswith("JOKER-"):
            _, variant = face.split("-", maxsplit=1)
            return cls.joker(copy_index, variant)
        suit_symbol = face[-1]
        rank = face[:-1]
        suit_index = encoding.SUIT_SYMBOLS.index(suit_symbol)
        rank_index = encoding.RANKS.index(rank)
        return cls(encoding.encode_standard_card(suit_index, rank_index, copy_index))

    @property
    def meta(self) -> encoding.EncodedCard:
        return encoding.decode_card(self.id)

    @property
    def rank(self) -> str:
        return self.meta.rank

    @property
    def suit(self) -> str:
        return self.meta.suit

    @property
    def suit_symbol(self) -> str:
        return self.meta.suit_symbol

    @property
    def is_joker(self) -> bool:
        return self.meta.is_joker

    @property
    def point_value(self) -> int:
        return encoding.point_value(self.id)

    @property
    def code(self) -> str:
        return self.meta.code


def full_deck() -> List[int]:
    """Return a deterministic ordering of all cards."""
    cards: List[int] = []
    for copy_index in range(encoding.NUM_DECKS):
        for suit_index, _ in enumerate(encoding.SUITS):
            for rank_index, _ in enumerate(encoding.RANKS):
                cards.append(encoding.encode_standard_card(suit_index, rank_index, copy_index))
        for variant_index, _ in enumerate(encoding.JOKER_VARIANTS):
            cards.append(encoding.encode_joker(copy_index, variant_index))
    return cards


def iter_cards(mask: encoding.Mask) -> Iterator[Card]:
    for card_id in encoding.iter_cards(mask):
        yield Card(card_id)


def mask_from_codes(codes: Iterable[str]) -> encoding.Mask:
    return encoding.mask_from_cards(Card.from_code(code).id for code in codes)


def sort_by_rank(cards: Iterable[Card]) -> List[Card]:
    return sorted(cards, key=lambda c: (c.meta.suit_index or -1, c.meta.rank_index or -1, c.meta.copy_index))


def format_cards(cards: Sequence[Card]) -> str:
    return " ".join(card.code for card in cards)
>>>>>>> main
