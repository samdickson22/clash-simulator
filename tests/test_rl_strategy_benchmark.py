from pathlib import Path

import pytest

from clasher.rl.strategy_benchmark import build_benchmark_report, render_markdown
from clasher.rl.strategy_bots import STRATEGY_NAMES


def _metrics(score: float) -> dict[str, float]:
    return {
        "wins": 2.0,
        "losses": 1.0,
        "draws": 1.0,
        "score_rate": score,
        "crown_diff_per_game": 0.25,
        "incoming_tower_danger_mean": 0.1,
        "defensive_action_rate_when_threatened": 0.75,
    }


def test_strategy_benchmark_report_is_machine_readable_and_pfsp_ready():
    results = {
        name: _metrics(0.2 + index * 0.1) for index, name in enumerate(STRATEGY_NAMES)
    }
    report = build_benchmark_report(
        checkpoint=Path("policy.pt"),
        checkpoint_update=1400,
        seed=23,
        games_per_opponent=4,
        reward_profile="defense-v2",
        results=results,
    )

    assert report["schema_version"] == 1
    assert report["summary"]["worst_opponent"] == STRATEGY_NAMES[0]
    assert sum(report["pfsp"]["weights"].values()) == pytest.approx(1.0)
    assert (
        report["pfsp"]["weights"][STRATEGY_NAMES[0]]
        > report["pfsp"]["weights"][STRATEGY_NAMES[-1]]
    )

    markdown = render_markdown(report)
    assert "update 1400" in markdown
    assert "PFSP weight" in markdown
    for name in STRATEGY_NAMES:
        assert name in markdown
