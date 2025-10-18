"""Card identifier encoding utilities for Konkan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable, Iterator

RANKS: Final[list[str]] = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS: Final[list[str]] = ["S", "H", "D", "C"]
RANK_TO_IDX: Final[dict[str, int]] = {rank: idx for idx, rank in enumerate(RANKS)}
SUIT_TO_IDX: Final[dict[str, int]] = {suit: idx for idx, suit in enumerate(SUITS)}
IDX_TO_RANK: Final[dict[int, str]] = {idx: rank for rank, idx in RANK_TO_IDX.items()}
IDX_TO_SUIT: Final[dict[int, str]] = {idx: suit for suit, idx in SUIT_TO_IDX.items()}
JOKER_IDS: Final[tuple[int, int]] = (104, 105)
POINTS: Final[list[int]] = [10] + list(range(2, 10)) + [10, 10, 10, 10]
DECK_CARD_COUNT: Final[int] = 106


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
            return 0
        return POINTS[represented_rank_idx]
    decoded = decode_id(card_identifier)
    return POINTS[decoded.rank_idx]


def bit_for(card_identifier: int) -> tuple[int, int]:
    """Return the bitset representation (hi, lo) for the provided identifier."""

    if card_identifier < 64:
        return 0, 1 << card_identifier
    return 1 << (card_identifier - 64), 0


def encode_standard_card(suit_idx: int, rank_idx: int, copy_idx: int) -> int:
    """Encode a standard (non-joker) card into an identifier."""

    if not 0 <= suit_idx < len(SUITS):
        raise ValueError("suit_idx out of range")
    if not 0 <= rank_idx < len(RANKS):
        raise ValueError("rank_idx out of range")
    return card_id(rank_idx, suit_idx, copy_idx)


def _validate_card_identifier(card_identifier: int) -> None:
    if card_identifier < 0 or card_identifier >= DECK_CARD_COUNT:
        raise ValueError(f"card identifier {card_identifier} out of range")


def mask_from_cards(cards: Iterable[int]) -> int:
    """Return a bit-mask representing the provided card identifiers."""

    mask = 0
    for card_identifier in cards:
        _validate_card_identifier(card_identifier)
        mask |= 1 << card_identifier
    return mask


def add_card(mask: int, card_identifier: int) -> int:
    """Return ``mask`` updated to include ``card_identifier``."""

    _validate_card_identifier(card_identifier)
    return mask | (1 << card_identifier)


def remove_card(mask: int, card_identifier: int, *, ignore_missing: bool = False) -> int:
    """Return ``mask`` without ``card_identifier``."""

    _validate_card_identifier(card_identifier)
    bit = 1 << card_identifier
    if mask & bit:
        return mask & ~bit
    if ignore_missing:
        return mask
    raise ValueError(f"card {card_identifier} not present in mask")


def has_card(mask: int, card_identifier: int) -> bool:
    """Return ``True`` if ``mask`` already includes ``card_identifier``."""

    if card_identifier < 0:
        return False
    return (mask >> card_identifier) & 1 == 1


def iter_cards(mask: int) -> Iterator[int]:
    """Yield all card identifiers present in ``mask``."""

    for card_identifier in range(DECK_CARD_COUNT):
        if (mask >> card_identifier) & 1:
            yield card_identifier


def cards_from_mask(mask: int) -> list[int]:
    """Return a list of card identifiers contained in ``mask``."""

    return list(iter_cards(mask))


def points_from_mask(mask: int) -> int:
    """Return the total point value represented by ``mask``."""

    total = 0
    for card_identifier in iter_cards(mask):
        total += card_points(card_identifier)
    return total


def split_mask(mask: int) -> tuple[int, int]:
    """Split a bit-mask into (hi, lo) components used by the Rust solver."""

    lo = mask & ((1 << 64) - 1)
    hi = mask >> 64
    return hi, lo


def combine_mask(mask_hi: int, mask_lo: int) -> int:
    """Combine (hi, lo) components into a single integer mask."""

    return (mask_hi << 64) | mask_lo
