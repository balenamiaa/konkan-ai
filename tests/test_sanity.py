"""Sanity tests ensuring the scaffolding imports correctly."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "konkan",
        "konkan.cards",
        "konkan.encoding",
        "konkan.state",
        "konkan.melds",
        "konkan.ismcts.search",
    ],
)
def test_modules_import(module_name: str) -> None:
    """Ensure all foundational modules can be imported."""

    assert importlib.import_module(module_name)
