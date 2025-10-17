"""Python interface for the Rust-based meld solver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


OBJ_MAX_CARDS = 0
OBJ_MIN_DEADWOOD = 1
OBJ_FIRST_14 = 2


class CoverResultProtocol(Protocol):
    """Structural protocol describing meld cover results."""

    @property
    def melds(self) -> list[object]:  # pragma: no cover - protocol only
        ...

    @property
    def covered_cards(self) -> int:  # pragma: no cover - protocol only
        ...

    @property
    def total_points(self) -> int:  # pragma: no cover - protocol only
        ...

    @property
    def used_jokers(self) -> int:  # pragma: no cover - protocol only
        ...


try:  # pragma: no cover - optional dependency
    from konkan_melds import CoverResult, best_cover, enumerate_melds
except Exception:  # pragma: no cover - optional dependency

    @dataclass(slots=True)
    class CoverResult:  # type: ignore[no-redef]
        """Fallback cover result used when the Rust extension is unavailable."""

        melds: list[object]
        covered_cards: int
        total_points: int
        used_jokers: int

    def enumerate_melds(mask_hi: int, mask_lo: int) -> list[object]:  # type: ignore[misc]
        """Fallback implementation returning no melds."""

        return []

    def best_cover(mask_hi: int, mask_lo: int, objective: int, threshold: int) -> CoverResult:  # type: ignore[misc]
        """Fallback best cover returning empty results."""

        return CoverResult(melds=[], covered_cards=0, total_points=0, used_jokers=0)


def best_cover_for_go_out(mask_hi: int, mask_lo: int) -> CoverResult:
    """Return the best cover targeting an immediate go-out scenario."""

    return best_cover(mask_hi, mask_lo, OBJ_FIRST_14, 0)


def best_cover_to_threshold(mask_hi: int, mask_lo: int, threshold: int) -> CoverResult:
    """Return the best cover targeting the provided points threshold."""

    return best_cover(mask_hi, mask_lo, OBJ_MIN_DEADWOOD, threshold)
