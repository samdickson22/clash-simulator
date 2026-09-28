"""Select repeatable TV Royale location-imitation gameplay candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from clasher.rl.model import PolicyConfig

SPLITS = ("validation", "archetype_test", "chronology_test")
EXPECTED_SEEDS = frozenset({1046001, 1046002})


def _checkpoint_metadata(checkpoint: Path) -> tuple[float, str]:
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    interpolation = payload.get("interpolation") or {}
    alpha = interpolation.get("alpha")
    if not isinstance(alpha, (float, int)):
        raise TypeError(f"blend checkpoint lacks interpolation alpha: {checkpoint}")
    hierarchy = PolicyConfig.from_dict(
        payload["model_config"]
    ).deterministic_hierarchy
    return float(alpha), hierarchy


def summarize_location_candidates(
    mapping: dict[str, dict[str, Any]],
    results: dict[str, dict[str, dict[str, Any]]],
    checkpoint_metadata: dict[str, tuple[float, str]],
    *,
    expected_seeds: frozenset[int] = EXPECTED_SEEDS,
    type_nll_tolerance: float = 1e-6,
    safe_alpha: float = 0.0625,
) -> dict[str, Any]:
    """Require held-out gains and exact two-seed replication per epoch rung."""
    rows: list[dict[str, Any]] = []
    for checkpoint, mapping_row in mapping.items():
        parent = str(mapping_row["parent"])
        if checkpoint == parent:
            continue
        alpha, hierarchy = checkpoint_metadata[checkpoint]
        location_improvement = {
            split: float(results[split][parent]["conditional_location_nll"])
            - float(results[split][checkpoint]["conditional_location_nll"])
            for split in SPLITS
        }
        type_change = {
            split: float(results[split][checkpoint]["action_type_nll"])
            - float(results[split][parent]["action_type_nll"])
            for split in SPLITS
        }
        rows.append(
            {
                "checkpoint": checkpoint,
                "parent": parent,
                "alpha": alpha,
                "hierarchy": hierarchy,
                "training_epochs": int(mapping_row["training_epochs"]),
                "training_seed": int(mapping_row["training_seed"]),
                "conditional_location_nll_improvement": location_improvement,
                "action_type_nll_change": type_change,
                "improves_location_all_splits": all(
                    value > 0.0 for value in location_improvement.values()
                ),
                "preserves_action_type_all_splits": all(
                    abs(value) <= type_nll_tolerance
                    for value in type_change.values()
                ),
                "mean_location_nll_improvement": sum(
                    location_improvement.values()
                )
                / len(SPLITS),
            }
        )

    groups: dict[tuple[str, str, int, float], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row["parent"]),
            str(row["hierarchy"]),
            int(row["training_epochs"]),
            float(row["alpha"]),
        )
        groups.setdefault(key, []).append(row)
    repeatable_groups = {
        key: values
        for key, values in groups.items()
        if {int(row["training_seed"]) for row in values} == expected_seeds
        and len(values) == len(expected_seeds)
        and all(
            row["improves_location_all_splits"]
            and row["preserves_action_type_all_splits"]
            for row in values
        )
    }
    for row in rows:
        key = (
            str(row["parent"]),
            str(row["hierarchy"]),
            int(row["training_epochs"]),
            float(row["alpha"]),
        )
        row["two_seed_repeatable"] = key in repeatable_groups

    def group_gain(item: tuple[tuple[str, str, int, float], list[dict[str, Any]]]) -> float:
        return sum(
            float(row["mean_location_nll_improvement"]) for row in item[1]
        ) / len(item[1])

    selected: list[str] = []
    for hierarchy in ("slot", "play-gate"):
        hierarchy_groups = [
            item for item in repeatable_groups.items() if item[0][1] == hierarchy
        ]
        if not hierarchy_groups:
            continue
        safe = min(
            hierarchy_groups,
            key=lambda item: (
                abs(item[0][3] - safe_alpha),
                -group_gain(item),
                item[0][2],
            ),
        )
        strongest = max(
            hierarchy_groups,
            key=lambda item: (
                group_gain(item),
                -item[0][2],
                -abs(item[0][3] - safe_alpha),
            ),
        )
        for _, group_rows in (safe, strongest):
            for row in sorted(group_rows, key=lambda value: value["training_seed"]):
                checkpoint = str(row["checkpoint"])
                if checkpoint not in selected:
                    selected.append(checkpoint)

    return {
        "schema_version": 2,
        "splits": list(SPLITS),
        "expected_training_seeds": sorted(expected_seeds),
        "candidate_count": len(rows),
        "eligible_count": sum(bool(row["two_seed_repeatable"]) for row in rows),
        "repeatable_group_count": len(repeatable_groups),
        "candidates": sorted(
            rows,
            key=lambda row: float(row["mean_location_nll_improvement"]),
            reverse=True,
        ),
        "gameplay_candidates": selected,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping-file", required=True, type=Path)
    parser.add_argument("--validation-report", required=True, type=Path)
    parser.add_argument("--archetype-report", required=True, type=Path)
    parser.add_argument("--chronology-report", required=True, type=Path)
    parser.add_argument("--summary-out", required=True, type=Path)
    parser.add_argument("--candidate-out", required=True, type=Path)
    args = parser.parse_args()

    mapping: dict[str, dict[str, Any]] = {}
    for line in args.mapping_file.read_text(encoding="utf-8").splitlines():
        checkpoint, parent, training_epochs, training_seed = line.split("\t")
        mapping[str(Path(checkpoint).resolve())] = {
            "parent": str(Path(parent).resolve()),
            "training_epochs": int(training_epochs),
            "training_seed": int(training_seed),
        }
    report_paths = {
        "validation": args.validation_report,
        "archetype_test": args.archetype_report,
        "chronology_test": args.chronology_report,
    }
    results = {
        split: {
            str(Path(row["checkpoint"]).resolve()): row
            for row in json.loads(path.read_text(encoding="utf-8"))["results"]
        }
        for split, path in report_paths.items()
    }
    metadata = {
        checkpoint: _checkpoint_metadata(Path(checkpoint))
        for checkpoint, row in mapping.items()
        if checkpoint != row["parent"]
    }
    summary = summarize_location_candidates(mapping, results, metadata)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    candidates = summary["gameplay_candidates"]
    args.candidate_out.parent.mkdir(parents=True, exist_ok=True)
    args.candidate_out.write_text(
        "".join(f"{checkpoint}\n" for checkpoint in candidates),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "location_imitation_complete",
                "repeatable_group_count": summary["repeatable_group_count"],
                "gameplay_candidates": candidates,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
