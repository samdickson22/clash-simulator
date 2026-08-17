from __future__ import annotations

from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import TargetType, Troop
from clasher.logic_math import native_percent_damage
from clasher.mechanics.shared.multi_target import MultipleTargetAttack
from clasher.torch_sim.catalog import MECHANIC_OPCODE
from clasher.torch_sim.combat_mechanics import (
    SUPPORTED_MECHANIC_NAMES,
    CombatMechanicOpcode,
    MechanicEventOpcode,
    TensorCombatMechanicCatalog,
    TensorDamageRampState,
    TensorMechanicEvents,
    TensorMechanicWorld,
    UnsupportedCombatMechanicDeviceError,
    apply_crown_tower_scaling,
    emit_area_damage_events,
    emit_area_spawn_events,
    emit_chain_lightning_events,
    emit_death_damage_events,
    emit_ice_spirit_freeze_events,
    emit_multiple_target_events,
    select_chain_targets,
    select_multiple_targets,
    targets_in_native_area,
    update_damage_ramp_,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable on this host")
    yield device


def _catalog(*names: str, device: str = "cpu") -> TensorCombatMechanicCatalog:
    return TensorCombatMechanicCatalog.compile(CardDataLoader(), names, device=device)


def _world(device: str = "cpu") -> TensorMechanicWorld:
    world = TensorMechanicWorld.empty(1, 6, device=device)
    world.present[0, :5] = True
    world.alive[0, :5] = True
    world.entity_id[0, :5] = torch.tensor([10, 30, 20, 50, 40], device=world.device)
    world.owner[0, :5] = torch.tensor([0, 1, 1, 1, 1], device=world.device)
    world.x_units[0, :5] = torch.tensor(
        [9_000, 10_000, 8_000, 12_000, 9_000], device=world.device
    )
    world.y_units[0, :5] = torch.tensor(
        [10_000, 10_000, 10_000, 10_000, 13_000], device=world.device
    )
    world.collision_radius_units[0, :5] = 500
    world.hp[0, :5] = torch.tensor(
        [500, 100, 500, 500, 500], dtype=torch.float64, device=world.device
    )
    return world


def _python_troop(
    battle: BattleState,
    name: str,
    entity_id: int,
    player_id: int,
    x: float,
    y: float,
    *,
    hp: float = 500,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    troop = Troop(
        id=entity_id,
        position=Position(x, y),
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
    setattr(troop, "battle_state", battle)
    return troop


def test_catalog_compiles_every_named_factory_mechanic_without_card_branches() -> None:
    definitions = CardDataLoader().load_card_definitions()
    names = tuple(
        name
        for name, definition in definitions.items()
        if any(
            type(mechanic).__name__ in SUPPORTED_MECHANIC_NAMES
            for mechanic in definition.mechanics
        )
    )
    catalog = _catalog(*names)

    for name in names:
        card_id = catalog.name_to_id[name]
        expected = [
            MECHANIC_OPCODE[type(mechanic).__name__]
            for mechanic in definitions[name].mechanics
            if type(mechanic).__name__ in SUPPORTED_MECHANIC_NAMES
        ]
        assert catalog.opcode[card_id, : len(expected)].tolist() == expected
        assert int(catalog.count[card_id].item()) == len(expected)

    inferno = catalog.name_to_id["InfernoDragon"]
    slot, present = catalog.mechanic_slot(
        torch.tensor([inferno]), CombatMechanicOpcode.DAMAGE_RAMP
    )
    assert present.tolist() == [True]
    ramp_slot = int(slot.item())
    assert catalog.ramp_stage_time_ms[inferno, ramp_slot].tolist() == [
        0,
        2_000,
        4_000,
    ]
    assert catalog.ramp_stage_damage[inferno, ramp_slot].tolist() == [
        35,
        120,
        422,
    ]

    for name, expected_support in {
        "ElectroWizard": True,
        "Lumberjack": True,
        "BattleHealer": False,
        "TriWizards": False,
        "SuspiciousBush": False,
    }.items():
        card_id = catalog.name_to_id[name]
        area_mask = torch.isin(
            catalog.opcode[card_id],
            torch.tensor(
                [
                    CombatMechanicOpcode.SPAWN_AREA,
                    CombatMechanicOpcode.DEATH_AREA,
                ]
            ),
        )
        area_slot = int(area_mask.to(torch.int64).argmax().item())
        assert (
            bool(catalog.area_payload_supported[card_id, area_slot]) is expected_support
        )


def test_crown_scaling_matches_python_native_arithmetic_on_cpu_and_cuda(
    tensor_device: str,
) -> None:
    catalog = _catalog("Miner", device=tensor_device)
    card_id = torch.tensor(
        [catalog.name_to_id["Miner"]] * 3,
        dtype=torch.int64,
        device=catalog.device,
    )
    damage = torch.tensor([100.0, 195.0, 100.0], device=catalog.device)
    crown = torch.tensor([True, True, False], device=catalog.device)

    result, applied = apply_crown_tower_scaling(catalog, card_id, damage, crown)

    assert applied.tolist() == [True, True, False]
    assert result.tolist() == [39, 39, 100]

    # Explicit values and native ceiling percentage share the same kernel.
    multiplier = torch.tensor([0.2], dtype=torch.float64)
    assert native_percent_damage(195, multiplier.item()) == 39


def test_mps_fails_closed_before_exact_catalog_allocation() -> None:
    if not torch.backends.mps.is_available():
        pytest.skip("MPS is unavailable on this host")
    with pytest.raises(UnsupportedCombatMechanicDeviceError):
        _catalog("Miner", device="mps")


def test_damage_ramp_target_clock_reset_and_stages_match_python_mechanic() -> None:
    catalog = _catalog("InfernoDragon")
    card = torch.tensor([catalog.name_to_id["InfernoDragon"]])
    state = TensorDamageRampState.empty((1,))
    target = torch.tensor([44])
    connected = torch.tensor([True])
    rate = torch.tensor([1.0], dtype=torch.float64)

    for _ in range(39):
        damage = update_damage_ramp_(state, catalog, card, target, connected, rate)
    assert state.target_time_ms.tolist() == [1_950]
    assert damage.tolist() == [35]

    damage = update_damage_ramp_(state, catalog, card, target, connected, rate)
    assert state.target_time_ms.tolist() == [2_000]
    assert damage.tolist() == [120]

    update_damage_ramp_(
        state,
        catalog,
        card,
        torch.tensor([99]),
        connected,
        torch.tensor([1.5]),
    )
    assert state.target_id.tolist() == [99]
    assert state.target_time_ms.tolist() == [75]
    assert state.damage.tolist() == [35]

    update_damage_ramp_(state, catalog, card, target, torch.tensor([False]), rate)
    assert state.target_id.tolist() == [0]
    assert state.target_time_ms.tolist() == [0]
    assert state.damage.tolist() == [35]


def test_chain_selection_uses_native_owner_relative_ties_and_visited_order() -> None:
    world = _world()
    selected, valid = select_chain_targets(
        world,
        owner=torch.tensor([0]),
        origin_x_units=torch.tensor([9_000]),
        origin_y_units=torch.tensor([10_000]),
        visited=world.entity_id == 10,
        chain_range_units=torch.tensor([4_000]),
        maximum_targets=4,
    )

    # IDs 20/30 are equally distant. Player-zero symmetric ordering prefers
    # the lower world X, then continues from each committed impact origin.
    assert selected.tolist() == [[20, 30, 50, 0]]
    assert valid.tolist() == [[True, True, True, False]]


def test_serialized_chain_and_secondary_hit_dispatch_keep_committed_order() -> None:
    world = _world()
    catalog = _catalog("ElectroDragon", "ElectroWizard")
    events = TensorMechanicEvents.empty(1, 16)
    dragon = torch.tensor([catalog.name_to_id["ElectroDragon"]])
    selected, valid = emit_chain_lightning_events(
        events,
        world,
        catalog,
        card_ids=dragon,
        source_id=torch.tensor([10]),
        owner=torch.tensor([0]),
        origin_x_units=torch.tensor([8_000]),
        origin_y_units=torch.tensor([10_000]),
        visited=world.entity_id == 20,
        damage=torch.tensor([100.0]),
        trigger=CombatMechanicOpcode.ELECTRO_DRAGON_CHAIN,
    )
    assert selected[0][valid[0]].tolist() == [30, 50]
    assert events.target_id[0, : events.count[0]].tolist() == [30, 50]
    assert events.duration_ms[0, : events.count[0]].tolist() == [300, 300]

    events = TensorMechanicEvents.empty(1, 8)
    wizard = torch.tensor([catalog.name_to_id["ElectroWizard"]])
    secondary, secondary_valid = emit_multiple_target_events(
        events,
        world,
        catalog,
        card_ids=wizard,
        source_id=torch.tensor([10]),
        owner=torch.tensor([0]),
        origin_x_units=torch.tensor([9_000]),
        origin_y_units=torch.tensor([10_000]),
        primary_id=torch.tensor([20]),
        damage=torch.tensor([192.0]),
    )
    assert secondary[0][secondary_valid[0]].tolist() == [30]
    assert events.opcode[0, 0].item() == MechanicEventOpcode.SECONDARY_HIT
    assert events.amount[0, 0].item() == 192


def test_multiple_target_selection_repeats_primary_only_when_serialized() -> None:
    world = _world()
    selected, valid = select_multiple_targets(
        world,
        owner=torch.tensor([0]),
        origin_x_units=torch.tensor([9_000]),
        origin_y_units=torch.tensor([10_000]),
        primary_id=torch.tensor([20]),
        target_count=torch.tensor([3]),
        all_targets_hit=torch.tensor([False]),
    )
    assert selected.tolist() == [[30, 40]]
    assert valid.tolist() == [[True, True]]

    battle = BattleState(fast_path=False)
    attacker = _python_troop(battle, "Knight", 10, 0, 9, 10)
    targets = [
        _python_troop(battle, "Knight", 30, 1, 10, 10),
        _python_troop(battle, "Knight", 20, 1, 8, 10),
        _python_troop(battle, "Knight", 50, 1, 12, 10),
        _python_troop(battle, "Knight", 40, 1, 9, 13),
    ]
    battle.entities = {entity.id: entity for entity in (attacker, *targets)}
    mechanic = MultipleTargetAttack(target_count=3)
    python_ids = [
        entity.id
        for entity in mechanic._ordered_secondary_targets(attacker, targets[1])[:2]
    ]
    python_world = _world()
    by_id = {entity.id: entity for entity in targets}
    for slot, entity_id in enumerate(python_world.entity_id[0].tolist()):
        if entity_id in by_id:
            python_world.targetable[0, slot] = attacker.can_attack_target(
                by_id[entity_id]
            )
    python_selected, python_valid = select_multiple_targets(
        python_world,
        owner=torch.tensor([0]),
        origin_x_units=torch.tensor([9_000]),
        origin_y_units=torch.tensor([10_000]),
        primary_id=torch.tensor([20]),
        target_count=torch.tensor([3]),
        all_targets_hit=torch.tensor([False]),
    )
    assert python_selected[0][python_valid[0]].tolist() == python_ids

    sparse = _world()
    sparse.present[0, 2:] = False
    sparse.alive[0, 2:] = False
    repeated, repeated_valid = select_multiple_targets(
        sparse,
        owner=torch.tensor([0]),
        origin_x_units=torch.tensor([9_000]),
        origin_y_units=torch.tensor([10_000]),
        primary_id=torch.tensor([30]),
        target_count=torch.tensor([3]),
        all_targets_hit=torch.tensor([True]),
    )
    assert repeated.tolist() == [[30, 30]]
    assert repeated_valid.tolist() == [[True, True]]


def test_death_damage_and_ice_freeze_event_families_keep_target_id_order() -> None:
    world = _world()
    events = TensorMechanicEvents.empty(1, 32)
    targets = emit_area_damage_events(
        events,
        world,
        source_id=torch.tensor([10]),
        owner=torch.tensor([0]),
        center_x_units=torch.tensor([9_000]),
        center_y_units=torch.tensor([10_000]),
        radius_units=torch.tensor([2_000]),
        damage=torch.tensor([120.0]),
        hits_air=torch.tensor([True]),
        hits_ground=torch.tensor([True]),
        stun_duration_ms=torch.tensor([1_200]),
        knockback_units=torch.tensor([1_800]),
        payload_opcode=CombatMechanicOpcode.ICE_SPIRIT_FREEZE,
    )

    assert targets[0, :3].tolist() == [False, True, True]
    count = int(events.count[0].item())
    assert events.opcode[0, :count].tolist() == [
        MechanicEventOpcode.DAMAGE,
        MechanicEventOpcode.DAMAGE,
        MechanicEventOpcode.STUN,
        MechanicEventOpcode.KNOCKBACK,
    ]
    assert events.target_id[0, :count].tolist() == [20, 30, 20, 20]
    # Target 30 has only 100 HP, so the committed damage kills it before the
    # second status/knockback query.
    assert events.duration_ms[0, :count].tolist() == [0, 0, 1_200, 0]

    ice_catalog = _catalog("IceSpirit")
    ice_events = TensorMechanicEvents.empty(1, 16)
    ice_targets = emit_ice_spirit_freeze_events(
        ice_events,
        world,
        ice_catalog,
        card_ids=torch.tensor([ice_catalog.name_to_id["IceSpirit"]]),
        source_id=torch.tensor([10]),
        owner=torch.tensor([0]),
        center_x_units=torch.tensor([9_000]),
        center_y_units=torch.tensor([10_000]),
        damage=torch.tensor([120.0]),
    )
    assert ice_targets[0, :3].tolist() == [False, True, True]
    assert ice_events.opcode[0, : ice_events.count[0]].tolist() == [
        MechanicEventOpcode.DAMAGE,
        MechanicEventOpcode.DAMAGE,
        MechanicEventOpcode.STUN,
    ]


def test_death_damage_payload_matches_python_mechanic_damage_and_targets() -> None:
    battle = BattleState(fast_path=False)
    source = _python_troop(battle, "IceGolem", 10, 0, 9, 10)
    left = _python_troop(battle, "Knight", 20, 1, 8, 10)
    right = _python_troop(battle, "Knight", 30, 1, 10, 10)
    battle.entities = {10: source, 30: right, 20: left}
    definition = battle.card_loader.load_card_definitions()["IceGolem"]
    mechanic = next(
        item for item in definition.mechanics if type(item).__name__ == "DeathDamage"
    )
    mechanic.on_attach(source)
    before = {20: left.hitpoints, 30: right.hitpoints}
    mechanic.on_death(source)

    catalog = _catalog("IceGolem")
    card_id = catalog.name_to_id["IceGolem"]
    slot, present = catalog.mechanic_slot(
        torch.tensor([card_id]), CombatMechanicOpcode.DEATH_DAMAGE
    )
    assert present.tolist() == [True]
    slot_index = int(slot.item())
    world = TensorMechanicWorld.empty(1, 3)
    world.present[:] = True
    world.alive[:] = True
    world.entity_id[0] = torch.tensor([10, 30, 20])
    world.owner[0] = torch.tensor([0, 1, 1])
    world.x_units[0] = torch.tensor([9_000, 10_000, 8_000])
    world.y_units[0] = 10_000
    world.collision_radius_units[0] = 500
    world.hp[0] = 500
    events = TensorMechanicEvents.empty(1, 8)
    emitted_targets = emit_death_damage_events(
        events,
        world,
        catalog,
        card_ids=torch.tensor([card_id]),
        source_id=torch.tensor([10]),
        owner=torch.tensor([0]),
        center_x_units=torch.tensor([9_000]),
        center_y_units=torch.tensor([10_000]),
    )

    expected_damage = before[20] - left.hitpoints
    assert expected_damage == before[30] - right.hitpoints
    assert expected_damage == catalog.damage[card_id, slot_index].item()
    assert emitted_targets.tolist() == [[False, True, True]]
    assert events.target_id[0, : events.count[0]].tolist() == [20, 30]
    assert events.amount[0, : events.count[0]].tolist() == [
        expected_damage,
        expected_damage,
    ]


def test_native_area_geometry_distinguishes_building_square_and_tangent_edge() -> None:
    world = TensorMechanicWorld.empty(1, 3)
    world.present[:] = True
    world.alive[:] = True
    world.entity_id[0] = torch.tensor([1, 2, 3])
    world.owner[0] = torch.tensor([0, 1, 1])
    world.x_units[0] = torch.tensor([0, 1_500, 1_500])
    world.y_units[0] = torch.tensor([0, 1_500, 0])
    world.collision_radius_units[0] = 500
    world.building[0, 1] = True

    targets = targets_in_native_area(
        world,
        owner=torch.tensor([0]),
        center_x_units=torch.tensor([0]),
        center_y_units=torch.tensor([0]),
        radius_units=torch.tensor([1_000]),
        hits_air=torch.tensor([True]),
        hits_ground=torch.tensor([True]),
    )

    # Building corner is outside the rounded-square intersection. Character
    # slot 2 is exactly tangent and native geometry excludes the perimeter.
    assert targets.tolist() == [[False, False, False]]


def test_spawn_and_death_area_events_expose_serialized_payloads() -> None:
    catalog = _catalog("ElectroWizard", "Lumberjack")
    events = TensorMechanicEvents.empty(2, 4)
    cards = torch.tensor(
        [
            catalog.name_to_id["ElectroWizard"],
            catalog.name_to_id["Lumberjack"],
        ]
    )
    source = torch.tensor([7, 8])

    spawn = emit_area_spawn_events(
        events,
        catalog,
        card_ids=cards,
        source_id=source,
        trigger=CombatMechanicOpcode.SPAWN_AREA,
    )
    death = emit_area_spawn_events(
        events,
        catalog,
        card_ids=cards,
        source_id=source,
        trigger=CombatMechanicOpcode.DEATH_AREA,
    )

    assert spawn.tolist() == [True, False]
    assert death.tolist() == [False, True]
    assert events.opcode[:, 0].tolist() == [
        MechanicEventOpcode.SPAWN_AREA,
        MechanicEventOpcode.DEATH_AREA,
    ]
    assert events.radius_units[:, 0].tolist() == [3_000, 3_000]
    assert events.duration_ms[:, 0].tolist() == [1, 5_500]
    assert events.amount[:, 0].tolist() == [192, 0]


def test_deterministic_mechanic_kernels_do_not_consume_torch_rng() -> None:
    torch.manual_seed(849_221)
    before = torch.random.get_rng_state().clone()
    world = _world()
    select_chain_targets(
        world,
        owner=torch.tensor([0]),
        origin_x_units=torch.tensor([9_000]),
        origin_y_units=torch.tensor([10_000]),
        visited=world.entity_id == 10,
        chain_range_units=torch.tensor([4_000]),
        maximum_targets=4,
    )
    select_multiple_targets(
        world,
        owner=torch.tensor([0]),
        origin_x_units=torch.tensor([9_000]),
        origin_y_units=torch.tensor([10_000]),
        primary_id=torch.tensor([20]),
        target_count=torch.tensor([3]),
        all_targets_hit=torch.tensor([False]),
    )
    assert torch.equal(torch.random.get_rng_state(), before)
