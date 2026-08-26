from __future__ import annotations

from dataclasses import fields
import inspect

import pytest
import torch

from clasher.torch_sim.simple_scheduled_spawns import (
    FastScheduledCastCommands,
    FastScheduledCastState,
    allocate_fast_scheduled_casts_,
    step_fast_scheduled_casts_,
)


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _commands(
    device: torch.device,
    rows: list[dict[str, int | float | bool]],
) -> FastScheduledCastCommands:
    defaults: dict[str, int | float | bool] = {
        "ready": True,
        "owner": 0,
        "source_card_id": 1,
        "x_units": 9_000,
        "y_units": 16_000,
        "first_delay_ticks": 0,
        "interval_ticks": 0,
        "waves": 1,
        "child_card_id": 2,
        "count": 1,
        "radius_units": 0,
        "deploy_ticks": 0,
        "initial_damage": 0.0,
        "initial_radius_units": 0,
        "initial_status_kind": 0,
        "initial_status_duration_ticks": 0,
        "tower_damage_multiplier": 1.0,
        "building_damage_multiplier": 1.0,
        "hits_air": True,
        "hits_ground": True,
    }
    values = [{**defaults, **row} for row in rows]

    def tensor(name: str, dtype: torch.dtype) -> torch.Tensor:
        return torch.tensor(
            [[value[name] for value in values]], dtype=dtype, device=device
        )

    return FastScheduledCastCommands(
        ready=tensor("ready", torch.bool),
        owner=tensor("owner", torch.int8),
        source_card_id=tensor("source_card_id", torch.int64),
        x_units=tensor("x_units", torch.int32),
        y_units=tensor("y_units", torch.int32),
        first_delay_ticks=tensor("first_delay_ticks", torch.int32),
        interval_ticks=tensor("interval_ticks", torch.int32),
        waves=tensor("waves", torch.int32),
        child_card_id=tensor("child_card_id", torch.int64),
        count=tensor("count", torch.int32),
        radius_units=tensor("radius_units", torch.int32),
        deploy_ticks=tensor("deploy_ticks", torch.int32),
        initial_damage=tensor("initial_damage", torch.float32),
        initial_radius_units=tensor("initial_radius_units", torch.int32),
        initial_status_kind=tensor("initial_status_kind", torch.int8),
        initial_status_duration_ticks=tensor(
            "initial_status_duration_ticks", torch.int32
        ),
        tower_damage_multiplier=tensor(
            "tower_damage_multiplier", torch.float32
        ),
        building_damage_multiplier=tensor(
            "building_damage_multiplier", torch.float32
        ),
        hits_air=tensor("hits_air", torch.bool),
        hits_ground=tensor("hits_ground", torch.bool),
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_one_shot_delayed_spawn_and_initial_area_payload(device_name: str) -> None:
    device = _device(device_name)
    state = FastScheduledCastState.empty(1, max_casts=2, device=device)
    commands = _commands(
        device,
        [
            {
                "owner": 1,
                "source_card_id": 21,
                "x_units": 10_000,
                "y_units": 12_000,
                "first_delay_ticks": 41,
                "child_card_id": 8,
                "deploy_ticks": 20,
                "initial_damage": 437.0,
                "initial_radius_units": 3_000,
                "tower_damage_multiplier": 0.3,
            }
        ],
    )
    allocation = allocate_fast_scheduled_casts_(state, commands, tick=100)
    assert allocation.accepted.tolist() == [[True]]
    assert state.stable_id.tolist() == [[1, 0]]
    assert state.next_tick.tolist() == [[141, 0]]

    early = step_fast_scheduled_casts_(state, tick=140)
    assert early.emitted_count.tolist() == [0]
    assert not bool(early.effect_commands.ready.any())
    assert not bool(early.spawn_commands.ready.any())

    due = step_fast_scheduled_casts_(state, tick=141)
    assert due.emitted_count.tolist() == [1]
    assert due.effect_commands.ready.tolist() == [[True, False]]
    assert due.spawn_commands.ready.tolist() == [[True, False]]
    assert due.effect_commands.cast_stable_id.tolist() == [[1, 0]]
    assert due.effect_commands.damage.tolist() == [[437.0, 0.0]]
    assert due.effect_commands.radius_units.tolist() == [[3_000, 0]]
    assert due.spawn_commands.child_card_id.tolist() == [[8, 0]]
    assert due.spawn_commands.deploy_ticks.tolist() == [[20, 0]]
    assert due.expired_mask.tolist() == [[True, False]]
    assert not bool(state.active.any())
    assert state.stable_id.tolist() == [[0, 0]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_repeated_area_spawn_waves_use_numeric_cadence(device_name: str) -> None:
    device = _device(device_name)
    state = FastScheduledCastState.empty(1, max_casts=3, device=device)
    commands = _commands(
        device,
        [
            {
                "first_delay_ticks": 10,
                "interval_ticks": 7,
                "waves": 3,
                "child_card_id": 4,
                "count": 1,
                "radius_units": 4_000,
                "deploy_ticks": 10,
            }
        ],
    )
    allocate_fast_scheduled_casts_(state, commands, tick=5)

    emissions: list[tuple[int, list[int], list[int]]] = []
    for tick in (14, 15, 21, 22, 29):
        result = step_fast_scheduled_casts_(state, tick=tick)
        if bool(result.spawn_commands.ready.any()):
            emissions.append(
                (
                    tick,
                    result.spawn_commands.child_card_id[
                        result.spawn_commands.ready
                    ].tolist(),
                    result.spawn_commands.radius_units[
                        result.spawn_commands.ready
                    ].tolist(),
                )
            )
    assert emissions == [(15, [4], [4_000]), (22, [4], [4_000]), (29, [4], [4_000])]
    assert not bool(state.active.any())
    assert int(state.next_stable_id[0]) == 2


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_capacity_rejection_and_slot_reuse_keep_monotonic_order(
    device_name: str,
) -> None:
    device = _device(device_name)
    state = FastScheduledCastState.empty(1, max_casts=2, device=device)
    initial = _commands(
        device,
        [
            {"first_delay_ticks": 10, "child_card_id": 10},
            {"first_delay_ticks": 20, "child_card_id": 20},
            {"first_delay_ticks": 30, "child_card_id": 30},
        ],
    )
    allocation = allocate_fast_scheduled_casts_(state, initial, tick=0)
    assert allocation.accepted.tolist() == [[True, True, False]]
    assert allocation.capacity_rejected.tolist() == [[False, False, True]]
    assert allocation.capacity_rejected_count.tolist() == [1]
    assert state.stable_id.tolist() == [[1, 2]]

    step_fast_scheduled_casts_(state, tick=10)
    assert state.stable_id.tolist() == [[0, 2]]
    reused = allocate_fast_scheduled_casts_(
        state,
        _commands(device, [{"first_delay_ticks": 10, "child_card_id": 30}]),
        tick=10,
    )
    assert reused.accepted.tolist() == [[True]]
    assert state.stable_id.tolist() == [[3, 2]]

    # Both casts are due at tick 20. The older cast (ID 2) is emitted before
    # the newly allocated cast (ID 3), independent of physical slot order.
    simultaneous = step_fast_scheduled_casts_(state, tick=20)
    assert simultaneous.spawn_commands.cast_stable_id.tolist() == [[2, 3]]
    assert simultaneous.spawn_commands.child_card_id.tolist() == [[20, 30]]
    assert simultaneous.expired_mask.tolist() == [[True, True]]
    assert not bool(state.active.any())
    assert int(state.next_stable_id[0]) == 4


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_scheduled_cast_replay_is_exact(device_name: str) -> None:
    device = _device(device_name)
    left = FastScheduledCastState.empty(1, max_casts=4, device=device)
    commands = _commands(
        device,
        [
            {
                "owner": 1,
                "first_delay_ticks": 4,
                "interval_ticks": 3,
                "waves": 3,
                "child_card_id": 5,
                "initial_damage": 90.0,
                "initial_status_kind": 2,
                "initial_status_duration_ticks": 8,
            },
            {"first_delay_ticks": 7, "child_card_id": 6},
        ],
    )
    allocate_fast_scheduled_casts_(left, commands, tick=10)
    right = left.clone()
    for tick in (13, 14, 17, 20):
        left_result = step_fast_scheduled_casts_(left, tick=tick)
        right_result = step_fast_scheduled_casts_(right, tick=tick)
        for descriptor in fields(left_result):
            left_value = getattr(left_result, descriptor.name)
            right_value = getattr(right_result, descriptor.name)
            if isinstance(left_value, torch.Tensor):
                assert torch.equal(left_value, right_value)
            else:
                for nested in fields(left_value):
                    assert torch.equal(
                        getattr(left_value, nested.name),
                        getattr(right_value, nested.name),
                    )
    for descriptor in fields(left):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(left, descriptor.name), getattr(right, descriptor.name)
            )


def test_invalid_schedules_fail_closed_without_spending_capacity() -> None:
    device = torch.device("cpu")
    state = FastScheduledCastState.empty(1, max_casts=2, device=device)
    commands = _commands(
        device,
        [
            {"waves": 2, "interval_ticks": 0},
            {
                "waves": 2,
                "interval_ticks": 1,
                "child_card_id": 0,
                "count": 0,
                "initial_damage": 1.0,
            },
            {
                "child_card_id": 0,
                "count": 0,
                "initial_damage": 0.0,
            },
        ],
    )
    allocation = allocate_fast_scheduled_casts_(state, commands, tick=0)
    assert allocation.invalid.tolist() == [[True, True, True]]
    assert not bool(allocation.accepted.any())
    assert not bool(allocation.capacity_rejected.any())
    assert not bool(state.active.any())
    assert int(state.next_stable_id[0]) == 1


def test_runtime_kernels_have_no_host_reads_names_or_dynamic_compaction() -> None:
    for function in (allocate_fast_scheduled_casts_, step_fast_scheduled_casts_):
        source = inspect.getsource(function)
        for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
            assert forbidden not in source
        assert "Graveyard" not in source
        assert "RoyalDelivery" not in source
