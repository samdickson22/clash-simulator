from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from scripts.import_tv_royale_placements import (
    _combined_detections,
    _combined_detections_reference,
)


def _result(rows: list[list[float]]) -> SimpleNamespace:
    return SimpleNamespace(orig_boxes=torch.tensor(rows, dtype=torch.float32))


def test_tensorized_detection_merge_matches_original_cpu_path_exactly() -> None:
    results = [
        _result(
            [
                [0.0, 0.0, 20.0, 20.0, 0.90, 0.0, 0.0],
                [40.0, 40.0, 50.0, 50.0, 0.75, 1.0, 1.0],
            ]
        ),
        _result(
            [
                [1.0, 1.0, 19.0, 19.0, 0.80, 1.0, 1.0],
                [70.0, 70.0, 80.0, 80.0, 0.65, 0.0, 0.0],
            ]
        ),
    ]
    models = [
        SimpleNamespace(names={0: "knight", 1: "archer"}),
        SimpleNamespace(names={0: "bar", 1: "knight"}),
    ]

    expected = _combined_detections_reference(
        [result.orig_boxes for result in results], models, nms_iou=0.6
    )
    actual = _combined_detections(
        results, models, nms_iou=0.6, nms_backend="native"
    )

    assert actual == expected
    assert [row.class_name for row in actual] == ["knight", "archer", "bar"]
    assert [row.belonging for row in actual] == [0, 1, 0]


def test_detection_merge_shadow_and_empty_paths_fail_closed() -> None:
    model = SimpleNamespace(names={0: "knight"})
    result = _result([[0.0, 0.0, 10.0, 10.0, 0.5, 0.0, 1.0]])

    assert _combined_detections(
        [result], [model], nms_iou=0.6, nms_backend="shadow"
    ) == _combined_detections(
        [result], [model], nms_iou=0.6, nms_backend="cpu"
    )
    assert _combined_detections(
        [SimpleNamespace(orig_boxes=torch.empty((0, 7), dtype=torch.float32))],
        [model],
        nms_iou=0.6,
    ) == []

    with pytest.raises(ValueError, match="unsupported detection NMS backend"):
        _combined_detections(
            [result], [model], nms_iou=0.6, nms_backend="surprise"
        )
