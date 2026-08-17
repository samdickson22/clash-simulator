from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import cast

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_types import CardStatsCompat
from clasher.data import CardDataLoader
from clasher.effects.projectile import ProjectileLaunch
from clasher.entities import (
    AreaEffect,
    DeathAreaEffectContainer,
    Entity,
    Projectile,
    RollingProjectile,
    TargetType,
    TimedExplosive,
    Troop,
)
from clasher.kinematics import tiles_to_logic_units
from clasher.mechanics.mechanic_base import BaseMechanic
from clasher.torch_sim.object_adapter import (
    RuntimeObjectKind,
    runtime_objects_to_tensor,
)
from clasher.torch_sim.objects import (
    ObjectEventOpcode,
    ObjectPhaseResult,
    UnsupportedObjectFeature,
    step_object_phase,
)

EMPTY_CARD_STATS = cast(CardStatsCompat, None)


def _battle(*entities: Entity, next_entity_id: int | None = None) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities = {entity.id: entity for entity in entities}
    battle.next_entity_id = next_entity_id or (
        max((entity.id for entity in entities), default=0) + 1
    )
    for entity in entities:
        setattr(entity, "battle_state", battle)
    return battle


def _troop(
    entity_id: int,
    player_id: int,
    position: Position,
    *,
    hp: float = 1_000.0,
) -> Troop:
    stats = CardDataLoader().get_card("Knight")
    assert stats is not None
    troop = Troop(
        id=entity_id,
        position=position,
        player_id=player_id,
        card_stats=stats,
        hitpoints=hp,
        max_hitpoints=hp,
        damage=float(stats.scaled_damage or stats.damage or 0),
        range=float(stats.range or 0),
        sight_range=float(stats.sight_range or 0),
        speed=float(stats.speed or 0),
        target_type=TargetType.GROUND,
    )
    troop._spawn_hook_pending = False
    troop._spawn_hook_fired = True
    return troop


def _projectile(
    entity_id: int,
    start: Position,
    target: Position,
    *,
    damage: float = 75.0,
    speed: float = 12.0,
    player_id: int = 0,
) -> Projectile:
    return Projectile(
        id=entity_id,
        position=start,
        player_id=player_id,
        card_stats=EMPTY_CARD_STATS,
        hitpoints=1,
        max_hitpoints=1,
        damage=damage,
        range=0,
        sight_range=0,
        target_position=target,
        travel_speed=speed,
        tracks_target=False,
        source_name="serialized-projectile",
    )


def _run_python_object_phase(battle: BattleState) -> None:
    ids = set(battle.entities)
    battle._run_object_phase(battle.dt, ids, ids)


def _event_opcodes(result: ObjectPhaseResult) -> list[int]:
    count = int(result.events.count[0].item())
    return [int(value) for value in result.events.opcode[0, :count].tolist()]


@dataclass
class _HitCounter(BaseMechanic):
    hits: int = 0

    def on_attack_hit(self, entity: Entity, target: Entity) -> None:
        del entity, target
        self.hits += 1


def test_runtime_projectiles_preserve_sparse_ids_and_manager_order() -> None:
    later = _projectile(19, Position(0, 0), Position(4, 0))
    earlier = _projectile(7, Position(0, 1), Position(4, 1))
    battle = _battle(later, earlier, next_entity_id=31)

    adapted = runtime_objects_to_tensor([battle], max_objects=8)

    assert adapted.failures == ()
    assert adapted.supported_batches.tolist() == [True]
    assert adapted.state.object_id[0, :2].tolist() == [7, 19]
    assert adapted.state.next_object_id.tolist() == [31]
    assert [
        adapted.metadata[int(value)].kind
        for value in adapted.state.blueprint_id[0, :2].tolist()
    ] == [RuntimeObjectKind.PROJECTILE, RuntimeObjectKind.PROJECTILE]

    result = step_object_phase(adapted.state)

    assert result.processed_count.tolist() == [2]
    assert adapted.sync_result([battle], result).tolist() == [True]
    assert tiles_to_logic_units(earlier.position.x) == 600
    assert tiles_to_logic_units(later.position.x) == 600
    assert tuple(battle.entities) == (19, 7)


def test_enabled_projectile_episode_and_impact_match_python_oracle() -> None:
    effect = cast(
        ProjectileLaunch,
        CardDataLoader().load_card_definitions()["Fireball"].effects[0],
    )
    target = _troop(3, 1, Position(0.4, 0), hp=500)
    projectile = _projectile(
        11,
        Position(0, 0),
        Position(0.4, 0),
        damage=float(effect.damage),
        speed=float(effect.travel_speed),
    )
    projectile.primary_target = target
    candidate = _battle(target, projectile, next_entity_id=12)
    oracle = copy.deepcopy(candidate)
    _run_python_object_phase(oracle)

    adapted = runtime_objects_to_tensor([candidate], max_objects=8)
    result = step_object_phase(adapted.state)
    adapted.sync_result([candidate], result)

    assert _event_opcodes(result) == [
        ObjectEventOpcode.PROJECTILE_IMPACT,
        ObjectEventOpcode.DEATH,
    ]
    assert candidate.entities[3].hitpoints == oracle.entities[3].hitpoints
    assert candidate.entities[11].is_alive == oracle.entities[11].is_alive
    assert candidate.entities[11].position == oracle.entities[11].position


def test_projectile_impacts_commit_before_deferred_lethal_resolution() -> None:
    blue_source = _troop(1, 0, Position(0, 0))
    red_source = _troop(2, 1, Position(1, 0))
    victim = _troop(3, 1, Position(0.5, 0), hp=100)
    blue_counter = _HitCounter()
    red_counter = _HitCounter()
    blue_source.mechanics.append(blue_counter)
    red_source.mechanics.append(red_counter)
    first = _projectile(
        10,
        Position(0.5, 0),
        Position(0.5, 0),
        damage=100,
    )
    second = _projectile(
        11,
        Position(0.5, 0),
        Position(0.5, 0),
        damage=100,
        player_id=0,
    )
    first.primary_target = victim
    second.primary_target = victim
    first.source_entity = blue_source
    second.source_entity = red_source
    candidate = _battle(
        blue_source,
        red_source,
        victim,
        first,
        second,
        next_entity_id=12,
    )
    oracle = copy.deepcopy(candidate)
    oracle._defer_projectile_impacts = True
    _run_python_object_phase(oracle)
    oracle._defer_projectile_impacts = False
    oracle._resolve_pending_projectile_impacts()

    adapted = runtime_objects_to_tensor([candidate], max_objects=8)
    result = step_object_phase(adapted.state)
    adapted.sync_result([candidate], result)

    oracle_blue = oracle.entities[1]
    oracle_red = oracle.entities[2]
    assert isinstance(oracle_blue, Troop)
    assert isinstance(oracle_red, Troop)
    assert candidate.entities[3].hitpoints == oracle.entities[3].hitpoints == 0
    oracle_blue_counter = cast(_HitCounter, oracle_blue.mechanics[-1])
    oracle_red_counter = cast(_HitCounter, oracle_red.mechanics[-1])
    assert blue_counter.hits == oracle_blue_counter.hits == 1
    assert red_counter.hits == oracle_red_counter.hits == 1


def test_scheduled_area_state_events_and_damage_match_python_oracle() -> None:
    target = _troop(5, 1, Position(9.5, 14), hp=900)
    area = AreaEffect(
        id=23,
        position=Position(9, 14),
        player_id=0,
        card_stats=EMPTY_CARD_STATS,
        hitpoints=1,
        max_hitpoints=1,
        damage=91,
        range=2,
        sight_range=2,
        duration=0.15,
        radius=2,
        damage_tick_interval=0.05,
        initial_damage_delay=0.05,
        max_damage_ticks=3,
    )
    candidate = _battle(target, area, next_entity_id=24)
    oracle = copy.deepcopy(candidate)

    for expected_tick in range(1, 4):
        _run_python_object_phase(oracle)
        adapted = runtime_objects_to_tensor([candidate], max_objects=8)
        result = step_object_phase(adapted.state)
        adapted.sync_result([candidate], result)
        assert candidate.entities[5].hitpoints == oracle.entities[5].hitpoints
        oracle_area = oracle.entities[23]
        assert isinstance(oracle_area, AreaEffect)
        assert area.time_alive == oracle_area.time_alive
        assert area.damage_ticks_applied == expected_tick
        assert area.is_alive == oracle.entities[23].is_alive


def test_timed_explosive_without_child_payload_matches_python_oracle() -> None:
    target = _troop(2, 1, Position(8.5, 12), hp=700)
    explosive = TimedExplosive(
        id=33,
        position=Position(8, 12),
        player_id=0,
        card_stats=EMPTY_CARD_STATS,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=0,
        sight_range=0,
        explosion_timer=0.05,
        explosion_radius=1.5,
        explosion_damage=177,
    )
    candidate = _battle(target, explosive, next_entity_id=34)
    oracle = copy.deepcopy(candidate)
    _run_python_object_phase(oracle)

    adapted = runtime_objects_to_tensor([candidate], max_objects=8)
    result = step_object_phase(adapted.state)
    adapted.sync_result([candidate], result)

    assert _event_opcodes(result) == [ObjectEventOpcode.DEATH]
    assert candidate.entities[2].hitpoints == oracle.entities[2].hitpoints
    assert not candidate.entities[33].is_alive


def test_death_area_child_allocates_and_ticks_in_same_frame_exactly() -> None:
    target = _troop(6, 1, Position(7.5, 12), hp=500)
    container = DeathAreaEffectContainer(
        id=40,
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
            "name": "SerializedDeathPulse",
            "damage": 80,
            "lifeDuration": 1,
            "radius": 1_000,
        },
    )
    candidate = _battle(target, container, next_entity_id=41)
    oracle = copy.deepcopy(candidate)
    _run_python_object_phase(oracle)

    adapted = runtime_objects_to_tensor([candidate], max_objects=8)
    result = step_object_phase(adapted.state)
    adapted.sync_result([candidate], result)

    assert result.processed_count.tolist() == [2]
    assert adapted.state.object_id[0, :2].tolist() == [40, 41]
    assert _event_opcodes(result) == [
        ObjectEventOpcode.SPAWN,
        ObjectEventOpcode.DEATH,
        ObjectEventOpcode.AREA_TICK,
        ObjectEventOpcode.DEATH,
    ]
    candidate_child = candidate.entities[41]
    oracle_child = oracle.entities[41]
    assert type(candidate_child) is AreaEffect
    assert type(oracle_child) is AreaEffect
    assert candidate_child.time_alive == oracle_child.time_alive
    assert candidate_child.damage_ticks_applied == 1
    assert candidate.entities[6].hitpoints == oracle.entities[6].hitpoints
    assert candidate.next_entity_id == oracle.next_entity_id == 42


def test_every_unrepresented_feature_fails_closed_without_state_mutation() -> None:
    homing_target = _troop(1, 1, Position(3, 4))
    homing = _projectile(8, Position(0, 0), Position(3, 4))
    homing.primary_target = homing_target
    homing.tracks_target = True
    rolling = RollingProjectile(
        id=9,
        position=Position(9, 9),
        player_id=0,
        card_stats=EMPTY_CARD_STATS,
        hitpoints=1,
        max_hitpoints=1,
        damage=100,
        range=1,
        sight_range=1,
    )
    unsupported = _battle(homing_target, homing, rolling, next_entity_id=10)
    supported = _battle(
        _projectile(17, Position(0, 0), Position(2, 0)),
        next_entity_id=18,
    )
    adapted = runtime_objects_to_tensor([unsupported, supported], max_objects=8)
    before = {
        name: value.clone()
        for name, value in vars(adapted.state).items()
        if isinstance(value, torch.Tensor)
    }

    result = step_object_phase(adapted.state)

    assert result.unsupported_batch.tolist() == [True, False]
    assert adapted.supported_batches.tolist() == [False, True]
    assert len(adapted.failures) == 2
    assert adapted.failures[0].features & UnsupportedObjectFeature.HOMING
    assert adapted.failures[1].features & UnsupportedObjectFeature.UNKNOWN_OPERATION
    for name, expected in before.items():
        actual = getattr(adapted.state, name)
        assert torch.equal(actual[0], expected[0]), name

    unsupported_before = copy.deepcopy(unsupported)
    synchronized = adapted.sync_result([unsupported, supported], result)
    assert synchronized.tolist() == [False, True]
    assert unsupported.entities[8].position == unsupported_before.entities[8].position
    actual_rolling = unsupported.entities[9]
    expected_rolling = unsupported_before.entities[9]
    assert isinstance(actual_rolling, RollingProjectile)
    assert isinstance(expected_rolling, RollingProjectile)
    assert actual_rolling.time_alive == expected_rolling.time_alive
