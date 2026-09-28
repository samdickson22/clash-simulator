from __future__ import annotations

import numpy as np
import pytest

from clasher.rl.perspective_sanitizer import (
    DualHudPerspectiveSpec,
    NormalizedRegion,
    PerspectiveContractError,
    PolicySurfaceCache,
    build_policy_pixel_input,
    sanitize_dual_hud_frame,
)


def _spec() -> DualHudPerspectiveSpec:
    return DualHudPerspectiveSpec(
        arena=NormalizedRegion(0.024, 0.196, 0.954, 0.659),
        clock=NormalizedRegion(0.790, 0.105, 0.200, 0.065),
        own_hud=NormalizedRegion(0.000, 0.855, 1.000, 0.140),
        opponent_private=NormalizedRegion(0.000, 0.000, 1.000, 0.160),
    )


def _frame() -> np.ndarray:
    rows = np.arange(1280, dtype=np.uint16)[:, None, None]
    columns = np.arange(592, dtype=np.uint16)[None, :, None]
    channels = np.arange(3, dtype=np.uint16)[None, None, :]
    return ((rows * 3 + columns * 5 + channels * 71) % 256).astype(np.uint8)


def _mutate_top_private_except_clock(frame: np.ndarray) -> np.ndarray:
    result = frame.copy()
    spec = _spec()
    height, width = result.shape[:2]
    tx1, ty1, tx2, ty2 = spec.opponent_private.pixels(width, height)
    cx1, cy1, cx2, cy2 = spec.clock.pixels(width, height)
    clock = result[cy1:cy2, cx1:cx2].copy()
    result[ty1:ty2, tx1:tx2] ^= np.uint8(0xFF)
    result[cy1:cy2, cx1:cx2] = clock
    return result


def test_top_private_pixels_cannot_change_surfaces_or_policy_input() -> None:
    original = _frame()
    changed = _mutate_top_private_except_clock(original)

    first = sanitize_dual_hud_frame(original, _spec())
    second = sanitize_dual_hud_frame(changed, _spec())
    first_input = build_policy_pixel_input(first)
    second_input = build_policy_pixel_input(second)

    assert first.pixel_sha256 == second.pixel_sha256
    assert np.array_equal(first.arena, second.arena)
    assert np.array_equal(first.clock, second.clock)
    assert np.array_equal(first.own_hud, second.own_hud)
    assert first_input.source_pixel_sha256 == second_input.source_pixel_sha256
    assert np.array_equal(first_input.arena, second_input.arena)
    assert np.array_equal(first_input.clock, second_input.clock)
    assert np.array_equal(first_input.own_hud, second_input.own_hud)


def test_bottom_own_hud_changes_remain_observable() -> None:
    original = _frame()
    changed = original.copy()
    x1, y1, x2, y2 = _spec().own_hud.pixels(changed.shape[1], changed.shape[0])
    changed[y1:y2, x1:x2] ^= np.uint8(0x7F)

    first = sanitize_dual_hud_frame(original, _spec())
    second = sanitize_dual_hud_frame(changed, _spec())
    first_input = build_policy_pixel_input(first)
    second_input = build_policy_pixel_input(second)

    assert np.array_equal(first.arena, second.arena)
    assert np.array_equal(first.clock, second.clock)
    assert not np.array_equal(first.own_hud, second.own_hud)
    assert not np.array_equal(first_input.own_hud, second_input.own_hud)
    assert first.pixel_sha256 != second.pixel_sha256


def test_public_clock_changes_remain_observable_inside_top_band() -> None:
    original = _frame()
    changed = original.copy()
    x1, y1, x2, y2 = _spec().clock.pixels(changed.shape[1], changed.shape[0])
    changed[y1:y2, x1:x2] ^= np.uint8(0x31)

    first = sanitize_dual_hud_frame(original, _spec())
    second = sanitize_dual_hud_frame(changed, _spec())

    assert not np.array_equal(first.clock, second.clock)
    assert first.pixel_sha256 != second.pixel_sha256


def test_surfaces_are_detached_read_only_copies_without_raw_frame() -> None:
    frame = _frame()
    surfaces = sanitize_dual_hud_frame(frame, _spec())

    assert not np.shares_memory(frame, surfaces.arena)
    assert not np.shares_memory(frame, surfaces.clock)
    assert not np.shares_memory(frame, surfaces.own_hud)
    assert surfaces.arena.flags.writeable is False
    assert surfaces.clock.flags.writeable is False
    assert surfaces.own_hud.flags.writeable is False
    assert not hasattr(surfaces, "raw_frame")
    assert not hasattr(surfaces, "opponent_hud")
    with pytest.raises(ValueError, match="read-only"):
        surfaces.own_hud[0, 0, 0] = 0


def test_raw_frames_fail_before_policy_input_or_cache() -> None:
    raw = _frame()
    cache = PolicySurfaceCache()

    with pytest.raises(PerspectiveContractError, match="never a raw frame"):
        build_policy_pixel_input(raw)  # type: ignore[arg-type]
    with pytest.raises(PerspectiveContractError, match="never a raw frame"):
        cache.store(raw)  # type: ignore[arg-type]

    sanitized = sanitize_dual_hud_frame(raw, _spec())
    key = cache.store(sanitized)
    assert key == sanitized.pixel_sha256
    assert cache.get(key).source_pixel_sha256 == key


def test_spec_rejects_private_overlap_with_arena_or_own_hud() -> None:
    with pytest.raises(PerspectiveContractError, match="overlaps arena"):
        DualHudPerspectiveSpec(
            arena=NormalizedRegion(0.0, 0.15, 1.0, 0.7),
            clock=NormalizedRegion(0.8, 0.1, 0.15, 0.05),
            own_hud=NormalizedRegion(0.0, 0.9, 1.0, 0.1),
            opponent_private=NormalizedRegion(0.0, 0.0, 1.0, 0.2),
        ).validate()

