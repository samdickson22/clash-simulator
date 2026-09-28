#!/usr/bin/env python3
"""Resolve the three-block external safety gate for hazard update 30."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

BLOCKS = (0, 1, 2)
WORKLOADS: dict[str, tuple[int, int, str, str | None, str]] = {
    "random12": (12, 10, "random", None, "heldout"),
    "balanced12": (12, 11, "strategy", "balanced", "heldout"),
    "reactive12": (12, 12, "strategy", "reactive-defense", "heldout"),
    "bridge6": (6, 13, "strategy", "bridge-pressure", "heldout"),
    "slow6": (6, 14, "strategy", "slow-push", "heldout"),
    "spell6": (6, 15, "strategy", "spell-control", "heldout"),
    "split6": (6, 16, "strategy", "split-lane", "heldout"),
    "hog12": (12, 17, "strategy", "balanced", "hog"),
}


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _array(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(
        isinstance(row, dict) for row in payload
    ):
        raise TypeError(f"expected JSON object array: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_path(value: object, expected: Path) -> bool:
    return isinstance(value, str) and Path(value).resolve() == expected.resolve()


def _score(outcome: object) -> float:
    if outcome == "win":
        return 1.0
    if outcome == "draw":
        return 0.5
    if outcome == "loss":
        return 0.0
    raise ValueError(f"invalid game outcome: {outcome!r}")


def _finite(metrics: dict[str, Any], name: str) -> float:
    value = float(metrics[name])
    if not math.isfinite(value):
        raise ValueError(f"non-finite evaluation metric: {name}")
    return value


def _verify_evaluation(
    *,
    metrics_path: Path,
    games_path: Path,
    checkpoint: Path,
    deck_pool: Path,
    games: int,
    seed: int,
    opponent_mode: str,
    opponent_strategy: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _object(metrics_path)
    metrics = payload.get("metrics")
    checks = {
        "schema": int(payload.get("schema_version", -1)) == 1,
        "checkpoint": _same_path(payload.get("checkpoint"), checkpoint),
        "checkpoint_sha256": payload.get("checkpoint_sha256")
        == _sha256(checkpoint),
        "opponent_checkpoint": payload.get("opponent_checkpoint") is None,
        "deck_pool": _same_path(payload.get("sampling_decks_path"), deck_pool),
        "deck_pool_sha256": payload.get("sampling_decks_sha256")
        == _sha256(deck_pool),
        "seed": int(payload.get("seed", -1)) == seed,
        "mirror_match": payload.get("mirror_match") is True,
        "opponent_mode": payload.get("opponent_mode") == opponent_mode,
        "opponent_strategy": payload.get("opponent_strategy") == opponent_strategy,
        "reward_profile": payload.get("reward_profile") == "objective-v1",
        "metrics": isinstance(metrics, dict),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(
            f"evaluation provenance mismatch ({metrics_path}): {', '.join(failed)}"
        )
    assert isinstance(metrics, dict)
    if int(metrics.get("games", -1)) != games:
        raise ValueError(f"evaluation game count mismatch: {metrics_path}")
    outcomes = [int(_finite(metrics, name)) for name in ("wins", "losses", "draws")]
    if sum(outcomes) != games:
        raise ValueError(f"evaluation outcomes do not sum to games: {metrics_path}")
    for name in (
        "crown_diff_per_game",
        "candidate_noop_when_playable",
        "candidate_placement_rate",
        "defense_event_success_rate",
        "defense_event_mean_outcome",
        "defense_events_resolved",
        "defensive_action_rate_when_threatened",
        "threatened_decisions",
        "incoming_tower_danger_mean",
    ):
        _finite(metrics, name)
    records = _array(games_path)
    if len(records) != games or [int(row.get("game", -1)) for row in records] != list(
        range(games)
    ):
        raise ValueError(f"game records are incomplete or unordered: {games_path}")
    if [int(row.get("candidate_player", -1)) for row in records].count(0) != games // 2:
        raise ValueError(f"game records are not seat-paired: {games_path}")
    if [int(row.get("candidate_player", -1)) for row in records].count(1) != games // 2:
        raise ValueError(f"game records are not seat-paired: {games_path}")
    if sum(_score(row.get("outcome")) == 1.0 for row in records) != outcomes[0]:
        raise ValueError(f"game records disagree with win count: {games_path}")
    return metrics, records


def _verify_matched_records(
    parent: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    *,
    label: str,
) -> None:
    if len(parent) != len(candidate):
        raise ValueError(f"matched record length differs: {label}")
    for before, after in zip(parent, candidate, strict=True):
        keys = (
            "game",
            "matchup",
            "matchup_seed",
            "candidate_player",
            "candidate_deck",
            "opponent_deck",
        )
        if any(before.get(key) != after.get(key) for key in keys):
            raise ValueError(f"matched game context differs: {label}")


def _outcome_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "games": float(len(rows)),
        "wins": float(sum(row["outcome"] == "win" for row in rows)),
        "losses": float(sum(row["outcome"] == "loss" for row in rows)),
        "draws": float(sum(row["outcome"] == "draw" for row in rows)),
        "score": float(sum(_score(row["outcome"]) for row in rows)),
        "crown_difference": float(
            sum(
                int(row["candidate_crowns"]) - int(row["opponent_crowns"])
                for row in rows
            )
        ),
    }


def _weighted_mean(
    rows: list[dict[str, Any]], value: str, weight: str | None = None
) -> float:
    weights = np.asarray(
        [float(row[weight]) if weight is not None else float(row["games"]) for row in rows],
        dtype=np.float64,
    )
    values = np.asarray([float(row[value]) for row in rows], dtype=np.float64)
    if not np.isfinite(values).all() or not np.isfinite(weights).all() or weights.sum() <= 0:
        raise ValueError(f"cannot aggregate {value}")
    return float(np.average(values, weights=weights))


def _behavior_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "noop_when_playable": _weighted_mean(rows, "candidate_noop_when_playable"),
        "placement_rate": _weighted_mean(rows, "candidate_placement_rate"),
        "defense_event_success_rate": _weighted_mean(
            rows, "defense_event_success_rate", "defense_events_resolved"
        ),
        "defense_event_mean_outcome": _weighted_mean(
            rows, "defense_event_mean_outcome", "defense_events_resolved"
        ),
        "defensive_action_rate_when_threatened": _weighted_mean(
            rows, "defensive_action_rate_when_threatened", "threatened_decisions"
        ),
        "incoming_tower_danger_mean": _weighted_mean(
            rows, "incoming_tower_danger_mean"
        ),
    }


def _clustered_bootstrap(
    score_units: list[float], crown_units: list[float], *, seed: int = 1069001
) -> dict[str, float]:
    scores = np.asarray(score_units, dtype=np.float64)
    crowns = np.asarray(crown_units, dtype=np.float64)
    if scores.ndim != 1 or scores.size < 2 or crowns.shape != scores.shape:
        raise ValueError("paired bootstrap requires aligned matchup clusters")
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, scores.size, size=(20_000, scores.size))
    score_samples = scores[draws].mean(axis=1)
    crown_samples = crowns[draws].mean(axis=1)
    return {
        "clusters": float(scores.size),
        "score_delta_mean": float(scores.mean()),
        "score_delta_ci95_low": float(np.quantile(score_samples, 0.025)),
        "score_delta_ci95_high": float(np.quantile(score_samples, 0.975)),
        "crown_delta_mean": float(crowns.mean()),
        "crown_delta_ci95_low": float(np.quantile(crown_samples, 0.025)),
        "crown_delta_ci95_high": float(np.quantile(crown_samples, 0.975)),
    }


def _human_summary(path: Path, *, parent: Path, candidate: Path) -> dict[str, Any]:
    payload = _object(path)
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise ValueError("full human evaluation must compare exactly two checkpoints")
    expected = ((parent, 20), (candidate, 30))
    summaries: dict[str, dict[str, float]] = {}
    for label, result, (checkpoint, update) in zip(
        ("parent", "candidate"), results, expected, strict=True
    ):
        if not isinstance(result, dict):
            raise TypeError("human evaluation result must be an object")
        if (
            not _same_path(result.get("checkpoint"), checkpoint)
            or result.get("checkpoint_sha256") != _sha256(checkpoint)
            or int(result.get("checkpoint_update", -1)) != update
        ):
            raise ValueError("human evaluation checkpoint provenance mismatch")
        summaries[label] = {
            name: float(result[name])
            for name in (
                "predicted_play_rate",
                "play_average_precision",
                "play_roc_auc",
                "play_brier",
                "play_ece_10_bin",
                "conditional_card_slot_accuracy",
                "play_samples",
            )
        }
    if summaries["parent"]["play_samples"] != summaries["candidate"]["play_samples"]:
        raise ValueError("human evaluation play counts differ")
    return summaries


def _gate_reasons(
    *,
    parent: dict[str, float],
    candidate: dict[str, float],
    blocks: dict[str, dict[str, dict[str, float]]],
    workloads: dict[str, dict[str, dict[str, float]]],
    behavior: dict[str, dict[str, float]],
    paired: dict[str, float],
    direct: dict[str, float],
    human: dict[str, dict[str, float]],
) -> list[str]:
    reasons: list[str] = []
    if candidate["wins"] < parent["wins"]:
        reasons.append("external_total_win_regression")
    if candidate["crown_difference"] < parent["crown_difference"]:
        reasons.append("external_total_crown_regression")
    if paired["score_delta_mean"] <= 0.0:
        reasons.append("external_paired_score_not_positive")
    for name, row in blocks.items():
        if row["candidate"]["wins"] < row["parent"]["wins"]:
            reasons.append(f"external_block_win_regression:{name}")
        if row["candidate"]["crown_difference"] < row["parent"]["crown_difference"]:
            reasons.append(f"external_block_crown_regression:{name}")
    for name, row in workloads.items():
        if row["candidate"]["wins"] < row["parent"]["wins"] - 1:
            reasons.append(f"external_workload_win_regression:{name}")
        if row["candidate"]["crown_difference"] < row["parent"]["crown_difference"] - 2:
            reasons.append(f"external_workload_crown_regression:{name}")
    before = behavior["parent"]
    after = behavior["candidate"]
    if after["defense_event_success_rate"] < before["defense_event_success_rate"] - 0.02:
        reasons.append("defense_success_regression")
    if after["defense_event_mean_outcome"] < before["defense_event_mean_outcome"]:
        reasons.append("defense_outcome_regression")
    if after["incoming_tower_danger_mean"] > before["incoming_tower_danger_mean"]:
        reasons.append("incoming_danger_regression")
    if abs(
        after["defensive_action_rate_when_threatened"]
        - before["defensive_action_rate_when_threatened"]
    ) > 0.02:
        reasons.append("threatened_action_rate_shift")
    if after["defensive_action_rate_when_threatened"] < 0.05:
        reasons.append("threatened_action_rate_below_five_percent")
    if not 0.01 < after["noop_when_playable"] < 0.95:
        reasons.append("playable_noop_outside_safety_interval")
    if not 0.01 < after["placement_rate"] < 0.20:
        reasons.append("placement_rate_outside_safety_interval")
    if direct["wins"] < 52:
        reasons.append("direct96_below_52_wins")
    if direct["wins_as_player0"] < 24 or direct["wins_as_player1"] < 24:
        reasons.append("direct96_losing_seat")
    human_before = human["parent"]
    human_after = human["candidate"]
    if not 0.005 < human_after["predicted_play_rate"] < 0.20:
        reasons.append("human_play_rate_outside_interval")
    if human_after["play_average_precision"] < human_before["play_average_precision"] - 0.002:
        reasons.append("human_hazard_ap_regression")
    if human_after["play_roc_auc"] < human_before["play_roc_auc"] - 0.01:
        reasons.append("human_hazard_roc_regression")
    if human_after["play_brier"] > human_before["play_brier"] + 0.005:
        reasons.append("human_play_brier_regression")
    if human_after["play_ece_10_bin"] > human_before["play_ece_10_bin"] + 0.01:
        reasons.append("human_play_ece_regression")
    if (
        human_after["conditional_card_slot_accuracy"]
        < human_before["conditional_card_slot_accuracy"] - 0.01
    ):
        reasons.append("human_card_accuracy_regression")
    return reasons


def finalize(
    *,
    root: Path,
    parent_checkpoint: Path,
    candidate_checkpoint: Path,
    heldout_decks: Path,
    hog_decks: Path,
    human_corpus: Path,
    human_sidecar: Path,
    output: Path,
) -> dict[str, Any]:
    for path in (
        parent_checkpoint,
        candidate_checkpoint,
        heldout_decks,
        hog_decks,
        human_corpus,
        human_sidecar,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    all_records: dict[str, list[dict[str, Any]]] = {"parent": [], "candidate": []}
    metrics_by_role: dict[str, list[dict[str, Any]]] = {"parent": [], "candidate": []}
    records_by_block: dict[int, dict[str, list[dict[str, Any]]]] = {}
    records_by_workload: dict[str, dict[str, list[dict[str, Any]]]] = {
        name: {"parent": [], "candidate": []} for name in WORKLOADS
    }
    score_clusters: list[float] = []
    crown_clusters: list[float] = []
    evidence_paths: list[Path] = [
        parent_checkpoint,
        candidate_checkpoint,
        heldout_decks,
        hog_decks,
        human_corpus,
        human_sidecar,
    ]
    for block in BLOCKS:
        records_by_block[block] = {"parent": [], "candidate": []}
        for name, (games, offset, mode, strategy, deck_group) in WORKLOADS.items():
            seed = 1_069_000 + block * 100 + offset
            pool = hog_decks if deck_group == "hog" else heldout_decks
            role_records: dict[str, list[dict[str, Any]]] = {}
            for role, checkpoint in (
                ("parent", parent_checkpoint),
                ("candidate", candidate_checkpoint),
            ):
                metrics_path = root / f"block{block}" / f"{role}_{name}.metrics.json"
                games_path = root / f"block{block}" / f"{role}_{name}.games.json"
                metrics, records = _verify_evaluation(
                    metrics_path=metrics_path,
                    games_path=games_path,
                    checkpoint=checkpoint,
                    deck_pool=pool,
                    games=games,
                    seed=seed,
                    opponent_mode=mode,
                    opponent_strategy=strategy,
                )
                metrics_by_role[role].append(metrics)
                all_records[role].extend(records)
                records_by_block[block][role].extend(records)
                records_by_workload[name][role].extend(records)
                role_records[role] = records
                evidence_paths.extend((metrics_path, games_path))
            _verify_matched_records(
                role_records["parent"], role_records["candidate"], label=f"block{block}/{name}"
            )
            for matchup in sorted({int(row["matchup"]) for row in role_records["parent"]}):
                before = [row for row in role_records["parent"] if int(row["matchup"]) == matchup]
                after = [row for row in role_records["candidate"] if int(row["matchup"]) == matchup]
                if len(before) != 2 or len(after) != 2:
                    raise ValueError("every bootstrap matchup cluster must contain both seats")
                score_clusters.append(
                    float(np.mean([_score(a["outcome"]) - _score(b["outcome"]) for b, a in zip(before, after, strict=True)]))
                )
                crown_clusters.append(
                    float(
                        np.mean(
                            [
                                (int(a["candidate_crowns"]) - int(a["opponent_crowns"]))
                                - (int(b["candidate_crowns"]) - int(b["opponent_crowns"]))
                                for b, a in zip(before, after, strict=True)
                            ]
                        )
                    )
                )
            comparison = root / f"block{block}" / f"{name}.compare.json"
            comparison_payload = _object(comparison)
            if (
                comparison_payload.get("baseline_sha256")
                != _sha256(root / f"block{block}" / f"parent_{name}.games.json")
                or comparison_payload.get("candidate_sha256")
                != _sha256(root / f"block{block}" / f"candidate_{name}.games.json")
            ):
                raise ValueError(f"comparison provenance mismatch: {comparison}")
            evidence_paths.append(comparison)

    parent_summary = _outcome_summary(all_records["parent"])
    candidate_summary = _outcome_summary(all_records["candidate"])
    block_summaries = {
        f"block{block}": {
            role: _outcome_summary(records_by_block[block][role])
            for role in ("parent", "candidate")
        }
        for block in BLOCKS
    }
    workload_summaries = {
        name: {
            role: _outcome_summary(records_by_workload[name][role])
            for role in ("parent", "candidate")
        }
        for name in WORKLOADS
    }
    behavior = {
        role: _behavior_summary(metrics_by_role[role])
        for role in ("parent", "candidate")
    }
    paired = _clustered_bootstrap(score_clusters, crown_clusters)

    direct_payload = _object(root / "direct96.metrics.json")
    direct_metrics = direct_payload.get("metrics")
    if not isinstance(direct_metrics, dict):
        raise TypeError("direct96 evaluation lacks metrics")
    direct_checks = {
        "candidate": _same_path(direct_payload.get("checkpoint"), candidate_checkpoint),
        "candidate_sha": direct_payload.get("checkpoint_sha256") == _sha256(candidate_checkpoint),
        "parent": _same_path(direct_payload.get("opponent_checkpoint"), parent_checkpoint),
        "parent_sha": direct_payload.get("opponent_checkpoint_sha256") == _sha256(parent_checkpoint),
        "heldout": _same_path(direct_payload.get("sampling_decks_path"), heldout_decks),
        "heldout_sha": direct_payload.get("sampling_decks_sha256") == _sha256(heldout_decks),
        "games": int(direct_metrics.get("games", -1)) == 96,
        "seed": int(direct_payload.get("seed", -1)) == 1_069_401,
        "mode": direct_payload.get("opponent_mode") == "policy",
        "reward": direct_payload.get("reward_profile") == "objective-v1",
    }
    failed_direct = [name for name, passed in direct_checks.items() if not passed]
    if failed_direct:
        raise ValueError("direct96 provenance mismatch: " + ", ".join(failed_direct))
    direct = {
        "wins": _finite(direct_metrics, "wins"),
        "losses": _finite(direct_metrics, "losses"),
        "draws": _finite(direct_metrics, "draws"),
        "wins_as_player0": _finite(direct_metrics, "wins_as_player0"),
        "wins_as_player1": _finite(direct_metrics, "wins_as_player1"),
        "crown_difference": _finite(direct_metrics, "crown_diff_per_game") * 96,
    }
    direct_records = _array(root / "direct96.games.json")
    if len(direct_records) != 96:
        raise ValueError("direct96 game records are incomplete")
    evidence_paths.extend((root / "direct96.metrics.json", root / "direct96.games.json"))

    human_path = root / "human_all.json"
    human_payload = _object(human_path)
    if (
        not _same_path(human_payload.get("corpus"), human_corpus)
        or human_payload.get("corpus_sha256") != _sha256(human_corpus)
        or not _same_path(human_payload.get("public_observation_sidecar"), human_sidecar)
        or human_payload.get("public_observation_sidecar_sha256") != _sha256(human_sidecar)
        or int(human_payload.get("evaluated_episodes", -1)) != 363
    ):
        raise ValueError("full human corpus provenance mismatch")
    human = _human_summary(human_path, parent=parent_checkpoint, candidate=candidate_checkpoint)
    evidence_paths.append(human_path)

    reasons = _gate_reasons(
        parent=parent_summary,
        candidate=candidate_summary,
        blocks=block_summaries,
        workloads=workload_summaries,
        behavior=behavior,
        paired=paired,
        direct=direct,
        human=human,
    )
    payload = {
        "schema": "clasher.fresh_f3_hazard_expanded_safety.v1",
        "parent_checkpoint": str(parent_checkpoint.resolve()),
        "parent_checkpoint_sha256": _sha256(parent_checkpoint),
        "candidate_checkpoint": str(candidate_checkpoint.resolve()),
        "candidate_checkpoint_sha256": _sha256(candidate_checkpoint),
        "external_games_per_checkpoint": len(all_records["parent"]),
        "parent": parent_summary,
        "candidate": candidate_summary,
        "blocks": block_summaries,
        "workloads": workload_summaries,
        "behavior": behavior,
        "paired_external": paired,
        "direct_parent": direct,
        "human_all": human,
        "rejection_reasons": reasons,
        "fresh_quarantine_authorized": not reasons,
        "promotion_authorized": False,
        "selected_development_parent": "candidate" if not reasons else "parent",
        "evidence_sha256": {
            str(path.resolve()): _sha256(path) for path in evidence_paths
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--heldout-decks", required=True, type=Path)
    parser.add_argument("--hog-decks", required=True, type=Path)
    parser.add_argument("--human-corpus", required=True, type=Path)
    parser.add_argument("--human-sidecar", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            finalize(
                root=args.root,
                parent_checkpoint=args.parent,
                candidate_checkpoint=args.candidate,
                heldout_decks=args.heldout_decks,
                hog_decks=args.hog_decks,
                human_corpus=args.human_corpus,
                human_sidecar=args.human_sidecar,
                output=args.output,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
