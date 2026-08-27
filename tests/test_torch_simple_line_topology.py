from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.torch_sim.simple_line_topology import select_line_capsule_hits


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _inputs(device_name: str) -> dict[str, torch.Tensor]:
    device = _device(device_name)
    return {
        "source_x_units": torch.tensor([[0, 100]], dtype=torch.int32, device=device),
        "source_y_units": torch.tensor([[0, 100]], dtype=torch.int32, device=device),
        "primary_x_units": torch.tensor(
            [[100, 100]], dtype=torch.int32, device=device
        ),
        "primary_y_units": torch.tensor(
            [[0, 200]], dtype=torch.int32, device=device
        ),
        "range_units": torch.tensor(
            [[1_000, 500]], dtype=torch.int32, device=device
        ),
        "half_width_units": torch.tensor(
            [[100, 50]], dtype=torch.int32, device=device
        ),
        "candidate_x_units": torch.tensor(
            [[500, 500, 500, -1, 1_050, 1_101, 100]],
            dtype=torch.int32,
            device=device,
        ),
        "candidate_y_units": torch.tensor(
            [[0, 100, 101, 0, 0, 0, 350]],
            dtype=torch.int32,
            device=device,
        ),
        "eligible": torch.ones((1, 2, 7), dtype=torch.bool, device=device),
    }


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_forward_capsule_covers_collinear_boundary_and_far_cap(
    device_name: str,
) -> None:
    inputs = _inputs(device_name)
    inputs["eligible"][0, 0, 0] = False

    result = select_line_capsule_hits(**inputs)

    # The otherwise-collinear first entity is suppressed by the caller's
    # already-resolved eligibility mask.  The boundary and far round cap hit;
    # off-axis, behind-source, and beyond-cap candidates miss.
    assert result.hit[0, 0].tolist() == [
        False,
        True,
        False,
        False,
        True,
        False,
        False,
    ]
    assert int(result.hit_count[0, 0]) == 2
    assert bool(result.valid_direction[0, 0])
    assert result.axial_distance[0, 0].tolist() == pytest.approx(
        [500.0, 500.0, 500.0, -1.0, 1_050.0, 1_101.0, 100.0]
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_direction_rotates_with_primary_and_retains_fixed_shape(
    device_name: str,
) -> None:
    inputs = _inputs(device_name)

    result = select_line_capsule_hits(**inputs)

    assert result.hit.shape == (1, 2, 7)
    assert result.hit_count.shape == (1, 2)
    assert result.hit[0, 1].tolist() == [
        False,
        False,
        False,
        False,
        False,
        False,
        True,
    ]
    assert int(result.hit_count[0, 1]) == 1


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_zero_length_primary_direction_fails_closed(device_name: str) -> None:
    inputs = _inputs(device_name)
    inputs["primary_x_units"].copy_(inputs["source_x_units"])
    inputs["primary_y_units"].copy_(inputs["source_y_units"])

    result = select_line_capsule_hits(**inputs)

    assert not result.valid_direction.any()
    assert not result.hit.any()
    assert torch.equal(result.hit_count, torch.zeros_like(result.hit_count))


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_line_topology_is_stable_under_deterministic_replay(device_name: str) -> None:
    inputs = _inputs(device_name)

    first = select_line_capsule_hits(**inputs)
    replay = select_line_capsule_hits(
        **{name: value.clone() for name, value in inputs.items()}
    )

    for descriptor in fields(first):
        assert torch.equal(
            getattr(first, descriptor.name), getattr(replay, descriptor.name)
        )


def test_line_topology_hot_path_has_no_sync_compaction_or_card_dispatch() -> None:
    source = inspect.getsource(select_line_capsule_hits)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
    for card_name in ("MagicArcher", "Bowler", "Executioner", "Princess"):
        assert card_name not in source


def test_line_topology_rejects_shape_and_dtype_mismatches() -> None:
    inputs = _inputs("cpu")
    inputs["eligible"] = torch.ones((1, 7), dtype=torch.bool)
    with pytest.raises(ValueError, match="eligible"):
        select_line_capsule_hits(**inputs)

    inputs = _inputs("cpu")
    inputs["eligible"] = inputs["eligible"].to(torch.int64)
    with pytest.raises(ValueError, match="eligible must be bool"):
        select_line_capsule_hits(**inputs)
