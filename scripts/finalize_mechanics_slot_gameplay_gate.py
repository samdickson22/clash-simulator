"""Fail-closed gameplay gate for a selected mechanics-slot RL initializer."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

PAIRED_WORKLOADS = (
    "random12",
    "balanced12",
    "reactive12",
    "bridge6",
    "slow6",
    "spell6",
    "split6",
    "hog12",
)

PAIRED_SPECS = {
    "random12": (12, 1056010, "random", None, "heldout"),
    "balanced12": (12, 1056011, "strategy", "balanced", "heldout"),
    "reactive12": (
        12,
        1056012,
        "strategy",
        "reactive-defense",
        "heldout",
    ),
    "bridge6": (6, 1056013, "strategy", "bridge-pressure", "heldout"),
    "slow6": (6, 1056014, "strategy", "slow-push", "heldout"),
    "spell6": (6, 1056015, "strategy", "spell-control", "heldout"),
    "split6": (6, 1056016, "strategy", "split-lane", "heldout"),
    "hog12": (12, 1056017, "strategy", "balanced", "hog"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _weighted_metric(
    rows: list[dict[str, Any]],
    *,
    value: str,
    weight: str,
) -> float:
    denominator = sum(float(row[weight]) for row in rows)
    if denominator <= 0.0:
        raise ValueError(f"cannot aggregate {value} without positive {weight}")
    return sum(float(row[value]) * float(row[weight]) for row in rows) / denominator


def _same_path(value: object, expected: Path) -> bool:
    return isinstance(value, str) and Path(value).resolve() == expected.resolve()


def _verify_eval_context(
    payload: dict[str, Any],
    *,
    checkpoint: Path,
    opponent_checkpoint: Path | None,
    decks_path: Path,
    games: int,
    seed: int,
    opponent_mode: str,
    opponent_strategy: str | None,
) -> dict[str, Any]:
    if int(payload.get("schema_version", -1)) != 1:
        raise ValueError("unsupported policy evaluation schema")
    expected = {
        "checkpoint": _same_path(payload.get("checkpoint"), checkpoint),
        "checkpoint_sha256": payload.get("checkpoint_sha256")
        == _sha256(checkpoint),
        "opponent_checkpoint": (
            payload.get("opponent_checkpoint") is None
            if opponent_checkpoint is None
            else _same_path(payload.get("opponent_checkpoint"), opponent_checkpoint)
        ),
        "opponent_checkpoint_sha256": (
            payload.get("opponent_checkpoint_sha256") is None
            if opponent_checkpoint is None
            else payload.get("opponent_checkpoint_sha256")
            == _sha256(opponent_checkpoint)
        ),
        "sampling_decks_path": _same_path(
            payload.get("sampling_decks_path"), decks_path
        ),
        "sampling_decks_sha256": payload.get("sampling_decks_sha256")
        == _sha256(decks_path),
        "games": int(payload.get("metrics", {}).get("games", -1)) == games,
        "seed": int(payload.get("seed", -1)) == seed,
        "mirror_match": payload.get("mirror_match") is True,
        "opponent_mode": payload.get("opponent_mode") == opponent_mode,
        "opponent_strategy": payload.get("opponent_strategy") == opponent_strategy,
        "reward_profile": payload.get("reward_profile") == "defense-v2",
    }
    failed = [name for name, passed in expected.items() if not passed]
    if failed:
        raise ValueError("policy evaluation provenance mismatch: " + ", ".join(failed))
    metrics = payload["metrics"]
    if not isinstance(metrics, dict):
        raise TypeError("policy evaluation metrics must be an object")
    outcomes: list[int] = []
    for name in ("wins", "losses", "draws"):
        value = float(metrics.get(name, -1.0))
        if not math.isfinite(value) or value < 0.0 or not value.is_integer():
            raise ValueError(f"policy evaluation has invalid {name}")
        outcomes.append(int(value))
    if sum(outcomes) != games:
        raise ValueError("policy evaluation outcome counts do not match games")
    crown_diff = float(metrics.get("crown_diff_per_game", math.nan))
    if not math.isfinite(crown_diff):
        raise ValueError("policy evaluation has invalid crown difference")
    return metrics


def _verify_comparison_context(
    payload: dict[str, Any],
    *,
    baseline: Path,
    candidate: Path,
    games: int,
) -> dict[str, Any]:
    if int(payload.get("schema_version", -1)) != 1:
        raise ValueError("unsupported matched-game comparison schema")
    checks = {
        "baseline": _same_path(payload.get("baseline"), baseline),
        "baseline_sha256": payload.get("baseline_sha256") == _sha256(baseline),
        "candidate": _same_path(payload.get("candidate"), candidate),
        "candidate_sha256": payload.get("candidate_sha256") == _sha256(candidate),
        "games": int(payload.get("games", -1)) == games,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("comparison provenance mismatch: " + ", ".join(failed))
    improvements = payload.get("improvements")
    regressions = payload.get("regressions")
    if not isinstance(improvements, list) or not isinstance(regressions, list):
        raise TypeError("comparison must enumerate improvements and regressions")
    improvement_count = int(payload.get("improvement_count", -1))
    regression_count = int(payload.get("regression_count", -1))
    unchanged_count = int(payload.get("unchanged_count", -1))
    if (
        improvement_count != len(improvements)
        or regression_count != len(regressions)
        or min(improvement_count, regression_count, unchanged_count) < 0
        or improvement_count + regression_count + unchanged_count != games
    ):
        raise ValueError("comparison outcome counts are inconsistent")
    if payload.get("passes_strict_no_regression") is not (regression_count == 0):
        raise ValueError("comparison no-regression flag is inconsistent")
    baseline_crowns = float(payload.get("baseline_crown_difference", math.nan))
    candidate_crowns = float(payload.get("candidate_crown_difference", math.nan))
    crown_change = float(payload.get("crown_difference_change", math.nan))
    if not all(math.isfinite(value) for value in (baseline_crowns, candidate_crowns, crown_change)):
        raise ValueError("comparison crown totals are invalid")
    if not math.isclose(
        crown_change,
        candidate_crowns - baseline_crowns,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError("comparison crown arithmetic is inconsistent")
    return payload


def finalize_gameplay_gate(
    *,
    root: Path,
    candidate_checkpoint: Path,
    parent_checkpoint: Path,
    validation_decks: Path,
    heldout_decks: Path,
    hog_decks: Path,
) -> dict[str, Any]:
    if not candidate_checkpoint.is_file() or not parent_checkpoint.is_file():
        raise FileNotFoundError("candidate and parent checkpoints must exist")
    materialized = _object(root.parent / "materialized_candidate_evaluation.json")
    if materialized.get("schema") != "mechanics-slot-materialized-evaluation-v1":
        raise ValueError("unsupported materialized evaluation schema")
    if (
        Path(materialized["candidate_checkpoint"]).resolve()
        != candidate_checkpoint.resolve()
    ):
        raise ValueError("materialized evaluation identifies another candidate")
    if not _same_path(materialized.get("parent_checkpoint"), parent_checkpoint):
        raise ValueError("materialized evaluation identifies another parent")
    if materialized.get("candidate_checkpoint_sha256") != _sha256(candidate_checkpoint):
        raise ValueError("candidate checkpoint changed after materialized evaluation")
    if materialized.get("parent_checkpoint_sha256") != _sha256(parent_checkpoint):
        raise ValueError("parent checkpoint changed after materialized evaluation")
    probe_checkpoint = Path(str(materialized.get("probe_checkpoint", "")))
    if not probe_checkpoint.is_file() or materialized.get(
        "probe_checkpoint_sha256"
    ) != _sha256(probe_checkpoint):
        raise ValueError("probe checkpoint is missing or changed")
    selection = _object(root.parent / "selection.json")
    if selection.get("schema") != "mechanics-slot-cross-seed-selection-v1":
        raise ValueError("unsupported mechanics selection schema")
    if selection.get("status") != "candidate_selected":
        raise ValueError("mechanics selection did not select a candidate")
    selected = selection.get("selected") or {}
    if float(materialized.get("alpha", -1.0)) != float(selected.get("alpha", -2.0)):
        raise ValueError("materialized alpha differs from selected alpha")
    if not _same_path(
        materialized.get("probe_checkpoint"),
        Path(str((selected.get("median_seed") or {}).get("probe", ""))),
    ):
        raise ValueError("materialized probe differs from selected median seed")
    if materialized.get("selection_splits") != [
        "simulator_validation",
        "simulator_heldout",
        "human_validation",
    ]:
        raise ValueError("materialized selection split declaration changed")
    if materialized.get("post_selection_evaluation_only_splits") != [
        "human_archetype_test",
        "human_chronology_test",
    ]:
        raise ValueError("materialized held-out split declaration changed")

    direct_rows: list[dict[str, Any]] = []
    for split, decks_path, seed in (
        ("validation", validation_decks, 1056001),
        ("heldout", heldout_decks, 1056002),
    ):
        direct_rows.append(
            _verify_eval_context(
                _object(root / f"direct_{split}12.metrics.json"),
                checkpoint=candidate_checkpoint,
                opponent_checkpoint=parent_checkpoint,
                decks_path=decks_path,
                games=12,
                seed=seed,
                opponent_mode="policy",
                opponent_strategy=None,
            )
        )
    direct_games = sum(int(row["games"]) for row in direct_rows)
    direct_wins = sum(int(row["wins"]) for row in direct_rows)
    direct_losses = sum(int(row["losses"]) for row in direct_rows)
    direct_crowns = sum(
        float(row["crown_diff_per_game"]) * int(row["games"]) for row in direct_rows
    )
    comparisons: dict[str, dict[str, Any]] = {}
    paired_metrics: dict[str, dict[str, dict[str, Any]]] = {
        "parent": {},
        "candidate": {},
    }
    for name in PAIRED_WORKLOADS:
        games, seed, opponent_mode, opponent_strategy, deck_group = PAIRED_SPECS[name]
        decks_path = hog_decks if deck_group == "hog" else heldout_decks
        for role, checkpoint in (
            ("parent", parent_checkpoint),
            ("candidate", candidate_checkpoint),
        ):
            paired_metrics[role][name] = _verify_eval_context(
                _object(root / f"{role}_{name}.metrics.json"),
                checkpoint=checkpoint,
                opponent_checkpoint=None,
                decks_path=decks_path,
                games=games,
                seed=seed,
                opponent_mode=opponent_mode,
                opponent_strategy=opponent_strategy,
            )
        comparisons[name] = _verify_comparison_context(
            _object(root / f"{name}.compare.json"),
            baseline=root / f"parent_{name}.games.json",
            candidate=root / f"candidate_{name}.games.json",
            games=games,
        )
    comparison_games = sum(int(row["games"]) for row in comparisons.values())

    parent_defense = [
        paired_metrics["parent"][name] for name in ("balanced12", "reactive12")
    ]
    candidate_defense = [
        paired_metrics["candidate"][name] for name in ("balanced12", "reactive12")
    ]
    parent_success = _weighted_metric(
        parent_defense,
        value="defense_event_success_rate",
        weight="defense_events_resolved",
    )
    candidate_success = _weighted_metric(
        candidate_defense,
        value="defense_event_success_rate",
        weight="defense_events_resolved",
    )
    parent_outcome = _weighted_metric(
        parent_defense,
        value="defense_event_mean_outcome",
        weight="defense_events_resolved",
    )
    candidate_outcome = _weighted_metric(
        candidate_defense,
        value="defense_event_mean_outcome",
        weight="defense_events_resolved",
    )
    parent_noop = _weighted_metric(
        parent_defense,
        value="candidate_noop_when_playable",
        weight="games",
    )
    candidate_noop = _weighted_metric(
        candidate_defense,
        value="candidate_noop_when_playable",
        weight="games",
    )

    parent_hog = _object(root / "parent_hog12.utilization.json")
    candidate_hog = _object(root / "candidate_hog12.utilization.json")
    for role, utilization in (("parent", parent_hog), ("candidate", candidate_hog)):
        decisions_path = root / f"{role}_hog12.decisions.json"
        games_path = root / f"{role}_hog12.games.json"
        if not _same_path(
            utilization.get("decisions"), decisions_path
        ) or utilization.get("decisions_sha256") != _sha256(decisions_path):
            raise ValueError(f"{role} Hog utilization decision provenance mismatch")
        if not _same_path(
            utilization.get("game_records"), games_path
        ) or utilization.get("game_records_sha256") != _sha256(games_path):
            raise ValueError(f"{role} Hog utilization game provenance mismatch")
    final_metrics = materialized["metrics"]
    heldout_metrics = [
        final_metrics["human_archetype_test"],
        final_metrics["human_chronology_test"],
    ]
    gates = {
        "candidate_checkpoint_exists": candidate_checkpoint.is_file(),
        "parent_checkpoint_exists": parent_checkpoint.is_file(),
        "direct_evidence_count": direct_games == 24,
        "direct_not_losing": direct_wins >= direct_losses and direct_crowns >= 0.0,
        "paired_evidence_count": comparison_games == 72,
        "strict_outcome_no_regression": all(
            row.get("passes_strict_no_regression") is True
            for row in comparisons.values()
        ),
        "aggregate_crown_no_regression": sum(
            float(row["crown_difference_change"]) for row in comparisons.values()
        )
        >= 0.0,
        "defense_success_no_regression": candidate_success >= parent_success - 0.02,
        "defense_outcome_no_regression": candidate_outcome >= parent_outcome - 0.02,
        "passivity_no_regression": candidate_noop <= parent_noop + 0.02,
        "hog_absolute_gate": candidate_hog.get("gate", {}).get("passed") is True,
        "hog_zero_use_no_regression": int(candidate_hog["zero_use_games"])
        <= int(parent_hog["zero_use_games"]),
        "hog_conversion_no_regression": float(candidate_hog["window_conversion_rate"])
        >= float(parent_hog["window_conversion_rate"]) - 0.05,
        "hog_probability_no_regression": float(
            candidate_hog["mean_role_probability_when_legal_affordable"]
        )
        >= float(parent_hog["mean_role_probability_when_legal_affordable"]) - 0.05,
        "human_archetype_and_chronology_no_regression": all(
            float(row["accuracy_gain"]) >= 0.0 for row in heldout_metrics
        ),
        "materialized_logit_parity": all(
            row.get("materialized_logit_parity") is True
            for row in final_metrics.values()
        ),
    }
    eligible = all(gates.values())
    evidence_paths = [
        root.parent / "materialized_candidate_evaluation.json",
        root.parent / "selection.json",
        *(
            root / f"direct_{split}12.metrics.json"
            for split in ("validation", "heldout")
        ),
        *(root / f"direct_{split}12.games.json" for split in ("validation", "heldout")),
    ]
    for name in PAIRED_WORKLOADS:
        evidence_paths.extend(
            [
                root / f"parent_{name}.metrics.json",
                root / f"candidate_{name}.metrics.json",
                root / f"parent_{name}.games.json",
                root / f"candidate_{name}.games.json",
                root / f"{name}.compare.json",
            ]
        )
    evidence_paths.extend(
        [
            root / "parent_hog12.decisions.json",
            root / "candidate_hog12.decisions.json",
            root / "parent_hog12.utilization.json",
            root / "candidate_hog12.utilization.json",
        ]
    )
    return {
        "schema": "mechanics-slot-gameplay-gate-v1",
        "status": "rl_initializer_ready" if eligible else "rejected",
        "rl_initializer_eligible": eligible,
        "candidate_checkpoint": str(candidate_checkpoint.resolve()),
        "candidate_checkpoint_sha256": _sha256(candidate_checkpoint),
        "parent_checkpoint": str(parent_checkpoint.resolve()),
        "parent_checkpoint_sha256": _sha256(parent_checkpoint),
        "gates": gates,
        "direct": {
            "games": direct_games,
            "wins": direct_wins,
            "losses": direct_losses,
            "crown_difference": direct_crowns,
        },
        "paired": {
            "games": comparison_games,
            "improvements": sum(
                int(row["improvement_count"]) for row in comparisons.values()
            ),
            "regressions": sum(
                int(row["regression_count"]) for row in comparisons.values()
            ),
            "crown_difference_change": sum(
                float(row["crown_difference_change"]) for row in comparisons.values()
            ),
            "workloads": comparisons,
        },
        "defense": {
            "parent_success_rate": parent_success,
            "candidate_success_rate": candidate_success,
            "parent_mean_outcome": parent_outcome,
            "candidate_mean_outcome": candidate_outcome,
            "parent_playable_noop": parent_noop,
            "candidate_playable_noop": candidate_noop,
        },
        "hog": {"parent": parent_hog, "candidate": candidate_hog},
        "evidence_sha256": {
            str(path.resolve()): _sha256(path) for path in evidence_paths
        },
        "claim_scope": (
            "eligible only as diversified league RL initialization; "
            "not a promoted policy or human-skill claim"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--candidate-checkpoint", required=True, type=Path)
    parser.add_argument("--parent-checkpoint", required=True, type=Path)
    parser.add_argument("--validation-decks", required=True, type=Path)
    parser.add_argument("--heldout-decks", required=True, type=Path)
    parser.add_argument("--hog-decks", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = finalize_gameplay_gate(
        root=args.root,
        candidate_checkpoint=args.candidate_checkpoint,
        parent_checkpoint=args.parent_checkpoint,
        validation_decks=args.validation_decks,
        heldout_decks=args.heldout_decks,
        hog_decks=args.hog_decks,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
