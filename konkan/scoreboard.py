"""Helpers for tracking multi-round Konkan match results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .rules import PlayerRoundScore

__all__ = ["RoundSummary", "PlayerMatchTotal", "MatchHistory"]


@dataclass(frozen=True, slots=True)
class RoundSummary:
    """Summary statistics captured after a single round."""

    round_number: int
    winner_index: int
    scores: Sequence[PlayerRoundScore]


@dataclass(frozen=True, slots=True)
class PlayerMatchTotal:
    """Aggregate match totals accumulated across all recorded rounds."""

    player_index: int
    wins: int
    laid_points: int
    deadwood_points: int
    net_points: int


@dataclass(slots=True)
class MatchHistory:
    """Mutable tracker that accumulates round summaries for a match."""

    num_players: int
    rounds: list[RoundSummary] = field(default_factory=list)
    _wins: list[int] = field(init=False, repr=False)
    _laid: list[int] = field(init=False, repr=False)
    _deadwood: list[int] = field(init=False, repr=False)
    _net: list[int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.num_players <= 0:
            raise ValueError("num_players must be positive")
        self._wins = [0 for _ in range(self.num_players)]
        self._laid = [0 for _ in range(self.num_players)]
        self._deadwood = [0 for _ in range(self.num_players)]
        self._net = [0 for _ in range(self.num_players)]

    def record(self, summary: RoundSummary) -> None:
        """Record ``summary`` and update cumulative totals."""

        if len(summary.scores) != self.num_players:
            raise ValueError("score count does not match number of players")
        self.rounds.append(summary)
        for score in summary.scores:
            idx = score.player_index
            if idx < 0 or idx >= self.num_players:
                raise ValueError("player index out of range")
            self._laid[idx] += score.laid_points
            self._deadwood[idx] += score.deadwood_points
            self._net[idx] += score.net_points
            if score.won_round:
                self._wins[idx] += 1

    def totals(self) -> list[PlayerMatchTotal]:
        """Return the cumulative totals for each player in seating order."""

        return [
            PlayerMatchTotal(
                player_index=idx,
                wins=self._wins[idx],
                laid_points=self._laid[idx],
                deadwood_points=self._deadwood[idx],
                net_points=self._net[idx],
            )
            for idx in range(self.num_players)
        ]
