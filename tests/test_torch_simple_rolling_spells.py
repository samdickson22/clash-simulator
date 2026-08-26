from __future__ import annotations

import inspect
from dataclasses import fields

import pytest
import torch

from clasher.torch_sim.simple_rolling_spells import (
    FAST_ROLLING_NO_SPAWN,
    FastRollingSpellCommands,
    FastRollingSpellState,
    allocate_fast_rolling_spells_,
    step_fast_rolling_spells_,
)
from clasher.torch_sim.simple_state import FastGymState


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _commands(
    device: torch.device,
    *,
    origins: list[tuple[int, int]],
    targets: list[tuple[int, int]],
    ranges: list[int],
    speeds: list[int],
    widths: list[int],
    damages: list[float],
    owners: list[int] | None = None,
    source_card_ids: list[int] | None = None,
    ground_only: list[bool] | None = None,
    tower_scales: list[float] | None = None,
    radial_push: list[int] | None = None,
    forward_push: list[int] | None = None,
    spawn_ids: list[int] | None = None,
    spawn_counts: list[int] | None = None,
    spawn_deploy_ticks: list[int] | None = None,
) -> FastRollingSpellCommands:
    count = len(origins)
    owners = [0] * count if owners is None else owners
    source_card_ids = (
        list(range(100, 100 + count)) if source_card_ids is None else source_card_ids
    )
    ground_only = [True] * count if ground_only is None else ground_only
    tower_scales = [1.0] * count if tower_scales is None else tower_scales
    radial_push = [0] * count if radial_push is None else radial_push
    forward_push = [0] * count if forward_push is None else forward_push
    spawn_ids = [FAST_ROLLING_NO_SPAWN] * count if spawn_ids is None else spawn_ids
    spawn_counts = [0] * count if spawn_counts is None else spawn_counts
    spawn_deploy_ticks = (
        [0] * count if spawn_deploy_ticks is None else spawn_deploy_ticks
    )

    def ints(values: list[int], dtype: torch.dtype) -> torch.Tensor:
        return torch.tensor([values], dtype=dtype, device=device)

    return FastRollingSpellCommands(
        ready=torch.ones((1, count), dtype=torch.bool, device=device),
        owner=ints(owners, torch.int8),
        source_card_id=ints(source_card_ids, torch.int64),
        origin_x_units=ints([point[0] for point in origins], torch.int32),
        origin_y_units=ints([point[1] for point in origins], torch.int32),
        target_x_units=ints([point[0] for point in targets], torch.int32),
        target_y_units=ints([point[1] for point in targets], torch.int32),
        travel_range_units=ints(ranges, torch.int32),
        speed_units_per_tick=ints(speeds, torch.int32),
        half_width_units=ints(widths, torch.int32),
        damage=torch.tensor([damages], dtype=torch.float32, device=device),
        ground_only=torch.tensor([ground_only], dtype=torch.bool, device=device),
        tower_damage_multiplier=torch.tensor(
            [tower_scales], dtype=torch.float32, device=device
        ),
        radial_push_units=ints(radial_push, torch.int32),
        forward_push_units=ints(forward_push, torch.int32),
        impact_spawn_blueprint_id=ints(spawn_ids, torch.int64),
        impact_spawn_count=ints(spawn_counts, torch.int32),
        impact_spawn_deploy_ticks=ints(spawn_deploy_ticks, torch.int32),
    )


def _seed_entity(
    gym: FastGymState,
    *,
    slot: int,
    stable_id: int,
    owner: int,
    x_units: int,
    y_units: int,
) -> None:
    gym.active[0, slot] = True
    gym.stable_id[0, slot] = stable_id
    gym.owner[0, slot] = owner
    gym.x_units[0, slot] = x_units
    gym.y_units[0, slot] = y_units
    gym.hp[0, slot] = 1_000.0
    gym.max_hp[0, slot] = 1_000.0


def _traits(
    gym: FastGymState,
    *,
    air_slots: tuple[int, ...] = (),
    tower_slots: tuple[int, ...] = (),
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    air = torch.zeros_like(gym.active)
    tower = torch.zeros_like(gym.active)
    radius = torch.zeros_like(gym.x_units)
    for slot in air_slots:
        air[0, slot] = True
    for slot in tower_slots:
        tower[0, slot] = True
    return air, radius, tower


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_log_like_swept_capsule_damages_once_and_returns_push(
    device_name: str,
) -> None:
    device = _device(device_name)
    gym = FastGymState.empty(1, max_entities=5, device=device)
    _seed_entity(
        gym,
        slot=0,
        stable_id=10,
        owner=1,
        x_units=1_000,
        y_units=100,
    )
    _seed_entity(
        gym,
        slot=1,
        stable_id=11,
        owner=1,
        x_units=1_000,
        y_units=0,
    )
    _seed_entity(
        gym,
        slot=2,
        stable_id=12,
        owner=0,
        x_units=1_000,
        y_units=0,
    )
    _seed_entity(
        gym,
        slot=3,
        stable_id=13,
        owner=1,
        x_units=3_000,
        y_units=0,
    )
    _seed_entity(
        gym,
        slot=4,
        stable_id=14,
        owner=1,
        x_units=2_000,
        y_units=0,
    )
    air, radii, towers = _traits(gym, air_slots=(1,), tower_slots=(3,))
    rolling = FastRollingSpellState.empty(
        1, max_rollers=2, max_hit_records=5, device=device
    )
    command = _commands(
        device,
        origins=[(0, 0)],
        targets=[(4_000, 0)],
        ranges=[3_000],
        speeds=[1_000],
        widths=[100],
        damages=[120.0],
        tower_scales=[0.25],
        radial_push=[200],
        forward_push=[300],
    )
    allocation = allocate_fast_rolling_spells_(rolling, command)
    assert allocation.accepted.tolist() == [[True]]
    assert allocation.roller_slot.tolist() == [[0]]

    first = step_fast_rolling_spells_(
        gym,
        rolling,
        entity_is_air=air,
        entity_collision_radius_units=radii,
        entity_is_crown_tower=towers,
    )
    assert first.hit[0, 0].tolist() == [True, False, False, False, False]
    assert gym.hp[0].tolist() == pytest.approx(
        [880.0, 1_000.0, 1_000.0, 1_000.0, 1_000.0]
    )
    assert first.impulse_dx_units[0].tolist() == [300, 0, 0, 0, 0]
    assert first.impulse_dy_units[0].tolist() == [200, 0, 0, 0, 0]

    second = step_fast_rolling_spells_(
        gym,
        rolling,
        entity_is_air=air,
        entity_collision_radius_units=radii,
        entity_is_crown_tower=towers,
    )
    # Slot zero lies in both consecutive capsules, but its stable identity is
    # present in the roller ledger and cannot be damaged twice.
    assert second.hit[0, 0].tolist() == [False, False, False, False, True]
    assert gym.hp[0].tolist() == pytest.approx(
        [880.0, 1_000.0, 1_000.0, 1_000.0, 880.0]
    )

    third = step_fast_rolling_spells_(
        gym,
        rolling,
        entity_is_air=air,
        entity_collision_radius_units=radii,
        entity_is_crown_tower=towers,
    )
    assert third.hit[0, 0].tolist() == [False, False, False, True, False]
    assert gym.hp[0, 3].item() == pytest.approx(970.0)
    assert third.ended.tolist() == [[True, False]]
    assert not bool(rolling.active.any())
    assert not bool(third.spawn.ready.any())


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_barrel_like_terminal_spawn_replays_and_pool_slot_reuses(
    device_name: str,
) -> None:
    device = _device(device_name)
    gym = FastGymState.empty(1, max_entities=2, device=device)
    _seed_entity(
        gym,
        slot=0,
        stable_id=71,
        owner=1,
        x_units=500,
        y_units=0,
    )
    air, radii, towers = _traits(gym)
    rolling = FastRollingSpellState.empty(
        1, max_rollers=1, max_hit_records=2, device=device
    )
    command = _commands(
        device,
        origins=[(0, 0)],
        targets=[(5_000, 0)],
        ranges=[2_500],
        speeds=[1_000],
        widths=[200],
        damages=[40.0],
        source_card_ids=[901],
        forward_push=[100],
        spawn_ids=[7],
        spawn_counts=[1],
        spawn_deploy_ticks=[10],
    )
    allocate_fast_rolling_spells_(rolling, command)
    replay_gym = gym.clone()
    replay_rolling = rolling.clone()

    for tick in range(3):
        left = step_fast_rolling_spells_(
            gym,
            rolling,
            entity_is_air=air,
            entity_collision_radius_units=radii,
            entity_is_crown_tower=towers,
        )
        right = step_fast_rolling_spells_(
            replay_gym,
            replay_rolling,
            entity_is_air=air,
            entity_collision_radius_units=radii,
            entity_is_crown_tower=towers,
        )
        for descriptor in fields(left):
            if descriptor.name == "spawn":
                for spawn_field in fields(left.spawn):
                    assert torch.equal(
                        getattr(left.spawn, spawn_field.name),
                        getattr(right.spawn, spawn_field.name),
                    )
            else:
                assert torch.equal(
                    getattr(left, descriptor.name),
                    getattr(right, descriptor.name),
                )
        assert bool(left.spawn.ready.any()) == (tick == 2)

    assert left.spawn.ready.tolist() == [[True]]
    assert left.spawn.blueprint_id.tolist() == [[7]]
    assert left.spawn.x_units.tolist() == [[2_500]]
    assert left.spawn.y_units.tolist() == [[0]]
    assert left.spawn.count.tolist() == [[1]]
    assert left.spawn.deploy_ticks.tolist() == [[10]]
    assert gym.hp[0, 0].item() == pytest.approx(960.0)
    assert torch.equal(gym.hp, replay_gym.hp)

    reused = allocate_fast_rolling_spells_(rolling, command)
    assert reused.roller_slot.tolist() == [[0]]
    assert not bool(rolling.hit_stable_ids.any())
    after_reuse = step_fast_rolling_spells_(
        gym,
        rolling,
        entity_is_air=air,
        entity_collision_radius_units=radii,
        entity_is_crown_tower=towers,
    )
    assert after_reuse.hit[0, 0, 0]
    assert gym.hp[0, 0].item() == pytest.approx(920.0)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_allocation_is_stable_and_invalid_commands_fail_closed(
    device_name: str,
) -> None:
    device = _device(device_name)
    rolling = FastRollingSpellState.empty(
        1, max_rollers=2, max_hit_records=2, device=device
    )
    commands = _commands(
        device,
        origins=[(0, 0), (100, 0), (200, 0)],
        targets=[(1_000, 0), (1_100, 0), (1_200, 0)],
        ranges=[1_000, 1_000, 1_000],
        speeds=[100, 100, 100],
        widths=[10, 10, 10],
        damages=[1.0, 2.0, 3.0],
        source_card_ids=[101, 102, 103],
    )
    first = allocate_fast_rolling_spells_(rolling, commands)
    assert first.accepted.tolist() == [[True, True, False]]
    assert first.capacity_rejected.tolist() == [[False, False, True]]
    assert first.roller_slot.tolist() == [[0, 1, -1]]
    assert rolling.source_card_id.tolist() == [[101, 102]]

    malformed = _commands(
        device,
        origins=[(0, 0)],
        targets=[(0, 0)],
        ranges=[1_000],
        speeds=[100],
        widths=[10],
        damages=[1.0],
        spawn_ids=[4],
        spawn_counts=[0],
    )
    rejected = allocate_fast_rolling_spells_(rolling, malformed)
    assert rejected.invalid.tolist() == [[True]]
    assert not bool(rejected.accepted.any())


def test_rolling_hot_paths_have_no_sync_compaction_or_card_dispatch() -> None:
    source = inspect.getsource(allocate_fast_rolling_spells_) + inspect.getsource(
        step_fast_rolling_spells_
    )
    for forbidden in (
        ".item(",
        ".tolist(",
        ".cpu(",
        ".nonzero(",
        "argsort(",
        "topk(",
    ):
        assert forbidden not in source
    for card_name in ("TheLog", "BarbarianBarrel"):
        assert card_name not in source
