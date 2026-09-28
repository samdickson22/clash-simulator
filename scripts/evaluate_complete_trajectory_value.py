"""Measure recurrent critic calibration against complete game outcomes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def _rank_auc(scores: np.ndarray, outcomes: np.ndarray) -> float | None:
    positive = outcomes > 0.5
    negative = outcomes < 0.5
    if not positive.any() or not negative.any():
        return None
    comparisons = scores[positive, None] - scores[negative][None, :]
    return float(np.mean(comparisons > 0) + 0.5 * np.mean(comparisons == 0))


def _pearson(left: np.ndarray, right: np.ndarray) -> float | None:
    if left.size < 2 or np.std(left) <= 1e-12 or np.std(right) <= 1e-12:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def evaluate_value_trace(
    games: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    outcomes = {
        int(game["game"]): (
            1.0
            if game["outcome"] == "win"
            else 0.0
            if game["outcome"] == "loss"
            else 0.5
        )
        for game in games
    }
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in decisions:
        grouped.setdefault(int(row["game"]), []).append(row)
    if set(grouped) != set(outcomes):
        raise ValueError("value trace and game records cover different games")
    rows: list[dict[str, float]] = []
    for game, trace in grouped.items():
        trace.sort(key=lambda row: int(row["tick"]))
        last_tick = max(1, int(games[game]["ticks"]))
        for row in trace:
            rows.append(
                {
                    "game": float(game),
                    "progress": int(row["tick"]) / last_tick,
                    "value": float(row["predicted_value"]),
                    "outcome": outcomes[game],
                }
            )
    values = np.asarray([row["value"] for row in rows], dtype=np.float64)
    targets = np.asarray([row["outcome"] for row in rows], dtype=np.float64)
    probabilities = 1.0 / (1.0 + np.exp(-np.clip(values, -20.0, 20.0)))
    phases = {
        "early": (0.0, 1.0 / 3.0),
        "middle": (1.0 / 3.0, 2.0 / 3.0),
        "late": (2.0 / 3.0, 1.01),
    }
    phase_reports: dict[str, Any] = {}
    progress = np.asarray([row["progress"] for row in rows], dtype=np.float64)
    for name, (lower, upper) in phases.items():
        keep = (progress >= lower) & (progress < upper)
        phase_values = values[keep]
        phase_targets = targets[keep]
        phase_probabilities = probabilities[keep]
        phase_reports[name] = {
            "decisions": int(keep.sum()),
            "value_mean": float(phase_values.mean()),
            "value_std": float(phase_values.std()),
            "value_outcome_pearson": _pearson(phase_values, phase_targets),
            "win_loss_auc": _rank_auc(phase_values, phase_targets),
            "sigmoid_brier": float(np.mean((phase_probabilities - phase_targets) ** 2)),
        }
    per_game = []
    for game, trace in grouped.items():
        trace.sort(key=lambda row: int(row["tick"]))
        values_for_game = [float(row["predicted_value"]) for row in trace]
        per_game.append(
            {
                "game": game,
                "outcome": outcomes[game],
                "first_value": values_for_game[0],
                "middle_value": values_for_game[len(values_for_game) // 2],
                "last_value": values_for_game[-1],
                "decisions": len(values_for_game),
            }
        )
    return {
        "schema_version": 1,
        "games": len(games),
        "decisions": len(rows),
        "outcome_counts": {
            "wins": sum(value == 1.0 for value in outcomes.values()),
            "draws": sum(value == 0.5 for value in outcomes.values()),
            "losses": sum(value == 0.0 for value in outcomes.values()),
        },
        "phases": phase_reports,
        "per_game": per_game,
        "all_values_finite": bool(np.isfinite(values).all()),
        "value_absolute_max": float(np.abs(values).max()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    games = json.loads(args.games.read_text())
    decisions = json.loads(args.decisions.read_text())
    report = evaluate_value_trace(games, decisions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
