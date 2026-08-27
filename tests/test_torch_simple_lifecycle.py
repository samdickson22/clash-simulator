from __future__ import annotations

import inspect

import pytest
import torch

from clasher.torch_sim.simple_lifecycle import (
    FastLifecycleState,
    step_fast_lifecycle_,
)
from clasher.torch_sim.simple_state import (
    FAST_KIND_BUILDING,
    FAST_KIND_TROOP,
    FastGymState,
)


def _devices() -> tuple[str, ...]:
    return ("cpu", "cuda")


@pytest.mark.parametrize("device", _devices())
def test_cannon_lifetime_expires_and_cleans_slot(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = FastGymState.empty(1, max_entities=4, device=device)
    lifecycle = FastLifecycleState.empty_like(state)
    state.active[0, 1] = True
    state.stable_id[0, 1] = 7
    state.next_stable_id[0] = 8
    state.kind[0, 1] = FAST_KIND_BUILDING
    state.owner[0, 1] = 1
    state.card_id[0, 1] = 22
    state.x_units[0, 1] = 9_000
    state.y_units[0, 1] = 18_000
    state.hp[0, 1] = 824
    state.max_hp[0, 1] = 824
    lifecycle.lifetime_ticks[0, 1] = 2

    first = step_fast_lifecycle_(state, lifecycle)
    assert lifecycle.lifetime_ticks[0, 1].item() == 1
    assert state.active[0, 1].item()
    assert not first.expired_mask.any().item()

    second = step_fast_lifecycle_(state, lifecycle)
    assert second.expired_mask.tolist() == [[False, True, False, False]]
    assert second.resolved_parent_mask.tolist() == [[False, True, False, False]]
    assert not state.active[0, 1].item()
    assert state.stable_id[0, 1].item() == 0
    assert state.hp[0, 1].item() == 0
    assert state.next_stable_id[0].item() == 8


@pytest.mark.parametrize("device", _devices())
def test_generic_six_child_death_spawn_is_stable_and_circular(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = FastGymState.empty(1, max_entities=10, device=device)
    lifecycle = FastLifecycleState.empty_like(state)
    state.active[0, :3] = True
    state.stable_id[0, :3] = torch.tensor([90, 4, 30], device=state.device)
    state.next_stable_id[0] = 91
    state.owner[0, :3] = torch.tensor([0, 1, 0], device=state.device)
    state.hp[0, :3] = torch.tensor([100.0, 0.0, 100.0], device=state.device)
    state.x_units[0, 1] = 5_000
    state.y_units[0, 1] = 7_000
    lifecycle.death_spawn_count[0, 1] = 6
    lifecycle.death_spawn_card_id[0, 1] = 73
    lifecycle.death_spawn_kind[0, 1] = FAST_KIND_TROOP
    lifecycle.death_spawn_hp[0, 1] = 81
    lifecycle.death_spawn_radius_units[0, 1] = 200
    lifecycle.death_spawn_deploy_ticks[0, 1] = 3

    result = step_fast_lifecycle_(state, lifecycle, reserved_slot_floor=1)

    # Parent slot 1 is immediately reusable; six lowest nonreserved free slots
    # receive monotonic IDs regardless of the parent's physical slot.
    assert result.spawned_mask.tolist() == [
        [False, True, False, True, True, True, True, True, False, False]
    ]
    assert state.stable_id[0, [1, 3, 4, 5, 6, 7]].tolist() == list(range(91, 97))
    assert result.spawned_parent_ids[0, [1, 3, 4, 5, 6, 7]].tolist() == [4] * 6
    assert state.owner[0, [1, 3, 4, 5, 6, 7]].tolist() == [1] * 6
    assert state.card_id[0, [1, 3, 4, 5, 6, 7]].tolist() == [73] * 6
    assert state.hp[0, [1, 3, 4, 5, 6, 7]].tolist() == [81.0] * 6
    assert state.deploy_ticks[0, [1, 3, 4, 5, 6, 7]].tolist() == [3] * 6
    assert state.next_stable_id.tolist() == [97]
    assert not result.capacity_rejected.any().item()
    positions = set(
        zip(
            state.x_units[0, [1, 3, 4, 5, 6, 7]].tolist(),
            state.y_units[0, [1, 3, 4, 5, 6, 7]].tolist(),
            strict=True,
        )
    )
    assert len(positions) == 6


def test_death_spawn_orders_parents_by_stable_id_and_reports_capacity() -> None:
    state = FastGymState.empty(1, max_entities=6)
    lifecycle = FastLifecycleState.empty_like(state)
    state.active[0, 1:4] = True
    state.stable_id[0, 1:4] = torch.tensor([20, 5, 40])
    state.next_stable_id[0] = 41
    state.owner[0, 1:4] = torch.tensor([0, 1, 0])
    state.hp[0, 1:4] = torch.tensor([0.0, 0.0, 100.0])
    state.x_units[0, 1:3] = torch.tensor([8_000, 2_000])
    lifecycle.death_spawn_count[0, 1:3] = torch.tensor([3, 3])
    lifecycle.death_spawn_card_id[0, 1:3] = torch.tensor([120, 105])
    lifecycle.death_spawn_kind[0, 1:3] = FAST_KIND_TROOP
    lifecycle.death_spawn_hp[0, 1:3] = 10

    result = step_fast_lifecycle_(state, lifecycle, reserved_slot_floor=1)

    # Four slots are available. Stable-ID 5 receives all three children first;
    # stable-ID 20 receives one and rejects its remaining two.
    assert state.card_id[0, 1:3].tolist() == [105, 105]
    assert state.card_id[0, 4].item() == 105
    assert state.card_id[0, 5].item() == 120
    assert result.spawned_parent_ids[0, [1, 2, 4, 5]].tolist() == [5, 5, 5, 20]
    assert result.capacity_rejected.tolist() == [
        [False, True, False, False, False, False]
    ]
    assert result.capacity_rejected_count.tolist() == [[0, 2, 0, 0, 0, 0]]
    assert state.next_stable_id.tolist() == [45]


def test_lifecycle_hot_path_has_no_dynamic_compaction_or_host_sync() -> None:
    source = inspect.getsource(step_fast_lifecycle_)
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
