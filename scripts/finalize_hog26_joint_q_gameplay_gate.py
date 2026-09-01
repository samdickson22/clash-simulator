#!/usr/bin/env python3
"""Apply the frozen matched gameplay gate to three control/joint-Q seeds."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from clasher.rl.strategy_bots import STRATEGY_NAMES

OPPONENTS = (*STRATEGY_NAMES, "random")
RUN_SEEDS = (1246001, 1246002, 1246003)
SCHEMA = "clasher.hog26.joint-q-gameplay-gate.v1"


def _score(row: dict[str, Any]) -> float:
    return float(row["wins"]) + 0.5 * float(row["draws"])


def _load_evaluation(path: Path, *, games: int, seed: int) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "clasher.hog26.simple-policy-evaluation.v1":
        raise ValueError(f"unexpected evaluation schema: {path}")
    if payload.get("games_per_opponent") != games:
        raise ValueError(f"evaluation game count drifted: {path}")
    if payload.get("base_seed") != seed:
        raise ValueError(f"evaluation seed drifted: {path}")
    rows = payload.get("rows")
    if not isinstance(rows, list) or tuple(row.get("opponent") for row in rows) != OPPONENTS:
        raise ValueError(f"evaluation opponent order drifted: {path}")
    if any(row.get("games") != games for row in rows):
        raise ValueError(f"evaluation row game count drifted: {path}")
    return cast(dict[str, Any], payload)


def finalize_gate(root: Path, *, games: int, base_seed: int) -> dict[str, Any]:
    evaluations: dict[int, dict[str, dict[str, Any]]] = {}
    seed_comparisons: list[dict[str, Any]] = []
    aggregate = {
        opponent: {"control_score": 0.0, "candidate_score": 0.0}
        for opponent in OPPONENTS
    }
    placement_rates: list[float] = []

    for index, run_seed in enumerate(RUN_SEEDS):
        evaluation_seed = base_seed + index * 100_000
        arms = {
            arm: _load_evaluation(
                root / f"seed_{run_seed}" / f"{arm}.json",
                games=games,
                seed=evaluation_seed,
            )
            for arm in ("control", "candidate")
        }
        evaluations[run_seed] = arms
        arm_scores: dict[str, float] = {}
        for arm, payload in arms.items():
            arm_scores[arm] = sum(_score(row) for row in payload["rows"])
            if arm == "candidate":
                placement_rates.extend(float(row["placement_rate"]) for row in payload["rows"])
            for row in payload["rows"]:
                aggregate[row["opponent"]][f"{arm}_score"] += _score(row)
        seed_comparisons.append(
            {
                "run_seed": run_seed,
                "evaluation_seed": evaluation_seed,
                "control_score": arm_scores["control"],
                "candidate_score": arm_scores["candidate"],
                "delta": arm_scores["candidate"] - arm_scores["control"],
            }
        )

    opponent_comparisons = []
    for opponent in OPPONENTS:
        row = {"opponent": opponent, **aggregate[opponent]}
        row["delta"] = row["candidate_score"] - row["control_score"]
        opponent_comparisons.append(row)

    seed_improvements = sum(row["delta"] > 0.0 for row in seed_comparisons)
    seed_regressions = sum(row["delta"] < 0.0 for row in seed_comparisons)
    opponent_improvements = sum(row["delta"] > 0.0 for row in opponent_comparisons)
    opponent_regressions = sum(row["delta"] < 0.0 for row in opponent_comparisons)
    total_control = sum(row["control_score"] for row in seed_comparisons)
    total_candidate = sum(row["candidate_score"] for row in seed_comparisons)
    cadence_ok = bool(placement_rates) and all(
        0.05 <= rate <= 0.35 for rate in placement_rates
    )
    passed = (
        total_candidate > total_control
        and seed_improvements >= 2
        and seed_regressions == 0
        and opponent_improvements >= 2
        and opponent_regressions == 0
        and cadence_ok
    )
    return {
        "schema": SCHEMA,
        "status": "candidate-passed-development-gate" if passed else "candidate-rejected",
        "games_per_opponent_per_arm_seed": games,
        "total_games": games * len(OPPONENTS) * 2 * len(RUN_SEEDS),
        "base_seed": base_seed,
        "total_control_score": total_control,
        "total_candidate_score": total_candidate,
        "seed_improvements": seed_improvements,
        "seed_regressions": seed_regressions,
        "opponent_improvements": opponent_improvements,
        "opponent_regressions": opponent_regressions,
        "candidate_cadence_ok": cadence_ok,
        "candidate_placement_rate_range": [
            min(placement_rates),
            max(placement_rates),
        ],
        "seed_comparisons": seed_comparisons,
        "opponent_comparisons": opponent_comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--base-seed", type=int, default=1247001)
    args = parser.parse_args()
    output = args.root / "summary.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite gameplay summary: {output}")
    payload = finalize_gate(args.root, games=args.games, base_seed=args.base_seed)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    output.write_text(encoded, encoding="utf-8")
    (args.root / "summary.sha256").write_text(
        hashlib.sha256(encoded.encode("utf-8")).hexdigest() + "\n",
        encoding="utf-8",
    )
    (args.root / "COMPLETE").write_text(
        "hog26_joint_q_gameplay_gate_complete_v1\n", encoding="utf-8"
    )
    if payload["status"] == "candidate-passed-development-gate":
        (args.root / "PROMOTE_CANDIDATE").write_text(
            "expanded_evaluation_required\n", encoding="utf-8"
        )
    print(json.dumps({"status": payload["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
