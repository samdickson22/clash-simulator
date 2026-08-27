from __future__ import annotations

import inspect
from dataclasses import fields, replace

import pytest
import torch

from clasher.torch_sim.simple_impulse import (
    FastRadialImpulseInputs,
    clone_fast_radial_impulse_inputs,
    compute_fast_radial_impulse,
)


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _inputs(
    device_name: str,
    *,
    centers: list[tuple[int, int]],
    targets: list[tuple[int, int]],
    stable_ids: list[int],
    magnitude_units: list[int],
    distance_percentage: list[int] | None = None,
    eligible: list[list[bool]] | None = None,
    max_displacement_units: list[int] | None = None,
) -> FastRadialImpulseInputs:
    device = _device(device_name)
    if distance_percentage is None:
        distance_percentage = [0] * len(centers)
    if eligible is None:
        eligible = [[True] * len(targets) for _ in centers]
    cap = None
    if max_displacement_units is not None:
        cap = torch.tensor(
            [max_displacement_units], dtype=torch.int32, device=device
        )
    return FastRadialImpulseInputs(
        center_x_units=torch.tensor(
            [[center[0] for center in centers]], dtype=torch.int32, device=device
        ),
        center_y_units=torch.tensor(
            [[center[1] for center in centers]], dtype=torch.int32, device=device
        ),
        target_x_units=torch.tensor(
            [[target[0] for target in targets]], dtype=torch.int32, device=device
        ),
        target_y_units=torch.tensor(
            [[target[1] for target in targets]], dtype=torch.int32, device=device
        ),
        target_stable_id=torch.tensor(
            [stable_ids], dtype=torch.int64, device=device
        ),
        eligible=torch.tensor([eligible], dtype=torch.bool, device=device),
        magnitude_units=torch.tensor(
            [magnitude_units], dtype=torch.int32, device=device
        ),
        distance_percentage=torch.tensor(
            [distance_percentage], dtype=torch.int32, device=device
        ),
        max_displacement_units=cap,
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_tornado_like_absolute_and_percentage_pulls(device_name: str) -> None:
    inputs = _inputs(
        device_name,
        centers=[(0, 0), (0, 0)],
        targets=[(1_000, 0), (0, 2_000)],
        stable_ids=[11, 12],
        magnitude_units=[-250, 0],
        distance_percentage=[0, -25],
        eligible=[[True, False], [False, True]],
    )

    result = compute_fast_radial_impulse(inputs)

    assert result.dx_units.dtype == torch.int32
    assert result.dy_units.dtype == torch.int32
    assert result.dx_units[0].tolist() == [-250, 0]
    assert result.dy_units[0].tolist() == [0, -500]
    assert result.affected[0].tolist() == [True, True]

    percentage_only = replace(inputs, magnitude_units=None)
    absolute_only = replace(inputs, distance_percentage=None)
    assert compute_fast_radial_impulse(percentage_only).dy_units[0].tolist() == [
        0,
        -500,
    ]
    assert compute_fast_radial_impulse(absolute_only).dx_units[0].tolist() == [
        -250,
        0,
    ]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_knockback_push_uses_integer_radial_normalization(device_name: str) -> None:
    inputs = _inputs(
        device_name,
        centers=[(0, 0)],
        targets=[(3_000, 4_000), (-3_000, 4_000)],
        stable_ids=[1, 2],
        magnitude_units=[1_000],
    )

    result = compute_fast_radial_impulse(inputs)

    assert result.dx_units[0].tolist() == [600, -600]
    assert result.dy_units[0].tolist() == [800, 800]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_exact_center_fallback_depends_on_stable_identity_not_slot(
    device_name: str,
) -> None:
    inputs = _inputs(
        device_name,
        centers=[(5_000, 5_000)],
        targets=[(5_000, 5_000)] * 4,
        stable_ids=[1, 2, 3, 4],
        magnitude_units=[200],
    )

    result = compute_fast_radial_impulse(inputs)

    assert result.dx_units[0].tolist() == [-200, 0, 0, 200]
    assert result.dy_units[0].tolist() == [0, 200, -200, 0]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_simultaneous_effects_sum_then_use_per_target_cap(device_name: str) -> None:
    inputs = _inputs(
        device_name,
        centers=[(0, 0), (0, 0), (1_000, -1_000)],
        targets=[(3_000, 4_000), (2_000, -1_000)],
        stable_ids=[7, 8],
        magnitude_units=[500, 500, 400],
        eligible=[[True, False], [True, False], [False, True]],
        max_displacement_units=[600, -1],
    )

    result = compute_fast_radial_impulse(inputs)

    # Target zero first receives (600, 800), then the summed vector is capped
    # to 600. Target one has its cap disabled and retains the full push.
    assert result.dx_units[0].tolist() == [360, 400]
    assert result.dy_units[0].tolist() == [480, 0]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_invalid_id_and_ineligible_lanes_fail_closed(device_name: str) -> None:
    inputs = _inputs(
        device_name,
        centers=[(0, 0)],
        targets=[(1_000, 0), (2_000, 0), (3_000, 0)],
        stable_ids=[0, 2, 3],
        magnitude_units=[500],
        eligible=[[True, False, True]],
        max_displacement_units=[-1, -1, 0],
    )

    result = compute_fast_radial_impulse(inputs)

    assert result.dx_units[0].tolist() == [0, 0, 0]
    assert result.dy_units[0].tolist() == [0, 0, 0]
    assert not result.affected.any()


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_impulse_replay_is_exact_and_inputs_are_not_mutated(device_name: str) -> None:
    inputs = _inputs(
        device_name,
        centers=[(500, 700), (9_000, 11_000)],
        targets=[(3_000, 4_000), (8_000, 12_000), (500, 700)],
        stable_ids=[101, 103, 107],
        magnitude_units=[-350, 225],
        distance_percentage=[-10, 5],
        eligible=[[True, False, True], [True, True, False]],
        max_displacement_units=[700, 500, 300],
    )
    replay = clone_fast_radial_impulse_inputs(inputs)
    preserved = clone_fast_radial_impulse_inputs(inputs)

    first = compute_fast_radial_impulse(inputs)
    second = compute_fast_radial_impulse(replay)

    assert torch.equal(first.dx_units, second.dx_units)
    assert torch.equal(first.dy_units, second.dy_units)
    assert torch.equal(first.affected, second.affected)
    for descriptor in fields(inputs):
        actual = getattr(inputs, descriptor.name)
        expected = getattr(preserved, descriptor.name)
        if actual is None:
            assert expected is None
        else:
            assert torch.equal(actual, expected)


def test_impulse_hot_path_has_no_host_sync_compaction_or_card_dispatch() -> None:
    source = inspect.getsource(compute_fast_radial_impulse)
    for forbidden in (
        ".item(",
        ".tolist(",
        ".cpu(",
        ".nonzero(",
        "argsort(",
        "topk(",
    ):
        assert forbidden not in source
    for card_name in ("Tornado", "TheLog", "Fireball"):
        assert card_name not in source
