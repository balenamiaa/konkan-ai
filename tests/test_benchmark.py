from __future__ import annotations

from konkan.benchmark import run_head_to_head
from konkan.ismcts.search import SearchConfig


def test_run_head_to_head_returns_report() -> None:
    baseline = SearchConfig(simulations=1)
    challenger = SearchConfig(simulations=1)

    report = run_head_to_head(rounds=2, baseline=baseline, challenger=challenger, seed=7)

    assert len(report.history.rounds) == 2
    total_wins = report.baseline.wins + report.challenger.wins
    assert total_wins == 2
    assert report.history.rounds[0].scores
