"""Fail-closed finalization for the bounded TV Royale diversified-RL pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def _same_path(left: object, right: Path) -> bool:
    return isinstance(left, str) and Path(left).expanduser().resolve() == right.resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finalize_rl_pilot(
    *,
    pilot_root: Path,
    candidate: Path,
    parent: Path,
    deck_exclusion_manifest: Path,
    promotion_candidate_path: Path,
) -> dict[str, Any]:
    promotion_candidate_path.parent.mkdir(parents=True, exist_ok=True)
    promotion_candidate_path.write_text("", encoding="utf-8")
    candidate = candidate.expanduser().resolve()
    parent = parent.expanduser().resolve()
    if not candidate.is_file() or not parent.is_file():
        raise FileNotFoundError("RL candidate and parent checkpoints must both exist")

    direct = _load(pilot_root / "direct_summary.json")
    priority = _load(pilot_root / "priority_summary.json")
    full168 = _load(pilot_root / "full168_summary.json")
    stability = _load(pilot_root / "training_stability.json")
    state_audit = _load(pilot_root / "state_dict_audit.json")
    exclusion = _load(deck_exclusion_manifest)
    view_payloads = {
        view: _load(pilot_root / f"human_meta_{view}64.metrics.json")
        for view in ("uniform", "frequency_weighted")
    }
    views = {view: payload["metrics"] for view, payload in view_payloads.items()}
    wins = sum(int(row["wins"]) for row in views.values())
    losses = sum(int(row["losses"]) for row in views.values())
    draws = sum(int(row["draws"]) for row in views.values())
    human_meta_games = sum(int(row["games"]) for row in views.values())

    summary_consistency = all(
        _same_path(summary.get("checkpoint"), candidate)
        and _same_path(summary.get("parent"), parent)
        for summary in (direct, priority, full168)
    )
    view_consistency = all(
        _same_path(payload.get("checkpoint"), candidate)
        and _same_path(payload.get("opponent_checkpoint"), parent)
        and payload.get("mirror_match") is True
        and int(payload.get("metrics", {}).get("games", 0)) == 64
        for payload in view_payloads.values()
    )
    exclusion_output = Path(str(exclusion.get("output", ""))).expanduser().resolve()
    exclusion_verified = (
        int(exclusion.get("retained_exclusion_overlap", -1)) == 0
        and int(exclusion.get("excluded_decks", 0)) > 0
        and int(exclusion.get("retained_decks", 0)) > 0
        and exclusion_output.is_file()
        and _sha256(exclusion_output) == exclusion.get("output_sha256")
    )
    gates = {
        "checkpoint_consistency": summary_consistency and view_consistency,
        "training_stability": (
            stability.get("passes") is True
            and int(stability.get("start_update", -1)) == 41
            and int(stability.get("end_update", -1)) == 44
            and int(stability.get("updates", -1)) == 4
            and int(stability.get("transition_delta", -1)) == 16_384
            and _same_path(stability.get("parent"), parent)
        ),
        "actor_and_value_changed_only": (
            state_audit.get("passes") is True
            and int(state_audit.get("actor_changed_parameter_count", 0)) > 0
            and int(state_audit.get("value_changed_parameter_count", 0)) > 0
            and state_audit.get("unauthorized_changes") == []
            and _same_path(state_audit.get("before"), parent)
            and _same_path(state_audit.get("after"), candidate)
        ),
        "human_meta_excluded_from_training": exclusion_verified,
        "direct_parent_improvement": (
            int(direct.get("games", 0)) == 48
            and direct.get("earns_priority_screen") is True
            and int(direct.get("wins", 0)) > int(direct.get("losses", 0))
        ),
        "priority_no_regression": (
            int(priority.get("games", 0)) == 60
            and priority.get("passes_strict_no_regression") is True
        ),
        "full168_no_regression": (
            int(full168.get("games", 0)) == 168
            and full168.get("passes_strict_no_regression") is True
        ),
        "human_meta_parent_improvement": (
            human_meta_games == 128
            and wins > losses
            and all(int(row["wins"]) >= int(row["losses"]) for row in views.values())
        ),
    }
    eligible = all(gates.values())
    payload = {
        "schema_version": 2,
        "status": "rl_pilot_promotion_candidate_ready" if eligible else "rl_pilot_rejected",
        "promotion_eligible": eligible,
        "checkpoint": str(candidate),
        "parent": str(parent),
        "training_pool_excluded_human_meta_signatures": exclusion_verified,
        "games": human_meta_games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "crown_difference": sum(
            float(row["crown_diff_per_game"]) * int(row["games"])
            for row in views.values()
        ),
        "passes_human_meta_gate": gates["human_meta_parent_improvement"],
        "views": views,
        "gates": gates,
    }
    if eligible:
        promotion_candidate_path.write_text(str(candidate) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-root", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--deck-exclusion-manifest", required=True, type=Path)
    parser.add_argument("--promotion-candidate", required=True, type=Path)
    parser.add_argument("--summary-out", required=True, type=Path)
    args = parser.parse_args()
    payload = finalize_rl_pilot(
        pilot_root=args.pilot_root,
        candidate=args.candidate,
        parent=args.parent,
        deck_exclusion_manifest=args.deck_exclusion_manifest,
        promotion_candidate_path=args.promotion_candidate,
    )
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
