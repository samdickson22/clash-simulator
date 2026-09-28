"""Fail-closed finalizer for the bounded mechanics-slot PFSP pilot."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from scripts.evaluate_win_condition_utilization import (
    promotion_gate as win_condition_promotion_gate,
)
from scripts.evaluate_win_condition_utilization import summarize_utilization
from scripts.finalize_mechanics_slot_gameplay_gate import (
    PAIRED_SPECS,
    PAIRED_WORKLOADS,
    _object,
    _same_path,
    _sha256,
    _verify_comparison_context,
    _verify_eval_context,
    _weighted_metric,
)
from scripts.finalize_win_condition_utilization_matrix import (
    finalize_win_condition_matrix,
)


def _verify_strategy_report(
    payload: dict[str, Any],
    *,
    checkpoint: Path,
    sampling_decks: Path,
) -> dict[str, Any]:
    candidate = payload.get("candidate") or {}
    protocol = payload.get("protocol") or {}
    if int(payload.get("schema_version", -1)) != 1:
        raise ValueError("unsupported strategy benchmark schema")
    expected_opponents = {
        "bridge-pressure",
        "slow-push",
        "spell-control",
        "reactive-defense",
        "split-lane",
        "balanced",
    }
    checks = {
        "checkpoint": _same_path(candidate.get("checkpoint"), checkpoint),
        "checkpoint_sha256": candidate.get("checkpoint_sha256") == _sha256(checkpoint),
        "sampling_decks": _same_path(
            protocol.get("sampling_decks_path"), sampling_decks
        ),
        "sampling_decks_sha256": protocol.get("sampling_decks_sha256")
        == _sha256(sampling_decks),
        "games_per_opponent": int(protocol.get("games_per_opponent", -1)) == 6,
        "seed": int(protocol.get("seed", -1)) == 1056201,
        "reward_profile": protocol.get("reward_profile") == "defense-v2",
        "paired_seats": protocol.get("paired_seats") is True,
        "public_information": protocol.get("public_information_only") is True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("strategy benchmark provenance mismatch: " + ", ".join(failed))
    results = payload.get("results")
    if not isinstance(results, dict) or set(results) != expected_opponents:
        raise ValueError("strategy benchmark must contain all six opponents")
    for name, row in results.items():
        if not isinstance(row, dict):
            raise TypeError(f"strategy result must be an object: {name}")
        score = float(row.get("score_rate", math.nan))
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(f"strategy result has invalid score rate: {name}")
    return payload


def _verify_human_evaluation(
    payload: dict[str, Any],
    *,
    corpus: Path,
    sidecar: Path,
    parent: Path,
    candidate: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if int(payload.get("schema_version", -1)) != 1:
        raise ValueError("unsupported recurrent-corpus evaluation schema")
    checks = {
        "corpus": _same_path(payload.get("corpus"), corpus),
        "corpus_sha256": payload.get("corpus_sha256") == _sha256(corpus),
        "sidecar": _same_path(payload.get("public_observation_sidecar"), sidecar),
        "sidecar_sha256": payload.get("public_observation_sidecar_sha256")
        == _sha256(sidecar),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("human evaluation provenance mismatch: " + ", ".join(failed))
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise ValueError("human evaluation must compare exactly parent and candidate")
    for row, checkpoint in zip(results, (parent, candidate), strict=True):
        if not _same_path(row.get("checkpoint"), checkpoint) or row.get(
            "checkpoint_sha256"
        ) != _sha256(checkpoint):
            raise ValueError("human evaluation checkpoint provenance mismatch")
    return results[0], results[1]


def _hog_slot_coverage_passes(payload: dict[str, Any]) -> bool:
    """Require the role card to be used from every hand slot it occupies."""

    by_slot = payload.get("by_slot")
    if not isinstance(by_slot, dict) or set(by_slot) != {"0", "1", "2", "3"}:
        return False
    for slot in ("0", "1", "2", "3"):
        row = by_slot.get(slot)
        if not isinstance(row, dict):
            return False
        legal = int(row.get("legal_affordable_decisions", -1))
        plays = int(row.get("plays", 0))
        if legal < 2 or plays < 1 or plays > legal or plays / legal < 0.25:
            return False
    return True


def _verify_hog_utilization(
    payload: dict[str, Any],
    *,
    decisions_path: Path,
    games_path: Path,
) -> dict[str, Any]:
    if not _same_path(payload.get("decisions"), decisions_path) or payload.get(
        "decisions_sha256"
    ) != _sha256(decisions_path):
        raise ValueError("Hog utilization decision provenance mismatch")
    if not _same_path(payload.get("game_records"), games_path) or payload.get(
        "game_records_sha256"
    ) != _sha256(games_path):
        raise ValueError("Hog utilization game provenance mismatch")
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    games = json.loads(games_path.read_text(encoding="utf-8"))
    if not isinstance(decisions, list) or not isinstance(games, list):
        raise TypeError("Hog decision and game records must be arrays")
    expected = summarize_utilization(
        decisions,
        games,
        role="primary_building_target",
        decision_seconds=0.4,
    )
    expected["gate"] = win_condition_promotion_gate(
        expected,
        max_zero_use_rate=0.10,
        min_window_conversion_rate=0.25,
        min_games_per_seat=5,
    )
    expected.update(
        {
            "decisions": str(decisions_path.resolve()),
            "decisions_sha256": _sha256(decisions_path),
            "game_records": str(games_path.resolve()),
            "game_records_sha256": _sha256(games_path),
        }
    )
    if payload != expected:
        raise ValueError("Hog utilization report does not match its decision records")
    return payload


def finalize_pfsp_pilot(
    *,
    root: Path,
    initializer_root: Path,
    parent: Path,
    candidate: Path,
    train_pool: Path,
    balance_report: Path,
    exclusion_manifest: Path,
    pfsp_sampling_decks: Path,
    pfsp_exclusion_manifest: Path,
    validation_decks: Path,
    heldout_decks: Path,
    hog_decks: Path,
    win_condition_root: Path,
    win_condition_manifest: Path,
    human_splits: dict[str, tuple[Path, Path]],
    start_update: int = 0,
    end_update: int = 4,
    expected_actor_prefixes: tuple[str, ...] = (
        "action_type_head.",
        "mechanics_slot_choice_query.",
    ),
) -> dict[str, Any]:
    if start_update < 0 or end_update <= start_update:
        raise ValueError("PFSP update interval must be positive and increasing")
    update_count = end_update - start_update
    if not parent.is_file() or not candidate.is_file():
        raise FileNotFoundError("PFSP parent and candidate checkpoints must exist")
    initializer = _object(initializer_root / "summary.json")
    if initializer.get("rl_initializer_eligible") is not True:
        raise ValueError("parent did not pass the mechanics gameplay initializer gate")
    if not _same_path(
        initializer.get("candidate_checkpoint"), parent
    ) or initializer.get("candidate_checkpoint_sha256") != _sha256(parent):
        raise ValueError("PFSP parent differs from the approved initializer")
    initializer_evidence = initializer.get("evidence_sha256")
    if not isinstance(initializer_evidence, dict):
        raise TypeError("initializer summary lacks bound evidence digests")

    def verify_initializer_evidence(path: Path) -> None:
        if initializer_evidence.get(str(path.resolve())) != _sha256(path):
            raise ValueError(f"initializer evidence changed: {path}")

    balance = _object(balance_report)
    exclusion = _object(exclusion_manifest)
    if not _same_path(balance.get("output"), train_pool) or balance.get(
        "output_sha256"
    ) != _sha256(train_pool):
        raise ValueError("training pool differs from card-balance report")
    exclusion_output = Path(str(exclusion.get("output", "")))
    if (
        not _same_path(balance.get("source"), exclusion_output)
        or balance.get("source_sha256") != exclusion.get("output_sha256")
        or int(exclusion.get("retained_exclusion_overlap", -1)) != 0
        or int(exclusion.get("retained_decks", -1)) != 1720
        or int(balance.get("decks", -1)) != 1720
        or int(balance.get("signature_changes", -1)) != 0
        or float(balance.get("after", {}).get("maximum_to_minimum_ratio", 1e9))
        >= float(balance.get("before", {}).get("maximum_to_minimum_ratio", -1.0))
    ):
        raise ValueError("training-pool separation or balancing contract failed")
    pfsp_exclusion = _object(pfsp_exclusion_manifest)
    if (
        not _same_path(pfsp_exclusion.get("output"), pfsp_sampling_decks)
        or pfsp_exclusion.get("output_sha256") != _sha256(pfsp_sampling_decks)
        or int(pfsp_exclusion.get("retained_exclusion_overlap", -1)) != 0
        or int(pfsp_exclusion.get("retained_decks", -1)) != 308
    ):
        raise ValueError("PFSP tuning pool overlaps a frozen evaluation pool")

    parent_strategy = _verify_strategy_report(
        _object(root / "parent_strategy.json"),
        checkpoint=parent,
        sampling_decks=pfsp_sampling_decks,
    )
    candidate_strategy = _verify_strategy_report(
        _object(root / "candidate_strategy.json"),
        checkpoint=candidate,
        sampling_decks=pfsp_sampling_decks,
    )
    stability = _object(root / "training_stability.json")
    state_audit = _object(root / "state_dict_audit.json")
    direct_rows: list[dict[str, Any]] = []
    for split, decks, seed in (
        ("validation", validation_decks, 1056301),
        ("heldout", heldout_decks, 1056302),
    ):
        direct_rows.append(
            _verify_eval_context(
                _object(root / f"direct_{split}12.metrics.json"),
                checkpoint=candidate,
                opponent_checkpoint=parent,
                decks_path=decks,
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
    candidate_metrics: dict[str, dict[str, Any]] = {}
    for name in PAIRED_WORKLOADS:
        games, seed, mode, strategy, deck_group = PAIRED_SPECS[name]
        decks = hog_decks if deck_group == "hog" else heldout_decks
        candidate_metrics[name] = _verify_eval_context(
            _object(root / f"candidate_{name}.metrics.json"),
            checkpoint=candidate,
            opponent_checkpoint=None,
            decks_path=decks,
            games=games,
            seed=seed,
            opponent_mode=mode,
            opponent_strategy=strategy,
        )
        comparisons[name] = _verify_comparison_context(
            _object(root / f"{name}.compare.json"),
            baseline=initializer_root / f"candidate_{name}.games.json",
            candidate=root / f"candidate_{name}.games.json",
            games=games,
        )

    parent_metrics: dict[str, dict[str, Any]] = {}
    for name in PAIRED_WORKLOADS:
        parent_payload = _object(initializer_root / f"candidate_{name}.metrics.json")
        parent_row = parent_payload.get("metrics")
        if not isinstance(parent_row, dict):
            raise TypeError(f"initializer metrics must be an object: {name}")
        parent_metrics[name] = parent_row
        verify_initializer_evidence(
            initializer_root / f"candidate_{name}.metrics.json"
        )
    parent_defense = [parent_metrics[name] for name in ("balanced12", "reactive12")]
    candidate_defense = [
        candidate_metrics[name] for name in ("balanced12", "reactive12")
    ]
    for name in PAIRED_WORKLOADS:
        verify_initializer_evidence(initializer_root / f"candidate_{name}.games.json")
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
        parent_defense, value="candidate_noop_when_playable", weight="games"
    )
    candidate_noop = _weighted_metric(
        candidate_defense, value="candidate_noop_when_playable", weight="games"
    )
    parent_noop_by_workload = {
        name: float(parent_metrics[name]["candidate_noop_when_playable"])
        for name in PAIRED_WORKLOADS
    }
    candidate_noop_by_workload = {
        name: float(candidate_metrics[name]["candidate_noop_when_playable"])
        for name in PAIRED_WORKLOADS
    }
    parent_hog_path = initializer_root / "candidate_hog12.utilization.json"
    parent_hog_decisions = initializer_root / "candidate_hog12.decisions.json"
    parent_hog_games = initializer_root / "candidate_hog12.games.json"
    parent_hog = _verify_hog_utilization(
        _object(parent_hog_path),
        decisions_path=parent_hog_decisions,
        games_path=parent_hog_games,
    )
    verify_initializer_evidence(parent_hog_path)
    verify_initializer_evidence(parent_hog_decisions)
    candidate_hog_decisions = root / "candidate_hog12.decisions.json"
    candidate_hog_games = root / "candidate_hog12.games.json"
    candidate_hog = _verify_hog_utilization(
        _object(root / "candidate_hog12.utilization.json"),
        decisions_path=candidate_hog_decisions,
        games_path=candidate_hog_games,
    )
    win_condition_matrix = finalize_win_condition_matrix(
        root=win_condition_root,
        manifest_path=win_condition_manifest,
        validation_pool=validation_decks,
        heldout_pool=heldout_decks,
        parent=parent,
        candidate=candidate,
    )

    human: dict[str, dict[str, Any]] = {}
    for name, (corpus, sidecar) in human_splits.items():
        before, after = _verify_human_evaluation(
            _object(root / f"human_{name}.json"),
            corpus=corpus,
            sidecar=sidecar,
            parent=parent,
            candidate=candidate,
        )
        human[name] = {"parent": before, "candidate": after}

    parent_strategy_scores = {
        name: float(row["score_rate"])
        for name, row in parent_strategy["results"].items()
    }
    candidate_strategy_scores = {
        name: float(row["score_rate"])
        for name, row in candidate_strategy["results"].items()
    }
    gates = {
        "approved_initializer": True,
        "strict_training_pool": True,
        "training_stability": (
            stability.get("passes") is True
            and int(stability.get("start_update", -1)) == start_update + 1
            and int(stability.get("end_update", -1)) == end_update
            and int(stability.get("updates", -1)) == update_count
            and int(stability.get("transition_delta", -1)) == update_count * 4_096
            and _same_path(stability.get("parent"), parent)
        ),
        "authorized_actor_and_value_changes": (
            state_audit.get("passes") is True
            and int(state_audit.get("actor_changed_parameter_count", 0)) > 0
            and int(state_audit.get("value_changed_parameter_count", 0)) > 0
            and state_audit.get("unauthorized_changes") == []
            and _same_path(state_audit.get("before"), parent)
            and _same_path(state_audit.get("after"), candidate)
            and set(state_audit.get("actor_prefixes") or ())
            == set(expected_actor_prefixes)
            and set(state_audit.get("value_prefixes") or ())
            == {"critic_encoder.", "value_head."}
        ),
        "direct_parent_improvement": (
            direct_games == 24 and direct_wins > direct_losses and direct_crowns >= 0.0
        ),
        "direct_each_split_no_regression": all(
            int(row["wins"]) >= int(row["losses"])
            and float(row["crown_diff_per_game"]) >= 0.0
            for row in direct_rows
        ),
        "paired_evidence_count": sum(int(row["games"]) for row in comparisons.values())
        == 72,
        "strict_outcome_no_regression": all(
            row.get("passes_strict_no_regression") is True
            for row in comparisons.values()
        ),
        "aggregate_crown_no_regression": sum(
            float(row["crown_difference_change"]) for row in comparisons.values()
        )
        >= 0.0,
        "defense_success_improvement": candidate_success >= parent_success + 0.02,
        "defense_outcome_no_regression": candidate_outcome >= parent_outcome - 0.005,
        "passivity_no_regression": candidate_noop <= parent_noop + 0.01,
        "passivity_each_workload_no_regression": all(
            candidate_noop_by_workload[name]
            <= parent_noop_by_workload[name] + 0.02
            for name in PAIRED_WORKLOADS
        ),
        "hog_absolute_gate": candidate_hog.get("gate", {}).get("passed") is True,
        "hog_each_slot_coverage": _hog_slot_coverage_passes(candidate_hog),
        "hog_zero_use_no_regression": int(candidate_hog["zero_use_games"])
        <= int(parent_hog["zero_use_games"]),
        "hog_conversion_no_regression": float(candidate_hog["window_conversion_rate"])
        >= float(parent_hog["window_conversion_rate"]) - 0.02,
        "hog_probability_no_regression": float(
            candidate_hog["mean_role_probability_when_legal_affordable"]
        )
        >= float(parent_hog["mean_role_probability_when_legal_affordable"]) - 0.02,
        "win_condition_matrix": win_condition_matrix.get("passes") is True,
        "strategy_mean_no_regression": sum(candidate_strategy_scores.values())
        >= sum(parent_strategy_scores.values()),
        "strategy_worst_no_regression": min(candidate_strategy_scores.values())
        >= min(parent_strategy_scores.values()),
        "strategy_each_no_regression": all(
            candidate_strategy_scores[name] >= parent_strategy_scores[name]
            for name in parent_strategy_scores
        ),
        "human_action_type_no_net_regression": all(
            int(rows["candidate"]["action_type_improvements_vs_first"])
            >= int(rows["candidate"]["action_type_regressions_vs_first"])
            for rows in human.values()
        ),
        "human_exact_no_net_regression": all(
            int(rows["candidate"]["exact_improvements_vs_first"])
            >= int(rows["candidate"]["exact_regressions_vs_first"])
            for rows in human.values()
        ),
    }
    eligible = all(gates.values())
    evidence_paths = [
        initializer_root / "summary.json",
        train_pool,
        balance_report,
        exclusion_manifest,
        pfsp_sampling_decks,
        pfsp_exclusion_manifest,
        root / "parent_strategy.json",
        root / "candidate_strategy.json",
        root / "training_stability.json",
        root / "state_dict_audit.json",
        *(
            root / f"direct_{split}12.metrics.json"
            for split in ("validation", "heldout")
        ),
        *(root / f"direct_{split}12.games.json" for split in ("validation", "heldout")),
        *(root / f"human_{name}.json" for name in human_splits),
    ]
    for name in PAIRED_WORKLOADS:
        evidence_paths.extend(
            [
                root / f"candidate_{name}.metrics.json",
                root / f"candidate_{name}.games.json",
                root / f"{name}.compare.json",
            ]
        )
    evidence_paths.extend(
        [
            root / "candidate_hog12.decisions.json",
            root / "candidate_hog12.utilization.json",
        ]
    )
    evidence_paths.extend(
        Path(path) for path in win_condition_matrix["evidence_sha256"]
    )
    return {
        "schema": "mechanics-slot-pfsp-pilot-v1",
        "status": "development_candidate_ready" if eligible else "rejected",
        "development_candidate_eligible": eligible,
        "parent": str(parent.resolve()),
        "parent_sha256": _sha256(parent),
        "candidate": str(candidate.resolve()),
        "candidate_sha256": _sha256(candidate),
        "training_interval": {
            "parent_update": start_update,
            "candidate_update": end_update,
            "updates": update_count,
            "expected_transitions": update_count * 4_096,
            "actor_prefixes": list(expected_actor_prefixes),
        },
        "gates": gates,
        "direct": {
            "games": direct_games,
            "wins": direct_wins,
            "losses": direct_losses,
            "crown_difference": direct_crowns,
        },
        "defense": {
            "parent_success_rate": parent_success,
            "candidate_success_rate": candidate_success,
            "parent_mean_outcome": parent_outcome,
            "candidate_mean_outcome": candidate_outcome,
            "parent_playable_noop": parent_noop,
            "candidate_playable_noop": candidate_noop,
        },
        "passivity_by_workload": {
            name: {
                "parent_playable_noop": parent_noop_by_workload[name],
                "candidate_playable_noop": candidate_noop_by_workload[name],
            }
            for name in PAIRED_WORKLOADS
        },
        "paired": comparisons,
        "strategy": {
            "parent_score_rates": parent_strategy_scores,
            "candidate_score_rates": candidate_strategy_scores,
        },
        "hog": {"parent": parent_hog, "candidate": candidate_hog},
        "win_condition_matrix": win_condition_matrix,
        "human": human,
        "evidence_sha256": {
            str(path.resolve()): _sha256(path) for path in evidence_paths
        },
        "claim_scope": (
            "bounded complete-game PFSP development candidate only; not a "
            "champion, human-skill, or mid-ladder claim"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--initializer-root", required=True, type=Path)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--train-pool", required=True, type=Path)
    parser.add_argument("--balance-report", required=True, type=Path)
    parser.add_argument("--exclusion-manifest", required=True, type=Path)
    parser.add_argument("--pfsp-sampling-decks", required=True, type=Path)
    parser.add_argument("--pfsp-exclusion-manifest", required=True, type=Path)
    parser.add_argument("--validation-decks", required=True, type=Path)
    parser.add_argument("--heldout-decks", required=True, type=Path)
    parser.add_argument("--hog-decks", required=True, type=Path)
    parser.add_argument("--win-condition-root", required=True, type=Path)
    parser.add_argument("--win-condition-manifest", required=True, type=Path)
    parser.add_argument("--start-update", type=int, default=0)
    parser.add_argument("--end-update", type=int, default=4)
    parser.add_argument("--actor-prefix", action="append")
    for name in ("validation", "archetype", "chronology"):
        parser.add_argument(f"--human-{name}-corpus", required=True, type=Path)
        parser.add_argument(f"--human-{name}-sidecar", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    human_splits = {
        name: (
            getattr(args, f"human_{name}_corpus"),
            getattr(args, f"human_{name}_sidecar"),
        )
        for name in ("validation", "archetype", "chronology")
    }
    payload = finalize_pfsp_pilot(
        root=args.root,
        initializer_root=args.initializer_root,
        parent=args.parent,
        candidate=args.candidate,
        train_pool=args.train_pool,
        balance_report=args.balance_report,
        exclusion_manifest=args.exclusion_manifest,
        pfsp_sampling_decks=args.pfsp_sampling_decks,
        pfsp_exclusion_manifest=args.pfsp_exclusion_manifest,
        validation_decks=args.validation_decks,
        heldout_decks=args.heldout_decks,
        hog_decks=args.hog_decks,
        win_condition_root=args.win_condition_root,
        win_condition_manifest=args.win_condition_manifest,
        human_splits=human_splits,
        start_update=args.start_update,
        end_update=args.end_update,
        expected_actor_prefixes=tuple(
            args.actor_prefix or ("action_type_head.", "mechanics_slot_choice_query.")
        ),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
