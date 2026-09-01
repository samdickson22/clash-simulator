from __future__ import annotations

import json
from pathlib import Path

from clasher.rl.strategy_bots import STRATEGY_NAMES
from scripts.evaluate_hog26_simple_policy import evaluation_seed
from scripts.finalize_hog26_joint_q_gameplay_gate import RUN_SEEDS, finalize_gate


def test_opponent_evaluation_seeds_are_stable_and_distinct() -> None:
    opponents = (*STRATEGY_NAMES, "random")
    seeds = [evaluation_seed(1247001, opponent) for opponent in opponents]
    assert seeds[0] == 1247001
    assert len(set(seeds)) == len(opponents)


def _write_evaluation(
    path: Path,
    *,
    seed: int,
    wins: list[int],
    placement_rate: float = 0.12,
) -> None:
    games = 4
    rows = [
        {
            "opponent": opponent,
            "games": games,
            "wins": win_count,
            "losses": games - win_count,
            "draws": 0,
            "placement_rate": placement_rate,
        }
        for opponent, win_count in zip((*STRATEGY_NAMES, "random"), wins, strict=True)
    ]
    path.write_text(
        json.dumps(
            {
                "schema": "clasher.hog26.simple-policy-evaluation.v1",
                "base_seed": seed,
                "games_per_opponent": games,
                "rows": rows,
            }
        )
    )


def _root(tmp_path: Path, candidate: list[list[int]]) -> Path:
    for index, run_seed in enumerate(RUN_SEEDS):
        directory = tmp_path / f"seed_{run_seed}"
        directory.mkdir()
        seed = 1247001 + index * 100_000
        _write_evaluation(directory / "control.json", seed=seed, wins=[1] * 7)
        _write_evaluation(directory / "candidate.json", seed=seed, wins=candidate[index])
    return tmp_path


def test_gate_accepts_broad_improvement_without_regressions(tmp_path: Path) -> None:
    root = _root(
        tmp_path,
        candidate=[
            [2, 2, 1, 1, 1, 1, 1],
            [2, 2, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1],
        ],
    )
    result = finalize_gate(root, games=4, base_seed=1247001)
    assert result["status"] == "candidate-passed-development-gate"
    assert result["seed_improvements"] == 2
    assert result["opponent_improvements"] == 2


def test_gate_rejects_shifted_strategy_regression(tmp_path: Path) -> None:
    root = _root(
        tmp_path,
        candidate=[
            [2, 2, 2, 1, 1, 1, 0],
            [2, 2, 2, 1, 1, 1, 0],
            [2, 2, 2, 1, 1, 1, 0],
        ],
    )
    result = finalize_gate(root, games=4, base_seed=1247001)
    assert result["total_candidate_score"] > result["total_control_score"]
    assert result["opponent_regressions"] == 1
    assert result["status"] == "candidate-rejected"


def test_gate_rejects_passive_candidate(tmp_path: Path) -> None:
    root = _root(tmp_path, candidate=[[2] * 7 for _seed in RUN_SEEDS])
    for path in root.glob("seed_*/candidate.json"):
        payload = json.loads(path.read_text())
        for row in payload["rows"]:
            row["placement_rate"] = 0.01
        path.write_text(json.dumps(payload))
    result = finalize_gate(root, games=4, base_seed=1247001)
    assert not result["candidate_cadence_ok"]
    assert result["status"] == "candidate-rejected"
