from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.torch_sim.simple_death_burst import (
    FastDeathBurstCatalog,
    FastDeathBurstState,
    step_fast_death_bursts_,
)
from clasher.torch_sim.simple_state import FastGymState


def _catalog(device: torch.device) -> FastDeathBurstCatalog:
    catalog = FastDeathBurstCatalog.empty(6, device=device)
    # Current-level values for a large parent and its two smaller children.
    catalog.enabled[2:4] = True
    catalog.damage[2:4] = torch.tensor([225.0, 99.0], device=device)
    catalog.radius_units[2:4] = 2_000
    catalog.hits_air[2:4] = True
    catalog.hits_ground[2:4] = True
    catalog.tower_damage_multiplier[2:4] = torch.tensor([0.7, 0.6], device=device)
    catalog.building_damage_multiplier[2:4] = torch.tensor([0.9, 0.8], device=device)
    return catalog


def _dead_sources(device: torch.device) -> FastGymState:
    state = FastGymState.empty(1, max_entities=5, device=device)
    state.active[0, :3] = True
    state.stable_id[0, :3] = torch.tensor([40, 11, 25], device=device)
    state.owner[0, :3] = torch.tensor([0, 0, 1], device=device)
    state.card_id[0, :3] = torch.tensor([2, 3, 3], device=device)
    state.x_units[0, :3] = torch.tensor([9_000, 7_500, 10_500], device=device)
    state.y_units[0, :3] = torch.tensor([14_000, 14_000, 15_000], device=device)
    state.hp[0, :3] = 0
    state.max_hp[0, :3] = 1
    return state


def _assert_equal(left: object, right: object) -> None:
    for descriptor in fields(left):  # type: ignore[arg-type]
        left_value = getattr(left, descriptor.name)
        right_value = getattr(right, descriptor.name)
        if isinstance(left_value, torch.Tensor):
            torch.testing.assert_close(left_value, right_value)
        elif hasattr(left_value, "__dataclass_fields__"):
            _assert_equal(left_value, right_value)
        else:
            assert left_value == right_value


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_parent_and_child_burst_profiles_emit_in_stable_order(device_name: str) -> None:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    state = _dead_sources(device)
    tracker = FastDeathBurstState.empty_like(state)

    result = step_fast_death_bursts_(state, _catalog(device), tracker)
    command = result.commands

    assert command.ready.tolist() == [[True, True, True, False, False]]
    assert command.source_stable_id.tolist() == [[11, 25, 40, 0, 0]]
    assert command.source_slot.tolist() == [[1, 2, 0, -1, -1]]
    assert command.source_owner.tolist() == [[0, 1, 0, 0, 0]]
    assert command.source_card_id.tolist() == [[3, 3, 2, 0, 0]]
    assert command.source_x_units.tolist() == [[7_500, 10_500, 9_000, 0, 0]]
    assert command.source_y_units.tolist() == [[14_000, 15_000, 14_000, 0, 0]]
    assert command.damage.tolist() == [[99.0, 99.0, 225.0, 0.0, 0.0]]
    assert command.radius_units.tolist() == [[2_000, 2_000, 2_000, 0, 0]]
    assert command.hits_air.tolist() == [[True, True, True, False, False]]
    assert command.hits_ground.tolist() == [[True, True, True, False, False]]
    torch.testing.assert_close(
        command.tower_damage_multiplier,
        torch.tensor([[0.6, 0.6, 0.7, 0.0, 0.0]], device=device),
    )
    torch.testing.assert_close(
        command.building_damage_multiplier,
        torch.tensor([[0.8, 0.8, 0.9, 0.0, 0.0]], device=device),
    )
    assert result.processed_source_mask.tolist() == [[True, True, True, False, False]]
    assert result.emitted_source_mask.tolist() == [[True, True, True, False, False]]
    assert result.emitted_count.tolist() == [3]
    assert result.capacity_rejected_count.tolist() == [0]
    assert command.ready.device == device


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_capacity_is_source_aligned_and_never_replays_rejection(
    device_name: str,
) -> None:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    state = _dead_sources(device)
    tracker = FastDeathBurstState.empty_like(state)
    catalog = _catalog(device)

    first = step_fast_death_bursts_(state, catalog, tracker, max_commands=2)
    assert first.commands.source_stable_id.tolist() == [[11, 25]]
    assert first.emitted_source_mask.tolist() == [[False, True, True, False, False]]
    assert first.capacity_rejected.tolist() == [[True, False, False, False, False]]
    assert first.emitted_count.tolist() == [2]
    assert first.capacity_rejected_count.tolist() == [1]

    second = step_fast_death_bursts_(state, catalog, tracker, max_commands=3)
    assert not bool(second.commands.ready.any())
    assert not bool(second.processed_source_mask.any())
    assert not bool(second.capacity_rejected.any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_slot_reuse_and_independent_row_reset_rearm_identity(device_name: str) -> None:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    state = FastGymState.empty(2, max_entities=2, device=device)
    state.active[:, 0] = True
    state.stable_id[:, 0] = torch.tensor([7, 8], device=device)
    state.card_id[:, 0] = 2
    state.hp[:, 0] = 0
    tracker = FastDeathBurstState.empty_like(state)
    catalog = _catalog(device)

    initial = step_fast_death_bursts_(state, catalog, tracker)
    assert initial.commands.source_stable_id.tolist() == [[7, 0], [8, 0]]
    duplicate = step_fast_death_bursts_(state, catalog, tracker)
    assert not bool(duplicate.commands.ready.any())

    # Reusing a physical slot with a new identity needs no manual cleanup.
    state.stable_id[0, 0] = 50
    reused = step_fast_death_bursts_(state, catalog, tracker)
    assert reused.commands.source_stable_id.tolist() == [[50, 0], [0, 0]]

    # An independent environment reset may restart stable IDs; reset only its
    # tracker row and leave the other row's exactly-once history intact.
    state.stable_id[0, 0] = 7
    tracker.reset_rows_(torch.tensor([True, False], device=device))
    reset = step_fast_death_bursts_(state, catalog, tracker)
    assert reset.commands.source_stable_id.tolist() == [[7, 0], [0, 0]]

    state.active[0, 0] = False
    step_fast_death_bursts_(state, catalog, tracker)
    assert int(tracker.emitted_source_stable_id[0, 0].cpu()) == 0


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_seedless_replay_is_bitwise_deterministic(device_name: str) -> None:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
    left_state = _dead_sources(device)
    right_state = left_state.clone()
    left_tracker = FastDeathBurstState.empty_like(left_state)
    right_tracker = FastDeathBurstState.empty_like(right_state)
    left_catalog = _catalog(device)
    right_catalog = left_catalog.clone()

    for capacity in (1, 5, 2):
        left = step_fast_death_bursts_(
            left_state, left_catalog, left_tracker, max_commands=capacity
        )
        right = step_fast_death_bursts_(
            right_state, right_catalog, right_tracker, max_commands=capacity
        )
        _assert_equal(left, right)
        torch.testing.assert_close(
            left_tracker.emitted_source_stable_id,
            right_tracker.emitted_source_stable_id,
        )

        # Reuse one slot between ticks to exercise identity tracking in replay.
        left_state.stable_id[0, 1].add_(100)
        right_state.stable_id[0, 1].add_(100)


def test_runtime_kernel_has_no_host_reads_or_dynamic_event_compaction() -> None:
    source = inspect.getsource(step_fast_death_bursts_)
    for forbidden in (".item(", ".tolist(", ".cpu(", "nonzero(", "unique("):
        assert forbidden not in source
