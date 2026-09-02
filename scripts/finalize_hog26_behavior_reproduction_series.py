#!/usr/bin/env python3
"""Aggregate independent action-hashed Hog behavior reproduction gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

INPUT_SCHEMA = "clasher.hog26.closed-loop-behavior-reproduction.v1"
SCHEMA = "clasher.hog26.closed-loop-behavior-reproduction-series.v1"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != INPUT_SCHEMA:
        raise ValueError(f"unknown reproduction comparison schema: {path}")
    return payload


def aggregate(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    if len(comparisons) < 2:
        raise ValueError("scaled reproduction requires at least two independent seeds")
    seeds = [int(row["base_seed"]) for row in comparisons]
    if len(set(seeds)) != len(seeds):
        raise ValueError("reproduction comparison seeds must be unique")
    for key in ("teacher_checkpoint_sha256", "student_checkpoint_sha256"):
        if len({str(row[key]) for row in comparisons}) != 1:
            raise ValueError(f"reproduction comparisons use different {key}")
    games = sum(int(row["games"]) for row in comparisons)
    hash_rows = sum(int(row["exact_action_hash_rows"]) for row in comparisons)
    hash_matches = sum(int(row["exact_action_hash_matches"]) for row in comparisons)
    all_behavior_pass = all(bool(row["behavior_gate_pass"]) for row in comparisons)
    exact_action_reproduction = hash_rows == games and hash_matches == games
    scale_gate_met = games >= 56
    passed = all_behavior_pass and exact_action_reproduction and scale_gate_met
    return {
        "schema": SCHEMA,
        "seeds": seeds,
        "comparisons": comparisons,
        "games_per_arm": games,
        "minimum_games_per_arm": 56,
        "teacher_checkpoint_sha256": comparisons[0]["teacher_checkpoint_sha256"],
        "student_checkpoint_sha256": comparisons[0]["student_checkpoint_sha256"],
        "teacher_score": sum(int(row["teacher_score"]) for row in comparisons),
        "student_score": sum(int(row["student_score"]) for row in comparisons),
        "exact_action_hash_rows": hash_rows,
        "exact_action_hash_matches": hash_matches,
        "exact_action_hash_match_rate": hash_matches / max(1, hash_rows),
        "all_behavior_gates_pass": all_behavior_pass,
        "exact_action_reproduction": exact_action_reproduction,
        "scale_gate_met": scale_gate_met,
        "status": "passed-closed-loop" if passed else "rejected",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite reproduction-series report")
    result = aggregate([_load(path) for path in args.comparison])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
