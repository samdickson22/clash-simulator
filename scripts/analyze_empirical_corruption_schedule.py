#!/usr/bin/env python3
"""Measure retained live-observation corruption and publish a bounded B1 schedule.

This analysis is deliberately read-only.  It consumes one retained YouTube replay,
its manually reviewed labels, and clean simulator-derived causal corpora.  It does
not inspect expert actions or produce training arrays.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA = "clasher.empirical_corruption_analysis.v1"
SCHEDULE_SCHEMA = "clasher.actor_augmentation_schedule.b1.v1"
DEFAULT_SEED = 1_064_401


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _load_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"expected object at {path}:{line_number}")
            rows.append(value)
    return rows


def _rounded(value: float) -> float:
    return round(float(value), 9)


def _summary(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray(list(values), dtype=np.float64)
    if array.size == 0:
        return {"count": 0, "mean": None, "p05": None, "p50": None, "p95": None}
    return {
        "count": int(array.size),
        "mean": _rounded(float(np.mean(array))),
        "p05": _rounded(float(np.quantile(array, 0.05))),
        "p50": _rounded(float(np.quantile(array, 0.50))),
        "p95": _rounded(float(np.quantile(array, 0.95))),
    }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return _rounded(numerator / denominator)


def _identity(entity: Mapping[str, Any]) -> tuple[bool, str | None]:
    raw = entity.get("identity")
    if not isinstance(raw, Mapping):
        return False, None
    stable_key = raw.get("stable_key")
    valid = bool(raw.get("valid")) and isinstance(stable_key, str)
    return valid, stable_key if isinstance(stable_key, str) else None


def _world_position(entity: Mapping[str, Any]) -> tuple[float, float] | None:
    raw = entity.get("world_position")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) != 2:
        return None
    if not all(isinstance(item, (int, float)) for item in raw):
        return None
    return float(raw[0]), float(raw[1])


def _quantile_bucket(value: float, low: float, high: float) -> str:
    if value <= low:
        return "low"
    if value >= high:
        return "high"
    return "medium"


def _time_quartile(timestamp_ms: int, duration_ms: int) -> str:
    if duration_ms <= 0:
        return "q0"
    fraction = min(max(timestamp_ms / duration_ms, 0.0), 1.0)
    return f"q{min(int(fraction * 4), 3)}"


def _tower_group(entity: Mapping[str, Any], stable_key: str) -> str | None:
    position = _world_position(entity)
    if position is None or not stable_key.startswith("tower:"):
        return None
    team = int(entity.get("team_id", -1))
    lane = "center"
    if stable_key == "tower:Tower":
        lane = "left" if position[0] < 9.0 else "right"
    return f"team{team}:{stable_key}:{lane}"


def _measure_spatial(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    tower_points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    nearest_distances: list[float] = []
    second_minus_first: list[float] = []
    candidate_counts: list[float] = []
    previous: dict[tuple[int, str], list[tuple[float, float]]] = {}

    for row in rows:
        current: dict[tuple[int, str], list[tuple[float, float]]] = defaultdict(list)
        public = row.get("public", {})
        entities = public.get("entities", []) if isinstance(public, Mapping) else []
        for entity in entities:
            if not isinstance(entity, Mapping):
                continue
            valid, stable_key = _identity(entity)
            position = _world_position(entity)
            if not valid or stable_key is None or position is None:
                continue
            group = _tower_group(entity, stable_key)
            if group is not None:
                tower_points[group].append(position)
            if stable_key.startswith(("troop_body:", "building_body:")):
                current[(int(entity.get("team_id", -1)), stable_key)].append(position)

        for key, points in current.items():
            candidates = previous.get(key, [])
            for point in points:
                distances = sorted(
                    math.dist(point, candidate) for candidate in candidates
                )
                candidate_counts.append(float(len(distances)))
                if distances:
                    nearest_distances.append(distances[0])
                if len(distances) >= 2:
                    second_minus_first.append(distances[1] - distances[0])
        previous = dict(current)

    tower_groups: dict[str, Any] = {}
    all_residuals: list[float] = []
    for group, points in sorted(tower_points.items()):
        values = np.asarray(points, dtype=np.float64)
        center = np.median(values, axis=0)
        residuals = np.sqrt(np.sum((values - center) ** 2, axis=1))
        all_residuals.extend(float(item) for item in residuals)
        tower_groups[group] = {
            "center_world": [_rounded(center[0]), _rounded(center[1])],
            "observations": int(values.shape[0]),
            "residual_world": _summary(residuals.tolist()),
        }

    return {
        "static_tower_detector_jitter_proxy": {
            "all_residual_world": _summary(all_residuals),
            "groups": tower_groups,
            "interpretation": (
                "Residual to the within-replay median detector position. It mixes detector "
                "jitter, duplicate boxes, and HUD animation; it is not ground-truth error."
            ),
        },
        "dynamic_association_proxy": {
            "candidate_count": _summary(candidate_counts),
            "nearest_same_identity_team_distance_world": _summary(nearest_distances),
            "second_minus_first_distance_world": _summary(second_minus_first),
            "interpretation": (
                "Frame-adjacent same-identity/team nearest-neighbor geometry. It mixes true "
                "motion, spawns, deaths, duplicates, and association ambiguity."
            ),
        },
    }


def _measure_gold(
    manual_gold: Mapping[str, Any],
    predicted_labels: Mapping[str, Any],
    annotation_decisions: Mapping[str, Any],
) -> dict[str, Any]:
    gold_by_id = {
        item["label_id"]: item
        for item in manual_gold.get("labels", [])
        if isinstance(item, Mapping) and isinstance(item.get("label_id"), str)
    }
    pred_by_id = {
        item["label_id"]: item
        for item in predicted_labels.get("labels", [])
        if isinstance(item, Mapping) and isinstance(item.get("label_id"), str)
    }
    identity_gold = 0
    identity_correct = 0
    identity_wrong = 0
    identity_missed = 0
    wrong_details: list[dict[str, Any]] = []
    placement_gold = 0
    placement_correct = 0
    placement_errors: list[float] = []
    for label_id, gold in sorted(gold_by_id.items()):
        predicted = pred_by_id.get(label_id, {})
        if gold.get("identity_valid"):
            identity_gold += 1
            if not predicted.get("identity_valid"):
                identity_missed += 1
            elif predicted.get("card_identity") == gold.get("card_identity"):
                identity_correct += 1
            else:
                identity_wrong += 1
                wrong_details.append(
                    {
                        "label_id": label_id,
                        "gold": gold.get("card_identity"),
                        "predicted": predicted.get("card_identity"),
                    }
                )
        if gold.get("placement_valid"):
            placement_gold += 1
            gold_tile = gold.get("deployment_tile_absolute")
            predicted_tile = predicted.get("deployment_tile_absolute")
            if (
                isinstance(gold_tile, Sequence)
                and isinstance(predicted_tile, Sequence)
                and len(gold_tile) == len(predicted_tile) == 2
            ):
                distance = math.dist(
                    (float(gold_tile[0]), float(gold_tile[1])),
                    (float(predicted_tile[0]), float(predicted_tile[1])),
                )
                placement_errors.append(distance)
                if distance == 0.0:
                    placement_correct += 1

    decisions = [
        item
        for item in annotation_decisions.get("decisions", [])
        if isinstance(item, Mapping)
    ]
    decision_counts = Counter(str(item.get("status", "unknown")) for item in decisions)
    explicitly_wrong_proposals = [
        str(item.get("queue_id"))
        for item in decisions
        if item.get("status") == "rejected"
        and any(
            token in str(item.get("reason", "")).lower()
            for token in ("excludes", "does not visually prove")
        )
    ]

    return {
        "card_identity_accepted_gold": {
            "gold": identity_gold,
            "correct": identity_correct,
            "wrong_identity": identity_wrong,
            "missed": identity_missed,
            "accuracy": _rate(identity_correct, identity_gold),
            "wrong_details": wrong_details,
            "scope": "Only manually accepted identities count as ground truth; withheld labels are not negatives.",
        },
        "deployment_tile_accepted_gold": {
            "gold": placement_gold,
            "exact": placement_correct,
            "exact_rate": _rate(placement_correct, placement_gold),
            "tile_error": _summary(placement_errors),
            "scope": "Candidate-conditioned visual review on one replay; not replay-disjoint calibration.",
        },
        "selected_entity_proposal_review": {
            "reviewed": len(decisions),
            "status_counts": dict(sorted(decision_counts.items())),
            "explicitly_wrong_proposal_ids": explicitly_wrong_proposals,
            "scope": "Selected annotation queue, not a random detector sample; no population error rate is valid.",
        },
    }


def _simulator_summary(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as arrays:
        required = ("entity_mask", "hand_ids", "episode_ids", "episode_starts")
        missing = [name for name in required if name not in arrays.files]
        if missing:
            raise ValueError(f"{path} missing required arrays: {missing}")
        entity_counts = np.sum(arrays["entity_mask"], axis=1)
        hand_ids = arrays["hand_ids"]
        episode_ids = arrays["episode_ids"]
        starts = arrays["episode_starts"]
        result: dict[str, Any] = {
            "path": str(path),
            "sha256": _sha256(path),
            "rows": int(entity_counts.shape[0]),
            "episodes": int(np.unique(episode_ids).size),
            "episode_starts": int(np.sum(starts)),
            "entity_count": _summary(entity_counts.tolist()),
            "hand_slot_present_rate": [
                _rate(int(np.count_nonzero(hand_ids[:, slot])), int(hand_ids.shape[0]))
                for slot in range(hand_ids.shape[1])
            ],
            "arrays_consumed": list(required),
            "target_arrays_consumed": [],
        }
    return result


def build_analysis(
    live_rows: Sequence[Mapping[str, Any]],
    clock_rows: Sequence[Mapping[str, Any]],
    manual_gold: Mapping[str, Any],
    predicted_labels: Mapping[str, Any],
    annotation_decisions: Mapping[str, Any],
    simulator_paths: Sequence[Path],
    provenance: Mapping[str, Any],
    *,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Build measurements and the evidence-bounded B1 augmentation contract."""

    if len(live_rows) != len(clock_rows):
        raise ValueError("live and clock row counts differ")
    match_ids = sorted(
        {
            str(row["match_id"])
            for row in live_rows
            if isinstance(row.get("match_id"), str)
        }
    )
    split_group_ids = sorted(
        {
            str(row["split_group_id"])
            for row in live_rows
            if isinstance(row.get("split_group_id"), str)
        }
    )
    if len(match_ids) > 1 or len(split_group_ids) > 1:
        raise ValueError("analysis input must contain exactly one replay/split group")
    clock_by_index = {int(row["sample_index"]): row for row in clock_rows}
    if len(clock_by_index) != len(clock_rows):
        raise ValueError("duplicate clock sample_index")

    entity_confidences: list[float] = []
    typed_entity_confidences: list[float] = []
    hp_confidences: list[float] = []
    tower_confidences: list[float] = []
    tower_hp_confidences: list[float] = []
    entity_counts: list[int] = []
    typed_count = hp_count = tower_count = tower_hp_count = 0
    entities_total = 0
    clock_confidences: list[float] = []
    clock_valid = 0

    for row in live_rows:
        public = row.get("public", {})
        entities = public.get("entities", []) if isinstance(public, Mapping) else []
        entity_counts.append(len(entities))
        entities_total += len(entities)
        for entity in entities:
            if not isinstance(entity, Mapping):
                continue
            confidence = float(entity.get("confidence", 0.0))
            entity_confidences.append(confidence)
            valid_identity, stable_key = _identity(entity)
            if valid_identity:
                typed_count += 1
                typed_entity_confidences.append(confidence)
            if entity.get("hp_valid"):
                hp_count += 1
                hp_confidences.append(float(entity.get("hp_confidence", 0.0)))
            if stable_key is not None and stable_key.startswith("tower:"):
                tower_count += 1
                tower_confidences.append(confidence)
                if entity.get("hp_valid"):
                    tower_hp_count += 1
                    tower_hp_confidences.append(float(entity.get("hp_confidence", 0.0)))
        clock_row = clock_by_index[int(row["sample_index"])]
        clock = clock_row.get("public", {}).get("clock", {})
        if clock.get("valid"):
            clock_valid += 1
            clock_confidences.append(float(clock.get("confidence", 0.0)))

    entity_array = np.asarray(entity_counts, dtype=np.float64)
    workload_low = float(np.quantile(entity_array, 1.0 / 3.0))
    workload_high = float(np.quantile(entity_array, 2.0 / 3.0))
    duration_ms = max(int(row.get("timestamp_ms", 0)) for row in live_rows)

    hand_all_scores: list[float] = []
    hand_valid_scores: list[float] = []
    next_all_scores: list[float] = []
    next_valid_scores: list[float] = []
    elixir_valid_scores: list[float] = []
    hand_slot_valid = [0, 0, 0, 0]
    next_valid = elixir_valid = actor_rows = 0
    co_missing: dict[str, Counter[str]] = defaultdict(Counter)
    pattern_rows: list[dict[str, Any]] = []

    for row in live_rows:
        sample_index = int(row["sample_index"])
        clock = clock_by_index[sample_index].get("public", {}).get("clock", {})
        entities = row.get("public", {}).get("entities", [])
        typed_any = any(_identity(entity)[0] for entity in entities)
        hp_any = any(bool(entity.get("hp_valid")) for entity in entities)
        tower_hp_any = any(
            bool(entity.get("hp_valid"))
            and (_identity(entity)[1] or "").startswith("tower:")
            for entity in entities
        )
        workload = _quantile_bucket(len(entities), workload_low, workload_high)
        time_bucket = _time_quartile(int(row.get("timestamp_ms", 0)), duration_ms)
        huds = row.get("offline_privileged_hud", {})
        for actor_id in (0, 1):
            hud = huds.get(str(actor_id), {}) if isinstance(huds, Mapping) else {}
            hand = hud.get("hand", []) if isinstance(hud, Mapping) else []
            if len(hand) != 4:
                raise ValueError(
                    f"sample {sample_index} actor {actor_id}: expected four hand slots"
                )
            hand_valid = [bool(slot.get("valid")) for slot in hand]
            hand_scores = [float(slot.get("score", 0.0)) for slot in hand]
            next_card = hud.get("next_card", {})
            elixir = hud.get("elixir", {})
            next_is_valid = bool(next_card.get("valid"))
            elixir_is_valid = bool(elixir.get("valid"))
            actor_rows += 1
            for slot, valid in enumerate(hand_valid):
                hand_slot_valid[slot] += int(valid)
            next_valid += int(next_is_valid)
            elixir_valid += int(elixir_is_valid)
            hand_all_scores.extend(hand_scores)
            hand_valid_scores.extend(
                score
                for score, valid in zip(hand_scores, hand_valid, strict=True)
                if valid
            )
            next_all_scores.append(float(next_card.get("score", 0.0)))
            if next_is_valid:
                next_valid_scores.append(float(next_card.get("score", 0.0)))
            if elixir_is_valid:
                elixir_valid_scores.append(float(elixir.get("score", 0.0)))

            flags = {
                "clock": bool(clock.get("valid")),
                "elixir": elixir_is_valid,
                "full_hand": all(hand_valid),
                "next": next_is_valid,
                "typed_entity_any": typed_any,
                "hp_any": hp_any,
                "tower_hp_any": tower_hp_any,
            }
            signature = (
                ",".join(name for name, valid in flags.items() if not valid)
                or "none_missing"
            )
            stratum = f"{time_bucket}/{workload}"
            co_missing[stratum][signature] += 1
            pattern_rows.append(
                {
                    "actor_id": actor_id,
                    "sample_index": sample_index,
                    "stratum": stratum,
                    "hand_valid": hand_valid,
                    "hand_score": [_rounded(item) for item in hand_scores],
                    "next_valid": next_is_valid,
                    "next_score": _rounded(float(next_card.get("score", 0.0))),
                    "elixir_valid": elixir_is_valid,
                    "elixir_score": _rounded(float(elixir.get("score", 0.0))),
                    "clock_valid": bool(clock.get("valid")),
                    "clock_score": _rounded(float(clock.get("confidence", 0.0))),
                }
            )

    co_missing_output: dict[str, Any] = {}
    for stratum, counter in sorted(co_missing.items()):
        total = sum(counter.values())
        co_missing_output[stratum] = {
            "rows": total,
            "patterns": [
                {"missing": pattern, "rows": count, "rate": _rate(count, total)}
                for pattern, count in sorted(
                    counter.items(), key=lambda item: (-item[1], item[0])
                )
            ],
        }

    simulator = [_simulator_summary(path) for path in simulator_paths]
    gold = _measure_gold(manual_gold, predicted_labels, annotation_decisions)
    spatial = _measure_spatial(live_rows)

    schedule = {
        "schema": SCHEDULE_SCHEMA,
        "version": "B1",
        "status": "bounded_one_replay_diagnostic_only",
        "seed": seed,
        "source_pattern_rows": len(pattern_rows),
        "actor_safe_channels": [
            "own_hand_0_3",
            "own_next",
            "own_elixir",
            "public_clock",
        ],
        "sampling": {
            "unit": "whole_actor_frame_pattern",
            "application_probability": 1.0,
            "strata": "media_time_quartile_x_live_entity_count_tercile",
            "selection": (
                "For each clean simulator actor row, derive time quartile from within-episode "
                "progress and workload tercile from entity_mask count; uniformly select one "
                "retained pattern row in that stratum with counter-based RNG(seed, epoch, "
                "episode_id, row_index). Never read expert action, reward, or target mask."
            ),
            "co_missingness": "apply all four channel masks/scores from the same selected row",
            "fallback": "fail closed if a stratum is empty; do not borrow a target label or invent noise",
        },
        "transform": {
            "present": "retain the clean simulator value and attach the selected observed score",
            "missing": "write the channel's ordinary missing sentinel and zero confidence",
            "identity_substitution": "disabled",
            "continuous_value_noise": "disabled",
            "position_jitter": "disabled",
        },
        "enabled_measurements": {
            "hand_next_missingness_and_score": "direct current-frame HUD observation",
            "elixir_missingness_and_score": "direct current-frame HUD observation; value error unmeasured",
            "clock_missingness_and_score": "portable current-frame recognizer on retained replay",
        },
        "disabled_insufficient_evidence": {
            "entity_dropout": "no exhaustive arena-entity ground truth",
            "entity_false_identity": "selected proposal review is not a random sample",
            "entity_or_deployment_position_noise": "no independent continuous-position ground truth",
            "hp_or_tower_hp_value_noise": "no independent HP ground truth",
            "hp_or_tower_hp_dropout": "HP bars are visibility-conditional, not random entity misses",
            "card_identity_confusion": "accepted gold has no wrong identities and only one miss; no confusion distribution",
            "elixir_value_noise": "no independent elixir gold",
            "clock_value_noise": "same-replay teacher comparison is not replay-disjoint calibration",
            "temporal_run_length_model": "one replay is insufficient",
        },
        "promotion_blockers": [
            "replay-disjoint calibration",
            "current-client arena detector ground truth",
            "independent HP/tower-HP/elixir continuous-value gold",
            "held-out card identity confusion evidence",
        ],
        "pattern_rows_sha256": hashlib.sha256(
            json.dumps(pattern_rows, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }

    return {
        "schema": SCHEMA,
        "decision": (
            "B1 may replay joint own-HUD/clock missingness as a one-replay diagnostic. "
            "No entity, HP, tower-HP, identity-confusion, elixir-value, or position noise is justified."
        ),
        "provenance": dict(provenance),
        "replay_scope": {
            "match_ids": match_ids,
            "split_group_ids": split_group_ids,
            "first_sample_index": int(live_rows[0]["sample_index"]),
            "last_sample_index": int(live_rows[-1]["sample_index"]),
            "first_timestamp_ms": int(live_rows[0].get("timestamp_ms", 0)),
            "last_timestamp_ms": int(live_rows[-1].get("timestamp_ms", 0)),
            "manual_gold_labels": len(manual_gold.get("labels", [])),
            "selected_entity_reviews": len(annotation_decisions.get("decisions", [])),
        },
        "live_rows": len(live_rows),
        "actor_pattern_rows": actor_rows,
        "measurements": {
            "entity": {
                "detections": entities_total,
                "per_frame": _summary(entity_counts),
                "detection_confidence": _summary(entity_confidences),
                "typed_identity": typed_count,
                "typed_identity_rate_per_detection": _rate(typed_count, entities_total),
                "typed_detection_confidence": _summary(typed_entity_confidences),
                "miss_rate_status": "unavailable_without_exhaustive_entity_gold",
                "false_identity_status": "selected_gold_only; see manual_gold",
            },
            "hp": {
                "valid": hp_count,
                "valid_rate_per_detection": _rate(hp_count, entities_total),
                "confidence_when_valid": _summary(hp_confidences),
                "value_error_status": "unavailable_without_independent_hp_gold",
            },
            "tower": {
                "typed_detections": tower_count,
                "detection_confidence": _summary(tower_confidences),
                "hp_valid": tower_hp_count,
                "hp_valid_rate": _rate(tower_hp_count, tower_count),
                "hp_confidence_when_valid": _summary(tower_hp_confidences),
                "miss_and_value_error_status": "unavailable_without_exhaustive_tower_gold",
            },
            "clock": {
                "valid": clock_valid,
                "rows": len(clock_rows),
                "valid_rate": _rate(clock_valid, len(clock_rows)),
                "confidence_when_valid": _summary(clock_confidences),
                "value_error_status": "same-replay verification only; not replay-disjoint",
            },
            "card_hud": {
                "actor_rows": actor_rows,
                "hand_slot_valid": hand_slot_valid,
                "hand_slot_valid_rate": [
                    _rate(item, actor_rows) for item in hand_slot_valid
                ],
                "hand_score_all": _summary(hand_all_scores),
                "hand_score_when_valid": _summary(hand_valid_scores),
                "next_valid": next_valid,
                "next_valid_rate": _rate(next_valid, actor_rows),
                "next_score_all": _summary(next_all_scores),
                "next_score_when_valid": _summary(next_valid_scores),
            },
            "elixir": {
                "valid": elixir_valid,
                "actor_rows": actor_rows,
                "valid_rate": _rate(elixir_valid, actor_rows),
                "score_when_valid": _summary(elixir_valid_scores),
                "value_error_status": "unavailable_without_independent_elixir_gold",
            },
            "manual_gold": gold,
            "spatial": spatial,
            "co_missingness": {
                "workload_entity_count_tercile_thresholds": {
                    "low_max": _rounded(workload_low),
                    "high_min": _rounded(workload_high),
                },
                "time_definition": "media elapsed quartiles q0..q3",
                "channels": [
                    "clock",
                    "elixir",
                    "full_hand",
                    "next",
                    "typed_entity_any",
                    "hp_any",
                    "tower_hp_any",
                ],
                "strata": co_missing_output,
            },
        },
        "clean_simulator_corpora": simulator,
        "schedule": schedule,
    }


def _markdown(report: Mapping[str, Any]) -> str:
    measurements = report["measurements"]
    schedule = report["schedule"]
    gold = measurements["manual_gold"]
    lines = [
        "# B1 empirical corruption and missingness schedule",
        "",
        f"Decision: **{report['decision']}**",
        "",
        "## Measured retained evidence",
        "",
        "| Channel | Coverage / correctness | What is not established |",
        "|---|---:|---|",
        f"| Entity typed identity | {measurements['entity']['typed_identity_rate_per_detection']:.3%} of detector boxes | Entity recall and population false-identity rate |",
        f"| HP visible/accepted | {measurements['hp']['valid_rate_per_detection']:.3%} of detector boxes | HP value error and entity-conditional miss rate |",
        f"| Tower HP visible/accepted | {measurements['tower']['hp_valid_rate']:.3%} of typed tower boxes | Tower recall and HP value error |",
        f"| Clock | {measurements['clock']['valid_rate']:.3%} of frames | Replay-disjoint value calibration |",
        f"| Hand slots | {', '.join(f'{item:.3%}' for item in measurements['card_hud']['hand_slot_valid_rate'])} | Replay-disjoint card confusion |",
        f"| Next | {measurements['card_hud']['next_valid_rate']:.3%} of actor rows | Replay-disjoint card confusion |",
        f"| Elixir | {measurements['elixir']['valid_rate']:.3%} of actor rows | Continuous value error |",
        f"| Accepted card gold | {gold['card_identity_accepted_gold']['correct']}/{gold['card_identity_accepted_gold']['gold']} correct, {gold['card_identity_accepted_gold']['missed']} miss | Withheld identities are unknown, not negatives |",
        f"| Accepted deployment gold | {gold['deployment_tile_accepted_gold']['exact']}/{gold['deployment_tile_accepted_gold']['gold']} exact tiles | Candidate-conditioned, one replay |",
        "",
        "Confidence values above are detector/HUD scores, not calibrated correctness probabilities.",
        "",
        "## B1 transform",
        "",
        f"Status: `{schedule['status']}`. For each simulator actor row, select one whole retained actor-frame pattern within the same media-time quartile and entity-load tercile. Apply hand, Next, elixir, and clock presence plus their observed scores together. Present fields retain the clean simulator value; missing fields use their normal missing sentinel and zero confidence. Application probability is {schedule['sampling']['application_probability']:.1f}, which matches a live observation on every actor step rather than inventing a clean/corrupt mixture.",
        "",
        "The selector is counter-based and may use only seed, epoch, episode ID, row index, entity count, and within-episode progress. It may not inspect an expert action, reward, target mask, future frame, or opponent-private HUD.",
        "",
        "## Explicitly disabled",
        "",
    ]
    for channel, reason in schedule["disabled_insufficient_evidence"].items():
        lines.append(f"- `{channel}`: {reason}.")
    lines.extend(
        [
            "",
            "## Provenance and limits",
            "",
            "This is a deterministic analysis of one retained permissioned replay plus current simulator-derived causal corpora. It performs no detector inference, download, training, or target-label read. The one-replay schedule is suitable only for a bounded B1 diagnostic; replay-disjoint calibration remains a promotion blocker.",
            "",
            f"Schema: `{report['schema']}`; schedule schema: `{schedule['schema']}`; pattern digest: `{schedule['pattern_rows_sha256']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--live-neutral",
        type=Path,
        default=root
        / "datasets/derived/tv_royale_youtube_fullmatch_cost_conditioned_hTG8dM4KtM4_20260817/neutral_sequence_cost_conditioned.jsonl.gz",
    )
    parser.add_argument(
        "--clock-neutral",
        type=Path,
        default=root
        / "datasets/derived/tv_royale_portable_clock_precision_v2_merged_hTG8dM4KtM4_20260817/neutral_sequence_clocked.jsonl.gz",
    )
    parser.add_argument(
        "--manual-gold",
        type=Path,
        default=root
        / "reports/tv_royale_youtube_action_visual_gold_hTG8dM4KtM4_20260817.json",
    )
    parser.add_argument(
        "--predicted-labels",
        type=Path,
        default=root
        / "datasets/derived/tv_royale_youtube_fullmatch_cost_conditioned_hTG8dM4KtM4_20260817/cached_action_labels_next_gold_v4.json",
    )
    parser.add_argument(
        "--annotation-decisions",
        type=Path,
        default=root
        / "reports/current_client_annotation_decisions_hTG8dM4KtM4_v1.json",
    )
    parser.add_argument(
        "--simulator-corpus",
        type=Path,
        action="append",
        default=None,
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=root / "reports/b1_empirical_corruption_schedule_20260817.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=root / "reports/b1_empirical_corruption_schedule_20260817.md",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(__file__).resolve().parents[1]
    simulator_paths = args.simulator_corpus or [
        root
        / "datasets/derived/fresh_compact_causal_v2_seed1062401/pretrain_balanced_public_mask_contract_v2.npz",
        root
        / "datasets/derived/structured_oracle_mix_seed1063501/mix_oracle3_12k_public_mask_contract_v2.npz",
    ]
    input_paths = {
        "live_neutral": args.live_neutral,
        "clock_neutral": args.clock_neutral,
        "manual_gold": args.manual_gold,
        "predicted_labels": args.predicted_labels,
        "annotation_decisions": args.annotation_decisions,
    }
    lineage_paths = {
        "source_acquisition_manifest": root
        / "datasets/external/tv_royale_youtube_fullmatch_20260817/hTG8dM4KtM4/manifest.json",
        "live_semantic_manifest": root
        / "datasets/derived/tv_royale_youtube_fullmatch_cost_conditioned_hTG8dM4KtM4_20260817/manifest.json",
        "clock_merge_manifest": root
        / "datasets/derived/tv_royale_portable_clock_precision_v2_merged_hTG8dM4KtM4_20260817/manifest.json",
    }
    input_paths.update(lineage_paths)
    provenance = {
        name: {"path": str(path), "sha256": _sha256(path)}
        for name, path in input_paths.items()
    }
    report = build_analysis(
        _load_jsonl_gz(args.live_neutral),
        _load_jsonl_gz(args.clock_neutral),
        _load_json(args.manual_gold),
        _load_json(args.predicted_labels),
        _load_json(args.annotation_decisions),
        simulator_paths,
        provenance,
        seed=args.seed,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output_md.write_text(_markdown(report))
    print(
        json.dumps(
            {
                "json": str(args.output_json),
                "json_sha256": _sha256(args.output_json),
                "markdown": str(args.output_md),
                "markdown_sha256": _sha256(args.output_md),
                "schedule": report["schedule"]["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
