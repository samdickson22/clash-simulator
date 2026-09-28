from __future__ import annotations

import numpy as np

from scripts.audit_portable_tv_royale_clock_canary import (
    _clock_crop,
    _metrics,
    _parse_teacher,
)


def test_teacher_requires_confident_exact_clock_pattern() -> None:
    assert _parse_teacher(
        {
            "candidates": [
                {"text": "Time left:", "confidence": 1.0},
                {"text": "2:09", "confidence": 0.99},
            ]
        }
    ) == (129, 0.99, ["Time left:", "2:09"])
    assert _parse_teacher(
        {"candidates": [{"text": "2:09", "confidence": 0.79}]}
    ) == (None, 0.0, ["2:09"])


def test_retained_frame_clock_crop_has_explicit_canonical_geometry() -> None:
    frame = np.zeros((640, 296, 3), dtype=np.uint8)
    assert _clock_crop(frame).shape == (192, 230, 3)


def test_metrics_do_not_count_teacher_missing_rows_as_errors() -> None:
    rows = [
        {
            "frame_key": "a",
            "teacher_seconds": 10,
            "portable_seconds": 10,
            "exact_match": True,
        },
        {
            "frame_key": "b",
            "teacher_seconds": 9,
            "portable_seconds": None,
            "exact_match": False,
        },
        {
            "frame_key": "c",
            "teacher_seconds": None,
            "portable_seconds": None,
            "exact_match": False,
        },
    ]
    metrics = _metrics(rows)
    assert metrics["teacher_confident"] == 2
    assert metrics["joint_accepted"] == 1
    assert metrics["correct"] == 1
    assert metrics["conditional_exact_accuracy"] == 1.0
    assert metrics["teacher_conditioned_portable_coverage"] == 0.5
