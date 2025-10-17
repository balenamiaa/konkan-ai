<<<<<<< HEAD
"""Card identifier encoding utilities for Konkan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Tuple

RANKS: Final[list[str]] = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS: Final[list[str]] = ["S", "H", "D", "C"]
RANK_TO_IDX: Final[dict[str, int]] = {rank: idx for idx, rank in enumerate(RANKS)}
SUIT_TO_IDX: Final[dict[str, int]] = {suit: idx for idx, suit in enumerate(SUITS)}
IDX_TO_RANK: Final[dict[int, str]] = {idx: rank for rank, idx in RANK_TO_IDX.items()}
IDX_TO_SUIT: Final[dict[int, str]] = {idx: suit for suit, idx in SUIT_TO_IDX.items()}
JOKER_IDS: Final[tuple[int, int]] = (104, 105)
POINTS: Final[list[int]] = [10] + list(range(2, 10)) + [10, 10, 10]


@dataclass(frozen=True, slots=True)
class CardDecoding:
    """Typed container describing a decoded card identifier."""

    is_joker: bool
    rank_idx: int
    suit_idx: int
    copy: int


def card_id(rank_idx: int, suit_idx: int, copy: int) -> int:
    """Encode a rank, suit, and copy index into a card identifier."""

    if copy not in (0, 1):
        raise ValueError("copy must be 0 or 1")
    base = suit_idx * 13 + rank_idx
    return base + copy * 52


def decode_id(card_identifier: int) -> CardDecoding:
    """Decode a card identifier into its properties."""

    if card_identifier in JOKER_IDS:
        return CardDecoding(True, -1, -1, -1)
    copy = 1 if card_identifier >= 52 else 0
    base = card_identifier - copy * 52
    suit_idx = base // 13
    rank_idx = base % 13
    return CardDecoding(False, rank_idx, suit_idx, copy)


def card_points(card_identifier: int, represented_rank_idx: int | None = None) -> int:
    """Return the point value associated with a card identifier."""

    if card_identifier in JOKER_IDS:
        if represented_rank_idx is None:
            raise ValueError("Joker requires represented_rank_idx for scoring")
        return POINTS[represented_rank_idx]
    decoded = decode_id(card_identifier)
    return POINTS[decoded.rank_idx]


def bit_for(card_identifier: int) -> tuple[int, int]:
    """Return the bitset representation (hi, lo) for the provided identifier."""

    if card_identifier < 64:
        return 0, 1 << card_identifier
    return 1 << (card_identifier - 64), 0
=======
"""Low-level card encodings and bitmask helpers for Konkan."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, List, Sequence

# Core deck definitions -----------------------------------------------------

SUITS: Sequence[str] = ("clubs", "diamonds", "hearts", "spades")
SUIT_SYMBOLS: Sequence[str] = ("♣", "♦", "♥", "♠")
RANKS: Sequence[str] = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")

NUM_DECKS = 2
COPIES_PER_STANDARD_CARD = NUM_DECKS
JOKERS_PER_DECK = 2

STANDARD_CARDS_PER_DECK = len(SUITS) * len(RANKS)
TOTAL_STANDARD_CARDS = STANDARD_CARDS_PER_DECK * NUM_DECKS
TOTAL_JOKERS = NUM_DECKS * JOKERS_PER_DECK
TOTAL_CARDS = TOTAL_STANDARD_CARDS + TOTAL_JOKERS

# Joker variants retain ordering so CLI/debug views remain stable.
JOKER_VARIANTS: Sequence[str] = ("black", "red")

RANK_POINTS = {
    "A": 10,
    "K": 10,
    "Q": 10,
    "J": 10,
    "10": 10,
    "9": 9,
    "8": 8,
    "7": 7,
    "6": 6,
    "5": 5,
    "4": 4,
    "3": 3,
    "2": 2,
}

PRINTED_JOKER_POINTS = 0

CardId = int
Mask = int


@dataclass(frozen=True)
class EncodedCard:
    """Metadata for a low-level card identifier."""

    card_id: CardId
    suit_index: int | None
    rank_index: int | None
    copy_index: int
    joker_variant: int | None

    @property
    def is_joker(self) -> bool:
        return self.joker_variant is not None

    @property
    def rank(self) -> str:
        if self.rank_index is None:
            return "J"
        return RANKS[self.rank_index]

    @property
    def suit(self) -> str:
        if self.suit_index is None:
            return "joker"
        return SUITS[self.suit_index]

    @property
    def suit_symbol(self) -> str:
        if self.suit_index is None:
            return "🃏"
        return SUIT_SYMBOLS[self.suit_index]

    @property
    def code(self) -> str:
        if self.is_joker:
            return f"JOKER-{JOKER_VARIANTS[self.joker_variant]}#{self.copy_index}"
        return f"{RANKS[self.rank_index]}{SUIT_SYMBOLS[self.suit_index]}#{self.copy_index}"


# Encoding helpers ----------------------------------------------------------

def _validate_copy_index(copy_index: int) -> None:
    if not 0 <= copy_index < NUM_DECKS:
        raise ValueError(f"copy_index must be within [0, {NUM_DECKS}), got {copy_index}")


def _validate_joker_variant(variant: int) -> None:
    if not 0 <= variant < JOKER_VARIANTS.__len__():
        raise ValueError(f"joker variant must be within [0, {len(JOKER_VARIANTS)}), got {variant}")


def encode_standard_card(suit_index: int, rank_index: int, copy_index: int) -> CardId:
    """Return a dense integer identifier for the requested card."""
    if not 0 <= suit_index < len(SUITS):
        raise ValueError("invalid suit index")
    if not 0 <= rank_index < len(RANKS):
        raise ValueError("invalid rank index")
    _validate_copy_index(copy_index)
    return copy_index * STANDARD_CARDS_PER_DECK + suit_index * len(RANKS) + rank_index


def encode_joker(copy_index: int, variant: int) -> CardId:
    """Return the identifier for a printed joker."""
    _validate_copy_index(copy_index)
    _validate_joker_variant(variant)
    return TOTAL_STANDARD_CARDS + copy_index * JOKERS_PER_DECK + variant


def decode_card(card_id: CardId) -> EncodedCard:
    """Recover the structured view for an encoded card id."""
    if not 0 <= card_id < TOTAL_CARDS:
        raise ValueError(f"card identifier {card_id} outside legal range")
    if card_id >= TOTAL_STANDARD_CARDS:
        joker_offset = card_id - TOTAL_STANDARD_CARDS
        copy_index, variant = divmod(joker_offset, JOKERS_PER_DECK)
        return EncodedCard(card_id, None, None, copy_index, variant)

    copy_index, within_deck = divmod(card_id, STANDARD_CARDS_PER_DECK)
    suit_index, rank_index = divmod(within_deck, len(RANKS))
    return EncodedCard(card_id, suit_index, rank_index, copy_index, None)


# Bitmask helpers -----------------------------------------------------------

def empty_mask() -> Mask:
    return 0


def card_bit(card_id: CardId) -> Mask:
    return 1 << card_id


def mask_from_cards(cards: Iterable[CardId]) -> Mask:
    mask = 0
    for card_id in cards:
        mask |= card_bit(card_id)
    return mask


def mask_without(mask: Mask, cards: Iterable[CardId]) -> Mask:
    for card_id in cards:
        mask &= ~card_bit(card_id)
    return mask


def iter_cards(mask: Mask) -> Iterator[CardId]:
    while mask:
        low_bit = mask & -mask
        card_id = low_bit.bit_length() - 1
        yield card_id
        mask &= mask - 1


def popcount(mask: Mask) -> int:
    return mask.bit_count()


def has_card(mask: Mask, card_id: CardId) -> bool:
    return bool(mask & card_bit(card_id))


def add_card(mask: Mask, card_id: CardId) -> Mask:
    return mask | card_bit(card_id)


def remove_card(mask: Mask, card_id: CardId) -> Mask:
    return mask & ~card_bit(card_id)


# Point helpers -------------------------------------------------------------

def point_value(card_id: CardId) -> int:
    encoded = decode_card(card_id)
    if encoded.is_joker:
        return PRINTED_JOKER_POINTS
    return RANK_POINTS[RANKS[encoded.rank_index]]


def points_for_mask(mask: Mask) -> int:
    total = 0
    for card_id in iter_cards(mask):
        total += point_value(card_id)
    return total


def describe_cards(card_ids: Iterable[CardId]) -> List[str]:
    return [decode_card(card_id).code for card_id in card_ids]
>>>>>>> main
