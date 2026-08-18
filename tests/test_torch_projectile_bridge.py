from __future__ import annotations

import copy
import random
from collections.abc import Iterator
from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Projectile, SpawnProjectile, TargetType, Troop
from clasher.mechanics.shared.knockback import apply_radial_knockback
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.combat import CombatStepResult
from clasher.torch_sim.combat_adapter import project_stationary_combat
from clasher.torch_sim.oracle_event_capture import (
    OracleEventRecord,
    OraclePayloadKind,
    PythonOracleEventCapture,
)
from clasher.torch_sim.projectile_bridge import (
    BridgePayloadKind,
    TensorResidentProjectileSpellBridge,
)
from clasher.torch_sim.resident_engine import _resident_deployment_catalog_closure
from clasher.torch_sim.runtime_objects import (
    TensorRuntimeObjectPhase,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable on this host")
    yield device


def _troop(
    battle: BattleState,
    name: str,
    entity_id: int,
    player_id: int,
    position: Position,
    *,
    hp: float = 500,
) -> Troop:
    stats = battle.card_loader.get_card(name)
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
        target_type=TargetType.BOTH,
    )
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.battle_state = battle  # type: ignore[attr-defined]
    return entity


def _battle(*entities: Troop | Building, cards: tuple[str, ...] = ()) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities = {entity.id: entity for entity in entities}
    battle.next_entity_id = max((entity.id for entity in entities), default=0) + 1
    for entity in entities:
        entity.battle_state = battle  # type: ignore[attr-defined]
    if cards:
        hand: list[str | None] = list(cards[:4])
        hand.extend([None] * (4 - len(hand)))
        for player in battle.players:
            player.deck = list(cards)
            player.hand = hand.copy()
            player.cycle_queue.clear()
    return battle


def _runtime_bridge(
    battles: list[BattleState],
    names: set[str],
    *,
    device: str = "cpu",
    max_entities: int = 16,
    max_objects: int = 16,
    event_capacity: int = 256,
) -> tuple[
    TensorBattleRuntime,
    TensorRuntimeObjectPhase,
    TensorResidentProjectileSpellBridge,
    TensorCardCatalog,
]:
    catalog_loader, closure = _resident_deployment_catalog_closure(
        battles[0].card_loader, names
    )
    catalog = TensorCardCatalog.compile(catalog_loader, closure, device=device)
    runtime = TensorBattleRuntime.from_battles(
        battles,
        device=device,
        max_entities=max_entities,
        event_capacity=event_capacity,
        catalog=catalog,
    )
    objects = TensorRuntimeObjectPhase.from_battles(
        runtime, battles, max_objects=max_objects
    )
    bridge = TensorResidentProjectileSpellBridge.from_battles(runtime, objects, battles)
    return runtime, objects, bridge, catalog


def _oracle_object_tick(battle: BattleState) -> None:
    ids = set(battle.entities)
    battle._defer_projectile_impacts = True
    battle._run_object_phase(battle.dt, ids, ids)
    battle._defer_projectile_impacts = False
    battle._resolve_pending_projectile_impacts()
    battle._cleanup_dead_entities()


def _tensor_event_tuples(
    runtime: TensorBattleRuntime, start: int = 0
) -> list[tuple[int, int, int, int, int, int, float, int]]:
    return [
        (
            int(runtime.events.phase[0, slot].item()),
            int(runtime.events.opcode[0, slot].item()),
            int(runtime.events.source_id[0, slot].item()),
            int(runtime.events.target_id[0, slot].item()),
            int(runtime.events.x_units[0, slot].item()),
            int(runtime.events.y_units[0, slot].item()),
            float(runtime.events.amount[0, slot].item()),
            int(runtime.events.payload[0, slot].item()),
        )
        for slot in range(start, int(runtime.events.count[0].item()))
    ]


def _oracle_event_tuples(
    events: list[OracleEventRecord], runtime: TensorBattleRuntime
) -> list[tuple[int, int, int, int, int, int, float, int]]:
    return [
        (
            event.phase,
            event.opcode,
            event.source_id,
            event.target_id,
            event.x_units,
            event.y_units,
            float(event.amount),
            runtime.battle.card_to_id[str(event.payload)],
        )
        for event in events
    ]


def test_serialized_payload_catalog_classifies_enabled_families_without_names() -> None:
    seed = BattleState(fast_path=False)
    target = _troop(seed, "Knight", 1, 1, Position(9, 14))
    cards = (
        "Archer",
        "Zap",
        "Fireball",
        "Arrows",
        "GoblinBarrel",
        "GlobalLightning",
    )
    battle = _battle(target, cards=cards)
    runtime, _, bridge, _ = _runtime_bridge([battle], {"Knight", *cards})

    expected = {
        "Archer": (BridgePayloadKind.COMBAT_PROJECTILE, True),
        "Zap": (BridgePayloadKind.DIRECT_SPELL, True),
        "Fireball": (BridgePayloadKind.PROJECTILE_SPELL, True),
        "Arrows": (BridgePayloadKind.PROJECTILE_SPELL, True),
        "GoblinBarrel": (BridgePayloadKind.SPAWN_PROJECTILE, True),
        "GlobalLightning": (BridgePayloadKind.AREA_SPELL, True),
    }
    for name, (kind, supported) in expected.items():
        card_id = runtime.battle.card_to_id[name]
        assert int(bridge.catalog.kind[card_id].item()) == int(kind)
        assert bool(bridge.catalog.supported[card_id].item()) is supported


def test_combat_projectile_launch_travel_homing_and_impact_match_python(
    tensor_device: str,
) -> None:
    seed = BattleState(fast_path=False)
    archer = _troop(seed, "Archer", 1, 0, Position(9, 10), hp=300)
    target = _troop(seed, "Knight", 2, 1, Position(9, 12), hp=500)
    archer.target_id = target.id
    battle = _battle(archer, target)
    oracle = copy.deepcopy(battle)
    runtime, objects, bridge, catalog = _runtime_bridge(
        [battle], {"Archer", "Knight"}, device=tensor_device
    )
    combat = project_stationary_combat(
        [battle], catalog, capacity=runtime.max_entities, device=tensor_device
    ).state
    source_slot = int(torch.where(combat.entity_id[0] == 1)[0][0].item())
    target_slot = int(torch.where(combat.entity_id[0] == 2)[0][0].item())
    combat.target_slot[0, source_slot] = target_slot
    launched = torch.zeros_like(combat.present)
    launched[0, source_slot] = True
    combat_result = CombatStepResult(
        attacked=launched.clone(),
        projectile_launched=launched,
        damage_received=torch.zeros_like(combat.hp),
        target_before=combat.target_slot.clone(),
        target_after=combat.target_slot.clone(),
    )

    oracle_archer = oracle.entities[1]
    oracle_target = oracle.entities[2]
    assert isinstance(oracle_archer, Troop)
    oracle_archer._create_projectile(oracle_target, oracle)
    oracle_projectile = oracle.entities[3]
    assert isinstance(oracle_projectile, Projectile)
    supported = bridge.materialize_combat_launches_(
        runtime, objects, combat, combat_result
    )

    assert supported.tolist() == [True]
    assert runtime.entity_pool.next_entity_id.tolist() == [4]
    assert objects.objects.object_id[0, 0].item() == 3
    assert objects.objects.x_units[0, 0].item() == round(
        oracle_projectile.position.x * 1_000
    )
    assert objects.objects.y_units[0, 0].item() == round(
        oracle_projectile.position.y * 1_000
    )
    assert objects.objects.speed_units_per_tick[0, 0].item() == round(
        oracle_projectile.travel_speed * 1_000 / 20
    )
    projectile_slot = int(
        torch.where(runtime.battle.entity_id[0] == oracle_projectile.id)[0][0].item()
    )
    assert bool(runtime.battle.entity_hp_integer_kind[0, projectile_slot].item())
    assert runtime.phases.target_slot[0, projectile_slot].item() == -1

    for tick in range(8):
        if tick == 1:
            oracle.entities[2].position.y += 0.2
            runtime.battle.entity_y_units[0, target_slot] += 200
        _oracle_object_tick(oracle)
        bridge.step_objects_(runtime, objects)
        if 3 not in oracle.entities:
            break
        oracle_projectile = oracle.entities[3]
        assert isinstance(oracle_projectile, Projectile)
        assert objects.objects.x_units[0, 0].item() == round(
            oracle_projectile.position.x * 1_000
        )
        assert objects.objects.y_units[0, 0].item() == round(
            oracle_projectile.position.y * 1_000
        )
    assert bool(runtime.battle.entity_hp_integer_kind[0, target_slot].item()) is (
        type(oracle.entities[2].hitpoints) is int
    )

    assert 3 not in oracle.entities
    assert not objects.objects.allocated.any()
    assert (
        runtime.battle.entity_hp[0, target_slot].item() == oracle.entities[2].hitpoints
    )


@pytest.mark.parametrize(
    ("source_name", "building_source"),
    (
        ("BabyDragon", False),
        ("Bomber", False),
        ("Princess", False),
        ("SpearGoblins", False),
        ("MegaMinion", False),
        ("Minions", False),
        ("Xbow", True),
    ),
)
def test_combat_projectile_public_events_match_scalar_callsite_lifecycle(
    tensor_device: str,
    source_name: str,
    building_source: bool,
) -> None:
    seed = BattleState(fast_path=False)
    if building_source:
        seed.entities.clear()
        seed.next_entity_id = 1
        stats = seed.card_loader.get_card(source_name)
        assert stats is not None
        source = seed._spawn_entity(Building, Position(9, 10), 0, stats)
        source.deploy_delay_remaining = 0.0
        source.placement_pending = False
        source._spawn_hook_pending = False
        source._spawn_hook_fired = True
    else:
        source = _troop(seed, source_name, 1, 0, Position(9, 10), hp=300)
    target = _troop(seed, "Knight", 2, 1, Position(9, 12), hp=50)
    source.target_id = target.id
    battle = _battle(source, target)
    oracle = copy.deepcopy(battle)
    runtime, objects, bridge, catalog = _runtime_bridge(
        [battle],
        {source_name, "Knight"},
        device=tensor_device,
    )

    with PythonOracleEventCapture(oracle) as capture:
        oracle_source = oracle.entities[source.id]
        with capture._scope(
            phase=TickPhase.COMBAT,
            source_id=source.id,
            source_payload=source_name,
        ):
            oracle_source._create_projectile(oracle.entities[target.id], oracle)
        assert capture.events[0].payload_kind == OraclePayloadKind.COMBAT_PROJECTILE

        combat = project_stationary_combat(
            [battle], catalog, capacity=runtime.max_entities, device=tensor_device
        ).state
        source_slot = int(torch.where(combat.entity_id[0] == source.id)[0][0].item())
        target_slot = int(torch.where(combat.entity_id[0] == target.id)[0][0].item())
        combat.target_slot[0, source_slot] = target_slot
        launched = torch.zeros_like(combat.present)
        launched[0, source_slot] = True
        combat_result = CombatStepResult(
            attacked=launched.clone(),
            projectile_launched=launched,
            damage_received=torch.zeros_like(combat.hp),
            target_before=combat.target_slot.clone(),
            target_after=combat.target_slot.clone(),
        )
        assert bridge.materialize_combat_launches_(
            runtime, objects, combat, combat_result
        ).all()
        assert _tensor_event_tuples(runtime) == _oracle_event_tuples(
            capture.events, runtime
        )

        oracle_event_start = len(capture.events)
        for _ in range(30):
            tensor_event_start = int(runtime.events.count[0].item())
            _oracle_object_tick(oracle)
            result = bridge.step_objects_(runtime, objects)
            assert result.supported_batch.tolist() == [True]
            expected = capture.events[oracle_event_start:]
            actual = _tensor_event_tuples(runtime, tensor_event_start)
            assert actual == _oracle_event_tuples(expected, runtime)
            if expected:
                assert expected[0].payload_kind == OraclePayloadKind.PROJECTILE_IMPACT
                assert expected[1].payload_kind == OraclePayloadKind.DAMAGE
                if len(expected) == 3:
                    assert expected[2].payload_kind == OraclePayloadKind.DEATH
            oracle_event_start = len(capture.events)
            oracle_projectiles = [
                entity
                for entity in oracle.entities.values()
                if isinstance(entity, Projectile)
            ]
            if not oracle_projectiles:
                assert not objects.objects.allocated.any()
                break
        else:
            raise AssertionError("combat projectile did not complete")

    if target.id in oracle.entities:
        expected_hp = oracle.entities[target.id].hitpoints
        assert runtime.battle.entity_hp[0, target_slot].item() == expected_hp
    else:
        assert target.id not in runtime.battle.entity_id[0].tolist()


def test_combat_projectile_events_preserve_prior_building_lifetime_phase(
    tensor_device: str,
) -> None:
    seed = BattleState(fast_path=False)
    seed.entities.clear()
    seed.next_entity_id = 1
    stats = seed.card_loader.get_card("Xbow")
    assert stats is not None
    source = seed._spawn_entity(Building, Position(9, 10), 0, stats)
    source.deploy_delay_remaining = 0.0
    source.placement_pending = False
    target = _troop(seed, "Knight", 2, 1, Position(9, 12), hp=500)
    battle = _battle(source, target)
    runtime, objects, bridge, catalog = _runtime_bridge(
        [battle], {"Xbow", "Knight"}, device=tensor_device
    )
    combat = project_stationary_combat(
        [battle], catalog, capacity=runtime.max_entities, device=tensor_device
    ).state
    source_slot = int(torch.where(combat.entity_id[0] == source.id)[0][0].item())
    target_slot = int(torch.where(combat.entity_id[0] == target.id)[0][0].item())
    combat.target_slot[0, source_slot] = target_slot
    launched = torch.zeros_like(combat.present)
    launched[0, source_slot] = True
    result = CombatStepResult(
        attacked=launched.clone(),
        projectile_launched=launched,
        damage_received=torch.zeros_like(combat.hp),
        target_before=combat.target_slot.clone(),
        target_after=combat.target_slot.clone(),
    )
    assert bridge.materialize_combat_launches_(runtime, objects, combat, result).all()
    runtime.events.append(
        phase=TickPhase.BUILDING_LIFETIME,
        opcode=RuntimeEventOpcode.DAMAGE,
        valid=torch.ones((1, 1), dtype=torch.bool, device=runtime.device),
        target_id=source.id,
        x_units=9_000,
        y_units=10_000,
        amount=1.0,
    )

    bridge.step_objects_(runtime, objects)

    assert runtime.events.phase[0, :4].tolist() == [
        TickPhase.COMBAT,
        TickPhase.BUILDING_LIFETIME,
        TickPhase.OBJECTS,
        TickPhase.OBJECTS,
    ]
    assert runtime.events.opcode[0, :4].tolist() == [
        RuntimeEventOpcode.PROJECTILE,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.PROJECTILE,
        RuntimeEventOpcode.DAMAGE,
    ]


def test_simultaneous_combat_projectiles_preserve_source_order_and_applied_amounts(
    tensor_device: str,
) -> None:
    seed = BattleState(fast_path=False)
    first = _troop(seed, "SpearGoblins", 1, 0, Position(8.8, 10), hp=300)
    second = _troop(seed, "SpearGoblins", 2, 0, Position(9.2, 10), hp=300)
    target = _troop(seed, "Knight", 3, 1, Position(9, 12), hp=100)
    battle = _battle(first, second, target)
    oracle = copy.deepcopy(battle)
    runtime, objects, bridge, catalog = _runtime_bridge(
        [battle], {"SpearGoblins", "Knight"}, device=tensor_device
    )

    with PythonOracleEventCapture(oracle) as capture:
        for source_id in (first.id, second.id):
            with capture._scope(
                phase=TickPhase.COMBAT,
                source_id=source_id,
                source_payload="SpearGoblins",
            ):
                oracle.entities[source_id]._create_projectile(
                    oracle.entities[target.id], oracle
                )
        combat = project_stationary_combat(
            [battle], catalog, capacity=runtime.max_entities, device=tensor_device
        ).state
        target_slot = int(torch.where(combat.entity_id[0] == target.id)[0][0].item())
        launched = torch.zeros_like(combat.present)
        for source_id in (first.id, second.id):
            source_slot = int(
                torch.where(combat.entity_id[0] == source_id)[0][0].item()
            )
            combat.target_slot[0, source_slot] = target_slot
            launched[0, source_slot] = True
        result = CombatStepResult(
            attacked=launched.clone(),
            projectile_launched=launched,
            damage_received=torch.zeros_like(combat.hp),
            target_before=combat.target_slot.clone(),
            target_after=combat.target_slot.clone(),
        )
        assert bridge.materialize_combat_launches_(
            runtime, objects, combat, result
        ).all()
        assert _tensor_event_tuples(runtime) == _oracle_event_tuples(
            capture.events, runtime
        )

        oracle_event_start = len(capture.events)
        for _ in range(10):
            tensor_event_start = int(runtime.events.count[0].item())
            _oracle_object_tick(oracle)
            bridge.step_objects_(runtime, objects)
            expected = capture.events[oracle_event_start:]
            assert _tensor_event_tuples(
                runtime, tensor_event_start
            ) == _oracle_event_tuples(expected, runtime)
            oracle_event_start = len(capture.events)
            if not objects.objects.allocated.any():
                break

    damage = runtime.events.opcode[0] == RuntimeEventOpcode.DAMAGE
    assert runtime.events.source_id[0, damage].tolist() == [4, 5]
    assert runtime.events.amount[0, damage].tolist() == [81.0, 19.0]


def test_zap_direct_spell_damage_stun_identity_and_events_match_python() -> None:
    seed = BattleState(fast_path=False)
    target = _troop(seed, "Knight", 1, 1, Position(9, 14), hp=500)
    battle = _battle(target, cards=("Zap", "Knight"))
    oracle = copy.deepcopy(battle)
    runtime, objects, bridge, _ = _runtime_bridge([battle], {"Zap", "Knight"})
    card_id = runtime.battle.card_to_id["Zap"]
    before_next = runtime.entity_pool.next_entity_id.clone()

    assert SPELL_REGISTRY["Zap"].cast(oracle, 0, Position(9, 14))
    supported = bridge.materialize_spell_actions_(
        runtime,
        objects,
        card_ids=torch.tensor([card_id]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    )

    assert supported.tolist() == [True]
    assert runtime.battle.entity_hp[0, 0].item() == oracle.entities[1].hitpoints
    assert not runtime.battle.entity_hp_integer_kind[0, 0].item()
    assert runtime.status.stun_timer[0, 0].item() == oracle.entities[1].stun_timer
    assert torch.equal(runtime.entity_pool.next_entity_id, before_next)
    assert not objects.objects.allocated.any()
    assert runtime.events.opcode[0, : runtime.events.count[0]].tolist() == [2]
    assert runtime.events.phase[0, 0].item() == TickPhase.COMBAT
    assert runtime.events.payload[0, 0].item() == 0


def test_target_death_before_projectile_impact_preserves_committed_endpoint() -> None:
    seed = BattleState(fast_path=False)
    archer = _troop(seed, "Archer", 1, 0, Position(9, 10), hp=300)
    target = _troop(seed, "Knight", 2, 1, Position(9, 12), hp=100)
    archer.target_id = target.id
    battle = _battle(archer, target)
    oracle = copy.deepcopy(battle)
    runtime, objects, bridge, catalog = _runtime_bridge([battle], {"Archer", "Knight"})
    combat = project_stationary_combat([battle], catalog, capacity=8).state
    source_slot = int(torch.where(combat.entity_id[0] == 1)[0][0].item())
    target_slot = int(torch.where(combat.entity_id[0] == 2)[0][0].item())
    combat.target_slot[0, source_slot] = target_slot
    launched = torch.zeros_like(combat.present)
    launched[0, source_slot] = True
    result = CombatStepResult(
        attacked=launched,
        projectile_launched=launched,
        damage_received=torch.zeros_like(combat.hp),
        target_before=combat.target_slot.clone(),
        target_after=combat.target_slot.clone(),
    )
    oracle_archer = oracle.entities[1]
    assert isinstance(oracle_archer, Troop)
    oracle_archer._create_projectile(oracle.entities[2], oracle)
    assert bridge.materialize_combat_launches_(runtime, objects, combat, result).all()

    oracle.entities[2].is_alive = False
    oracle._cleanup_dead_entities()
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, target_slot] = True
    runtime.battle.entity_active[0, target_slot] = False
    runtime.entity_pool.cleanup(dead)

    for _ in range(8):
        _oracle_object_tick(oracle)
        bridge.step_objects_(runtime, objects)
        if not objects.objects.allocated.any():
            break

    assert set(oracle.entities) == {1}
    assert runtime.battle.entity_id[0].nonzero().numel() == 1
    assert runtime.events.opcode[0, : runtime.events.count[0]].tolist() == [
        RuntimeEventOpcode.PROJECTILE,
        RuntimeEventOpcode.PROJECTILE,
    ]
    assert runtime.events.phase[0, : runtime.events.count[0]].tolist() == [
        TickPhase.COMBAT,
        TickPhase.OBJECTS,
    ]
    assert runtime.events.source_id[0, : runtime.events.count[0]].tolist() == [1, 3]
    assert runtime.events.target_id[0, : runtime.events.count[0]].tolist() == [3, 0]


def test_simultaneous_launch_allocation_uses_entity_ids_not_physical_slots() -> None:
    seed = BattleState(fast_path=False)
    first = _troop(seed, "Archer", 10, 0, Position(8, 10))
    second = _troop(seed, "Archer", 20, 0, Position(10, 10))
    target = _troop(seed, "Knight", 30, 1, Position(9, 12))
    battle = _battle(first, second, target)
    battle.next_entity_id = 31
    runtime, objects, bridge, catalog = _runtime_bridge([battle], {"Archer", "Knight"})
    combat = project_stationary_combat([battle], catalog, capacity=8).state
    # Permute every combat plane while leaving runtime physical slots intact.
    for descriptor in fields(combat):
        value = getattr(combat, descriptor.name)
        value[:, [0, 1]] = value[:, [1, 0]].clone()
    target_slot = int(torch.where(combat.entity_id[0] == 30)[0][0].item())
    combat.target_slot[0, :2] = target_slot
    launched = torch.zeros_like(combat.present)
    launched[0, :2] = True
    result = CombatStepResult(
        attacked=launched,
        projectile_launched=launched,
        damage_received=torch.zeros_like(combat.hp),
        target_before=combat.target_slot.clone(),
        target_after=combat.target_slot.clone(),
    )

    supported = bridge.materialize_combat_launches_(runtime, objects, combat, result)

    assert supported.tolist() == [True]
    assert objects.objects.object_id[0, :2].tolist() == [31, 32]
    # ID 10 is now physical combat slot 1, so its x=8000 launch owns ID 31.
    first_muzzle = first._projectile_launch_geometry(target)[0]
    second_muzzle = second._projectile_launch_geometry(target)[0]
    assert objects.objects.x_units[0, :2].tolist() == [
        round(first_muzzle.x * 1_000),
        round(second_muzzle.x * 1_000),
    ]


def test_pure_area_spell_lifecycle_and_first_damage_match_python() -> None:
    seed = BattleState(fast_path=False)
    target = _troop(seed, "Knight", 1, 1, Position(9, 14), hp=500)
    battle = _battle(target, cards=("GlobalLightning", "Knight"))
    oracle = copy.deepcopy(battle)
    runtime, objects, bridge, _ = _runtime_bridge(
        [battle], {"GlobalLightning", "Knight"}, max_objects=4
    )
    card_id = runtime.battle.card_to_id["GlobalLightning"]

    assert SPELL_REGISTRY["GlobalLightning"].cast(oracle, 0, Position(9, 14))
    supported = bridge.materialize_spell_actions_(
        runtime,
        objects,
        card_ids=torch.tensor([card_id]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    )
    assert supported.tolist() == [True]
    assert runtime.entity_pool.next_entity_id.tolist() == [3]

    for tick in range(100):
        _oracle_object_tick(oracle)
        result = bridge.step_objects_(runtime, objects)
        assert result.supported_batch.tolist() == [True]
        if tick == 0:
            assert runtime.battle.entity_hp[0, 0].item() == oracle.entities[1].hitpoints

    assert set(oracle.entities) == {1}
    assert not objects.objects.allocated.any()
    assert runtime.battle.entity_id[0, :2].tolist() == [1, 0]


def test_simple_projectile_spell_launch_and_lifecycle_match_python(
    tensor_device: str,
) -> None:
    seed = BattleState(fast_path=False)
    target = _troop(seed, "Knight", 1, 1, Position(9, 14), hp=500)
    battle = _battle(target, cards=("GoblinPartyRocket", "Knight"))
    oracle = copy.deepcopy(battle)
    runtime, objects, bridge, _ = _runtime_bridge(
        [battle],
        {"GoblinPartyRocket", "Knight"},
        device=tensor_device,
        max_objects=4,
    )
    card_id = runtime.battle.card_to_id["GoblinPartyRocket"]

    assert SPELL_REGISTRY["GoblinPartyRocket"].cast(oracle, 0, Position(9, 14))
    python_projectile = oracle.entities[2]
    assert isinstance(python_projectile, Projectile)
    supported = bridge.materialize_spell_actions_(
        runtime,
        objects,
        card_ids=torch.tensor([card_id], device=runtime.device),
        player_ids=torch.tensor([0], device=runtime.device),
        target_x_units=torch.tensor([9_000], device=runtime.device),
        target_y_units=torch.tensor([14_000], device=runtime.device),
        valid=torch.tensor([True], device=runtime.device),
    )

    assert supported.tolist() == [True]
    assert objects.objects.x_units[0, 0].item() == round(
        python_projectile.position.x * 1_000
    )
    assert objects.objects.y_units[0, 0].item() == round(
        python_projectile.position.y * 1_000
    )
    assert runtime.entity_pool.next_entity_id.tolist() == [3]

    for _ in range(40):
        _oracle_object_tick(oracle)
        bridge.step_objects_(runtime, objects)
        if not objects.objects.allocated.any():
            break
    assert set(oracle.entities) == {1}
    assert not objects.objects.allocated.any()
    assert runtime.battle.entity_hp[0, 0].item() == oracle.entities[1].hitpoints


@pytest.mark.parametrize("spell_name", ["Fireball", "Snowball"])
def test_projectile_spell_knockback_and_slow_handoffs_match_python(
    spell_name: str,
) -> None:
    seed = BattleState(fast_path=False)
    target = _troop(seed, "Knight", 1, 1, Position(9.5, 14), hp=2_000)
    battle = _battle(target, cards=(spell_name, "Knight"))
    oracle = copy.deepcopy(battle)
    runtime, objects, bridge, _ = _runtime_bridge(
        [battle], {spell_name, "Knight"}, max_objects=4
    )
    card_id = runtime.battle.card_to_id[spell_name]
    spell = SPELL_REGISTRY[spell_name]
    assert spell.cast(oracle, 0, Position(9, 14))
    supported = bridge.materialize_spell_actions_(
        runtime,
        objects,
        card_ids=torch.tensor([card_id]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    )
    assert supported.tolist() == [True]

    for _ in range(80):
        _oracle_object_tick(oracle)
        bridge.step_objects_(runtime, objects)
        if not objects.objects.allocated.any():
            break

    oracle_target = oracle.entities[1]
    assert runtime.battle.entity_hp[0, 0].item() == oracle_target.hitpoints
    assert oracle_target._knockback_target is not None
    assert bridge.knockback_active[0, 0].item() is True
    assert bridge.knockback_target_units[0, 0].tolist() == [
        round(oracle_target._knockback_target.x * 1_000),
        round(oracle_target._knockback_target.y * 1_000),
    ]
    assert (
        bridge.knockback_velocity_work[0, 0].item()
        == oracle_target._knockback_velocity_work
    )
    if spell_name == "Snowball":
        assert runtime.status.slow_timer[0, 0].item() == oracle_target.slow_timer
        assert (
            runtime.status.slow_multiplier[0, 0].item() == oracle_target.slow_multiplier
        )


def test_reused_low_slot_uses_new_card_knockback_immunity() -> None:
    seed = BattleState(fast_path=False)
    target = _troop(seed, "Knight", 1, 1, Position(9.5, 14), hp=2_000)
    battle = _battle(target, cards=("Fireball", "Knight", "Golem"))
    runtime, objects, bridge, _ = _runtime_bridge(
        [battle], {"Fireball", "Knight", "Golem"}, max_objects=4
    )
    bridge.knockback_active[0, 0] = True
    bridge.knockback_entity_id[0, 0] = 1
    bridge.knockback_velocity_work[0, 0] = 100
    # Reuse physical slot zero for a newly deployed knockback-immune Golem.
    runtime.battle.entity_id[0, 0] = 2
    runtime.entity_pool.active[0, 0] = True
    runtime.battle.entity_active[0, 0] = True
    runtime.battle.entity_card[0, 0] = runtime.battle.card_to_id["Golem"]
    runtime.battle.entity_hp[0, 0] = 5_000
    runtime.battle.entity_max_hp[0, 0] = 5_000
    runtime.entity_pool.next_entity_id[0] = 3
    objects.objects.next_object_id[0] = 3
    card_id = runtime.battle.card_to_id["Fireball"]
    assert bridge.materialize_spell_actions_(
        runtime,
        objects,
        card_ids=torch.tensor([card_id]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    ).all()
    for _ in range(80):
        bridge.step_objects_(runtime, objects)
        if not objects.objects.allocated.any():
            break
    assert (
        bridge.catalog.card_knockback_immune[runtime.battle.card_to_id["Golem"]].item()
        is True
    )
    assert bridge.knockback_active[0, 0].item() is False
    assert bridge.knockback_entity_id[0, 0].item() == 0


def test_randomized_radial_knockback_geometry_and_motion_match_python(
    tensor_device: str,
) -> None:
    rng = random.Random(5_820_441)
    target_names = (
        "Skeletons",
        "Archer",
        "MiniPekka",
        "Knight",
        "Giant",
        "Pekka",
        "Golem",
    )
    distance_boundaries = (
        0,
        1,
        24,
        25,
        249,
        250,
        251,
        999,
        1_000,
        1_001,
        1_799,
        1_800,
        2_500,
        9_999,
        10_000,
        10_001,
    )
    fallback_vectors = (
        (0, 0),
        (1, 0),
        (0, 1),
        (-1, 0),
        (0, -1),
        (1, 1),
        (-1, 1),
        (7_999, -8_000),
    )
    specifications: list[tuple[str, int, int, int, int, bool, bool]] = []
    for mass_index, target_name in enumerate(target_names):
        for distance_index, distance in enumerate(distance_boundaries):
            exact_center = (mass_index + distance_index) % 2 == 0
            fallback_x, fallback_y = fallback_vectors[
                (mass_index * len(distance_boundaries) + distance_index)
                % len(fallback_vectors)
            ]
            specifications.append(
                (
                    target_name,
                    distance,
                    fallback_x,
                    fallback_y,
                    distance_index,
                    exact_center,
                    (mass_index + distance_index) % 3 == 0,
                )
            )
    for index in range(64):
        specifications.append(
            (
                rng.choice(target_names),
                rng.randrange(0, 12_001),
                rng.randrange(-32_000, 32_001),
                rng.randrange(-32_000, 32_001),
                index,
                bool(rng.randrange(2)),
                bool(rng.randrange(2)),
            )
        )

    cases: list[tuple[BattleState, Troop, int, int, int, int, int, bool]] = []
    for index, (
        target_name,
        distance,
        fallback_x,
        fallback_y,
        coordinate_seed,
        exact_center,
        ignores_mass,
    ) in enumerate(specifications):
        seed = BattleState(fast_path=False)
        x_units = 2_000 + (coordinate_seed * 7_919 + index * 101) % 14_000
        y_units = 4_000 + (coordinate_seed * 4_051 + index * 211) % 24_000
        player_id = index % 2
        target = _troop(
            seed,
            target_name,
            1,
            player_id,
            Position(x_units / 1_000, y_units / 1_000),
            hp=2_000,
        )
        battle = _battle(target, cards=("Fireball", target_name))
        if exact_center:
            center_x, center_y = x_units, y_units
        else:
            center_x = x_units + ((index * 577) % 3_001) - 1_500
            center_y = y_units + ((index * 997) % 3_001) - 1_500
            if center_x == x_units and center_y == y_units:
                center_x += 1
        cases.append(
            (
                battle,
                target,
                center_x,
                center_y,
                fallback_x,
                fallback_y,
                distance,
                ignores_mass,
            )
        )

    battles = [case[0] for case in cases]
    runtime, _, bridge, _ = _runtime_bridge(
        battles,
        {"Fireball", *target_names},
        device=tensor_device,
        max_entities=4,
        max_objects=2,
    )
    device = runtime.device
    center_x_tensor = torch.tensor([case[2] for case in cases], device=device)
    center_y_tensor = torch.tensor([case[3] for case in cases], device=device)
    fallback_x_tensor = torch.tensor([case[4] for case in cases], device=device)
    fallback_y_tensor = torch.tensor([case[5] for case in cases], device=device)
    distance_tensor = torch.tensor([case[6] for case in cases], device=device)
    ignores_mass_tensor = torch.tensor(
        [case[7] for case in cases], dtype=torch.bool, device=device
    )
    bridge._install_knockback_(
        runtime,
        target_mask=torch.ones_like(runtime.entity_pool.active),
        center_x=center_x_tensor,
        center_y=center_y_tensor,
        fallback_x=fallback_x_tensor,
        fallback_y=fallback_y_tensor,
        distance_units=distance_tensor,
        ignores_mass=ignores_mass_tensor,
    )
    applied: list[bool] = []
    for battle, target, cx, cy, fx, fy, distance_units, ignores_mass in cases:
        applied.append(
            apply_radial_knockback(
                target,
                battle,
                Position(cx / 1_000, cy / 1_000),
                distance_units / 1_000,
                source_kind="randomized",
                ignores_mass=ignores_mass,
                fallback_direction=(fx / 1_000, fy / 1_000),
            )
        )

    for row, (_, target, *_rest) in enumerate(cases):
        assert bridge.knockback_active[row, 0].item() is applied[row]
        if not applied[row]:
            assert target._knockback_target is None
            continue
        assert target._knockback_target is not None
        assert bridge.knockback_target_units[row, 0].tolist() == [
            round(target._knockback_target.x * 1_000),
            round(target._knockback_target.y * 1_000),
        ]
        assert (
            bridge.knockback_velocity_work[row, 0].item()
            == target._knockback_velocity_work
        )

    for _ in range(32):
        start = bridge.knockback_active.clone()
        bridge._advance_knockback_(runtime, start)
        for applied_row, (battle, target, *_rest) in zip(applied, cases, strict=True):
            if applied_row:
                target._update_knockback_movement(battle)
        for row, (_, target, *_rest) in enumerate(cases):
            assert runtime.battle.entity_x_units[row, 0].item() == round(
                target.position.x * 1_000
            )
            assert runtime.battle.entity_y_units[row, 0].item() == round(
                target.position.y * 1_000
            )
            assert (
                bridge.knockback_velocity_work[row, 0].item()
                == target._knockback_velocity_work
            )
            assert bridge.knockback_active[row, 0].item() is (
                target._knockback_target is not None
            )


def test_active_knockback_slot_reuse_installs_exact_new_entity_lifecycle(
    tensor_device: str,
) -> None:
    seed = BattleState(fast_path=False)
    old_target = _troop(seed, "Knight", 1, 1, Position(9.5, 14.5), hp=2_000)
    battle = _battle(old_target, cards=("Fireball", "Knight", "Archer"))
    runtime, _, bridge, _ = _runtime_bridge(
        [battle],
        {"Fireball", "Knight", "Archer"},
        device=tensor_device,
        max_entities=4,
        max_objects=2,
    )
    bridge._install_knockback_(
        runtime,
        target_mask=torch.tensor([[True, False, False, False]], device=runtime.device),
        center_x=torch.tensor([9_500], device=runtime.device),
        center_y=torch.tensor([14_500], device=runtime.device),
        fallback_x=torch.tensor([81], device=runtime.device),
        fallback_y=torch.tensor([1_799], device=runtime.device),
        distance_units=torch.tensor([1_800], device=runtime.device),
        ignores_mass=torch.tensor([False], device=runtime.device),
    )
    assert bridge.knockback_entity_id[0, 0].item() == 1

    oracle_seed = BattleState(fast_path=False)
    new_target = _troop(oracle_seed, "Archer", 2, 0, Position(8.25, 13.75), hp=2_000)
    oracle = _battle(new_target, cards=("Fireball", "Knight", "Archer"))
    runtime.battle.entity_id[0, 0] = 2
    runtime.entity_pool.active[0, 0] = True
    runtime.battle.entity_active[0, 0] = True
    runtime.battle.entity_card[0, 0] = runtime.battle.card_to_id["Archer"]
    runtime.battle.entity_player[0, 0] = 0
    runtime.battle.entity_x_units[0, 0] = 8_250
    runtime.battle.entity_y_units[0, 0] = 13_750
    bridge._install_knockback_(
        runtime,
        target_mask=torch.tensor([[True, False, False, False]], device=runtime.device),
        center_x=torch.tensor([8_000], device=runtime.device),
        center_y=torch.tensor([13_000], device=runtime.device),
        fallback_x=torch.tensor([-5_000], device=runtime.device),
        fallback_y=torch.tensor([7_000], device=runtime.device),
        distance_units=torch.tensor([2_500], device=runtime.device),
        ignores_mass=torch.tensor([False], device=runtime.device),
    )
    assert apply_radial_knockback(
        new_target,
        oracle,
        Position(8, 13),
        2.5,
        source_kind="slot-reuse",
        fallback_direction=(-5, 7),
    )
    assert bridge.knockback_entity_id[0, 0].item() == 2
    assert new_target._knockback_target is not None
    assert bridge.knockback_target_units[0, 0].tolist() == [
        round(new_target._knockback_target.x * 1_000),
        round(new_target._knockback_target.y * 1_000),
    ]

    for _ in range(32):
        start = bridge.knockback_active.clone()
        bridge._advance_knockback_(runtime, start)
        new_target._update_knockback_movement(oracle)
        assert runtime.battle.entity_x_units[0, 0].item() == round(
            new_target.position.x * 1_000
        )
        assert runtime.battle.entity_y_units[0, 0].item() == round(
            new_target.position.y * 1_000
        )
        assert bridge.knockback_active[0, 0].item() is (
            new_target._knockback_target is not None
        )


def test_arrows_grouped_waves_positions_rng_damage_and_lifecycle_match_python(
    tensor_device: str,
) -> None:
    seed = BattleState(fast_path=False)
    first = _troop(seed, "Knight", 1, 1, Position(9, 14), hp=2_000)
    second = _troop(seed, "Knight", 2, 1, Position(10, 14), hp=2_000)
    battle = _battle(first, second, cards=("Arrows", "Knight"))
    oracle = copy.deepcopy(battle)
    runtime, objects, bridge, _ = _runtime_bridge(
        [battle],
        {"Arrows", "Knight"},
        device=tensor_device,
        max_entities=64,
        max_objects=40,
        event_capacity=4_096,
    )
    card_id = runtime.battle.card_to_id["Arrows"]

    assert SPELL_REGISTRY["Arrows"].cast(oracle, 0, Position(9, 14))
    supported = bridge.materialize_spell_actions_(
        runtime,
        objects,
        card_ids=torch.tensor([card_id], device=runtime.device),
        player_ids=torch.tensor([0], device=runtime.device),
        target_x_units=torch.tensor([9_000], device=runtime.device),
        target_y_units=torch.tensor([14_000], device=runtime.device),
        valid=torch.tensor([True], device=runtime.device),
    )
    assert supported.tolist() == [True]
    python_projectiles = [
        entity for entity in oracle.entities.values() if isinstance(entity, Projectile)
    ]
    assert len(python_projectiles) == 30
    assert objects.objects.object_id[0, :30].tolist() == list(range(3, 33))
    assert objects.objects.target_x_units[0, :30].tolist() == [
        round(projectile.target_position.x * 1_000) for projectile in python_projectiles
    ]
    assert objects.objects.target_y_units[0, :30].tolist() == [
        round(projectile.target_position.y * 1_000) for projectile in python_projectiles
    ]
    assert objects.objects.launch_delay_ms[0, :30].tolist() == [
        round(projectile.launch_delay * 1_000) for projectile in python_projectiles
    ]
    assert oracle.rng.getstate() == runtime.battle.rng.python_state(0)

    for _ in range(50):
        _oracle_object_tick(oracle)
        result = bridge.step_objects_(runtime, objects)
        assert result.supported_batch.tolist() == [True]
        assert runtime.battle.entity_hp[0, :2].tolist() == [
            oracle.entities[entity_id].hitpoints for entity_id in (1, 2)
        ]
        assert runtime.battle.entity_hp_integer_kind[0, :2].tolist() == [
            type(oracle.entities[entity_id].hitpoints) is int for entity_id in (1, 2)
        ]
        live_python = sorted(
            entity.id
            for entity in oracle.entities.values()
            if isinstance(entity, Projectile)
        )
        live_tensor = sorted(
            objects.objects.object_id[0, objects.objects.allocated[0]].tolist()
        )
        assert live_tensor == live_python
        if not live_python:
            break

    assert runtime.battle.entity_hp[0, :2].tolist() == [1_634.0, 1_634.0]
    assert oracle.rng.getstate() == runtime.battle.rng.python_state(0)


@pytest.mark.parametrize(("player_id", "target_x"), ((0, 9), (1, 8)))
def test_goblin_barrel_spawn_handoff_identity_formation_and_delay_match_python(
    tensor_device: str, player_id: int, target_x: int
) -> None:
    battle = _battle(cards=("GoblinBarrel",))
    oracle = copy.deepcopy(battle)
    runtime, objects, bridge, shared_catalog = _runtime_bridge(
        [battle],
        {"GoblinBarrel"},
        device=tensor_device,
        max_entities=16,
        max_objects=4,
    )
    assert runtime.catalog is shared_catalog
    card_id = runtime.battle.card_to_id["GoblinBarrel"]
    assert SPELL_REGISTRY["GoblinBarrel"].cast(
        oracle, player_id, Position(target_x, 14)
    )
    assert isinstance(oracle.entities[1], SpawnProjectile)
    assert bridge.materialize_spell_actions_(
        runtime,
        objects,
        card_ids=torch.tensor([card_id], device=runtime.device),
        player_ids=torch.tensor([player_id], device=runtime.device),
        target_x_units=torch.tensor([target_x * 1_000], device=runtime.device),
        target_y_units=torch.tensor([14_000], device=runtime.device),
        valid=torch.tensor([True], device=runtime.device),
    ).all()
    carrier_slot = int(torch.where(runtime.battle.entity_id[0] == 1)[0][0].item())
    assert runtime.battle.entity_card[0, carrier_slot].item() == 0

    for _ in range(50):
        _oracle_object_tick(oracle)
        bridge.step_objects_(runtime, objects)
        python_carriers = [
            entity
            for entity in oracle.entities.values()
            if isinstance(entity, SpawnProjectile)
        ]
        if python_carriers:
            assert objects.objects.x_units[0, 0].item() == round(
                python_carriers[0].position.x * 1_000
            )
            assert objects.objects.y_units[0, 0].item() == round(
                python_carriers[0].position.y * 1_000
            )
        else:
            break

    assert sorted(oracle.entities) == [2, 3, 4]
    active_slots = torch.where(runtime.entity_pool.active[0])[0]
    assert runtime.battle.entity_id[0, active_slots].tolist() == [2, 3, 4]
    goblin_card_id = runtime.battle.card_to_id["Goblin"]
    goblin_catalog_id = runtime.card_catalog_index[goblin_card_id]
    assert goblin_catalog_id.item() > 0
    assert runtime.catalog.hitpoints[goblin_catalog_id].item() == 202
    assert runtime.catalog.load_time_ms[goblin_catalog_id].item() == 700
    for slot, entity_id in zip(active_slots.tolist(), (2, 3, 4), strict=True):
        entity = oracle.entities[entity_id]
        assert runtime.battle.entity_card[0, slot].item() == goblin_card_id
        assert runtime.battle.entity_x_units[0, slot].item() == round(
            entity.position.x * 1_000
        )
        assert runtime.battle.entity_y_units[0, slot].item() == round(
            entity.position.y * 1_000
        )
        assert runtime.battle.entity_hp[0, slot].item() == entity.hitpoints
        assert (
            runtime.battle.entity_deploy_delay[0, slot].item()
            == entity.deploy_delay_remaining
        )
        assert (
            runtime.battle.entity_placement_pending[0, slot].item()
            is entity.placement_pending
        )
        assert bridge.spawn_target_distance_discount_sq_units[0, slot].item() == (
            entity._native_target_distance_discount_sq_units
        )
    spawn_events = runtime.events.opcode == RuntimeEventOpcode.SPAWN
    carrier_spawn = spawn_events & (runtime.events.payload == 0)
    assert runtime.events.source_id[carrier_spawn].tolist() == [1]
    assert runtime.events.payload[carrier_spawn].tolist() == [0]
    child_spawn = spawn_events & (runtime.events.payload == goblin_card_id)
    assert runtime.events.source_id[child_spawn].tolist() == [2, 3, 4]
    assert runtime.events.target_id[child_spawn].tolist() == [0, 0, 0]


def test_spawn_projectile_requires_exact_shared_child_catalog_without_replacement() -> (
    None
):
    battle = _battle(cards=("GoblinBarrel",))
    shared_catalog = TensorCardCatalog.compile(battle.card_loader, {"GoblinBarrel"})
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=128, catalog=shared_catalog
    )
    objects = TensorRuntimeObjectPhase.from_battles(runtime, [battle], max_objects=4)
    bridge = TensorResidentProjectileSpellBridge.from_battles(
        runtime, objects, [battle]
    )
    assert runtime.catalog is shared_catalog
    card_id = runtime.battle.card_to_id["GoblinBarrel"]
    assert bridge.catalog.supported[card_id].item() is False
    assert "shared card catalog" in str(bridge.catalog.unsupported_reason[card_id])
    before_ids = runtime.battle.entity_id.clone()
    before_next = runtime.entity_pool.next_entity_id.clone()
    before_objects = objects.objects.allocated.clone()

    supported = bridge.materialize_spell_actions_(
        runtime,
        objects,
        card_ids=torch.tensor([card_id]),
        player_ids=torch.tensor([0]),
        target_x_units=torch.tensor([9_000]),
        target_y_units=torch.tensor([14_000]),
        valid=torch.tensor([True]),
    )

    assert supported.tolist() == [False]
    assert torch.equal(runtime.battle.entity_id, before_ids)
    assert torch.equal(runtime.entity_pool.next_entity_id, before_next)
    assert torch.equal(objects.objects.allocated, before_objects)


def test_unsupported_spell_families_fail_atomically_without_rng_consumption() -> None:
    cards = ("Freeze", "Arrows", "GoblinBarrel", "Knight")
    battles: list[BattleState] = []
    for _ in range(3):
        seed = BattleState(fast_path=False)
        target = _troop(seed, "Knight", 1, 1, Position(9, 14))
        battles.append(_battle(target, cards=cards))
    runtime, objects, bridge, _ = _runtime_bridge(
        battles, set(cards), max_entities=4, max_objects=8
    )
    names = ("Freeze", "Arrows", "GoblinBarrel")
    card_ids = torch.tensor([runtime.battle.card_to_id[name] for name in names])
    before_runtime = {
        (type(owner).__name__, name): value.clone()
        for owner in (runtime.battle, runtime.entity_pool, runtime.events)
        for name, value in vars(owner).items()
        if isinstance(value, torch.Tensor)
    }
    before_objects = {
        name: value.clone()
        for name, value in vars(objects.objects).items()
        if isinstance(value, torch.Tensor)
    }
    before_rng_words = runtime.battle.rng.words.clone()
    before_rng_index = runtime.battle.rng.index.clone()

    supported = bridge.materialize_spell_actions_(
        runtime,
        objects,
        card_ids=card_ids,
        player_ids=torch.zeros(3, dtype=torch.int64),
        target_x_units=torch.full((3,), 9_000),
        target_y_units=torch.full((3,), 14_000),
        valid=torch.ones(3, dtype=torch.bool),
    )

    assert supported.tolist() == [False, False, False]
    assert torch.equal(runtime.battle.rng.words, before_rng_words)
    assert torch.equal(runtime.battle.rng.index, before_rng_index)
    for owner in (runtime.battle, runtime.entity_pool, runtime.events):
        for name, value in vars(owner).items():
            if isinstance(value, torch.Tensor):
                key = (type(owner).__name__, name)
                assert torch.equal(value, before_runtime[key]), key
    for name, value in before_objects.items():
        assert torch.equal(getattr(objects.objects, name), value), name
