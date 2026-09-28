#!/usr/bin/env python3
# mypy: disable-error-code="import-untyped"
"""Search card-agnostic balanced-teacher weights with held-out validation."""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.strategy_bots import (
    BALANCED,
    STRATEGY_NAMES,
    BalancedStrategyConfig,
)
from scripts.evaluate_strategy_teacher_matrix import RANDOM, evaluate


def candidate_config(index: int, seed: int) -> BalancedStrategyConfig:
    if index < 0:
        raise ValueError("candidate index must be non-negative")
    if index == 0:
        return BalancedStrategyConfig()
    rng = np.random.default_rng(seed + index * 104_729)
    return BalancedStrategyConfig(
        threat_scale=float(rng.uniform(0.65, 2.75)),
        defense_fit_weight=float(rng.uniform(3.0, 8.0)),
        defensive_building_bonus=float(rng.uniform(0.4, 2.8)),
        offense_position_weight=float(rng.uniform(2.0, 5.5)),
        offense_y=float(rng.uniform(11.5, 15.0)),
        offense_y_scale=float(rng.uniform(2.2, 5.0)),
        efficiency_weight=float(rng.uniform(0.15, 1.25)),
        tower_pressure_weight=float(rng.uniform(1.0, 4.5)),
        spell_cluster_weight=float(rng.uniform(1.0, 4.5)),
        cost_weight=float(rng.uniform(0.12, 0.7)),
        noop_score=float(rng.uniform(1.5, 4.5)),
        noop_threat_threshold=float(rng.uniform(0.03, 0.16)),
        noop_elixir_threshold=float(rng.uniform(5.5, 9.25)),
    )


def _score(payload: dict[str, Any]) -> float:
    ranking = payload["rankings"][0]
    rows = payload["results"][BALANCED]
    mean_crowns = float(
        np.mean([float(row["crown_diff_per_game"]) for row in rows.values()])
    )
    return float(
        ranking["mean_score_rate"]
        + 0.20 * ranking["worst_score_rate"]
        + 0.01 * mean_crowns
    )


def _job(spec: dict[str, Any]) -> dict[str, Any]:
    config = BalancedStrategyConfig(**spec["config"])
    payload = evaluate(
        decks_path=Path(spec["decks_path"]),
        learner_decks_path=Path(spec["learner_decks_path"]),
        opponent_decks_path=Path(spec["opponent_decks_path"]),
        candidate_strategies=[BALANCED],
        opponent_controllers=[*STRATEGY_NAMES, RANDOM],
        games_per_matchup=int(spec["games_per_matchup"]),
        seed=int(spec["seed"]),
        balanced_config=config,
    )
    return {
        "index": int(spec["index"]),
        "config": asdict(config),
        "objective": _score(payload),
        "matrix": payload,
    }


def search(
    *,
    decks_path: Path,
    learner_decks_path: Path,
    search_decks_path: Path,
    validation_decks_path: Path,
    candidates: int,
    finalists: int,
    search_games_per_matchup: int,
    validation_games_per_matchup: int,
    workers: int,
    seed: int,
) -> dict[str, Any]:
    if candidates < 2:
        raise ValueError("search requires at least two candidates")
    if not 1 <= finalists <= candidates:
        raise ValueError("finalists must be in [1, candidates]")
    if workers <= 0:
        raise ValueError("workers must be positive")
    common = {
        "decks_path": str(decks_path),
        "learner_decks_path": str(learner_decks_path),
    }
    search_specs = [
        {
            **common,
            "index": index,
            "config": asdict(candidate_config(index, seed)),
            "opponent_decks_path": str(search_decks_path),
            "games_per_matchup": search_games_per_matchup,
            "seed": seed,
        }
        for index in range(candidates)
    ]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        search_rows = list(executor.map(_job, search_specs))
    search_rows.sort(key=lambda row: (row["objective"], -row["index"]), reverse=True)
    finalist_indices = [int(row["index"]) for row in search_rows[:finalists]]
    if 0 not in finalist_indices:
        finalist_indices[-1] = 0
    finalist_indices = list(dict.fromkeys(finalist_indices))
    validation_specs = [
        {
            **common,
            "index": index,
            "config": asdict(candidate_config(index, seed)),
            "opponent_decks_path": str(validation_decks_path),
            "games_per_matchup": validation_games_per_matchup,
            "seed": seed + 1_000_003,
        }
        for index in finalist_indices
    ]
    with ProcessPoolExecutor(max_workers=min(workers, len(validation_specs))) as executor:
        validation_rows = list(executor.map(_job, validation_specs))
    validation_rows.sort(
        key=lambda row: (row["objective"], -row["index"]), reverse=True
    )
    default = next(row for row in validation_rows if int(row["index"]) == 0)
    best = validation_rows[0]
    default_rank = default["matrix"]["rankings"][0]
    best_rank = best["matrix"]["rankings"][0]
    reasons: list[str] = []
    if float(best_rank["mean_score_rate"]) < float(
        default_rank["mean_score_rate"]
    ) + 0.10:
        reasons.append("heldout_mean_score_gain_below_0p10")
    if float(best_rank["worst_score_rate"]) < float(
        default_rank["worst_score_rate"]
    ):
        reasons.append("heldout_worst_matchup_regression")
    if int(best_rank["total_wins"]) < int(default_rank["total_wins"]) + 3:
        reasons.append("heldout_win_gain_below_three")
    selected = 0 if reasons else int(best["index"])
    return {
        "schema": "clasher.balanced_strategy_teacher_search.v1",
        "seed": seed,
        "search_contract": {
            "candidates": candidates,
            "finalists": finalists,
            "search_games_per_matchup": search_games_per_matchup,
            "validation_games_per_matchup": validation_games_per_matchup,
            "workers": workers,
            "card_name_rules": False,
        },
        "search_rows": search_rows,
        "validation_rows": validation_rows,
        "selected_index": selected,
        "selected_config": asdict(candidate_config(selected, seed)),
        "rejection_reasons": reasons,
        "teacher_upgrade_authorized": selected != 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--learner-decks-path", type=Path, required=True)
    parser.add_argument("--search-decks-path", type=Path, required=True)
    parser.add_argument("--validation-decks-path", type=Path, required=True)
    parser.add_argument("--candidates", type=int, default=32)
    parser.add_argument("--finalists", type=int, default=6)
    parser.add_argument("--search-games-per-matchup", type=int, default=2)
    parser.add_argument("--validation-games-per-matchup", type=int, default=4)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--seed", type=int, default=1075201)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    payload = search(
        decks_path=args.decks_path.resolve(),
        learner_decks_path=args.learner_decks_path.resolve(),
        search_decks_path=args.search_decks_path.resolve(),
        validation_decks_path=args.validation_decks_path.resolve(),
        candidates=args.candidates,
        finalists=args.finalists,
        search_games_per_matchup=args.search_games_per_matchup,
        validation_games_per_matchup=args.validation_games_per_matchup,
        workers=args.workers,
        seed=args.seed,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.json_out.with_suffix(args.json_out.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, args.json_out)
    print(
        json.dumps(
            {
                "selected_index": payload["selected_index"],
                "teacher_upgrade_authorized": payload[
                    "teacher_upgrade_authorized"
                ],
                "rejection_reasons": payload["rejection_reasons"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
