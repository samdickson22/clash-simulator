# mypy: disable-error-code="import-untyped"

"""Select a behaviorally informative TV Royale blend gameplay screen."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from clasher.rl.model import PolicyConfig


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


def select_gameplay_candidates(
    rows: list[dict[str, Any]],
    *,
    metadata: dict[str, tuple[float, str]],
    safe_alpha: float = 0.0625,
    middle_alpha: float = 0.50,
) -> list[str]:
    """Select safe, middle, and strongest-likelihood candidates per hierarchy."""
    eligible: list[dict[str, Any]] = []
    for row in rows:
        checkpoint = str(row["checkpoint"])
        if not (
            row.get("improves_all_splits") is True
            and row.get("defensive_context_safe") is True
            and row.get("two_seed_repeatable") is True
            and Path(checkpoint).name.startswith("alpha")
        ):
            continue
        if checkpoint not in metadata:
            raise ValueError(f"missing checkpoint metadata: {checkpoint}")
        alpha, hierarchy = metadata[checkpoint]
        eligible.append({**row, "alpha": alpha, "hierarchy": hierarchy})

    selected: list[str] = []
    for hierarchy in ("slot", "play-gate"):
        hierarchy_rows = [
            row for row in eligible if row["hierarchy"] == hierarchy
        ]
        if not hierarchy_rows:
            continue
        safe_distance = min(
            abs(float(row["alpha"]) - safe_alpha) for row in hierarchy_rows
        )
        middle_distance = min(
            abs(float(row["alpha"]) - middle_alpha) for row in hierarchy_rows
        )
        strongest_improvement = max(
            float(row["mean_nll_improvement"]) for row in hierarchy_rows
        )
        strongest_alpha = max(
            (
                row
                for row in hierarchy_rows
                if float(row["mean_nll_improvement"]) == strongest_improvement
            ),
            key=lambda row: float(row["alpha"]),
        )["alpha"]
        selected_alphas = {
            float(row["alpha"])
            for row in hierarchy_rows
            if abs(float(row["alpha"]) - safe_alpha) == safe_distance
            or abs(float(row["alpha"]) - middle_alpha) == middle_distance
            or float(row["alpha"]) == float(strongest_alpha)
        }
        selected_rows = sorted(
            (
                row
                for row in hierarchy_rows
                if float(row["alpha"]) in selected_alphas
            ),
            key=lambda row: (
                float(row["alpha"]),
                -float(row["mean_nll_improvement"]),
                str(row["checkpoint"]),
            ),
        )
        for row in selected_rows:
            checkpoint = str(row["checkpoint"])
            if checkpoint not in selected:
                selected.append(checkpoint)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--safe-alpha", type=float, default=0.0625)
    parser.add_argument("--middle-alpha", type=float, default=0.50)
    args = parser.parse_args()

    payload = json.loads(args.summary.read_text(encoding="utf-8"))
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        raise TypeError("blend summary needs a candidate list")
    checkpoint_paths = {
        str(row["checkpoint"]): Path(row["checkpoint"])
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("checkpoint"), str)
        and Path(row["checkpoint"]).name.startswith("alpha")
        and row.get("improves_all_splits") is True
        and row.get("defensive_context_safe") is True
        and row.get("two_seed_repeatable") is True
    }
    metadata = {
        checkpoint: _checkpoint_metadata(path)
        for checkpoint, path in checkpoint_paths.items()
    }
    candidates = select_gameplay_candidates(
        rows,
        metadata=metadata,
        safe_alpha=args.safe_alpha,
        middle_alpha=args.middle_alpha,
    )
    if not candidates:
        raise SystemExit("no blend improves action-type NLL on every held-out split")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(candidates) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "gameplay_candidates_ready",
                "count": len(candidates),
                "candidates": candidates,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
