"""Compatibility helpers for optional third-party dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence, cast

try:  # pragma: no cover - direct import path
    import numpy as _np
except ModuleNotFoundError:  # pragma: no cover - fallback environment

    @dataclass
    class _Array:
        data: list[int]

        def copy(self) -> "_Array":
            return _Array(self.data.copy())

        def __iter__(self):
            return iter(self.data)

    class _CompatNumpy:
        uint16 = int
        uint64 = int

        @staticmethod
        def array(values: Sequence[int], dtype: Any | None = None) -> _Array:
            return _Array(list(values))

        @staticmethod
        def zeros(length: int, dtype: Any | None = None) -> _Array:
            return _Array([0] * length)

    np = cast(Any, _CompatNumpy())
else:  # pragma: no cover - numpy available
    np = cast(Any, _np)

__all__ = ["np"]
