from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_types import CardStatsCompat, Mechanic
from clasher.entities import (
    AreaEffect,
    DeathAreaEffectContainer,
    Entity,
    Projectile,
    TargetType,
    TimedExplosive,
    Troop,
)
from clasher.torch_sim.runtime_objects import (
    TensorRuntimeObjectPhase,
    step_runtime_object_phase_,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
)

EMPTY_CARD_STATS = cast(CardStatsCompat, None)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable on this host")
    yield device


def _troop(
    battle: BattleState,
    entity_id: int,
    player_id: int,
    position: Position,
    *,
    hp: float = 500.0,
) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    entity = Troop(
        id=entity_id,
        position=position,
        player_id=player_id,
        card_stats=stats,
        hitpoints=hp,
        max_hitpoints=hp,
        damage=float(stats.scaled_damage or stats.damage or 0),
        range=float(stats.range or 0),
        sight_range=float(stats.sight_range or 0),
        speed=0,
        target_type=TargetType.GROUND,
    )
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _projectile(
    entity_id: int,
    target: Troop,
    *,
    start: Position = Position(0, 0),
    target_position: Position | None = None,
    damage: float = 123,
    speed: float = 8,
) -> Projectile:
    return Projectile(
        id=entity_id,
        position=Position(start.x, start.y),
        player_id=1 - target.player_id,
        card_stats=EMPTY_CARD_STATS,
        hitpoints=1,
        max_hitpoints=1,
        damage=damage,
        range=0,
        sight_range=0,
        target_position=target_position
        or Position(target.position.x, target.position.y),
        travel_speed=speed,
        tracks_target=False,
        primary_target=target,
        source_name="serialized-projectile",
    )


def _battle(*entities: Entity, next_entity_id: int | None = None) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities = {entity.id: entity for entity in entities}
    battle.next_entity_id = next_entity_id or (
        max((entity.id for entity in entities), default=0) + 1
    )
    for entity in entities:
        setattr(entity, "battle_state", battle)
    return battle


def _runtime_phase(
    battles: list[BattleState],
    *,
    device: str = "cpu",
    event_capacity: int = 64,
    max_entities: int = 16,
    max_objects: int = 16,
) -> tuple[TensorBattleRuntime, TensorRuntimeObjectPhase]:
    runtime = TensorBattleRuntime.from_battles(
        battles,
        device=device,
        max_entities=max_entities,
        event_capacity=event_capacity,
    )
    phase = TensorRuntimeObjectPhase.from_battles(
        runtime, battles, max_objects=max_objects
    )
    return runtime, phase


def _oracle_object_tick(battle: BattleState) -> None:
    initial_ids = set(battle.entities)
    battle._defer_projectile_impacts = True
    battle._run_object_phase(battle.dt, initial_ids, initial_ids)
    battle._defer_projectile_impacts = False
    battle._resolve_pending_projectile_impacts()
    battle._cleanup_dead_entities()


def _runtime_row_snapshot(
    runtime: TensorBattleRuntime, row: int
) -> dict[str, torch.Tensor]:
    snapshot: dict[str, torch.Tensor] = {}
    for owner_name in ("battle", "entity_pool", "status", "phases", "events"):
        owner = getattr(runtime, owner_name)
        for name, value in vars(owner).items():
            if (
                isinstance(value, torch.Tensor)
                and value.ndim > 0
                and value.shape[0] == runtime.batch_size
            ):
                snapshot[f"{owner_name}.{name}"] = value[row].clone()
    return snapshot


def test_retained_projectile_travel_and_direct_impact_are_exact_on_device(
    tensor_device: str,
) -> None:
    seed = BattleState(fast_path=False)
    target = _troop(seed, 1, 1, Position(1.2, 0), hp=500)
    projectile = _projectile(2, target, target_position=Position(1.2, 0))
    battle = _battle(target, projectile, next_entity_id=3)
    oracle = copy.deepcopy(battle)
    runtime, phase = _runtime_phase([battle], device=tensor_device)

    _oracle_object_tick(oracle)
    first = step_runtime_object_phase_(runtime, phase)
    assert first.supported_batch.tolist() == [True]
    assert int(runtime.battle.entity_x_units[0, 1].item()) == 400
    assert oracle.entities[2].position.x == 0.4
    assert runtime.events.count.tolist() == [0]

    _oracle_object_tick(oracle)
    second = step_runtime_object_phase_(runtime, phase)
    assert second.supported_batch.tolist() == [True]
    assert int(runtime.battle.entity_x_units[0, 1].item()) == 800
    assert oracle.entities[2].position.x == 0.8

    _oracle_object_tick(oracle)
    third = step_runtime_object_phase_(runtime, phase)
    assert third.supported_batch.tolist() == [True]
    assert runtime.battle.entity_hp[0, 0].item() == 377
    assert runtime.battle.entity_id[0, :2].tolist() == [1, 0]
    assert third.removed.entity_ids[0, 0].item() == 2
    assert oracle.entities[1].hitpoints == runtime.battle.entity_hp[0, 0].item()
    assert set(oracle.entities) == {1}
    assert runtime.events.opcode[0, : runtime.events.count[0]].tolist() == [
        RuntimeEventOpcode.PROJECTILE,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
    ]


def test_scheduled_area_and_timed_explosive_damage_runtime_planes_exactly() -> None:
    area_seed = BattleState(fast_path=False)
    area_target = _troop(area_seed, 1, 1, Position(9.5, 14), hp=500)
    area = AreaEffect(
        id=2,
        position=Position(9, 14),
        player_id=0,
        card_stats=EMPTY_CARD_STATS,
        hitpoints=1,
        max_hitpoints=1,
        damage=80,
        range=2,
        sight_range=2,
        duration=0.05,
        radius=2,
        damage_tick_interval=0.05,
        initial_damage_delay=0.05,
        max_damage_ticks=1,
    )
    area_battle = _battle(area_target, area, next_entity_id=3)

    explosive_seed = BattleState(fast_path=False)
    explosive_target = _troop(explosive_seed, 1, 1, Position(9.5, 14), hp=500)
    explosive = TimedExplosive(
        id=2,
        position=Position(9, 14),
        player_id=0,
        card_stats=EMPTY_CARD_STATS,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=0,
        sight_range=0,
        explosion_timer=0.05,
        explosion_radius=2,
        explosion_damage=80,
    )
    explosive_battle = _battle(explosive_target, explosive, next_entity_id=3)
    area_oracle = copy.deepcopy(area_battle)
    explosive_oracle = copy.deepcopy(explosive_battle)
    runtime, phase = _runtime_phase([area_battle, explosive_battle])

    _oracle_object_tick(area_oracle)
    _oracle_object_tick(explosive_oracle)
    result = step_runtime_object_phase_(runtime, phase)

    assert result.supported_batch.tolist() == [True, True]
    assert runtime.battle.entity_hp[:, 0].tolist() == [420, 420]
    assert runtime.battle.entity_id[:, :2].tolist() == [[1, 0], [1, 0]]
    assert result.damage[:, 0].tolist() == [80, 80]
    assert result.removed.entity_ids[:, 0].tolist() == [2, 2]
    assert runtime.battle.entity_hp[:, 0].tolist() == [
        area_oracle.entities[1].hitpoints,
        explosive_oracle.entities[1].hitpoints,
    ]
    assert set(area_oracle.entities) == set(explosive_oracle.entities) == {1}


def test_death_area_terminal_child_grows_then_cleans_up_in_same_frame() -> None:
    seed = BattleState(fast_path=False)
    spectator = _troop(seed, 1, 1, Position(1, 1))
    container = DeathAreaEffectContainer(
        id=2,
        position=Position(7, 12),
        player_id=0,
        card_stats=EMPTY_CARD_STATS,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=0,
        sight_range=0,
        activation_delay=0.05,
        area_data={
            "name": "SerializedZeroPulse",
            "damage": 0,
            "lifeDuration": 1,
            "radius": 1_000,
        },
    )
    battle = _battle(spectator, container, next_entity_id=3)
    oracle = copy.deepcopy(battle)
    runtime, phase = _runtime_phase([battle], max_objects=4)

    _oracle_object_tick(oracle)
    result = step_runtime_object_phase_(runtime, phase)

    assert result.supported_batch.tolist() == [True]
    assert result.object_result.processed_count.tolist() == [2]
    assert result.spawned[0].sum().item() == 1
    assert result.removed.entity_ids[0, :2].tolist() == [2, 3]
    assert runtime.entity_pool.next_entity_id.tolist() == [4]
    assert runtime.battle.entity_id[0, :3].tolist() == [1, 0, 0]
    assert runtime.events.opcode[0, : runtime.events.count[0]].tolist() == [
        RuntimeEventOpcode.SPAWN,
        RuntimeEventOpcode.DEATH,
        RuntimeEventOpcode.DEATH,
    ]
    assert runtime.events.target_id[0, 0].item() == 3
    assert not phase.objects.allocated.any()
    assert set(oracle.entities) == {1}
    assert oracle.next_entity_id == runtime.entity_pool.next_entity_id.item() == 4


def test_no_python_object_update_is_called_on_retained_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = BattleState(fast_path=False)
    target = _troop(seed, 1, 1, Position(0.4, 0))
    projectile = _projectile(2, target, target_position=Position(0.4, 0))
    battle = _battle(target, projectile, next_entity_id=3)
    runtime, phase = _runtime_phase([battle])

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Python object stepping reached retained runtime")

    monkeypatch.setattr(Projectile, "update", forbidden)
    monkeypatch.setattr(AreaEffect, "update", forbidden)
    monkeypatch.setattr(TimedExplosive, "update", forbidden)
    monkeypatch.setattr(DeathAreaEffectContainer, "update", forbidden)

    result = step_runtime_object_phase_(runtime, phase)

    assert result.supported_batch.tolist() == [True]
    assert runtime.battle.entity_hp[0, 0].item() == 377


def test_mixed_unsupported_object_and_target_rows_are_atomic() -> None:
    supported_seed = BattleState(fast_path=False)
    supported_target = _troop(supported_seed, 1, 1, Position(0.4, 0))
    supported_projectile = _projectile(
        2, supported_target, target_position=Position(0.4, 0)
    )
    supported_battle = _battle(supported_target, supported_projectile, next_entity_id=3)

    homing_seed = BattleState(fast_path=False)
    homing_target = _troop(homing_seed, 1, 1, Position(0.4, 0))
    homing = _projectile(2, homing_target, target_position=Position(0.4, 0))
    homing.tracks_target = True
    homing_battle = _battle(homing_target, homing, next_entity_id=3)

    mechanic_seed = BattleState(fast_path=False)
    mechanic_target = _troop(mechanic_seed, 1, 1, Position(0.4, 0))
    mechanic_target.mechanics.append(cast(Mechanic, object()))
    mechanic_projectile = _projectile(
        2, mechanic_target, target_position=Position(0.4, 0)
    )
    mechanic_battle = _battle(mechanic_target, mechanic_projectile, next_entity_id=3)
    battles = [supported_battle, homing_battle, mechanic_battle]
    runtime, phase = _runtime_phase(battles)
    before_homing = _runtime_row_snapshot(runtime, 1)
    before_mechanic = _runtime_row_snapshot(runtime, 2)
    object_before = phase.objects.object_id.clone(), phase.objects.active.clone()

    result = step_runtime_object_phase_(runtime, phase)

    assert result.supported_batch.tolist() == [True, False, False]
    assert runtime.battle.entity_hp[0, 0].item() == 377
    for row, expected in ((1, before_homing), (2, before_mechanic)):
        actual = _runtime_row_snapshot(runtime, row)
        for name, value in expected.items():
            if name in {"phases.supported"}:
                continue
            assert torch.equal(actual[name], value), (row, name)
    assert torch.equal(phase.objects.object_id[1:], object_before[0][1:])
    assert torch.equal(phase.objects.active[1:], object_before[1][1:])
    assert runtime.events.count.tolist() == [3, 0, 0]


def test_event_overflow_fails_closed_before_runtime_or_object_commit() -> None:
    seed = BattleState(fast_path=False)
    target = _troop(seed, 1, 1, Position(0.4, 0))
    projectile = _projectile(2, target, target_position=Position(0.4, 0))
    battle = _battle(target, projectile, next_entity_id=3)
    runtime, phase = _runtime_phase([battle], event_capacity=1)
    before = _runtime_row_snapshot(runtime, 0)
    object_before = copy.deepcopy(
        {
            name: value.clone()
            for name, value in vars(phase.objects).items()
            if isinstance(value, torch.Tensor)
        }
    )

    result = step_runtime_object_phase_(runtime, phase)

    assert result.supported_batch.tolist() == [False]
    after = _runtime_row_snapshot(runtime, 0)
    for name, value in before.items():
        if name == "phases.supported":
            continue
        assert torch.equal(after[name], value), name
    for name, value in object_before.items():
        assert torch.equal(getattr(phase.objects, name), value), name
    assert runtime.events.count.tolist() == [0]
