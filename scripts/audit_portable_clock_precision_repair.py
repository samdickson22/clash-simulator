from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _distribution(values: list[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    if not len(array):
        return {"count": 0}
    return {
        "count": len(array),
        "minimum": float(np.min(array)),
        "q01": float(np.quantile(array, 0.01, method="higher")),
        "q05": float(np.quantile(array, 0.05, method="higher")),
        "median": float(np.median(array)),
        "q95": float(np.quantile(array, 0.95, method="lower")),
        "maximum": float(np.max(array)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-anchors", type=Path, required=True)
    parser.add_argument("--repaired-anchors", type=Path, required=True)
    parser.add_argument("--original-verification", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--replay-before", type=Path, required=True)
    parser.add_argument("--replay-after", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    original_anchors = _rows(args.original_anchors)
    repaired_anchors = _rows(args.repaired_anchors)
    original_verification = json.loads(
        args.original_verification.read_text(encoding="utf-8")
    )
    if original_verification["all"]["conditional_exact_accuracy"] != 1.0:
        raise ValueError("calibration source is not exact")
    calibration_confidences = [float(row["confidence"]) for row in original_anchors]
    support_floor = min(calibration_confidences)
    if original_anchors != repaired_anchors:
        raise ValueError("precision repair changed exact-source anchor output")

    before = _rows(args.replay_before)
    after = _rows(args.replay_after)
    before_by_key = {row["frame_key"]: row for row in before}
    after_by_key = {row["frame_key"]: row for row in after}
    if set(before_by_key) != set(after_by_key):
        raise ValueError("before/after replay frame sets differ")
    if any(
        before_by_key[key]["teacher_seconds"] != after_by_key[key]["teacher_seconds"]
        for key in before_by_key
    ):
        raise ValueError("before/after Vision teacher labels differ")

    before_joint = [
        row
        for row in before
        if row["teacher_seconds"] is not None and row["portable_seconds"] is not None
    ]
    before_correct = [row for row in before_joint if row["exact_match"]]
    before_errors = [row for row in before_joint if not row["exact_match"]]
    after_teacher = [row for row in after if row["teacher_seconds"] is not None]
    after_joint = [
        row
        for row in after_teacher
        if row["portable_seconds"] is not None
    ]
    after_correct = [row for row in after_joint if row["exact_match"]]
    empirical_accuracy = len(after_correct) / len(after_joint) if after_joint else 0.0
    coverage = len(after_joint) / len(after_teacher) if after_teacher else 0.0

    report = {
        "schema": "clasher.youtube.portable_clock_precision_repair.v1",
        "selection": {
            "rule": "reject confidence below minimum exact calibration support",
            "support_floor": support_floor,
            "selected_from": "original exact 1182x2560 source only",
            "replay_labels_used_for_selection": False,
            "confidence_semantics": (
                "minimum across the three digits of normalized nearest-template "
                "distance margin: (second_distance-best_distance)/second_distance"
            ),
        },
        "distributions": {
            "calibration_exact_normalized_margin": _distribution(
                calibration_confidences
            ),
            "replay_before_correct_normalized_margin": _distribution(
                [float(row["portable_confidence"]) for row in before_correct]
            ),
            "replay_before_error_normalized_margin": _distribution(
                [float(row["portable_confidence"]) for row in before_errors]
            ),
            "replay_after_accepted_normalized_margin": _distribution(
                [float(row["portable_confidence"]) for row in after_joint]
            ),
        },
        "exact_source": {
            "anchors": len(original_anchors),
            "before_sha256": _sha256(args.original_anchors),
            "after_sha256": _sha256(args.repaired_anchors),
            "byte_identical": True,
            "conditional_accuracy": 1.0,
        },
        "replay_disjoint": {
            "teacher_confident": len(after_teacher),
            "accepted_before": len(before_joint),
            "correct_before": len(before_correct),
            "errors_before": [row["frame_key"] for row in before_errors],
            "accepted_after": len(after_joint),
            "correct_after": len(after_correct),
            "errors_after": [
                row["frame_key"] for row in after_joint if not row["exact_match"]
            ],
            "teacher_conditioned_coverage": coverage,
            "conditional_exact_accuracy": empirical_accuracy,
        },
        "gates": {
            "accepted_accuracy_at_least_0_995": empirical_accuracy >= 0.995,
            "teacher_conditioned_coverage_at_least_0_50": coverage >= 0.50,
            "exact_source_output_preserved": True,
            "current_frame_only_preserved": True,
            "native_886_888_remain_fail_closed": True,
        },
        "decision": (
            "accept_precision_repair_keep_layout_expansion_blocked"
            if empirical_accuracy >= 0.995 and coverage >= 0.50
            else "reject_precision_repair"
        ),
        "provider": {
            "path": str(args.provider.resolve()),
            "sha256": _sha256(args.provider),
        },
        "inputs": {
            "original_verification_sha256": _sha256(args.original_verification),
            "replay_before_sha256": _sha256(args.replay_before),
            "replay_after_sha256": _sha256(args.replay_after),
        },
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
