"""Opponent modeling hooks for IS-MCTS."""

from __future__ import annotations

from dataclasses import dataclass

from .. import encoding
from ..actions import PlayAction
from ..state import KonkanState


@dataclass(slots=True)
class OpponentModel:
    """Light-weight heuristic opponent model used to bias search priors."""

    trash_penalty: float = 0.12
    laydown_bonus: float = 0.08
    sarf_bonus: float = 0.05
    joker_penalty: float = 0.4

    def prior_adjustment(self, state: KonkanState, action: PlayAction) -> float:
        """Return a multiplicative adjustment for ``action`` originating at ``state``."""

        discard = action.discard
        decoded = encoding.decode_id(discard)
        points = encoding.card_points(discard)

        adjustment = 1.0
        adjustment -= self.trash_penalty * (points / 10.0)
        if decoded.is_joker:
            adjustment -= self.joker_penalty
        if action.lay_down:
            adjustment += self.laydown_bonus
        if action.sarf_moves:
            adjustment += self.sarf_bonus * len(action.sarf_moves)

        return max(0.05, adjustment)
