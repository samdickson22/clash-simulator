from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.torch_sim.simple_chain_topology import (
    FAST_MAX_CHAIN_TARGETS,
    FastChainTopologyInputs,
    clone_fast_chain_inputs,
    fast_chain_hit_count,
)


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _one_chain(
    device_name: str,
    *,
    positions: list[tuple[int, int]],
    stable_ids: list[int],
    primary_id: int,
    hop_radius_units: int,
    target_count: int,
    eligible: list[bool] | None = None,
) -> FastChainTopologyInputs:
    device = _device(device_name)
    if eligible is None:
        eligible = [True] * len(positions)
    primary_slot = stable_ids.index(primary_id)
    return FastChainTopologyInputs(
        source_x_units=torch.tensor([[0]], dtype=torch.int32, device=device),
        source_y_units=torch.tensor([[0]], dtype=torch.int32, device=device),
        primary_target_id=torch.tensor(
            [[primary_id]], dtype=torch.int64, device=device
        ),
        primary_x_units=torch.tensor(
            [[positions[primary_slot][0]]], dtype=torch.int32, device=device
        ),
        primary_y_units=torch.tensor(
            [[positions[primary_slot][1]]], dtype=torch.int32, device=device
        ),
        entity_stable_id=torch.tensor([stable_ids], dtype=torch.int64, device=device),
        entity_x_units=torch.tensor(
            [[position[0] for position in positions]],
            dtype=torch.int32,
            device=device,
        ),
        entity_y_units=torch.tensor(
            [[position[1] for position in positions]],
            dtype=torch.int32,
            device=device,
        ),
        eligible=torch.tensor([[eligible]], dtype=torch.bool, device=device),
        hop_radius_units=torch.tensor(
            [[hop_radius_units]], dtype=torch.int32, device=device
        ),
        target_count=torch.tensor([[target_count]], dtype=torch.int16, device=device),
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_three_target_chain_uses_each_new_hop_as_its_origin(device_name: str) -> None:
    inputs = _one_chain(
        device_name,
        positions=[(1_000, 0), (4_500, 0), (8_000, 0), (11_500, 0)],
        stable_ids=[10, 20, 30, 40],
        primary_id=10,
        hop_radius_units=4_000,
        target_count=3,
    )

    hit_count = fast_chain_hit_count(inputs)

    assert hit_count.dtype == torch.int16
    assert hit_count.shape == (1, 1, 4)
    assert hit_count[0, 0].tolist() == [1, 1, 1, 0]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_nine_target_chain_is_fixed_shape_and_caps_before_tenth(
    device_name: str,
) -> None:
    positions = [(1_000 + 3_500 * index, 0) for index in range(10)]
    inputs = _one_chain(
        device_name,
        positions=positions,
        stable_ids=list(range(100, 110)),
        primary_id=100,
        hop_radius_units=4_000,
        target_count=FAST_MAX_CHAIN_TARGETS,
    )

    hit_count = fast_chain_hit_count(inputs)

    assert hit_count[0, 0, :9].tolist() == [1] * 9
    assert int(hit_count[0, 0, 9]) == 0
    assert int(hit_count.sum()) == FAST_MAX_CHAIN_TARGETS


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_chain_excludes_visited_ineligible_and_out_of_range_targets(
    device_name: str,
) -> None:
    # Equal-distance stable IDs 30 and 20 flank the primary. ID 20 wins, then
    # the next hop continues right instead of revisiting the closer primary.
    tie = _one_chain(
        device_name,
        positions=[(0, 0), (-3_000, 0), (3_000, 0), (6_500, 0)],
        stable_ids=[10, 30, 20, 40],
        primary_id=10,
        hop_radius_units=4_000,
        target_count=3,
    )
    assert fast_chain_hit_count(tie)[0, 0].tolist() == [1, 0, 1, 1]

    cutoff = _one_chain(
        device_name,
        positions=[(0, 0), (4_001, 0), (1_000, 0)],
        stable_ids=[10, 20, 30],
        primary_id=10,
        hop_radius_units=4_000,
        target_count=3,
        eligible=[True, True, False],
    )
    assert fast_chain_hit_count(cutoff)[0, 0].tolist() == [1, 0, 0]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_chain_replay_is_exact_and_inputs_are_not_mutated(device_name: str) -> None:
    inputs = _one_chain(
        device_name,
        positions=[(500, 500), (3_500, 1_000), (6_500, 1_500), (9_500, 2_000)],
        stable_ids=[7, 11, 13, 17],
        primary_id=7,
        hop_radius_units=3_500,
        target_count=4,
    )
    replay = clone_fast_chain_inputs(inputs)
    preserved = clone_fast_chain_inputs(inputs)

    first = fast_chain_hit_count(inputs)
    second = fast_chain_hit_count(replay)

    assert torch.equal(first, second)
    for descriptor in fields(inputs):
        assert torch.equal(
            getattr(inputs, descriptor.name),
            getattr(preserved, descriptor.name),
        )


def test_chain_hot_path_has_no_host_sync_dynamic_compaction_or_card_dispatch() -> None:
    source = inspect.getsource(fast_chain_hit_count)
    for forbidden in (
        ".item(",
        ".tolist(",
        ".cpu(",
        ".nonzero(",
        "argsort(",
        "topk(",
    ):
        assert forbidden not in source
    for card_name in ("ElectroDragon", "ElectroSpirit"):
        assert card_name not in source
