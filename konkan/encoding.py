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
