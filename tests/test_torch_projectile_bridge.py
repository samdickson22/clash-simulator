from __future__ import annotations

import copy
from collections.abc import Iterator
from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile, TargetType, Troop
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.combat import CombatStepResult
from clasher.torch_sim.combat_adapter import project_stationary_combat
from clasher.torch_sim.projectile_bridge import (
    BridgePayloadKind,
    TensorResidentProjectileSpellBridge,
)
from clasher.torch_sim.runtime_objects import (
    TensorRuntimeObjectPhase,
)
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TensorBattleRuntime


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


def _battle(*entities: Troop, cards: tuple[str, ...] = ()) -> BattleState:
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
    catalog = TensorCardCatalog.compile(battles[0].card_loader, names, device=device)
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
        "Fireball": (BridgePayloadKind.PROJECTILE_SPELL, False),
        "Arrows": (BridgePayloadKind.PROJECTILE_SPELL, False),
        "GoblinBarrel": (BridgePayloadKind.UNSUPPORTED, False),
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

    assert 3 not in oracle.entities
    assert not objects.objects.allocated.any()
    assert (
        runtime.battle.entity_hp[0, target_slot].item() == oracle.entities[2].hitpoints
    )


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
    assert runtime.status.stun_timer[0, 0].item() == oracle.entities[1].stun_timer
    assert torch.equal(runtime.entity_pool.next_entity_id, before_next)
    assert not objects.objects.allocated.any()
    assert runtime.events.opcode[0, : runtime.events.count[0]].tolist() == [2, 4]


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
    opcodes = runtime.events.opcode[0, : runtime.events.count[0]].tolist()
    assert RuntimeEventOpcode.DAMAGE not in opcodes


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


def test_unsupported_spell_families_fail_atomically_without_rng_consumption() -> None:
    cards = ("Fireball", "Arrows", "GoblinBarrel", "Knight")
    battles: list[BattleState] = []
    for _ in range(3):
        seed = BattleState(fast_path=False)
        target = _troop(seed, "Knight", 1, 1, Position(9, 14))
        battles.append(_battle(target, cards=cards))
    runtime, objects, bridge, _ = _runtime_bridge(
        battles, set(cards), max_entities=8, max_objects=8
    )
    names = ("Fireball", "Arrows", "GoblinBarrel")
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
    before_rng = bridge.rng_counter.clone()

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
    assert torch.equal(bridge.rng_counter, before_rng)
    for owner in (runtime.battle, runtime.entity_pool, runtime.events):
        for name, value in vars(owner).items():
            if isinstance(value, torch.Tensor):
                key = (type(owner).__name__, name)
                assert torch.equal(value, before_runtime[key]), key
    for name, value in before_objects.items():
        assert torch.equal(getattr(objects.objects, name), value), name
