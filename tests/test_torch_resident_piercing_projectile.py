from __future__ import annotations

import copy
import random
from contextlib import AbstractContextManager
from dataclasses import fields
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile, Troop
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.oracle_event_capture import (
    OracleEventRecord,
    PythonOracleEventCapture,
)
from clasher.torch_sim.resident_piercing_projectile import (
    TensorResidentPiercingProjectiles,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    battle._spawn_unit_at_position(
        position,
        player,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    entity = battle.entities[battle.next_entity_id - 1]
    assert isinstance(entity, Troop)
    entity.position = Position(position.x, position.y)
    entity.stun_timer = 100.0
    entity.attack_cooldown = 100.0
    return entity


def _battle(*, start_target: bool = False) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(1_001_700))
    battle.entities.clear()
    battle.next_entity_id = 1
    _spawn(battle, "MagicArcher", 0, Position(9.0, 10.0))
    if start_target:
        _spawn(battle, "Knight", 1, Position(10.0, 10.8))
        _spawn(battle, "Knight", 1, Position(10.2, 10.8))
        _spawn(battle, "Knight", 1, Position(9.0, 15.0))
    else:
        _spawn(battle, "Knight", 1, Position(9.0, 15.0))
        _spawn(battle, "Knight", 1, Position(9.0, 18.5))
        _spawn(battle, "Knight", 1, Position(10.5, 15.0))
    return battle


def _owners(
    battle: BattleState,
    device: str,
    *,
    max_entities: int = 16,
    event_capacity: int = 1_024,
    capacity: int = 4,
) -> tuple[TensorBattleRuntime, TensorResidentPiercingProjectiles]:
    runtime = TensorBattleRuntime.from_battles(
        [copy.deepcopy(battle)],
        device=device,
        max_entities=max_entities,
        event_capacity=event_capacity,
    )
    return runtime, TensorResidentPiercingProjectiles.from_battles(
        runtime, [battle], capacity=capacity
    )


def _slot(runtime: TensorBattleRuntime, entity_id: int) -> int:
    return runtime.battle.entity_id[0].tolist().index(entity_id)


def _commit_tensor(
    runtime: TensorBattleRuntime,
    owner: TensorResidentPiercingProjectiles,
    *,
    target_id: int,
) -> None:
    result = owner.commit_attacks_(
        runtime,
        source_slots=torch.tensor(
            [[_slot(runtime, 1)]], dtype=torch.int64, device=runtime.device
        ),
        target_slots=torch.tensor(
            [[_slot(runtime, target_id)]], dtype=torch.int64, device=runtime.device
        ),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )
    assert result.committed.tolist() == [True]
    assert result.accepted.tolist() == [True]


def _event_tuples(
    runtime: TensorBattleRuntime,
    start: int,
) -> list[tuple[int, int, int, int, int, int, float]]:
    end = int(runtime.events.count[0].item())
    return [
        (
            int(runtime.events.phase[0, index].item()),
            int(runtime.events.opcode[0, index].item()),
            int(runtime.events.source_id[0, index].item()),
            int(runtime.events.target_id[0, index].item()),
            int(runtime.events.x_units[0, index].item()),
            int(runtime.events.y_units[0, index].item()),
            float(runtime.events.amount[0, index].item()),
        )
        for index in range(start, end)
    ]


def _oracle_tuples(
    events: tuple[OracleEventRecord, ...] | list[OracleEventRecord],
) -> list[tuple[int, int, int, int, int, int, float]]:
    return [
        (
            event.phase,
            event.opcode,
            event.source_id,
            event.target_id,
            event.x_units,
            event.y_units,
            float(cast(Any, event.amount)),
        )
        for event in events
    ]


def _phase_scope(
    capture: PythonOracleEventCapture, phase: TickPhase, source_id: int
) -> AbstractContextManager[None]:
    return cast(
        AbstractContextManager[None],
        cast(Any, capture)._scope(phase=phase, source_id=source_id),
    )


def test_magic_archer_full_piercing_lifecycle_matches_scalar(
    tensor_device: str,
) -> None:
    seed = _battle()
    oracle = copy.deepcopy(seed)
    runtime, owner = _owners(seed, tensor_device)
    source = cast(Troop, oracle.entities[1])
    primary = cast(Troop, oracle.entities[2])
    capture = PythonOracleEventCapture(oracle)
    with capture:
        with _phase_scope(capture, TickPhase.COMBAT, source.id):
            source._create_projectile(primary, oracle)
        launch_events = tuple(capture.events)
        _commit_tensor(runtime, owner, target_id=2)
        card = int(owner.card_id[0, 0].item())

        assert owner.catalog.supported[card].item()
        assert owner.catalog.speed_units[card].item() == 1_000
        assert owner.catalog.range_units[card].item() == 11_000
        assert owner.catalog.radius_units[card].item() == 250
        assert owner.catalog.start_extra_radius_units[card].item() == 400
        assert owner.catalog.homing_time_ms[card].item() == 100
        assert owner.catalog.homing_min_distance_units[card].item() == 5_000
        assert owner.catalog.damage[card].item() == 143
        assert owner.position_units[0, 0].tolist() == [9_000, 10_800]
        assert owner.endpoint_units[0, 0].tolist() == [9_000, 21_800]
        assert owner.temporary_homing_remaining_ms[0, 0].item() == 0
        assert _event_tuples(runtime, 0) == _oracle_tuples(launch_events)

        scalar_projectile = next(
            entity
            for entity in oracle.entities.values()
            if isinstance(entity, Projectile)
        )
        for _ in range(15):
            before_oracle = len(capture.events)
            before_tensor = int(runtime.events.count[0].item())
            if scalar_projectile.is_alive:
                with _phase_scope(capture, TickPhase.OBJECTS, scalar_projectile.id):
                    scalar_projectile.update(oracle.dt, oracle)
            oracle._cleanup_dead_entities()
            result = owner.step_(runtime)
            assert result.committed.tolist() == [True]
            assert _event_tuples(runtime, before_tensor) == _oracle_tuples(
                capture.events[before_oracle:]
            )
            for target_id in (2, 3, 4):
                tensor_slot = _slot(runtime, target_id)
                scalar_target = oracle.entities[target_id]
                assert runtime.battle.entity_hp[0, tensor_slot].item() == (
                    scalar_target.hitpoints
                )
                assert runtime.battle.entity_hp_integer_kind[0, tensor_slot].item() == (
                    type(scalar_target.hitpoints) is int
                )
            if scalar_projectile.is_alive:
                assert owner.active[0, 0].item()
                assert owner.position_units[0, 0].tolist() == [
                    tiles_to_logic_units(scalar_projectile.position.x),
                    tiles_to_logic_units(scalar_projectile.position.y),
                ]
                assert owner.endpoint_units[0, 0].tolist() == [
                    tiles_to_logic_units(scalar_projectile.target_position.x),
                    tiles_to_logic_units(scalar_projectile.target_position.y),
                ]
            else:
                assert not owner.active.any()
                break

    assert oracle.entities[2].hitpoints == 1_766 - 143
    assert oracle.entities[3].hitpoints == 1_766 - 143
    assert oracle.entities[4].hitpoints == 1_766


def test_start_collision_is_enlarged_once_and_event_order_is_exact(
    tensor_device: str,
) -> None:
    seed = _battle(start_target=True)
    oracle = copy.deepcopy(seed)
    runtime, owner = _owners(seed, tensor_device)
    source = cast(Troop, oracle.entities[1])
    primary = cast(Troop, oracle.entities[4])
    capture = PythonOracleEventCapture(oracle)
    inside_before = oracle.entities[2].hitpoints
    outside_before = oracle.entities[3].hitpoints
    with capture:
        with _phase_scope(capture, TickPhase.COMBAT, source.id):
            source._create_projectile(primary, oracle)
        _commit_tensor(runtime, owner, target_id=4)

        assert oracle.entities[2].hitpoints == inside_before - source.damage
        assert oracle.entities[3].hitpoints == outside_before
        assert runtime.battle.entity_hp[0, _slot(runtime, 2)].item() == (
            oracle.entities[2].hitpoints
        )
        assert _event_tuples(runtime, 0) == _oracle_tuples(capture.events)
        assert owner.hit_count[0, 0].item() == 1

        projectile = next(
            entity
            for entity in oracle.entities.values()
            if isinstance(entity, Projectile)
        )
        before_oracle = len(capture.events)
        before_tensor = int(runtime.events.count[0].item())
        with _phase_scope(capture, TickPhase.OBJECTS, projectile.id):
            projectile.update(oracle.dt, oracle)
        step = owner.step_(runtime)
        assert step.committed.tolist() == [True]
        assert oracle.entities[2].hitpoints == inside_before - source.damage
        assert owner.hit_count[0, 0].item() == 1
        assert _event_tuples(runtime, before_tensor) == _oracle_tuples(
            capture.events[before_oracle:]
        )


def test_live_boundary_projectile_checks_tick_points_not_swept_segments(
    tensor_device: str,
) -> None:
    battle = BattleState(fast_path=False, rng=random.Random(1_001_706))
    battle.entities.clear()
    battle.next_entity_id = 1
    archer = _spawn(battle, "MagicArcher", 0, Position(3.0, 10.0))
    between = _spawn(battle, "Knight", 1, Position(4.5, 10.74))
    on_sample = _spawn(battle, "Knight", 1, Position(5.0, 10.74))
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(3.0, 10.0),
        player_id=archer.player_id,
        card_stats=archer.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=archer.damage,
        range=11.0,
        sight_range=0.0,
        target_position=Position(8.0, 10.0),
        travel_speed=20.0,
        splash_radius=0.25,
        source_name="MagicArcher",
        source_entity=archer,
        tracks_target=False,
        pierces=True,
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    oracle = copy.deepcopy(battle)
    runtime, owner = _owners(battle, tensor_device)
    scalar = cast(Projectile, oracle.entities[projectile.id])
    between_hp = between.hitpoints
    sample_hp = on_sample.hitpoints

    assert owner.active.sum().item() == 1
    for tick in range(2):
        scalar.update(oracle.dt, oracle)
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
        assert owner.position_units[0, 0].tolist() == [
            tiles_to_logic_units(scalar.position.x),
            tiles_to_logic_units(scalar.position.y),
        ]
        assert runtime.battle.entity_hp[0, _slot(runtime, between.id)].item() == (
            oracle.entities[between.id].hitpoints
        )
        assert runtime.battle.entity_hp[0, _slot(runtime, on_sample.id)].item() == (
            oracle.entities[on_sample.id].hitpoints
        )
        if tick == 0:
            assert oracle.entities[between.id].hitpoints == between_hp
            assert oracle.entities[on_sample.id].hitpoints == sample_hp
    assert oracle.entities[between.id].hitpoints == between_hp
    assert oracle.entities[on_sample.id].hitpoints == sample_hp - archer.damage


def test_temporary_homing_uses_cached_target_after_target_cleanup(
    tensor_device: str,
) -> None:
    seed = _battle()
    cast(Troop, seed.entities[2]).position = Position(11.0, 16.2)
    oracle = copy.deepcopy(seed)
    runtime, owner = _owners(seed, tensor_device)
    source = cast(Troop, oracle.entities[1])
    primary = cast(Troop, oracle.entities[2])
    source._create_projectile(primary, oracle)
    _commit_tensor(runtime, owner, target_id=2)
    projectile = next(
        entity for entity in oracle.entities.values() if isinstance(entity, Projectile)
    )
    assert projectile._temporary_homing_remaining_ms == 100
    assert owner.temporary_homing_remaining_ms[0, 0].item() == 100

    primary.is_alive = False
    oracle._cleanup_dead_entities()
    target_slot = _slot(runtime, 2)
    cleanup = torch.zeros_like(runtime.entity_pool.active)
    cleanup[0, target_slot] = True
    runtime.entity_pool.cleanup(cleanup)
    runtime.battle.entity_active[0, target_slot] = False

    for expected in (50, 0):
        projectile.update(oracle.dt, oracle)
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
        assert owner.temporary_homing_remaining_ms[0, 0].item() == expected
        assert owner.endpoint_units[0, 0].tolist() == [
            tiles_to_logic_units(projectile.target_position.x),
            tiles_to_logic_units(projectile.target_position.y),
        ]
        assert owner.position_units[0, 0].tolist() == [
            tiles_to_logic_units(projectile.position.x),
            tiles_to_logic_units(projectile.position.y),
        ]


def test_low_physical_slot_reuse_keeps_one_hit_identity_by_entity_id(
    tensor_device: str,
) -> None:
    seed = BattleState(fast_path=False, rng=random.Random(1_001_711))
    seed.entities.clear()
    seed.next_entity_id = 1
    source = _spawn(seed, "MagicArcher", 0, Position(9.0, 10.0))
    old_target = _spawn(seed, "Knight", 1, Position(9.0, 10.8))
    primary = _spawn(seed, "Knight", 1, Position(9.0, 15.0))
    oracle = copy.deepcopy(seed)
    runtime, owner = _owners(seed, tensor_device)
    scalar_source = cast(Troop, oracle.entities[source.id])
    scalar_primary = cast(Troop, oracle.entities[primary.id])
    scalar_source._create_projectile(scalar_primary, oracle)
    _commit_tensor(runtime, owner, target_id=primary.id)
    assert owner.hit_entity_ids[0, 0, 0].item() == old_target.id

    del oracle.entities[old_target.id]
    replacement = _spawn(oracle, "Knight", 1, Position(9.0, 11.8))
    old_slot = _slot(runtime, old_target.id)
    cleanup = torch.zeros_like(runtime.entity_pool.active)
    cleanup[0, old_slot] = True
    runtime.entity_pool.cleanup(cleanup)
    allocation = runtime.entity_pool.allocate(
        torch.ones(1, dtype=torch.int64, device=runtime.device)
    )
    assert allocation.slots[0, 0].item() == old_slot
    assert allocation.entity_ids[0, 0].item() == replacement.id
    core = runtime.battle
    source_slot = _slot(runtime, primary.id)
    for descriptor in fields(core):
        value = getattr(core, descriptor.name)
        if (
            descriptor.name.startswith("entity_")
            and descriptor.name != "entity_id"
            and isinstance(value, torch.Tensor)
            and value.ndim >= 2
            and value.shape[:2] == core.entity_id.shape
        ):
            value[0, old_slot] = value[0, source_slot]
    core.entity_active[0, old_slot] = True
    core.entity_x_units[0, old_slot] = 9_000
    core.entity_y_units[0, old_slot] = 11_800
    core.entity_tower_slot[0, old_slot] = -1
    runtime.phases.target_slot[0, old_slot] = -1

    scalar_projectile = next(
        entity for entity in oracle.entities.values() if isinstance(entity, Projectile)
    )
    scalar_projectile.update(oracle.dt, oracle)
    result = owner.step_(runtime)

    assert result.committed.tolist() == [True]
    assert runtime.battle.entity_hp[0, old_slot].item() == replacement.hitpoints
    assert replacement.hitpoints == replacement.max_hitpoints - source.damage
    assert owner.hit_count[0, 0].item() == 2
    assert owner.hit_entity_ids[0, 0, :2].tolist() == [
        old_target.id,
        replacement.id,
    ]


def test_lethal_same_sample_targets_follow_id_and_event_order(
    tensor_device: str,
) -> None:
    seed = BattleState(fast_path=False, rng=random.Random(1_001_712))
    seed.entities.clear()
    seed.next_entity_id = 1
    _spawn(seed, "MagicArcher", 0, Position(9.0, 10.0))
    first = _spawn(seed, "Knight", 1, Position(9.0, 10.8))
    second = _spawn(seed, "Knight", 1, Position(9.0, 10.8))
    primary = _spawn(seed, "Knight", 1, Position(9.0, 15.0))
    first.hitpoints = second.hitpoints = 143
    oracle = copy.deepcopy(seed)
    runtime, owner = _owners(seed, tensor_device)
    source = cast(Troop, oracle.entities[1])
    capture = PythonOracleEventCapture(oracle)
    with capture:
        with _phase_scope(capture, TickPhase.COMBAT, source.id):
            source._create_projectile(cast(Troop, oracle.entities[primary.id]), oracle)
        launch = owner.commit_attacks_(
            runtime,
            source_slots=torch.tensor(
                [[_slot(runtime, source.id)]], device=runtime.device
            ),
            target_slots=torch.tensor(
                [[_slot(runtime, primary.id)]], device=runtime.device
            ),
            valid=torch.tensor([[True]], device=runtime.device),
        )

        assert launch.committed.tolist() == [True]
        assert launch.deaths[0, _slot(runtime, first.id)].item()
        assert launch.deaths[0, _slot(runtime, second.id)].item()
        assert _event_tuples(runtime, 0) == _oracle_tuples(capture.events)
        assert [
            target
            for _, opcode, _, target, _, _, _ in _event_tuples(runtime, 0)
            if opcode == int(RuntimeEventOpcode.DEATH)
        ] == [first.id, second.id]
        assert not runtime.battle.entity_hp_integer_kind[
            0, _slot(runtime, first.id)
        ].item()
        assert not runtime.battle.entity_hp_integer_kind[
            0, _slot(runtime, second.id)
        ].item()


def test_clone_fork_reset_and_capacity_failure_are_atomic(
    tensor_device: str,
) -> None:
    battle = _battle()
    runtime, owner = _owners(
        battle,
        tensor_device,
        max_entities=4,
        event_capacity=16,
        capacity=1,
    )
    before_runtime = {
        descriptor.name: getattr(runtime.battle, descriptor.name).clone()
        for descriptor in fields(runtime.battle)
        if isinstance(getattr(runtime.battle, descriptor.name), torch.Tensor)
    }
    before_next = runtime.entity_pool.next_entity_id.clone()
    before_events = runtime.events.count.clone()

    result = owner.commit_attacks_(
        runtime,
        source_slots=torch.tensor(
            [[_slot(runtime, 1)]], dtype=torch.int64, device=runtime.device
        ),
        target_slots=torch.tensor(
            [[_slot(runtime, 2)]], dtype=torch.int64, device=runtime.device
        ),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )

    assert result.committed.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert not owner.active.any()
    assert torch.equal(runtime.entity_pool.next_entity_id, before_next)
    assert torch.equal(runtime.events.count, before_events)
    for name, expected in before_runtime.items():
        assert torch.equal(getattr(runtime.battle, name), expected), name

    clone = owner.clone()
    clone.entity_id[0, 0] = 99
    assert owner.entity_id[0, 0].item() == 0
    fork = clone.fork([0])
    assert fork.entity_id[0, 0].item() == 99
    clone.reset_rows_([0], owner, [0])
    assert clone.entity_id[0, 0].item() == 0


def test_catalog_is_serialized_and_fails_closed_on_extra_payloads() -> None:
    battle = _battle()
    extra_ids = {
        name: _spawn(battle, name, 0, Position(3.0 + index, 10.0)).id
        for index, name in enumerate(
            (
                "AxeMan",
                "Hunter",
                "Wallbreakers",
                "SuperArcher",
                "SuperEliteArcher",
            )
        )
    }
    runtime = TensorBattleRuntime.from_battles(
        [copy.deepcopy(battle)], max_entities=16, event_capacity=64
    )
    owner = TensorResidentPiercingProjectiles.from_battles(runtime, [battle])
    magic = int(runtime.battle.entity_card[0, _slot(runtime, 1)].item())
    assert owner.catalog.supported[magic].item()
    for name in ("AxeMan", "Hunter"):
        card = int(
            runtime.battle.entity_card[0, _slot(runtime, extra_ids[name])].item()
        )
        assert owner.catalog.supported[card].item()

    # These rows are selected or rejected from their payload/mechanic shape,
    # without runtime name branches.
    definitions = battle.card_loader.load_card_definitions()
    for name in ("Wallbreakers", "SuperArcher", "SuperEliteArcher"):
        card = int(
            runtime.battle.entity_card[0, _slot(runtime, extra_ids[name])].item()
        )
        assert not owner.catalog.supported[card].item(), definitions[name]

    count = int(runtime.events.count.item())
    assert count == 0
    assert RuntimeEventOpcode.PROJECTILE != RuntimeEventOpcode.SPAWN
