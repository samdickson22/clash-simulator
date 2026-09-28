#!/usr/bin/env python3
"""Resolve the parent-heavy random safety confirmation without reusing its seed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _random_row(payload: dict[str, Any]) -> dict[str, float]:
    metrics = payload["metrics"]
    games = int(metrics["games"])
    return {
        "games": float(games),
        "wins": float(metrics["wins"]),
        "losses": float(metrics["losses"]),
        "crown_difference": float(metrics["crown_diff_per_game"]) * games,
        "noop_when_playable": float(metrics["candidate_noop_when_playable"]),
    }


def finalize(
    *,
    initial_decision_path: Path,
    confirmation_root: Path,
    output: Path,
) -> dict[str, Any]:
    initial = _object(initial_decision_path)
    if initial.get("selected") != "anchor":
        raise ValueError("initial decision must retain anchor pending confirmation")
    if initial.get("random_confirmation_authorized") is not True:
        raise ValueError("initial decision did not authorize random confirmation")
    if initial["arms"]["plain"].get("rejection_reasons") != ["random_regression"]:
        raise ValueError("plain arm must have exactly the random regression blocker")

    paths = {
        arm: confirmation_root / f"{arm}.metrics.json"
        for arm in ("anchor", "plain")
    }
    initial_random_paths = {
        arm: initial_decision_path.parent / arm / "random24.metrics.json"
        for arm in ("anchor", "plain")
    }
    payloads = {arm: _object(path) for arm, path in paths.items()}
    initial_random_payloads = {
        arm: _object(path) for arm, path in initial_random_paths.items()
    }
    for arm, payload in payloads.items():
        expected = initial["arms"][arm]["checkpoint_sha256"]
        if payload.get("checkpoint_sha256") != expected:
            raise ValueError(f"{arm} confirmation checkpoint changed")
        if int(payload.get("seed", -1)) != 1_070_101:
            raise ValueError(f"{arm} confirmation seed changed")
        if payload.get("opponent_mode") != "random" or not payload.get("mirror_match"):
            raise ValueError(f"{arm} confirmation protocol changed")
        if int(payload["metrics"]["games"]) != 48:
            raise ValueError(f"{arm} confirmation must contain 48 games")
    if (
        payloads["anchor"].get("sampling_decks_sha256")
        != payloads["plain"].get("sampling_decks_sha256")
    ):
        raise ValueError("confirmation arms used different deck pools")

    rows = {arm: _random_row(payload) for arm, payload in payloads.items()}
    initial_rows = {
        arm: _random_row(payload)
        for arm, payload in initial_random_payloads.items()
    }
    combined: dict[str, dict[str, float]] = {}
    for arm in ("anchor", "plain"):
        initial_random = initial_rows[arm]
        combined[arm] = {
            "games": initial_random["games"] + rows[arm]["games"],
            "wins": float(initial_random["wins"]) + rows[arm]["wins"],
            "losses": float(initial_random["losses"]) + rows[arm]["losses"],
            "crown_difference": (
                initial_random["crown_difference"] + rows[arm]["crown_difference"]
            ),
        }

    reasons: list[str] = []
    if rows["plain"]["wins"] < rows["anchor"]["wins"] - 1:
        reasons.append("confirmation_random_regression")
    if combined["plain"]["wins"] < combined["anchor"]["wins"] - 1:
        reasons.append("combined_random_regression")
    if combined["plain"]["crown_difference"] < combined["anchor"]["crown_difference"]:
        reasons.append("combined_crown_regression")
    if rows["plain"]["noop_when_playable"] >= 0.95:
        reasons.append("playable_noop_at_or_above_95_percent")
    passed = not reasons
    selected = "plain" if passed else "anchor"
    payload = {
        "schema": "clasher.fresh_f3_hazard_parentheavy_random_confirmation.v1",
        "initial_decision": str(initial_decision_path.resolve()),
        "confirmation": rows,
        "combined_random": combined,
        "plain_rejection_reasons": reasons,
        "selected": selected,
        "development_parent_authorized": passed,
        "hog_specialist_curriculum_authorized": passed,
        "fresh_quarantine_evaluation_authorized": False,
        "promotion_authorized": False,
        "evidence_sha256": {
            str(initial_decision_path.resolve()): _sha256(initial_decision_path),
            **{
                str(path.resolve()): _sha256(path)
                for path in initial_random_paths.values()
            },
            **{str(path.resolve()): _sha256(path) for path in paths.values()},
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-decision", required=True, type=Path)
    parser.add_argument("--confirmation-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            finalize(
                initial_decision_path=args.initial_decision,
                confirmation_root=args.confirmation_root,
                output=args.output,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
