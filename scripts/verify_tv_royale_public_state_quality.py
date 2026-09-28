"""Verify confidence-aware public-state coverage across a finalized TV corpus."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.oracle_corpus import atomic_write_json, file_sha256


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return payload


def _same_path(raw: object, expected: Path) -> bool:
    try:
        return Path(str(raw)).resolve() == expected.resolve()
    except (OSError, RuntimeError, ValueError):
        return False


def _arena_number(name: str) -> int:
    prefix, separator, value = name.rpartition("_")
    if not separator or prefix != "arena" or not value.isdigit():
        raise ValueError(f"invalid arena name: {name}")
    return int(value)


def _empty_counts() -> dict[str, float | int]:
    return {
        "games": 0,
        "samples": 0,
        "visible_entities": 0,
        "position_measurements": 0,
        "entity_hp_measurements": 0,
        "entity_hp_confidence_sum": 0.0,
        "motion_direction_measurements": 0,
        "tower_hp_measurements": 0,
    }


def _add_counts(
    destination: dict[str, float | int], source: dict[str, float | int]
) -> None:
    for name, value in source.items():
        destination[name] += value


def _rates(counts: dict[str, float | int]) -> dict[str, float | int]:
    visible = int(counts["visible_entities"])
    samples = int(counts["samples"])
    hp = int(counts["entity_hp_measurements"])
    return {
        **counts,
        "position_coverage": int(counts["position_measurements"])
        / max(1, visible),
        "entity_hp_coverage": hp / max(1, visible),
        "mean_entity_hp_confidence": float(counts["entity_hp_confidence_sum"])
        / max(1, hp),
        "motion_direction_coverage": int(counts["motion_direction_measurements"])
        / max(1, visible),
        "tower_hp_measurements_per_sample": int(counts["tower_hp_measurements"])
        / max(1, samples),
    }


def _sidecar_counts(path: Path) -> dict[str, float | int]:
    with np.load(path, allow_pickle=False) as payload:
        required = {
            "source_frames",
            "entity_features",
            "entity_mask",
            "entity_id_confidence",
            "entity_feature_confidence",
            "global_feature_confidence",
            "schema_version",
        }
        missing = sorted(required - set(payload.files))
        if missing:
            raise ValueError(f"public sidecar lacks arrays {missing}: {path}")
        if int(np.asarray(payload["schema_version"]).item()) != 2:
            raise ValueError(f"unsupported public sidecar schema: {path}")
        source_frames = np.asarray(payload["source_frames"])
        entity_features = np.asarray(payload["entity_features"])
        entity_mask = np.asarray(payload["entity_mask"], dtype=np.bool_)
        entity_id_confidence = np.asarray(payload["entity_id_confidence"])
        feature_confidence = np.asarray(payload["entity_feature_confidence"])
        global_confidence = np.asarray(payload["global_feature_confidence"])
    samples = int(source_frames.size)
    if (
        entity_features.ndim != 3
        or entity_features.shape[:2] != entity_mask.shape
        or entity_id_confidence.shape != entity_mask.shape
        or feature_confidence.shape != entity_features.shape
        or entity_features.shape[0] != samples
        or entity_features.shape[2] <= 28
        or global_confidence.ndim != 2
        or global_confidence.shape[0] != samples
        or global_confidence.shape[1] < 14
    ):
        raise ValueError(f"public sidecar array shapes are inconsistent: {path}")
    for name, values in (
        ("entity features", entity_features),
        ("entity identity confidence", entity_id_confidence),
        ("entity feature confidence", feature_confidence),
        ("global feature confidence", global_confidence),
    ):
        if not np.all(np.isfinite(values)):
            raise ValueError(f"public sidecar has non-finite {name}: {path}")
    for name, confidence in (
        ("entity identity", entity_id_confidence),
        ("entity feature", feature_confidence),
        ("global feature", global_confidence),
    ):
        if np.any(confidence < 0.0) or np.any(confidence > 1.0):
            raise ValueError(f"public sidecar has invalid {name} confidence: {path}")
    visible = int(np.count_nonzero(entity_mask))
    if visible <= 0 or samples <= 0:
        raise ValueError(f"public sidecar has no visible samples: {path}")
    if np.any(entity_id_confidence[entity_mask] <= 0.0):
        raise ValueError(f"visible entity lacks identity confidence: {path}")
    positioned = (
        entity_mask
        & (feature_confidence[..., 0] > 0.0)
        & (feature_confidence[..., 1] > 0.0)
    )
    hp_confidence = feature_confidence[..., 9]
    observed_hp = entity_mask & (hp_confidence > 0.0)
    observed_motion = entity_mask & (feature_confidence[..., 27] > 0.0)
    return {
        "games": 1,
        "samples": samples,
        "visible_entities": visible,
        "position_measurements": int(np.count_nonzero(positioned)),
        "entity_hp_measurements": int(np.count_nonzero(observed_hp)),
        "entity_hp_confidence_sum": float(hp_confidence[observed_hp].sum()),
        "motion_direction_measurements": int(np.count_nonzero(observed_motion)),
        "tower_hp_measurements": int(
            np.count_nonzero(global_confidence[:, 8:14] > 0.0)
        ),
    }


def _verify_manifest_statistics(
    game_manifest: dict[str, Any], counts: dict[str, float | int], *, path: Path
) -> None:
    statistics = (game_manifest.get("public_state_v2") or {}).get("statistics")
    if not isinstance(statistics, dict):
        raise TypeError(f"game manifest lacks public-state statistics: {path}")
    expected = {
        "samples": int(counts["samples"]),
        "visible_entities": int(counts["visible_entities"]),
        "entities_with_measured_hp": int(counts["entity_hp_measurements"]),
        "entities_with_motion_direction": int(
            counts["motion_direction_measurements"]
        ),
        "tower_hp_measurements": int(counts["tower_hp_measurements"]),
    }
    for name, value in expected.items():
        if int(statistics.get(name, -1)) != value:
            raise ValueError(f"game manifest statistic changed ({name}): {path}")
    rates = _rates(counts)
    for name in ("entity_hp_coverage", "motion_direction_coverage"):
        if not math.isclose(
            float(statistics.get(name, math.nan)),
            float(rates[name]),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"game manifest statistic changed ({name}): {path}")
    if not math.isclose(
        float(statistics.get("mean_observed_hp_confidence", math.nan)),
        float(rates["mean_entity_hp_confidence"]),
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise ValueError(
            f"game manifest statistic changed (mean HP confidence): {path}"
        )


def verify_public_state_quality(
    *,
    run_manifest_path: Path,
    target_games: int,
    expected_arenas: int,
    minimum_entity_hp_coverage: float = 0.50,
    minimum_arena_entity_hp_coverage: float = 0.45,
    minimum_mean_entity_hp_confidence: float = 0.45,
    minimum_motion_direction_coverage: float = 0.30,
    minimum_arena_motion_direction_coverage: float = 0.25,
    minimum_tower_hp_measurements_per_sample: float = 3.0,
    minimum_arena_tower_hp_measurements_per_sample: float = 2.5,
) -> dict[str, Any]:
    if target_games <= 0 or expected_arenas <= 0:
        raise ValueError("target games and expected arenas must be positive")
    run_manifest_path = run_manifest_path.resolve()
    run_root = run_manifest_path.parent
    run = _object(run_manifest_path)
    records = [
        row
        for row in run.get("records", ())
        if isinstance(row, dict) and row.get("status") == "complete"
    ]
    if int(run.get("completed_games", -1)) != len(records):
        raise ValueError("run completed-game count differs from its records")
    aggregate = _empty_counts()
    by_arena_counts: defaultdict[str, dict[str, float | int]] = defaultdict(
        _empty_counts
    )
    evidence_sha256: dict[str, str] = {
        str(run_manifest_path): file_sha256(run_manifest_path)
    }
    for record in records:
        arena = str(record.get("arena", ""))
        _arena_number(arena)
        corpus = Path(str(record.get("corpus", ""))).resolve()
        if not corpus.is_relative_to(run_root):
            raise ValueError(f"corpus escapes run root: {corpus}")
        game_manifest_path = corpus.parent / "manifest.json"
        game_manifest = _object(game_manifest_path)
        sidecar_path = Path(str(record.get("public_state_v2", ""))).resolve()
        sidecar_manifest = game_manifest.get("public_state_v2") or {}
        if (
            game_manifest.get("arena") != arena
            or game_manifest.get("replay") != record.get("replay")
            or not sidecar_path.is_relative_to(run_root)
            or not sidecar_path.is_file()
            or not _same_path(sidecar_manifest.get("path"), sidecar_path)
            or record.get("public_state_v2_sha256") != file_sha256(sidecar_path)
            or sidecar_manifest.get("sha256") != file_sha256(sidecar_path)
        ):
            raise ValueError(f"public sidecar provenance mismatch: {game_manifest_path}")
        counts = _sidecar_counts(sidecar_path)
        _verify_manifest_statistics(game_manifest, counts, path=game_manifest_path)
        _add_counts(aggregate, counts)
        _add_counts(by_arena_counts[arena], counts)
        evidence_sha256[str(game_manifest_path)] = file_sha256(game_manifest_path)
        evidence_sha256[str(sidecar_path)] = file_sha256(sidecar_path)

    aggregate_rates = _rates(aggregate)
    by_arena = {
        arena: _rates(by_arena_counts[arena])
        for arena in sorted(by_arena_counts, key=_arena_number)
    }
    gates = {
        "complete_game_count": len(records) == target_games,
        "arena_count": len(by_arena) == expected_arenas,
        "all_visible_entities_positioned": float(
            aggregate_rates["position_coverage"]
        )
        == 1.0
        and all(float(row["position_coverage"]) == 1.0 for row in by_arena.values()),
        "entity_hp_coverage": float(aggregate_rates["entity_hp_coverage"])
        >= minimum_entity_hp_coverage,
        "entity_hp_coverage_each_arena": all(
            float(row["entity_hp_coverage"]) >= minimum_arena_entity_hp_coverage
            for row in by_arena.values()
        ),
        "mean_entity_hp_confidence": float(
            aggregate_rates["mean_entity_hp_confidence"]
        )
        >= minimum_mean_entity_hp_confidence,
        "motion_direction_coverage": float(
            aggregate_rates["motion_direction_coverage"]
        )
        >= minimum_motion_direction_coverage,
        "motion_direction_coverage_each_arena": all(
            float(row["motion_direction_coverage"])
            >= minimum_arena_motion_direction_coverage
            for row in by_arena.values()
        ),
        "tower_hp_measurements_per_sample": float(
            aggregate_rates["tower_hp_measurements_per_sample"]
        )
        >= minimum_tower_hp_measurements_per_sample,
        "tower_hp_measurements_per_sample_each_arena": all(
            float(row["tower_hp_measurements_per_sample"])
            >= minimum_arena_tower_hp_measurements_per_sample
            for row in by_arena.values()
        ),
    }
    return {
        "schema": "tv-royale-public-state-quality-v1",
        "status": "passed" if all(gates.values()) else "rejected",
        "passes": all(gates.values()),
        "run_manifest": str(run_manifest_path),
        "run_manifest_sha256": file_sha256(run_manifest_path),
        "thresholds": {
            "target_games": target_games,
            "expected_arenas": expected_arenas,
            "minimum_entity_hp_coverage": minimum_entity_hp_coverage,
            "minimum_arena_entity_hp_coverage": minimum_arena_entity_hp_coverage,
            "minimum_mean_entity_hp_confidence": minimum_mean_entity_hp_confidence,
            "minimum_motion_direction_coverage": minimum_motion_direction_coverage,
            "minimum_arena_motion_direction_coverage": minimum_arena_motion_direction_coverage,
            "minimum_tower_hp_measurements_per_sample": minimum_tower_hp_measurements_per_sample,
            "minimum_arena_tower_hp_measurements_per_sample": minimum_arena_tower_hp_measurements_per_sample,
        },
        "gates": gates,
        "aggregate": aggregate_rates,
        "by_arena": by_arena,
        "evidence_sha256": evidence_sha256,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-manifest", required=True, type=Path)
    parser.add_argument("--target-games", required=True, type=int)
    parser.add_argument("--expected-arenas", required=True, type=int)
    parser.add_argument("--minimum-entity-hp-coverage", type=float, default=0.50)
    parser.add_argument(
        "--minimum-arena-entity-hp-coverage", type=float, default=0.45
    )
    parser.add_argument(
        "--minimum-mean-entity-hp-confidence", type=float, default=0.45
    )
    parser.add_argument(
        "--minimum-motion-direction-coverage", type=float, default=0.30
    )
    parser.add_argument(
        "--minimum-arena-motion-direction-coverage", type=float, default=0.25
    )
    parser.add_argument(
        "--minimum-tower-hp-measurements-per-sample", type=float, default=3.0
    )
    parser.add_argument(
        "--minimum-arena-tower-hp-measurements-per-sample",
        type=float,
        default=2.5,
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = verify_public_state_quality(
        run_manifest_path=args.run_manifest,
        target_games=args.target_games,
        expected_arenas=args.expected_arenas,
        minimum_entity_hp_coverage=args.minimum_entity_hp_coverage,
        minimum_arena_entity_hp_coverage=args.minimum_arena_entity_hp_coverage,
        minimum_mean_entity_hp_confidence=args.minimum_mean_entity_hp_confidence,
        minimum_motion_direction_coverage=args.minimum_motion_direction_coverage,
        minimum_arena_motion_direction_coverage=args.minimum_arena_motion_direction_coverage,
        minimum_tower_hp_measurements_per_sample=args.minimum_tower_hp_measurements_per_sample,
        minimum_arena_tower_hp_measurements_per_sample=args.minimum_arena_tower_hp_measurements_per_sample,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output, payload)
    print(json.dumps(payload, sort_keys=True))
    if not payload["passes"]:
        raise SystemExit("TV Royale public-state quality gate rejected the corpus")


if __name__ == "__main__":
    main()
