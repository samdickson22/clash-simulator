from __future__ import annotations

from dataclasses import replace

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import (
    AreaEffect,
    DeathAreaEffectContainer,
    Projectile,
    SpawnProjectile,
    Troop,
)
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.catalog import EFFECT_OPCODE
from clasher.torch_sim.objects import (
    ObjectBlueprint,
    ObjectEventOpcode,
    ObjectOpcode,
    TensorObjectCatalog,
    TensorObjectState,
    UnsupportedObjectFeature,
    step_object_phase,
)


def _events(result, batch: int = 0) -> list[tuple[int, int, int]]:
    count = int(result.events.count[batch].item())
    return [
        (
            int(result.events.opcode[batch, index].item()),
            int(result.events.source_id[batch, index].item()),
            int(result.events.payload_count[batch, index].item()),
        )
        for index in range(count)
    ]


def test_object_opcodes_are_factory_effect_opcodes_not_card_names() -> None:
    assert ObjectOpcode.PERIODIC_AREA == EFFECT_OPCODE["PeriodicArea"]
    assert ObjectOpcode.PROJECTILE_LAUNCH == EFFECT_OPCODE["ProjectileLaunch"]

    definitions = CardDataLoader().load_card_definitions()
    fireball = definitions["Fireball"].effects[0]
    blueprint = ObjectBlueprint.from_serialized_effect(
        fireball,
        player_id=0,
        position=(1.0, 2.0),
        target_position=(4.0, 6.0),
    )

    assert blueprint.opcode == ObjectOpcode.PROJECTILE_LAUNCH
    assert blueprint.speed_units_per_tick == 600
    assert blueprint.amount == 269
    assert blueprint.x_units == 1000
    assert blueprint.target_y_units == 6000


def test_enabled_fireball_projectile_travel_and_arrival_match_python_exactly() -> None:
    effect = CardDataLoader().load_card_definitions()["Fireball"].effects[0]
    blueprint = ObjectBlueprint.from_serialized_effect(
        effect,
        player_id=0,
        position=(0.0, 0.0),
        target_position=(3.0, 4.0),
    )
    catalog = TensorObjectCatalog.compile([blueprint])
    state = TensorObjectState.create(catalog, [[1]], max_objects=4)

    battle = BattleState()
    battle.entities.clear()
    projectile = Projectile(
        id=1,
        position=Position(0.0, 0.0),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=effect.damage,
        range=0,
        sight_range=0,
        target_position=Position(3.0, 4.0),
        travel_speed=effect.travel_speed,
        source_name="serialized-projectile",
        tracks_target=False,
    )

    last_result = None
    for _ in range(9):
        projectile.update(battle.dt, battle)
        last_result = step_object_phase(state)
        assert int(state.x_units[0, 0]) == tiles_to_logic_units(projectile.position.x)
        assert int(state.y_units[0, 0]) == tiles_to_logic_units(projectile.position.y)
        assert bool(state.active[0, 0]) == projectile.is_alive

    assert last_result is not None
    assert _events(last_result) == [
        (ObjectEventOpcode.PROJECTILE_IMPACT, 1, 0),
        (ObjectEventOpcode.DEATH, 1, 0),
    ]
    assert int(last_result.events.x_units[0, 0]) == 3000
    assert int(last_result.events.y_units[0, 0]) == 4000


def test_scheduled_area_tick_clocks_and_lifetime_match_python_exactly() -> None:
    blueprint = ObjectBlueprint(
        opcode=ObjectOpcode.PERIODIC_AREA,
        x_units=9000,
        y_units=14000,
        duration_ms=150,
        tick_interval_ms=50,
        initial_tick_ms=50,
        max_ticks=3,
        amount=91,
    )
    catalog = TensorObjectCatalog.compile([blueprint])
    state = TensorObjectState.create(catalog, [[1]], max_objects=4)

    battle = BattleState()
    battle.entities.clear()
    area = AreaEffect(
        id=1,
        position=Position(9.0, 14.0),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=91,
        range=3,
        sight_range=3,
        duration=0.15,
        radius=3,
        damage_tick_interval=0.05,
        initial_damage_delay=0.05,
        max_damage_ticks=3,
    )

    all_event_opcodes: list[int] = []
    for _ in range(3):
        area.update(battle.dt, battle)
        result = step_object_phase(state)
        count = int(result.events.count[0])
        all_event_opcodes.extend(result.events.opcode[0, :count].tolist())
        assert int(state.age_ms[0, 0]) == round(area.time_alive * 1000)
        assert int(state.ticks_remaining[0, 0]) == 3 - area.damage_ticks_applied
        assert bool(state.active[0, 0]) == area.is_alive

    assert all_event_opcodes == [
        ObjectEventOpcode.AREA_TICK,
        ObjectEventOpcode.AREA_TICK,
        ObjectEventOpcode.AREA_TICK,
        ObjectEventOpcode.DEATH,
    ]


def test_enabled_goblin_barrel_impact_emits_exact_spawn_count() -> None:
    from clasher.spells import SPELL_REGISTRY

    spell = SPELL_REGISTRY["GoblinBarrel"]
    blueprint = ObjectBlueprint(
        opcode=ObjectOpcode.PROJECTILE_LAUNCH,
        player_id=0,
        x_units=0,
        y_units=0,
        target_x_units=400,
        target_y_units=0,
        speed_units_per_tick=400,
        payload_id=17,
        payload_count=spell.spawn_count,
    )
    state = TensorObjectState.create(
        TensorObjectCatalog.compile([blueprint]), [[1]], max_objects=8
    )

    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 2
    projectile = SpawnProjectile(
        id=1,
        position=Position(0.0, 0.0),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=0,
        sight_range=0,
        target_position=Position(0.4, 0.0),
        travel_speed=8.0,
        splash_radius=0,
        source_name="serialized-carrier",
        spawn_count=spell.spawn_count,
        spawn_character=spell.spawn_character,
        spawn_character_data=spell.spawn_character_data,
        spawn_deploy_delay_override=spell.spawn_deploy_delay,
        spawn_const_priority=spell.spawn_const_priority,
        tracks_target=False,
    )
    battle.entities[1] = projectile

    projectile.update(battle.dt, battle)
    result = step_object_phase(state)

    spawned = [entity for entity in battle.entities.values() if isinstance(entity, Troop)]
    assert len(spawned) == spell.spawn_count
    assert _events(result) == [
        (ObjectEventOpcode.PROJECTILE_IMPACT, 1, spell.spawn_count),
        (ObjectEventOpcode.SPAWN, 1, spell.spawn_count),
        (ObjectEventOpcode.DEATH, 1, spell.spawn_count),
    ]


def test_death_container_appends_and_ticks_child_in_same_frame() -> None:
    area_blueprint = ObjectBlueprint(
        opcode=ObjectOpcode.PERIODIC_AREA,
        duration_ms=1,
        tick_interval_ms=50,
        initial_tick_ms=0,
        max_ticks=1,
        amount=10,
        inherit_terminal_position=True,
        inherit_player=True,
    )
    container_blueprint = ObjectBlueprint(
        opcode=ObjectOpcode.TIMED_PAYLOAD,
        player_id=1,
        x_units=7000,
        y_units=12000,
        activation_delay_ms=50,
        payload_id=23,
        payload_count=1,
        terminal_blueprint=1,
    )
    catalog = TensorObjectCatalog.compile([area_blueprint, container_blueprint])
    state = TensorObjectState.create(catalog, [[2]], max_objects=4)

    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 2
    container = DeathAreaEffectContainer(
        id=1,
        position=Position(7.0, 12.0),
        player_id=1,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=0,
        sight_range=0,
        activation_delay=0.05,
        area_data={
            "name": "SerializedDeathPulse",
            "damage": 10,
            "lifeDuration": 1,
            "radius": 1000,
        },
    )
    battle.entities[1] = container

    battle._run_object_phase(battle.dt, {1}, set())
    result = step_object_phase(state)

    python_child = battle.entities[2]
    assert isinstance(python_child, AreaEffect)
    assert not container.is_alive
    assert not python_child.is_alive
    assert python_child.time_alive == battle.dt
    assert python_child.damage_ticks_applied == 1
    assert result.processed_count.tolist() == [2]
    assert state.object_id[0, :2].tolist() == [1, 2]
    assert state.active[0, :2].tolist() == [False, False]
    assert state.age_ms[0, :2].tolist() == [50, 50]
    assert _events(result) == [
        (ObjectEventOpcode.SPAWN, 1, 1),
        (ObjectEventOpcode.DEATH, 1, 1),
        (ObjectEventOpcode.AREA_TICK, 2, 0),
        (ObjectEventOpcode.DEATH, 2, 0),
    ]


def test_worklist_uses_object_id_order_even_when_slots_are_permuted() -> None:
    first = ObjectBlueprint(
        opcode=ObjectOpcode.PROJECTILE_LAUNCH,
        target_x_units=0,
        target_y_units=0,
        speed_units_per_tick=1,
    )
    second = replace(first, amount=2)
    state = TensorObjectState.create(
        TensorObjectCatalog.compile([first, second]), [[1, 2]], max_objects=4
    )
    for field in (
        "allocated",
        "active",
        "object_id",
        "blueprint_id",
        "opcode",
        "player",
        "x_units",
        "y_units",
        "target_x_units",
        "target_y_units",
        "speed_units_per_tick",
        "launch_delay_ms",
        "activation_delay_ms",
        "age_ms",
        "duration_ms",
        "tick_interval_ms",
        "next_tick_ms",
        "ticks_remaining",
        "amount",
        "payload_id",
        "payload_count",
        "terminal_blueprint",
        "feature_mask",
    ):
        tensor = getattr(state, field)
        tensor[:, [0, 1]] = tensor[:, [1, 0]].clone()

    result = step_object_phase(state)

    assert result.events.source_id[0, :4].tolist() == [1, 1, 2, 2]


def test_unsupported_serialized_area_fails_closed_without_mutation() -> None:
    serialized_area = CardDataLoader().load_card_definitions()["Tornado"].effects[0]
    attraction_area = replace(
        serialized_area,
        attract_percentage=100.0,
        push_speed_factor=100.0,
    )
    blueprint = ObjectBlueprint.from_serialized_effect(
        attraction_area,
        player_id=0,
        position=(9.0, 14.0),
    )
    assert blueprint.feature_mask & UnsupportedObjectFeature.CONTINUOUS_AREA
    state = TensorObjectState.create(
        TensorObjectCatalog.compile([blueprint]), [[1]], max_objects=4
    )
    before = {
        name: value.clone()
        for name, value in vars(state).items()
        if isinstance(value, torch.Tensor)
    }

    result = step_object_phase(state)

    assert result.unsupported_batch.tolist() == [True]
    assert result.processed_count.tolist() == [0]
    assert result.events.count.tolist() == [0]
    for name, expected in before.items():
        assert torch.equal(getattr(state, name), expected), name


def test_supported_and_unsupported_battles_share_one_tensor_batch() -> None:
    supported = ObjectBlueprint(
        opcode=ObjectOpcode.PROJECTILE_LAUNCH,
        target_x_units=0,
        target_y_units=0,
        speed_units_per_tick=1,
    )
    unsupported = replace(
        supported,
        feature_mask=int(UnsupportedObjectFeature.HOMING),
    )
    state = TensorObjectState.create(
        TensorObjectCatalog.compile([supported, unsupported]),
        [[1], [2]],
        max_objects=4,
    )

    result = step_object_phase(state)

    assert result.unsupported_batch.tolist() == [False, True]
    assert result.processed_count.tolist() == [1, 0]
    assert state.active[:, 0].tolist() == [False, True]
    assert result.events.count.tolist() == [2, 0]
