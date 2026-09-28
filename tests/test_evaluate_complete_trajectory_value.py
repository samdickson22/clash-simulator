from __future__ import annotations

from scripts.evaluate_complete_trajectory_value import evaluate_value_trace


def test_complete_trajectory_value_reports_phase_calibration() -> None:
    games = [
        {"game": 0, "outcome": "win", "ticks": 100},
        {"game": 1, "outcome": "loss", "ticks": 100},
    ]
    decisions = [
        {"game": 0, "tick": 10, "predicted_value": 0.2},
        {"game": 0, "tick": 50, "predicted_value": 1.0},
        {"game": 0, "tick": 90, "predicted_value": 2.0},
        {"game": 1, "tick": 10, "predicted_value": -0.2},
        {"game": 1, "tick": 50, "predicted_value": -1.0},
        {"game": 1, "tick": 90, "predicted_value": -2.0},
    ]

    report = evaluate_value_trace(games, decisions)

    assert report["all_values_finite"] is True
    assert report["outcome_counts"] == {"wins": 1, "draws": 0, "losses": 1}
    for phase in ("early", "middle", "late"):
        assert report["phases"][phase]["win_loss_auc"] == 1.0
        assert report["phases"][phase]["value_outcome_pearson"] > 0.999
