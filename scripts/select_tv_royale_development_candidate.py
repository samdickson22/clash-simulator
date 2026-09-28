"""Summarize a TV Royale development screen and choose a safety-first winner."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from pathlib import Path
from typing import Any

import torch

from clasher.rl.model import PolicyConfig

DEVELOPMENT_SPLITS = ("validation12", "heldout12")


def load_development_screen_rows(
    *,
    screen_root: Path,
    candidate_paths: list[Path],
    opponent_checkpoint: Path,
    sampling_decks: dict[str, Path],
    seeds: dict[str, int],
    games_per_split: int = 12,
) -> list[dict[str, Any]]:
    """Reopen exact paired evidence and reject stale/mismatched screen rows."""
    resolved_parent = opponent_checkpoint.resolve()
    seen_candidates: set[Path] = set()
    rows: list[dict[str, Any]] = []
    for candidate_path in candidate_paths:
        resolved_candidate = candidate_path.resolve()
        if resolved_candidate in seen_candidates:
            raise ValueError(f"duplicate development candidate: {candidate_path}")
        if not resolved_candidate.is_file():
            raise ValueError(f"development candidate does not exist: {candidate_path}")
        seen_candidates.add(resolved_candidate)
        slug = f"{candidate_path.parent.name}_{candidate_path.stem}"
        directory = screen_root / slug
        metrics = []
        for name in DEVELOPMENT_SPLITS:
            path = directory / f"{name}.metrics.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            metric = payload.get("metrics")
            if not isinstance(metric, dict):
                raise TypeError(f"development metrics missing payload: {path}")
            actual_games = int(metric.get("games", -1))
            outcome_games = sum(
                int(metric.get(key, -1)) for key in ("wins", "losses", "draws")
            )
            expected_decks = sampling_decks[name].resolve()
            mismatches = {
                "schema_version": (1, payload.get("schema_version")),
                "checkpoint": (resolved_candidate, Path(str(payload.get("checkpoint", ""))).resolve()),
                "opponent_mode": ("policy", payload.get("opponent_mode")),
                "opponent_checkpoint": (
                    resolved_parent,
                    Path(str(payload.get("opponent_checkpoint", ""))).resolve(),
                ),
                "sampling_decks_path": (
                    expected_decks,
                    Path(str(payload.get("sampling_decks_path", ""))).resolve(),
                ),
                "seed": (seeds[name], int(payload.get("seed", -1))),
                "reward_profile": ("defense-v2", payload.get("reward_profile")),
                "deterministic": (True, payload.get("deterministic")),
                "mirror_match": (True, payload.get("mirror_match")),
                "games": (games_per_split, actual_games),
                "outcome_games": (games_per_split, outcome_games),
            }
            failures = {
                key: {"expected": expected, "actual": actual}
                for key, (expected, actual) in mismatches.items()
                if actual != expected
            }
            if failures:
                raise ValueError(
                    f"development evidence mismatch for {path}: {failures}"
                )
            metrics.append(payload)
        rows.append(
            {
                "checkpoint": str(resolved_candidate),
                "wins": sum(int(row["metrics"]["wins"]) for row in metrics),
                "losses": sum(int(row["metrics"]["losses"]) for row in metrics),
                "draws": sum(int(row["metrics"]["draws"]) for row in metrics),
                "crown_difference": sum(
                    row["metrics"]["crown_diff_per_game"]
                    * row["metrics"]["games"]
                    for row in metrics
                ),
            }
        )
    return rows


def select_development_candidate(
    rows: list[dict[str, Any]],
    *,
    metadata: dict[str, tuple[float, str]],
    safe_alpha: float = 0.0625,
) -> dict[str, Any] | None:
    """Choose the winning candidate nearest a previously safe blend strength."""
    winning = [row for row in rows if int(row["wins"]) > int(row["losses"])]
    if not winning:
        return None
    annotated = []
    for row in winning:
        checkpoint = str(row["checkpoint"])
        if checkpoint not in metadata:
            raise ValueError(f"missing checkpoint metadata: {checkpoint}")
        alpha, hierarchy = metadata[checkpoint]
        annotated.append({**row, "alpha": alpha, "hierarchy": hierarchy})
    return min(
        annotated,
        key=lambda row: (
            abs(float(row["alpha"]) - safe_alpha),
            0 if row["hierarchy"] == "slot" else 1,
            -(int(row["wins"]) - int(row["losses"])),
            -float(row["crown_difference"]),
            str(row["checkpoint"]),
        ),
    )


def _metadata(checkpoint: Path) -> tuple[float, str]:
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    interpolation = payload.get("interpolation") or {}
    alpha = interpolation.get("alpha")
    if not isinstance(alpha, (int, float)):
        raise TypeError(f"blend checkpoint lacks interpolation alpha: {checkpoint}")
    hierarchy = PolicyConfig.from_dict(
        payload["model_config"]
    ).deterministic_hierarchy
    return float(alpha), hierarchy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen-root", required=True, type=Path)
    parser.add_argument("--candidate-list", required=True, type=Path)
    parser.add_argument("--selected-out", required=True, type=Path)
    parser.add_argument("--opponent-checkpoint", required=True, type=Path)
    parser.add_argument("--validation-decks", required=True, type=Path)
    parser.add_argument("--heldout-decks", required=True, type=Path)
    parser.add_argument("--safe-alpha", type=float, default=0.0625)
    args = parser.parse_args()

    candidate_paths = [
        Path(value)
        for value in args.candidate_list.read_text(encoding="utf-8").splitlines()
        if value
    ]
    rows = load_development_screen_rows(
        screen_root=args.screen_root,
        candidate_paths=candidate_paths,
        opponent_checkpoint=args.opponent_checkpoint,
        sampling_decks={
            "validation12": args.validation_decks,
            "heldout12": args.heldout_decks,
        },
        seeds={"validation12": 1046501, "heldout12": 1046502},
    )
    metadata = {
        str(row["checkpoint"]): _metadata(Path(row["checkpoint"])) for row in rows
    }
    selected = select_development_candidate(
        rows,
        metadata=metadata,
        safe_alpha=args.safe_alpha,
    )
    payload = {"schema_version": 1, "candidates": rows, "selected": selected}
    (args.screen_root / "development_screen_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.selected_out.parent.mkdir(parents=True, exist_ok=True)
    args.selected_out.write_text(
        "" if selected is None else str(selected["checkpoint"]) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": (
                    "no_candidate_earned_expanded_screen"
                    if selected is None
                    else "candidate_selected_for_expanded_screen"
                ),
                "selected": selected,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
