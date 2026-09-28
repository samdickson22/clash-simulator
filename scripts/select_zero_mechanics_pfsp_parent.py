"""Select a neutral mechanics PFSP parent from matched gameplay baselines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.finalize_mechanics_slot_gameplay_gate import (
    PAIRED_WORKLOADS,
    _object,
    _sha256,
)


def _verify_summary(path: Path) -> dict[str, Any]:
    payload = _object(path)
    checks = {
        "schema": payload.get("schema") == "zero-mechanics-rl-initializer-v1",
        "eligible": payload.get("rl_initializer_eligible") is True,
        "baseline_games": int(payload.get("baseline_games", -1)) == 72,
        "checkpoint_exists": Path(
            str(payload.get("candidate_checkpoint", ""))
        ).is_file(),
    }
    checkpoint = Path(str(payload.get("candidate_checkpoint", "")))
    if checkpoint.is_file():
        checks["checkpoint_sha256"] = payload.get(
            "candidate_checkpoint_sha256"
        ) == _sha256(checkpoint)
    evidence = payload.get("evidence_sha256")
    if not isinstance(evidence, dict) or not evidence:
        checks["evidence"] = False
    else:
        for evidence_path, expected_sha in evidence.items():
            target = Path(evidence_path)
            checks[f"evidence:{target.name}"] = (
                target.is_file() and _sha256(target) == expected_sha
            )
    metrics = payload.get("workload_metrics")
    checks["workloads"] = isinstance(metrics, dict) and set(metrics) == set(
        PAIRED_WORKLOADS
    )
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"initializer summary failed validation: {path}: {failed}")
    return payload


def _score(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = summary["workload_metrics"]
    total_wins = sum(int(metrics[name]["wins"]) for name in PAIRED_WORKLOADS)
    total_losses = sum(int(metrics[name]["losses"]) for name in PAIRED_WORKLOADS)
    total_draws = sum(int(metrics[name]["draws"]) for name in PAIRED_WORKLOADS)
    weighted_noop = (
        sum(
            float(metrics[name]["candidate_noop_when_playable"])
            * int(metrics[name]["games"])
            for name in PAIRED_WORKLOADS
        )
        / 72
    )
    return {
        "wins": total_wins,
        "losses": total_losses,
        "draws": total_draws,
        "crown_difference": sum(
            float(metrics[name]["crown_diff_per_game"]) * int(metrics[name]["games"])
            for name in PAIRED_WORKLOADS
        ),
        "weighted_playable_noop": weighted_noop,
        "worst_playable_noop": max(
            float(metrics[name]["candidate_noop_when_playable"])
            for name in PAIRED_WORKLOADS
        ),
        "random_wins": int(metrics["random12"]["wins"]),
        "hog_wins": int(metrics["hog12"]["wins"]),
        "hog_gate": summary["hog"].get("gate", {}).get("passed") is True,
        "hog_zero_use_games": int(summary["hog"]["zero_use_games"]),
        "hog_window_conversion_rate": float(summary["hog"]["window_conversion_rate"]),
        "hog_mean_role_probability": float(
            summary["hog"]["mean_role_probability_when_legal_affordable"]
        ),
    }


def select_parent(
    *,
    incumbent_summary: Path,
    challenger_summary: Path,
) -> dict[str, Any]:
    incumbent = _verify_summary(incumbent_summary)
    challenger = _verify_summary(challenger_summary)
    before = _score(incumbent)
    after = _score(challenger)
    gates = {
        "matched_72_game_protocol": True,
        "winning_aggregate": after["wins"] > after["losses"],
        "large_incumbent_improvement": after["wins"] >= before["wins"] + 12,
        "random_robustness": after["random_wins"] >= 8,
        "meaningful_passivity_reduction": after["weighted_playable_noop"]
        <= before["weighted_playable_noop"] - 0.10,
        "no_frozen_workload": after["worst_playable_noop"] <= 0.90,
        "hog_utilization": after["hog_gate"],
        "hog_zero_use": after["hog_zero_use_games"] <= 1,
    }
    selected = all(gates.values())
    broad_ready = all(
        passed
        for name, passed in gates.items()
        if name not in {"hog_utilization", "hog_zero_use"}
    )
    targeted_hog_defect = (
        not after["hog_gate"]
        and 2 <= after["hog_zero_use_games"] <= 4
        and after["hog_window_conversion_rate"] >= 0.50
        and after["hog_mean_role_probability"] >= 0.50
    )
    repair_pilot_authorized = broad_ready and targeted_hog_defect
    return {
        "schema": "zero-mechanics-pfsp-parent-selection-v3",
        "status": (
            "challenger_selected"
            if selected
            else "targeted_repair_pilot_authorized"
            if repair_pilot_authorized
            else "rejected"
        ),
        "challenger_selected": selected,
        "repair_pilot_authorized": repair_pilot_authorized,
        "targeted_hog_defect": targeted_hog_defect,
        "incumbent_summary": str(incumbent_summary.resolve()),
        "incumbent_summary_sha256": _sha256(incumbent_summary),
        "challenger_summary": str(challenger_summary.resolve()),
        "challenger_summary_sha256": _sha256(challenger_summary),
        "incumbent_checkpoint": incumbent["candidate_checkpoint"],
        "incumbent_checkpoint_sha256": incumbent["candidate_checkpoint_sha256"],
        "challenger_checkpoint": challenger["candidate_checkpoint"],
        "challenger_checkpoint_sha256": challenger["candidate_checkpoint_sha256"],
        "incumbent": before,
        "challenger": after,
        "gates": gates,
        "claim_scope": (
            "selects a passing parent or authorizes a bounded mechanics-only repair "
            "pilot for one measured Hog-use defect; it is not a promoted-policy or "
            "human-skill claim"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incumbent-summary", required=True, type=Path)
    parser.add_argument("--challenger-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = select_parent(
        incumbent_summary=args.incumbent_summary,
        challenger_summary=args.challenger_summary,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
