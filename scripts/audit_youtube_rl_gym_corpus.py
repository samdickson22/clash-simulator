"""Read-only coverage audit for a persistent YouTube real-game corpus.

The corpus root must contain one directory per match with ``manifest.json`` and
the manifest-declared neutral JSONL sequence. The command writes nothing: JSON
or Markdown is emitted to stdout for an RL-gym validation handoff.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, TextIO

AUDIT_SCHEMA = "clasher.youtube.rl_gym_corpus_audit.v1"
MANIFEST_COUNTERS = (
    "detections",
    "typed_identity_valid",
    "hp_valid",
    "clock_valid_frames",
    "play_events",
    "play_events_valid",
    "play_event_identity_valid",
    "play_event_placement_valid",
    "status_valid",
    "projectile_target_valid",
)


class CorpusAuditError(ValueError):
    """Raised when a corpus root cannot be audited safely."""


def _object(value: object, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CorpusAuditError(f"{context} must be a JSON object")
    return value


def _integer(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CorpusAuditError(f"{context} must be numeric")
    result = int(value)
    if result < 0 or result != value:
        raise CorpusAuditError(f"{context} must be a non-negative integer")
    return result


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return _object(json.load(stream), context=str(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusAuditError(f"cannot read JSON {path}: {exc}") from exc


def _neutral_path(manifest_path: Path, manifest: Mapping[str, Any]) -> Path:
    artifacts = _object(
        manifest.get("artifacts"), context=f"{manifest_path}: artifacts"
    )
    neutral = _object(
        artifacts.get("neutral_sequence"),
        context=f"{manifest_path}: artifacts.neutral_sequence",
    )
    raw_path = neutral.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise CorpusAuditError(
            f"{manifest_path}: artifacts.neutral_sequence.path is missing"
        )
    declared = Path(raw_path)
    candidates: list[Path] = []
    if not declared.is_absolute():
        candidates.extend(
            (
                manifest_path.parent / declared,
                manifest_path.parent.parent / declared,
            )
        )
    candidates.append(manifest_path.parent / declared.name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise CorpusAuditError(
        f"neutral sequence declared by {manifest_path} is absent under the supplied root: "
        f"{declared.name}"
    )


def _jsonl_stream(
    path: Path,
    stream: TextIO,
) -> Iterable[tuple[int, Mapping[str, Any]]]:
    for line_number, line in enumerate(stream, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CorpusAuditError(
                f"invalid JSONL at {path}:{line_number}: {exc}"
            ) from exc
        yield line_number, _object(value, context=f"{path}:{line_number}")


def _jsonl(path: Path) -> Iterable[tuple[int, Mapping[str, Any]]]:
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                yield from _jsonl_stream(path, stream)
        else:
            with path.open("r", encoding="utf-8") as stream:
                yield from _jsonl_stream(path, stream)
    except OSError as exc:
        raise CorpusAuditError(f"cannot read neutral sequence {path}: {exc}") from exc


def _coverage(valid: int, total: int) -> dict[str, object]:
    return {
        "availability": "available" if valid > 0 else "unavailable",
        "valid": valid,
        "total": total,
        "rate": None if total == 0 else round(valid / total, 6),
    }


def _percentile(sorted_values: list[float], quantile: float) -> float | None:
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(sorted_values[lower], 6)
    weight = position - lower
    return round(
        sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight,
        6,
    )


def _confidence_summary(values: list[float]) -> dict[str, object]:
    values.sort()
    if not values:
        return {
            "count": 0,
            "minimum": None,
            "p10": None,
            "median": None,
            "p90": None,
            "maximum": None,
            "mean": None,
        }
    return {
        "count": len(values),
        "minimum": round(values[0], 6),
        "p10": _percentile(values, 0.10),
        "median": _percentile(values, 0.50),
        "p90": _percentile(values, 0.90),
        "maximum": round(values[-1], 6),
        "mean": round(sum(values) / len(values), 6),
    }


def _valid_world_position(value: object) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == 2
        and all(
            isinstance(coordinate, (int, float))
            and not isinstance(coordinate, bool)
            and math.isfinite(float(coordinate))
            for coordinate in value
        )
    )


def audit_corpus(root: str | Path) -> dict[str, object]:
    """Audit ``root`` without modifying it and return a JSON-serializable summary."""

    corpus_root = Path(root).expanduser()
    if not corpus_root.exists():
        raise CorpusAuditError(f"corpus root does not exist: {corpus_root}")
    if not corpus_root.is_dir():
        raise CorpusAuditError(f"corpus root is not a directory: {corpus_root}")
    manifest_paths = sorted(corpus_root.glob("*/manifest.json"))
    if not manifest_paths:
        raise CorpusAuditError(
            f"corpus root contains no match manifests: {corpus_root}"
        )

    manifest_totals: Counter[str] = Counter()
    manifest_counter_presence: Counter[str] = Counter()
    declared_frames = 0
    offline_action_targets = 0
    actor_rows = 0
    actual_frames = 0
    detections = 0
    typed_identity_valid = 0
    hp_valid = 0
    clock_valid = 0
    position_resolved = 0
    position_malformed = 0
    position_confidence_missing = 0
    status_valid = 0
    projectile_target_valid = 0
    position_confidences: list[float] = []
    coordinate_frames: Counter[str] = Counter()
    status_unavailable_reasons: Counter[str] = Counter()
    projectile_unavailable_reasons: Counter[str] = Counter()
    match_ids: set[str] = set()
    frame_row_mismatches: list[dict[str, object]] = []

    for manifest_path in manifest_paths:
        manifest = _load_json(manifest_path)
        coverage = _object(
            manifest.get("coverage"), context=f"{manifest_path}: coverage"
        )
        for name in MANIFEST_COUNTERS:
            if name in coverage:
                manifest_totals[name] += _integer(
                    coverage[name], context=f"{manifest_path}: coverage.{name}"
                )
                manifest_counter_presence[name] += 1
        artifacts = _object(
            manifest.get("artifacts"), context=f"{manifest_path}: artifacts"
        )
        neutral = _object(
            artifacts.get("neutral_sequence"),
            context=f"{manifest_path}: artifacts.neutral_sequence",
        )
        declared = _integer(
            neutral.get("rows"),
            context=f"{manifest_path}: artifacts.neutral_sequence.rows",
        )
        declared_frames += declared
        trajectories = artifacts.get("actor_trajectories", [])
        if not isinstance(trajectories, list):
            raise CorpusAuditError(
                f"{manifest_path}: artifacts.actor_trajectories must be a list"
            )
        for index, trajectory in enumerate(trajectories):
            trajectory_object = _object(
                trajectory,
                context=f"{manifest_path}: actor_trajectories[{index}]",
            )
            actor_rows += _integer(
                trajectory_object.get("rows"),
                context=f"{manifest_path}: actor_trajectories[{index}].rows",
            )
        target_artifact = artifacts.get("offline_actor_targets")
        if target_artifact is not None:
            target_object = _object(
                target_artifact,
                context=f"{manifest_path}: artifacts.offline_actor_targets",
            )
            offline_action_targets += _integer(
                target_object.get("rows"),
                context=f"{manifest_path}: offline_actor_targets.rows",
            )

        match_frames = 0
        neutral_path = _neutral_path(manifest_path, manifest)
        for line_number, frame in _jsonl(neutral_path):
            match_frames += 1
            actual_frames += 1
            match_id = frame.get("match_id")
            if not isinstance(match_id, str) or not match_id:
                raise CorpusAuditError(
                    f"{neutral_path}:{line_number}: match_id is missing"
                )
            match_ids.add(match_id)
            public = _object(
                frame.get("public"), context=f"{neutral_path}:{line_number}: public"
            )
            coordinate_frame = public.get("coordinate_frame")
            coordinate_frames[
                coordinate_frame if isinstance(coordinate_frame, str) else "missing"
            ] += 1
            clock = public.get("clock")
            if isinstance(clock, Mapping) and clock.get("valid") is True:
                clock_valid += 1
            entities = public.get("entities")
            if not isinstance(entities, list):
                raise CorpusAuditError(
                    f"{neutral_path}:{line_number}: public.entities must be a list"
                )
            for entity_index, raw_entity in enumerate(entities):
                entity = _object(
                    raw_entity,
                    context=(f"{neutral_path}:{line_number}: entities[{entity_index}]"),
                )
                detections += 1
                identity = entity.get("identity")
                if isinstance(identity, Mapping) and identity.get("valid") is True:
                    typed_identity_valid += 1
                if entity.get("hp_valid") is True:
                    hp_valid += 1
                world_position = entity.get("world_position")
                if world_position is not None:
                    if _valid_world_position(world_position):
                        position_resolved += 1
                        confidence = entity.get("confidence")
                        if (
                            isinstance(confidence, (int, float))
                            and not isinstance(confidence, bool)
                            and math.isfinite(float(confidence))
                        ):
                            position_confidences.append(float(confidence))
                        else:
                            position_confidence_missing += 1
                    else:
                        position_malformed += 1
                status = entity.get("status")
                if isinstance(status, Mapping) and status.get("valid") is True:
                    status_valid += 1
                else:
                    reason = (
                        status.get("reason") if isinstance(status, Mapping) else None
                    )
                    status_unavailable_reasons[
                        reason
                        if isinstance(reason, str) and reason
                        else "missing_reason"
                    ] += 1
                projectile = entity.get("projectile_target")
                if isinstance(projectile, Mapping) and projectile.get("valid") is True:
                    projectile_target_valid += 1
                else:
                    reason = (
                        projectile.get("reason")
                        if isinstance(projectile, Mapping)
                        else None
                    )
                    projectile_unavailable_reasons[
                        reason
                        if isinstance(reason, str) and reason
                        else "missing_reason"
                    ] += 1
        if match_frames != declared:
            frame_row_mismatches.append(
                {
                    "match_directory": manifest_path.parent.name,
                    "declared": declared,
                    "observed": match_frames,
                }
            )

    scanned = {
        "detections": detections,
        "typed_identity_valid": typed_identity_valid,
        "hp_valid": hp_valid,
        "clock_valid_frames": clock_valid,
        "status_valid": status_valid,
        "projectile_target_valid": projectile_target_valid,
    }
    manifest_mismatches: dict[str, dict[str, int]] = {}
    for name, observed in scanned.items():
        if manifest_counter_presence[name] != len(manifest_paths):
            continue
        expected = manifest_totals[name]
        if expected != observed:
            manifest_mismatches[name] = {
                "manifest": expected,
                "observed": observed,
            }

    play_events = manifest_totals["play_events"]
    play_valid = manifest_totals["play_events_valid"]
    play_identity = manifest_totals["play_event_identity_valid"]
    play_placement = manifest_totals["play_event_placement_valid"]
    report: dict[str, object] = {
        "schema": AUDIT_SCHEMA,
        "root": str(corpus_root.resolve()),
        "matches": {
            "directories": len(manifest_paths),
            "distinct_match_ids": len(match_ids),
        },
        "frames": {
            "observed": actual_frames,
            "manifest_declared": declared_frames,
            "actor_overlay_rows": actor_rows,
        },
        "entities": {
            "detections": detections,
            "typed_identity": _coverage(typed_identity_valid, detections),
            "hp": _coverage(hp_valid, detections),
            "position": {
                **_coverage(position_resolved, detections),
                "malformed_non_null": position_malformed,
                "coordinate_frames": dict(sorted(coordinate_frames.items())),
                "resolved_confidence": _confidence_summary(position_confidences),
                "resolved_confidence_missing": position_confidence_missing,
            },
            "status_targets": {
                **_coverage(status_valid, detections),
                "unavailable_reasons": dict(status_unavailable_reasons.most_common()),
            },
            "projectile_targets": {
                **_coverage(projectile_target_valid, detections),
                "unavailable_reasons": dict(
                    projectile_unavailable_reasons.most_common()
                ),
            },
        },
        "clock": _coverage(clock_valid, actual_frames),
        "actions": {
            "offline_only": True,
            "events": play_events,
            "complete_identity_and_placement": _coverage(play_valid, play_events),
            "typed_identity": _coverage(play_identity, play_events),
            "placement": _coverage(play_placement, play_events),
            "actor_training_targets": offline_action_targets,
        },
        "rl_gym_validation": {
            "actor_state_signals": [
                "typed_entity_identity",
                "entity_hp_fraction",
                "resolved_world_position",
                "public_clock",
            ],
            "offline_only_targets": ["card_play_action"],
            "explicitly_unavailable_targets": [
                "entity_status",
                "projectile_target",
            ],
        },
        "integrity": {
            "frame_row_mismatches": frame_row_mismatches,
            "manifest_counter_mismatches": manifest_mismatches,
            "clean": not frame_row_mismatches and not manifest_mismatches,
        },
    }
    return report


def _rate_text(metric: Mapping[str, object]) -> str:
    rate = metric.get("rate")
    return "n/a" if not isinstance(rate, (int, float)) else f"{float(rate) * 100:.2f}%"


def render_markdown(report: Mapping[str, object]) -> str:
    """Render a concise human-readable audit without losing JSON precision."""

    matches = _object(report["matches"], context="report.matches")
    frames = _object(report["frames"], context="report.frames")
    entities = _object(report["entities"], context="report.entities")
    actions = _object(report["actions"], context="report.actions")
    clock = _object(report["clock"], context="report.clock")
    position = _object(entities["position"], context="report.entities.position")
    confidence = _object(
        position["resolved_confidence"], context="report.position.confidence"
    )
    rows = [
        ("Typed entity identity", _object(entities["typed_identity"], context="typed")),
        ("Entity HP", _object(entities["hp"], context="hp")),
        ("Resolved world position", position),
        ("Public clock", clock),
        (
            "Complete offline action label",
            _object(actions["complete_identity_and_placement"], context="actions"),
        ),
        (
            "Offline action identity",
            _object(actions["typed_identity"], context="action identity"),
        ),
        (
            "Offline action placement",
            _object(actions["placement"], context="action placement"),
        ),
        ("Entity status target", _object(entities["status_targets"], context="status")),
        (
            "Projectile target",
            _object(entities["projectile_targets"], context="projectile"),
        ),
    ]
    lines = [
        "# YouTube real-game corpus RL-gym audit",
        "",
        f"- Root: `{report['root']}`",
        (
            f"- Matches: {matches['directories']} directories / "
            f"{matches['distinct_match_ids']} distinct IDs"
        ),
        (
            f"- Frames: {frames['observed']} observed / "
            f"{frames['manifest_declared']} manifest-declared"
        ),
        f"- Entity detections: {entities['detections']}",
        "",
        "| Signal or target | Valid | Total | Coverage | Availability |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for label, metric in rows:
        lines.append(
            f"| {label} | {metric['valid']} | {metric['total']} | "
            f"{_rate_text(metric)} | {metric['availability']} |"
        )
    lines.extend(
        [
            "",
            (
                "Position confidence among resolved detections: "
                f"mean={confidence['mean']}, median={confidence['median']}, "
                f"p10={confidence['p10']}, p90={confidence['p90']}."
            ),
            "",
            (
                "Action labels are offline-only. Entity status and projectile-target "
                "supervision remain explicitly unavailable and must not be inferred "
                "from zero counts."
            ),
            "",
            f"Integrity checks: `clean={_object(report['integrity'], context='integrity')['clean']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit a persistent YouTube corpus for RL-gym signal coverage."
    )
    parser.add_argument(
        "root",
        type=Path,
        help="root containing one manifest-bearing directory per real-game match",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="stdout format (default: json)",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    args = _parser().parse_args(argv)
    try:
        report = audit_corpus(args.root)
    except CorpusAuditError as exc:
        print(f"error: {exc}", file=stderr)
        return 2
    if args.format == "markdown":
        stdout.write(render_markdown(report))
    else:
        json.dump(report, stdout, indent=2, sort_keys=True)
        stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
