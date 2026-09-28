"""Require two-seed replication for TV Royale type-imitation blends."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from clasher.rl.model import PolicyConfig

EXPECTED_SEEDS = frozenset({1045901, 1045902})


def _checkpoint_metadata(checkpoint: Path) -> tuple[float, str, int]:
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    interpolation = payload.get("interpolation") or {}
    alpha = interpolation.get("alpha")
    if not isinstance(alpha, (float, int)):
        raise TypeError(f"blend checkpoint lacks interpolation alpha: {checkpoint}")
    hierarchy = PolicyConfig.from_dict(
        payload["model_config"]
    ).deterministic_hierarchy
    seed = (payload.get("args") or {}).get("seed")
    if not isinstance(seed, int):
        raise TypeError(f"blend checkpoint lacks training seed: {checkpoint}")
    return float(alpha), hierarchy, seed


def annotate_type_repeatability(
    summary: dict[str, Any],
    metadata: dict[str, tuple[float, str, int]],
    *,
    expected_seeds: frozenset[int] = EXPECTED_SEEDS,
) -> dict[str, Any]:
    """Annotate only exact, safe, two-seed blend groups as repeatable."""
    rows = summary.get("candidates")
    if not isinstance(rows, list):
        raise TypeError("type blend summary needs a candidate list")
    groups: dict[tuple[str, float], list[dict[str, Any]]] = {}
    for row in rows:
        checkpoint = str(row["checkpoint"])
        if checkpoint not in metadata:
            row["two_seed_repeatable"] = False
            continue
        alpha, hierarchy, seed = metadata[checkpoint]
        row["alpha"] = alpha
        row["hierarchy"] = hierarchy
        row["training_seed"] = seed
        groups.setdefault((hierarchy, alpha), []).append(row)

    repeatable_groups = {
        key: values
        for key, values in groups.items()
        if {int(row["training_seed"]) for row in values} == expected_seeds
        and len(values) == len(expected_seeds)
        and all(
            row.get("improves_all_splits") is True
            and row.get("defensive_context_safe") is True
            for row in values
        )
    }
    for values in groups.values():
        for row in values:
            key = (str(row["hierarchy"]), float(row["alpha"]))
            row["two_seed_repeatable"] = key in repeatable_groups

    return {
        **summary,
        "schema_version": max(2, int(summary.get("schema_version", 0))),
        "expected_training_seeds": sorted(expected_seeds),
        "repeatable_group_count": len(repeatable_groups),
        "repeatable_candidate_count": sum(
            bool(row.get("two_seed_repeatable")) for row in rows
        ),
        "candidates": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-seed", action="append", type=int)
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    rows = summary.get("candidates")
    if not isinstance(rows, list):
        raise TypeError("type blend summary needs a candidate list")
    blend_paths = {
        str(row["checkpoint"]): Path(row["checkpoint"])
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("checkpoint"), str)
        and Path(row["checkpoint"]).name.startswith("alpha")
    }
    metadata = {
        checkpoint: _checkpoint_metadata(path)
        for checkpoint, path in blend_paths.items()
    }
    expected_seeds = frozenset(args.expected_seed or EXPECTED_SEEDS)
    if len(expected_seeds) < 2:
        raise ValueError("type repeatability requires at least two distinct seeds")
    annotated = annotate_type_repeatability(
        summary,
        metadata,
        expected_seeds=expected_seeds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(annotated, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not annotated["repeatable_group_count"]:
        raise SystemExit("no type-imitation blend repeats safely across both seeds")
    print(
        json.dumps(
            {
                "status": "type_repeatability_verified",
                "repeatable_group_count": annotated["repeatable_group_count"],
                "repeatable_candidate_count": annotated[
                    "repeatable_candidate_count"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
