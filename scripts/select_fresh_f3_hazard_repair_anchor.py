#!/usr/bin/env python3
"""Select the only mixed-league checkpoint eligible for a repair A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CANDIDATES = (23, 24, 29, 30)


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select(*, series_root: Path, anchor_root: Path, checkpoint_dir: Path) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    evidence: list[Path] = []
    for update in CANDIDATES:
        checkpoint = checkpoint_dir / f"policy_v2_update_{update:06d}.pt"
        direct_path = series_root / f"update{update}.metrics.json"
        strategy_path = anchor_root / f"update{update}" / "strategy.json"
        random_path = anchor_root / f"update{update}" / "random24.metrics.json"
        hog_path = anchor_root / f"update{update}" / "hog12.metrics.json"
        for path in (checkpoint, direct_path, strategy_path, random_path, hog_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        direct = _object(direct_path)["metrics"]
        strategy = _object(strategy_path)["results"]
        random = _object(random_path)["metrics"]
        hog = _object(hog_path)["metrics"]
        row: dict[str, Any] = {
            "checkpoint": str(checkpoint.resolve()),
            "checkpoint_sha256": _sha256(checkpoint),
            "direct": {
                "wins": float(direct["wins"]),
                "losses": float(direct["losses"]),
                "wins_as_player0": float(direct["wins_as_player0"]),
                "wins_as_player1": float(direct["wins_as_player1"]),
                "crown_difference": float(direct["crown_diff_per_game"]) * 24,
                "noop_when_playable": float(direct["candidate_noop_when_playable"]),
            },
            "strategy": {
                "wins": sum(float(result["wins"]) for result in strategy.values()),
                "losses": sum(float(result["losses"]) for result in strategy.values()),
                "crown_difference": sum(
                    float(result["crown_diff_per_game"]) * 4
                    for result in strategy.values()
                ),
            },
            "random": {
                "wins": float(random["wins"]),
                "losses": float(random["losses"]),
            },
            "hog": {"wins": float(hog["wins"]), "losses": float(hog["losses"])},
        }
        reasons: list[str] = []
        if row["direct"]["wins"] < 15:
            reasons.append("direct_below_15_wins")
        if min(
            row["direct"]["wins_as_player0"], row["direct"]["wins_as_player1"]
        ) < 6:
            reasons.append("direct_seat_below_6_wins")
        if row["direct"]["noop_when_playable"] >= 0.95:
            reasons.append("playable_noop_at_or_above_95_percent")
        row["rejection_reasons"] = reasons
        rows[str(update)] = row
        evidence.extend((checkpoint, direct_path, strategy_path, random_path, hog_path))

    endpoint = rows["30"]
    eligible = [
        update
        for update in CANDIDATES
        if not rows[str(update)]["rejection_reasons"]
        and rows[str(update)]["strategy"]["wins"]
        >= endpoint["strategy"]["wins"] - 1
        and rows[str(update)]["random"]["wins"] >= endpoint["random"]["wins"] - 2
        and rows[str(update)]["hog"]["wins"] >= endpoint["hog"]["wins"]
    ]
    selected = max(
        eligible,
        key=lambda update: (
            rows[str(update)]["direct"]["wins"],
            rows[str(update)]["direct"]["crown_difference"],
            rows[str(update)]["strategy"]["wins"],
        ),
    ) if eligible else None
    return {
        "schema": "clasher.fresh_f3_hazard_repair_anchor.v1",
        "candidates": rows,
        "eligible_updates": eligible,
        "selected_update": selected,
        "selected_checkpoint": None if selected is None else rows[str(selected)]["checkpoint"],
        "repair_ab_authorized": selected is not None,
        "promotion_authorized": False,
        "evidence_sha256": {str(path.resolve()): _sha256(path) for path in evidence},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--series-root", required=True, type=Path)
    parser.add_argument("--anchor-root", required=True, type=Path)
    parser.add_argument("--checkpoint-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = select(
        series_root=args.series_root,
        anchor_root=args.anchor_root,
        checkpoint_dir=args.checkpoint_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
