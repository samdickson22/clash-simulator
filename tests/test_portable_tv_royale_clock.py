from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


def _module():
    path = Path("tools/recognize_public_clock.py")
    spec = importlib.util.spec_from_file_location("recognize_public_clock", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_embedded_templates_are_complete_and_immutable() -> None:
    module = _module()
    assert set(module.TEMPLATES) == set(range(10))
    assert all(template.shape == (40, 32) for template in module.TEMPLATES.values())
    assert all(template.dtype == np.uint8 for template in module.TEMPLATES.values())
    assert module.CONFIDENCE_THRESHOLD == 0.5560975423673304


def test_current_frame_composes_unseen_timestamp_from_digit_templates() -> None:
    module = _module()
    height, width = 2560, 1182
    x, y, box_width, box_height = module.CLOCK_REGION
    x1, y1 = round(x * width), round(y * height)
    x2, y2 = round((x + box_width) * width), round((y + box_height) * height)
    crop = np.zeros((y2 - y1, x2 - x1, 3), dtype=np.uint8)
    for left, digit in zip((55, 105, 150), (2, 5, 8), strict=True):
        template = module.TEMPLATES[digit]
        patch = crop[65:105, left : left + 32]
        patch[template > 0] = (255, 255, 255)
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[y1:y2, x1:x2] = crop
    assert module.recognize_current_frame(frame) == (178, 1.0)


def test_current_frame_fails_closed_without_three_confident_digits() -> None:
    module = _module()
    frame = np.zeros((2560, 1182, 3), dtype=np.uint8)
    assert module.recognize_current_frame(frame) is None


def test_clock_crop_normalizes_supported_native_layouts_without_state() -> None:
    module = _module()
    for width, height in module.SUPPORTED_SOURCE_SIZES:
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        crop = module._clock_crop(frame)
        assert (crop.shape[1], crop.shape[0]) == module.CANONICAL_CLOCK_SIZE
