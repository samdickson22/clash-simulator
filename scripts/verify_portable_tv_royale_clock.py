from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from itertools import pairwise
from pathlib import Path
from typing import Any

HOLDOUT_BLOCKS_MS = (
    (30_000, 45_000),
    (90_000, 105_000),
    (150_000, 165_000),
    (210_000, 225_000),
    (270_000, 285_000),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _teacher(path: Path) -> dict[int, tuple[int, int]]:
    rows: dict[int, tuple[int, int]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            output_pts = int(row["output_pts"])
            clock = row["public"]["clock"]
            if (
                output_pts % 5 == 0
                and clock.get("valid")
                and int(clock["anchor_output_pts"]) == output_pts
            ):
                rows[output_pts] = (int(row["timestamp_ms"]), int(clock["value"]))
    return rows


def _predictions(path: Path) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        output_pts = int(row["output_pts"])
        if (
            row.get("schema") != "clasher.youtube.clock_anchor.v1"
            or row.get("current_frame_only") is not True
            or output_pts % 5
            or not 0 <= int(row["seconds_remaining"]) <= 599
            or not 0.0 < float(row["confidence"]) <= 1.0
        ):
            raise ValueError(f"invalid clock anchor: {row}")
        if output_pts in result:
            raise ValueError(f"duplicate output_pts: {output_pts}")
        result[output_pts] = row
    if not result:
        raise ValueError("no portable clock predictions")
    return result


def _is_holdout(timestamp_ms: int) -> bool:
    return any(start <= timestamp_ms < end for start, end in HOLDOUT_BLOCKS_MS)


def _partition(
    teachers: dict[int, tuple[int, int]],
    predictions: dict[int, dict[str, Any]],
    *,
    holdout: bool | None,
) -> dict[str, Any]:
    eligible = {
        output_pts: value
        for output_pts, value in teachers.items()
        if holdout is None or _is_holdout(value[0]) is holdout
    }
    accepted = sorted(set(eligible) & set(predictions))
    errors = [
        {
            "output_pts": output_pts,
            "timestamp_ms": eligible[output_pts][0],
            "teacher": eligible[output_pts][1],
            "prediction": int(predictions[output_pts]["seconds_remaining"]),
            "confidence": float(predictions[output_pts]["confidence"]),
        }
        for output_pts in accepted
        if int(predictions[output_pts]["seconds_remaining"]) != eligible[output_pts][1]
    ]
    correct = len(accepted) - len(errors)
    return {
        "teacher_anchors": len(eligible),
        "accepted": len(accepted),
        "coverage": len(accepted) / len(eligible),
        "correct": correct,
        "conditional_exact_accuracy": correct / len(accepted) if accepted else 0.0,
        "unconditional_exact_accuracy": correct / len(eligible),
        "errors": errors,
    }


def _monotonic_violations(predictions: dict[int, dict[str, Any]]) -> list[dict[str, int]]:
    violations: list[dict[str, int]] = []
    ordered = sorted(predictions.items())
    for (prior_pts, prior_row), (current_pts, current_row) in pairwise(ordered):
        prior = int(prior_row["seconds_remaining"])
        current = int(current_row["seconds_remaining"])
        elapsed = (current_pts - prior_pts) / 10
        legal_overtime_reset = prior <= 1 and 115 <= current <= 120
        if (current > prior and not legal_overtime_reset) or current < max(
            0, prior - int(elapsed) - 2
        ):
            violations.append(
                {
                    "prior_output_pts": prior_pts,
                    "prior_seconds": prior,
                    "current_output_pts": current_pts,
                    "current_seconds": current,
                }
            )
    return violations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-neutral", type=Path, required=True)
    parser.add_argument("--anchors", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--source-video", type=Path, required=True)
    parser.add_argument("--provider-wall-seconds", type=float, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    teachers = _teacher(args.teacher_neutral)
    predictions = _predictions(args.anchors)
    all_metrics = _partition(teachers, predictions, holdout=None)
    calibration = _partition(teachers, predictions, holdout=False)
    holdout = _partition(teachers, predictions, holdout=True)
    monotonic = _monotonic_violations(predictions)
    gates = {
        "all_coverage_at_least_0_80": all_metrics["coverage"] >= 0.80,
        "calibration_conditional_accuracy_1_0": (
            calibration["conditional_exact_accuracy"] == 1.0
        ),
        "holdout_coverage_at_least_0_80": holdout["coverage"] >= 0.80,
        "holdout_conditional_accuracy_1_0": (
            holdout["conditional_exact_accuracy"] == 1.0
        ),
        "monotonic_violations_zero": not monotonic,
        "full_video_wall_under_30_seconds": args.provider_wall_seconds < 30.0,
    }
    report = {
        "schema": "clasher.youtube.portable_clock_verification.v1",
        "provider": {
            "path": str(args.provider.resolve()),
            "sha256": _sha256(args.provider),
        },
        "source_video": {
            "path": str(args.source_video.resolve()),
            "sha256": _sha256(args.source_video),
        },
        "teacher_neutral": {
            "path": str(args.teacher_neutral.resolve()),
            "sha256": _sha256(args.teacher_neutral),
        },
        "anchors": {
            "path": str(args.anchors.resolve()),
            "sha256": _sha256(args.anchors),
            "published": len(predictions),
        },
        "split": {
            "method": "fixed contiguous temporal holdout blocks; templates use no holdout anchors",
            "holdout_blocks_ms": HOLDOUT_BLOCKS_MS,
        },
        "all": all_metrics,
        "calibration": calibration,
        "holdout": holdout,
        "monotonic_violations": monotonic,
        "performance": {
            "full_video_wall_seconds": args.provider_wall_seconds,
            "source_duration_seconds": 320.353,
            "source_realtime_factor": 320.353 / args.provider_wall_seconds,
            "wall_ms_per_published_anchor_including_decode": (
                1000 * args.provider_wall_seconds / len(predictions)
            ),
            "isolated_recognizer_latency_ms_per_anchor_from_build": 0.164,
        },
        "gates": gates,
        "failed_gates": [name for name, passed in gates.items() if not passed],
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["failed_gates"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
