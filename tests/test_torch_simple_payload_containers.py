from __future__ import annotations

import inspect

import pytest
import torch

from clasher.torch_sim.simple_payload_containers import (
    FastPayloadContainerCommands,
    FastPayloadContainerState,
    allocate_fast_payload_containers_,
    step_fast_payload_containers_,
)


def _commands(
    state: FastPayloadContainerState,
    *,
    lifetimes: tuple[int, ...],
    damages: tuple[float, ...],
    blueprints: tuple[int, ...],
) -> FastPayloadContainerCommands:
    count = len(lifetimes)
    device = state.device
    shape = (state.batch_size, count)
    assert state.batch_size == 1
    return FastPayloadContainerCommands(
        ready=torch.ones(shape, dtype=torch.bool, device=device),
        source_id=torch.arange(10, 10 + count, dtype=torch.int64, device=device)[None],
        owner=torch.tensor(
            [[index % 2 for index in range(count)]],
            dtype=torch.int8,
            device=device,
        ),
        x_units=torch.arange(
            5_000, 5_000 + count * 100, 100, dtype=torch.int32, device=device
        )[None],
        y_units=torch.arange(
            8_000, 8_000 + count * 100, 100, dtype=torch.int32, device=device
        )[None],
        lifetime_ticks=torch.tensor([lifetimes], dtype=torch.int32, device=device),
        effect_card_id=torch.arange(100, 100 + count, dtype=torch.int64, device=device)[
            None
        ],
        effect_damage=torch.tensor([damages], dtype=torch.float32, device=device),
        effect_radius_units=torch.full(shape, 3_000, dtype=torch.int32, device=device),
        effect_status_kind=torch.zeros(shape, dtype=torch.int8, device=device),
        effect_status_duration_ticks=torch.zeros(
            shape, dtype=torch.int32, device=device
        ),
        tower_damage_multiplier=torch.full(
            shape, 0.3, dtype=torch.float32, device=device
        ),
        building_damage_multiplier=torch.ones(
            shape, dtype=torch.float32, device=device
        ),
        hits_air=torch.ones(shape, dtype=torch.bool, device=device),
        hits_ground=torch.ones(shape, dtype=torch.bool, device=device),
        nested_spawn_blueprint_id=torch.tensor(
            [blueprints], dtype=torch.int64, device=device
        ),
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_balloon_bomb_bomb_tower_bomb_and_container_native_timing(
    device_name: str,
) -> None:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    state = FastPayloadContainerState.empty(1, max_containers=4, device=device_name)
    # Native logic ticks are 50 ms: the serialized deploy times are 3000,
    # 3000, and 600 ms respectively. The third payload also releases a nested
    # Skeleton blueprint after its terminal damage.
    commands = _commands(
        state,
        lifetimes=(60, 60, 12),
        damages=(144.0, 87.0, 57.0),
        blueprints=(0, 0, 41),
    )
    allocation = allocate_fast_payload_containers_(state, commands)
    assert allocation.accepted.all()
    assert state.stable_id[0, :3].tolist() == [1, 2, 3]

    for _ in range(11):
        result = step_fast_payload_containers_(state)
        assert not result.expired_mask.any()
    result = step_fast_payload_containers_(state)
    assert result.emitted_count.tolist() == [1]
    assert result.effect_commands.ready[0, 0]
    assert result.effect_commands.payload_stable_id[0, 0].item() == 3
    assert result.effect_commands.damage[0, 0].item() == 57.0
    assert result.spawn_triggers.ready[0, 0]
    assert result.spawn_triggers.blueprint_id[0, 0].item() == 41
    assert not state.active[0, 2]

    for _ in range(47):
        result = step_fast_payload_containers_(state)
        assert not result.expired_mask.any()
    result = step_fast_payload_containers_(state)
    assert result.emitted_count.tolist() == [2]
    assert result.effect_commands.ready[0, :2].tolist() == [True, True]
    assert result.effect_commands.payload_stable_id[0, :2].tolist() == [1, 2]
    assert result.effect_commands.damage[0, :2].tolist() == [144.0, 87.0]
    assert not result.spawn_triggers.ready.any()
    assert not state.active.any()


def test_simultaneous_expiry_is_stable_id_ordered_not_slot_ordered() -> None:
    state = FastPayloadContainerState.empty(1, max_containers=5)
    state.active[0, [0, 2, 4]] = True
    state.stable_id[0, [0, 2, 4]] = torch.tensor([30, 5, 20])
    state.source_id[0, [0, 2, 4]] = torch.tensor([130, 105, 120])
    state.owner[0, [0, 2, 4]] = torch.tensor([0, 1, 0], dtype=torch.int8)
    state.lifetime_ticks[0, [0, 2, 4]] = 1
    state.effect_card_id[0, [0, 2, 4]] = 9
    state.effect_damage[0, [0, 2, 4]] = torch.tensor([30.0, 5.0, 20.0])
    state.effect_radius_units[0, [0, 2, 4]] = 2_000

    result = step_fast_payload_containers_(state)

    assert result.effect_commands.payload_stable_id[0, :3].tolist() == [5, 20, 30]
    assert result.effect_commands.source_id[0, :3].tolist() == [105, 120, 130]
    assert result.effect_commands.damage[0, :3].tolist() == [5.0, 20.0, 30.0]
    assert result.effect_commands.ready[0, :3].all()
    assert not result.effect_commands.ready[0, 3:].any()
    assert not state.active.any()


def test_replay_is_deterministic_and_capacity_rejection_is_explicit() -> None:
    initial = FastPayloadContainerState.empty(1, max_containers=2)
    commands = _commands(
        initial,
        lifetimes=(3, 2, 1),
        damages=(3.0, 2.0, 1.0),
        blueprints=(0, 0, 7),
    )
    allocation = allocate_fast_payload_containers_(initial, commands)
    assert allocation.accepted.tolist() == [[True, True, False]]
    assert allocation.capacity_rejected.tolist() == [[False, False, True]]
    assert allocation.capacity_rejected_count.tolist() == [1]
    assert not allocation.invalid.any()

    left = initial.clone()
    right = initial.clone()
    for _ in range(3):
        left_result = step_fast_payload_containers_(left)
        right_result = step_fast_payload_containers_(right)
        for field in (
            "expired_mask",
            "emitted_count",
        ):
            torch.testing.assert_close(
                getattr(left_result, field), getattr(right_result, field)
            )
        for field in (
            "ready",
            "payload_stable_id",
            "source_id",
            "owner",
            "effect_card_id",
            "x_units",
            "y_units",
            "damage",
            "radius_units",
            "status_kind",
            "status_duration_ticks",
            "tower_damage_multiplier",
            "building_damage_multiplier",
            "hits_air",
            "hits_ground",
        ):
            torch.testing.assert_close(
                getattr(left_result.effect_commands, field),
                getattr(right_result.effect_commands, field),
            )
        torch.testing.assert_close(left.active, right.active)
        torch.testing.assert_close(left.stable_id, right.stable_id)


def test_expiry_and_slot_reuse_clear_every_stale_descriptor() -> None:
    state = FastPayloadContainerState.empty(1, max_containers=1)
    first = _commands(
        state,
        lifetimes=(1,),
        damages=(12.0,),
        blueprints=(22,),
    )
    first = FastPayloadContainerCommands(
        **{
            **first.__dict__,
            "effect_status_kind": torch.tensor([[2]], dtype=torch.int8),
            "effect_status_duration_ticks": torch.tensor([[9]], dtype=torch.int32),
            "hits_air": torch.tensor([[False]]),
            "tower_damage_multiplier": torch.tensor([[0.25]]),
        }
    )
    allocate_fast_payload_containers_(state, first)
    step_fast_payload_containers_(state)
    assert not state.active.any()
    assert state.effect_damage.item() == 0
    assert state.effect_status_kind.item() == 0
    assert state.nested_spawn_blueprint_id.item() == 0
    assert state.hits_air.item()
    assert state.tower_damage_multiplier.item() == 1.0

    second = _commands(
        state,
        lifetimes=(2,),
        damages=(0.0,),
        blueprints=(99,),
    )
    allocation = allocate_fast_payload_containers_(state, second)
    assert allocation.accepted.item()
    assert state.stable_id.item() == 2
    assert state.effect_damage.item() == 0
    assert state.effect_status_kind.item() == 0
    assert state.nested_spawn_blueprint_id.item() == 99
    assert state.hits_air.item()
    assert state.tower_damage_multiplier.item() == pytest.approx(0.3)


def test_payload_hot_paths_do_not_sync_or_compact_on_host() -> None:
    for function in (
        allocate_fast_payload_containers_,
        step_fast_payload_containers_,
    ):
        source = inspect.getsource(function)
        for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
            assert forbidden not in source
