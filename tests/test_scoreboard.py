from __future__ import annotations

import pytest

from konkan import scoreboard
from konkan.rules import PlayerRoundScore


def _score(player_index: int, laid: int, deadwood: int, net: int, won: bool) -> PlayerRoundScore:
    return PlayerRoundScore(
        player_index=player_index,
        laid_points=laid,
        deadwood_points=deadwood,
        net_points=net,
        won_round=won,
    )


def test_match_history_accumulates_totals() -> None:
    history = scoreboard.MatchHistory(num_players=2)
    history.record(
        scoreboard.RoundSummary(
            round_number=1,
            winner_index=0,
            scores=[
                _score(0, laid=100, deadwood=0, net=100, won=True),
                _score(1, laid=40, deadwood=30, net=10, won=False),
            ],
        )
    )
    history.record(
        scoreboard.RoundSummary(
            round_number=2,
            winner_index=1,
            scores=[
                _score(0, laid=20, deadwood=15, net=5, won=False),
                _score(1, laid=90, deadwood=0, net=90, won=True),
            ],
        )
    )

    totals = history.totals()
    assert len(history.rounds) == 2
    assert totals[0].wins == 1
    assert totals[1].wins == 1
    assert totals[0].laid_points == 120
    assert totals[1].laid_points == 130
    assert totals[0].deadwood_points == 15
    assert totals[1].deadwood_points == 30
    assert totals[0].net_points == 105
    assert totals[1].net_points == 100


def test_match_history_validates_player_count() -> None:
    history = scoreboard.MatchHistory(num_players=2)
    summary = scoreboard.RoundSummary(
        round_number=1,
        winner_index=0,
        scores=[
            _score(0, laid=0, deadwood=0, net=0, won=True),
        ],
    )
    with pytest.raises(ValueError):
        history.record(summary)
