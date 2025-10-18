"""Python interface for the Rust-based meld solver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol, cast

OBJ_MAX_CARDS = 0
OBJ_MIN_DEADWOOD = 1
OBJ_FIRST_14 = 2


class MeldProtocol(Protocol):
    """Minimal protocol describing a meld from the solver."""

    mask_hi: int
    mask_lo: int
    points: int
    jokers_used: int


class CoverResultProtocol(Protocol):
    """Structural protocol describing meld cover results."""

    @property
    def melds(self) -> list[MeldProtocol]:  # pragma: no cover - protocol only
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


native_best_cover: Callable[[int, int, int, int], CoverResultProtocol] | None = None
native_enumerate_melds: Callable[[int, int], list[MeldProtocol]] | None = None

if TYPE_CHECKING:  # pragma: no cover - typing helper
    pass

try:  # pragma: no cover - optional dependency
    from konkan_melds import best_cover as _native_best_cover
    from konkan_melds import enumerate_melds as _native_enumerate_melds

    native_best_cover = cast(
        Callable[[int, int, int, int], CoverResultProtocol], _native_best_cover
    )
    native_enumerate_melds = cast(Callable[[int, int], list[MeldProtocol]], _native_enumerate_melds)
except Exception:  # pragma: no cover - optional dependency
    native_best_cover = None
    native_enumerate_melds = None


HAVE_NATIVE_SOLVER = native_best_cover is not None and native_enumerate_melds is not None


@dataclass(slots=True)
class _FallbackCoverResult(CoverResultProtocol):
    melds: list[MeldProtocol]
    covered_cards: int
    total_points: int
    used_jokers: int


def enumerate_melds(mask_hi: int, mask_lo: int) -> list[MeldProtocol]:
    """Return all melds contained in the provided bit masks."""

    if native_enumerate_melds is None:
        return []
    return list(native_enumerate_melds(mask_hi, mask_lo))


def best_cover(mask_hi: int, mask_lo: int, objective: int, threshold: int) -> CoverResultProtocol:
    """Return the solver cover for ``objective`` or a fallback if unavailable."""

    if native_best_cover is None:
        return _FallbackCoverResult(melds=[], covered_cards=0, total_points=0, used_jokers=0)
    return native_best_cover(mask_hi, mask_lo, objective, threshold)


def best_cover_for_go_out(mask_hi: int, mask_lo: int) -> CoverResultProtocol:
    """Return the best cover targeting an immediate go-out scenario."""

    return best_cover(mask_hi, mask_lo, OBJ_FIRST_14, 0)


def best_cover_to_threshold(mask_hi: int, mask_lo: int, threshold: int) -> CoverResultProtocol:
    """Return the best cover targeting the provided points threshold."""

    return best_cover(mask_hi, mask_lo, OBJ_MIN_DEADWOOD, threshold)
