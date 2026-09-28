from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def _array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _subset_report(
    source: dict[str, Any],
    arrays: dict[str, np.ndarray],
    mask: np.ndarray,
    output: Path,
    *,
    split: str,
) -> dict[str, Any]:
    selected_arrays = {name: value[mask] for name, value in arrays.items()}
    selected_games = {int(value) for value in selected_arrays["game_ids"]}
    states = [
        row for row in source["states"] if int(row["game"]) in selected_games
    ]
    games = [
        row for row in source["games"] if int(row["game"]) in selected_games
    ]
    if len(states) != int(mask.sum()):
        raise ValueError("counterfactual split report and array rows disagree")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        np.savez_compressed(handle, **selected_arrays)  # type: ignore[arg-type]
    return {
        **{
            key: value
            for key, value in source.items()
            if key
            not in {
                "array_shapes",
                "array_sha256",
                "states",
                "games",
                "output",
                "states_collected",
                "decisive_improvements",
                "base_terminal_wins",
            }
        },
        "derived_split": split,
        "states_collected": len(states),
        "decisive_improvements": sum(
            bool(row["decisive_improvement"]) for row in states
        ),
        "base_terminal_wins": sum(float(row["base_score"]) == 1.0 for row in states),
        "array_shapes": {
            name: list(value.shape) for name, value in selected_arrays.items()
        },
        "array_sha256": {
            name: _array_sha256(value) for name, value in selected_arrays.items()
        },
        "output": str(output.resolve()),
        "games": games,
        "states": states,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--train-out", type=Path, required=True)
    parser.add_argument("--train-report", type=Path, required=True)
    parser.add_argument("--validation-out", type=Path, required=True)
    parser.add_argument("--validation-report", type=Path, required=True)
    parser.add_argument("--validation-modulus", type=int, default=4)
    parser.add_argument("--validation-remainder", type=int, default=3)
    args = parser.parse_args()
    if args.validation_modulus <= 1 or not (
        0 <= args.validation_remainder < args.validation_modulus
    ):
        raise ValueError("counterfactual validation modulus/remainder is invalid")
    with np.load(args.input, allow_pickle=False) as source:
        arrays = {name: np.asarray(source[name]) for name in source.files}
    report = json.loads(args.report.read_text(encoding="utf-8"))
    row_count = len(arrays["game_ids"])
    if any(value.shape[0] != row_count for value in arrays.values()):
        raise ValueError("counterfactual split arrays have inconsistent rows")
    validation_mask = (
        arrays["game_ids"] % args.validation_modulus
        == args.validation_remainder
    )
    train_mask = ~validation_mask
    if not np.any(train_mask) or not np.any(validation_mask):
        raise ValueError("counterfactual split requires two nonempty partitions")
    outputs = (
        (
            args.train_out,
            args.train_report,
            train_mask,
            "internal-train",
        ),
        (
            args.validation_out,
            args.validation_report,
            validation_mask,
            "internal-validation",
        ),
    )
    summaries = {}
    for output, report_path, mask, split in outputs:
        result = _subset_report(report, arrays, mask, output, split=split)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summaries[split] = {
            "states": int(mask.sum()),
            "games": len({int(value) for value in arrays["game_ids"][mask]}),
            "array_sha256": result["array_sha256"],
        }
    print(json.dumps(summaries, sort_keys=True))


if __name__ == "__main__":
    main()
