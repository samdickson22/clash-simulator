#!/usr/bin/env python3
"""Finalize the matched Simple-Gym gate for the spatial-teacher candidate."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from clasher.rl.strategy_bots import STRATEGY_NAMES

OPPONENTS = (*STRATEGY_NAMES, "random")
SCHEMA = "clasher.hog26.spatial-teacher-cuda-gate.v1"


def _load(path: Path, *, games: int, seed: int) -> dict[str, Any]:
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    if payload.get("schema") != "clasher.hog26.simple-policy-evaluation.v1":
        raise ValueError(f"unexpected evaluation schema: {path}")
    if payload.get("device") != "cuda":
        raise ValueError(f"evaluation did not use CUDA: {path}")
    if payload.get("games_per_opponent") != games or payload.get("base_seed") != seed:
        raise ValueError(f"evaluation contract drifted: {path}")
    rows = payload.get("rows")
    if not isinstance(rows, list) or tuple(row.get("opponent") for row in rows) != OPPONENTS:
        raise ValueError(f"opponent order drifted: {path}")
    for row in rows:
        metadata = row.get("simulation_backend_metadata")
        if not isinstance(metadata, dict) or metadata.get("execution_mode") != "cuda-graph":
            raise ValueError(f"row did not use CUDA Graph execution: {path}")
    return payload


def _score(row: dict[str, Any]) -> float:
    return float(row["wins"]) + 0.5 * float(row["draws"])


def finalize(root: Path, *, games: int, seed: int) -> dict[str, Any]:
    arms = {
        arm: _load(root / f"{arm}.json", games=games, seed=seed)
        for arm in ("base", "candidate")
    }
    comparisons = []
    candidate_rates = []
    for base_row, candidate_row in zip(
        arms["base"]["rows"], arms["candidate"]["rows"], strict=True
    ):
        base_score = _score(base_row)
        candidate_score = _score(candidate_row)
        candidate_rates.append(float(candidate_row["placement_rate"]))
        comparisons.append(
            {
                "opponent": base_row["opponent"],
                "base_score": base_score,
                "candidate_score": candidate_score,
                "delta": candidate_score - base_score,
            }
        )
    total_base = sum(row["base_score"] for row in comparisons)
    total_candidate = sum(row["candidate_score"] for row in comparisons)
    improvements = sum(row["delta"] > 0 for row in comparisons)
    regressions = sum(row["delta"] < 0 for row in comparisons)
    cadence_ok = all(0.05 <= rate <= 0.35 for rate in candidate_rates)
    passed = (
        total_candidate > total_base
        and improvements >= 2
        and regressions == 0
        and cadence_ok
    )
    return {
        "schema": SCHEMA,
        "status": "candidate-passed-development-gate" if passed else "candidate-rejected",
        "seed": seed,
        "games_per_opponent": games,
        "total_games": games * len(OPPONENTS) * 2,
        "base_checkpoint_sha256": arms["base"]["checkpoint_sha256"],
        "candidate_checkpoint_sha256": arms["candidate"]["checkpoint_sha256"],
        "total_base_score": total_base,
        "total_candidate_score": total_candidate,
        "opponent_improvements": improvements,
        "opponent_regressions": regressions,
        "candidate_cadence_ok": cadence_ok,
        "candidate_placement_rate_range": [min(candidate_rates), max(candidate_rates)],
        "opponent_comparisons": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1249301)
    args = parser.parse_args()
    output = args.root / "summary.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite gate summary: {output}")
    payload = finalize(args.root, games=args.games, seed=args.seed)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    output.write_text(encoded, encoding="utf-8")
    (args.root / "summary.sha256").write_text(
        hashlib.sha256(encoded.encode("utf-8")).hexdigest() + "\n",
        encoding="utf-8",
    )
    (args.root / "COMPLETE").write_text(
        "hog26_spatial_teacher_cuda_gate_complete_v1\n", encoding="utf-8"
    )
    if payload["status"] == "candidate-passed-development-gate":
        (args.root / "EXPANDED_EVALUATION_REQUIRED").write_text(
            "candidate_is_not_yet_promoted\n", encoding="utf-8"
        )
    print(json.dumps({"status": payload["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
