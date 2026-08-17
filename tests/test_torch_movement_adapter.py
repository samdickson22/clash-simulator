from __future__ import annotations

import math

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.kinematics import tiles_to_logic_units
from clasher.pathfinding import ground_path_waypoint, native_single_node_waypoint
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.movement import (
    accumulate_collision_vectors,
    river_jump_step,
    target_directed_movement_step,
)
from clasher.torch_sim.movement_adapter import (
    MovementUnsupported,
    TensorMovementAdapter,
)

ENABLED_CARDS = frozenset(unique_cards_from_decks(load_deck_pool()))


def _spawn_troop(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    assert card_name in ENABLED_CARDS
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    troop = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop.on_spawn()
    assert not troop.mechanics
    return troop


def _spawn_building(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Building:
    assert card_name in ENABLED_CARDS
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_entity(Building, position, player_id, stats)
    building = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Building)
    )
    building.deploy_delay_remaining = 0.0
    building.placement_pending = False
    return building


def _slot(adapter: TensorMovementAdapter, entity: Troop | Building) -> int:
    return adapter.slots_for_ids(0, [entity.id])[0]


def _oracle_route_head(
    battle: BattleState,
    mover_id: int,
    target_id: int,
) -> tuple[tuple[int, int], tuple[tuple[int, int], ...], object]:
    clone = battle.clone()
    mover = clone.entities[mover_id]
    target = clone.entities[target_id]
    assert isinstance(mover, Troop)
    waypoint = (
        native_single_node_waypoint(mover, target)
        if mover.is_air_unit
        else ground_path_waypoint(
            clone,
            mover,
            target.position,
            target_entity=target,
            backwards_reference=target.position,
        )
    )
    return (
        (tiles_to_logic_units(waypoint.x), tiles_to_logic_units(waypoint.y)),
        tuple(getattr(mover, "_native_ground_route_cells", [])),
        getattr(mover, "_ground_path_cache_key", None),
    )


@pytest.mark.parametrize(
    ("card_name", "is_air"),
    [
        ("Archers", False),
        ("BabyDragon", True),
        ("Bats", True),
        ("Bomber", False),
        ("Bowler", False),
        ("DartGoblin", False),
        ("Giant", False),
        ("GoblinGang", False),
        ("HogRider", False),
        ("Knight", False),
        ("MagicArcher", False),
        ("MegaMinion", True),
        ("MiniPekka", False),
        ("Minions", True),
        ("Musketeer", False),
        ("Pekka", False),
        ("Prince", False),
        ("Princess", False),
        ("RoyalHogs", False),
        ("Skeletons", False),
        ("SpearGoblins", False),
        ("Valkyrie", False),
    ],
)
def test_enabled_mechanic_free_ground_and_air_route_heads_match_oracle(
    card_name: str,
    is_air: bool,
) -> None:
    battle = BattleState()
    mover = _spawn_troop(battle, card_name, 0, Position(8.75, 12.25))
    target = _spawn_troop(battle, "Knight", 1, Position(10.25, 20.75))
    mover._movement_target_id = target.id
    expected_head, expected_route, expected_cache = _oracle_route_head(
        battle, mover.id, target.id
    )

    adapter = TensorMovementAdapter.from_battles([battle])
    slot = _slot(adapter, mover)

    assert mover.is_air_unit is is_air
    assert adapter.is_air[0, slot].item() is is_air
    assert adapter.waypoint_valid[0, slot].item()
    assert tuple(adapter.waypoint_units[0, slot].tolist()) == expected_head
    count = int(adapter.route_count[0, slot].item())
    assert tuple(map(tuple, adapter.route_cells[0, slot, :count].tolist())) == (
        expected_route
    )
    specialized_component = bool(
        adapter.charge_component[0, slot].item()
        or adapter.movement_cycle[0, slot].item()
    )
    assert adapter.ordinary_supported[0, slot].item() is (not specialized_component)
    if specialized_component:
        expected_reason = (
            MovementUnsupported.CHARGE_COMPONENT
            if adapter.charge_component[0, slot].item()
            else MovementUnsupported.MOVEMENT_CYCLE
        )
        assert int(adapter.ordinary_unsupported[0, slot].item()) & int(expected_reason)
    else:
        assert int(adapter.ordinary_unsupported[0, slot].item()) == 0

    # Compiling support is read-only; retained path state remains absent from
    # the authoritative object until an explicit sync boundary.
    assert getattr(mover, "_ground_path_cache_key", None) is None
    adapter.sync_to_battles([battle])
    assert getattr(mover, "_ground_path_cache_key", None) == expected_cache


@pytest.mark.parametrize(
    ("player_id", "start", "target_position"),
    [
        (0, Position(9.0, 14.25), Position(9.0, 20.0)),
        (1, Position(9.0, 17.75), Position(9.0, 12.0)),
        (0, Position(3.5, 15.75), Position(4.0, 20.0)),
        (1, Position(14.5, 16.25), Position(14.0, 12.0)),
    ],
)
def test_bridge_and_river_route_heads_match_native_pathfinder(
    player_id: int,
    start: Position,
    target_position: Position,
) -> None:
    battle = BattleState()
    mover = _spawn_troop(battle, "Knight", player_id, start)
    target = _spawn_troop(battle, "Knight", 1 - player_id, target_position)
    mover._movement_target_id = target.id
    expected_head, expected_route, _ = _oracle_route_head(battle, mover.id, target.id)

    adapter = TensorMovementAdapter.from_battles([battle])
    slot = _slot(adapter, mover)
    assert tuple(adapter.waypoint_units[0, slot].tolist()) == expected_head
    count = int(adapter.route_count[0, slot].item())
    assert tuple(map(tuple, adapter.route_cells[0, slot, :count].tolist())) == (
        expected_route
    )
    assert count > 0
    assert adapter.ordinary_supported[0, slot].item()


def test_active_river_jump_has_separate_support_and_syncs_exact_state() -> None:
    battle = BattleState()
    hog = _spawn_troop(battle, "HogRider", 0, Position(9.25, 14.75))
    target = _spawn_troop(battle, "Knight", 1, Position(9.75, 20.0))
    hog._movement_target_id = target.id
    hog._river_jump_origin = Position(9.25, 14.75)
    hog._river_jump_target = Position(9.75, 17.25)
    hog._river_jump_elapsed = 0.1
    hog._river_jump_duration = 0.790625
    hog._river_jump_active = True
    hog._river_jump_blocked = False
    hog._special_move_active = True
    hog._special_move_consumed_tick = False
    setattr(hog, "_native_ground_route_cells", [(18, 35)])
    setattr(
        hog,
        "_ground_path_cache_key",
        ((18, 40), hog._native_lane_id, True),
    )
    expected = battle.clone()
    expected_hog = expected.entities[hog.id]
    assert isinstance(expected_hog, Troop)
    expected_hog._update_river_jump(expected.dt, expected)

    adapter = TensorMovementAdapter.from_battles([battle])
    slot = _slot(adapter, hog)
    assert adapter.river_jump_supported[0, slot].item()
    assert not adapter.ordinary_supported[0, slot].item()
    assert int(adapter.river_unsupported[0, slot].item()) == 0
    assert int(adapter.ordinary_unsupported[0, slot].item()) & int(
        MovementUnsupported.RIVER_JUMP_ACTIVE
    )

    result = river_jump_step(
        adapter.position_units,
        adapter.river_target_units,
        adapter.jump_speed_units,
        active=adapter.river_jump_supported,
        avoidance=adapter.avoidance,
    )
    adapter.apply_river_result(result, dt=battle.dt)
    adapter.sync_to_battles([battle])

    assert hog.position == expected_hog.position
    assert hog.native_facing_units() == expected_hog.native_facing_units()
    assert hog._river_jump_elapsed == expected_hog._river_jump_elapsed
    assert hog._river_jump_duration == expected_hog._river_jump_duration
    assert hog._river_jump_active is expected_hog._river_jump_active
    assert hog._special_move_active is expected_hog._special_move_active
    assert getattr(hog, "_native_ground_route_cells") == [(18, 35)]


def test_ordinary_kernel_result_round_trips_route_and_internal_state() -> None:
    battle = BattleState()
    mover = _spawn_troop(battle, "Knight", 0, Position(8.75, 10.25))
    target = _spawn_troop(battle, "Knight", 1, Position(10.25, 13.75))
    mover._movement_target_id = target.id
    mover._native_natural_movement_active = True
    expected = battle.clone()
    expected_mover = expected.entities[mover.id]
    expected_target = expected.entities[target.id]
    assert isinstance(expected_mover, Troop)
    expected_mover._move_towards_target(expected_target, expected.dt, expected)
    expected_mover.finish_movement_tick(expected)
    expected_mover.quantize_logic_position()

    adapter = TensorMovementAdapter.from_battles([battle])
    result = target_directed_movement_step(
        adapter.position_units,
        adapter.waypoint_units,
        adapter.effective_speed_units,
        supported=adapter.ordinary_supported,
        external_vector_units=adapter.pending_vector_units,
        avoidance=adapter.avoidance,
    )
    adapter.apply_natural_result(result)
    adapter.sync_to_battles([battle])

    assert mover.position == expected_mover.position
    assert mover.native_facing_units() == expected_mover.native_facing_units()
    assert getattr(mover, "_native_ground_route_cells") == getattr(
        expected_mover, "_native_ground_route_cells"
    )
    assert getattr(mover, "_ground_path_cache_key") == getattr(
        expected_mover, "_ground_path_cache_key"
    )
    assert getattr(mover, "_ground_path_cache_backwards") == (
        getattr(expected_mover, "_ground_path_cache_backwards")
    )
    assert mover._ground_path_backwards == expected_mover._ground_path_backwards
    assert mover._pending_movement_consumed is True


def test_crowded_collision_inputs_match_scalar_oracle_in_entity_id_order() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    knight = _spawn_troop(battle, "Knight", 0, Position(9.0, 10.0))
    giant = _spawn_troop(battle, "Giant", 1, Position(9.55, 10.0))
    air = _spawn_troop(battle, "MegaMinion", 1, Position(9.1, 10.0))
    cannon = _spawn_building(battle, "Cannon", 1, Position(8.55, 10.0))
    knight._movement_target_id = giant.id

    adapter = TensorMovementAdapter.from_battles([battle])
    collision = adapter.collision_batch()
    actual = accumulate_collision_vectors(collision)
    assert actual.supported_batch.tolist() == [True]
    assert collision.entity_id[0, :4].tolist() == [1, 2, 3, 4]
    assert collision.air_collision[0, _slot(adapter, air)].item()
    assert not collision.air_collision[0, _slot(adapter, knight)].item()

    oracle = battle.clone()
    expected_by_id: dict[int, tuple[int, int, int]] = {}
    for entity in sorted(oracle.entities.values(), key=lambda item: item.id):
        if not isinstance(entity, Troop):
            continue
        oracle._accumulate_troop_collision_for(entity)
        expected_by_id[entity.id] = (
            entity._movement_vector_x_units,
            entity._movement_vector_y_units,
            entity._movement_vector_count,
        )
    for entity in (knight, giant, air):
        slot = _slot(adapter, entity)
        assert (
            tuple(actual.accumulated_vector_units[0, slot].tolist())
            == (expected_by_id[entity.id][:2])
        )
        assert int(actual.contact_count[0, slot].item()) == expected_by_id[entity.id][2]
    assert int(actual.contact_count[0, _slot(adapter, knight)].item()) >= 2
    assert cannon.id == 4
    knight_slot = _slot(adapter, knight)
    assert not adapter.ordinary_supported[0, knight_slot].item()
    assert adapter.avoidance_prepass_required[0, knight_slot].item()
    assert int(adapter.ordinary_unsupported[0, knight_slot].item()) & int(
        MovementUnsupported.AVOIDANCE_PREPASS
    )


def test_hidden_movement_state_round_trips_losslessly() -> None:
    battle = BattleState()
    mover = _spawn_troop(battle, "Knight", 0, Position(8.125, 11.375))
    target = _spawn_troop(battle, "Knight", 1, Position(10.625, 18.875))
    mover._movement_target_id = target.id
    mover._facing_x_units = -1234
    mover._facing_y_units = 5678
    mover._native_avoidance = -170
    mover._movement_vector_x_units = 901
    mover._movement_vector_y_units = -307
    mover._movement_vector_count = 3
    mover._movement_vector_bypasses_cap = True
    mover._pending_movement_x = 0.125
    mover._pending_movement_y = -0.075
    mover._pending_movement_consumed = False
    mover._native_natural_movement_active = True
    mover.movement_phase_elapsed_ms = 937
    mover._native_charge_progress = 12345
    mover.distance_traveled = math.nextafter(17.25, math.inf)

    adapter = TensorMovementAdapter.from_battles([battle])
    slot = _slot(adapter, mover)
    expected_bits = int(adapter.distance_traveled_bits[0, slot].item())
    mover.position = Position(1.0, 1.0)
    mover._facing_x_units = 0
    mover._facing_y_units = 0
    mover._native_avoidance = 0
    mover._movement_vector_x_units = 0
    mover._movement_vector_y_units = 0
    mover._movement_vector_count = 0
    mover._pending_movement_x = 0.0
    mover._pending_movement_y = 0.0
    mover.distance_traveled = 0.0
    adapter.sync_to_battles([battle])

    assert mover.position == Position(8.125, 11.375)
    assert mover.native_facing_units() == (-1234, 5678)
    assert mover._native_avoidance == -170
    assert (
        mover._movement_vector_x_units,
        mover._movement_vector_y_units,
        mover._movement_vector_count,
    ) == (901, -307, 3)
    assert mover._movement_vector_bypasses_cap is True
    assert mover._pending_movement_x == 0.125
    assert mover._pending_movement_y == -0.075
    assert mover._pending_movement_consumed is False
    assert mover._native_natural_movement_active is True
    assert mover.movement_phase_elapsed_ms == 937
    assert mover._native_charge_progress == 12345
    assert mover.distance_traveled == math.nextafter(17.25, math.inf)
    round_trip = TensorMovementAdapter.from_battles([battle])
    round_trip_slot = _slot(round_trip, mover)
    assert int(round_trip.distance_traveled_bits[0, round_trip_slot].item()) == (
        expected_bits
    )


def test_sync_fails_closed_if_entity_identity_changes() -> None:
    battle = BattleState()
    adapter = TensorMovementAdapter.from_battles([battle])
    battle.entities.pop(max(battle.entities))
    with pytest.raises(ValueError, match="identity/order changed"):
        adapter.sync_to_battles([battle])


def test_mixed_batch_keeps_independent_route_and_support_lanes() -> None:
    ground_battle = BattleState()
    ground = _spawn_troop(ground_battle, "Knight", 0, Position(5.0, 12.0))
    ground_target = _spawn_troop(ground_battle, "Knight", 1, Position(13.0, 20.0))
    ground._movement_target_id = ground_target.id

    air_battle = BattleState()
    air = _spawn_troop(air_battle, "BabyDragon", 0, Position(13.0, 12.0))
    air_target = _spawn_troop(air_battle, "Knight", 1, Position(5.0, 20.0))
    air._movement_target_id = air_target.id

    adapter = TensorMovementAdapter.from_battles(
        [ground_battle, air_battle], max_entities=16
    )
    ground_slot = adapter.slots_for_ids(0, [ground.id])[0]
    air_slot = adapter.slots_for_ids(1, [air.id])[0]
    assert adapter.ordinary_supported[0, ground_slot].item()
    assert adapter.ordinary_supported[1, air_slot].item()
    assert not adapter.is_air[0, ground_slot].item()
    assert adapter.is_air[1, air_slot].item()
    assert adapter.position_units.shape == (2, 16, 2)
    assert adapter.collision_batch().entity_id.shape == (2, 16)
