import copy
import random
import math

import pytest

from clasher.arena import Position
from clasher.balance import GLOBAL_ATTACK_FINISH_TIME_MS
from clasher.battle import BattleState
from clasher.mechanics.shared import MultipleTargetAttack, SerializedOnHitBuff
from clasher.mechanics.mechanic_base import BaseMechanic
from clasher.entities import (
    AreaEffect,
    BuffAreaEffect,
    Building,
    ChainLightning,
    DeathAreaEffectContainer,
    DeathAreaStartAction,
    Projectile,
    TimedExplosive,
    Troop,
)
from clasher.formations import formation_offset
from clasher.kinematics import (
    logic_speed_to_tiles_per_second,
    logic_units_to_tiles,
    movement_component_vector_logic_units,
    normalized_vector_logic_units,
    speed_work_for_duration,
    spawn_path_travel_tick_count,
    tiles_to_logic_units,
    vector_towards_logic_units,
)
from clasher.mechanics.shared.scaling import CrownTowerScaling
from clasher.mechanics.shared.death_area import spawn_death_area_object
from clasher.pathfinding import (
    _cell_for_position,
    _cell_center,
    _native_grid_route,
    _native_pathfinder_tile_cost,
    ground_path_waypoint,
    native_jump_landing_waypoint,
    native_route_goal_cell,
    native_single_node_waypoint,
)
from clasher.unit_traits import unit_mass


def _spawn_one(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
    *,
    resolve_spawn_payload: bool = True,
) -> Troop:
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
    if resolve_spawn_payload:
        # This helper creates an already-deployed character outside the
        # battle's phased update. Complete any object produced by its spawn
        # hook so callers receive the same post-deployment state. Ordering
        # tests use the real BattleState step and opt out explicitly.
        spawned_areas = [
            entity
            for entity_id, entity in battle.entities.items()
            if entity_id not in before
            and isinstance(entity, AreaEffect)
            and entity is not troop
        ]
        for area in spawned_areas:
            area.update(battle.dt, battle)
            if not area.is_alive:
                battle.entities.pop(area.id, None)
    return troop


def _run_natural_movement_component(
    battle: BattleState,
    troop: Troop,
    target: Troop | Building,
) -> None:
    """Run the native collision -> avoidance -> movement phase ordering."""

    troop._movement_target_id = target.id
    troop._native_natural_movement_active = True
    battle._accumulate_troop_collision_for(troop)
    troop.begin_movement_tick()
    try:
        troop.update_movement_component(battle.dt, battle)
    finally:
        troop.finish_movement_tick(battle)
        troop.quantize_logic_position()


def _advance_tesla_hide(mechanic, tesla, dt_ms):
    # Establish the combat state before exercising the object timer directly.
    tesla.update_combat_component(0.0, tesla.battle_state)
    mechanic.on_object_tick(tesla, dt_ms)


def _fully_hide_tesla(tesla: Building) -> None:
    hide = next(
        mechanic
        for mechanic in tesla.mechanics
        if type(mechanic).__name__ == "HideWhenIdle"
    )
    # Isolated effect tests may already have an enemy inside Tesla range. Put
    # the object at the exact native hidden boundary without consuming an
    # object phase; the live idle transition itself is tested separately.
    hide._phase_ms = float(hide.hide_delay_ms)
    tesla._hidden_building = True
    tesla._special_move_active = True
    tesla.target_id = None
    battle = tesla.battle_state
    if battle is not None:
        battle.sync_fast_target_entity(tesla)
    assert tesla._hidden_building


def test_entity_kind_classification_includes_gameplay_subclasses():
    class SpecializedBuilding(Building):
        pass

    class SpecializedTroop(Troop):
        pass

    battle = BattleState()
    building = battle._spawn_entity(
        SpecializedBuilding,
        Position(9.0, 12.0),
        0,
        battle.card_loader.get_card("Cannon"),
    )
    troop = battle._spawn_entity(
        SpecializedTroop,
        Position(9.0, 14.0),
        1,
        battle.card_loader.get_card("Knight"),
    )

    assert building.entity_kind == 1
    assert troop.entity_kind == 0


def test_entity_id_zero_is_a_real_target_and_keeps_its_attack_lock():
    battle = BattleState()
    tower = battle.entities.pop(1)
    tower.id = 0
    battle.entities[0] = tower
    attacker = _spawn_one(battle, "Knight", 1, Position(3.5, 8.5))
    distraction = _spawn_one(battle, "Skeletons", 0, Position(3.5, 9.0))
    attacker.position = Position(3.5, 8.5)
    distraction.position = Position(3.5, 9.0)
    attacker.target_id = tower.id

    assert tower.id == 0
    assert attacker.is_within_attack_reach(tower)
    assert attacker.get_nearest_target(battle.entities) is distraction

    attacker.update(battle.dt, battle)

    assert attacker.target_id == tower.id


def test_fallback_crown_target_cache_cannot_leak_outside_queried_entities():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    barrel = _spawn_one(
        battle,
        "SkeletonBarrel",
        0,
        Position(9.0, 14.0),
    )
    knight = _spawn_one(
        battle,
        "Knight",
        1,
        Position(9.0, 20.0),
    )

    # BattleState initialized its building cache with six live Crown Tower
    # objects. Clearing/replacing the queried entity collection must not let
    # those detached objects remain fallback objectives.
    assert barrel.get_nearest_target(battle.entities) is None
    assert barrel.get_nearest_target(
        {
            barrel.id: barrel,
            knight.id: knight,
        }
    ) is None


def test_attack_and_sight_ranges_include_both_hitboxes():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    attack_reach = (
        knight.range
        + knight.card_stats.collision_radius
        + target.card_stats.collision_radius
    )

    target.position = Position(9.0, 10.0 + attack_reach - 1e-6)
    assert knight.can_attack_target(target)
    target.position = Position(9.0, 10.0 + attack_reach + 1e-6)
    assert not knight.can_attack_target(target)

    sight_reach = (
        knight.sight_range + knight.get_collision_radius()
        + target.card_stats.collision_radius
    )
    target.position = Position(9.0, 10.0 + sight_reach - 1e-6)
    assert knight.get_nearest_target(battle.entities) is target


@pytest.mark.parametrize(
    ("extra_distance", "expects_hit"),
    [(0.0, True), (0.001, False)],
)
def test_mobile_committed_hit_uses_native_long_distance_guard(
    extra_distance: float,
    expects_hit: bool,
):
    class MoveTargetAtAttackStart(BaseMechanic):
        def __init__(self, destination: Position):
            self.destination = destination

        def on_attack_start(self, entity, target) -> None:
            target.position = self.destination

    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Skeletons", 1, Position(9.0, 10.5))
    target_hp = target.hitpoints
    hit_frame_reach = knight.get_effective_attack_range() + target.get_collision_radius() + 1.5
    knight.mechanics.append(
        MoveTargetAtAttackStart(
            Position(9.0, knight.position.y + hit_frame_reach + extra_distance)
        )
    )
    knight.target_id = target.id
    knight.attack_cooldown = 0.0

    knight.update_combat_component(battle.dt, battle)

    if expects_hit:
        assert target.hitpoints == pytest.approx(max(0.0, target_hp - knight.damage))
    else:
        assert target.hitpoints == target_hp
    # Knight has LoadTime but not the distinct LoadFirstHit capability.
    # Native therefore reloads a complete cycle whether the committed payload
    # connects or the late-distance guard discards it.
    assert knight.attack_cooldown == pytest.approx(
        knight.get_base_attack_interval_seconds()
    )


def test_discarded_hit_retains_load_only_for_serialized_load_first_hit(
    monkeypatch,
):
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    knight.attack_cooldown = 0.0

    monkeypatch.setattr(
        "clasher.entities.LOGIC_LOAD_FIRST_HIT_KEEP_LOADED_AFTER_DISCARD",
        True,
    )
    assert not knight.card_stats.load_first_hit
    assert knight.get_post_attack_cooldown_seconds(
        payload_discarded=True,
    ) == pytest.approx(knight.get_base_attack_interval_seconds())

    # Exercise the native capability independently of a card name so future
    # decoded data automatically receives the same shared rule.
    knight.card_stats.load_first_hit = True
    assert knight.get_post_attack_cooldown_seconds(
        payload_discarded=True,
    ) == 0.0

    monkeypatch.setattr(
        "clasher.entities.LOGIC_LOAD_FIRST_HIT_KEEP_LOADED_AFTER_DISCARD",
        False,
    )
    assert knight.get_post_attack_cooldown_seconds(
        payload_discarded=True,
    ) == pytest.approx(knight.get_base_attack_interval_seconds())


def test_long_distance_hit_guard_uses_character_capabilities_not_card_names():
    battle = BattleState()
    target = _spawn_one(battle, "Skeletons", 1, Position(9.0, 15.0))
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    bandit = _spawn_one(battle, "Bandit", 0, Position(8.0, 10.0))
    cannon = battle._spawn_entity(
        Building,
        Position(10.0, 10.0),
        0,
        battle.card_loader.get_card("Cannon"),
    )

    assert knight.should_cancel_committed_hit(target)
    # Serialized Speed == 0 exempts every building, while a positive
    # DashCooldown exempts every dash character through the same shared rule.
    assert not cannon.should_cancel_committed_hit(target)
    assert not bandit.should_cancel_committed_hit(target)


def test_discarded_projectile_attack_does_not_apply_attack_pushback():
    class MoveTargetAtAttackStart(BaseMechanic):
        def __init__(self, destination: Position):
            self.destination = destination

        def on_attack_start(self, entity, target) -> None:
            target.position = self.destination

    battle = BattleState()
    firecracker = _spawn_one(
        battle,
        "Firecracker",
        0,
        Position(9.0, 10.0),
    )
    target = _spawn_one(
        battle,
        "Skeletons",
        1,
        Position(9.0, 14.0),
    )
    start = Position(firecracker.position.x, firecracker.position.y)
    hit_frame_reach = (
        firecracker.get_effective_attack_range() + target.get_collision_radius() + 1.501
    )
    firecracker.mechanics.append(
        MoveTargetAtAttackStart(
            Position(9.0, firecracker.position.y + hit_frame_reach)
        )
    )
    firecracker.target_id = target.id
    firecracker.attack_cooldown = 0.0

    firecracker.update_combat_component(battle.dt, battle)

    assert firecracker.position == start
    assert not firecracker.forced_movement_active
    assert not any(
        isinstance(entity, Projectile)
        and entity.source_entity is firecracker
        for entity in battle.entities.values()
    )
    assert not firecracker.card_stats.load_first_hit
    assert firecracker.attack_cooldown == pytest.approx(
        firecracker.get_base_attack_interval_seconds()
    )


def test_long_distance_guard_discards_the_entire_direct_area_payload():
    class MoveAreaAtAttackStart(BaseMechanic):
        def __init__(self, destination: Position, bystander: Troop):
            self.destination = destination
            self.bystander = bystander

        def on_attack_start(self, entity, target) -> None:
            target.position = self.destination
            self.bystander.position = Position(
                self.destination.x + 0.5,
                self.destination.y,
            )

    battle = BattleState()
    attacker = _spawn_one(battle, "DarkPrince", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Skeletons", 1, Position(9.0, 10.5))
    bystander = _spawn_one(battle, "Knight", 1, Position(1.0, 1.0))
    target_hp = target.hitpoints
    bystander_hp = bystander.hitpoints
    hit_frame_reach = attacker.get_effective_attack_range() + target.get_collision_radius() + 1.501
    attacker.mechanics.append(
        MoveAreaAtAttackStart(
            Position(9.0, attacker.position.y + hit_frame_reach),
            bystander,
        )
    )
    attacker.target_id = target.id
    attacker.attack_cooldown = 0.0

    attacker.update_combat_component(battle.dt, battle)

    assert target.hitpoints == target_hp
    assert bystander.hitpoints == bystander_hp
    assert not attacker.card_stats.load_first_hit
    assert attacker.attack_cooldown == pytest.approx(
        attacker.get_base_attack_interval_seconds()
    )


def test_area_payload_discard_is_governed_by_the_shared_global(monkeypatch):
    battle = BattleState()
    attacker = _spawn_one(battle, "DarkPrince", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Skeletons", 1, Position(9.0, 10.5))
    target.position = Position(
        9.0,
        attacker.position.y
        + attacker.get_effective_attack_range()
        + target.get_collision_radius()
        + 1.501,
    )

    assert attacker.should_cancel_committed_hit(target)

    monkeypatch.setattr(
        "clasher.entities.LOGIC_ALLOW_DISCARD_HIT_ON_AREA_DAMAGE",
        False,
    )
    assert not attacker.should_cancel_committed_hit(target)


def test_projectile_splash_discard_does_not_consult_direct_area_global(
    monkeypatch,
):
    battle = BattleState()
    attacker = _spawn_one(battle, "BabyDragon", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Skeletons", 1, Position(9.0, 10.5))
    target.position = Position(
        9.0,
        attacker.position.y
        + attacker.get_effective_attack_range()
        + target.get_collision_radius()
        + 1.501,
    )

    assert attacker.card_stats.projectile_splash_radius > 0
    assert attacker.should_cancel_committed_hit(target)

    monkeypatch.setattr(
        "clasher.entities.LOGIC_ALLOW_DISCARD_HIT_ON_AREA_DAMAGE",
        False,
    )
    assert attacker.should_cancel_committed_hit(target)


def test_native_death_spawn_distance_allowance_affects_reach_and_target_order():
    battle = BattleState()
    attacker = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    nearer = _spawn_one(battle, "Knight", 1, Position(8.9, 12.0))
    discounted = _spawn_one(battle, "Knight", 1, Position(9.1, 12.001))
    discounted._native_target_distance_discount_sq_units = 80**2

    # The second target is 1 logic unit farther by center distance, but native
    # subtracts the child's squared allowance before acquisition ranking.
    assert attacker.position.distance_to(nearer.position) < (
        attacker.position.distance_to(discounted.position)
    )
    assert attacker.get_nearest_target(battle.entities) is discounted
    attacker.target_id = nearer.id
    assert attacker._should_switch_target(nearer, discounted)

    battle.fast_path = True
    battle._refresh_fast_path_caches()
    assert attacker.get_nearest_target(battle.entities) is discounted

    discounted.position = Position(9.0, 11.701)
    battle._refresh_fast_path_caches()
    assert attacker.position.distance_to(discounted.position) > (
        attacker.range + discounted.get_collision_radius()
    )
    assert attacker.is_within_attack_reach(discounted)


def test_ordinary_buildings_receive_no_extra_sight_allowance():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 10.0),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    sight_edge = (
        knight.sight_range + knight.get_collision_radius()
        + cannon.get_collision_radius()
    )

    cannon.position = Position(9.0, 10.0 + sight_edge - 1e-6)
    assert knight.is_within_sight(cannon)
    assert not knight.is_within_attack_reach(cannon)
    cannon.position = Position(9.0, 10.0 + sight_edge + 1e-6)
    assert not knight.is_within_sight(cannon)


def test_crown_towers_receive_the_serialized_two_tile_sight_allowance():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    tower = next(
        entity
        for entity in battle.entities.values()
        if (
            isinstance(entity, Building)
            and entity.player_id == 1
            and entity.card_stats.name == "Tower"
        )
    )
    sight_edge = knight.sight_range + knight.get_collision_radius() + tower.get_collision_radius() + 2.0

    tower.position = Position(9.0, 10.0 + sight_edge - 1e-6)
    assert knight.is_within_sight(tower)
    tower.position = Position(9.0, 10.0 + sight_edge + 1e-6)
    assert not knight.is_within_sight(tower)


@pytest.mark.parametrize("fast_path", [False, True])
def test_target_geometry_is_governed_by_shared_current_client_globals(
    monkeypatch,
    fast_path,
):
    import clasher.entities as entity_module

    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 10.0),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    cannon.position = Position(
        9.0,
        10.0 + knight.sight_range + knight.get_collision_radius() + cannon.get_collision_radius() + 0.25,
    )

    if fast_path:
        battle._refresh_fast_path_caches()
    assert knight.get_nearest_target(
        battle.entities,
        include_crown_fallback=False,
    ) is None

    monkeypatch.setattr(entity_module, "EXTRA_SIGHT_RANGE_TO_BUILDING", 250)
    if fast_path:
        battle._refresh_fast_path_caches()
    assert knight.get_nearest_target(
        battle.entities,
        include_crown_fallback=False,
    ) is cannon

    reach_with_radius = knight.reach_distance_to(cannon, knight.range)
    monkeypatch.setattr(entity_module, "ADD_CHARACTER_RANGE_TO_RADIUS", False)
    assert knight.reach_distance_to(cannon, knight.range) == pytest.approx(
        reach_with_radius - cannon.get_collision_radius()
    )


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("player_id", [0, 1])
def test_directional_sight_clips_rear_and_side_but_not_forward(
    fast_path,
    player_id,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    giant = _spawn_one(battle, "Giant", player_id, Position(9.0, 14.0))
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 14.0),
        1 - player_id,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    sight_reach = giant.sight_range + giant.get_collision_radius() + cannon.get_collision_radius()
    rear_reach = sight_reach - giant.card_stats.sight_clip
    side_reach = sight_reach - giant.card_stats.sight_clip_side
    forward = 1.0 if player_id == 0 else -1.0

    def acquired_at(position):
        cannon.position = position
        if fast_path:
            battle._refresh_fast_path_caches()
        return giant.get_nearest_target(battle.entities)

    assert acquired_at(
        Position(9.0, 14.0 - forward * (rear_reach - 1e-6))
    ) is cannon
    assert acquired_at(
        Position(9.0, 14.0 - forward * (rear_reach + 1e-6))
    ) is not cannon
    assert acquired_at(
        Position(9.0, 14.0 + forward * (sight_reach - 1e-6))
    ) is cannon
    assert acquired_at(Position(9.0 + side_reach - 1e-6, 14.0)) is cannon
    assert acquired_at(Position(9.0 + side_reach + 1e-6, 14.0)) is not cannon


def test_directional_sight_clips_do_not_shorten_crown_tower_fallback():
    battle = BattleState()
    giant = _spawn_one(battle, "Giant", 0, Position(9.0, 14.0))
    tower = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 1
        and entity.card_stats.name == "Tower"
    )
    sight_reach = giant.sight_range + tower.get_collision_radius() + 1.0
    tower.position = Position(9.0, 14.0 - sight_reach + 1e-6)

    assert giant.is_within_sight(tower)


@pytest.mark.parametrize("player_id", [0, 1])
def test_moving_troops_receive_the_native_one_tile_rear_sight_clip(player_id):
    battle = BattleState()
    attacker = _spawn_one(battle, "Knight", player_id, Position(9.0, 14.0))
    target = _spawn_one(
        battle,
        "Knight",
        1 - player_id,
        Position(9.0, 14.0),
    )
    sight_reach = attacker.sight_range + attacker.get_collision_radius() + target.get_collision_radius()
    rear_reach = sight_reach - 1.0
    forward = 1.0 if player_id == 0 else -1.0

    assert attacker.card_stats.sight_clip == 1.0
    target.position = Position(
        9.0,
        14.0 - forward * (rear_reach + 1e-6),
    )
    assert not attacker.is_within_sight(target)
    target.position = Position(
        9.0,
        14.0 + forward * (sight_reach - 1e-6),
    )
    assert attacker.is_within_sight(target)


def test_same_tick_lethal_melee_hits_trade_between_eligible_components():
    for first_player in (0, 1):
        battle = BattleState()
        battle.entities.clear()
        battle.next_entity_id = 1
        first = _spawn_one(battle, "Knight", first_player, Position(9.0, 10.0))
        second = _spawn_one(
            battle,
            "Knight",
            1 - first_player,
            Position(9.0, 11.0),
        )
        first.hitpoints = first.damage
        second.hitpoints = second.damage
        first.attack_cooldown = 0.0
        second.attack_cooldown = 0.0

        battle.step()

        assert not first.is_alive
        assert not second.is_alive
        assert battle.entities == {}


def test_same_tick_committed_projectiles_trade_independent_of_entity_order():
    for first_player in (0, 1):
        battle = BattleState()
        battle.entities.clear()
        battle.next_entity_id = 1
        first = _spawn_one(battle, "Knight", first_player, Position(8.0, 10.0))
        second = _spawn_one(
            battle,
            "Knight",
            1 - first_player,
            Position(10.0, 10.0),
        )
        first.stun_timer = second.stun_timer = 10.0
        for owner, target in (
            (second.player_id, first),
            (first.player_id, second),
        ):
            projectile = Projectile(
                id=battle.next_entity_id,
                position=Position(target.position.x, target.position.y),
                player_id=owner,
                card_stats=None,
                hitpoints=1,
                max_hitpoints=1,
                damage=target.hitpoints,
                range=0.0,
                sight_range=0.0,
                target_position=Position(target.position.x, target.position.y),
                travel_speed=1.0,
                primary_target=target,
            )
            battle.entities[projectile.id] = projectile
            battle.next_entity_id += 1

        battle.step()

        assert not first.is_alive
        assert not second.is_alive
        assert battle.entities == {}


def test_committed_splash_snapshot_precedes_primary_target_death_knockback():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    valkyrie = _spawn_one(battle, "Valkyrie", 0, Position(9.0, 14.0))
    golem = _spawn_one(battle, "Golem", 1, Position(10.0, 14.0))
    secondary = _spawn_one(battle, "Knight", 1, Position(11.499, 14.0))
    golem.stun_timer = secondary.stun_timer = 10.0
    golem.hitpoints = valkyrie.damage
    valkyrie.attack_cooldown = 0.0
    secondary_hp = secondary.hitpoints

    battle.step()

    assert not golem.is_alive
    assert valkyrie.position.x < 9.0  # Golem's death nova displaced her.
    assert secondary.hitpoints == pytest.approx(secondary_hp - valkyrie.damage)


def test_wall_breaker_explosion_snapshot_precedes_victim_death_knockback():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    golem = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))
    secondary = _spawn_one(battle, "Knight", 1, Position(10.0, 14.0))
    wall_breaker = _spawn_one(battle, "Wallbreakers", 0, Position(9.0, 14.0))
    cannon = battle._spawn_entity(
        Building,
        Position(10.0, 14.0),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    golem.hitpoints = 1.0
    secondary_hp = secondary.hitpoints
    wall_breaker.attack_cooldown = 0.0

    battle.step()

    assert not wall_breaker.is_alive
    assert golem.is_alive
    battle.step()  # The committed projectile begins on the following frame.
    assert not golem.is_alive
    assert secondary.hitpoints == pytest.approx(secondary_hp - wall_breaker.damage)


def test_wall_breaker_splash_is_centered_on_its_committed_launch_position():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    wall_breaker = _spawn_one(battle, "Wallbreakers", 0, Position(9.0, 14.0))
    cannon = battle._spawn_entity(
        Building,
        Position(10.0, 14.0),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    behind = _spawn_one(battle, "Knight", 1, Position(7.9, 14.0))
    beyond = _spawn_one(battle, "Knight", 1, Position(11.999, 14.0))
    wall_breaker.position = Position(9.0, 14.0)
    cannon.position = Position(10.0, 14.0)
    behind.position = Position(7.9, 14.0)
    beyond.position = Position(11.999, 14.0)
    hp_before = (behind.hitpoints, beyond.hitpoints)
    wall_breaker.attack_cooldown = 0.0

    wall_breaker.update_combat_component(battle.dt, battle)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and entity.source_entity is wall_breaker
    )
    assert projectile.pierces
    assert projectile.splash_radius == pytest.approx(
        wall_breaker.card_stats.area_damage_radius / 1000.0
    )
    assert projectile.launch_position == wall_breaker.position
    assert projectile.launch_position.distance_to(
        projectile.target_position
    ) == pytest.approx(0.001)
    projectile.update(battle.dt, battle)

    assert behind.hitpoints == hp_before[0] - wall_breaker.damage
    assert beyond.hitpoints == hp_before[1]


def test_wall_breaker_committed_projectile_cannot_hit_birth_tick_death_spawns():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    wall_breaker = _spawn_one(
        battle,
        "Wallbreakers",
        0,
        Position(9.0, 14.0),
    )
    tombstone = battle._spawn_entity(
        Building,
        Position(10.0, 14.0),
        1,
        battle.card_loader.get_card("Tombstone"),
    )
    finisher = _spawn_one(
        battle,
        "MiniPekka",
        0,
        Position(10.0, 14.0),
    )
    tombstone.deploy_delay_remaining = 0.0
    tombstone.placement_pending = False
    wall_breaker.attack_cooldown = 0.0
    finisher.attack_cooldown = 0.0
    finisher.damage = 100_000.0
    tombstone.hitpoints = finisher.damage

    battle.step()

    # The Wall Breaker commits its one-unit projectile first. The later-ID
    # Mini P.E.K.K.A. then destroys Tombstone during the same combat phase,
    # and its four Skeletons are born before the projectile object ticks.
    # LOGIC_DEATH_SPAWN_IMMUNE_FIRST_TICK keeps the newly created children
    # immune to that already-committed splash when it ticks next frame.
    assert not wall_breaker.is_alive
    assert not tombstone.is_alive
    assert battle.next_entity_id == 9
    skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    ]
    assert len(skeletons) == 4
    assert all(skeleton.hitpoints == skeleton.max_hitpoints for skeleton in skeletons)
    assert any(isinstance(e, Projectile) for e in battle.entities.values())
    battle.step()
    assert all(skeleton.hitpoints == skeleton.max_hitpoints for skeleton in skeletons)
    assert list(battle.entities) == [finisher.id, *(skeleton.id for skeleton in skeletons)]


def test_electro_wizard_spawn_area_snapshot_precedes_victim_death_knockback():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    golem = _spawn_one(battle, "Golem", 1, Position(10.0, 14.0))
    secondary = _spawn_one(battle, "Knight", 1, Position(11.0, 14.0))
    golem.hitpoints = 1.0
    secondary_hp = secondary.hitpoints

    wizard = _spawn_one(
        battle,
        "ElectroWizard",
        0,
        Position(9.0, 14.0),
        resolve_spawn_payload=False,
    )
    spawn_area = next(
        mechanic
        for mechanic in wizard.mechanics
        if type(mechanic).__name__ == "SpawnAreaEffect"
    )
    area = next(
        target
        for target in battle.entities.values()
        if isinstance(target, AreaEffect) and target.card_stats is wizard.card_stats
    )
    area.update(battle.dt, battle)

    assert wizard.position.x == 9.0
    assert wizard._knockback_target is not None
    expected_damage = wizard.card_stats.get_scaled_stat(spawn_area.area_data["damage"])
    assert secondary.hitpoints == pytest.approx(secondary_hp - expected_damage)
    assert secondary.stun_timer == pytest.approx(
        spawn_area.area_data["buffTime"] / 1000.0
    )
    golemites = [
        target
        for target in battle.entities.values()
        if isinstance(target, Troop)
        and target.player_id == golem.player_id
        and target.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(target.hitpoints == target.max_hitpoints for target in golemites)
    assert all(
        target.stun_timer == pytest.approx(
            spawn_area.area_data["buffTime"] / 1000.0
        )
        for target in golemites
    )


def test_spawn_area_snapshot_precedes_victim_death_knockback():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    golem = _spawn_one(battle, "Golem", 1, Position(10.0, 14.0))
    secondary = _spawn_one(battle, "Knight", 1, Position(11.5, 14.0))
    golem.hitpoints = 1.0
    secondary_hp = secondary.hitpoints
    wizard = _spawn_one(
        battle,
        "IceWizard",
        0,
        Position(9.0, 14.0),
        resolve_spawn_payload=False,
    )
    spawn_area = next(
        mechanic
        for mechanic in wizard.mechanics
        if type(mechanic).__name__ == "SpawnAreaEffect"
    )
    area = next(
        target
        for target in battle.entities.values()
        if isinstance(target, AreaEffect) and target.card_stats is wizard.card_stats
    )
    area.update(battle.dt, battle)

    assert wizard.position.x == 9.0
    assert wizard._knockback_target is not None
    assert secondary.hitpoints == pytest.approx(
        secondary_hp - wizard.card_stats.get_scaled_stat(33)
    )
    assert secondary.slow_multiplier == 0.7
    golemites = [
        target
        for target in battle.entities.values()
        if isinstance(target, Troop)
        and target.player_id == golem.player_id
        and target.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(target.hitpoints == target.max_hitpoints for target in golemites)
    assert all(target.slow_multiplier == 0.7 for target in golemites)
    assert all(
        target.slow_timer == pytest.approx(
            spawn_area.area_data["buffTime"] / 1000.0
        )
        for target in golemites
    )


def test_ice_wizard_projectile_status_pass_excludes_active_lethal_death_spawns():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    wizard = _spawn_one(battle, "IceWizard", 0, Position(9.0, 12.0))
    golem = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))
    golem.hitpoints = wizard.damage

    wizard._create_projectile(golem, battle)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile) and entity.source_entity is wizard
    )
    projectile.position = Position(
        projectile.target_position.x,
        projectile.target_position.y,
    )
    projectile.update(battle.dt, battle)

    golemites = [
        target
        for target in battle.entities.values()
        if isinstance(target, Troop)
        and target.player_id == golem.player_id
        and target.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(target.hitpoints == target.max_hitpoints for target in golemites)
    assert all(target.slow_timer == 0.0 for target in golemites)
    assert all(target.slow_multiplier == 1.0 for target in golemites)


def test_ice_spirit_status_pass_excludes_active_lethal_death_spawns():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    spirit = _spawn_one(battle, "IceSpirit", 0, Position(9.0, 14.0))
    golem = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))
    golem.hitpoints = spirit.damage
    mechanic = next(
        mechanic
        for mechanic in spirit.mechanics
        if type(mechanic).__name__ == "IceSpiritFreeze"
    )

    mechanic._freeze(spirit, Position(9.0, 14.0))

    golemites = [
        target
        for target in battle.entities.values()
        if isinstance(target, Troop)
        and target.player_id == golem.player_id
        and target.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(target.hitpoints == target.max_hitpoints for target in golemites)
    assert all(target.stun_timer == 0.0 for target in golemites)


def test_death_spawn_target_immunity_uses_attack_finish_timer():
    battle = BattleState(fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, "Knight", 0, Position(9.0, 12.0))
    golem = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))

    golem.take_damage(golem.hitpoints)
    golemites = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == golem.player_id
        and entity.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(
        target._death_spawn_target_immunity_elapsed_ms == 0
        for target in golemites
    )
    assert all(not target.is_targetable_by(attacker.player_id) for target in golemites)
    assert all(
        not target.can_receive_area_damage("Test", source_entity=attacker)
        for target in golemites
    )
    assert all(target.can_receive_area_damage("Test") for target in golemites)

    # The native marker is not a generic damage/status invulnerability flag.
    for target in golemites:
        target.take_damage(10.0, source_kind="Test")
        target.apply_stun(0.5, source_kind="Test")
        target.apply_slow(0.5, 0.5, source_kind="Test")
    assert all(target.hitpoints == target.max_hitpoints - 10.0 for target in golemites)
    assert all(target.stun_timer == 0.5 for target in golemites)
    assert all(target.slow_timer == 0.5 for target in golemites)

    battle._refresh_fast_path_caches()
    for elapsed in range(50, GLOBAL_ATTACK_FINISH_TIME_MS + 1, 50):
        for target in golemites:
            target.tick_character_object_phase(battle.dt)
            index = battle._target_index_by_id[target.id]
            assert not bool(battle._target_is_targetable[index])
            assert target._death_spawn_target_immunity_elapsed_ms == elapsed
            assert not target.is_targetable_by(attacker.player_id)

    for target in golemites:
        target.tick_character_object_phase(battle.dt)
        index = battle._target_index_by_id[target.id]
        assert target._death_spawn_target_immunity_elapsed_ms == -1
        assert target.is_targetable_by(attacker.player_id)
        assert bool(battle._target_is_targetable[index])


def test_death_spawn_target_immunity_is_governed_by_shared_global(monkeypatch):
    import clasher.entities as entity_module

    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, "Knight", 0, Position(9.0, 12.0))
    golem = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))

    golem.take_damage(golem.hitpoints)
    golemites = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == golem.player_id
        and entity.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(not target.is_targetable_by(attacker.player_id) for target in golemites)
    assert all(
        not target.can_receive_area_damage("Test", source_entity=attacker)
        for target in golemites
    )

    monkeypatch.setattr(
        entity_module,
        "LOGIC_DEATH_SPAWN_IMMUNE_FIRST_TICK",
        False,
    )
    assert all(target.is_targetable_by(attacker.player_id) for target in golemites)
    assert all(
        target.can_receive_area_damage("Test", source_entity=attacker)
        for target in golemites
    )


def test_disabled_death_spawn_global_does_not_install_latent_marker(monkeypatch):
    import clasher.entities as entity_module

    monkeypatch.setattr(
        entity_module,
        "LOGIC_DEATH_SPAWN_IMMUNE_FIRST_TICK",
        False,
    )
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    golem = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))

    golem.take_damage(golem.hitpoints)
    golemites = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == golem.player_id
        and entity.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(
        target._death_spawn_target_immunity_elapsed_ms == -1
        for target in golemites
    )

    # Native decides whether to install the marker at creation time. Enabling
    # the global later cannot resurrect immunity on an already-created child.
    monkeypatch.setattr(
        entity_module,
        "LOGIC_DEATH_SPAWN_IMMUNE_FIRST_TICK",
        True,
    )
    assert all(not target._has_death_spawn_target_immunity() for target in golemites)


def test_sub_logic_unit_mirror_drift_cannot_change_reach_decisions():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    reach = knight.reach_distance_to(target, knight.range + knight.get_collision_radius())

    target.position = Position(9.0, 10.0 + reach + 2e-9)

    assert knight.is_within_attack_reach(target)

    target.position = Position(9.0, 10.0 + reach + 2e-6)
    assert not knight.is_within_attack_reach(target)


def test_existing_target_lock_has_native_25_unit_range_extension():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    reach = knight.reach_distance_to(target, knight.range + knight.get_collision_radius())

    target.position = Position(9.0, 10.0 + reach + 0.024)
    assert not knight.is_within_attack_reach(target)
    assert knight.is_within_target_keep_reach(target)

    target.position = Position(9.0, 10.0 + reach + 0.026)
    assert not knight.is_within_target_keep_reach(target)


def test_existing_target_lock_extension_is_governed_by_shared_global(monkeypatch):
    import clasher.entities as entity_module

    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    reach = knight.reach_distance_to(target, knight.range + knight.get_collision_radius())
    target.position = Position(9.0, 10.0 + reach + 0.001)

    assert knight.is_within_target_keep_reach(target)
    monkeypatch.setattr(entity_module, "LOGIC_RANGE_EXTENSION_TO_KEEP_TARGET", 0)
    assert not knight.is_within_target_keep_reach(target)


def test_started_attack_target_lock_has_native_500_unit_extension():
    battle = BattleState()
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    reach = musketeer.reach_distance_to(target, musketeer.range + musketeer.get_collision_radius())
    musketeer._attack_windup_active = True

    target.position = Position(9.0, 10.0 + reach + 0.499)
    assert not musketeer.is_within_attack_reach(target)
    assert musketeer.is_within_target_keep_reach(target)
    assert musketeer.is_within_attack_clock_reach(target)

    target.position = Position(9.0, 10.0 + reach + 0.501)
    assert not musketeer.is_within_target_keep_reach(target)
    assert musketeer.is_within_attack_clock_reach(target)


def test_started_projectile_lock_preservation_is_governed_by_shared_global(
    monkeypatch,
):
    import clasher.entities as entity_module

    battle = BattleState()
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    reach = musketeer.reach_distance_to(target, musketeer.range + musketeer.get_collision_radius())
    musketeer._attack_windup_active = True
    target.position = Position(9.0, 10.0 + reach + 0.1)

    assert musketeer.is_within_target_keep_reach(target)
    monkeypatch.setattr(
        entity_module,
        "LOGIC_PRESERVE_TARGET_IF_HIT_STARTED",
        False,
    )
    assert not musketeer.is_within_target_keep_reach(target)


@pytest.mark.parametrize(
    ("elapsed_ms", "preserves_target"),
    ((50, False), (51, True), (100, True)),
)
def test_projectile_target_preservation_uses_native_hit_cycle_phase(
    elapsed_ms,
    preserves_target,
):
    battle = BattleState()
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    reach = musketeer.reach_distance_to(target, musketeer.range + musketeer.get_collision_radius())
    target.position = Position(9.0, 10.0 + reach + 0.1)
    musketeer._attack_windup_active = False
    musketeer._has_attacked_once = True  # Simulate an already running hit cycle.
    musketeer.attack_cooldown = (
        musketeer.get_base_attack_interval_seconds() - elapsed_ms / 1000.0
    )

    assert musketeer.has_started_projectile_hit_cycle() is preserves_target
    assert musketeer.is_within_target_keep_reach(target) is preserves_target
    assert musketeer.is_within_attack_clock_reach(target) is preserves_target


def test_hit_cycle_preservation_requires_combat_component_global(monkeypatch):
    import clasher.entities as entity_module

    battle = BattleState()
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    musketeer._has_attacked_once = True  # Simulate an already running hit cycle.
    musketeer.attack_cooldown = (
        musketeer.get_base_attack_interval_seconds() - 0.1
    )

    assert musketeer.has_started_projectile_hit_cycle()
    monkeypatch.setattr(entity_module, "COMBAT_CMP_USE_HIT_STARTED", False)
    assert not musketeer.has_started_projectile_hit_cycle()


def test_overloaded_retarget_clock_maps_to_zero_preservation_phase():
    battle = BattleState()
    dragon = _spawn_one(battle, "InfernoDragon", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    reach = dragon.reach_distance_to(target, dragon.range + dragon.get_collision_radius())
    target.position = Position(9.0, 10.0 + reach + 0.1)
    dragon._attack_windup_active = False
    dragon.attack_cooldown = dragon.card_stats.retarget_time / 1000.0

    assert dragon.card_stats.retarget_time == 800
    assert dragon.card_stats.hit_speed == 400
    assert not dragon.has_started_projectile_hit_cycle()
    assert not dragon.is_within_target_keep_reach(target)


def test_started_direct_attack_keeps_only_native_25_unit_extension():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    reach = knight.reach_distance_to(target, knight.range + knight.get_collision_radius())
    knight._attack_windup_active = True

    target.position = Position(9.0, 10.0 + reach + 0.024)
    assert knight.is_within_target_keep_reach(target)
    assert knight.is_within_attack_clock_reach(target)

    target.position = Position(9.0, 10.0 + reach + 0.026)
    assert not knight.is_within_target_keep_reach(target)
    assert knight.is_within_attack_clock_reach(target)


@pytest.mark.parametrize("fast_path", [False, True])
def test_pending_target_removal_preserves_preload_without_committing_next_target(fast_path):
    battle = BattleState(fast_path=fast_path)
    archer = _spawn_one(battle, "Archers", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 12.0))
    archer.target_id = target.id
    archer._last_combat_target_id = target.id
    archer._combat_target_pending_lethal = True
    archer._attack_windup_active = True
    archer._has_attacked_once = True
    archer.attack_cooldown = 0.3

    archer.on_combat_target_removed(target.id)

    assert archer._attack_finish_elapsed_ms == 0
    assert archer.attack_cooldown == pytest.approx(0.3)
    assert not archer._attack_windup_active
    assert not archer._has_attacked_once
    reach = archer.reach_distance_to(target, archer.get_effective_attack_range())
    target.position = Position(9.0, 10.0 + reach + 0.1)
    assert not archer.is_within_target_keep_reach(target)
    assert not archer.is_within_attack_clock_reach(target)


def test_started_projectile_attack_finishes_inside_native_500_unit_leash():
    battle = BattleState()
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    reach = musketeer.reach_distance_to(target, musketeer.range + musketeer.get_collision_radius())
    target.position = Position(9.0, 10.0 + reach + 0.499)
    musketeer.target_id = target.id
    musketeer.attack_cooldown = battle.dt
    musketeer._attack_windup_active = True

    musketeer.update_combat_component(battle.dt, battle)

    assert any(
        isinstance(entity, Projectile)
        and entity.source_entity is musketeer
        for entity in battle.entities.values()
    )
    assert musketeer.attack_cooldown == pytest.approx(
        musketeer.get_base_attack_interval_seconds()
    )


@pytest.mark.parametrize("fast_path", [False, True])
def test_spawned_allies_cannot_break_witch_crown_tower_windup(fast_path):
    battle = BattleState(fast_path=fast_path)
    tower = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 1
        and entity.card_stats.name == "Tower"
        and entity.position.x < 9.0
    )
    witch = _spawn_one(battle, "Witch", 0, Position(3.5, 18.5))
    spawned_skeleton = _spawn_one(
        battle,
        "Skeletons",
        0,
        Position(3.5, 18.9),
    )
    distraction = _spawn_one(
        battle,
        "Knight",
        1,
        Position(5.5, 18.5),
    )
    witch.speed = 0.0
    spawned_skeleton.position = Position(3.5, 18.9)
    spawned_skeleton.apply_stun(99.0)
    distraction.apply_stun(99.0)
    witch.target_id = tower.id
    witch.attack_cooldown = 0.4
    witch._attack_windup_active = True
    battle.sync_fast_target_entity(witch)
    battle.sync_fast_target_entity(spawned_skeleton)
    battle.sync_fast_target_entity(distraction)

    assert witch.is_within_attack_reach(tower)
    battle.step()
    assert not witch.is_within_attack_reach(tower)
    assert witch.is_within_target_keep_reach(tower)

    for _ in range(7):
        battle.step()

    assert witch.target_id == tower.id
    assert any(
        isinstance(entity, Projectile)
        and entity.source_entity is witch
        for entity in battle.entities.values()
    )


@pytest.mark.parametrize("fast_path", [False, True])
def test_sub_nanotile_distance_ties_preserve_target_insertion_order(fast_path):
    battle = BattleState(fast_path=fast_path)
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(
        Building,
        Position(6.5, 16.5),
        1,
        cannon_stats,
    )
    first = _spawn_one(
        battle,
        "Knight",
        0,
        Position(4.2041812914724686, 14.650596356494555),
    )
    _spawn_one(
        battle,
        "Knight",
        0,
        Position(3.7180204500870477, 15.524465703882035),
    )
    if fast_path:
        battle._refresh_fast_path_caches()

    assert cannon.get_nearest_target(battle.entities) is first


@pytest.mark.parametrize("fast_path", [False, True])
def test_equal_distance_character_precedes_building_in_native_target_order(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    attacker = _spawn_one(battle, "GoblinGang", 1, Position(5.5, 9.921))
    tower = battle.entities[1]
    troop = _spawn_one(battle, "Princess", 0, Position(7.5, 6.5))
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    tower.position = Position(3.5, 6.5)
    if fast_path:
        battle._refresh_fast_path_caches()

    assert attacker.native_target_distance_to(tower) == pytest.approx(
        attacker.native_target_distance_to(troop)
    )
    assert attacker.get_nearest_target(battle.entities) is troop


@pytest.mark.parametrize("fast_path", [False, True])
def test_centered_crown_tower_target_ties_keep_native_candidate_order(fast_path):
    upper_battle = BattleState(fast_path=fast_path)
    lower_battle = BattleState(fast_path=fast_path)
    # Keep the two Princess Towers equally distant and nearer than the King.
    upper = _spawn_one(upper_battle, "Archers", 1, Position(9.0, 10.0))
    lower = _spawn_one(lower_battle, "Archers", 0, Position(9.0, 22.0))
    for battle, attacker in ((upper_battle, upper), (lower_battle, lower)):
        candidates = [
            entity for entity in battle.entities.values()
            if isinstance(entity, Building)
            and entity.player_id != attacker.player_id
            and entity.card_stats.name == "Tower"
        ]
        assert len(candidates) == 2
        assert attacker.native_target_distance_to(candidates[0]) == pytest.approx(
            attacker.native_target_distance_to(candidates[1])
        )
    if fast_path:
        upper_battle._refresh_fast_path_caches()
        lower_battle._refresh_fast_path_caches()

    upper_target = upper.get_nearest_target(upper_battle.entities)
    lower_target = lower.get_nearest_target(lower_battle.entities)

    assert isinstance(upper_target, Building)
    assert isinstance(lower_target, Building)
    assert upper_target.card_stats.name == "Tower"
    assert lower_target.card_stats.name == "Tower"
    assert upper_target.position.x == pytest.approx(14.5)
    assert lower_target.position.x == pytest.approx(3.5)


@pytest.mark.parametrize("fast_path", [False, True])
def test_equal_distance_building_ties_use_rotationally_symmetric_iteration(
    fast_path,
):
    selected_x = []
    for player_id, attacker_y, building_y in (
        (0, 10.0, 14.0),
        (1, 22.0, 18.0),
    ):
        battle = BattleState(fast_path=fast_path)
        attacker = _spawn_one(
            battle,
            "Giant",
            player_id,
            Position(9.0, attacker_y),
        )
        cannon_stats = battle.card_loader.get_card("Cannon")
        assert cannon_stats is not None
        for x in (7.0, 11.0):
            cannon = battle._spawn_entity(
                Building,
                Position(x, building_y),
                1 - player_id,
                cannon_stats,
            )
            cannon.deploy_delay_remaining = 0.0
            cannon.placement_pending = False
            cannon.on_spawn()
        if fast_path:
            battle._refresh_fast_path_caches()

        target = attacker.get_nearest_target(battle.entities)
        assert isinstance(target, Building)
        assert target.card_stats.name == "Cannon"
        selected_x.append(target.position.x)

    assert selected_x == [7.0, 11.0]


@pytest.mark.parametrize("fast_path", [False, True])
def test_destroyed_princess_tower_fallback_keeps_king_on_open_lane(fast_path):
    cases = (
        # player, destroyed enemy lane, open-lane start, surviving-lane start
        (0, 3.5, Position(3.5, 10.0), Position(14.5, 10.0)),
        (1, 14.5, Position(14.5, 22.0), Position(3.5, 22.0)),
    )
    for player_id, destroyed_x, open_start, surviving_start in cases:
        battle = BattleState(fast_path=fast_path)
        enemy_id = 1 - player_id
        destroyed = next(
            entity
            for entity in battle.entities.values()
            if (
                isinstance(entity, Building)
                and entity.player_id == enemy_id
                and entity.card_stats.name == "Tower"
                and entity.position.x == destroyed_x
            )
        )
        destroyed.take_damage(destroyed.hitpoints)
        open_lane_troop = _spawn_one(battle, "Knight", player_id, open_start)
        surviving_lane_troop = _spawn_one(
            battle,
            "Knight",
            player_id,
            surviving_start,
        )
        if fast_path:
            battle._refresh_fast_path_caches()

        open_target = open_lane_troop.get_nearest_target(battle.entities)
        surviving_target = surviving_lane_troop.get_nearest_target(battle.entities)

        assert isinstance(open_target, Building)
        assert open_target.card_stats.name == "KingTower"
        assert open_target.position.x == pytest.approx(9.0)
        assert isinstance(surviving_target, Building)
        assert surviving_target.card_stats.name == "Tower"
        assert surviving_target.position.x == pytest.approx(18.0 - destroyed_x)


@pytest.mark.parametrize("fast_path", [False, True])
def test_default_princess_candidate_competes_against_closer_king(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    attacker = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    destroyed = next(
        entity
        for entity in battle.entities.values()
        if (
            isinstance(entity, Building)
            and entity.player_id == 1
            and entity.card_stats.name == "Tower"
            and entity.position.x == 3.5
        )
    )
    destroyed.take_damage(destroyed.hitpoints)
    king = next(
        entity
        for entity in battle.entities.values()
        if (
            isinstance(entity, Building)
            and entity.player_id == 1
            and entity.card_stats.name == "KingTower"
        )
    )
    surviving = next(
        entity
        for entity in battle.entities.values()
        if (
            isinstance(entity, Building)
            and entity.player_id == 1
            and entity.card_stats.name == "Tower"
            and entity.is_alive
        )
    )

    # Isolate the infinite-sight fallback and make the King geometrically
    # closer. Native f5e5a4 compares the candidate against the King baseline.
    attacker.sight_range = 0.0
    king.position = Position(9.0, 20.0)
    surviving.position = Position(14.5, 25.5)
    if fast_path:
        battle._refresh_fast_path_caches()

    assert attacker.native_target_distance_to(king) < attacker.native_target_distance_to(
        surviving
    )
    assert attacker.get_nearest_target(battle.entities) is king

    # Ordinary sight acquisition remains independent of fallback selection.  A King Tower that is actually
    # inside sight range remains an ordinary valid building target.
    attacker.sight_range = 20.0
    assert attacker.get_nearest_target(battle.entities) is king


@pytest.mark.parametrize("fast_path", [False, True])
def test_ground_default_target_uses_current_x_after_cross_lane_displacement(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    giant = _spawn_one(battle, "Giant", 0, Position(3.5, 10.0))
    assert giant._native_lane_id == 1
    giant.position = Position(14.5, 10.0)
    giant._native_deployed_elapsed_ms = 500
    if fast_path:
        battle._refresh_fast_path_caches()

    target = giant.get_nearest_target(battle.entities)

    assert isinstance(target, Building)
    assert target.card_stats.name == "Tower"
    assert target.position.x == pytest.approx(14.5)


@pytest.mark.parametrize("fast_path", [False, True])
def test_ground_open_lane_default_keeps_king_after_displacement(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    giant = _spawn_one(battle, "Giant", 0, Position(3.5, 10.0))
    destroyed = next(
        entity
        for entity in battle.entities.values()
        if (
            isinstance(entity, Building)
            and entity.player_id == 1
            and entity.card_stats.name == "Tower"
            and entity.position.x == 3.5
        )
    )
    destroyed.take_damage(destroyed.hitpoints)
    giant.position = Position(14.5, 10.0)
    giant._native_deployed_elapsed_ms = 500
    if fast_path:
        battle._refresh_fast_path_caches()

    target = giant.get_nearest_target(battle.entities)

    assert isinstance(target, Building)
    assert target.card_stats.name == "KingTower"
    assert target.position.x == pytest.approx(9.0)


@pytest.mark.parametrize("fast_path", [False, True])
def test_flying_default_target_uses_current_x_instead_of_spawn_lane(fast_path):
    battle = BattleState(fast_path=fast_path)
    hound = _spawn_one(battle, "LavaHound", 0, Position(3.5, 10.0))
    assert hound._native_lane_id == 1
    hound.position = Position(14.5, 10.0)
    hound._native_deployed_elapsed_ms = 500
    if fast_path:
        battle._refresh_fast_path_caches()

    target = hound.get_nearest_target(battle.entities)

    assert isinstance(target, Building)
    assert target.card_stats.name == "Tower"
    assert target.position.x == pytest.approx(14.5)


@pytest.mark.parametrize("fast_path", [False, True])
def test_hovering_default_target_uses_current_x_instead_of_spawn_lane(fast_path):
    battle = BattleState(fast_path=fast_path)
    ghost = _spawn_one(battle, "RoyalGhost", 0, Position(3.5, 10.0))
    assert ghost._native_lane_id == 1
    ghost.position = Position(14.5, 10.0)
    ghost._native_deployed_elapsed_ms = 500
    if fast_path:
        battle._refresh_fast_path_caches()

    target = ghost.get_nearest_target(battle.entities)

    assert isinstance(target, Building)
    assert target.card_stats.name == "Tower"
    assert target.position.x == pytest.approx(14.5)


@pytest.mark.parametrize("pierces", [False, True])
def test_sub_nanotile_projectile_endpoint_drift_cannot_add_a_flight_tick(pierces):
    battle = BattleState()
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(8.0, 10.0),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=0,
        sight_range=0,
        target_position=Position(9.0000000005, 10.0),
        travel_speed=1.0,
        pierces=pierces,
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1

    projectile.update(1.0, battle)

    assert not projectile.is_alive
    if pierces:
        assert projectile.position.x == pytest.approx(projectile.target_position.x)


@pytest.mark.parametrize(
    ("player_id", "start", "target_position"),
    (
        (0, Position(5.0, 10.0), Position(8.0, 14.0)),
        (1, Position(13.0, 22.0), Position(10.0, 18.0)),
    ),
)
def test_diagonal_troop_movement_uses_native_integer_components(
    player_id,
    start,
    target_position,
):
    battle = BattleState()
    mover = _spawn_one(battle, "Knight", player_id, start)
    target = _spawn_one(battle, "Knight", 1 - player_id, target_position)

    waypoint = ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
    )
    expected_delta_units = movement_component_vector_logic_units(
        tiles_to_logic_units(waypoint.x - start.x),
        tiles_to_logic_units(waypoint.y - start.y),
        speed_work_for_duration(mover.speed, battle.dt),
    )

    mover._move_towards_target(target, battle.dt, battle)

    assert mover.position == Position(
        start.x + logic_units_to_tiles(expected_delta_units[0]),
        start.y + logic_units_to_tiles(expected_delta_units[1]),
    )


@pytest.mark.parametrize("fast_path", [False, True])
def test_ground_pathfinder_turns_before_reaching_an_intervening_building(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 0

    troop = _spawn_one(battle, "Knight", 0, Position(9.25, 10.25))
    target = _spawn_one(battle, "Knight", 1, Position(9.25, 20.25))
    target.position = Position(9.25, 15.25)
    building = battle._spawn_entity(
        Building,
        Position(9.25, 12.75),
        0,
        battle.card_loader.get_card("Cannon"),
    )
    building.deploy_delay_remaining = 0.0
    building.placement_pending = False
    building.on_spawn()
    if fast_path:
        battle._refresh_fast_path_caches()

    initial_x = troop.position.x
    first_turn_distance = None
    for _ in range(30):
        _run_natural_movement_component(battle, troop, target)
        if first_turn_distance is None and troop.position.x != pytest.approx(initial_x):
            first_turn_distance = troop.position.distance_to(building.position)

    # Routing and retained-heading avoidance both anticipate the building;
    # steering must begin before collision observes physical overlap.
    assert first_turn_distance is not None
    assert first_turn_distance > (
        troop.card_stats.collision_radius
        + building.card_stats.collision_radius
    )
    assert troop.position.y > 10.25


@pytest.mark.parametrize("fast_path", [False, True])
def test_ground_pathfinder_routes_around_overlapping_building_obstacles(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 0
    troop = _spawn_one(battle, "Knight", 0, Position(9.25, 8.75))
    target = _spawn_one(battle, "Knight", 1, Position(9.25, 20.25))
    target.position = Position(9.25, 14.25)
    cannon_stats = battle.card_loader.get_card("Cannon")
    buildings = [
        battle._spawn_entity(
            Building,
            Position(building_x, 11.75),
            0,
            cannon_stats,
        )
        for building_x in (8.75, 9.75)
    ]
    for building in buildings:
        building.deploy_delay_remaining = 0.0
        building.placement_pending = False
        building.on_spawn()
    if fast_path:
        battle._refresh_fast_path_caches()

    max_lateral_offset = 0.0
    for _ in range(240):
        _run_natural_movement_component(battle, troop, target)
        max_lateral_offset = max(
            max_lateral_offset,
            abs(troop.position.x - 9.25),
        )
        if troop.is_within_attack_engagement_reach(target):
            break

    assert max_lateral_offset > 0.2
    assert troop.is_within_attack_engagement_reach(target)
    assert troop.position.y > max(building.position.y for building in buildings)


@pytest.mark.parametrize("fast_path", [False, True])
def test_building_targeter_routes_around_friendly_building_to_attack(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 0
    giant = _spawn_one(battle, "Giant", 0, Position(9.25, 8.75))
    cannon_stats = battle.card_loader.get_card("Cannon")
    friendly = battle._spawn_entity(
        Building,
        Position(9.25, 11.75),
        0,
        cannon_stats,
    )
    target = battle._spawn_entity(
        Building,
        Position(9.25, 14.25),
        1,
        cannon_stats,
    )
    for building in (friendly, target):
        building.deploy_delay_remaining = 0.0
        building.placement_pending = False
        building.on_spawn()
    if fast_path:
        battle._refresh_fast_path_caches()

    max_lateral_offset = 0.0
    for _ in range(240):
        if giant.is_within_attack_engagement_reach(target):
            break
        _run_natural_movement_component(battle, giant, target)
        max_lateral_offset = max(
            max_lateral_offset,
            abs(giant.position.x - 9.25),
        )

    assert max_lateral_offset > 0.2
    assert giant.is_within_attack_engagement_reach(target)


@pytest.mark.parametrize("fast_path", [False, True])
def test_hovering_ground_troop_passes_through_buildings_without_detouring(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 0
    ghost = _spawn_one(battle, "RoyalGhost", 0, Position(9.25, 10.25))
    target = _spawn_one(battle, "Knight", 1, Position(9.25, 20.25))
    target.position = Position(9.25, 14.25)
    cannon = battle._spawn_entity(
        Building,
        Position(9.25, 12.25),
        0,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    cannon.on_spawn()

    initial_x = ghost.position.x
    minimum_distance = float("inf")
    for _ in range(30):
        ghost._move_towards_target(target, battle.dt, battle)
        minimum_distance = min(
            minimum_distance,
            ghost.position.distance_to(cannon.position),
        )

    assert ghost.position.x == pytest.approx(initial_x)
    assert minimum_distance < (
        ghost.get_collision_radius() + cannon.get_collision_radius()
    )


def test_ground_pathfinder_uses_native_world_scan_for_displaced_river_target():
    lower = BattleState()
    upper = BattleState()
    lower.entities.clear()
    upper.entities.clear()
    lower.next_entity_id = upper.next_entity_id = 0
    lower_troop = _spawn_one(lower, "Knight", 0, Position(9.25, 14.0))
    lower_target = _spawn_one(lower, "Knight", 1, Position(9.25, 20.25))
    lower_target.position = Position(9.25, 15.5)
    upper_troop = _spawn_one(upper, "Knight", 1, Position(8.75, 18.0))
    upper_target = _spawn_one(upper, "Knight", 0, Position(8.75, 11.75))
    upper_target.position = Position(8.75, 16.5)

    # Serialized 1.2 range plus the mover's 0.5 radius selects these dry cells.
    assert native_route_goal_cell(lower_troop, lower_target) == (18, 28)
    assert native_route_goal_cell(upper_troop, upper_target) == (17, 35)
    # Both displaced targets are already in attack reach. Combat would not
    # force thirty movement calls through a target as the old fixture did.
    assert lower_troop.is_within_attack_engagement_reach(lower_target)
    assert upper_troop.is_within_attack_engagement_reach(upper_target)


def test_native_ground_route_retains_and_consumes_one_cell_per_frame():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 0
    mover = _spawn_one(battle, "Knight", 0, Position(9.25, 8.75))
    target = _spawn_one(battle, "Knight", 1, Position(9.25, 14.25))

    first = ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
    )
    retained_before = list(mover._native_ground_route_cells)
    mover._move_towards_target(target, battle.dt, battle)
    second = ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
    )

    assert first == Position(9.25, 9.25)
    assert retained_before[:2] == [(18, 18), (18, 19)]
    assert mover._native_ground_route_cells == retained_before[1:]
    assert second == Position(9.25, 9.75)


def test_native_flying_route_rebuilds_its_consumed_range_goal():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 0
    mover = _spawn_one(battle, "BabyDragon", 0, Position(2.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(4.0, 14.0))

    mover._move_towards_target(target, battle.dt, battle)

    assert mover.position == Position(2.085, 10.028)
    assert mover._native_ground_route_cells == []
    assert native_single_node_waypoint(mover, target) == Position(2.75, 10.25)


def test_native_pathfinder_boundary_division_and_heap_ties_are_world_relative():
    assert _cell_for_position(Position(8.5, 14.9)) == (17, 29)
    assert _cell_for_position(Position(9.5, 17.1)) == (19, 34)

    def in_bounds(cell):
        return 0 <= cell[0] < 5 and 0 <= cell[1] < 5

    obstacle = (2, 1)
    lower_route = _native_grid_route(
        (2, 2),
        (2, 0),
        lambda cell: 20 if in_bounds(cell) and cell != obstacle else None,
    )
    upper_route = _native_grid_route(
        (2, 0),
        (2, 2),
        lambda cell: 20 if in_bounds(cell) and cell != obstacle else None,
    )

    # Native neighbor insertion plus the priority-only binary heap selects
    # these opposite lateral ties; no secondary h-score or owner transform is
    # involved.
    assert lower_route == [(2, 2), (3, 1), (2, 0)]
    assert upper_route == [(2, 0), (1, 1), (2, 2)]


@pytest.mark.parametrize("rotation", (1.0, -1.0))
def test_diagonal_projectile_movement_uses_native_integer_components(rotation):
    start = Position(5.0 if rotation > 0 else 13.0, 10.0 if rotation > 0 else 22.0)
    target = Position(start.x + 3.0 * rotation, start.y + 4.0 * rotation)
    projectile = Projectile(
        id=1,
        position=Position(start.x, start.y),
        player_id=0 if rotation > 0 else 1,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=0,
        sight_range=0,
        target_position=target,
        # 20 tiles/second is the runtime representation of native Speed=1000.
        travel_speed=20.0,
    )

    projectile._move_towards(target, 0.05)

    assert projectile.position == Position(
        start.x + 0.6 * rotation,
        start.y + 0.8 * rotation,
    )


def test_fixed_point_path_validation_matches_fast_path_at_bridge_edges():
    normal = BattleState(rng=random.Random(0))
    accelerated = BattleState(rng=random.Random(0), fast_path=True)
    for battle in (normal, accelerated):
        battle.entities.clear()
        battle.next_entity_id = 1
        battle._refresh_fast_path_caches()

    for battle in (normal, accelerated):
        battle._spawn_troop(
            Position(8.5, 14.5),
            0,
            battle.card_loader.get_card("GoblinGang"),
        )
        battle._spawn_troop(
            Position(9.5, 17.5),
            1,
            battle.card_loader.get_card("Princess"),
        )

    for _ in range(90):
        normal.step()
        accelerated.step()

    assert normal.entities.keys() == accelerated.entities.keys()
    for entity_id, entity in normal.entities.items():
        fast_entity = accelerated.entities[entity_id]
        assert entity.position == fast_entity.position
        assert entity.hitpoints == fast_entity.hitpoints


def test_projectile_tracks_a_destroyed_targets_final_position_without_damaging_it():
    battle = BattleState()
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=battle.card_loader.get_card("Musketeer"),
        hitpoints=1,
        max_hitpoints=1,
        damage=100,
        range=0,
        sight_range=0,
        target_position=Position(9.0, 14.0),
        travel_speed=1.0,
        primary_target=target,
        tracks_target=True,
    )
    target.take_damage(target.hitpoints)
    target.position = Position(10.0, 15.0)

    projectile.update(battle.dt, battle)

    assert projectile.target_position == Position(10.0, 15.0)
    assert target.hitpoints == 0


def test_nearest_valid_spawn_ties_rotate_with_player_perspective():
    lower_battle = BattleState()
    upper_battle = BattleState()
    tesla_stats = lower_battle.card_loader.get_card("Tesla")
    assert tesla_stats is not None

    lower_battle._spawn_entity(
        Building,
        Position(9.5, 17.5),
        1,
        tesla_stats,
    )
    upper_battle._spawn_entity(
        Building,
        Position(8.5, 14.5),
        0,
        tesla_stats,
    )

    lower = lower_battle._snap_to_valid_position(
        Position(9.188744074384672, 18.046232223154032),
        0,
        mover_radius=0.3,
    )
    upper = upper_battle._snap_to_valid_position(
        Position(8.811255925615328, 13.953767776845968),
        1,
        mover_radius=0.3,
    )

    assert upper.x == pytest.approx(18.0 - lower.x)
    assert upper.y == pytest.approx(32.0 - lower.y)


def test_nearest_valid_spawn_ulp_ties_keep_owner_relative_search_order():
    battle = BattleState()
    upper_input = Position(0.7556581667634957, 17.997367332946016)
    lower_input = Position(18.0 - upper_input.x, 32.0 - upper_input.y)

    upper = battle._snap_to_valid_position(upper_input, 1, mover_radius=0.5)
    lower = battle._snap_to_valid_position(lower_input, 0, mover_radius=0.5)

    assert upper.x == pytest.approx(18.0 - lower.x)
    assert upper.y == pytest.approx(32.0 - lower.y)
    assert upper.x == pytest.approx(upper_input.x + 0.5)
    assert upper.y == pytest.approx(upper_input.y)


def test_tower_footprint_boundary_ulp_drift_blocks_both_player_mirrors():
    battle = BattleState()
    upper = Position(14.5, 24.00000000000002)
    lower = Position(18.0 - upper.x, 32.0 - upper.y)

    assert battle.arena.is_tower_tile(upper, battle)
    assert battle.arena.is_tower_tile(lower, battle)

    upper_spawn = battle._snap_to_valid_position(upper, 1, mover_radius=0.5)
    lower_spawn = battle._snap_to_valid_position(lower, 0, mover_radius=0.5)
    assert upper_spawn.x == pytest.approx(18.0 - lower_spawn.x)
    assert upper_spawn.y == pytest.approx(32.0 - lower_spawn.y)


def test_both_river_edges_have_rotationally_symmetric_walkability():
    battle = BattleState()

    for x in (9.0, 3.5):
        lower = Position(x, battle.arena.RIVER_Y1)
        upper = Position(18.0 - x, battle.arena.RIVER_Y2 + 1.0)
        assert battle.arena.is_walkable(lower) == battle.arena.is_walkable(upper)

    assert not battle.arena.is_walkable(Position(9.0, 15.0))
    assert not battle.arena.is_walkable(Position(9.0, 17.0))
    assert battle.arena.is_walkable(Position(9.0, 14.999))
    assert battle.arena.is_walkable(Position(9.0, 17.001))


def test_tile_and_bridge_boundaries_rotate_without_half_open_artifacts():
    battle = BattleState()

    for x_half in range(1, 36):
        for y_half in range(1, 64):
            position = Position(x_half / 2.0, y_half / 2.0)
            mirrored = Position(18.0 - position.x, 32.0 - position.y)
            assert battle.arena.is_walkable(position) == battle.arena.is_walkable(
                mirrored
            )

    assert not battle.arena.is_walkable(Position(2.5, 1.0))
    assert not battle.arena.is_walkable(Position(15.5, 31.0))
    assert battle.arena.is_walkable(Position(2.0, 16.0))
    assert battle.arena.is_walkable(Position(16.0, 16.0))


@pytest.mark.parametrize(
    ("position", "expected_path_id"),
    [
        (Position(3.5, 16.0), 1),
        (Position(14.5, 16.0), 2),
        (Position(8.999, 14.0), 1),
        # The native x-major scan reaches path 2 first at the exact center
        # because coordinates are quantized to half-tile cells.
        (Position(9.0, 14.0), 2),
    ],
)
def test_standard_arena_path_ids_use_the_native_half_tile_map(
    position,
    expected_path_id,
):
    assert BattleState().arena.native_path_id_at(position) == expected_path_id


def test_native_child_terrain_uses_the_tilemap_obstruction_channel():
    battle = BattleState()
    child_stats = battle.card_loader.get_card("Skeletons")
    assert child_stats is not None

    # A half-tile-radius child must fit wholly inside the map's two bridge
    # openings. Ordinary arena fence/deploy restrictions are a different
    # channel and are deliberately absent from this native child check.
    assert not battle._is_native_child_spawn_point(
        Position(2.5, 16.0),
        child_stats,
    )
    assert battle._is_native_child_spawn_point(
        Position(3.0, 16.0),
        child_stats,
    )
    assert battle._is_native_child_spawn_point(
        Position(4.0, 16.0),
        child_stats,
    )
    assert not battle._is_native_child_spawn_point(
        Position(4.5, 16.0),
        child_stats,
    )
    assert battle._is_native_child_spawn_point(
        Position(0.5, 0.5),
        child_stats,
    )


def test_outer_row_mixed_swarm_positions_are_exact_river_reflections():
    lower = BattleState()
    upper = BattleState()
    stats = lower.card_loader.get_card("GoblinGang")
    assert stats is not None

    lower.entities.clear()
    upper.entities.clear()
    lower.next_entity_id = upper.next_entity_id = 0
    lower._spawn_troop(Position(11.5, 0.5), 0, stats)
    upper._spawn_troop(Position(11.5, 31.5), 1, stats)

    lower_units = sorted(
        (
            entity.card_stats.name,
            entity.deploy_delay_remaining,
            entity.position.x,
            entity.position.y,
        )
        for entity in lower.entities.values()
        if isinstance(entity, Troop)
    )
    upper_units = sorted(
            (
                entity.card_stats.name,
                entity.deploy_delay_remaining,
                entity.position.x,
                32.0 - entity.position.y,
        )
        for entity in upper.entities.values()
        if isinstance(entity, Troop)
    )

    assert len(lower_units) == len(upper_units)
    for lower_unit, upper_unit in zip(lower_units, upper_units):
        assert lower_unit[:2] == upper_unit[:2]
        assert lower_unit[2:] == pytest.approx(upper_unit[2:])


def test_tied_bridge_routes_use_rotationally_symmetric_player_relative_lane():
    battle = BattleState()
    lower = _spawn_one(battle, "IceSpirit", 0, Position(8.0, 14.0))
    upper = _spawn_one(battle, "IceSpirit", 1, Position(10.0, 18.0))
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    upper_target = battle._spawn_entity(
        Building,
        Position(10.0, 18.0),
        1,
        cannon_stats,
    )
    lower_target = battle._spawn_entity(
        Building,
        Position(8.0, 14.0),
        0,
        cannon_stats,
    )

    lower_bridge = lower._get_pathfind_target(upper_target, battle)
    upper_bridge = upper._get_pathfind_target(lower_target, battle)

    assert lower_bridge == Position(3.5, 14.5)
    assert upper_bridge == Position(14.5, 17.5)
    assert lower_bridge.x == pytest.approx(18.0 - upper_bridge.x)
    assert lower_bridge.y == pytest.approx(32.0 - upper_bridge.y)


def test_centerline_target_side_is_resolved_by_owner_for_mirrored_pathing():
    lower_battle = BattleState()
    upper_battle = BattleState()
    lower = _spawn_one(lower_battle, "Skeletons", 1, Position(7.0, 18.5))
    lower_target = _spawn_one(lower_battle, "Knight", 0, Position(1.0, 14.5))
    lower_target.position = Position(1.0, 16.0)
    upper = _spawn_one(upper_battle, "Skeletons", 0, Position(11.0, 13.5))
    upper_target = _spawn_one(upper_battle, "Knight", 1, Position(17.0, 17.5))
    upper_target.position = Position(17.0, 16.0)

    lower_path = lower._get_pathfind_target(lower_target, lower_battle)
    upper_path = upper._get_pathfind_target(upper_target, upper_battle)

    assert upper_path.x == pytest.approx(18.0 - lower_path.x)
    assert upper_path.y == pytest.approx(32.0 - lower_path.y)


def test_bridge_approach_threshold_ulp_drift_changes_neither_player_path():
    battle = BattleState()
    upper = _spawn_one(battle, "Giant", 1, Position(3.5, 18.0))
    lower = _spawn_one(battle, "Giant", 0, Position(14.5, 14.0))
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    lower_target = battle._spawn_entity(
        Building,
        Position(3.5, 10.0),
        0,
        cannon_stats,
    )
    upper_target = battle._spawn_entity(
        Building,
        Position(14.5, 22.0),
        1,
        cannon_stats,
    )
    upper.position = Position(3.5 + 1e-13, 18.0)
    lower.position = Position(14.5 - 1e-13, 14.0)

    upper_path = upper._get_pathfind_target(lower_target, battle)
    lower_path = lower._get_pathfind_target(upper_target, battle)

    assert (upper_path.x, upper_path.y) == pytest.approx((3.5, 17.5))
    assert (lower_path.x, lower_path.y) == pytest.approx((14.5, 14.5))


def test_unrelated_destroyed_princess_tower_does_not_change_bridge_route():
    battle = BattleState()
    troop = _spawn_one(battle, "Knight", 0, Position(3.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(4.0, 22.0))

    route_before = troop._get_pathfind_target(target, battle)
    battle.players[1].right_tower_hp = 0
    route_after = troop._get_pathfind_target(target, battle)

    assert route_before == Position(3.5, 14.5)
    assert route_after == route_before


def test_bridge_crossing_direction_comes_from_positions_not_ownership():
    battle = BattleState()
    displaced_lower_owner = _spawn_one(
        battle, "Knight", 0, Position(8.0, 18.0)
    )
    lower_enemy = _spawn_one(battle, "Knight", 1, Position(10.0, 14.0))
    displaced_upper_owner = _spawn_one(
        battle, "Knight", 1, Position(10.0, 14.0)
    )
    upper_enemy = _spawn_one(battle, "Knight", 0, Position(8.0, 18.0))

    downward_route = displaced_lower_owner._get_pathfind_target(lower_enemy, battle)
    upward_route = displaced_upper_owner._get_pathfind_target(upper_enemy, battle)

    assert downward_route == Position(3.5, 17.5)
    assert upward_route == Position(14.5, 14.5)
    assert downward_route.x == pytest.approx(18.0 - upward_route.x)
    assert downward_route.y == pytest.approx(32.0 - upward_route.y)


def test_passing_bank_y_does_not_skip_lateral_bridge_alignment():
    battle = BattleState()
    lower = _spawn_one(battle, "Knight", 0, Position(8.0, 14.5))
    upper_target = _spawn_one(battle, "Knight", 1, Position(10.0, 18.0))
    upper = _spawn_one(battle, "Knight", 1, Position(10.0, 17.5))
    lower_target = _spawn_one(battle, "Knight", 0, Position(8.0, 14.0))
    lower.position = Position(8.0, 14.6)
    upper.position = Position(10.0, 17.4)

    lower_route = lower._get_pathfind_target(upper_target, battle)
    upper_route = upper._get_pathfind_target(lower_target, battle)

    assert lower_route == Position(3.5, 14.5)
    assert upper_route == Position(14.5, 17.5)
    assert lower_route.x == pytest.approx(18.0 - upper_route.x)
    assert lower_route.y == pytest.approx(32.0 - upper_route.y)


def test_non_bridge_river_spawn_snap_prefers_the_owners_mirrored_bank():
    battle = BattleState()

    lower = battle._snap_to_valid_position(Position(8.5, 16.0), player_id=0)
    upper = battle._snap_to_valid_position(Position(9.5, 16.0), player_id=1)

    assert lower == Position(8.5, 14.5)
    assert upper == Position(9.5, 17.5)
    assert lower.x == pytest.approx(18.0 - upper.x)
    assert lower.y == pytest.approx(32.0 - upper.y)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("player_id", [0, 1])
def test_backwards_ground_route_keeps_current_target_before_crown_fallback(
    fast_path,
    player_id,
):
    battle = BattleState(fast_path=fast_path)
    attacker_position = (
        Position(9.0, 14.9)
        if player_id == 0
        else Position(9.0, 17.1)
    )
    target_position = (
        Position(9.0, 24.0)
        if player_id == 0
        else Position(9.0, 8.0)
    )
    attacker = _spawn_one(battle, "Knight", player_id, attacker_position)
    target = _spawn_one(battle, "Knight", 1 - player_id, target_position)
    attacker.target_id = target.id

    # From the middle non-bridge bank the planned bridge route initially
    # increases integer distance to this out-of-sight target.
    attacker._movement_target_id = target.id
    attacker.update_movement_component(battle.dt, battle)
    assert attacker._ground_path_backwards
    assert attacker._native_natural_movement_active
    if fast_path:
        battle._refresh_fast_path_caches()
    assert attacker.get_nearest_target(
        battle.entities,
        include_crown_fallback=False,
    ) is None

    attacker.update_combat_component(battle.dt, battle)

    assert attacker.target_id == target.id


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("player_id", [0, 1])
def test_forward_ground_route_still_uses_crown_fallback_when_scan_is_empty(
    fast_path,
    player_id,
):
    battle = BattleState(fast_path=fast_path)
    attacker_position = (
        Position(3.5, 12.0)
        if player_id == 0
        else Position(14.5, 20.0)
    )
    target_position = (
        Position(14.5, 25.0)
        if player_id == 0
        else Position(3.5, 7.0)
    )
    attacker = _spawn_one(battle, "Knight", player_id, attacker_position)
    target = _spawn_one(battle, "Knight", 1 - player_id, target_position)
    attacker.target_id = target.id

    attacker._move_towards_target(target, battle.dt, battle)
    assert not attacker._ground_path_backwards
    if fast_path:
        battle._refresh_fast_path_caches()
    assert attacker.get_nearest_target(
        battle.entities,
        include_crown_fallback=False,
    ) is None
    fallback = attacker.get_nearest_target(battle.entities)
    assert isinstance(fallback, Building)

    attacker.update_combat_component(battle.dt, battle)

    assert attacker.target_id == fallback.id


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("player_id", [0, 1])
def test_forward_route_installs_farther_crown_fallback_unconditionally(
    fast_path,
    player_id,
):
    battle = BattleState(fast_path=fast_path)
    attacker_position = (
        Position(3.5, 12.0)
        if player_id == 0
        else Position(14.5, 20.0)
    )
    # The retained troop is outside sight but still substantially nearer than
    # the opposing princess tower. Native's empty-scan forward-route branch
    # nevertheless replaces it with the crown fallback.
    target_position = (
        Position(3.5, 20.0)
        if player_id == 0
        else Position(14.5, 12.0)
    )
    attacker = _spawn_one(battle, "Knight", player_id, attacker_position)
    target = _spawn_one(battle, "Knight", 1 - player_id, target_position)
    attacker.target_id = target.id

    attacker._move_towards_target(target, battle.dt, battle)
    assert not attacker._ground_path_backwards
    if fast_path:
        battle._refresh_fast_path_caches()
    assert attacker.get_nearest_target(
        battle.entities,
        include_crown_fallback=False,
    ) is None
    fallback = attacker.get_nearest_target(battle.entities)
    assert isinstance(fallback, Building)
    assert attacker.native_target_distance_to(target) < (
        attacker.native_target_distance_to(fallback)
    )

    attacker.update_combat_component(battle.dt, battle)

    assert attacker.target_id == fallback.id


@pytest.mark.parametrize("fast_path", [False, True])
def test_river_jump_landings_use_native_world_cell_division(fast_path):
    battle = BattleState(fast_path=fast_path)
    lower = _spawn_one(battle, "HogRider", 0, Position(8.5, 14.9))
    upper = _spawn_one(battle, "HogRider", 1, Position(9.5, 17.1))
    upper_target = _spawn_one(battle, "Knight", 1, Position(9.5, 18.5))
    lower_target = _spawn_one(battle, "Knight", 0, Position(8.5, 13.5))

    assert lower._try_start_river_jump(
        upper_target.position,
        Position(8.5, 15.1),
        battle,
    )
    assert upper._try_start_river_jump(
        lower_target.position,
        Position(9.5, 16.9),
        battle,
    )
    # Native state 5 reconstructs the first land node after the river run as
    # ``cell * 500 + 250`` logic units. It does not intersect the movement ray
    # with the continuous river edge.
    assert lower._river_jump_target == Position(9.75, 17.25)
    # The landing comes from the first land node on the selected route,
    # which can differ from the starting column.
    assert upper._river_jump_target == Position(8.75, 14.75)


def test_native_route_allows_a_short_water_crossing_to_a_bridge():
    lower_battle = BattleState()
    upper_battle = BattleState()
    lower = _spawn_one(lower_battle, "Prince", 0, Position(5.493, 14.884))
    upper = _spawn_one(upper_battle, "Prince", 1, Position(12.507, 17.116))
    lower_target = lower_battle.entities[6]
    upper_target = upper_battle.entities[3]

    # These positions sit just outside the bridge corridors. Native routing
    # costs 5 on either road and 7 on jumpable water. The shorter route can
    # cross water to reach a bridge instead of walking along the bank.
    assert lower._native_lane_id == 1
    assert upper._native_lane_id == 2
    assert _native_pathfinder_tile_cost(lower, (6, 29)) == 5
    assert _native_pathfinder_tile_cost(lower, (28, 35)) == 5
    assert _native_pathfinder_tile_cost(lower, (12, 31)) == 7
    assert native_jump_landing_waypoint(
        lower_battle,
        lower,
        lower_target.position,
    ) is not None
    assert native_jump_landing_waypoint(
        upper_battle,
        upper,
        upper_target.position,
    ) is not None


def test_air_capable_knockback_displaces_river_jumper_and_rebases_landing():
    from clasher.mechanics.shared.knockback import apply_radial_knockback

    battle = BattleState()
    hog = _spawn_one(battle, "HogRider", 0, Position(9.0, 14.9))
    assert hog._try_start_river_jump(
        Position(9.0, 20.0),
        Position(9.0, battle.arena.RIVER_Y1),
        battle,
    )
    committed_landing = Position(hog._river_jump_target.x, hog._river_jump_target.y)
    hog._update_river_jump(battle.dt, battle)
    before_push = Position(hog.position.x, hog.position.y)
    old_remaining = hog._river_jump_duration - hog._river_jump_elapsed

    assert apply_radial_knockback(
        hog,
        battle,
        Position(hog.position.x, hog.position.y + 1.0),
        1.0,
        ignores_mass=True,
    )

    assert hog.position == before_push
    for _ in range(9):
        hog.update_movement_component(battle.dt, battle)
    assert hog.position.y == pytest.approx(before_push.y - 0.9)
    assert hog._river_jump_target == committed_landing
    assert hog._river_jump_elapsed == 0.0
    assert hog._river_jump_duration > old_remaining
    while hog._river_jump_active:
        hog._update_river_jump(battle.dt, battle)
    # Native leaves river state within two jump-speed steps of the node.
    assert 0 < hog.position.distance_to(committed_landing) < 0.320


@pytest.mark.parametrize(
    ("target_position", "origin", "expected", "expected_after_nine", "expected_after_ten"),
    (
        (
            Position(9.0, 10.0),
            Position(6.0, 6.0),
            Position(9.6, 10.8),
            Position(9.536, 10.715),
            Position(9.521, 10.695),
        ),
        (
            Position(9.0, 22.0),
            Position(12.0, 26.0),
            Position(8.4, 21.2),
            Position(8.464, 21.285),
            Position(8.479, 21.305),
        ),
    ),
)
def test_radial_knockback_uses_native_integer_velocity_curve(
    target_position,
    origin,
    expected,
    expected_after_nine,
    expected_after_ten,
):
    from clasher.mechanics.shared.knockback import apply_radial_knockback

    battle = BattleState()
    target = _spawn_one(
        battle,
        "Knight",
        0 if target_position.y < 16 else 1,
        target_position,
    )

    assert apply_radial_knockback(
        target,
        battle,
        origin,
        1.0,
        ignores_mass=True,
    )

    assert target.position == target_position
    target.update_movement_component(battle.dt, battle)
    first_delta = movement_component_vector_logic_units(
        tiles_to_logic_units(expected.x - target_position.x),
        tiles_to_logic_units(expected.y - target_position.y),
        200,
    )
    first_step = Position(
        target_position.x + logic_units_to_tiles(first_delta[0]),
        target_position.y + logic_units_to_tiles(first_delta[1]),
    )
    assert target.position == first_step
    for _ in range(8):
        target.update_movement_component(battle.dt, battle)
    assert target.position == expected_after_nine
    assert target.forced_movement_active
    target.update_movement_component(battle.dt, battle)
    # Native consumes the signed -25 work frame before clearing the state.
    assert target.position == expected_after_ten
    assert not target.forced_movement_active
    assert target.position.x * 1000 == round(target.position.x * 1000)
    assert target.position.y * 1000 == round(target.position.y * 1000)


def test_active_native_pushback_ignores_a_second_push():
    from clasher.mechanics.shared.knockback import apply_radial_knockback

    battle = BattleState()
    target = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))

    assert apply_radial_knockback(
        target,
        battle,
        Position(8.0, 10.0),
        1.0,
        ignores_mass=True,
    )
    assert not apply_radial_knockback(
        target,
        battle,
        Position(10.0, 10.0),
        1.5,
        ignores_mass=True,
    )
    for _ in range(9):
        target.update_movement_component(battle.dt, battle)

    assert target.position == Position(9.9, 10.0)
    assert target.forced_movement_active
    assert not apply_radial_knockback(
        target,
        battle,
        Position(10.0, 10.0),
        1.5,
        ignores_mass=True,
    )
    target.update_movement_component(battle.dt, battle)
    assert not target.forced_movement_active


def test_native_pushback_enters_river_then_recovers_before_later_push_steps():
    from clasher.mechanics.shared.knockback import apply_radial_knockback

    battle = BattleState()
    target = _spawn_one(battle, "Knight", 0, Position(9.0, 14.4))

    assert apply_radial_knockback(
        target,
        battle,
        Position(9.0, 13.4),
        1.0,
        ignores_mass=True,
    )
    entered_water = False
    for _ in range(9):
        target.update_movement_component(battle.dt, battle)
        entered_water |= not battle.arena.is_walkable(target.position)

    # Native permits the initial entry, then recovers before later positive
    # push steps. The both-seat Giant controls bind its world-left tie break.
    assert entered_water
    assert battle.arena.is_walkable(target.position)
    assert target.position.x < 9.0
    assert target.forced_movement_active
    target.update_movement_component(battle.dt, battle)
    assert not target.forced_movement_active


def test_native_pushback_composes_collision_before_boundary_clamp():
    from clasher.mechanics.shared.knockback import apply_radial_knockback

    battle = BattleState()
    target = _spawn_one(battle, "Knight", 0, Position(0.6, 10.0))

    assert apply_radial_knockback(
        target,
        battle,
        Position(1.6, 10.0),
        1.0,
        ignores_mass=True,
    )
    target.accumulate_movement_vector(0.15, 0.0)
    target.begin_movement_tick()
    target.update_movement_component(battle.dt, battle)
    target.finish_movement_tick(battle)

    # Native updateMovementTowards sums the -0.2 push step and +0.15 body
    # pressure before LogicTileMap applies its per-axis boundary clamp.
    assert target.position == Position(0.55, 10.0)


@pytest.mark.parametrize(
    ("player_id", "start", "expected_x"),
    (
        (0, Position(9.0, 10.0), 9.9),
        (1, Position(9.0, 22.0), 8.1),
    ),
)
def test_exact_center_radial_push_uses_owner_rotated_native_fallback(
    player_id,
    start,
    expected_x,
):
    from clasher.mechanics.shared.knockback import apply_radial_knockback

    battle = BattleState()
    target = _spawn_one(battle, "Knight", player_id, start)

    assert apply_radial_knockback(
        target,
        battle,
        Position(start.x, start.y),
        1.0,
        ignores_mass=True,
    )
    for _ in range(9):
        target.update_movement_component(battle.dt, battle)

    assert target.position == Position(expected_x, start.y)


def test_native_pushback_caps_both_endpoint_and_velocity_distance():
    from clasher.mechanics.shared.knockback import apply_radial_knockback

    battle = BattleState()
    target = _spawn_one(battle, "Knight", 0, Position(2.0, 10.0))

    assert apply_radial_knockback(
        target,
        battle,
        Position(1.0, 10.0),
        20.0,
        ignores_mass=True,
    )

    assert target._knockback_target == Position(12.0, 10.0)


@pytest.mark.parametrize("fast_path", [False, True])
def test_sight_edge_target_acquisition_matches_fast_and_scalar_paths(fast_path):
    battle = BattleState(fast_path=fast_path)
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    reach = knight.reach_distance_to(target, knight.sight_range)
    target.position = Position(9.0, 10.0 + reach - 1e-5)
    battle._refresh_fast_path_caches()

    assert knight.get_nearest_target(battle.entities) is target


@pytest.mark.parametrize(
    ("blue_name", "red_name"),
    [
        ("ArcherQueen", "Knight"),
        ("HogRider", "BombTower"),
        ("DartGoblin", "Tombstone"),
    ],
)
def test_fast_target_cache_preserves_scalar_tick_order_and_ties(blue_name, red_name):
    scalar = BattleState(rng=random.Random(123))
    _spawn_one(scalar, blue_name, 0, Position(9.0, 11.5))
    red_stats = scalar.card_loader.get_card(red_name)
    assert red_stats is not None
    if str(red_stats.card_type).lower() == "building":
        red = scalar._spawn_entity(Building, Position(9.0, 18.5), 1, red_stats)
        red.deploy_delay_remaining = 0.0
        red.placement_pending = False
        red.on_spawn()
    else:
        _spawn_one(scalar, red_name, 1, Position(9.0, 18.5))

    fast = copy.deepcopy(scalar)
    fast.fast_path = True
    fast._refresh_fast_path_caches()

    def signature(battle):
        return [
            (
                entity_id,
                type(entity).__name__,
                getattr(getattr(entity, "card_stats", None), "name", None),
                entity.is_alive,
                round(float(entity.hitpoints), 6),
                round(float(entity.position.x), 6),
                round(float(entity.position.y), 6),
                entity.target_id,
            )
            for entity_id, entity in sorted(battle.entities.items())
            if not (getattr(entity, "entity_kind", 4) in {2, 3} and not entity.is_alive)
        ]

    for _ in range(90):
        scalar.step()
        fast.step()
        assert signature(fast) == signature(scalar)


def test_bomber_projectile_splashes_ground_group_but_not_air():
    battle = BattleState()
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    secondary = _spawn_one(battle, "Knight", 1, Position(10.0, 14.0))
    air = _spawn_one(battle, "MegaMinion", 1, Position(9.5, 14.0))
    bomber = _spawn_one(battle, "Bomber", 0, Position(9.0, 10.0))
    for troop in (primary, secondary, air, bomber):
        troop.speed = 0.0
    before = (primary.hitpoints, secondary.hitpoints, air.hitpoints)

    for _ in range(80):
        battle.step()
        if primary.hitpoints < before[0]:
            break

    assert primary.hitpoints < before[0]
    assert secondary.hitpoints < before[1]
    assert air.hitpoints == before[2]


def test_valkyrie_spin_is_centered_on_herself_and_hits_behind_her():
    battle = BattleState()
    valkyrie = _spawn_one(battle, "Valkyrie", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 11.6))
    behind = _spawn_one(battle, "Knight", 1, Position(9.0, 7.6))
    air = _spawn_one(battle, "MegaMinion", 1, Position(9.0, 9.0))
    before = (primary.hitpoints, behind.hitpoints, air.hitpoints)

    valkyrie.attack_cooldown = 0.0
    valkyrie.update(battle.dt, battle)

    assert before[0] - primary.hitpoints == valkyrie.damage
    assert before[1] - behind.hitpoints == valkyrie.damage
    assert air.hitpoints == before[2]


def test_royal_hogs_use_native_wide_unit_offsets_with_staggered_deploys():
    for player_id in (0, 1):
        battle = BattleState()
        stats = battle.card_loader.get_card("RoyalHogs")
        assert stats is not None
        before = set(battle.entities)
        battle._spawn_troop(Position(9.0, 12.0), player_id, stats)
        hogs = [
            entity
            for entity_id, entity in battle.entities.items()
            if entity_id not in before and isinstance(entity, Troop)
        ]

        assert len(hogs) == 4
        assert stats.summon_radius == 0.001
        direction = 1.0 if player_id == 0 else -1.0
        expected = [
            (10.75, 12.0),
            (9.584, 12.0 - 0.001 * direction),
            (8.417, 12.0),
            (7.25, 12.0 - 0.001 * direction),
        ]
        assert [(hog.position.x, hog.position.y) for hog in hogs] == pytest.approx(expected)
        assert [hog.deploy_delay_remaining for hog in hogs] == pytest.approx(
            [1.0, 1.1, 1.2, 1.3]
        )


@pytest.mark.parametrize("count", [2, 3, 4])
def test_native_deploy_sequence_mirrors_small_formations_on_path_one(count):
    path_one = [
        formation_offset(index, count, 0.5, 0, lane_id=1)
        for index in range(count)
    ]
    path_two = [
        formation_offset(index, count, 0.5, 0, lane_id=2)
        for index in range(count)
    ]

    assert path_one == pytest.approx(
        [(-offset_x, offset_y) for offset_x, offset_y in path_two]
    )


def test_native_deploy_sequence_does_not_mirror_five_slot_formation():
    path_one = [
        formation_offset(index, 5, 0.5, 0, lane_id=1)
        for index in range(5)
    ]
    path_two = [
        formation_offset(index, 5, 0.5, 0, lane_id=2)
        for index in range(5)
    ]

    assert path_one == path_two


def test_symmetric_deploy_snap_nudges_shared_ground_anchor_by_one_logic_unit():
    battle = BattleState()
    knight = battle.card_loader.get_card("Knight")
    assert knight is not None

    bottom_left = battle._apply_symmetric_deploy_snap(
        Position(8.0, 10.0), 0, knight
    )
    bottom_right = battle._apply_symmetric_deploy_snap(
        Position(10.0, 10.0), 0, knight
    )
    top_left = battle._apply_symmetric_deploy_snap(
        Position(8.0, 22.0), 1, knight
    )

    assert (
        tiles_to_logic_units(bottom_left.x),
        tiles_to_logic_units(bottom_left.y),
    ) == (7999, 10000)
    assert (
        tiles_to_logic_units(bottom_right.x),
        tiles_to_logic_units(bottom_right.y),
    ) == (10000, 10000)
    assert (
        tiles_to_logic_units(top_left.x),
        tiles_to_logic_units(top_left.y),
    ) == (7999, 21999)


@pytest.mark.parametrize(
    ("card_name", "expected"),
    [("Bats", Position(8.0, 22.0)), ("Cannon", Position(8.0, 22.0)),
     ("Bandit", Position(7.999, 21.999)), ("MegaKnight", Position(7.999, 21.999))],
)
def test_symmetric_deploy_snap_uses_character_capability_gates(card_name, expected):
    battle = BattleState()
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    anchor = Position(8.0, 22.0)

    assert battle._apply_symmetric_deploy_snap(anchor, 1, stats) == expected


@pytest.mark.parametrize(
    ("player_id", "anchor", "expected"),
    [
        (0, Position(8.0, 10.0), (8499, 10500)),
        (1, Position(8.0, 22.0), (8499, 22499)),
    ],
)
def test_card_deployment_applies_symmetric_snap_before_character_birth(
    player_id, anchor, expected
):
    battle = BattleState()
    before = set(battle.entities)

    assert battle.deploy_card(player_id, "Knight", anchor)
    knight = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )

    assert (
        tiles_to_logic_units(knight.position.x),
        tiles_to_logic_units(knight.position.y),
    ) == expected


def test_deploy_sequence_uses_shared_anchor_lane_for_spawn_order():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Skeletons")
    assert stats is not None
    left_anchor = Position(5.0, 12.0)
    right_anchor = Position(13.0, 12.0)
    assert battle.arena.native_path_id_at(left_anchor) == 1
    assert battle.arena.native_path_id_at(right_anchor) == 2

    def deployed_offsets(anchor):
        before = set(battle.entities)
        battle._spawn_troop(anchor, 0, stats)
        return [
            (
                entity.position.x - anchor.x,
                entity.position.y - anchor.y,
            )
            for entity_id, entity in battle.entities.items()
            if entity_id not in before and isinstance(entity, Troop)
        ]

    left = deployed_offsets(left_anchor)
    right = deployed_offsets(right_anchor)
    assert left == pytest.approx(
        [(-offset_x, offset_y) for offset_x, offset_y in right]
    )


def test_deploy_formation_offsets_are_not_individually_relocated_from_water():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Skeletons")
    assert stats is not None

    anchor = Position(9.5, 14.5)
    battle._spawn_troop(anchor, 0, stats)
    skeletons = [
        entity for entity in battle.entities.values() if isinstance(entity, Troop)
    ]

    assert len(skeletons) == 3
    expected = []
    for index in range(3):
        offset_x, offset_y = formation_offset(
            index,
            3,
            stats.summon_radius,
            0,
        )
        expected.append(
            Position(
                logic_units_to_tiles(tiles_to_logic_units(anchor.x + offset_x)),
                logic_units_to_tiles(tiles_to_logic_units(anchor.y + offset_y)),
            )
        )

    assert [entity.position for entity in skeletons] == expected
    # The forward member is deliberately born at its serialized offset even
    # when the formation crosses the non-bridge river. Native code resolves
    # the card's anchor once and does not snap each spawned character.
    assert not battle.arena.is_walkable(skeletons[0].position)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("player_id", [0, 1])
@pytest.mark.parametrize(
    ("card_name", "unit_count"),
    [
        ("Bats", 5),
        ("GoblinGang", 6),
        ("Minions", 3),
        ("RoyalHogs", 4),
        ("SpearGoblins", 3),
        ("Wallbreakers", 2),
    ],
)
def test_enabled_swarm_deploy_delay_applies_between_each_successive_unit(
    card_name,
    unit_count,
    player_id,
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 0
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    assert stats.summon_deploy_delay == 100

    battle._spawn_troop(Position(9.0, 12.0), player_id, stats)
    units = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
    ]
    assert len(units) == unit_count

    initial_delays = [
        stats.deploy_time / 1000.0 + index * stats.summon_deploy_delay / 1000.0
        for index in range(unit_count)
    ]
    assert [unit.deploy_delay_remaining for unit in units] == pytest.approx(
        initial_delays
    )
    assert [unit.spawn_stagger_remaining for unit in units] == pytest.approx(
        [index * stats.summon_deploy_delay / 1000.0 for index in range(unit_count)]
    )

    elapsed = 0.0
    while elapsed < initial_delays[-1] - 1e-9:
        battle.step()
        elapsed += battle.dt
        expected_remaining = [
            max(0.0, delay - elapsed) for delay in initial_delays
        ]
        assert [unit.deploy_delay_remaining for unit in units] == pytest.approx(
            expected_remaining,
            abs=1e-9,
        )
        assert [unit.placement_pending for unit in units] == [
            remaining > 1e-9 for remaining in expected_remaining
        ]


def test_bats_use_native_rotated_ring_and_mixed_swarms_face_the_opponent():
    for player_id, direction in ((0, 1.0), (1, -1.0)):
        bats_battle = BattleState()
        bat_stats = bats_battle.card_loader.get_card("Bats")
        assert bat_stats is not None
        bats_battle._spawn_troop(Position(9.0, 12.0), player_id, bat_stats)
        bats = [entity for entity in bats_battle.entities.values() if isinstance(entity, Troop)]
        assert len(bats) == 5
        expected_offsets = [
            (0.993, 0.993 * direction),
            (1.251, -0.638 * direction),
            (-0.219, -1.387 * direction),
            (-1.387, -0.219 * direction),
            (-0.638, 1.251 * direction),
        ]
        actual_offsets = [
            (bat.position.x - 9.0, bat.position.y - 12.0)
            for bat in bats
        ]
        for actual, expected in zip(actual_offsets, expected_offsets, strict=True):
            assert actual == pytest.approx(expected)
        assert [bat.deploy_delay_remaining for bat in bats] == pytest.approx(
            [1.0, 1.1, 1.2, 1.3, 1.4]
        )

        gang_battle = BattleState()
        gang_stats = gang_battle.card_loader.get_card("GoblinGang")
        assert gang_stats is not None
        gang_battle._spawn_troop(Position(9.0, 12.0), player_id, gang_stats)
        gang = [entity for entity in gang_battle.entities.values() if isinstance(entity, Troop)]
        assert len(gang) == 6
        assert [entity.card_stats.name for entity in gang[:3]] == ["Goblin_Stab"] * 3
        assert [entity.card_stats.name for entity in gang[3:]] == ["SpearGoblin"] * 3
        assert [unit_mass(entity.card_stats) for entity in gang] == [2.0] * 3 + [1.0] * 3
        assert [entity.position.y for entity in gang] == pytest.approx(
            [
                12.0 + 0.577 * direction,
                12.0 + 1.154 * direction,
                12.0 + 0.577 * direction,
                12.0 - 0.577 * direction,
                12.0 - 1.154 * direction,
                12.0 - 0.577 * direction,
            ]
        )


def test_spear_goblins_use_the_current_wider_serialized_spawn_radius():
    positions_by_player = []
    for player_id in (0, 1):
        battle = BattleState()
        battle.entities.clear()
        battle.next_entity_id = 1
        stats = battle.card_loader.get_card("SpearGoblins")
        assert stats is not None
        assert stats.summon_radius == pytest.approx(0.8)

        battle._spawn_troop(Position(9.0, 12.0), player_id, stats)
        positions = [
            entity.position
            for entity in battle.entities.values()
            if isinstance(entity, Troop)
        ]
        assert positions == [
            Position(9.0, 12.923 if player_id == 0 else 11.077),
            Position(9.799, 11.539 if player_id == 0 else 12.461),
            Position(8.201, 11.539 if player_id == 0 else 12.461),
        ]
        positions_by_player.append(positions)

    assert [
        Position(position.x, 24.0 - position.y)
        for position in positions_by_player[0]
    ] == positions_by_player[1]


def test_xbow_locks_ground_only_after_its_full_deploy_window():
    battle = BattleState()
    xbow_stats = battle.card_loader.get_card("Xbow")
    assert xbow_stats is not None
    xbow = battle._spawn_entity(Building, Position(9.0, 14.0), 0, xbow_stats)
    ground = _spawn_one(battle, "Knight", 1, Position(9.0, 20.0))
    air = _spawn_one(battle, "MegaMinion", 1, Position(9.5, 20.0))
    ground.speed = air.speed = 0.0
    before = (ground.hitpoints, air.hitpoints)

    assert xbow.deploy_delay_remaining == 3.5
    assert xbow.card_stats.lifetime_ms == 30_000
    for _ in range(math.ceil(3.5 / battle.dt) - 1):
        battle.step()
    assert (ground.hitpoints, air.hitpoints) == before

    for _ in range(80):
        battle.step()
        if ground.hitpoints < before[0]:
            break
    assert ground.hitpoints < before[0]
    assert air.hitpoints == before[1]


def test_deployment_payloads_resolve_when_deploy_timer_finishes():
    for card_name in ("ElectroWizard", "MegaKnight"):
        battle = BattleState()
        target = _spawn_one(battle, "Knight", 1, Position(9.0, 12.0))
        hp_before = target.hitpoints
        stats = battle.card_loader.get_card(card_name)
        assert stats is not None
        before = set(battle.entities)
        battle._spawn_unit_at_position(Position(9.0, 12.0), 0, stats)
        unit = next(
            entity
            for entity_id, entity in battle.entities.items()
            if entity_id not in before and isinstance(entity, Troop)
        )

        assert unit.deploy_delay_remaining == 1.0
        assert target.hitpoints == hp_before
        deployment_steps = math.ceil(1.0 / battle.dt)
        for _ in range(deployment_steps - 1):
            unit.update(battle.dt, battle)
        assert target.hitpoints == hp_before
        unit.update(battle.dt, battle)
        for area in [
            entity
            for entity in battle.entities.values()
            if isinstance(entity, AreaEffect)
            and entity.card_stats is unit.card_stats
            and entity.is_alive
        ]:
            area.update(battle.dt, battle)
        assert target.hitpoints < hp_before


@pytest.mark.parametrize("fast_path", [False, True])
def test_spawn_area_object_damages_later_same_frame_character_spawns(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    wizard_stats = battle.card_loader.get_card("IceWizard")
    tombstone_stats = battle.card_loader.get_card("Tombstone")
    assert wizard_stats is not None and tombstone_stats is not None
    battle._spawn_unit_at_position(Position(9.0, 14.0), 0, wizard_stats)
    wizard = next(iter(battle.entities.values()))
    tombstone = battle._spawn_entity(
        Building,
        Position(9.0, 14.0),
        1,
        tombstone_stats,
    )
    for entity in (wizard, tombstone):
        entity.deploy_delay_remaining = battle.dt
        entity.placement_delay_total = battle.dt
        entity.placement_pending = True
    spawner = next(
        mechanic
        for mechanic in tombstone.mechanics
        if type(mechanic).__name__ == "PeriodicSpawner"
    )
    first_deadline = (
        spawner.first_spawn_delay_ms
        if spawner.first_spawn_delay_ms is not None
        else spawner.spawn_interval_ms
    )
    spawner.time_since_spawn_ms = first_deadline - battle.dt * 1000.0

    battle.step()

    surviving_skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == tombstone.player_id
        and entity.card_stats.name == "Skeleton"
    ]
    # Tombstone created the first Skeleton after Ice Wizard's object tick.
    # The newly appended nova object then resolved later in the same manager
    # pass and killed it; a synchronous on_spawn shortcut leaves it alive.
    assert spawner.current_wave_spawned == 1
    assert spawner.pending_units == 1
    assert surviving_skeletons == []


def test_electro_spirit_chains_on_contact_not_on_deployment():
    battle = BattleState()
    first = _spawn_one(battle, "Knight", 1, Position(2.5, 15.5))
    second = _spawn_one(battle, "Knight", 1, Position(4.5, 15.5))
    spirit = _spawn_one(battle, "ElectroSpirit", 0, Position(2.5, 14.0))

    first_hp = first.hitpoints
    second_hp = second.hitpoints
    assert first.hitpoints == first_hp
    assert second.hitpoints == second_hp

    spirit.attack_cooldown = 0.0
    spirit.update(battle.dt, battle)
    assert spirit.is_alive
    assert spirit._special_move_active
    spirit_hp = spirit.hitpoints
    spirit.take_damage(9999)
    spirit.apply_stun(1.0)
    assert spirit.hitpoints == spirit_hp
    assert spirit.stun_timer == 0.0
    assert not first._is_valid_target(spirit)
    assert first.hitpoints == first_hp
    assert second.hitpoints == second_hp
    for _ in range(10):
        spirit.update(battle.dt, battle)
        if not spirit.is_alive:
            break

    assert first.hitpoints == first_hp - spirit.damage
    assert first.stun_timer > 0
    assert second.hitpoints == second_hp
    chain = next(entity for entity in battle.entities.values() if isinstance(entity, ChainLightning))
    assert spirit.card_stats.projectile_data["speed"] == 1000
    assert chain.travel_speed == pytest.approx(1000 / 50)
    assert chain.fixed_hop_duration == pytest.approx(0.25)
    chain.update(0.24, battle)
    assert second.hitpoints == second_hp
    chain.update(0.01, battle)
    assert second.hitpoints == second_hp - spirit.damage
    assert second.stun_timer > 0
    assert not spirit.is_alive


def test_electro_spirit_chains_after_its_first_hit_kills_the_target():
    battle = BattleState()
    first = _spawn_one(battle, "Knight", 1, Position(5.0, 15.0))
    second = _spawn_one(battle, "Knight", 1, Position(7.0, 15.0))
    spirit = _spawn_one(battle, "ElectroSpirit", 0, Position(5.0, 13.0))
    first.hitpoints = min(first.hitpoints, spirit.damage)
    second_hp = second.hitpoints

    spirit.attack_cooldown = 0.0
    spirit.update(battle.dt, battle)
    for _ in range(10):
        spirit.update(battle.dt, battle)
        if not spirit.is_alive:
            break

    assert not first.is_alive
    chain = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, ChainLightning)
    )
    assert chain.visited_ids == {first.id}
    assert second.hitpoints == second_hp

    chain.update(0.25, battle)

    assert second.hitpoints == second_hp - spirit.damage
    assert second.stun_timer == pytest.approx(0.5)


def test_electro_spirit_chain_cannot_enter_active_lethal_first_hit_death_spawns():
    battle = BattleState()
    hound = _spawn_one(battle, "LavaHound", 1, Position(5.0, 15.0))
    spirit = _spawn_one(battle, "ElectroSpirit", 0, Position(5.0, 13.0))
    hound.hitpoints = min(hound.hitpoints, spirit.damage)

    spirit.attack_cooldown = 0.0
    spirit.update(battle.dt, battle)
    for _ in range(10):
        spirit.update(battle.dt, battle)
        if not spirit.is_alive:
            break

    pups = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == hound.player_id
        and entity.card_stats.name == "LavaPups"
    ]
    assert not hound.is_alive
    assert len(pups) == 6
    hp_before = [pup.hitpoints for pup in pups]
    chain = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, ChainLightning)
    )

    # The first 250 ms link seeks its target while the native marker is still
    # active; it clears only on the following 50 ms character-object tick.
    chain.update(0.25, battle)

    assert [pup.hitpoints for pup in pups] == hp_before
    assert all(pup.stun_timer == 0.0 for pup in pups)


@pytest.mark.parametrize("distance", (0.5, 4.0))
def test_electro_spirit_chain_interval_is_independent_of_hop_distance(distance):
    battle = BattleState()
    primary = _spawn_one(battle, "Knight", 1, Position(5.0, 15.0))
    target = _spawn_one(
        battle,
        "Knight",
        1,
        Position(primary.position.x + distance, primary.position.y),
    )
    target.position = Position(
        primary.position.x + distance,
        primary.position.y,
    )
    before = target.hitpoints
    chain = ChainLightning(
        id=battle.next_entity_id,
        position=Position(primary.position.x, primary.position.y),
        player_id=0,
        card_stats=battle.card_loader.get_card("ElectroSpirit"),
        hitpoints=1,
        max_hitpoints=1,
        damage=99,
        range=0,
        sight_range=0,
        origin=Position(primary.position.x, primary.position.y),
        remaining_bounces=1,
        fixed_hop_duration=0.25,
        visited_ids={primary.id},
    )

    chain.update(0.249, battle)
    assert target.hitpoints == before
    chain.update(0.001, battle)
    assert target.hitpoints == before - 99


def test_fixed_chain_interval_is_paid_for_each_bounce_with_a_large_update():
    battle = BattleState()
    first = _spawn_one(battle, "Knight", 1, Position(5.0, 15.0))
    second = _spawn_one(battle, "Knight", 1, Position(6.0, 15.0))
    third = _spawn_one(battle, "Knight", 1, Position(7.0, 15.0))
    second.position = Position(6.0, 15.0)
    third.position = Position(7.0, 15.0)
    before = (second.hitpoints, third.hitpoints)
    chain = ChainLightning(
        id=battle.next_entity_id,
        position=Position(first.position.x, first.position.y),
        player_id=0,
        card_stats=battle.card_loader.get_card("ElectroSpirit"),
        hitpoints=1,
        max_hitpoints=1,
        damage=99,
        range=0,
        sight_range=0,
        origin=Position(first.position.x, first.position.y),
        remaining_bounces=2,
        fixed_hop_duration=0.25,
        visited_ids={first.id},
    )

    chain.update(0.499, battle)
    assert second.hitpoints == before[0] - 99
    assert third.hitpoints == before[1]
    chain.update(0.001, battle)
    assert third.hitpoints == before[1] - 99


def test_fixed_chain_interpolation_is_exact_under_the_player_rotation():
    normal = BattleState()
    mirrored = BattleState()
    normal.entities.clear()
    mirrored.entities.clear()
    target = _spawn_one(normal, "Knight", 1, Position(4.523, 17.85))
    mirrored_target = _spawn_one(
        mirrored,
        "Knight",
        0,
        Position(13.477, 14.15),
    )
    target.position = Position(4.523, 17.85)
    mirrored_target.position = Position(13.477, 14.15)
    stats = normal.card_loader.get_card("ElectroSpirit")
    mirrored_stats = mirrored.card_loader.get_card("ElectroSpirit")
    chain = ChainLightning(
        id=normal.next_entity_id,
        position=Position(4.567, 15.933),
        player_id=0,
        card_stats=stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=99,
        range=0,
        sight_range=0,
        origin=Position(4.567, 15.933),
        remaining_bounces=1,
        fixed_hop_duration=0.25,
    )
    mirrored_chain = ChainLightning(
        id=mirrored.next_entity_id,
        position=Position(13.433, 16.067),
        player_id=1,
        card_stats=mirrored_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=99,
        range=0,
        sight_range=0,
        origin=Position(13.433, 16.067),
        remaining_bounces=1,
        fixed_hop_duration=0.25,
    )

    chain.update(0.05, normal)
    mirrored_chain.update(0.05, mirrored)
    target.position = Position(4.563, 18.086)
    mirrored_target.position = Position(13.437, 13.914)
    chain.update(0.05, normal)
    mirrored_chain.update(0.05, mirrored)

    assert (
        tiles_to_logic_units(chain.position.x)
        + tiles_to_logic_units(mirrored_chain.position.x)
        == 18_000
    )
    assert (
        tiles_to_logic_units(chain.position.y)
        + tiles_to_logic_units(mirrored_chain.position.y)
        == 32_000
    )


def test_chain_lightning_can_enter_a_character_that_is_still_deploying():
    battle = BattleState()
    pending = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    active = _spawn_one(battle, "Knight", 1, Position(10.0, 14.0))
    pending.placement_pending = True
    pending.deploy_delay_remaining = 1.0
    before = (pending.hitpoints, active.hitpoints)
    chain = ChainLightning(
        id=battle.next_entity_id,
        position=Position(9.0, 13.0),
        player_id=0,
        card_stats=battle.card_loader.get_card("ElectroSpirit"),
        hitpoints=1,
        max_hitpoints=1,
        damage=99,
        range=0,
        sight_range=0,
        origin=Position(9.0, 13.0),
        remaining_bounces=1,
    )

    chain.update(0.03, battle)

    assert pending.hitpoints == before[0] - 99
    assert active.hitpoints == before[1]
    assert pending.stun_timer > 0


def test_chain_lightning_can_jump_to_invisible_units_but_not_hidden_buildings():
    battle = BattleState()
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    ghost = _spawn_one(battle, "RoyalGhost", 1, Position(11.0, 14.0))
    tesla_stats = battle.card_loader.get_card("Tesla")
    assert tesla_stats is not None
    tesla = battle._spawn_entity(Building, Position(8.0, 14.0), 1, tesla_stats)
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    tesla.on_spawn()
    before = (ghost.hitpoints, tesla.hitpoints)
    assert not ghost.is_targetable_by(0)
    _fully_hide_tesla(tesla)
    assert tesla._hidden_building

    chain = ChainLightning(
        id=battle.next_entity_id,
        position=Position(primary.position.x, primary.position.y),
        player_id=0,
        card_stats=battle.card_loader.get_card("ElectroSpirit"),
        hitpoints=1,
        max_hitpoints=1,
        damage=99,
        range=0,
        sight_range=0,
        origin=Position(primary.position.x, primary.position.y),
        remaining_bounces=1,
        visited_ids={primary.id},
    )

    chain.update(0.2, battle)

    assert ghost.hitpoints == before[0] - 99
    assert ghost.stun_timer > 0
    assert tesla.hitpoints == before[1]


@pytest.mark.parametrize("target_name", ("RoyalGhost", "ArcherQueen"))
def test_projectile_committed_before_invisibility_still_connects(target_name):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, target_name, 1, Position(9.0, 14.0))
    target._stealth_until = 0
    attacker.target_id = target.id
    attacker.attack_cooldown = 0.0
    before = target.hitpoints

    attacker.update(battle.dt, battle)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and entity.source_entity is attacker
    )
    target._stealth_until = 2**31 - 1
    assert not target.is_targetable_by(attacker.player_id)

    for _ in range(100):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break

    assert not projectile.is_alive
    assert before - target.hitpoints == attacker.damage


def test_chain_lightning_equal_distance_tie_rotates_with_its_owner():
    normal = BattleState()
    mirrored = BattleState()
    normal.entities.clear()
    mirrored.entities.clear()
    left = _spawn_one(normal, "Knight", 1, Position(7.95, 17.5))
    _spawn_one(normal, "Knight", 1, Position(11.05, 17.5))
    mirrored_left = _spawn_one(mirrored, "Knight", 0, Position(10.05, 14.5))
    _spawn_one(mirrored, "Knight", 0, Position(6.95, 14.5))
    stats = normal.card_loader.get_card("ElectroDragon")
    mirrored_stats = mirrored.card_loader.get_card("ElectroDragon")
    assert stats is not None and mirrored_stats is not None
    chain = ChainLightning(
        id=normal.next_entity_id,
        position=Position(9.5, 17.5),
        player_id=0,
        card_stats=stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=99,
        range=0,
        sight_range=0,
        origin=Position(9.5, 17.5),
        remaining_bounces=1,
    )
    mirrored_chain = ChainLightning(
        id=mirrored.next_entity_id,
        position=Position(8.5, 14.5),
        player_id=1,
        card_stats=mirrored_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=99,
        range=0,
        sight_range=0,
        origin=Position(8.5, 14.5),
        remaining_bounces=1,
    )

    assert chain._find_next_target(normal) is left
    assert mirrored_chain._find_next_target(mirrored) is mirrored_left


def test_destroyed_ice_spirit_does_not_freeze_without_connecting():
    battle = BattleState()
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    spirit = _spawn_one(battle, "IceSpirit", 0, Position(9.0, 14.0))

    spirit.take_damage(spirit.hitpoints)

    assert not spirit.is_alive
    assert target.stun_timer == 0.0


def test_ice_spirit_jump_is_delayed_untargetable_and_area_damages_on_landing():
    battle = BattleState(rng=random.Random(3))
    primary = _spawn_one(battle, "Knight", 1, Position(3.5, 15.5))
    secondary = _spawn_one(battle, "Knight", 1, Position(4.5, 15.5))
    spirit = _spawn_one(battle, "IceSpirit", 0, Position(3.5, 14.0))
    hp_before = (primary.hitpoints, secondary.hitpoints)
    spirit_hp = spirit.hitpoints

    spirit.attack_cooldown = 0.0
    spirit.update(battle.dt, battle)
    assert spirit._special_move_active
    spirit.take_damage(9999)
    spirit.apply_stun(1.0)
    assert spirit.hitpoints == spirit_hp
    assert spirit.stun_timer == 0.0
    assert (primary.hitpoints, secondary.hitpoints) == hp_before

    for _ in range(30):
        spirit.update(battle.dt, battle)
        if not spirit.is_alive:
            break
    assert hp_before[0] - primary.hitpoints == spirit.damage
    assert hp_before[1] - secondary.hitpoints == spirit.damage
    assert primary.stun_timer == secondary.stun_timer == 1.1


@pytest.mark.parametrize(
    ("card_name", "expected_next_frame_travel"),
    (("IceSpirit", 0.4), ("ElectroSpirit", 1.0)),
)
def test_spirit_attack_launch_waits_until_next_object_phase(
    card_name,
    expected_next_frame_travel,
):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    spirit = _spawn_one(battle, card_name, 0, Position(3.5, 14.0))
    target = _spawn_one(battle, "Knight", 1, Position(3.5, 15.5))
    target.apply_stun(10.0)
    spirit.target_id = target.id
    spirit.attack_cooldown = 0.0
    start_y = spirit.position.y

    battle.step()

    assert spirit._special_move_active
    assert spirit.position.y == start_y
    battle.step()
    assert spirit.position.y - start_y == pytest.approx(
        expected_next_frame_travel
    )


def test_ice_spirit_projectile_still_detonates_if_primary_dies_mid_jump():
    battle = BattleState(rng=random.Random(301))
    primary = _spawn_one(battle, "Knight", 1, Position(3.5, 15.5))
    secondary = _spawn_one(battle, "Knight", 1, Position(4.5, 15.5))
    spirit = _spawn_one(battle, "IceSpirit", 0, Position(3.5, 14.0))
    secondary_hp = secondary.hitpoints

    spirit.attack_cooldown = 0.0
    spirit.update(battle.dt, battle)
    assert spirit._special_move_active
    primary.take_damage(primary.hitpoints)

    for _ in range(30):
        spirit.update(battle.dt, battle)
        if not spirit.is_alive:
            break

    assert not spirit.is_alive
    assert spirit._ice_spirit_detonated
    assert secondary_hp - secondary.hitpoints == spirit.damage
    assert secondary.stun_timer == 1.1


@pytest.mark.parametrize("fast_path", [False, True])
def test_electro_spirit_requires_live_primary_contact_to_start_chain(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    spirit = _spawn_one(
        battle,
        "ElectroSpirit",
        0,
        Position(3.5, 14.0),
    )
    primary = _spawn_one(
        battle,
        "Knight",
        1,
        Position(3.5, 17.0),
    )
    secondary = _spawn_one(
        battle,
        "Knight",
        1,
        Position(4.5, 17.0),
    )
    primary.apply_stun(10.0)
    secondary.apply_stun(10.0)
    secondary_hp = secondary.hitpoints
    spirit.target_id = primary.id
    spirit.attack_cooldown = 0.0

    battle.step()
    assert spirit._special_move_active
    primary.take_damage(primary.hitpoints)

    for _ in range(3):
        battle.step()
        if not spirit.is_alive:
            break

    assert not spirit.is_alive
    assert primary.id not in battle.entities
    assert secondary.hitpoints == secondary_hp
    assert not any(
        isinstance(entity, ChainLightning)
        and entity.card_stats.name == "ElectroSpirit"
        for entity in battle.entities.values()
    )


@pytest.mark.parametrize(
    ("card_name", "target_step", "initial_deadline_ticks"),
    (("IceSpirit", 0.3, 4), ("ElectroSpirit", 0.9, 2)),
)
def test_spirit_homing_jump_keeps_serialized_speed_when_target_flees(
    card_name,
    target_step,
    initial_deadline_ticks,
):
    battle = BattleState()
    target = _spawn_one(battle, "Knight", 1, Position(3.5, 15.5))
    spirit = _spawn_one(battle, card_name, 0, Position(3.5, 14.0))
    mechanic = next(
        mechanic
        for mechanic in spirit.mechanics
        if type(mechanic).__name__ in {"IceSpiritFreeze", "ElectroSpiritChain"}
    )
    native_speed = mechanic.jump_speed_logic_units_per_tick

    spirit.attack_cooldown = 0.0
    spirit.update(battle.dt, battle)
    assert spirit._special_move_active

    previous_y_units = tiles_to_logic_units(spirit.position.y)
    for _ in range(initial_deadline_ticks):
        target.position.y = logic_units_to_tiles(
            tiles_to_logic_units(target.position.y + target_step)
        )
        spirit.update(battle.dt, battle)
        current_y_units = tiles_to_logic_units(spirit.position.y)
        assert current_y_units - previous_y_units == native_speed
        assert spirit.position.y == logic_units_to_tiles(current_y_units)
        previous_y_units = current_y_units

    # The old fixed-deadline interpolation landed here by accelerating toward
    # the updated endpoint. A homing jump instead remains in flight until its
    # serialized per-tick movement actually closes the extra distance.
    assert spirit.is_alive
    assert spirit._special_move_active

    for _ in range(20):
        spirit.update(battle.dt, battle)
        if not spirit.is_alive:
            break
    assert not spirit.is_alive


def test_wall_breaker_contact_is_one_data_scaled_explosion():
    battle = BattleState()
    wall_breaker = _spawn_one(battle, "Wallbreakers", 0, Position(9.0, 14.0))
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(Building, Position(9.0, 15.0), 1, cannon_stats)
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False

    hp_before = cannon.hitpoints
    wall_breaker.attack_cooldown = 0.0
    wall_breaker.update_combat_component(battle.dt, battle)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and entity.source_entity is wall_breaker
    )
    projectile.update(battle.dt, battle)

    assert hp_before - cannon.hitpoints == wall_breaker.damage
    assert not wall_breaker.is_alive


def test_golem_and_golemite_death_novas_are_scaled_and_hit_both_planes():
    battle = BattleState(rng=random.Random(4))
    ground = _spawn_one(battle, "Knight", 1, Position(10.5, 14.0))
    air = _spawn_one(battle, "BabyDragon", 1, Position(10.5, 14.0))
    heavy = _spawn_one(battle, "Pekka", 1, Position(9.0, 15.0))
    golem = _spawn_one(battle, "Golem", 0, Position(9.0, 14.0))
    hp_before = (ground.hitpoints, air.hitpoints)
    heavy_position = Position(heavy.position.x, heavy.position.y)

    golem.take_damage(golem.hitpoints)
    expected_golem_death = golem.card_stats.get_scaled_stat(88)
    assert hp_before[0] - ground.hitpoints == expected_golem_death
    assert hp_before[1] - air.hitpoints == expected_golem_death
    assert ground.position.x == air.position.x == 10.5
    for _ in range(12):
        ground.update_movement_component(battle.dt, battle)
        air.update_movement_component(battle.dt, battle)
    assert ground.position.x == pytest.approx(12.125)
    assert air.position.x == pytest.approx(12.125)
    assert ground.forced_movement_active
    assert air.forced_movement_active
    ground.update_movement_component(battle.dt, battle)
    air.update_movement_component(battle.dt, battle)
    assert not ground.forced_movement_active
    assert not air.forced_movement_active
    assert ground.position.x == pytest.approx(12.1)
    assert air.position.x == pytest.approx(12.1)
    assert heavy.position == heavy_position
    golemites = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(not golemites_unit.placement_pending for golemites_unit in golemites)
    assert all(golemites_unit.deploy_delay_remaining == 0.0 for golemites_unit in golemites)
    assert all(golemites_unit.card_stats.sight_clip == 2.0 for golemites_unit in golemites)
    assert all(golemites_unit.card_stats.sight_clip_side == 2.0 for golemites_unit in golemites)
    assert all(golemite.position == golem.position for golemite in golemites)
    assert [
        golemite._death_spawn_travel_target.x for golemite in golemites
    ] == pytest.approx([7.5, 10.5])
    assert [
        golemite._death_spawn_travel_ticks_remaining for golemite in golemites
    ] == [6, 6]
    assert [
        golemite._native_target_distance_discount_sq_units
        for golemite in golemites
    ] == [0, 0]
    assert any(type(mechanic).__name__ == "DeathDamage" for mechanic in golemites[0].mechanics)

    golemites[0].deploy_delay_remaining = 0.0
    golemites[0].placement_pending = False
    golemites[0].on_spawn()
    golemites[0].position = Position(ground.position.x - 1.0, ground.position.y)
    ground_hp = ground.hitpoints
    ground_x = ground.position.x
    battle.tick += 1
    golemites[0].take_damage(golemites[0].hitpoints)
    assert ground_hp - ground.hitpoints == golemites[0].card_stats.get_scaled_stat(39)
    for _ in range(9):
        ground.update_movement_component(battle.dt, battle)
    assert ground.position.x == pytest.approx(ground_x + 0.675)


def test_ice_golem_death_slow_is_a_one_shot_post_damage_snapshot():
    battle = BattleState(rng=random.Random(41))
    ice_golem = _spawn_one(battle, "IceGolem", 0, Position(9.0, 14.0))
    golem = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))
    survivor = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    tesla = battle._spawn_entity(
        Building,
        Position(9.0, 14.0),
        1,
        battle.card_loader.get_card("Tesla"),
    )
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    tesla.on_spawn()
    tesla_hp = tesla.hitpoints
    _fully_hide_tesla(tesla)
    assert tesla._hidden_building
    ice_golem.position = Position(9.0, 14.0)
    golem.position = Position(9.0, 14.0)
    survivor.position = Position(10.0, 14.0)
    death_damage = next(
        mechanic.scaled_damage
        for mechanic in ice_golem.mechanics
        if type(mechanic).__name__ == "DeathDamage"
    )
    golem.hitpoints = death_damage

    ice_golem.take_damage(ice_golem.hitpoints)

    golemites = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == golem.player_id
        and entity.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    slow_field = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, AreaEffect)
        and entity.player_id == ice_golem.player_id
        and entity.speed_multiplier < 1.0
    )
    assert slow_field.duration == pytest.approx(1.0)
    assert slow_field.slow_refresh_duration == pytest.approx(2.0)
    assert survivor.slow_timer == 0.0
    assert all(golemite.slow_timer == 0.0 for golemite in golemites)
    # Ice Golem's direct death nova is not marked AffectsHidden.
    assert tesla.hitpoints == tesla_hp
    assert tesla.slow_timer == 0.0

    slow_field.update(battle.dt, battle)

    assert survivor.slow_multiplier == pytest.approx(0.7)
    assert survivor.slow_timer == pytest.approx(2.0)
    assert all(golemite.slow_multiplier == pytest.approx(0.7) for golemite in golemites)
    assert all(golemite.slow_timer == pytest.approx(2.0) for golemite in golemites)
    # Its separate death-area slow is marked AffectsHidden in the current
    # AreaEffectObject table and therefore reaches a retracted Tesla.
    assert slow_field.affects_hidden
    assert tesla.hitpoints == tesla_hp
    assert tesla.slow_timer == pytest.approx(2.0)
    assert tesla.slow_multiplier == pytest.approx(0.7)

    late = _spawn_one(battle, "Knight", 1, Position(16.0, 14.0))
    late.position = Position(9.0, 14.0)
    slow_field.update(0.9, battle)
    assert late.slow_timer == 0.0
    assert late.slow_multiplier == 1.0


def test_lumberjack_death_rage_keeps_its_distinct_crown_tower_modifier():
    battle = BattleState()
    tower = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 1
        and entity.card_stats.name == "Tower"
    )
    tower.position = Position(10.5, 14.0)
    target = _spawn_one(battle, "Knight", 1, Position(9.5, 14.0))
    tesla = battle._spawn_entity(
        Building,
        Position(9.0, 14.0),
        1,
        battle.card_loader.get_card("Tesla"),
    )
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    tesla.on_spawn()
    _fully_hide_tesla(tesla)
    assert tesla._hidden_building
    lumberjack = _spawn_one(battle, "Lumberjack", 0, Position(9.0, 14.0))
    target_hp = target.hitpoints
    tower_hp = tower.hitpoints
    tesla_hp = tesla.hitpoints

    lumberjack.take_damage(lumberjack.hitpoints)
    start_action = next(
        entity for entity in battle.entities.values()
        if isinstance(entity, DeathAreaStartAction)
    )
    start_action.update(battle.dt, battle)
    bottle = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, DeathAreaEffectContainer)
        and entity.player_id == lumberjack.player_id
    )
    bottle.update(0.5, battle)
    rage = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, BuffAreaEffect)
        and entity.player_id == lumberjack.player_id
    )
    rage.update(battle.dt, battle)
    impact = next(
        entity for entity in battle.entities.values()
        if isinstance(entity, AreaEffect) and entity.damage > 0
    )
    impact.update(battle.dt, battle)

    assert rage.impact_damage == 179
    assert rage.impact_affects_hidden
    assert rage.crown_tower_damage_multiplier == pytest.approx(0.3)
    assert rage.crown_tower_damage is None
    assert target_hp - target.hitpoints == 179
    assert tower_hp - tower.hitpoints == 54
    assert tesla_hp - tesla.hitpoints == 179


def test_spawn_area_without_affects_hidden_does_not_reach_retracted_tesla():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    tesla = battle._spawn_entity(
        Building,
        Position(9.0, 14.0),
        1,
        battle.card_loader.get_card("Tesla"),
    )
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    tesla.on_spawn()
    _fully_hide_tesla(tesla)
    assert tesla._hidden_building
    hp_before = tesla.hitpoints

    _spawn_one(
        battle,
        "IceWizard",
        0,
        Position(9.0, 14.0),
        resolve_spawn_payload=False,
    )
    spawn_area = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, AreaEffect)
    )
    assert not spawn_area.affects_hidden
    spawn_area.update(battle.dt, battle)

    assert tesla.hitpoints == hp_before
    assert tesla.slow_timer == 0.0


def test_lumberjack_death_dispatches_bottle_area_and_impact_on_separate_frames():
    battle = BattleState()
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    lumberjack = _spawn_one(battle, "Lumberjack", 0, Position(9.0, 14.0))
    hp_before = target.hitpoints
    lumberjack.take_damage(lumberjack.hitpoints)
    start_action = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, DeathAreaStartAction)
        and entity.player_id == lumberjack.player_id
    )
    assert start_action.id == lumberjack.id + 1
    later_unit = _spawn_one(
        battle,
        "Knight",
        lumberjack.player_id,
        Position(2.0, 2.0),
    )
    later_unit.stun_timer = 10.0
    assert later_unit.id == start_action.id + 1

    for _ in range(11):
        battle.step()

    bottle = next(e for e in battle.entities.values() if isinstance(e, DeathAreaEffectContainer))
    assert bottle.is_alive
    assert not any(
        isinstance(entity, BuffAreaEffect)
        for entity in battle.entities.values()
    )
    assert target.hitpoints == hp_before

    battle.step()
    rage = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, BuffAreaEffect)
        and entity.player_id == lumberjack.player_id
    )

    assert not rage.impact_applied
    assert rage.id == bottle.id + 1
    assert target.hitpoints == hp_before
    battle.step()
    assert rage.impact_applied
    assert target.hitpoints == hp_before
    battle.step()
    assert target.hitpoints == hp_before - rage.impact_damage


def test_lumberjack_rage_buff_waits_for_its_own_300ms_area_scan():
    battle = BattleState()
    ally = _spawn_one(battle, "Knight", 0, Position(9.0, 14.0))
    lumberjack = _spawn_one(battle, "Lumberjack", 0, Position(9.0, 14.0))
    lumberjack.take_damage(lumberjack.hitpoints)

    for _ in range(17):
        battle.step()

    rage = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, BuffAreaEffect)
        and entity.player_id == lumberjack.player_id
    )
    # The externally triggered death belongs to boundary1, dispatches its
    # bottle at2, and creates Rage at12. Its first object tick is13.
    assert rage.impact_applied
    assert rage.time_alive == pytest.approx(0.25)
    assert ally.haste_timer == 0.0

    battle.step()
    assert rage.time_alive == pytest.approx(0.3)
    assert ally.haste_timer == pytest.approx(1.0)
    assert ally.movement_speed_buff_multiplier == pytest.approx(1.3)


@pytest.mark.parametrize(
    ("cap_to_area", "expected_refresh"),
    ((False, 1.0), (True, 0.1)),
)
def test_positive_area_buff_falloff_uses_serialized_cap_flag(
    cap_to_area,
    expected_refresh,
):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    ally = _spawn_one(battle, "Knight", 0, Position(9.0, 14.0))
    lumberjack_stats = battle.card_loader.get_card("Lumberjack")
    assert lumberjack_stats is not None
    rage_data = copy.deepcopy(
        lumberjack_stats._raw_entry["summonCharacterData"]
        ["deathAreaEffectData"]["onStartingActionData"]
        ["spawnDataData"]["deathAreaEffectData"]
    )
    if cap_to_area:
        rage_data["capBuffTimeToAreaEffectTime"] = True

    rage = spawn_death_area_object(
        battle,
        player_id=0,
        position=Position(9.0, 14.0),
        card_stats=lumberjack_stats,
        area_data=rage_data,
    )
    assert isinstance(rage, BuffAreaEffect)
    assert rage.cap_buff_time_to_effect is cap_to_area

    # Isolate the last 300 ms area scan. Only 100 ms of the field remains at
    # this scan, while the serialized recipient falloff is a full second.
    rage.time_alive = 5.1
    rage.next_effect_time = 5.4
    rage.impact_applied = True
    rage.update(0.3, battle)

    assert ally.haste_timer == pytest.approx(expected_refresh)


def test_lumberjack_rage_lingers_after_its_area_expires():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    ally = _spawn_one(battle, "Knight", 0, Position(9.0, 14.0))
    lumberjack_stats = battle.card_loader.get_card("Lumberjack")
    assert lumberjack_stats is not None
    rage_data = copy.deepcopy(
        lumberjack_stats._raw_entry["summonCharacterData"]
        ["deathAreaEffectData"]["onStartingActionData"]
        ["spawnDataData"]["deathAreaEffectData"]
    )
    rage = spawn_death_area_object(
        battle,
        player_id=0,
        position=Position(9.0, 14.0),
        card_stats=lumberjack_stats,
        area_data=rage_data,
    )
    rage.time_alive = 5.1
    rage.next_effect_time = 5.4
    rage.impact_applied = True

    rage.update(0.3, battle)
    ally.update_status_effects(0.1)
    rage.update(0.1, battle)

    assert not rage.is_alive
    assert ally.haste_timer == pytest.approx(0.9)
    assert ally.movement_speed_buff_multiplier == pytest.approx(1.3)


def test_skeleton_barrel_breaks_on_building_contact_then_opens_container():
    battle = BattleState(rng=random.Random(6))
    barrel = _spawn_one(battle, "SkeletonBarrel", 0, Position(9.0, 14.0))
    assert barrel.damage == 0
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(Building, Position(9.0, 14.8), 1, cannon_stats)
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    hp_before = cannon.hitpoints

    barrel.attack_cooldown = 0.0
    for _ in range(30):
        barrel.update(battle.dt, battle)
        if not barrel.is_alive:
            break
    assert not barrel.is_alive
    container = next(entity for entity in battle.entities.values() if isinstance(entity, TimedExplosive))
    assert container.explosion_timer == 0.6
    assert container.explosion_radius == 2.0
    assert container.knockback_distance == 1.0
    assert container.death_spawn_radius == 1.48

    knight = _spawn_one(
        battle,
        "Knight",
        1,
        Position(container.position.x + 1.0, container.position.y),
    )
    knight.attack_cooldown = 0.0
    knight._has_attacked_once = True
    knight_hp = knight.hitpoints
    knight_x = knight.position.x
    container.update(0.6, battle)

    assert hp_before - cannon.hitpoints == barrel.card_stats.get_scaled_stat(57)
    assert knight_hp - knight.hitpoints == barrel.card_stats.get_scaled_stat(57)
    assert knight.position.x == knight_x
    for _ in range(9):
        knight.update_movement_component(battle.dt, battle)
    assert knight.position.x == pytest.approx(knight_x + 0.9)
    # Ordinary pushback preserves loaded work instead of forcing a full reload.
    assert knight.attack_cooldown == pytest.approx(
        knight.get_preloaded_attack_time_seconds()
    )
    assert not knight._has_attacked_once
    knight.advance_attack_clock(10.0, target_in_range=False)
    assert knight.attack_cooldown == pytest.approx(
        knight.get_preloaded_attack_time_seconds()
    )
    knight.advance_attack_clock(0.1, target_in_range=True)
    assert knight.attack_cooldown == pytest.approx(
        knight.get_preloaded_attack_time_seconds() - 0.1
    )
    skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    ]
    assert len(skeletons) == 7
    assert all(skeleton.placement_pending for skeleton in skeletons)
    assert all(skeleton.deploy_delay_remaining == 0.5 for skeleton in skeletons)


@pytest.mark.parametrize("fast_path", [False, True])
def test_object_phase_death_spawns_consume_deploy_time_on_birth_frame(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    barrel = _spawn_one(
        battle,
        "SkeletonBarrel",
        0,
        Position(9.0, 14.0),
    )
    barrel.take_damage(barrel.hitpoints)
    container = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, TimedExplosive)
    )
    container.time_alive = container.explosion_timer - battle.dt

    battle.step()

    skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    ]
    assert len(skeletons) == 7
    assert all(skeleton.placement_pending for skeleton in skeletons)
    assert all(
        skeleton.deploy_delay_remaining == pytest.approx(0.45)
        for skeleton in skeletons
    )


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize(
    (
        "card_name",
        "payload_type",
        "payload_name",
        "payload_count",
        "deploy_time_after_birth",
    ),
    [
        ("Balloon", TimedExplosive, None, 1, None),
        ("BombTower", TimedExplosive, None, 1, None),
        ("SkeletonBarrel", TimedExplosive, None, 1, None),
        ("Golem", Troop, "Golemite", 2, 0.0),
        ("LavaHound", Troop, "LavaPups", 6, 0.0),
        ("BattleRam", Troop, "Barbarian", 2, 0.95),
        ("NightWitch", Troop, "Bat", 1, 0.0),
        ("Tombstone", Troop, "Skeleton", 4, 0.0),
    ],
)
def test_object_phase_lethal_hit_ticks_every_enabled_death_payload_on_birth_frame(
    fast_path,
    card_name,
    payload_type,
    payload_name,
    payload_count,
    deploy_time_after_birth,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    if str(stats.card_type).lower() == "building":
        source = battle._spawn_entity(
            Building,
            Position(9.0, 14.0),
            0,
            stats,
        )
        source.deploy_delay_remaining = 0.0
        source.placement_pending = False
        source.on_spawn()
    else:
        source = _spawn_one(
            battle,
            card_name,
            0,
            Position(9.0, 14.0),
        )
    source.hitpoints = 1.0
    source.speed = 0.0

    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(source.position.x, source.position.y),
        player_id=1,
        card_stats=battle.card_loader.get_card("Knight"),
        hitpoints=1,
        max_hitpoints=1,
        damage=1,
        range=0.0,
        sight_range=0.0,
        target_position=Position(source.position.x, source.position.y),
        travel_speed=1.0,
        source_name="Knight",
        primary_target=source,
    )
    projectile.battle_state = battle
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1

    battle.step()

    payloads = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, payload_type)
        and (
            payload_name is None
            or entity.card_stats.name == payload_name
        )
    ]
    assert len(payloads) == payload_count
    if payload_type is TimedExplosive:
        assert all(payload.time_alive == pytest.approx(0.05) for payload in payloads)
    else:
        assert all(
            payload._death_spawn_target_immunity_elapsed_ms == 50
            for payload in payloads
        )
        assert all(
            payload.deploy_delay_remaining
            == pytest.approx(deploy_time_after_birth)
            for payload in payloads
        )


@pytest.mark.parametrize("fast_path", [False, True])
def test_nested_death_area_waits_until_after_container_spawn_boundary(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    barrel = _spawn_one(
        battle,
        "SkeletonBarrel",
        0,
        Position(9.0, 14.0),
    )
    barrel.take_damage(barrel.hitpoints)
    container = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, TimedExplosive)
    )
    container.time_alive = container.explosion_timer - battle.dt

    ice_golem = _spawn_one(
        battle,
        "IceGolem",
        1,
        Position(9.0, 14.0),
    )
    ice_golem.hitpoints = container.explosion_damage

    battle.step()

    slow_field = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, AreaEffect)
        and entity.player_id == ice_golem.player_id
        and entity.speed_multiplier < 1.0
    )
    skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == barrel.player_id
        and entity.card_stats.name == "Skeleton"
    ]
    assert len(skeletons) == 7
    assert slow_field.id < min(skeleton.id for skeleton in skeletons)
    assert slow_field.time_alive == 0.0
    assert all(skeleton.hitpoints == skeleton.max_hitpoints for skeleton in skeletons)
    assert all(
        skeleton.deploy_delay_remaining == pytest.approx(0.45)
        for skeleton in skeletons
    )
    assert all(skeleton.slow_timer == 0 for skeleton in skeletons)
    battle.step()
    assert slow_field.time_alive == pytest.approx(0.05)
    assert all(skeleton.slow_multiplier == pytest.approx(0.7) for skeleton in skeletons)
    assert all(skeleton.slow_timer == pytest.approx(2.0) for skeleton in skeletons)


def test_skeleton_barrel_uses_committed_half_second_contact_countdown():
    battle = BattleState()
    barrel = _spawn_one(battle, "SkeletonBarrel", 0, Position(9.0, 14.0))
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 14.8),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    barrel.attack_cooldown = 0.0
    contact = Position(barrel.position.x, barrel.position.y)

    barrel.update(battle.dt, battle)
    assert barrel.kamikaze_primed
    assert barrel.kamikaze_timer_remaining == pytest.approx(0.5)
    assert barrel.is_alive
    assert not any(isinstance(entity, TimedExplosive) for entity in battle.entities.values())

    # Once the pop animation is committed, the target can disappear without
    # cancelling it and the barrel no longer advances.
    cannon.take_damage(cannon.hitpoints)
    for _ in range(9):
        barrel.update(battle.dt, battle)
    assert barrel.is_alive
    assert barrel.position == contact
    barrel.update(battle.dt, battle)
    assert not barrel.is_alive
    assert any(isinstance(entity, TimedExplosive) for entity in battle.entities.values())


def test_lava_hound_splits_with_native_descending_radial_enumeration():
    for player_id in (0, 1):
        battle = BattleState()
        hound = _spawn_one(battle, "LavaHound", player_id, Position(9.0, 14.0))
        assert hound.card_stats.projectile_start_radius == 1.0
        hound.take_damage(hound.hitpoints)
        pups = [
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Troop) and entity.card_stats.name == "LavaPups"
        ]
        assert len(pups) == 6
        assert all(pup.card_stats.projectile_start_radius == 0.5 for pup in pups)
        assert all(not pup.placement_pending for pup in pups)
        assert all(pup.deploy_delay_remaining == 0.0 for pup in pups)
        assert all(
            pup._native_target_distance_discount_sq_units == 0
            for pup in pups
        )
        expected_offsets = [
            (1.25, -2.165),
            (-1.25, -2.165),
            (-2.5, 0.0),
            (-1.25, 2.165),
            (1.25, 2.165),
            (2.5, 0.0),
        ]
        assert all(pup.position == hound.position for pup in pups)
        assert [
            (
                logic_units_to_tiles(
                    tiles_to_logic_units(
                        pup._death_spawn_travel_target.x - hound.position.x
                    )
                ),
                logic_units_to_tiles(
                    tiles_to_logic_units(
                        pup._death_spawn_travel_target.y - hound.position.y
                    )
                ),
            )
            for pup in pups
        ] == expected_offsets
        assert [
            pup._death_spawn_travel_ticks_remaining for pup in pups
        ] == [9, 9, 10, 9, 9, 10]


@pytest.mark.parametrize("fast_path", [False, True])
def test_death_spawn_pushback_uses_250_unit_noninterrupting_travel(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    hound = _spawn_one(battle, "LavaHound", 0, Position(9.0, 14.0))
    hound.take_damage(hound.hitpoints)
    pups = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "LavaPups"
    ]
    pup = pups[0]
    # This component-only test omits the object cleanup that precedes the
    # children's first battle tick. Remove excluded bodies rather than leaving
    # them resident as death-frame avoidance obstacles.
    battle.entities.pop(hound.id)
    for sibling in pups[1:]:
        battle.entities.pop(sibling.id)

    # The dedicated travel state does not set the ordinary forced-movement
    # combat gate. A child with a live in-range target can launch its attack
    # before its movement component advances the first radial frame.
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.5))
    target.stun_timer = 99.0
    pup.target_id = target.id
    pup.attack_cooldown = 0.0
    pup.update_combat_component(battle.dt, battle)
    assert any(
        isinstance(entity, Projectile)
        and entity.source_name == "LavaPups"
        for entity in battle.entities.values()
    )
    assert not pup.forced_movement_active
    # The movement dispatcher services this state before its stun/deployment
    # branches, so freezing the child does not pause the radial launch.
    pup.stun_timer = 99.0

    expected_positions = [
        (9.125, 13.785),
        (9.249, 13.570),
        (9.373, 13.355),
        (9.498, 13.140),
        (9.622, 12.925),
        (9.746, 12.710),
        (9.870, 12.494),
        (9.995, 12.279),
        (10.119, 12.063),
    ]
    for expected in expected_positions:
        pup.begin_movement_tick()
        try:
            pup.update_movement_component(battle.dt, battle)
        finally:
            pup.finish_movement_tick(battle)
            pup.quantize_logic_position()
        assert (pup.position.x, pup.position.y) == pytest.approx(expected)

    # The native duration truncates 2499 / 250 to nine frames and does not
    # snap the diagonal child to its retained 2500-unit ring coordinate.
    assert pup._death_spawn_travel_ticks_remaining == 0
    assert pup._death_spawn_travel_target is None
    assert pup.position != Position(10.25, 11.835)


def test_death_spawn_pushback_ring_is_world_fixed_without_const_priority():
    targets_by_lane = {}

    for x in (5.0, 13.0):
        battle = BattleState()
        golem = _spawn_one(battle, "Golem", 0, Position(x, 14.0))
        golem.take_damage(golem.hitpoints)
        golemites = [
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Troop)
            and entity.card_stats.name == "Golemite"
        ]
        targets_by_lane[battle.arena.native_path_id_at(golem.position)] = [
            (
                logic_units_to_tiles(
                    tiles_to_logic_units(
                        golemite._death_spawn_travel_target.x - golem.position.x
                    )
                ),
                golemite._native_target_distance_discount_sq_units,
            )
            for golemite in golemites
        ]
        assert all(golemite.position == golem.position for golemite in golemites)

    assert targets_by_lane == {
        1: [(-1.5, 0), (1.5, 0)],
        2: [(-1.5, 0), (1.5, 0)],
    }


@pytest.mark.parametrize("card_name", ["Balloon", "BombTower"])
def test_other_enabled_death_bombs_do_not_inherit_skeleton_barrel_knockback(card_name):
    battle = BattleState()
    entity_type = Building if card_name == "BombTower" else Troop
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    source = battle._spawn_entity(entity_type, Position(9.0, 14.0), 0, stats)
    source.deploy_delay_remaining = 0.0
    source.placement_pending = False
    source.take_damage(source.hitpoints)

    explosive = next(entity for entity in battle.entities.values() if isinstance(entity, TimedExplosive))
    assert explosive.knockback_distance == 0.0
    assert explosive.explosion_radius == 3.0

    knight = _spawn_one(battle, "Knight", 1, Position(10.0, 14.0))
    position_before = Position(knight.position.x, knight.position.y)
    explosive.update(explosive.explosion_timer, battle)
    assert knight.position == position_before


def test_bomb_tower_uses_one_serialized_timed_death_bomb_with_local_hitbox_aoe():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("BombTower")
    assert stats is not None
    tower = battle._spawn_entity(Building, Position(9.0, 14.0), 0, stats)
    tower.deploy_delay_remaining = 0.0
    tower.placement_pending = False
    tower.take_damage(tower.hitpoints)
    payloads = [
        entity for entity in battle.entities.values() if isinstance(entity, TimedExplosive)
    ]
    assert len(payloads) == 1
    bomb = payloads[0]
    assert bomb.explosion_timer == 3.0
    assert bomb.explosion_radius == 3.0

    near_ground = _spawn_one(battle, "Knight", 1, Position(12.4, 14.0))
    near_air = _spawn_one(battle, "BabyDragon", 1, Position(9.0, 17.4))
    far_ground = _spawn_one(battle, "Knight", 1, Position(12.6, 14.0))
    near_ground.position = Position(12.4, 14.0)
    near_air.position = Position(9.0, 17.4)
    far_ground.position = Position(12.6, 14.0)
    hp_before = (near_ground.hitpoints, near_air.hitpoints, far_ground.hitpoints)

    bomb.update(2.999, battle)
    assert (near_ground.hitpoints, near_air.hitpoints, far_ground.hitpoints) == hp_before
    bomb.update(0.002, battle)

    assert hp_before[0] - near_ground.hitpoints == bomb.explosion_damage
    assert hp_before[1] - near_air.hitpoints == bomb.explosion_damage
    assert far_ground.hitpoints == hp_before[2]


@pytest.mark.parametrize(
    ("card_name", "logic_frames"),
    [
        ("SkeletonBarrel", 12),
        ("Balloon", 60),
        ("BombTower", 60),
    ],
)
def test_enabled_death_payloads_explode_on_exact_logic_frame(
    card_name,
    logic_frames,
):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    source_type = Building if card_name == "BombTower" else Troop
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    source = battle._spawn_entity(
        source_type,
        Position(9.0, 14.0),
        0,
        stats,
    )
    source.deploy_delay_remaining = 0.0
    source.placement_pending = False
    source.on_spawn()
    source.take_damage(source.hitpoints)
    explosive = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, TimedExplosive)
    )
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    hp_before = target.hitpoints

    for _ in range(logic_frames - 1):
        explosive.update(battle.dt, battle)

    assert explosive.is_alive
    assert target.hitpoints == hp_before

    explosive.update(battle.dt, battle)

    assert not explosive.is_alive
    assert target.hitpoints == hp_before - explosive.explosion_damage


def test_skeleton_barrel_container_propagates_spawn_const_priority():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("SkeletonBarrel")
    assert stats is not None
    barrel = battle._spawn_entity(
        Troop,
        Position(9.0, 14.0),
        0,
        stats,
    )
    barrel.deploy_delay_remaining = 0.0
    barrel.placement_pending = False
    barrel.take_damage(barrel.hitpoints)

    container = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, TimedExplosive)
    )
    assert container.spawn_const_priority

    # Exercise the serialized priority flag independently of radial pushback.
    # DeathSpawnPushback controls travel only; it never grants this allowance.
    container.death_spawn_pushback = False
    container.update(container.explosion_timer, battle)
    skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.card_stats.name == "Skeleton"
    ]
    assert len(skeletons) == 7
    assert [
        skeleton._native_target_distance_discount_sq_units
        for skeleton in skeletons
    ] == [(index * 80) ** 2 for index in range(7)]


def test_skeleton_barrel_children_combine_pushback_travel_and_const_priority():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    barrel = _spawn_one(
        battle,
        "SkeletonBarrel",
        0,
        Position(9.0, 14.0),
    )
    barrel.take_damage(barrel.hitpoints)
    container = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, TimedExplosive)
    )
    assert container.death_spawn_pushback
    assert container.spawn_const_priority

    container.update(container.explosion_timer, battle)

    skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.card_stats.name == "Skeleton"
    ]
    assert len(skeletons) == 7
    assert all(skeleton.position == container.position for skeleton in skeletons)
    assert all(
        skeleton._death_spawn_travel_target is not None
        for skeleton in skeletons
    )
    assert all(
        skeleton._death_spawn_travel_ticks_remaining == 5
        for skeleton in skeletons
    )
    assert [
        skeleton._native_target_distance_discount_sq_units
        for skeleton in skeletons
    ] == [(index * 80) ** 2 for index in range(7)]


@pytest.mark.parametrize("card_name", ["Balloon", "BombTower", "SkeletonBarrel"])
def test_enabled_timed_death_payloads_reserve_their_placement_footprint(card_name):
    battle = BattleState()
    entity_type = Building if card_name == "BombTower" else Troop
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    source = battle._spawn_entity(entity_type, Position(9.0, 10.0), 0, stats)
    source.deploy_delay_remaining = 0.0
    source.placement_pending = False
    source.take_damage(source.hitpoints)
    payload = next(
        entity for entity in battle.entities.values() if isinstance(entity, TimedExplosive)
    )

    knight_stats = battle.card_loader.get_card("Knight")
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert knight_stats is not None
    assert cannon_stats is not None
    assert battle.is_deployment_payload_occupied(
        payload.position,
        mover_radius=knight_stats.collision_radius or 0.5,
    )
    assert battle.is_deployment_payload_occupied(
        payload.position,
        card_stats=cannon_stats,
    )

    payload.update(payload.explosion_timer, battle)
    assert not battle.is_deployment_payload_occupied(
        payload.position,
        mover_radius=knight_stats.collision_radius or 0.5,
    )
    assert not battle.is_deployment_payload_occupied(
        payload.position,
        card_stats=cannon_stats,
    )


def test_ground_splash_hits_ground_once_and_never_hits_air():
    battle = BattleState()
    valkyrie = _spawn_one(battle, "Valkyrie", 0, Position(3.5, 14.0))
    primary = _spawn_one(battle, "Knight", 1, Position(3.5, 15.0))
    secondary = _spawn_one(battle, "Knight", 1, Position(4.5, 15.0))
    bat = _spawn_one(battle, "Bats", 1, Position(4.0, 15.0))

    primary_hp = primary.hitpoints
    secondary_hp = secondary.hitpoints
    bat_hp = bat.hitpoints
    valkyrie.attack_cooldown = 0.0
    valkyrie.update(battle.dt, battle)

    assert primary_hp - primary.hitpoints == valkyrie.damage
    assert secondary_hp - secondary.hitpoints == valkyrie.damage
    assert bat.hitpoints == bat_hp


def test_self_centered_splash_uses_strict_radius_without_source_hitbox_inflation():
    battle = BattleState()
    valkyrie = _spawn_one(battle, "Valkyrie", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 11.0))
    inside = _spawn_one(
        battle,
        "Knight",
        1,
        Position(
                9.0
                + valkyrie.card_stats.area_damage_radius / 1000.0
                + 0.499,
            10.0,
        ),
    )
    before = inside.hitpoints

    valkyrie._deal_attack_damage(primary, valkyrie.damage, battle)

    assert before - inside.hitpoints == valkyrie.damage

    tangent = _spawn_one(
        battle,
        "Knight",
        1,
        Position(
                9.0
                + valkyrie.card_stats.area_damage_radius / 1000.0
                + 0.5,
            10.0,
        ),
    )
    tangent_before = tangent.hitpoints
    valkyrie._deal_attack_damage(primary, valkyrie.damage, battle)
    assert tangent.hitpoints == tangent_before


def test_spawn_randomness_is_owned_by_each_battle():
    first = BattleState(rng=random.Random(73))
    second = BattleState(rng=random.Random(73))
    first_stats = first.card_loader.get_card("GoblinGang")
    second_stats = second.card_loader.get_card("GoblinGang")
    assert first_stats is not None and second_stats is not None

    first._spawn_troop(Position(9.0, 10.0), 0, first_stats)
    second._spawn_troop(Position(9.0, 10.0), 0, second_stats)

    first_positions = [
        (entity.position.x, entity.position.y)
        for entity in first.entities.values()
        if isinstance(entity, Troop)
    ]
    second_positions = [
        (entity.position.x, entity.position.y)
        for entity in second.entities.values()
        if isinstance(entity, Troop)
    ]
    assert first_positions == second_positions


def test_witches_use_one_second_first_wave_and_stable_data_counts():
    for card_name, spawned_name, expected_count in (
        ("Witch", "Skeleton", 4),
        ("NightWitch", "Bat", 2),
    ):
        battle = BattleState(rng=random.Random(74))
        witch = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
        for _ in range(19):
            witch.update(battle.dt, battle)
        spawned = [
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Troop) and entity.card_stats.name == spawned_name
        ]
        assert spawned == []

        witch.update(battle.dt, battle)
        for expected_so_far in range(1, expected_count + 1):
            spawned = [
                entity
                for entity in battle.entities.values()
                if isinstance(entity, Troop) and entity.card_stats.name == spawned_name
            ]
            assert len(spawned) == expected_so_far
            if expected_so_far < expected_count:
                witch.update(battle.dt, battle)
        assert all(not entity.placement_pending for entity in spawned)
        assert all(entity.deploy_delay_remaining == 0.0 for entity in spawned)
        assert len({(entity.position.x, entity.position.y) for entity in spawned}) == expected_count


def test_miner_travels_from_king_at_650_then_emerges_intangible_and_scaled():
    battle = BattleState()
    miner_stats = battle.card_loader.get_card("Miner")
    assert miner_stats is not None
    before = set(battle.entities)
    battle._spawn_troop(Position(9.0, 20.0), 0, miner_stats)
    miner = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    enemy = _spawn_one(battle, "Knight", 1, Position(9.0, 20.5))
    enemy.stun_timer = 10.0
    hp_before = miner.hitpoints

    origin = battle.arena.BLUE_KING_TOWER
    destination = Position(9.0, 20.0)
    distance_units = round(origin.distance_to(destination) * 1000)
    # Native state 7 splits the 650-unit frame budget into 250-unit movement
    # substeps and tests the full 650-unit reached radius after each one.
    travel_ticks = 26
    assert distance_units == 17000
    assert spawn_path_travel_tick_count(
        distance_units,
        650,
        reached_radius_from_speed=True,
    ) == travel_ticks
    # The global is behavior, not documentation: the former fixed 1000-unit
    # radius completes this nearby boundary case one frame earlier.
    assert spawn_path_travel_tick_count(
        17600,
        650,
        reached_radius_from_speed=True,
    ) == 27
    assert spawn_path_travel_tick_count(
        17600,
        650,
        reached_radius_from_speed=False,
    ) == 26
    travel_seconds = travel_ticks * battle.dt
    tunnel = miner.mechanics[1]
    assert tunnel.travel_speed_logic_units_per_tick == 650
    assert miner.card_stats._raw_entry["summonCharacterData"]["spawnPathfindSpeed"] == 650
    assert miner.position == origin
    assert miner.placement_delay_total == pytest.approx(travel_seconds + 1.0)

    assert miner._special_move_active
    assert not enemy._is_valid_target(miner)
    miner.take_damage(100)
    miner.apply_stun(1.0)
    miner.apply_slow(1.0, 0.5)
    assert miner.hitpoints == hp_before
    assert miner.stun_timer == miner.slow_timer == 0.0

    battle.step()
    assert origin.y < miner.position.y < destination.y
    assert enemy.position == Position(9.0, 20.5)

    for _ in range(travel_ticks - 1):
        battle.step()
    assert miner.position.y == pytest.approx(destination.y)
    assert miner._special_move_active
    assert enemy.position == Position(9.0, 20.5)

    while miner.placement_pending:
        battle.step()
    assert not miner._special_move_active
    # Ordinary body collision begins only after he surfaces.
    assert miner.position.distance_to(destination) <= miner.get_collision_radius()
    assert enemy._is_valid_target(miner)
    enemy.take_damage(enemy.hitpoints)

    tower = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 1
        and entity.card_stats.name == "Tower"
    )
    tower_hp = tower.hitpoints
    full_damage = next(
        mechanic.stored_original_damage
        for mechanic in miner.mechanics
        if type(mechanic).__name__ == "CrownTowerScaling"
    )
    miner.position = Position(tower.position.x, tower.position.y - 1.0)
    miner.target_id = tower.id
    miner.attack_cooldown = 0.0
    for _ in range(30):
        miner.update(battle.dt, battle)
        if tower.hitpoints < tower_hp:
            break
    assert full_damage == 194
    assert miner.damage == full_damage
    assert tower_hp - tower.hitpoints == 39

    troop = _spawn_one(
        battle,
        "Knight",
        1,
        Position(miner.position.x, miner.position.y + 1.0),
    )
    troop.position = Position(miner.position.x, miner.position.y + 1.0)
    troop_hp = troop.hitpoints
    miner.target_id = troop.id
    miner.attack_cooldown = 0.0
    for _ in range(30):
        miner.update(battle.dt, battle)
        if troop.hitpoints < troop_hp:
            break
    assert troop_hp - troop.hitpoints == full_damage


def test_miner_underground_travel_time_depends_on_distance_and_rotates():
    battle = BattleState()
    stats = battle.card_loader.get_card("Miner")
    assert stats is not None

    spawned = []
    for player_id, position in (
        (0, Position(4.0, 22.0)),
        (0, Position(4.0, 27.0)),
        (1, Position(14.0, 10.0)),
    ):
        before = set(battle.entities)
        battle._spawn_troop(position, player_id, stats)
        spawned.append(next(battle.entities[i] for i in battle.entities.keys() - before))

    near, far, rotated = spawned
    assert near.placement_delay_total < far.placement_delay_total
    raw_distance = battle.arena.BLUE_KING_TOWER.distance_to(Position(4.0, 22.0))
    continuous_duration = raw_distance / (650.0 / 50.0)
    assert near._underground_travel_duration == 1.5
    assert near.placement_delay_total == 2.5
    assert near._underground_travel_duration != pytest.approx(continuous_duration)
    assert rotated.position == battle.arena.RED_KING_TOWER


def test_miner_dirt_trail_no_longer_collides_with_troops_underground():
    battle = BattleState()
    ground = _spawn_one(battle, "Knight", 1, Position(8.8, 8.0))
    air = _spawn_one(battle, "Minions", 1, Position(8.8, 8.0))
    ground.stun_timer = 10.0
    air.stun_timer = 10.0
    stats = battle.card_loader.get_card("Miner")
    assert stats is not None
    battle._spawn_troop(Position(9.0, 20.0), 0, stats)

    ground_start = Position(ground.position.x, ground.position.y)
    air_start = Position(air.position.x, air.position.y)
    for _ in range(25):
        battle.step()

    assert ground.position == ground_start
    assert air.position == air_start


def test_first_hit_windup_uses_hit_cycle_minus_recovery_time():
    battle = BattleState()
    cases = (
        ("MiniPekka", 0.5),
        ("Musketeer", 0.7),
        ("Princess", 0.3),
        ("Guards", 0.5),
        ("SpearGoblins", 0.5),
        ("Miner", 0.5),
        ("DartGoblin", 0.35),
        ("Minions", 0.5),
        ("Bats", 0.6),
        ("Skeletons", 0.5),
        ("DarkPrince", 0.4),
        ("BattleRam", 0.05),
    )
    for index, (card_name, expected) in enumerate(cases):
        troop = _spawn_one(
            battle,
            card_name,
            0,
            Position(2.0 + (index % 7) * 2.0, 8.0 + (index // 7) * 2.0),
        )
        assert troop.attack_cooldown == expected


@pytest.mark.parametrize("card_name", ["Minions", "Guards"])
def test_default_three_unit_formation_uses_collision_diameter_spacing(card_name):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None

    battle._spawn_troop(Position(9.0, 10.0), 0, stats)
    troops = list(battle.entities.values())

    assert len(troops) == 3
    expected = {
        (9.0, 10.577),
        (9.499, 9.712),
        (8.501, 9.712),
    }
    assert {(troop.position.x, troop.position.y) for troop in troops} == expected
    assert all(
        coordinate * 1000 == round(coordinate * 1000)
        for troop in troops
        for coordinate in (troop.position.x, troop.position.y)
    )


@pytest.mark.parametrize(
    ("card_name", "stop_after_ms", "wait_ms", "pre_pause_ticks", "rest_ticks"),
    (
        ("Giant", 640, 100, 12, 2),
        ("Golem", 1000, 200, 20, 3),
        ("IceGolem", 470, 80, 9, 1),
    ),
)
def test_serialized_footstep_cycle_pauses_movement(
    card_name,
    stop_after_ms,
    wait_ms,
    pre_pause_ticks,
    rest_ticks,
):
    battle = BattleState()
    walker = _spawn_one(battle, card_name, 0, Position(9.0, 5.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    assert walker.card_stats.stop_movement_after_ms == stop_after_ms
    assert walker.card_stats.wait_ms == wait_ms

    positions = [Position(walker.position.x, walker.position.y)]
    for _ in range(pre_pause_ticks + rest_ticks):
        walker._move_towards_target(target, battle.dt, battle)
        positions.append(Position(walker.position.x, walker.position.y))

    assert all(
        positions[index] != positions[index - 1]
        for index in range(1, pre_pause_ticks + 1)
    )
    assert positions[pre_pause_ticks + 1 :] == (
        [positions[pre_pause_ticks]] * rest_ticks
    )

    walker._move_towards_target(target, battle.dt, battle)
    assert walker.position != positions[-1]


def test_rage_advances_giant_footstep_clock_with_native_per_frame_truncation():
    battle = BattleState()
    giant = _spawn_one(battle, "Giant", 0, Position(9.0, 5.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 20.0))
    giant.apply_haste(10.0, 1.3, 1.3, 1.3)
    # The gait-normalized stride speed is52; Rage floors52*130/100 to67.
    # The independent footstep clock scales100 by130%, then halves to65.

    for _ in range(10):
        giant._move_towards_target(target, battle.dt, battle)

    assert giant.movement_phase_elapsed_ms == 650
    position_after_ten = copy.copy(giant.position)

    giant._move_towards_target(target, battle.dt, battle)
    assert giant.movement_phase_elapsed_ms == 715
    assert giant.position == position_after_ten

    giant._move_towards_target(target, battle.dt, battle)
    assert giant.movement_phase_elapsed_ms == 40
    assert giant.position != position_after_ten


def test_projectile_launched_in_combat_starts_flight_next_frame():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    # Player-one deployment helpers mirror formation offsets; pin the intended
    # absolute test geometry after materializing the target.
    target.position = Position(9.0, 15.0)
    target.apply_stun(10.0)
    musketeer.target_id = target.id
    musketeer.attack_cooldown = 0.0

    battle.step()

    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
    )
    # Creation establishes the launch offset; flight begins next frame.
    assert projectile.position == Position(9.0, 10.45)
    battle.step()
    assert projectile.position == Position(9.0, 11.45)


@pytest.mark.parametrize(
    ("card_name", "overrides_finish", "finish_ms"),
    (
        ("Knight", False, 250),
        ("Valkyrie", True, 100),
        ("Princess", True, 200),
        ("Bowler", True, 150),
        ("ElectroDragon", True, 0),
        ("ElectroWizard", True, 0),
    ),
)
@pytest.mark.parametrize("fast_path", [False, True])
def test_target_removal_finish_gate_respects_native_card_exceptions(
    card_name,
    overrides_finish,
    finish_ms,
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    first = _spawn_one(battle, "Knight", 1, Position(9.0, 12.0))
    second = _spawn_one(battle, "Knight", 1, Position(10.0, 12.0))
    attacker.position = Position(9.0, 10.0)
    first.position = Position(9.0, 12.0)
    second.position = Position(10.0, 12.0)
    attacker.target_id = first.id

    assert attacker.card_stats.override_attack_finish_time is overrides_finish
    assert attacker.card_stats.attack_finish_time == finish_ms
    attacker.attack_cooldown = 0.0
    attacker.update_combat_component(battle.dt, battle)
    assert attacker.target_id == first.id
    assert first.is_alive

    first.take_damage(first.hitpoints)
    battle._cleanup_dead_entities()
    battle._rebuild_target_cache()

    # Native ordinary removal arms the global gate only when the character
    # has no explicit AttackFinishTime override (and no load-first weapon).
    if not overrides_finish:
        for _ in range(5):
            attacker.update_combat_component(battle.dt, battle)
            assert attacker.target_id is None
    attacker.update_combat_component(battle.dt, battle)
    assert attacker.target_id == second.id


@pytest.mark.parametrize("fast_path", [False, True])
def test_troop_target_death_during_windup_respects_finish_interval(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    first = _spawn_one(battle, "Skeletons", 1, Position(9.0, 11.0))
    second = _spawn_one(battle, "Skeletons", 1, Position(10.0, 11.0))

    attacker.update(battle.dt, battle)
    assert attacker.target_id == first.id
    assert attacker._attack_windup_active
    assert first.hitpoints == first.max_hitpoints

    first.take_damage(first.hitpoints)
    battle._cleanup_dead_entities()
    battle._rebuild_target_cache()

    for _ in range(5):
        attacker.update_combat_component(battle.dt, battle)
        assert attacker.target_id is None
    attacker.update_combat_component(battle.dt, battle)
    assert attacker.target_id == second.id


@pytest.mark.parametrize("fast_path", [False, True])
def test_direct_area_attack_cancels_payload_after_target_death(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, "DarkPrince", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Skeletons", 1, Position(9.0, 11.0))
    bystander = _spawn_one(battle, "Knight", 1, Position(10.0, 11.0))
    attacker.position = Position(9.0, 10.0)
    primary.position = Position(9.0, 11.0)
    bystander.position = Position(10.0, 11.0)

    attacker.update_combat_component(battle.dt, battle)
    assert attacker.target_id == primary.id
    assert attacker._attack_windup_active
    bystander_hp = bystander.hitpoints

    primary.take_damage(primary.hitpoints)
    battle._cleanup_dead_entities()
    primary.position = Position(1.0, 1.0)

    attacker.update_combat_component(battle.dt, battle)
    assert attacker.target_id is None
    assert bystander.hitpoints == bystander_hp


@pytest.mark.parametrize("attacker_kind", ("troop", "building"))
@pytest.mark.parametrize("fast_path", [False, True])
def test_projectile_area_attack_cancels_payload_after_target_death(
    attacker_kind,
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    if attacker_kind == "troop":
        attacker = _spawn_one(battle, "Bomber", 0, Position(9.0, 10.0))
    else:
        attacker = battle._spawn_entity(
            Building,
            Position(9.0, 10.0),
            0,
            battle.card_loader.get_card("BombTower"),
        )
        attacker.deploy_delay_remaining = 0.0
        attacker.placement_pending = False
        attacker.on_spawn()
    primary = _spawn_one(battle, "Skeletons", 1, Position(9.0, 13.0))
    bystander = _spawn_one(battle, "Knight", 1, Position(10.0, 13.0))
    primary.position = Position(9.0, 13.0)
    bystander.position = Position(10.0, 13.0)

    attacker.update_combat_component(battle.dt, battle)
    assert attacker.target_id == primary.id
    assert attacker._attack_windup_active
    bystander_hp = bystander.hitpoints
    primary.take_damage(primary.hitpoints)
    battle._cleanup_dead_entities()
    primary.position = Position(1.0, 1.0)

    attacker.update_combat_component(battle.dt, battle)
    assert attacker.target_id is None
    assert bystander.hitpoints == bystander_hp
    assert not any(
        isinstance(entity, Projectile) and entity.source_entity is attacker
        for entity in battle.entities.values()
    )


@pytest.mark.parametrize("fast_path", [False, True])
def test_area_attack_recoil_does_not_run_after_target_death(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, "Firecracker", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    primary.position = Position(9.0, 15.0)
    attacker.attack_cooldown = attacker.get_preloaded_attack_time_seconds()

    attacker.update_combat_component(battle.dt, battle)
    assert attacker._attack_windup_active
    primary.take_damage(primary.hitpoints)
    battle._cleanup_dead_entities()
    primary.position = Position(15.0, 10.0)

    for _ in range(5):
        attacker.update_combat_component(battle.dt, battle)
        assert attacker.position == Position(9.0, 10.0)

    assert not any(
        isinstance(entity, Projectile) and entity.source_entity is attacker
        for entity in battle.entities.values()
    )


@pytest.mark.parametrize("fast_path", [False, True])
def test_building_target_death_during_windup_respects_finish_interval(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 10.0),
        0,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    first = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    second = _spawn_one(battle, "Knight", 1, Position(10.0, 14.0))

    cannon.update(battle.dt, battle)
    assert cannon.target_id == first.id
    assert cannon._attack_windup_active
    assert first.hitpoints == first.max_hitpoints

    first.take_damage(first.hitpoints)
    battle._cleanup_dead_entities()
    battle._rebuild_target_cache()

    for _ in range(5):
        cannon.update_combat_component(battle.dt, battle)
        assert cannon.target_id is None
    cannon.update_combat_component(battle.dt, battle)
    assert cannon.target_id == second.id


def test_first_hit_preload_does_not_finish_while_walking_and_restarts_on_retarget():
    battle = BattleState(rng=random.Random(17))
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    first = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    second = _spawn_one(battle, "Knight", 1, Position(12.0, 14.0))

    first_hit = knight.card_stats.first_hit_time / 1000.0
    assert knight.attack_cooldown == first_hit
    knight.update(battle.dt, battle)
    assert knight.target_id == first.id
    assert knight.attack_cooldown == first_hit

    first.position = Position(9.0, 11.0)
    knight.update(battle.dt, battle)
    assert knight.attack_cooldown < first_hit

    knight.attack_cooldown = 0.0
    knight._has_attacked_once = True
    knight._note_combat_target(first)
    knight._note_combat_target(second)
    assert knight.attack_cooldown == first_hit
    assert not knight._has_attacked_once

    gang_stats = battle.card_loader.get_card("GoblinGang")
    assert gang_stats is not None
    before = set(battle.entities)
    battle._spawn_troop(Position(9.0, 10.0), 0, gang_stats)
    gang = [
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    ]
    melee = [entity for entity in gang if entity.card_stats.name == "Goblin_Stab"]
    ranged = [entity for entity in gang if entity.card_stats.name == "SpearGoblin"]
    assert len(melee) == len(ranged) == 3
    assert {entity.attack_cooldown for entity in melee} == {0.6}
    assert {entity.attack_cooldown for entity in ranged} == {0.5}


def test_full_attack_cycles_only_preload_to_first_hit_without_a_target():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    first_hit = knight.card_stats.first_hit_time / 1000.0

    knight.attack_cooldown = knight.get_base_attack_interval_seconds()
    knight._has_attacked_once = True
    knight.advance_attack_clock(10.0, target_in_range=False)
    assert knight.attack_cooldown == pytest.approx(first_hit)

    knight.advance_attack_clock(0.1, target_in_range=True)
    assert knight.attack_cooldown == pytest.approx(first_hit - 0.1)

    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(Building, Position(9.0, 14.0), 0, cannon_stats)
    cannon.attack_cooldown = cannon.get_base_attack_interval_seconds()
    cannon._has_attacked_once = True
    cannon.advance_attack_clock(10.0, target_in_range=False)
    assert cannon.attack_cooldown == pytest.approx(
        cannon.card_stats.first_hit_time / 1000.0
    )


def test_overloaded_attack_data_drives_inferno_first_hit_and_retarget_preload():
    battle = BattleState()
    dragon = _spawn_one(battle, "InfernoDragon", 0, Position(9.0, 10.0))
    first = _spawn_one(battle, "Knight", 1, Position(9.0, 13.0))
    second = _spawn_one(battle, "Knight", 1, Position(10.0, 13.0))

    assert dragon.attack_cooldown == pytest.approx(0.4)
    dragon._note_combat_target(first)
    dragon.attack_cooldown = dragon.get_base_attack_interval_seconds()
    dragon._note_combat_target(second)
    assert dragon.attack_cooldown == pytest.approx(0.8)

    # Losing the lock starts the same retarget clock, but idle cooling can
    # preload it only as far as the 0.4-second first-hit floor.
    dragon._note_combat_target(None)
    dragon.advance_attack_clock(10.0, target_in_range=False)
    assert dragon.attack_cooldown == pytest.approx(0.4)
    dragon._note_combat_target(first)
    assert dragon.attack_cooldown == pytest.approx(0.4)


@pytest.mark.parametrize("card_name", ["InfernoDragon", "InfernoTower"])
def test_zap_resets_overloaded_inferno_weapon_to_one_hit_speed_cycle(card_name):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    attacker = battle._spawn_entity(
        Building if card_name == "InfernoTower" else Troop,
        Position(9.0, 12.0),
        0,
        stats,
    )
    if isinstance(attacker, Building):
        attacker.deploy_delay_remaining = 0.0
        attacker.placement_pending = False
        attacker.on_spawn()
    target = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))
    attacker.target_id = target.id
    attacker._last_combat_target_id = target.id
    attacker.attack_cooldown = 0.01

    attacker.apply_stun(0.5, source_kind="Zap")

    # Native reset stores LoadTime in the combat component.  On an overloaded
    # weapon (LoadTime > HitSpeed), updateHitTimer discards that marker and
    # begins a fresh HitSpeed counter.  It must not use the 0.8-second ordinary
    # retarget penalty or preserve the nearly-ready channel above.
    assert attacker.card_stats.load_time == 1200
    assert attacker.card_stats.hit_speed == 400
    assert attacker.card_stats.retarget_time == 800
    assert attacker.target_id is None
    assert attacker.attack_cooldown == pytest.approx(0.4)


def test_mobile_continuous_damage_approaches_500_units_closer_then_keeps_full_range():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    dragon = _spawn_one(battle, "InfernoDragon", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.001))
    dragon.target_id = target.id
    ramp = next(
        mechanic
        for mechanic in dragon.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )

    # Both collision radii extend the serialized 3.5-tile range, but a new continuous channel approaches 0.5 tiles
    # closer before combat enters the attack state.
    assert dragon.is_within_attack_reach(target)
    assert not dragon.is_within_attack_engagement_reach(target)
    dragon.update_components(battle.dt, battle)
    assert dragon.position.y > 10.0
    assert ramp._current_target_id is None

    # At the exact reduced boundary the beam connects. Once connected, the
    # same target may move back out to the full serialized range without
    # causing the dragon to chase or reset its ramp.
    dragon.position = Position(9.0, 10.0)
    target.position = Position(9.0, 14.0)
    dragon.update_components(battle.dt, battle)
    assert dragon.position == Position(9.0, 10.0)
    assert ramp._current_target_id == target.id

    target.position = Position(9.0, 14.499)
    connected_ms = ramp._current_target_ms
    dragon.update_components(battle.dt, battle)
    assert dragon.position == Position(9.0, 10.0)
    assert ramp._current_target_id == target.id
    assert ramp._current_target_ms > connected_ms


def test_continuous_damage_approach_is_governed_by_shared_global(monkeypatch):
    import clasher.mechanics.shared.damage_ramp as damage_ramp_module

    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    dragon = _spawn_one(battle, "InfernoDragon", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.001))

    assert not dragon.is_within_attack_engagement_reach(target)
    monkeypatch.setattr(
        damage_ramp_module,
        "LOGIC_CHARACTER_CONTINUOUS_DAMAGE_ATTACK_CLOSER",
        0,
    )
    assert dragon.is_within_attack_engagement_reach(target)


def test_continuous_damage_approach_reduction_does_not_apply_to_buildings():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("InfernoTower")
    assert stats is not None
    tower = battle._spawn_entity(
        Building,
        Position(9.0, 10.0),
        0,
        stats,
    )
    tower.deploy_delay_remaining = 0.0
    tower.placement_pending = False
    tower.on_spawn()
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 16.499))
    target.position = Position(9.0, 16.499)

    assert tower.is_within_attack_reach(target)
    assert tower.is_within_attack_engagement_reach(target)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("card_name", ["InfernoDragon", "InfernoTower"])
def test_inferno_retargets_from_effect_immune_dashing_bandit(
    fast_path,
    card_name,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    if card_name == "InfernoTower":
        attacker = battle._spawn_entity(
            Building,
            Position(9.0, 10.0),
            0,
            stats,
        )
        attacker.deploy_delay_remaining = 0.0
        attacker.placement_pending = False
        attacker.on_spawn()
    else:
        attacker = _spawn_one(
            battle,
            card_name,
            0,
            Position(9.0, 10.0),
        )
    bandit = _spawn_one(battle, "Bandit", 1, Position(9.0, 13.0))
    replacement = _spawn_one(battle, "Knight", 1, Position(10.0, 13.0))
    ordinary_attacker = _spawn_one(
        battle,
        "Knight",
        0,
        Position(8.0, 13.0),
    )
    bandit.position = Position(9.0, 13.0)
    replacement.position = Position(10.0, 13.0)
    bandit._bandit_dashing = True
    bandit._special_move_active = True
    attacker.target_id = bandit.id

    # Dash immunity does not make Bandit globally untargetable. Ordinary
    # weapons retain her, while a continuous-damage channel cannot connect
    # and must acquire another eligible recipient.
    assert bandit.is_targetable_by(attacker.player_id)
    assert ordinary_attacker._is_valid_target(bandit)
    assert not attacker._is_valid_target(bandit)

    attacker.update_combat_component(battle.dt, battle)

    assert attacker.target_id == replacement.id
    ramp = next(
        mechanic
        for mechanic in attacker.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    assert ramp._current_target_id == replacement.id

    bandit._bandit_dashing = False
    bandit._special_move_active = False
    assert attacker._is_valid_target(bandit)


@pytest.mark.parametrize("card_name", ["InfernoDragon", "InfernoTower"])
def test_inferno_damage_stages_use_native_connected_combat_timer(card_name):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    if card_name == "InfernoTower":
        attacker = battle._spawn_entity(
            Building,
            Position(9.0, 12.0),
            0,
            stats,
        )
        attacker.deploy_delay_remaining = 0.0
        attacker.placement_pending = False
        attacker.on_spawn()
    else:
        attacker = _spawn_one(
            battle,
            card_name,
            0,
            Position(9.0, 12.0),
        )
    target = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))
    target.hitpoints = 100_000.0
    target.max_hitpoints = 100_000.0
    attacker.position = Position(9.0, 12.0)
    target.position = Position(9.0, 14.0)
    ramp = next(
        mechanic
        for mechanic in attacker.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    hits = []

    for _ in range(80):
        hp_before = target.hitpoints
        attacker.update(battle.dt, battle)
        if target.hitpoints < hp_before:
            hits.append(hp_before - target.hitpoints)

    assert len(hits) == 10
    assert hits[:4] == [ramp.stages[0][1]] * 4
    assert hits[4:9] == [ramp.stages[1][1]] * 5
    assert hits[9] == ramp.stages[2][1]
    assert ramp._current_target_ms == 4000


@pytest.mark.parametrize(
    ("status", "expected_ramp_work"),
    [
        ("slow", 35.0),
        ("rage", 65.0),
        ("both", 45.0),
    ],
)
def test_inferno_ramp_clock_uses_native_status_scaled_combat_work(
    status,
    expected_ramp_work,
):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    dragon = _spawn_one(
        battle,
        "InfernoDragon",
        0,
        Position(9.0, 12.0),
    )
    target = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))
    dragon.position = Position(9.0, 12.0)
    target.position = Position(9.0, 14.0)
    if status in {"slow", "both"}:
        dragon.apply_slow(1.0, 0.7)
    if status in {"rage", "both"}:
        dragon.apply_haste(1.0, 1.3, 1.3, 1.3)
    ramp = next(
        mechanic
        for mechanic in dragon.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )

    dragon.update(battle.dt, battle)

    assert ramp._current_target_ms == pytest.approx(expected_ramp_work)


@pytest.mark.parametrize("card_name", ["InfernoDragon", "InfernoTower"])
def test_inferno_shield_break_resets_stage_without_changing_target(card_name):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    if card_name == "InfernoTower":
        attacker = battle._spawn_entity(
            Building,
            Position(9.0, 10.0),
            0,
            stats,
        )
    else:
        attacker = _spawn_one(
            battle,
            card_name,
            0,
            Position(9.0, 10.0),
        )
    target = _spawn_one(battle, "DarkPrince", 1, Position(9.0, 12.0))
    shield = next(
        mechanic
        for mechanic in target.mechanics
        if type(mechanic).__name__ == "Shield"
    )
    ramp = next(
        mechanic
        for mechanic in attacker.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    shield.current_shield = 1
    attacker.target_id = target.id
    ramp._current_target_id = target.id
    ramp._current_target_ms = 4000.0
    attacker.damage = ramp.stages[-1][1]
    hp_before = target.hitpoints

    attacker._deal_attack_damage(target, attacker.damage, battle)

    assert shield.current_shield == 0
    assert target.hitpoints == hp_before
    assert attacker.target_id == target.id
    assert ramp._current_target_id == target.id
    assert ramp._current_target_ms == 0.0
    assert attacker.damage == ramp.stages[0][1]


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("card_name", ["InfernoDragon", "InfernoTower"])
def test_external_shield_break_resets_connected_inferno_immediately(
    card_name,
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    if card_name == "InfernoTower":
        inferno = battle._spawn_entity(
            Building,
            Position(9.0, 10.0),
            0,
            stats,
        )
    else:
        inferno = _spawn_one(
            battle,
            card_name,
            0,
            Position(9.0, 10.0),
        )
    ally = _spawn_one(battle, "Knight", 0, Position(8.0, 10.0))
    target = _spawn_one(battle, "DarkPrince", 1, Position(9.0, 12.0))
    shield = next(
        mechanic
        for mechanic in target.mechanics
        if type(mechanic).__name__ == "Shield"
    )
    ramp = next(
        mechanic
        for mechanic in inferno.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    shield.current_shield = 1
    inferno.target_id = target.id
    ramp._current_target_id = target.id
    ramp._current_target_ms = 4000.0
    inferno.damage = ramp.stages[-1][1]

    ally._deal_attack_damage(target, ally.damage, battle)

    assert shield.current_shield == 0
    assert target._shield_break_count == 1
    assert inferno.target_id == target.id
    assert ramp._current_target_id == target.id
    assert ramp._current_target_ms == 0.0
    assert inferno.damage == ramp.stages[0][1]
    hp_before_inferno_hit = target.hitpoints

    inferno._deal_attack_damage(target, inferno.damage, battle)

    assert target.hitpoints == hp_before_inferno_hit - ramp.stages[0][1]
    assert inferno.target_id == target.id
    assert ramp._current_target_id == target.id
    assert ramp._current_target_ms == 0.0
    assert inferno.damage == ramp.stages[0][1]


def test_shield_break_consumes_damage_but_not_status_or_knockback_payloads():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    guard = _spawn_one(battle, "Guards", 1, Position(9.0, 12.0))
    shield = next(
        mechanic
        for mechanic in guard.mechanics
        if type(mechanic).__name__ == "Shield"
    )
    hp_before = guard.hitpoints
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(guard.position.x, guard.position.y),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=shield.current_shield + hp_before,
        range=0.0,
        sight_range=0.0,
        target_position=Position(guard.position.x, guard.position.y),
        travel_speed=1.0,
        source_name="shield-break-probe",
        stun_duration=0.5,
        knockback_distance=1.0,
        primary_target=guard,
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1

    projectile.update(battle.dt, battle)

    assert shield.current_shield == 0
    assert guard.hitpoints == hp_before
    assert guard.stun_timer == pytest.approx(0.5)
    assert guard.forced_movement_active


def test_lethal_projectiles_reserve_targets_and_respect_shield_hit_consumption():
    battle = BattleState()
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    first = _spawn_one(battle, "Knight", 1, Position(9.0, 13.0))
    second = _spawn_one(battle, "Knight", 1, Position(10.0, 13.0))

    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(musketeer.position.x, musketeer.position.y),
        player_id=0,
        card_stats=musketeer.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=first.hitpoints,
        range=0.0,
        sight_range=0.0,
        target_position=Position(first.position.x, first.position.y),
        travel_speed=10.0,
        source_name="Musketeer",
        source_entity=musketeer,
        primary_target=first,
    )
    projectile.battle_state = battle
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1

    assert first.is_expected_to_die_from_projectiles()
    assert musketeer.get_nearest_target(battle.entities) is second

    guard = _spawn_one(battle, "Guards", 1, Position(8.0, 13.0))
    shield = next(mechanic for mechanic in guard.mechanics if type(mechanic).__name__ == "Shield")
    shield_breaker = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=musketeer.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=shield.current_shield,
        range=0.0,
        sight_range=0.0,
        target_position=Position(guard.position.x, guard.position.y),
        travel_speed=10.0,
        primary_target=guard,
    )
    shield_breaker.battle_state = battle
    battle.entities[shield_breaker.id] = shield_breaker
    battle.next_entity_id += 1
    assert not guard.is_expected_to_die_from_projectiles()

    finisher = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=musketeer.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=guard.hitpoints,
        range=0.0,
        sight_range=0.0,
        target_position=Position(guard.position.x, guard.position.y),
        travel_speed=10.0,
        primary_target=guard,
    )
    finisher.battle_state = battle
    battle.entities[finisher.id] = finisher
    # Native HitpointComponent::isEnoughToKill always returns false while a
    # protection shield is live, even when separate committed hits can break
    # the shield and then defeat the underlying unit.
    assert not guard.is_expected_to_die_from_projectiles()

    shield.current_shield = 0
    assert guard.is_expected_to_die_from_projectiles()


@pytest.mark.parametrize("fast_path", [False, True])
def test_only_projectile_attackers_skip_lethally_reserved_targets(fast_path):
    battle = BattleState(fast_path=fast_path)
    ranged = _spawn_one(battle, "Musketeer", 0, Position(8.0, 10.0))
    melee = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    first = _spawn_one(battle, "Skeletons", 1, Position(9.0, 13.0))
    second = _spawn_one(battle, "Skeletons", 1, Position(10.5, 13.0))
    first.hitpoints = ranged.damage

    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(ranged.position.x, ranged.position.y),
        player_id=0,
        card_stats=ranged.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=first.hitpoints,
        range=0.0,
        sight_range=0.0,
        target_position=Position(first.position.x, first.position.y),
        travel_speed=10.0,
        source_name="Musketeer",
        source_entity=ranged,
        primary_target=first,
    )
    projectile.battle_state = battle
    battle.entities[projectile.id] = projectile
    if fast_path:
        battle._refresh_fast_path_caches()

    assert first.is_expected_to_die_from_projectiles()
    assert ranged.ignores_targets_with_pending_projectile_damage()
    assert not melee.ignores_targets_with_pending_projectile_damage()
    assert ranged.get_nearest_target(battle.entities) is second
    assert melee.get_nearest_target(battle.entities) is first


@pytest.mark.parametrize(
    ("distance_units", "expected_duration_ms", "expected_reserved"),
    [
        (2999, 600, True),
        (3000, 600, True),
        # The native duration division truncates 600.8 ms to 600 before the
        # target rounds to its 50 ms bookkeeping grid.
        (3004, 600, True),
        (3005, 650, False),
    ],
)
def test_pending_projectile_reservation_uses_native_600ms_duration_cutoff(
    distance_units,
    expected_duration_ms,
    expected_reserved,
):
    battle = BattleState()
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    target = _spawn_one(
        battle,
        "Skeletons",
        1,
        Position(9.0, 10.0 + logic_units_to_tiles(distance_units)),
    )
    target.hitpoints = musketeer.damage
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=musketeer.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=target.hitpoints,
        range=0.0,
        sight_range=0.0,
        target_position=Position(target.position.x, target.position.y),
        travel_speed=logic_speed_to_tiles_per_second(250),
        source_name="Musketeer",
        source_entity=musketeer,
        primary_target=target,
    )
    projectile.battle_state = battle
    battle.entities[projectile.id] = projectile

    assert target._pending_projectile_max_duration_ms == expected_duration_ms
    assert target.is_expected_to_die_from_projectiles() is expected_reserved


def test_pending_damage_duration_cutoff_is_governed_by_shared_global(monkeypatch):
    import clasher.entities as entity_module

    battle = BattleState()
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Skeletons", 1, Position(9.0, 13.0))
    target.hitpoints = musketeer.damage
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=musketeer.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=target.hitpoints,
        range=0.0,
        sight_range=0.0,
        target_position=Position(target.position.x, target.position.y),
        travel_speed=logic_speed_to_tiles_per_second(250),
        source_name="Musketeer",
        source_entity=musketeer,
        primary_target=target,
    )
    projectile.battle_state = battle
    battle.entities[projectile.id] = projectile

    assert target._pending_projectile_max_duration_ms == 600
    assert target.is_expected_to_die_from_projectiles()
    monkeypatch.setattr(
        entity_module,
        "LOGIC_PENDING_DAMAGE_IGNORE_IF_DURATION_LESS",
        550,
    )
    assert not target.is_expected_to_die_from_projectiles()


def test_pending_projectile_duration_counts_down_after_launch_and_removal():
    battle = BattleState()
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Skeletons", 1, Position(9.0, 13.0))
    target.hitpoints = musketeer.damage

    short = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=musketeer.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=target.hitpoints,
        range=0.0,
        sight_range=0.0,
        target_position=Position(target.position.x, target.position.y),
        travel_speed=logic_speed_to_tiles_per_second(250),
        source_name="Musketeer",
        source_entity=musketeer,
        primary_target=target,
    )
    short.battle_state = battle
    battle.entities[short.id] = short
    battle.next_entity_id += 1
    assert target.is_expected_to_die_from_projectiles()

    long = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=musketeer.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=1,
        range=0.0,
        sight_range=0.0,
        target_position=Position(target.position.x, target.position.y),
        travel_speed=logic_speed_to_tiles_per_second(200),
        source_name="Musketeer",
        source_entity=musketeer,
        primary_target=target,
    )
    long.battle_state = battle
    battle.entities[long.id] = long

    assert target._pending_projectile_max_duration_ms == 750
    assert not target.is_expected_to_die_from_projectiles()

    # Projectile removal subtracts damage but does not reset the timer.
    long.is_alive = False
    assert target._pending_projectile_max_duration_ms == 750
    assert not target.is_expected_to_die_from_projectiles()

    # Native character object ticks decrement the aggregate even after the
    # long projectile disappears. The surviving lethal shot becomes eligible
    # for target rejection once the remaining duration reaches 600 ms.
    for expected in (700, 650):
        target.tick_character_object_phase(0.05)
        assert target._pending_projectile_max_duration_ms == expected
        assert not target.is_expected_to_die_from_projectiles()
    target.tick_character_object_phase(0.05)
    assert target._pending_projectile_max_duration_ms == 600
    assert target.is_expected_to_die_from_projectiles()
    for _ in range(13):
        target.tick_character_object_phase(0.05)
    assert target._pending_projectile_max_duration_ms == 0

@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("has_attacked", [False, True])
@pytest.mark.parametrize("keep_pending", [False, True])
@pytest.mark.parametrize("global_enabled", [False, True])
def test_current_target_pending_damage_retention(
    fast_path, has_attacked, keep_pending, global_enabled, monkeypatch
):
    monkeypatch.setattr(
        "clasher.entities.CURRENT_TARGET_IGNORES_PENDING_DAMAGE", global_enabled
    )
    battle = BattleState(fast_path=fast_path)
    locked = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    observer = _spawn_one(battle, "Musketeer", 0, Position(8.0, 10.0))
    first = _spawn_one(battle, "Skeletons", 1, Position(9.0, 13.0))
    second = _spawn_one(battle, "Skeletons", 1, Position(11.0, 13.0))
    first.hitpoints = locked.damage

    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 11.0),
        player_id=0,
        card_stats=locked.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=first.hitpoints,
        range=0.0,
        sight_range=0.0,
        target_position=Position(first.position.x, first.position.y),
        travel_speed=10.0,
        source_name="Musketeer",
        source_entity=observer,
        primary_target=first,
    )
    projectile.battle_state = battle
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    locked.target_id = first.id
    locked.attack_cooldown = 1.0
    locked._has_attacked_once = has_attacked
    locked._has_attacked_current_target = has_attacked
    locked._last_combat_target_id = first.id
    locked.card_stats.keep_target_with_pending_damage = keep_pending
    retains_target = has_attacked and keep_pending and global_enabled

    if fast_path:
        battle._refresh_fast_path_caches()

    assert first.is_expected_to_die_from_projectiles()
    assert not locked._is_valid_target(first)
    assert locked._is_valid_target(first, is_current_target=True) == retains_target
    assert observer.get_nearest_target(battle.entities) is second

    locked.update(battle.dt, battle)

    assert locked.target_id == (first.id if retains_target else second.id)
    assert locked._combat_target_pending_lethal == retains_target
    if retains_target:
        cooldown = locked.attack_cooldown
        locked.on_combat_target_removed(first.id)
        assert locked.target_id is None
        assert not locked._combat_target_pending_lethal
        assert locked._attack_finish_elapsed_ms == 0
        assert locked._last_combat_target_id is None
        assert locked.attack_cooldown == cooldown
        locked.target_id = second.id
        locked._note_combat_target(second)
        assert not locked._has_attacked_current_target


@pytest.mark.parametrize("fast_path", [False, True])
def test_pending_lethality_observes_prior_melee_damage_in_same_combat_phase(fast_path):
    battle = BattleState(fast_path=fast_path)
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 12.0))
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 12.5))
    target.hitpoints = knight.damage + musketeer.damage
    target.attack_cooldown = 10.0
    knight.target_id = target.id
    knight._last_combat_target_id = target.id
    knight.attack_cooldown = 0.0
    musketeer.target_id = target.id
    musketeer._last_combat_target_id = target.id
    musketeer._has_attacked_current_target = True
    musketeer._has_attacked_once = True
    musketeer.attack_cooldown = 0.9
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 7.0),
        player_id=0,
        card_stats=musketeer.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=musketeer.damage,
        range=0.0,
        sight_range=0.0,
        target_position=Position(target.position.x, target.position.y),
        travel_speed=10.0,
        source_name="Musketeer",
        source_entity=musketeer,
        primary_target=target,
    )
    projectile.battle_state = battle
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    assert not target.is_expected_to_die_from_projectiles()

    # Native Knight/Cannon/Archer trace628: the earlier melee component makes
    # existing pending damage lethal before the later ranged observer runs.
    battle.step()
    assert target.hitpoints == musketeer.damage
    assert target.is_alive and projectile.is_alive
    assert musketeer.target_id == target.id
    assert musketeer._combat_target_pending_lethal
    target.take_damage(target.hitpoints)
    battle._cleanup_dead_entities()
    assert musketeer.target_id is None
    assert musketeer._attack_finish_elapsed_ms == 0


def test_non_homing_splash_projectiles_do_not_reserve_lethal_targets():
    battle = BattleState()
    bomber = _spawn_one(battle, "Bomber", 0, Position(9.0, 10.0))
    observer = _spawn_one(battle, "Musketeer", 0, Position(8.0, 10.0))
    first = _spawn_one(battle, "Knight", 1, Position(9.0, 13.0))
    second = _spawn_one(battle, "Knight", 1, Position(11.0, 13.0))
    first.hitpoints = bomber.damage

    bomber.target_id = first.id
    bomber.attack_cooldown = 0.0
    bomber.update(battle.dt, battle)
    bomb = max(
        (entity for entity in battle.entities.values() if isinstance(entity, Projectile)),
        key=lambda entity: entity.id,
    )

    assert not bomb.reserves_pending_damage
    assert not first.is_expected_to_die_from_projectiles()
    assert observer.get_nearest_target(battle.entities) is first
    assert second.is_alive


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("card_name", ["Witch", "BabyDragon", "IceWizard"])
def test_homing_splash_projectiles_reserve_their_primary_target(
    card_name,
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    attacker = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    first = _spawn_one(battle, "Skeletons", 1, Position(9.0, 13.0))
    second = _spawn_one(battle, "Skeletons", 1, Position(11.0, 13.0))
    first.hitpoints = attacker.damage
    projectile_data = attacker.card_stats.projectile_data
    assert projectile_data
    assert bool(projectile_data.get("homing", True))
    assert float(projectile_data.get("radius", 0) or 0) > 0

    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(attacker.position.x, attacker.position.y),
        player_id=0,
        card_stats=attacker.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=first.hitpoints,
        range=0.0,
        sight_range=0.0,
        target_position=Position(first.position.x, first.position.y),
        travel_speed=logic_speed_to_tiles_per_second(
            projectile_data.get("speed", 500)
        ),
        splash_radius=float(projectile_data["radius"]) / 1000.0,
        source_name=card_name,
        source_entity=attacker,
        primary_target=first,
        tracks_target=True,
    )
    projectile.battle_state = battle
    battle.entities[projectile.id] = projectile

    assert projectile.reserves_pending_damage
    assert first.is_expected_to_die_from_projectiles()
    assert attacker.get_nearest_target(battle.entities) is second


def test_hidden_tesla_is_bypassed_until_triggered_and_allows_earthquake_and_freeze():
    battle = BattleState()
    tesla_stats = battle.card_loader.get_card("Tesla")
    assert tesla_stats is not None
    assert (
        tesla_stats.hit_speed,
        tesla_stats.load_time,
        tesla_stats.first_hit_time,
    ) == (1100, 700, 400)
    tesla = battle._spawn_entity(Building, Position(9.0, 14.0), 1, tesla_stats)
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    hog = _spawn_one(battle, "HogRider", 0, Position(9.0, 7.0))
    knight = _spawn_one(battle, "Knight", 0, Position(8.0, 7.0))

    # Native construction starts at phase zero, so this initial idle
    # transition is exposed and ordinary damage can reach it.
    assert not tesla._hidden_building
    initial_hp = tesla.hitpoints
    tesla.take_damage(100, source_kind="Fireball")
    assert tesla.hitpoints == initial_hp - 100
    mechanic = next(
        mechanic
        for mechanic in tesla.mechanics
        if type(mechanic).__name__ == "HideWhenIdle"
    )
    _advance_tesla_hide(mechanic, tesla, 799)
    assert not tesla._hidden_building
    _advance_tesla_hide(mechanic, tesla, 1)
    assert tesla._hidden_building
    assert hog.get_nearest_target(battle.entities) is not tesla
    assert knight.get_nearest_target(battle.entities) is not tesla
    assert not hog.can_attack_target(tesla)

    hp_before = tesla.hitpoints
    tesla.take_damage(100, source_kind="Fireball")
    assert tesla.hitpoints == hp_before
    tesla.take_damage(
        100,
        source_kind="Earthquake",
        affects_hidden=True,
    )
    assert tesla.hitpoints == hp_before - 100
    tesla.take_damage(
        100,
        source_kind="Freeze",
        affects_hidden=True,
    )
    assert tesla.hitpoints == hp_before - 200

    hog.position = Position(9.0, 9.0)
    tesla.update(battle.dt, battle)
    assert not tesla._hidden_building
    hog.position = Position(9.0, 12.8)
    assert hog.can_attack_target(tesla)

    # Finish the remaining rise phase before measuring a complete hide.
    _advance_tesla_hide(mechanic, tesla, 750)
    assert mechanic._phase_ms == 0.0

    hog.position = Position(9.0, 7.0)
    assert mechanic.hide_delay_ms == 800
    _advance_tesla_hide(mechanic, tesla, 799)
    assert not tesla._hidden_building
    _advance_tesla_hide(mechanic, tesla, 1)
    assert tesla._hidden_building


@pytest.mark.parametrize("fast_path", [False, True])
def test_hidden_tesla_reveal_redirects_wall_breaker_before_contact(fast_path):
    """Exercise the live Tesla/Wall Breaker interaction as one complete lock."""
    battle = BattleState(fast_path=fast_path)
    tesla = battle._spawn_entity(
        Building,
        Position(9.0, 15.0),
        1,
        battle.card_loader.get_card("Tesla"),
    )
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    tesla.on_spawn()
    _fully_hide_tesla(tesla)
    wall_breaker = _spawn_one(
        battle,
        "Wallbreakers",
        0,
        Position(9.0, 8.0),
    )

    initial_target = wall_breaker.get_nearest_target(battle.entities)
    assert initial_target is not None
    assert initial_target is not tesla
    wall_breaker.target_id = initial_target.id

    # A hidden Tesla cannot be acquired. Once the Wall Breaker enters the
    # Tesla's own attack reach, the shared hide state reveals the building and
    # ordinary building-only targeting redirects to it on the next combat
    # component.
    wall_breaker.position = Position(9.0, 9.1)
    battle.sync_fast_target_entity(wall_breaker)
    hide = next(
        mechanic
        for mechanic in tesla.mechanics
        if type(mechanic).__name__ == "HideWhenIdle"
    )
    _advance_tesla_hide(hide, tesla, 50)
    assert not tesla._hidden_building

    wall_breaker.update_combat_component(battle.dt, battle)
    assert wall_breaker.target_id == tesla.id

    # The redirected contact uses the same data-scaled kamikaze payload as
    # every other building target; revealing Tesla must not create a special
    # damage or targeting path.
    wall_breaker.position = Position(9.0, 14.1)
    battle.sync_fast_target_entity(wall_breaker)
    wall_breaker.attack_cooldown = 0.0
    tesla_hp = tesla.hitpoints
    wall_breaker.update_combat_component(battle.dt, battle)

    assert not wall_breaker.is_alive
    assert tesla.hitpoints == tesla_hp
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and entity.source_entity is wall_breaker
    )
    projectile.update(battle.dt, battle)
    assert tesla_hp - tesla.hitpoints == wall_breaker.damage

    replacement = _spawn_one(
        battle,
        "Wallbreakers",
        0,
        Position(9.0, 8.0),
    )
    assert replacement.get_nearest_target(battle.entities) is tesla
    replacement.target_id = tesla.id

    # Retraction is the inverse targetability transition and must invalidate
    # an accelerated-engine lock just as reveal publishes a new candidate.
    _advance_tesla_hide(hide, tesla, 750)
    _advance_tesla_hide(hide, tesla, 800)
    assert tesla._hidden_building
    replacement.update_combat_component(battle.dt, battle)
    assert replacement.target_id != tesla.id


def test_hidden_tesla_lifetime_decay_bypasses_underground_damage_immunity():
    battle = BattleState(rng=random.Random(72))
    stats = battle.card_loader.get_card("Tesla")
    assert stats is not None
    tesla = battle._spawn_entity(Building, Position(9.0, 10.0), 0, stats)
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    tesla.on_spawn()
    _fully_hide_tesla(tesla)
    assert tesla._hidden_building
    hp_before = tesla.hitpoints

    tesla.update(1.0, battle)
    decay_rate = 5000 * int(tesla.max_hitpoints) // stats.lifetime_ms
    assert tesla.hitpoints == hp_before - decay_rate * 20 // 100
    assert tesla.lifetime_decay_work == decay_rate * 20 % 100

    for _ in range(24):
        tesla.update(1.0, battle)
    assert tesla.is_alive
    assert tesla.hitpoints == 2.0

    tesla.update(battle.dt, battle)
    assert not tesla.is_alive
    assert tesla.hitpoints == 0.0


@pytest.mark.parametrize("fast_path", [False, True])
def test_projectile_impacts_respect_hidden_tesla_immunity(fast_path):
    battle = BattleState(fast_path=fast_path)
    tesla = battle._spawn_entity(
        Building,
        Position(9.0, 14.0),
        1,
        battle.card_loader.get_card("Tesla"),
    )
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    tesla.on_spawn()
    hide = next(
        mechanic
        for mechanic in tesla.mechanics
        if type(mechanic).__name__ == "HideWhenIdle"
    )
    musketeer = _spawn_one(
        battle,
        "Musketeer",
        0,
        Position(9.0, 8.0),
    )
    # A target inside reach holds the freshly constructed phase at zero.
    _advance_tesla_hide(hide, tesla, 800)
    assert not tesla._hidden_building

    musketeer._create_projectile(tesla, battle)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and entity.source_entity is musketeer
    )
    assert projectile.tracks_target
    hp_before = tesla.hitpoints

    # Once the shooter leaves Tesla's range, the building fully retracts
    # before the slow in-flight shot reaches it.
    musketeer.position = Position(1.0, 1.0)
    _advance_tesla_hide(hide, tesla, 800)
    assert tesla._hidden_building
    assert not tesla.can_receive_effect("Musketeer")

    for _ in range(120):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break

    assert not projectile.is_alive
    assert tesla.hitpoints == hp_before

    # Splash also excludes a Tesla that is hidden by arrival time.
    baby_dragon = _spawn_one(
        battle,
        "BabyDragon",
        0,
        Position(9.0, 8.0),
    )
    _advance_tesla_hide(hide, tesla, 800)
    assert not tesla._hidden_building
    baby_dragon._create_projectile(tesla, battle)
    splash = max(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Projectile)
            and entity.source_entity is baby_dragon
        ),
        key=lambda entity: entity.id,
    )
    assert splash.tracks_target
    assert splash.splash_radius > 0.0
    baby_dragon.position = Position(1.0, 1.0)
    _advance_tesla_hide(hide, tesla, 800)
    assert tesla._hidden_building
    hp_before_splash = tesla.hitpoints

    for _ in range(120):
        splash.update(battle.dt, battle)
        if not splash.is_alive:
            break

    assert not splash.is_alive
    assert tesla.hitpoints == hp_before_splash


def test_freeze_pauses_hidden_tesla_reveal_and_visible_tesla_retraction():
    battle = BattleState()
    tesla_stats = battle.card_loader.get_card("Tesla")
    assert tesla_stats is not None
    tesla = battle._spawn_entity(Building, Position(9.0, 14.0), 1, tesla_stats)
    tesla.deploy_delay_remaining = 0.0
    tesla.placement_pending = False
    tesla.on_spawn()
    _fully_hide_tesla(tesla)
    hog = _spawn_one(battle, "HogRider", 0, Position(9.0, 12.5))
    mechanic = next(
        mechanic
        for mechanic in tesla.mechanics
        if type(mechanic).__name__ == "HideWhenIdle"
    )

    tesla.apply_stun(
        0.5,
        source_kind="Freeze",
        affects_hidden=True,
    )
    _advance_tesla_hide(mechanic, tesla, 500)
    assert tesla._hidden_building

    tesla.update_status_effects(0.5)
    _advance_tesla_hide(mechanic, tesla, 1)
    assert not tesla._hidden_building
    _advance_tesla_hide(mechanic, tesla, 799)
    assert mechanic._phase_ms == 0.0

    hog.position = Position(1.0, 1.0)
    tesla.apply_stun(2.0, source_kind="Freeze")
    _advance_tesla_hide(mechanic, tesla, 2000)
    assert not tesla._hidden_building

    tesla.update_status_effects(2.0)
    _advance_tesla_hide(mechanic, tesla, 799)
    assert not tesla._hidden_building
    _advance_tesla_hide(mechanic, tesla, 1)
    assert tesla._hidden_building


def test_enabled_spawners_preserve_first_wave_and_intra_wave_timing():
    tomb_battle = BattleState()
    tomb_stats = tomb_battle.card_loader.get_card("Tombstone")
    assert tomb_stats is not None
    tomb = tomb_battle._spawn_entity(
        Building,
        Position(9.0, 10.0),
        0,
        tomb_stats,
    )
    tomb.deploy_delay_remaining = 0.0
    assert tomb.damage == 0

    def skeleton_count(battle):
        return sum(
            isinstance(entity, Troop)
            and entity.player_id == 0
            and entity.card_stats.name == "Skeleton"
            for entity in battle.entities.values()
        )

    tomb_spawner = next(
        mechanic
        for mechanic in tomb.mechanics
        if type(mechanic).__name__ == "PeriodicSpawner"
    )
    assert tomb_spawner.spawn_radius_tiles == 0.0

    # Deployment and production use separate clocks. Tombstone's first pair
    # starts after its serialized 3.5-second cadence, with the two Skeletons
    # separated by the serialized half-second intra-wave gap.
    tomb_spawner.on_object_tick(tomb, 3499)
    assert skeleton_count(tomb_battle) == 0
    tomb_spawner.on_object_tick(tomb, 1)
    assert skeleton_count(tomb_battle) == 1
    tomb_spawner.on_object_tick(tomb, 499)
    assert skeleton_count(tomb_battle) == 1
    tomb_spawner.on_object_tick(tomb, 1)
    assert skeleton_count(tomb_battle) == 2
    tomb_skeletons = [
        entity
        for entity in tomb_battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    ]
    # Missing SpawnRadius is not an implicit 1.5-tile ring. Native character
    # spawning tries the same owner-forward terrain candidate for each child,
    # and does not reject a sibling already occupying it.
    assert [
        (
            skeleton.position.x - tomb.position.x,
            skeleton.position.y - tomb.position.y,
        )
        for skeleton in tomb_skeletons
    ] == pytest.approx([(0.0, 1.5), (0.0, 1.5)])

    witch_battle = BattleState()
    witch = _spawn_one(witch_battle, "Witch", 0, Position(9.0, 10.0))
    witch.speed = 0.0
    witch_spawner = next(
        mechanic
        for mechanic in witch.mechanics
        if type(mechanic).__name__ == "PeriodicSpawner"
    )
    assert witch_spawner.first_spawn_delay_ms == 1000
    assert witch_spawner.spawn_radius_tiles == 2.0
    for _ in range(19):
        witch.update(witch_battle.dt, witch_battle)
    assert skeleton_count(witch_battle) == 0
    wave_origin = Position(witch.position.x, witch.position.y)
    witch.update(witch_battle.dt, witch_battle)
    assert skeleton_count(witch_battle) == 1
    for expected_count in (2, 3, 4):
        witch.update(witch_battle.dt, witch_battle)
        assert skeleton_count(witch_battle) == expected_count
    assert skeleton_count(witch_battle) == 4
    witch_skeletons = [
        entity
        for entity in witch_battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    ]
    assert all(
        wave_origin.distance_to(skeleton.position) == pytest.approx(2.0)
        for skeleton in witch_skeletons
    )
    witch_offsets = [
        (
            skeleton.position.x - wave_origin.x,
            skeleton.position.y - wave_origin.y,
        )
        for skeleton in witch_skeletons
    ]
    for actual, expected in zip(
        witch_offsets,
        ((0.0, -2.0), (-2.0, 0.0), (0.0, 2.0), (2.0, 0.0)),
        strict=True,
    ):
        assert actual == pytest.approx(expected)

    # Night Witch embeds the shared troop under the singular raw name `Bat`.
    # Its spawned units must retain the same live combat timing as deck Bats.
    night_battle = BattleState()
    night_witch = _spawn_one(
        night_battle,
        "NightWitch",
        0,
        Position(9.0, 10.0),
    )
    night_spawner = next(
        mechanic
        for mechanic in night_witch.mechanics
        if type(mechanic).__name__ == "PeriodicSpawner"
    )
    assert night_spawner.first_spawn_delay_ms == 1000
    assert night_spawner.spawn_radius_tiles == 1.5
    night_spawner.on_object_tick(night_witch, 1000)
    assert sum(
        isinstance(entity, Troop) and entity.card_stats.name == "Bat"
        for entity in night_battle.entities.values()
    ) == 1
    night_spawner.on_object_tick(night_witch, 50)
    spawned_bats = [
        entity
        for entity in night_battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Bat"
    ]
    deck_bats = night_battle.card_loader.get_card("Bats")
    assert deck_bats is not None
    assert len(spawned_bats) == 2
    assert all(bat.card_stats.hit_speed == deck_bats.hit_speed == 1200 for bat in spawned_bats)
    assert all(bat.card_stats.first_hit_time == deck_bats.first_hit_time == 600 for bat in spawned_bats)
    assert all(bat.card_stats.attack_dash_time == 150 for bat in spawned_bats)
    actual_offsets = [
        (bat.position.x - night_witch.position.x, bat.position.y - night_witch.position.y)
        for bat in spawned_bats
    ]
    # A nonzero SpawnAngleShift is added to the parent's retained facing.
    # With the initial player-0 facing, Night Witch's descending two-slot
    # ring is horizontal.
    for actual, expected in zip(
        actual_offsets,
        ((1.5, 0.0), (-1.5, 0.0)),
        strict=True,
    ):
        assert actual == pytest.approx(expected)


def test_night_witch_child_rings_follow_retained_combat_facing():
    battle = BattleState()
    night_witch = _spawn_one(
        battle,
        "NightWitch",
        0,
        Position(9.0, 10.0),
    )
    target = _spawn_one(battle, "Knight", 1, Position(10.0, 11.0))
    night_witch.update_combat_component(battle.dt, battle)
    assert night_witch.target_id == target.id
    assert night_witch.native_facing_units() == (1000, 1000)

    spawner = next(
        mechanic
        for mechanic in night_witch.mechanics
        if type(mechanic).__name__ == "PeriodicSpawner"
    )
    spawner.on_object_tick(night_witch, 1000)
    spawner.on_object_tick(night_witch, 50)
    periodic_bats = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Bat"
    ]
    assert len(periodic_bats) == 2
    for bat, expected in zip(
        periodic_bats,
        ((1.06, -1.06), (-1.06, 1.06)),
        strict=True,
    ):
        assert (
            bat.position.x - night_witch.position.x,
            bat.position.y - night_witch.position.y,
        ) == pytest.approx(expected)

    night_witch.take_damage(night_witch.hitpoints)
    death_bat = max(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Troop) and entity.card_stats.name == "Bat"
        ),
        key=lambda entity: entity.id,
    )
    assert (
        death_bat.position.x - night_witch.position.x,
        death_bat.position.y - night_witch.position.y,
    ) == pytest.approx((-0.353, 0.353))


def test_bat_attack_dash_time_is_presentation_only():
    battle = BattleState()
    bat = _spawn_one(battle, "Bats", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 11.0))
    bat.position = Position(9.0, 10.0)
    target.position = Position(9.0, 11.0)
    origin = Position(bat.position.x, bat.position.y)
    bat.target_id = target.id
    bat.attack_cooldown = bat.get_preloaded_attack_time_seconds()

    assert bat.card_stats.attack_dash_time == 150
    target_hp = target.hitpoints
    for _ in range(12):
        bat.update(battle.dt, battle)
        assert bat.position == origin

    # The animation metadata does not alter authoritative attack timing.
    assert target.hitpoints == target_hp - bat.damage


def test_bat_visual_lunge_cannot_change_logic_collision_footprint():
    battle = BattleState()
    bat = _spawn_one(battle, "Bats", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 11.0))
    bystander = _spawn_one(battle, "Knight", 1, Position(9.0, 9.0))
    bat.position = Position(9.0, 10.0)
    target.position = Position(9.0, 11.0)
    bystander.position = Position(9.0, 9.0)
    origin = Position(bat.position.x, bat.position.y)
    bat.target_id = target.id
    bat.attack_cooldown = bat.get_preloaded_attack_time_seconds()

    for _ in range(6):
        bat.update(battle.dt, battle)
        assert bat.position == origin
        assert bat.position.distance_to(bystander.position) == pytest.approx(1.0)


def test_stunned_ordinary_troop_pauses_observation_movement_and_attack():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    old_target = _spawn_one(battle, "Knight", 1, Position(9.0, 20.0))
    closer_target = _spawn_one(battle, "Knight", 1, Position(9.0, 13.0))
    knight.target_id = old_target.id
    knight.attack_cooldown = 0.01
    origin = Position(knight.position.x, knight.position.y)

    knight.apply_stun(0.5)
    knight.update(battle.dt, battle)

    assert knight.target_id is None
    assert knight.position == origin
    assert knight.attack_cooldown == pytest.approx(0.01)
    assert closer_target.hitpoints == closer_target.max_hitpoints


def test_stun_preserves_idle_preload_when_attacker_has_no_target_lock():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    knight.target_id = None
    knight._last_combat_target_id = None
    knight.attack_cooldown = knight.get_preloaded_attack_time_seconds()

    knight.apply_stun(0.5, source_kind="Zap")

    # The opened ordinary Zap control preserves load and hit work.
    assert knight.target_id is None
    assert knight.attack_cooldown == pytest.approx(
        knight.get_preloaded_attack_time_seconds()
    )


def test_zap_reload_global_is_gated_by_serialized_load_first_hit(monkeypatch):
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    monkeypatch.setattr(
        "clasher.entities.LOGIC_LOAD_FIRST_HIT_RESET_TIMER_WHEN_ZAPPED",
        False,
    )

    knight.attack_cooldown = 0.01
    knight.apply_stun(0.5, source_kind="Zap")
    assert not knight.card_stats.load_first_hit
    assert knight.attack_cooldown == pytest.approx(0.01)

    knight.stun_timer = 0.0
    knight.card_stats.load_first_hit = True
    knight.attack_cooldown = 0.01
    knight.apply_stun(0.5, source_kind="Zap")
    assert knight.attack_cooldown == pytest.approx(0.01)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize(
    ("attacker_name", "targets_buildings"),
    [
        ("Knight", False),
        ("Xbow", False),
        ("HogRider", True),
        ("Balloon", True),
    ],
)
def test_stun_clears_connected_lock_before_reacquiring_the_nearest_target(
    fast_path,
    attacker_name,
    targets_buildings,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    if attacker_name != "Xbow":
        attacker = _spawn_one(
            battle,
            attacker_name,
            0,
            Position(9.0, 10.0),
        )
    else:
        attacker = battle._spawn_entity(
            Building,
            Position(9.0, 10.0),
            0,
            battle.card_loader.get_card(attacker_name),
        )
        attacker.deploy_delay_remaining = 0.0
        attacker.placement_pending = False
        attacker.on_spawn()

    if targets_buildings:
        cannon_stats = battle.card_loader.get_card("Cannon")
        assert cannon_stats is not None
        connected = battle._spawn_entity(
            Building,
            Position(9.0, 10.5),
            1,
            cannon_stats,
        )
        nearest = battle._spawn_entity(
            Building,
            Position(9.1, 10.1),
            1,
            cannon_stats,
        )
        for target in (connected, nearest):
            target.deploy_delay_remaining = 0.0
            target.placement_pending = False
            target.on_spawn()
    else:
        connected = _spawn_one(
            battle,
            "Knight",
            1,
            Position(9.0, 11.2),
        )
        nearest = _spawn_one(
            battle,
            "Skeletons",
            1,
            Position(9.2, 10.4),
        )
    attacker.target_id = connected.id
    # An ordinary weapon retains its almost-ready hit across the target pause.
    # These additional card cases exercise the shared adapter; only Knight has
    # an independent native Zap clock fixture here.
    attacker.attack_cooldown = 0.01
    assert attacker.is_within_target_keep_reach(connected)
    if fast_path:
        battle._refresh_fast_path_caches()
    assert attacker.get_nearest_target(battle.entities) is nearest

    attacker.apply_stun(0.5, source_kind="Zap")
    attacker.update_combat_component(battle.dt, battle)

    assert attacker.target_id is None
    assert attacker.attack_cooldown == pytest.approx(0.01)
    assert connected.hitpoints == connected.max_hitpoints
    assert nearest.hitpoints == nearest.max_hitpoints
    for _ in range(10):
        attacker.update_buff_component(battle.dt)
    attacker.update_combat_component(battle.dt, battle)
    assert attacker.target_id == nearest.id


@pytest.mark.parametrize(
    ("position", "player_id", "expected"),
    (
        (Position(9.0, 31.0), 0, Position(7.5, 31.0)),
        (Position(9.0, 0.5), 1, Position(7.5, 0.5)),
        # The first owner-forward candidate overlaps non-bridge water, so the
        # four-candidate native scan rotates left.
        (Position(9.0, 14.0), 0, Position(7.5, 14.0)),
        # The same footprint is legal at a bridge and stays owner-forward.
        (Position(3.5, 14.0), 0, Position(3.5, 15.5)),
    ),
)
def test_zero_radius_spawner_uses_native_footprint_candidate_scan(
    position,
    player_id,
    expected,
):
    battle = BattleState()
    tomb_stats = battle.card_loader.get_card("Tombstone")
    assert tomb_stats is not None
    tomb = battle._spawn_entity(Building, position, player_id, tomb_stats)
    tomb.deploy_delay_remaining = 0.0

    spawner = next(
        mechanic
        for mechanic in tomb.mechanics
        if type(mechanic).__name__ == "PeriodicSpawner"
    )
    spawner.on_object_tick(tomb, 4000)

    skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    ]
    assert len(skeletons) == 2
    assert all(skeleton.position == expected for skeleton in skeletons)


def test_rage_accelerates_enabled_periodic_spawners():
    normal_battle = BattleState()
    normal = _spawn_one(normal_battle, "Witch", 0, Position(9.0, 10.0))
    raged_battle = BattleState()
    raged = _spawn_one(raged_battle, "Witch", 0, Position(9.0, 10.0))
    raged.apply_haste(1.0, 1.3, 1.3, 1.3)

    for _ in range(16):
        normal.update(normal_battle.dt, normal_battle)
        raged.update(raged_battle.dt, raged_battle)

    normal_skeletons = sum(
        isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
        for entity in normal_battle.entities.values()
    )
    raged_skeletons = sum(
        isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
        for entity in raged_battle.entities.values()
    )
    assert normal_skeletons == 0
    assert raged_skeletons == 1

    # The first accelerated wave begins before the normal one, but native
    # production still emits at most one member per logic frame.
    for _ in range(3):
        normal.update(normal_battle.dt, normal_battle)
        raged.update(raged_battle.dt, raged_battle)
    assert not any(
        isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
        for entity in normal_battle.entities.values()
    )
    assert sum(
        isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
        for entity in raged_battle.entities.values()
    ) == 4


def test_equal_rage_and_ice_slow_multiply_on_all_three_speed_axes():
    battle = BattleState(rng=random.Random(75))
    witch = _spawn_one(battle, "Witch", 0, Position(9.0, 10.0))
    base_speed = witch.speed

    witch.apply_slow(2.0, 0.7)
    witch.apply_haste(2.0, 1.3, 1.3, 1.3)

    conceptual_rate = 0.7 * 1.3
    native_tick_rate = 0.9
    assert witch.get_movement_rate_multiplier() == pytest.approx(conceptual_rate)
    assert witch.get_attack_rate_multiplier() == pytest.approx(native_tick_rate)
    assert witch.get_spawn_rate_multiplier() == pytest.approx(native_tick_rate)

    target = _spawn_one(battle, "Knight", 1, Position(9.0, 20.0))
    start = Position(witch.position.x, witch.position.y)
    path_target = ground_path_waypoint(
        battle,
        witch,
        target.position,
        target_entity=target,
    )
    expected_x_units, expected_y_units = movement_component_vector_logic_units(
        tiles_to_logic_units(path_target.x - start.x),
        tiles_to_logic_units(path_target.y - start.y),
        speed_work_for_duration(base_speed * native_tick_rate, battle.dt),
    )
    witch._move_towards_target(target, battle.dt, battle)
    assert witch.position == Position(
        start.x + logic_units_to_tiles(expected_x_units),
        start.y + logic_units_to_tiles(expected_y_units),
    )

    spawner = next(
        mechanic
        for mechanic in witch.mechanics
        if type(mechanic).__name__ == "PeriodicSpawner"
    )
    spawner.on_object_tick(witch, 1111)
    skeletons = lambda: [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    ]
    assert skeletons() == []
    spawner.on_object_tick(witch, 1)
    assert len(skeletons()) == 1
    for expected_count in (2, 3, 4):
        spawner.on_object_tick(witch, 56)
        assert len(skeletons()) == expected_count


def test_combined_rage_and_slow_use_integer_attack_work_each_frame():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    dark_prince = _spawn_one(
        battle,
        "DarkPrince",
        0,
        Position(9.0, 10.0),
    )
    target = _spawn_one(battle, "Giant", 1, Position(9.0, 11.0))
    target.apply_stun(99.0)
    dark_prince.apply_slow(99.0, 0.7)
    dark_prince.apply_haste(99.0, 1.3, 1.3, 1.3)
    # Measure an established cycle, excluding the separate acquisition load.
    dark_prince.target_id = target.id
    dark_prince._note_combat_target(target)
    from clasher.attack_clock import OrdinaryAttackClock
    from clasher.ordinary_combat_clock import publish

    dark_prince._ordinary_clock = OrdinaryAttackClock(
        1400, 1000, hit_timeline_ms=1400, load_remaining_ms=1000,
    )
    publish(dark_prince, dark_prince._ordinary_clock)
    hp_before = target.hitpoints

    # calculateHitSpeed floors 50 * 130 / 100 * 70 / 100 to 45 ms.
    # Multiplying the conceptual 0.91 rate would consume 45.5 ms and make
    # this 1.4-second cycle connect one frame early.
    for _ in range(31):
        dark_prince.update_combat_component(battle.dt, battle)

    assert target.hitpoints == hp_before
    assert dark_prince.attack_cooldown == pytest.approx(0.005)

    dark_prince.update_combat_component(battle.dt, battle)

    assert target.hitpoints == hp_before - dark_prince.damage


def test_hasted_spawner_preserves_fractional_tick_budget_without_drift():
    battle = BattleState(rng=random.Random(76))
    witch = _spawn_one(battle, "Witch", 0, Position(9.0, 10.0))
    witch.apply_haste(2.0, 1.3, 1.3, 1.3)
    spawner = next(
        mechanic
        for mechanic in witch.mechanics
        if type(mechanic).__name__ == "PeriodicSpawner"
    )

    for _ in range(10):
        spawner.on_object_tick(witch, 33)

    assert spawner.time_since_spawn_ms == pytest.approx(429.0)


def test_distinct_haste_sources_expire_without_restoring_or_erasing_each_other():
    battle = BattleState(rng=random.Random(761))
    troop = _spawn_one(battle, "Witch", 0, Position(9.0, 10.0))

    # A stronger, shorter effect and a weaker, longer effect share the same
    # strongest-positive native lane, but retain independent lifetimes.
    troop.apply_haste(0.5, 1.5, 1.4, 1.2)
    troop.apply_haste(1.0, 1.3, 1.3, 1.3)
    assert troop.haste_timer == pytest.approx(1.0)
    assert troop.movement_speed_buff_multiplier == pytest.approx(1.5)
    assert troop.attack_speed_buff_multiplier == pytest.approx(1.4)
    assert troop.spawn_speed_buff_multiplier == pytest.approx(1.3)

    troop.update_status_effects(0.5)
    assert troop.haste_timer == pytest.approx(0.5)
    assert troop.movement_speed_buff_multiplier == pytest.approx(1.3)
    assert troop.attack_speed_buff_multiplier == pytest.approx(1.3)
    assert troop.spawn_speed_buff_multiplier == pytest.approx(1.3)

    # Refreshing the remaining signature extends only that source.
    troop.apply_haste(0.75, 1.3, 1.3, 1.3)
    troop.update_status_effects(0.5)
    assert troop.haste_timer == pytest.approx(0.25)
    assert troop.attack_speed_buff_multiplier == pytest.approx(1.3)
    troop.update_status_effects(0.25)
    assert troop.haste_timer == pytest.approx(0.0)
    assert troop.movement_speed_buff_multiplier == pytest.approx(1.0)
    assert troop.attack_speed_buff_multiplier == pytest.approx(1.0)
    assert troop.spawn_speed_buff_multiplier == pytest.approx(1.0)


def test_explicitly_capped_haste_falloff_never_extends_past_area_lifetime():
    battle = BattleState(rng=random.Random(77))
    troop = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    rage = BuffAreaEffect(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=3.0,
        sight_range=3.0,
        duration=0.2,
        radius=3.0,
        refresh_duration=1.0,
        cap_buff_time_to_effect=True,
        effect_tick_interval=0.19,
        movement_multiplier=1.3,
        attack_speed_multiplier=1.3,
        spawn_speed_multiplier=1.3,
    )

    rage.update(0.19, battle)
    assert troop.haste_timer == pytest.approx(0.01)
    troop.update_status_effects(0.02)
    rage.update(0.02, battle)

    assert not rage.is_alive
    assert troop.haste_timer <= 0
    assert troop.movement_speed_buff_multiplier == 1.0


@pytest.mark.parametrize("fast_path", [False, True])
def test_rage_area_is_an_effect_container_not_a_combat_target(fast_path):
    battle = BattleState(fast_path=fast_path)
    attacker = _spawn_one(battle, "ElectroWizard", 1, Position(9.0, 12.0))
    rage = BuffAreaEffect(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=0,
        range=3.0,
        sight_range=3.0,
    )
    rage.battle_state = battle
    battle.entities[rage.id] = rage
    battle.next_entity_id += 1
    battle._refresh_fast_path_caches()

    assert rage.entity_kind == 3
    assert attacker.get_nearest_target(battle.entities) is not rage


def test_ice_wizard_spawn_nova_is_delayed_scaled_and_hits_both_planes():
    battle = BattleState()
    ground = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    air = _spawn_one(battle, "BabyDragon", 1, Position(10.0, 14.0))
    ice_stats = battle.card_loader.get_card("IceWizard")
    assert ice_stats is not None
    before = set(battle.entities)
    battle._spawn_troop(Position(9.0, 14.0), 0, ice_stats)
    wizard = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    hp_before = (ground.hitpoints, air.hitpoints)

    for _ in range(19):
        battle.step()
    assert (ground.hitpoints, air.hitpoints) == hp_before
    battle.step()

    expected = ice_stats.get_scaled_stat(33)
    assert hp_before[0] - ground.hitpoints == expected
    assert hp_before[1] - air.hitpoints == expected
    assert ground.slow_multiplier == air.slow_multiplier == 0.7
    assert (
        ground.attack_speed_debuff_multiplier
        == air.attack_speed_debuff_multiplier
        == 0.7
    )
    assert (
        ground.spawn_speed_debuff_multiplier
        == air.spawn_speed_debuff_multiplier
        == 0.7
    )
    assert ground.slow_timer == air.slow_timer == pytest.approx(2.5)
    assert ice_stats.projectile_data["buffTime"] == 2500
    assert wizard.is_alive


def test_single_target_projectile_hits_on_impact_and_tracks_its_target():
    battle = BattleState(rng=random.Random(5))
    musketeer = _spawn_one(battle, "Musketeer", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    overlapping = _spawn_one(battle, "Knight", 1, Position(9.1, 14.0))
    primary_hp = primary.hitpoints
    overlapping_hp = overlapping.hitpoints

    musketeer.attack_cooldown = 0.0
    musketeer.update(battle.dt, battle)
    projectile = next(entity for entity in battle.entities.values() if isinstance(entity, Projectile))
    assert primary.hitpoints == primary_hp
    assert overlapping.hitpoints == overlapping_hp

    primary.position = Position(10.0, 14.0)
    for _ in range(120):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break

    assert primary.hitpoints == primary_hp - musketeer.damage
    assert overlapping.hitpoints == overlapping_hp


@pytest.mark.parametrize(
    ("player_id", "source_y", "target_y", "expected_launch_y"),
    (
        (0, 10.0, 14.2, 10.45),
        (1, 20.0, 15.8, 19.55),
    ),
)
def test_projectile_muzzle_radius_rotates_with_attack_direction_and_shortens_flight(
    player_id,
    source_y,
    target_y,
    expected_launch_y,
):
    battle = BattleState()
    musketeer = _spawn_one(battle, "Musketeer", player_id, Position(9.0, source_y))
    target = _spawn_one(battle, "Knight", 1 - player_id, Position(9.0, target_y))
    musketeer.position = Position(9.0, source_y)
    target.position = Position(9.0, target_y)
    hp_before = target.hitpoints

    musketeer.attack_cooldown = 0.0
    musketeer.update(battle.dt, battle)
    projectile = max(
        (entity for entity in battle.entities.values() if isinstance(entity, Projectile)),
        key=lambda entity: entity.id,
    )

    assert musketeer.card_stats.projectile_start_radius == 0.45
    assert projectile.position == Position(9.0, expected_launch_y)
    for _ in range(3):
        projectile.update(battle.dt, battle)
    assert target.hitpoints == hp_before
    projectile.update(battle.dt, battle)
    assert target.hitpoints == hp_before - musketeer.damage


def test_non_homing_bomb_commits_to_the_target_location_at_attack_time():
    battle = BattleState()
    bomber = _spawn_one(battle, "Bomber", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    stationary = _spawn_one(battle, "Knight", 1, Position(10.0, 14.0))
    hp_before = (primary.hitpoints, stationary.hitpoints)

    bomber.target_id = primary.id
    bomber.attack_cooldown = 0.0
    bomber.update(battle.dt, battle)
    bomb = max(
        (entity for entity in battle.entities.values() if isinstance(entity, Projectile)),
        key=lambda entity: entity.id,
    )
    committed_target = Position(bomb.target_position.x, bomb.target_position.y)
    assert not bomb.tracks_target

    primary.position = Position(9.0, 18.0)
    for _ in range(120):
        bomb.update(battle.dt, battle)
        if not bomb.is_alive:
            break

    assert bomb.target_position == committed_target
    assert primary.hitpoints == hp_before[0]
    assert stationary.hitpoints == hp_before[1] - bomber.damage


@pytest.mark.parametrize(
    ("card_name", "tracks_target"),
    (
        ("Musketeer", True),
        ("Princess", False),
        ("Bomber", False),
    ),
)
def test_enabled_troop_projectile_homing_comes_from_projectile_data(
    card_name,
    tracks_target,
):
    battle = BattleState()
    attacker = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    attacker.target_id = target.id
    attacker.attack_cooldown = 0.0
    attacker.update(battle.dt, battle)
    projectile = max(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Projectile) and entity.source_entity is attacker
        ),
        key=lambda entity: entity.id,
    )
    assert projectile.tracks_target is tracks_target


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize(
    ("player_id", "archer_y", "target_y"),
    (
        (0, 10.0, 16.2),
        (1, 22.0, 15.8),
    ),
)
def test_magic_archer_launch_installs_projectile_owned_temporary_homing(
    fast_path,
    player_id,
    archer_y,
    target_y,
):
    battle = BattleState(fast_path=fast_path)
    archer = _spawn_one(
        battle,
        "MagicArcher",
        player_id,
        Position(9.0, archer_y),
    )
    target = _spawn_one(
        battle,
        "Knight",
        1 - player_id,
        Position(9.0, target_y),
    )
    archer.position = Position(9.0, archer_y)
    target.position = Position(9.0, target_y)
    target.apply_stun(10.0)
    archer.target_id = target.id
    archer.attack_cooldown = 0.0
    if fast_path:
        battle._refresh_fast_path_caches()

    archer.update(battle.dt, battle)

    projectile = max(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Projectile) and entity.source_entity is archer
        ),
        key=lambda entity: entity.id,
    )
    data = archer.card_stats.projectile_data
    assert data["homing"] is False
    assert data["homingTime"] == 100
    assert data["homingMinDistance"] == 5000
    assert projectile.tracks_target is False
    assert projectile.pierces
    assert projectile.projectile_range == 11.0
    assert projectile._temporary_homing_remaining_ms == 100


@pytest.mark.parametrize("forward", [1, -1])
@pytest.mark.parametrize(
    ("launch_distance", "expected_remaining_ms"),
    (
        (5.0, 0),
        (5.001, 50),
    ),
)
def test_temporary_homing_launch_distance_threshold_is_strict_native_integer(
    forward,
    launch_distance,
    expected_remaining_ms,
):
    battle = BattleState()
    battle.entities.clear()
    target = _spawn_one(
        battle,
        "Knight",
        1,
        Position(9.0, 10.0 + forward * launch_distance),
    )
    target.position = Position(
        9.0,
        10.0 + forward * launch_distance,
    )
    initial_endpoint = Position(9.0, 10.0 + forward * 11.0)
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=1,
        range=0.0,
        sight_range=0.0,
        target_position=Position(initial_endpoint.x, initial_endpoint.y),
        travel_speed=logic_speed_to_tiles_per_second(1000),
        primary_target=target,
        tracks_target=False,
        pierces=True,
        projectile_range=11.0,
        homing_time_ms=100,
        homing_min_distance=5.0,
    )
    target.position.x += 2.0

    projectile.update(battle.dt, battle)

    assert projectile._temporary_homing_remaining_ms == expected_remaining_ms
    if expected_remaining_ms:
        assert projectile.target_position != initial_endpoint
        assert projectile.position.x != 9.0
    else:
        assert projectile.target_position == initial_endpoint
        assert projectile.position.x == 9.0


@pytest.mark.parametrize("forward", [1, -1])
def test_magic_archer_temporary_homing_reaims_two_frames_then_freezes_ray(
    forward,
):
    battle = BattleState()
    battle.entities.clear()
    target = _spawn_one(
        battle,
        "Knight",
        1,
        Position(9.0, 10.0 + forward * 6.0),
    )
    target.position = Position(11.0, 10.0 + forward * 6.0)
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=1,
        range=0.0,
        sight_range=0.0,
        target_position=Position(9.0, 10.0 + forward * 11.0),
        travel_speed=logic_speed_to_tiles_per_second(1000),
        primary_target=target,
        tracks_target=False,
        pierces=True,
        projectile_range=11.0,
        homing_time_ms=100,
        homing_min_distance=5.0,
    )

    projectile.update(battle.dt, battle)
    first_endpoint = Position(
        projectile.target_position.x,
        projectile.target_position.y,
    )
    assert projectile._temporary_homing_remaining_ms == 50

    target.position = Position(7.0, 10.0 + forward * 6.0)
    position_before_second_tick = Position(
        projectile.position.x,
        projectile.position.y,
    )
    dx_units = (
        tiles_to_logic_units(target.position.x)
        - tiles_to_logic_units(position_before_second_tick.x)
    )
    dy_units = (
        tiles_to_logic_units(target.position.y)
        - tiles_to_logic_units(position_before_second_tick.y)
    )
    expected_dx, expected_dy = normalized_vector_logic_units(
        dx_units,
        dy_units,
        11000,
    )
    expected_second_endpoint = Position(
        logic_units_to_tiles(
            tiles_to_logic_units(position_before_second_tick.x) + expected_dx
        ),
        logic_units_to_tiles(
            tiles_to_logic_units(position_before_second_tick.y) + expected_dy
        ),
    )

    projectile.update(battle.dt, battle)

    assert projectile._temporary_homing_remaining_ms == 0
    assert projectile.target_position == expected_second_endpoint
    assert projectile.target_position != first_endpoint

    target.position = Position(12.0, 10.0 + forward * 6.0)
    frozen_endpoint = Position(
        projectile.target_position.x,
        projectile.target_position.y,
    )
    projectile.update(battle.dt, battle)
    assert projectile.target_position == frozen_endpoint


def test_lava_hound_death_spawned_pup_uses_its_homing_projectile_data():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    hound = _spawn_one(battle, "LavaHound", 0, Position(9.0, 10.0))
    hound.take_damage(hound.hitpoints)
    pup = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == hound.player_id
        and entity.card_stats.name == "LavaPups"
    )
    pup.position = Position(9.0, 10.0)
    pup.deploy_delay_remaining = 0.0
    pup.placement_pending = False
    pup.on_spawn()
    assert pup.card_stats.projectile_data["name"] == "LavaPupProjectile"
    assert pup.card_stats.projectile_data["homing"] is True
    assert pup.damage == 81

    target = _spawn_one(battle, "Knight", 1, Position(9.0, 12.0))
    target.apply_stun(10.0)
    pup.target_id = target.id
    pup.attack_cooldown = 0.0
    pup.update(battle.dt, battle)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and entity.source_entity is pup
    )
    assert projectile.tracks_target

    target.position = Position(10.0, 13.0)
    projectile.update(battle.dt, battle)
    assert projectile.target_position == target.position


def test_rolling_and_piercing_ranges_begin_at_their_forward_launch_points():
    battle = BattleState()
    bowler = _spawn_one(battle, "Bowler", 0, Position(7.0, 10.0))
    bowler_target = _spawn_one(battle, "Knight", 1, Position(7.0, 14.0))
    magic_archer = _spawn_one(battle, "MagicArcher", 0, Position(11.0, 10.0))
    archer_target = _spawn_one(battle, "Knight", 1, Position(11.0, 14.0))

    bowler.target_id = bowler_target.id
    bowler.attack_cooldown = 0.0
    bowler.update(battle.dt, battle)
    rolling = max(
        (
            entity
            for entity in battle.entities.values()
            if type(entity).__name__ == "RollingProjectile"
        ),
        key=lambda entity: entity.id,
    )
    assert rolling.position == Position(7.0, 11.0)

    magic_archer.target_id = archer_target.id
    magic_archer.attack_cooldown = 0.0
    magic_archer.update(battle.dt, battle)
    arrow = max(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Projectile) and entity.source_entity is magic_archer
        ),
        key=lambda entity: entity.id,
    )
    assert arrow.position == Position(11.0, 10.8)
    assert arrow.target_position == Position(11.0, 21.8)


def test_enabled_defenses_and_crown_towers_use_serialized_muzzle_geometry():
    battle = BattleState()
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 10.0),
        0,
        battle.card_loader.get_card("Cannon"),
    )
    before = set(battle.entities)
    cannon._create_projectile(target, battle)
    cannonball = next(battle.entities[entity_id] for entity_id in battle.entities.keys() - before)
    assert cannon.card_stats.projectile_start_radius == 1.0
    assert cannonball.position == Position(9.0, 11.0)
    assert cannonball.tracks_target

    bomb_tower = battle._spawn_entity(
        Building,
        Position(7.0, 10.0),
        0,
        battle.card_loader.get_card("BombTower"),
    )
    before = set(battle.entities)
    bomb_tower._create_projectile(target, battle)
    building_bomb = next(
        battle.entities[entity_id] for entity_id in battle.entities.keys() - before
    )
    assert not building_bomb.tracks_target

    for player_id, direction in ((0, 1.0), (1, -1.0)):
        king = next(
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Building)
            and entity.player_id == player_id
            and entity.card_stats.name == "KingTower"
        )
        enemy = _spawn_one(
            battle,
            "Knight",
            1 - player_id,
            Position(king.position.x, king.position.y + direction * 4.0),
        )
        before = set(battle.entities)
        king._create_projectile(enemy, battle)
        shot = next(battle.entities[entity_id] for entity_id in battle.entities.keys() - before)
        assert shot.position == Position(
            king.position.x,
            king.position.y + direction * 1.15,
        )

def test_princess_uses_its_combat_projectile_damage_and_splash():
    battle = BattleState(rng=random.Random(7))
    princess = _spawn_one(battle, "Princess", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 18.0))
    secondary = _spawn_one(battle, "Knight", 1, Position(10.5, 18.0))
    hp_before = (primary.hitpoints, secondary.hitpoints)

    assert princess.card_stats.damage == 66
    princess.attack_cooldown = 0.0
    princess.update(battle.dt, battle)
    projectile = next(entity for entity in battle.entities.values() if isinstance(entity, Projectile))
    for _ in range(120):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break

    assert hp_before[0] - primary.hitpoints == princess.damage
    assert hp_before[1] - secondary.hitpoints == princess.damage


def test_firecracker_carrier_deals_no_damage_and_shrapnel_hits_individually():
    battle = BattleState(rng=random.Random(9))
    firecracker = _spawn_one(battle, "Firecracker", 0, Position(3.5, 10.0))
    dark_prince = _spawn_one(battle, "DarkPrince", 1, Position(3.5, 15.0))
    hp_before = dark_prince.hitpoints
    shield = next(
        mechanic for mechanic in dark_prince.mechanics if type(mechanic).__name__ == "Shield"
    )

    firecracker.attack_cooldown = 0.0
    firecracker.update(battle.dt, battle)
    projectile = next(entity for entity in battle.entities.values() if isinstance(entity, Projectile))
    assert projectile.damage == 0
    for _ in range(120):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break

    shards = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile) and entity.is_alive
    ]
    assert len(shards) == 5
    # Each shard runs its native start collision as it is added. Four hits
    # consume the level-scaled shield and the fifth reaches health; the
    # carrier itself contributes no extra hit.
    assert shield.current_shield == 0
    assert hp_before - dark_prince.hitpoints == firecracker.damage
    hp_after_start_collisions = dark_prince.hitpoints
    for shard in shards:
        shard.update(battle.dt, battle)
    assert dark_prince.hitpoints == hp_after_start_collisions


def test_lethal_shrapnel_start_collision_keeps_every_spawned_projectile():
    battle = BattleState(rng=random.Random(109))
    firecracker = _spawn_one(
        battle,
        "Firecracker",
        0,
        Position(3.5, 10.0),
    )
    golem = _spawn_one(battle, "Golem", 1, Position(3.5, 15.0))
    golem.hitpoints = firecracker.damage

    firecracker._create_projectile(golem, battle)
    carrier = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
    )
    for _ in range(120):
        carrier.update(battle.dt, battle)
        if not carrier.is_alive:
            break

    shards = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and entity is not carrier
        and entity.is_alive
    ]
    golemites = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.card_stats.name == "Golemite"
    ]
    assert len(shards) == 5
    assert len(golemites) == 2
    assert len({entity.id for entity in shards + golemites}) == 7
    assert battle.next_entity_id > max(battle.entities)


def test_magic_archer_uses_the_enlarged_hitbox_only_at_projectile_start():
    battle = BattleState(rng=random.Random(93))
    archer = _spawn_one(battle, "MagicArcher", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    inside_start_extra = _spawn_one(
        battle,
        "Knight",
        1,
        Position(10.0, 10.8),
    )
    outside_start_extra = _spawn_one(
        battle,
        "Knight",
        1,
        Position(10.2, 10.8),
    )
    inside_hp = inside_start_extra.hitpoints
    outside_hp = outside_start_extra.hitpoints

    archer._create_projectile(primary, battle)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
    )

    assert projectile.position == Position(9.0, 10.8)
    assert projectile.splash_radius == 0.25
    assert projectile.start_extra_radius == 0.4
    assert inside_hp - inside_start_extra.hitpoints == archer.damage
    assert outside_start_extra.hitpoints == outside_hp

    projectile.update(battle.dt, battle)
    assert inside_hp - inside_start_extra.hitpoints == archer.damage


def test_lethal_projectile_start_collision_cannot_be_overwritten_by_death_spawns():
    battle = BattleState(rng=random.Random(193))
    archer = _spawn_one(battle, "MagicArcher", 0, Position(9.0, 10.0))
    golem = _spawn_one(battle, "Golem", 1, Position(9.0, 10.8))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    golem.hitpoints = archer.damage
    primary_hp = primary.hitpoints

    archer._create_projectile(primary, battle)

    projectiles = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
    ]
    golemites = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.card_stats.name == "Golemite"
    ]
    assert len(projectiles) == 1
    assert len(golemites) == 2
    projectile = projectiles[0]
    assert projectile.is_alive
    assert all(projectile.id < golemite.id for golemite in golemites)
    assert battle.next_entity_id > max(battle.entities)

    for _ in range(80):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break

    assert primary_hp - primary.hitpoints == archer.damage


def test_piercing_projectiles_check_native_tick_points_not_swept_segments():
    battle = BattleState(rng=random.Random(94))
    archer = _spawn_one(battle, "MagicArcher", 0, Position(3.0, 10.0))
    between_samples = _spawn_one(
        battle,
        "Knight",
        1,
        Position(4.5, 10.74),
    )
    on_sample = _spawn_one(
        battle,
        "Knight",
        1,
        Position(5.0, 10.74),
    )
    between_hp = between_samples.hitpoints
    on_sample_hp = on_sample.hitpoints
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

    projectile.update(battle.dt, battle)
    assert projectile.position == Position(4.0, 10.0)
    assert between_samples.hitpoints == between_hp
    assert on_sample.hitpoints == on_sample_hp

    projectile.update(battle.dt, battle)
    assert projectile.position == Position(5.0, 10.0)
    assert between_samples.hitpoints == between_hp
    assert on_sample_hp - on_sample.hitpoints == archer.damage


def test_firecracker_uses_the_current_base_cards_one_tile_recoil():
    battle = BattleState(rng=random.Random(90))
    firecracker = _spawn_one(battle, "Firecracker", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    firecracker.position = Position(9.0, 10.0)
    target.position = Position(9.0, 15.0)
    firecracker.attack_cooldown = 0.0

    firecracker.update(battle.dt, battle)

    assert firecracker.target_id == target.id
    assert firecracker.card_stats.attack_pushback == 1.0
    assert firecracker.position == Position(9.0, 9.8)
    for _ in range(8):
        firecracker.update_movement_component(battle.dt, battle)
    assert firecracker.position == Position(9.0, 9.1)


def test_firecracker_uses_the_current_faster_serialized_projectile_speed():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    firecracker = _spawn_one(
        battle,
        "Firecracker",
        0,
        Position(9.0, 10.0),
    )
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))

    firecracker._create_projectile(target, battle)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and entity.source_entity is firecracker
    )
    assert firecracker.card_stats.projectile_data["speed"] == 500
    assert projectile.travel_speed == pytest.approx(10.0)
    start = Position(projectile.position.x, projectile.position.y)

    projectile.update(battle.dt, battle)

    assert projectile.position.y - start.y == pytest.approx(0.5)


def test_firecracker_noninterrupting_recoil_keeps_attack_clock_running():
    battle = BattleState(rng=random.Random(90))
    firecracker = _spawn_one(battle, "Firecracker", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    firecracker.position = Position(9.0, 10.0)
    target.position = Position(9.0, 15.0)
    firecracker.attack_cooldown = 0.0

    firecracker.update_components(battle.dt, battle)
    committed_cooldown = firecracker.attack_cooldown
    assert committed_cooldown == firecracker.get_base_attack_interval_seconds()

    for _ in range(9):
        firecracker.update_components(battle.dt, battle)

    assert not firecracker.forced_movement_active
    assert firecracker.attack_cooldown == pytest.approx(
        committed_cooldown - 9 * battle.dt
    )


def test_firecracker_shrapnel_uses_native_five_tile_line_scatter():
    battle = BattleState(rng=random.Random(91))
    firecracker = _spawn_one(battle, "Firecracker", 0, Position(3.5, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(3.5, 15.0))
    center = _spawn_one(battle, "Knight", 1, Position(3.5, 19.0))
    angle = math.radians(32.0)
    outer = _spawn_one(
        battle,
        "Knight",
        1,
        Position(3.5 + math.sin(angle) * 4.0, 15.0 + math.cos(angle) * 4.0),
    )
    center_hp = center.hitpoints
    outer_hp = outer.hitpoints

    firecracker.attack_cooldown = 0.0
    firecracker.update(battle.dt, battle)
    projectile = next(entity for entity in battle.entities.values() if isinstance(entity, Projectile))
    for _ in range(120):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break

    shards = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile) and entity.is_alive
    ]
    assert len(shards) == 5
    assert [
        (
            tiles_to_logic_units(
                shard.target_position.x - shard.launch_position.x
            ),
            tiles_to_logic_units(
                shard.target_position.y - shard.launch_position.y
            ),
        )
        for shard in shards
    ] == [
        (2651, 4238),
        (1376, 4804),
        (0, 5000),
        (-1377, 4804),
        (-2652, 4238),
    ]
    scatter_angles = sorted(
        round(
            math.degrees(
                math.atan2(
                    shard.target_position.x - shard.launch_position.x,
                    shard.target_position.y - shard.launch_position.y,
                )
            )
        )
        for shard in shards
    )
    assert scatter_angles == [-32, -16, 0, 16, 32]
    for _ in range(20):
        for shard in shards:
            shard.update(battle.dt, battle)

    # These targets are beyond Firecracker's own six-tile range after recoil,
    # but lie on the center and +32 degree shrapnel rays. SpawnRadius=80 is
    # the native line-scatter numerator: (-2..2) * 80 / 5 degrees.
    assert center_hp - center.hitpoints == firecracker.damage
    assert outer_hp - outer.hitpoints == firecracker.damage


def test_firecracker_shrapnel_uses_projectile_travel_time_and_can_miss_movers():
    battle = BattleState(rng=random.Random(92))
    firecracker = _spawn_one(battle, "Firecracker", 0, Position(3.5, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(3.5, 15.0))
    mover = _spawn_one(battle, "Knight", 1, Position(3.5, 17.0))
    hp_before = mover.hitpoints

    firecracker.attack_cooldown = 0.0
    firecracker.update(battle.dt, battle)
    carrier = next(
        entity for entity in battle.entities.values() if isinstance(entity, Projectile)
    )
    for _ in range(120):
        carrier.update(battle.dt, battle)
        if not carrier.is_alive:
            break

    shards = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile) and entity.is_alive
    ]
    assert len(shards) == 5
    assert mover.hitpoints == hp_before

    # The center shard needs several server frames to reach this point. A
    # troop that leaves its swept path before then is not hit retroactively.
    mover.position = Position(6.5, 17.0)
    for _ in range(30):
        for shard in shards:
            shard.update(battle.dt, battle)
    assert mover.hitpoints == hp_before


def test_magic_archer_arrow_pierces_the_full_data_range_once_per_target():
    battle = BattleState(rng=random.Random(10))
    archer = _spawn_one(battle, "MagicArcher", 0, Position(9.0, 8.0))
    first = _spawn_one(battle, "Knight", 1, Position(9.0, 12.0))
    second = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    third = _spawn_one(battle, "Knight", 1, Position(9.0, 18.5))
    off_line = _spawn_one(battle, "Knight", 1, Position(10.5, 15.0))
    targets = (first, second, third, off_line)
    hp_before = [target.hitpoints for target in targets]

    archer.attack_cooldown = 0.0
    archer.update(battle.dt, battle)
    projectile = next(entity for entity in battle.entities.values() if isinstance(entity, Projectile))
    assert projectile.pierces
    for _ in range(120):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break

    damage_taken = [before - target.hitpoints for before, target in zip(hp_before, targets)]
    assert damage_taken == [archer.damage, archer.damage, archer.damage, 0]

def test_electro_dragon_chain_occurs_when_projectile_lands():
    battle = BattleState(rng=random.Random(11))
    dragon = _spawn_one(battle, "ElectroDragon", 0, Position(9.0, 12.0))
    first = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    second = _spawn_one(battle, "Knight", 1, Position(11.0, 14.0))
    third = _spawn_one(battle, "Knight", 1, Position(13.0, 14.0))
    hp_before = [target.hitpoints for target in (first, second, third)]

    dragon.attack_cooldown = 0.0
    dragon.update(battle.dt, battle)
    projectile = next(entity for entity in battle.entities.values() if isinstance(entity, Projectile))
    assert [target.hitpoints for target in (first, second, third)] == hp_before

    for _ in range(120):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break

    assert [before - target.hitpoints for before, target in zip(hp_before, (first, second, third))] == [
        dragon.damage,
        0,
        0,
    ]
    chain = next(entity for entity in battle.entities.values() if isinstance(entity, ChainLightning))
    assert chain.fixed_hop_duration is None
    chain.update(0.05, battle)
    assert second.hitpoints == hp_before[1] - dragon.damage
    assert second.stun_timer == 0.5
    assert third.hitpoints == hp_before[2]
    chain.update(0.05, battle)
    assert third.hitpoints == hp_before[2] - dragon.damage
    assert third.stun_timer == 0.5


def test_electro_dragon_chain_arrival_uses_native_integer_distance():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    dragon = _spawn_one(battle, "ElectroDragon", 0, Position(9.0, 10.0))
    target = _spawn_one(
        battle,
        "Knight",
        1,
        Position(10.201, 15.6),
    )
    target.position = Position(10.201, 15.6)
    chain = ChainLightning(
        id=battle.next_entity_id,
        position=Position(9.0, 14.0),
        player_id=dragon.player_id,
        card_stats=dragon.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=dragon.damage,
        range=0.0,
        sight_range=0.0,
        origin=Position(9.0, 14.0),
        remaining_bounces=1,
        chain_range=4.0,
        travel_speed=40.0,
        stun_duration=0.5,
    )
    battle.entities[chain.id] = chain
    hp_before = target.hitpoints

    # The quantized vector is exactly 2,000 logic units long even though its
    # reconstructed floating-point length is slightly over two tiles.
    assert math.hypot(
        target.position.x - chain.position.x,
        target.position.y - chain.position.y,
    ) > 2.0
    chain.update(battle.dt, battle)

    assert not chain.is_alive
    assert target.hitpoints == hp_before - dragon.damage
    assert target.stun_timer == 0.5


def test_chain_lightning_uses_native_death_spawn_distance_for_range_and_order():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    origin = Position(9.0, 14.0)
    center_nearer = _spawn_one(
        battle,
        "Knight",
        1,
        Position(10.0, 14.0),
    )
    native_nearer = _spawn_one(
        battle,
        "Knight",
        1,
        Position(10.003, 14.0),
    )
    native_nearer._native_target_distance_discount_sq_units = 80**2
    chain = ChainLightning(
        id=battle.next_entity_id,
        position=Position(origin.x, origin.y),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=1,
        range=0.0,
        sight_range=0.0,
        origin=Position(origin.x, origin.y),
        remaining_bounces=1,
        chain_range=4.0,
    )

    assert origin.distance_to(center_nearer.position) < origin.distance_to(
        native_nearer.position
    )
    assert chain.native_target_distance_from(origin, native_nearer) < (
        chain.native_target_distance_from(origin, center_nearer)
    )
    assert chain._find_next_target(battle) is native_nearer

    center_nearer.is_alive = False
    native_nearer.is_alive = False
    edge = _spawn_one(
        battle,
        "Knight",
        1,
        Position(13.001, 14.0),
    )
    edge.position = Position(13.001, 14.0)
    edge._native_target_distance_discount_sq_units = 160**2

    assert origin.distance_to(edge.position) > chain.chain_range
    assert chain.native_target_distance_from(origin, edge) < chain.chain_range
    assert chain._find_next_target(battle) is edge


def test_electro_dragon_committed_projectile_chains_after_source_death():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    dragon = _spawn_one(battle, "ElectroDragon", 0, Position(9.0, 10.0))
    first = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    second = _spawn_one(battle, "Knight", 1, Position(11.0, 14.0))
    hp_before = (first.hitpoints, second.hitpoints)

    dragon.attack_cooldown = 0.0
    dragon.update(battle.dt, battle)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
    )
    dragon.take_damage(dragon.hitpoints)
    battle._cleanup_dead_entities()
    assert dragon.id not in battle.entities

    for _ in range(120):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break
    chain = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, ChainLightning)
    )
    chain.update(0.1, battle)

    assert hp_before[0] - first.hitpoints == projectile.damage
    assert hp_before[1] - second.hitpoints == projectile.damage
    assert second.stun_timer == 0.5


def test_electro_wizard_deploy_zap_is_level_scaled_and_does_not_damage_crown_towers():
    battle = BattleState(rng=random.Random(13))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    hp_before = target.hitpoints
    wizard = _spawn_one(battle, "ElectroWizard", 0, Position(9.0, 12.0))
    expected_spawn_damage = wizard.card_stats.get_scaled_stat(75)

    assert hp_before - target.hitpoints == expected_spawn_damage
    assert target.stun_timer == 0.5

    tower_battle = BattleState(rng=random.Random(14))
    enemy_tower = next(
        entity
        for entity in tower_battle.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 1
        and entity.card_stats.name == "Tower"
    )
    tower_hp = enemy_tower.hitpoints
    tower_wizard = _spawn_one(
        tower_battle,
        "ElectroWizard",
        0,
        Position(enemy_tower.position.x, enemy_tower.position.y - 2.0),
    )
    assert enemy_tower.hitpoints == tower_hp
    assert enemy_tower.stun_timer == 0.5


def test_electro_wizard_fires_two_simultaneous_bolts():
    split_battle = BattleState(rng=random.Random(14))
    first = _spawn_one(split_battle, "Knight", 1, Position(9.0, 14.0))
    second = _spawn_one(split_battle, "Knight", 1, Position(10.0, 14.0))
    wizard = _spawn_one(split_battle, "ElectroWizard", 0, Position(9.0, 10.0))
    assert wizard.damage == 117
    hp_before = (first.hitpoints, second.hitpoints)
    wizard.attack_cooldown = 0.0
    wizard.update(split_battle.dt, split_battle)
    assert hp_before[0] - first.hitpoints == wizard.damage
    assert hp_before[1] - second.hitpoints == wizard.damage
    assert first.stun_timer == second.stun_timer == 0.5

    edge_battle = BattleState(rng=random.Random(141))
    edge_primary = _spawn_one(edge_battle, "Knight", 1, Position(9.0, 14.0))
    edge_wizard = _spawn_one(edge_battle, "ElectroWizard", 0, Position(9.0, 10.0))
    edge_secondary = _spawn_one(edge_battle, "Knight", 1, Position(14.4, 10.0))
    edge_hp = edge_secondary.hitpoints
    assert edge_wizard.can_attack_target(edge_secondary)
    edge_wizard.attack_cooldown = 0.0
    edge_wizard.update(edge_battle.dt, edge_battle)
    assert edge_hp - edge_secondary.hitpoints == edge_wizard.damage

    far_battle = BattleState(rng=random.Random(142))
    far_primary = _spawn_one(far_battle, "Knight", 1, Position(9.0, 14.0))
    far_wizard = _spawn_one(far_battle, "ElectroWizard", 0, Position(9.0, 10.0))
    far_secondary = _spawn_one(far_battle, "Knight", 1, Position(17.0, 10.0))
    far_hp = far_secondary.hitpoints
    far_wizard.attack_cooldown = 0.0
    far_wizard.update(far_battle.dt, far_battle)
    assert far_secondary.hitpoints == far_hp
    assert far_primary.hitpoints < far_primary.max_hitpoints

    single_battle = BattleState(rng=random.Random(15))
    lone_target = _spawn_one(single_battle, "Knight", 1, Position(9.0, 14.0))
    lone_wizard = _spawn_one(single_battle, "ElectroWizard", 0, Position(9.0, 10.0))
    lone_mechanic = next(
        item
        for item in lone_wizard.mechanics
        if isinstance(item, MultipleTargetAttack)
    )
    assert lone_wizard.card_stats._raw_entry["summonCharacterData"][
        "allTargetsHit"
    ] is True
    assert lone_mechanic.all_targets_hit
    assert lone_mechanic.target_count == 2
    on_hit_buff = next(
        item
        for item in lone_wizard.mechanics
        if isinstance(item, SerializedOnHitBuff)
    )
    assert on_hit_buff.duration_ms == 500
    assert on_hit_buff.movement_multiplier == 0.0
    assert on_hit_buff.attack_multiplier == 0.0
    assert on_hit_buff.spawn_multiplier == 0.0
    lone_hp = lone_target.hitpoints
    lone_wizard.attack_cooldown = 0.0
    lone_wizard.update(single_battle.dt, single_battle)
    assert lone_hp - lone_target.hitpoints == 2 * lone_wizard.damage


def test_electro_wizard_simultaneous_bolts_do_not_retarget_lethal_death_spawns():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    wizard = _spawn_one(battle, "ElectroWizard", 0, Position(9.0, 10.0))
    golem = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))
    golem.hitpoints = wizard.damage
    wizard.target_id = golem.id
    wizard.attack_cooldown = 0.0

    wizard.update(battle.dt, battle)

    golemites = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == golem.player_id
        and entity.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(entity.hitpoints == entity.max_hitpoints for entity in golemites)
    assert all(entity.stun_timer == 0.0 for entity in golemites)


@pytest.mark.parametrize("attacker_name", ["ElectroDragon", "ElectroSpirit"])
def test_chain_links_cannot_target_active_lethal_primary_death_spawns(attacker_name):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, attacker_name, 0, Position(9.0, 12.0))
    golem = _spawn_one(battle, "Golem", 1, Position(9.0, 14.0))
    golem.hitpoints = attacker.damage

    if attacker_name == "ElectroDragon":
        attacker._create_projectile(golem, battle)
        projectile = next(
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Projectile)
            and entity.source_entity is attacker
        )
        projectile.position = Position(
            projectile.target_position.x,
            projectile.target_position.y,
        )
        projectile.update(battle.dt, battle)
    else:
        mechanic = next(
            mechanic
            for mechanic in attacker.mechanics
            if type(mechanic).__name__ == "ElectroSpiritChain"
        )
        mechanic.on_attack_start(attacker, golem)
        mechanic.on_movement_tick(attacker, 100)

    chain = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, ChainLightning)
    )
    # Both chain variants seek their next character before the death-spawn
    # marker crosses the 250 ms attack-finish boundary.
    while chain.is_alive:
        chain.update(0.25, battle)

    golemites = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == golem.player_id
        and entity.card_stats.name == "Golemite"
    ]
    assert len(golemites) == 2
    assert all(entity.hitpoints == entity.max_hitpoints for entity in golemites)
    assert all(entity.stun_timer == 0.0 for entity in golemites)


def test_electro_wizard_duplicate_bolt_follows_all_targets_hit_payload():
    battle = BattleState()
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    wizard = _spawn_one(battle, "ElectroWizard", 0, Position(9.0, 10.0))
    mechanic = next(
        item
        for item in wizard.mechanics
        if isinstance(item, MultipleTargetAttack)
    )
    mechanic.all_targets_hit = False
    hp_before = target.hitpoints

    wizard.attack_cooldown = 0.0
    wizard.update(battle.dt, battle)

    assert hp_before - target.hitpoints == wizard.damage


def test_electro_wizard_second_bolt_survives_invulnerable_primary():
    battle = BattleState()
    primary = _spawn_one(battle, "Bandit", 1, Position(9.0, 14.0))
    secondary = _spawn_one(battle, "Knight", 1, Position(10.0, 14.0))
    wizard = _spawn_one(battle, "ElectroWizard", 0, Position(9.0, 10.0))
    primary._bandit_dashing = True
    hp_before = (primary.hitpoints, secondary.hitpoints)

    wizard.attack_cooldown = 0.0
    wizard.update(battle.dt, battle)

    assert primary.hitpoints == hp_before[0]
    assert secondary.hitpoints == hp_before[1] - wizard.damage
    assert primary.stun_timer == 0.0
    assert secondary.stun_timer == 0.5


def test_electro_wizard_equal_distance_split_target_rotates_with_owner():
    normal = BattleState()
    mirrored = BattleState()
    normal.entities.clear()
    mirrored.entities.clear()
    wizard = _spawn_one(normal, "ElectroWizard", 0, Position(9.5, 10.0))
    mirrored_wizard = _spawn_one(
        mirrored,
        "ElectroWizard",
        1,
        Position(8.5, 22.0),
    )
    primary = _spawn_one(normal, "Knight", 1, Position(9.5, 13.0))
    mirrored_primary = _spawn_one(mirrored, "Knight", 0, Position(8.5, 19.0))
    left = _spawn_one(normal, "Knight", 1, Position(8.4, 14.0))
    mirrored_left = _spawn_one(mirrored, "Knight", 0, Position(9.6, 18.0))
    _spawn_one(normal, "Knight", 1, Position(10.6, 14.0))
    _spawn_one(mirrored, "Knight", 0, Position(7.4, 18.0))
    mechanic = next(
        item for item in wizard.mechanics if isinstance(item, MultipleTargetAttack)
    )
    mirrored_mechanic = next(
        item
        for item in mirrored_wizard.mechanics
        if isinstance(item, MultipleTargetAttack)
    )

    assert mechanic._ordered_secondary_targets(wizard, primary)[0] is left
    assert (
        mirrored_mechanic._ordered_secondary_targets(
            mirrored_wizard,
            mirrored_primary,
        )[0]
        is mirrored_left
    )


@pytest.mark.parametrize("fast_path", [False, True])
def test_electro_wizard_split_target_uses_native_death_spawn_distance_allowance(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    wizard = _spawn_one(battle, "ElectroWizard", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    center_nearer = _spawn_one(
        battle,
        "Knight",
        1,
        Position(8.0, 14.0),
    )
    native_nearer = _spawn_one(
        battle,
        "Knight",
        1,
        Position(10.003, 14.0),
    )
    # The first nonzero SpawnConstPriority index receives (1 * 80)^2 native
    # squared-distance allowance. Its center is slightly farther away, but
    # the same adjusted distance used by combat acquisition makes it the
    # nearest secondary recipient.
    native_nearer._native_target_distance_discount_sq_units = 80**2
    assert wizard.position.distance_to(center_nearer.position) < (
        wizard.position.distance_to(native_nearer.position)
    )
    assert wizard.native_target_distance_to(native_nearer) < (
        wizard.native_target_distance_to(center_nearer)
    )
    mechanic = next(
        item
        for item in wizard.mechanics
        if isinstance(item, MultipleTargetAttack)
    )

    assert mechanic._ordered_secondary_targets(wizard, primary)[0] is native_nearer
    hp_before = (
        primary.hitpoints,
        center_nearer.hitpoints,
        native_nearer.hitpoints,
    )
    primary.stun_timer = 99.0
    center_nearer.stun_timer = 99.0
    native_nearer.stun_timer = 99.0
    wizard.target_id = primary.id
    wizard.attack_cooldown = 0.0

    wizard.update(battle.dt, battle)

    assert primary.hitpoints == hp_before[0] - wizard.damage
    assert center_nearer.hitpoints == hp_before[1]
    assert native_nearer.hitpoints == hp_before[2] - wizard.damage


def test_archer_queen_ability_is_explicit_and_uses_gamedata_modifiers():
    battle = BattleState(rng=random.Random(17))
    queen = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 12.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    mechanic = queen.mechanics[0]
    battle.players[0].elixir = 10.0
    base_damage = queen.damage
    base_speed = queen.speed
    base_interval = queen.get_attack_interval_seconds()

    queen.target_id = target.id
    mechanic.on_tick(queen, 33)
    assert battle.players[0].elixir == 10.0
    assert not mechanic.ability.is_active

    assert mechanic.activate_ability(queen)
    assert battle.players[0].elixir == 9.0
    assert queen.damage == base_damage
    assert queen.speed == base_speed
    assert queen._stealth_until == 0

    battle.time += 0.199
    mechanic.on_tick(queen, 199)
    assert queen._stealth_until == 0
    assert mechanic.blocks_combat_actions(queen)

    battle.time += 0.001
    mechanic.on_tick(queen, 1)
    assert queen.speed == base_speed * 0.75
    assert queen.get_attack_interval_seconds() < base_interval
    assert queen._stealth_until > int(battle.time * 1000)
    assert mechanic.blocks_combat_actions(queen)

    battle.time += 0.734
    mechanic.on_tick(queen, 734)
    assert not mechanic.blocks_combat_actions(queen)

    battle.time += 3.6
    mechanic.on_tick(queen, 3600)
    assert queen.speed == base_speed
    assert queen.get_attack_interval_seconds() == base_interval
    assert queen._stealth_until == 0


def test_archer_queen_cloak_uses_exact_integer_server_deadlines():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    queen = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 10.0))
    _spawn_one(battle, "Knight", 1, Position(9.0, 15.0))
    mechanic = queen.mechanics[0]
    battle.players[0].elixir = 10.0
    assert mechanic.activate_ability(queen)

    for _ in range(3):
        battle.step()
    assert battle.time == pytest.approx(0.15)
    assert queen._stealth_until == 0
    assert mechanic.blocks_combat_actions(queen)

    battle.step()
    assert battle.time == pytest.approx(0.2)
    assert queen._stealth_until == 3700
    assert mechanic.ability.is_active

    for _ in range(14):
        battle.step()
    assert battle.time == pytest.approx(0.9)
    assert mechanic.blocks_combat_actions(queen)

    battle.step()
    assert battle.time == pytest.approx(0.95)
    assert not mechanic.blocks_combat_actions(queen)

    for _ in range(54):
        battle.step()
    assert battle.time == pytest.approx(3.65)
    assert mechanic.ability.is_active
    assert queen._stealth_until == 3700

    battle.step()
    assert battle.time == pytest.approx(3.7)
    assert not mechanic.ability.is_active
    assert queen._stealth_until == 0


def test_archer_queen_cloak_survives_slow_start_and_expiry_without_speed_corruption():
    battle = BattleState(rng=random.Random(18))
    queen = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 12.0))
    mechanic = queen.mechanics[0]
    battle.players[0].elixir = 10.0
    base_speed = queen.speed

    assert mechanic.activate_ability(queen)
    battle.time += 0.934
    mechanic.on_tick(queen, 934)
    assert queen.speed == pytest.approx(base_speed * 0.75)

    queen.apply_slow(0.5, 0.7)
    # Both are negative CharacterBuffData modifiers. Native keeps only the
    # stronger reduction instead of multiplying two slowdown lanes.
    assert queen.speed == pytest.approx(base_speed * 0.7)
    assert queen.get_movement_rate_multiplier() == pytest.approx(0.7)
    queen.update_status_effects(0.6)
    assert queen.speed == pytest.approx(base_speed * 0.75)

    battle.time += 3.6
    mechanic.on_tick(queen, 3600)
    assert queen.speed == pytest.approx(base_speed)
    assert queen.original_speed is None


def test_archer_queen_cloak_and_rage_expire_without_restoring_or_erasing_each_other():
    battle = BattleState(rng=random.Random(183))
    queen = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 12.0))
    mechanic = queen.mechanics[0]
    battle.players[0].elixir = 10.0

    # Rage is already active when Cloak starts, then expires first.
    queen.apply_haste(0.5, 1.3, 1.3, 1.3)
    assert mechanic.activate_ability(queen)
    battle.time = mechanic.trigger_delay_ms / 1000.0
    mechanic.on_tick(queen, mechanic.trigger_delay_ms)
    assert queen.attack_speed_buff_multiplier == 1.3
    assert queen.attack_mode_multiplier == 2.8
    assert queen.get_attack_rate_multiplier() == 2.8
    assert queen.get_movement_rate_multiplier() == pytest.approx(0.75 * 1.3)

    queen.update_status_effects(0.5)
    assert queen.attack_speed_buff_multiplier == 1.0
    assert queen.get_attack_rate_multiplier() == 2.8
    assert queen.get_movement_rate_multiplier() == pytest.approx(0.75)

    battle.time += mechanic.duration_ms / 1000.0
    mechanic.on_tick(queen, mechanic.duration_ms)
    assert queen.attack_mode_multiplier == 1.0
    assert queen.get_attack_rate_multiplier() == 1.0

    # A Rage whose falloff outlasts Cloak remains active when Cloak ends.
    assert mechanic.ability.can_activate(queen, battle) is False
    mechanic.ability.last_use_time = -10**12
    queen.apply_haste(10.0, 1.3, 1.3, 1.3)
    assert mechanic.activate_ability(queen)
    battle.time += mechanic.trigger_delay_ms / 1000.0
    mechanic.on_tick(queen, mechanic.trigger_delay_ms)
    battle.time += mechanic.duration_ms / 1000.0
    mechanic.on_tick(queen, mechanic.duration_ms)

    assert queen.attack_mode_multiplier == 1.0
    assert queen.attack_speed_buff_multiplier == 1.3
    assert queen.get_attack_rate_multiplier() == 1.3
    assert queen.get_movement_rate_multiplier() == pytest.approx(1.3)


def test_archer_queen_cooldown_begins_when_cloak_ends():
    battle = BattleState(rng=random.Random(180))
    queen = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 12.0))
    mechanic = queen.mechanics[0]
    battle.players[0].elixir = 10.0

    assert mechanic.activate_ability(queen)
    trigger_seconds = mechanic.trigger_delay_ms / 1000.0
    duration_seconds = mechanic.duration_ms / 1000.0
    cooldown_seconds = mechanic.ability.cooldown_ms / 1000.0

    battle.time = trigger_seconds + duration_seconds
    mechanic.on_tick(queen, mechanic.duration_ms)
    assert not mechanic.ability.is_active
    assert mechanic.ability.get_cooldown_remaining(battle) == mechanic.ability.cooldown_ms

    battle.time = trigger_seconds + duration_seconds + cooldown_seconds - 0.001
    assert not mechanic.can_activate_ability(queen)

    battle.time += 0.001
    assert mechanic.can_activate_ability(queen)


def test_newest_archer_queen_owns_ability_and_death_transfers_it_back():
    battle = BattleState(rng=random.Random(182))
    battle.players[0].elixir = 10.0
    first = _spawn_one(battle, "ArcherQueen", 0, Position(8.0, 12.0))
    first_mechanic = first.mechanics[0]

    assert battle.activate_champion_ability(0)
    battle.time = (
        first_mechanic.trigger_delay_ms + first_mechanic.duration_ms
    ) / 1000.0
    first_mechanic.on_tick(
        first,
        first_mechanic.trigger_delay_ms + first_mechanic.duration_ms,
    )
    assert not first_mechanic.ability.is_active
    assert not first_mechanic.can_activate_ability(first)

    queen_stats = battle.card_loader.get_card("ArcherQueen")
    assert queen_stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(
        Position(10.0, 12.0),
        0,
        queen_stats,
    )
    second = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    second_mechanic = second.mechanics[0]

    # Ownership moves on placement, not after the deploy timer. During that
    # timer the old Queen has lost the crown while the new Queen cannot press
    # the button yet.
    assert second.placement_pending
    assert battle._champion_ability_mechanic(0) == (second, second_mechanic)
    assert not first_mechanic.can_activate_ability(first)
    assert not first_mechanic.activate_ability(first)
    assert not battle.can_activate_champion_ability(0)

    second.deploy_delay_remaining = 0.0
    second.placement_pending = False
    second.on_spawn()
    assert second_mechanic.can_activate_ability(second)
    assert battle.activate_champion_ability(0)

    second.take_damage(second.hitpoints)
    battle._cleanup_dead_entities()

    assert battle._champion_ability_mechanic(0) == (first, first_mechanic)
    assert first_mechanic.ability.get_cooldown_remaining(battle) == 0
    assert first_mechanic.can_activate_ability(first)


def test_archer_queen_can_activate_ability_while_stunned():
    battle = BattleState(rng=random.Random(181))
    queen = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 12.0))
    mechanic = queen.mechanics[0]
    battle.players[0].elixir = 10.0

    queen.apply_stun(0.5)
    assert mechanic.can_activate_ability(queen)
    assert mechanic.activate_ability(queen)
    assert battle.players[0].elixir == 9.0


def test_archer_queen_cast_locks_combat_after_cloak_triggers():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    queen = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 12.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 16.0))
    mechanic = queen.mechanics[0]
    battle.players[0].elixir = 10.0
    queen.attack_cooldown = 0.0
    origin = Position(queen.position.x, queen.position.y)
    target_hp = target.hitpoints

    assert mechanic.activate_ability(queen)
    for _ in range(18):
        battle.time += battle.dt
        queen.update(battle.dt, battle)

    assert queen.position == origin
    assert target.hitpoints == target_hp
    assert not any(
        isinstance(entity, Projectile) and entity.player_id == queen.player_id
        for entity in battle.entities.values()
    )
    assert queen._stealth_until > int(battle.time * 1000)
    assert mechanic.blocks_combat_actions(queen)

    battle.time += battle.dt
    queen.update(battle.dt, battle)
    assert queen._stealth_until > int(battle.time * 1000)
    assert not mechanic.blocks_combat_actions(queen)
    assert any(
        isinstance(entity, Projectile) and entity.player_id == queen.player_id
        for entity in battle.entities.values()
    )


def test_stun_does_not_interrupt_archer_queen_cast():
    battle = BattleState()
    queen = _spawn_one(battle, "ArcherQueen", 0, Position(9.0, 12.0))
    mechanic = queen.mechanics[0]
    battle.players[0].elixir = 10.0

    assert mechanic.activate_ability(queen)
    queen.apply_stun(0.5)

    assert battle.players[0].elixir == 9.0
    assert queen._stealth_until == 0
    assert mechanic.ability.is_active
    assert mechanic.blocks_combat_actions(queen)
    assert not mechanic.can_activate_ability(queen)

    battle.time = mechanic.trigger_delay_ms / 1000.0
    mechanic.on_tick(queen, mechanic.trigger_delay_ms)
    assert queen.is_stunned()
    assert queen._stealth_until == mechanic.trigger_delay_ms + mechanic.duration_ms
    assert mechanic.ability.is_active
    assert mechanic.blocks_combat_actions(queen)
    assert battle.players[0].elixir == 9.0


def test_royal_ghost_fades_by_time_since_attack_and_breaks_enemy_lock():
    battle = BattleState(rng=random.Random(19))
    ghost = _spawn_one(battle, "RoyalGhost", 0, Position(9.0, 12.0))
    enemy = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    mechanic = ghost.mechanics[0]

    assert not enemy._is_valid_target(ghost)
    enemy.target_id = ghost.id
    mechanic.time_since_attack_ms = mechanic.fade_delay_ms
    mechanic.on_object_tick(ghost, 33)
    enemy.update(battle.dt, battle)
    assert enemy.target_id != ghost.id

    mechanic.on_attack_start(ghost, enemy)
    assert ghost._stealth_until == 0


def test_royal_ghost_fade_clock_continues_while_stunned():
    battle = BattleState()
    ghost = _spawn_one(battle, "RoyalGhost", 0, Position(9.0, 12.0))
    enemy = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    mechanic = ghost.mechanics[0]

    mechanic.on_attack_start(ghost, enemy)
    ghost.apply_stun(3.0)
    mechanic.on_object_tick(ghost, mechanic.fade_delay_ms)

    assert ghost.stun_timer > 0
    assert ghost._stealth_until == 2**31 - 1


def test_royal_ghost_recloaks_after_combat_on_exact_fortieth_logic_frame():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    ghost = _spawn_one(battle, "RoyalGhost", 0, Position(9.0, 12.0))
    enemy = _spawn_one(battle, "Knight", 1, Position(9.0, 13.1))
    mechanic = ghost.mechanics[0]
    mechanic.on_attack_start(ghost, enemy)
    battle.entities.pop(enemy.id)
    assert ghost._stealth_until == 0

    for _ in range(39):
        ghost.update(battle.dt, battle)

    assert mechanic.time_since_attack_ms == 1950.0
    assert ghost._stealth_until == 0

    ghost.update(battle.dt, battle)

    assert mechanic.time_since_attack_ms == 2000.0
    assert ghost._stealth_until == 2**31 - 1


def test_enemy_commits_attack_before_royal_ghost_recloaks_in_object_phase():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    ghost = _spawn_one(battle, "RoyalGhost", 0, Position(9.0, 10.0))
    musketeer = _spawn_one(
        battle,
        "Musketeer",
        1,
        Position(9.0, 15.0),
    )
    ghost.position = Position(9.0, 10.0)
    musketeer.position = Position(9.0, 15.0)
    fade = ghost.mechanics[0]
    fade.on_attack_start(ghost, musketeer)
    fade.time_since_attack_ms = fade.fade_delay_ms - 50
    ghost.target_id = None
    musketeer.target_id = ghost.id
    musketeer.attack_cooldown = 0.0

    battle.step()

    assert ghost._stealth_until == 2**31 - 1
    assert fade.time_since_attack_ms == fade.fade_delay_ms
    assert any(
        isinstance(entity, Projectile)
        and entity.player_id == musketeer.player_id
        and entity.primary_target is ghost
        for entity in battle.entities.values()
    )


@pytest.mark.parametrize("fast_path", [False, True])
def test_combat_phase_stun_prevents_same_frame_movement_and_then_ticks(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    wizard = _spawn_one(
        battle,
        "ElectroWizard",
        0,
        Position(9.0, 10.0),
    )
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    wizard.position = Position(9.0, 10.0)
    target.position = Position(9.0, 14.0)
    wizard.target_id = target.id
    wizard.attack_cooldown = 0.0
    target.target_id = wizard.id
    target_origin = Position(target.position.x, target.position.y)

    battle.step()

    assert target.position == target_origin
    # The 500 ms hit stun is installed during combat, blocks component type 1,
    # then consumes its first 50 ms in component type 3 of the same frame.
    assert target.stun_timer == pytest.approx(0.45)


@pytest.mark.parametrize("stunner_has_lower_id", [False, True])
def test_combat_phase_stun_only_denies_later_id_attack_component(
    stunner_has_lower_id,
):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    if stunner_has_lower_id:
        wizard = _spawn_one(
            battle,
            "ElectroWizard",
            0,
            Position(9.0, 10.0),
        )
        knight = _spawn_one(battle, "Knight", 1, Position(9.0, 11.0))
    else:
        knight = _spawn_one(battle, "Knight", 1, Position(9.0, 11.0))
        wizard = _spawn_one(
            battle,
            "ElectroWizard",
            0,
            Position(9.0, 10.0),
        )
    wizard.target_id = knight.id
    knight.target_id = wizard.id
    # Isolate the ordinary attack stun from Electro Wizard's already-resolved
    # deployment zap.
    knight.stun_timer = 0.0
    knight._freeze_target_pause_remaining = 0.0
    wizard.attack_cooldown = 0.0
    knight.attack_cooldown = 0.0
    wizard_hp = wizard.hitpoints

    battle.step()

    assert knight.stun_timer == pytest.approx(0.45)
    if stunner_has_lower_id:
        assert wizard.hitpoints == wizard_hp
    else:
        assert wizard_hp - wizard.hitpoints == knight.damage


def test_royal_ghost_character_clock_runs_on_deploy_zero_crossing():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("RoyalGhost")
    assert stats is not None
    battle._spawn_unit_at_position(Position(9.0, 12.0), 0, stats)
    ghost = next(
        entity for entity in battle.entities.values() if isinstance(entity, Troop)
    )
    mechanic = ghost.mechanics[0]
    mechanic.time_since_attack_ms = 0.0
    ghost._stealth_until = 0
    ghost.deploy_delay_remaining = battle.dt
    ghost.placement_delay_total = battle.dt
    ghost.placement_pending = True

    ghost.update(battle.dt, battle)

    assert not ghost.placement_pending
    assert mechanic.time_since_attack_ms == 50.0
    assert ghost._stealth_until == 0


@pytest.mark.parametrize("status", ["stun", "slow"])
def test_royal_ghost_does_not_recloak_mid_fight_when_status_delays_next_hit(status):
    battle = BattleState()
    ghost = _spawn_one(battle, "RoyalGhost", 0, Position(9.0, 12.0))
    enemy = _spawn_one(battle, "Knight", 1, Position(9.0, 13.5))
    mechanic = ghost.mechanics[0]
    ghost.target_id = enemy.id

    mechanic.on_attack_start(ghost, enemy)
    if status == "stun":
        ghost.apply_stun(3.0)
        # Stun breaks the old lock. The combat observer reacquires before the
        # character-owned inactivity clock advances in a normal frame.
        ghost.update_combat_component(battle.dt, battle)
    else:
        ghost.apply_slow(3.0, 0.7)
    mechanic.on_object_tick(ghost, mechanic.fade_delay_ms + 50)

    assert mechanic.use_attack_range
    assert mechanic.time_since_attack_ms == 0.0
    assert ghost._stealth_until == 0


def test_royal_ghost_hovers_across_the_river_without_becoming_an_air_target():
    battle = BattleState()
    ghost = _spawn_one(battle, "RoyalGhost", 0, Position(9.0, 14.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 20.0))
    target.speed = 0.0

    assert not ghost.is_air_unit
    assert not ghost._can_attack_air()
    goal = native_route_goal_cell(ghost, target)
    assert goal is not None
    goal_center = _cell_center(goal)
    for _ in range(90):
        ghost._move_towards_target(target, battle.dt, battle)
        if ghost.position.y >= 17.0:
            break

    assert ghost.position.y >= 17.0
    assert abs(ghost.position.x - goal_center.x) < abs(9.0 - goal_center.x)


def test_hovering_troops_touch_blocked_tiles_symmetrically_at_boundaries():
    battle = BattleState()
    lower = _spawn_one(battle, "RoyalGhost", 0, Position(3.5, 12.0))
    upper = _spawn_one(battle, "RoyalGhost", 1, Position(14.5, 20.0))
    lower_boundary = Position(0.823, 14.0)
    upper_boundary = Position(17.177, 18.0)

    assert not battle.is_ground_position_walkable(lower_boundary, lower)
    assert not battle.is_ground_position_walkable(upper_boundary, upper)


def test_fisherman_hook_uses_serialized_range_windup_and_projectile_motion():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn_one(battle, "Fisherman", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 16.0))
    fisherman.position = Position(9.0, 10.0)
    target.position = Position(9.0, 16.0)
    mechanic = fisherman.mechanics[0]

    assert mechanic.hook_min_range == 3.5
    assert mechanic.hook_range == 7.0
    assert mechanic.hook_windup_ms == 1300
    assert mechanic.projectile_speed == pytest.approx(800 / 50)
    assert mechanic.drag_back_speed == pytest.approx(850 / 50)
    assert mechanic.drag_self_speed == pytest.approx(450 / 50)
    assert mechanic.drag_back_as_attractor
    assert mechanic.drag_margin == 0.2

    target.position.y = 13.5
    mechanic.on_tick(fisherman, 1)
    assert mechanic.state == "idle"

    target.position.y = 16.0
    mechanic.on_tick(fisherman, 1)
    assert mechanic.state == "windup"
    assert fisherman._special_move_active
    mechanic.on_tick(fisherman, 1299)
    assert mechanic.state == "windup"
    assert mechanic.windup_remaining_ms == pytest.approx(1)
    mechanic.on_tick(fisherman, 1)
    assert mechanic.state == "flight"
    assert mechanic.hook_position == Position(9.0, 10.45)

    before = Position(mechanic.hook_position.x, mechanic.hook_position.y)
    mechanic.on_object_tick(fisherman, 50)
    assert mechanic.state == "flight"
    assert mechanic.hook_position.y - before.y == pytest.approx(
        mechanic.projectile_speed * 0.05
    )


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("hook_state", ["windup", "flight", "drag"])
def test_stun_resets_fisherman_hook_in_every_committed_state(
    fast_path,
    hook_state,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn_one(battle, "Fisherman", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 16.0))
    target.apply_stun(10.0)
    mechanic = fisherman.mechanics[0]

    mechanic.on_tick(fisherman, 1)
    assert mechanic.state == "windup"
    if hook_state != "windup":
        mechanic.on_tick(fisherman, 1300)
        assert mechanic.state == "flight"
    if hook_state == "drag":
        mechanic.hook_position = Position(target.position.x, target.position.y)
        mechanic.on_object_tick(fisherman, 50)
        assert mechanic.state == "drag"
        assert target.forced_movement_active

    fisherman_position = Position(fisherman.position.x, fisherman.position.y)
    target_position = Position(target.position.x, target.position.y)

    fisherman.apply_stun(0.5, source_kind="Zap")

    assert mechanic.state == "idle"
    assert mechanic.hook_target_id is None
    assert mechanic.hook_position is None
    assert fisherman.target_id is None
    assert not fisherman._special_move_active
    assert not target.forced_movement_active

    battle.step()

    assert fisherman.position == fisherman_position
    assert target.position == target_position
    assert mechanic.state == "idle"


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("hook_state", ["windup", "flight", "drag"])
def test_primary_death_cancels_fisherman_hook_in_every_committed_state(
    fast_path,
    hook_state,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn_one(battle, "Fisherman", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 16.0))
    mechanic = fisherman.mechanics[0]

    mechanic.on_tick(fisherman, 1)
    if hook_state != "windup":
        mechanic.on_tick(fisherman, 1300)
    if hook_state == "drag":
        mechanic.hook_position = Position(target.position.x, target.position.y)
        mechanic.on_object_tick(fisherman, 50)
        assert target.forced_movement_active
    assert mechanic.state == hook_state

    target.take_damage(target.hitpoints)
    if hook_state == "windup":
        mechanic.on_tick(fisherman, 50)
    else:
        mechanic.on_object_tick(fisherman, 50)

    assert mechanic.state == "idle"
    assert mechanic.hook_target_id is None
    assert mechanic.hook_position is None
    assert fisherman.target_id is None
    assert not fisherman._special_move_active
    assert not target.forced_movement_active


@pytest.mark.parametrize("fast_path", [False, True])
def test_fisherman_death_immediately_releases_a_hooked_target(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn_one(battle, "Fisherman", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 16.0))
    mechanic = fisherman.mechanics[0]
    mechanic.on_tick(fisherman, 1)
    mechanic.on_tick(fisherman, 1300)
    mechanic.hook_position = Position(target.position.x, target.position.y)
    mechanic.on_object_tick(fisherman, 50)
    assert mechanic.state == "drag"
    assert target.forced_movement_active

    target_position = Position(target.position.x, target.position.y)
    fisherman.take_damage(fisherman.hitpoints)

    assert mechanic.state == "idle"
    assert mechanic.hook_target_id is None
    assert mechanic.hook_position is None
    assert not target.forced_movement_active
    target.update_movement_component(battle.dt, battle)
    assert target.position == target_position


def test_fisherman_hook_launch_advances_in_same_frames_object_phase():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn_one(battle, "Fisherman", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 16.0))
    target.apply_stun(10.0)
    mechanic = fisherman.mechanics[0]
    mechanic._begin_windup(fisherman, target)
    mechanic.windup_remaining_ms = 50.0

    battle.step()

    assert mechanic.state == "flight"
    # The 0.45-tile muzzle offset is followed by one serialized 800-unit
    # projectile step in the launch frame's later object phase.
    assert mechanic.hook_position == Position(9.0, 11.25)


def test_fisherman_hook_pulls_only_the_victim_to_the_serialized_surface_margin():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn_one(battle, "Fisherman", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 16.0))
    fisherman.position = Position(9.0, 10.0)
    target.position = Position(9.0, 16.0)
    mechanic = fisherman.mechanics[0]
    target_hp = target.hitpoints

    mechanic.on_tick(fisherman, 1)
    mechanic.on_tick(fisherman, 1300)
    for _ in range(40):
        mechanic.on_object_tick(fisherman, 50)
        if mechanic.state == "idle":
            break

    expected_distance = (
        fisherman.get_collision_radius()
        + target.get_collision_radius()
        + mechanic.drag_margin
    )
    assert mechanic.state == "idle"
    assert fisherman.position == Position(9.0, 10.0)
    assert target.position.y < 16.0
    assert fisherman.position.distance_to(target.position) == pytest.approx(
        expected_distance
    )
    assert not target.forced_movement_active
    assert target.attack_cooldown == pytest.approx(
        target.get_base_attack_interval_seconds()
    )
    assert target.hitpoints == target_hp
    assert target.slow_multiplier == 1.0


def test_fisherman_hook_pulls_self_to_buildings_without_moving_them():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn_one(battle, "Fisherman", 0, Position(9.0, 10.0))
    fisherman.position = Position(9.0, 10.0)
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 16.0),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    cannon.on_spawn()
    mechanic = fisherman.mechanics[0]
    cannon_position = Position(cannon.position.x, cannon.position.y)

    mechanic.on_tick(fisherman, 1)
    mechanic.on_tick(fisherman, 1300)
    for _ in range(50):
        mechanic.on_object_tick(fisherman, 50)
        if mechanic.state == "idle":
            break

    assert cannon.position == cannon_position
    assert fisherman.position.y > 10.0
    assert fisherman.position.distance_to(cannon.position) == pytest.approx(
        fisherman.get_collision_radius()
        + cannon.get_collision_radius()
        + mechanic.drag_margin
    )


def test_fisherman_hook_preserves_the_victims_existing_combat_lock():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn_one(battle, "Fisherman", 0, Position(9.0, 10.0))
    victim = _spawn_one(battle, "Knight", 1, Position(9.0, 16.0))
    locked_target = _spawn_one(battle, "Giant", 0, Position(9.0, 24.0))
    victim.target_id = locked_target.id
    victim._last_combat_target_id = locked_target.id
    mechanic = fisherman.mechanics[0]

    mechanic.on_tick(fisherman, 1)
    mechanic.on_tick(fisherman, 1300)
    for _ in range(40):
        mechanic.on_object_tick(fisherman, 50)
        if mechanic.state == "idle":
            break

    assert mechanic.state == "idle"
    assert victim.target_id == locked_target.id
    assert victim._last_combat_target_id == locked_target.id


def test_fisherman_hook_in_flight_misses_a_target_that_starts_a_river_jump():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn_one(battle, "Fisherman", 0, Position(9.0, 10.0))
    hog = _spawn_one(battle, "HogRider", 1, Position(9.0, 16.0))
    mechanic = fisherman.mechanics[0]

    mechanic.on_tick(fisherman, 1)
    mechanic.on_tick(fisherman, 1300)
    assert mechanic.state == "flight"
    position_before = Position(hog.position.x, hog.position.y)
    hog._river_jump_active = True

    mechanic.on_object_tick(fisherman, 50)

    assert mechanic.state == "idle"
    assert hog.position == position_before
    assert not hog.forced_movement_active


@pytest.mark.parametrize("card_name", ["Bandit", "MegaKnight"])
def test_fisherman_hook_cancels_invulnerable_dash_and_mega_knight_leap(card_name):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    fisherman = _spawn_one(battle, "Fisherman", 0, Position(9.0, 10.0))
    mover = _spawn_one(battle, card_name, 1, Position(9.0, 16.0))
    mover.target_id = fisherman.id
    special = mover.mechanics[0]
    if card_name == "Bandit":
        special._launch_dash(mover, fisherman)
        assert mover._bandit_dashing
        assert not mover.can_receive_effect("Fisherman")
    else:
        special._launch_leap(mover, fisherman, 6.0)
        assert mover._mk_leap_phase == "airborne"

    assert mover.can_receive_forced_movement("Fisherman", "hook")
    hook = fisherman.mechanics[0]
    hook.state = "flight"
    hook.hook_target_id = mover.id
    hook.hook_position = Position(mover.position.x, mover.position.y)

    hook.on_object_tick(fisherman, 50)

    assert hook.state == "drag"
    assert mover.forced_movement_active
    assert not mover._special_move_active
    if card_name == "Bandit":
        assert not mover._bandit_dashing
        assert mover._bandit_invulnerable_until == 0
    else:
        assert mover._mk_leap_phase is None


def test_charge_distance_uses_game_units_and_can_recharge_after_attacking():
    battle = BattleState(rng=random.Random(23))
    prince = _spawn_one(battle, "Prince", 0, Position(9.0, 10.0))
    giant = _spawn_one(battle, "Giant", 1, Position(9.0, 24.0))
    prince.attack_cooldown = 0.8

    for _ in range(41):
        prince._move_towards_target(giant, battle.dt, battle)
    assert not prince.is_charging
    assert prince._native_charge_progress == 9840

    prince._move_towards_target(giant, battle.dt, battle)
    assert prince.is_charging
    assert prince._native_charge_progress == 10080
    # Crossing the threshold happens at the end of the native call. Charged
    # speed and the combat preload byte take effect on the following call.
    assert prince.speed == 60.0
    assert prince.attack_cooldown == 0.8

    prince._move_towards_target(giant, battle.dt, battle)
    assert prince.speed == 120.0
    assert prince.attack_cooldown == 0.0
    assert prince._get_attack_damage() == prince.card_stats.scaled_damage_special

    prince._on_attack()
    assert not prince.is_charging
    assert prince.speed == 60.0
    prince.position = Position(9.0, 10.0)
    for _ in range(42):
        prince._move_towards_target(giant, battle.dt, battle)
    assert prince.is_charging
    prince.apply_stun(0.5)
    assert prince.is_charging
    prince.update_movement_component(battle.dt, battle)
    assert not prince.is_charging
    assert prince.attack_cooldown == pytest.approx(
        prince.card_stats.first_hit_time / 1000.0
    )

    # Charge readiness is canceled while ordinary passive load is retained.
    prince.is_charging = True
    prince.attack_cooldown = 0.0
    prince.interrupt_by_knockback()
    assert not prince.is_charging
    assert prince.attack_cooldown == pytest.approx(
        prince.card_stats.first_hit_time / 1000.0
    )

    prince.apply_slow(1.0, 0.5)
    prince._native_charge_progress = 10000
    prince._update_charging_state(battle)
    prince._prepare_native_charge_movement()
    assert prince.speed == 60.0
    prince.reset_charge()
    assert prince.speed == 30.0
    prince.update_status_effects(1.0)
    assert prince.speed == 60.0


@pytest.mark.parametrize("card_name", ["Prince", "DarkPrince", "BattleRam"])
@pytest.mark.parametrize("interruption", ["stun", "knockback"])
def test_every_enabled_charging_troop_uses_native_windup_after_interruption(
    card_name,
    interruption,
):
    battle = BattleState(rng=random.Random(24))
    troop = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    troop.is_charging = True
    troop.attack_cooldown = 0.0

    if interruption == "stun":
        troop.apply_stun(0.5)
        assert troop.is_charging
        troop.update_movement_component(battle.dt, battle)
    else:
        troop.interrupt_by_knockback()

    assert not troop.is_charging
    expected = troop.card_stats.first_hit_time / 1000.0
    assert troop.attack_cooldown == pytest.approx(
        expected
    )


@pytest.mark.parametrize("card_name", ["Prince", "DarkPrince", "BattleRam"])
def test_enabled_chargers_use_absolute_serialized_speed_percentage(card_name):
    battle = BattleState()
    troop = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    base_speed = troop.card_stats.speed
    troop._native_charge_progress = 10000

    troop._update_charging_state(battle)
    troop._prepare_native_charge_movement()

    assert troop.is_charging
    assert troop.card_stats.charge_speed_multiplier == 200
    assert troop.speed == pytest.approx(base_speed * 2.0)


@pytest.mark.parametrize(
    ("card_name", "activation_frames", "final_progress"),
    [
        ("Prince", 42, 10080),
        ("DarkPrince", 50, 10000),
        ("BattleRam", 50, 10000),
    ],
)
def test_every_enabled_charger_uses_serialized_integer_progress(
    card_name,
    activation_frames,
    final_progress,
):
    battle = BattleState()
    troop = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Giant", 1, Position(9.0, 25.0))

    for _ in range(activation_frames - 1):
        troop._move_towards_target(target, battle.dt, battle)
    assert not troop.is_charging

    troop._move_towards_target(target, battle.dt, battle)

    assert troop._native_charge_progress == final_progress
    assert troop.is_charging


@pytest.mark.parametrize(
    ("effect", "increment", "activation_frames", "crossing_speed"),
    [
        ("normal", 240, 42, 60.0),
        ("rage", 312, 33, 60.0),
        ("slow", 168, 60, 42.0),
    ],
)
def test_charge_uses_native_multiply_before_divide_under_speed_effects(
    effect,
    increment,
    activation_frames,
    crossing_speed,
):
    battle = BattleState()
    prince = _spawn_one(battle, "Prince", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Giant", 1, Position(9.0, 25.0))
    prince.attack_cooldown = 0.75
    if effect == "rage":
        prince.apply_haste(10.0, 1.3, 1.3, 1.3)
    elif effect == "slow":
        prince.apply_slow(10.0, 0.7)

    for _ in range(activation_frames - 1):
        prince._move_towards_target(target, battle.dt, battle)

    assert prince._native_charge_progress == increment * (activation_frames - 1)
    assert not prince.is_charging

    prince._move_towards_target(target, battle.dt, battle)

    assert prince._native_charge_progress == increment * activation_frames
    assert prince.is_charging
    assert prince.speed == pytest.approx(crossing_speed)
    assert prince.attack_cooldown == 0.75

    prince._move_towards_target(target, battle.dt, battle)

    assert prince.speed == pytest.approx(120.0 * prince.slow_multiplier)
    assert prince.attack_cooldown == 0.0


def test_positive_sub_ten_movement_advances_partial_charge():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    prince = _spawn_one(battle, "Prince", 0, Position(9.0, 10.0))
    prince._native_charge_progress = 9999
    prince.distance_traveled = 2.49

    prince._advance_native_charge(5)

    # Native f688d4..f688e4 adds 1000*5/250; positive work does not reset.
    assert prince._native_charge_progress == 10019
    assert prince.distance_traveled == pytest.approx(2.495)
    assert prince.is_charging


def test_tilemap_terrain_query_does_not_override_native_move_or_charge_work(
    monkeypatch,
):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    prince = _spawn_one(battle, "Prince", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 13.0))
    start = copy.copy(prince.position)
    monkeypatch.setattr(
        battle,
        "is_ground_position_walkable",
        lambda position, mover: position == start,
    )

    waypoint = ground_path_waypoint(
        battle,
        prince,
        target.position,
        target_entity=target,
    )
    delta = movement_component_vector_logic_units(
        tiles_to_logic_units(waypoint.x - start.x),
        tiles_to_logic_units(waypoint.y - start.y),
        speed_work_for_duration(prince.speed, battle.dt),
    )
    prince._move_towards_target(target, battle.dt, battle)
    assert prince.position == Position(
        start.x + logic_units_to_tiles(delta[0]),
        start.y + logic_units_to_tiles(delta[1]),
    )
    assert prince._native_charge_progress == 240
    assert prince.distance_traveled == 0.06


def test_charge_resets_when_stopped_troop_starts_toward_a_new_target():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    prince = _spawn_one(battle, "Prince", 0, Position(9.0, 10.0))
    first = _spawn_one(battle, "Giant", 1, Position(9.0, 15.0))
    second = _spawn_one(battle, "Giant", 1, Position(11.5, 16.0))
    prince.attack_cooldown = 99.0
    prince.target_id = first.id

    for _ in range(10):
        prince.update_combat_component(battle.dt, battle)
        prince.update_movement_component(battle.dt, battle)

    assert prince._native_natural_movement_active
    assert prince._native_charge_progress == 2400

    # Entering reach clears an incomplete charge bank. Full charge readiness
    # is a separate state covered by the charged-hit native controls.
    first.position = Position(prince.position.x, prince.position.y + 1.0)
    prince.update_combat_component(battle.dt, battle)
    prince.update_movement_component(battle.dt, battle)
    stopped_progress = prince._native_charge_progress
    assert stopped_progress == 0
    assert not prince._native_natural_movement_active

    first.take_damage(first.hitpoints)
    battle._cleanup_dead_entities()
    # Entering range started a hit even while its load was incomplete.
    # Removal consumes the ordinary finish interval before movement resumes.
    assert prince._attack_finish_elapsed_ms > 0
    while prince._attack_finish_elapsed_ms:
        prince.update_combat_component(battle.dt, battle)
        prince.update_movement_component(battle.dt, battle)
        assert prince._native_charge_progress == stopped_progress
        assert not prince._native_natural_movement_active
    prince.target_id = second.id
    prince.update_combat_component(battle.dt, battle)
    prince.update_movement_component(battle.dt, battle)

    assert prince.target_id == second.id
    assert prince._native_natural_movement_active
    assert prince._native_charge_progress == 240
    assert prince.distance_traveled == 0.06


def test_charged_prince_hit_is_consumed_by_shield_without_health_overflow():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    prince = _spawn_one(battle, "Prince", 0, Position(9.0, 10.0))
    guard = _spawn_one(battle, "Guards", 1, Position(9.0, 11.0))
    shield = next(
        mechanic
        for mechanic in guard.mechanics
        if type(mechanic).__name__ == "Shield"
    )
    hp_before = guard.hitpoints
    prince._native_charge_progress = 10000
    prince._update_charging_state()
    prince.attack_cooldown = 0.0

    prince.update_combat_component(battle.dt, battle)

    assert shield.current_shield == 0
    assert guard.hitpoints == hp_before
    assert prince._native_charge_progress == 0
    assert not prince.is_charging


@pytest.mark.parametrize("charged", [False, True])
def test_dark_prince_charge_payload_splashes_each_shield_once(charged):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    dark_prince = _spawn_one(
        battle,
        "DarkPrince",
        0,
        Position(9.0, 10.0),
    )
    primary = _spawn_one(battle, "Guards", 1, Position(9.0, 11.0))
    secondary = _spawn_one(battle, "Guards", 1, Position(10.0, 11.0))
    shields = [
        next(
            mechanic
            for mechanic in target.mechanics
            if type(mechanic).__name__ == "Shield"
        )
        for target in (primary, secondary)
    ]
    hp_before = (primary.hitpoints, secondary.hitpoints)
    if charged:
        dark_prince._native_charge_progress = 10000
        dark_prince._update_charging_state()
    dark_prince.attack_cooldown = 0.0

    dark_prince.update_combat_component(battle.dt, battle)

    assert [shield.current_shield for shield in shields] == [0, 0]
    assert (primary.hitpoints, secondary.hitpoints) == hp_before
    assert dark_prince._native_charge_progress == 0
    assert not dark_prince.is_charging


def test_jump_height_units_cross_the_river_off_bridge_and_are_untargetable_midair():
    battle = BattleState(rng=random.Random(27))
    hog = _spawn_one(battle, "HogRider", 0, Position(9.0, 14.0))
    enemy = _spawn_one(battle, "Knight", 1, Position(10.0, 18.0))
    hog_hp = hog.hitpoints

    for _ in range(120):
        hog.update(battle.dt, battle)
        if getattr(hog, "_river_jump_active", False):
            break
    assert hog._river_jump_active
    assert enemy._is_valid_target(hog)
    assert enemy.get_nearest_target(battle.entities) is not hog
    enemy.target_id = hog.id
    enemy.update(battle.dt, battle)
    assert enemy.target_id != hog.id

    from clasher.spells import DirectDamageSpell

    ground_only = DirectDamageSpell(
        "ground-test", 0, radius=1.0, damage=10, hits_air=False, hits_ground=True
    )
    assert not ground_only.cast(battle, 1, Position(hog.position.x, hog.position.y))
    assert hog.hitpoints == hog_hp

    air_capable = DirectDamageSpell(
        "air-test", 0, radius=1.0, damage=10, stun_duration=1.0,
        hits_air=True, hits_ground=False,
    )
    assert air_capable.cast(battle, 1, Position(hog.position.x, hog.position.y))
    assert hog.hitpoints == hog_hp - 10
    assert hog.stun_timer == 1.0

    for _ in range(120):
        hog.update(battle.dt, battle)
        if not getattr(hog, "_river_jump_active", False):
            break
    assert hog.position.y >= 17.0
    assert battle.arena.is_walkable(hog.position)


def test_battle_ram_connect_deals_one_charge_hit_then_releases_barbarians():
    battle = BattleState(rng=random.Random(29))
    ram = _spawn_one(battle, "BattleRam", 0, Position(9.0, 14.0))
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(Building, Position(9.0, 15.0), 1, cannon_stats)
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    ram.is_charging = True
    ram.attack_cooldown = 0.0
    hp_before = cannon.hitpoints

    ram.update(battle.dt, battle)
    assert hp_before - cannon.hitpoints == ram.card_stats.scaled_damage_special
    assert not ram.is_alive
    battle._cleanup_dead_entities()
    barbarians = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.player_id == 0 and entity.card_stats.name == "Barbarian"
    ]
    assert len(barbarians) == 2
    assert all(barbarian.placement_pending for barbarian in barbarians)
    assert all(barbarian.deploy_delay_remaining == 1.0 for barbarian in barbarians)
    assert all(
        (
            barbarian.max_hitpoints,
            barbarian.card_stats.hit_speed,
            barbarian.card_stats.load_time,
            barbarian.card_stats.first_hit_time,
        )
        == (691, 1400, 1000, 400)
        for barbarian in barbarians
    )
    # SpawnAngleShift=180 is relative to the ram's retained +y facing. The
    # native descending two-slot ring therefore releases one Barbarian ahead
    # and one behind, not via a Battle-Ram-only perpendicular special case.
    for barbarian, expected in zip(
        barbarians,
        ((0.0, 0.6), (0.0, -0.6)),
        strict=True,
    ):
        assert (
            barbarian.position.x - ram.position.x,
            barbarian.position.y - ram.position.y,
        ) == pytest.approx(expected)


@pytest.mark.parametrize("fast_path", [False, True])
def test_spawn_slam_cannot_target_lethal_battle_ram_death_spawns_same_frame(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    battle._spawn_unit_at_position(
        Position(8.75, 13.0),
        0,
        battle.card_loader.get_card("BattleRam"),
        snap_to_valid=False,
    )
    battle._spawn_unit_at_position(
        Position(9.25, 13.8),
        1,
        battle.card_loader.get_card("MegaKnight"),
        snap_to_valid=False,
    )
    mega_knight = battle.entities[2]
    for entity in battle.entities.values():
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity.attack_cooldown = 0.0
        entity._attack_preload_blocked = False
        entity.speed = 0.0
        entity.hitpoints = 1.0
        entity.damage = 100_000.0
    if fast_path:
        battle._refresh_fast_path_caches()

    battle.step()

    barbarians = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Barbarian"
    ]
    assert len(barbarians) == 2
    assert all(barbarian.hitpoints == barbarian.max_hitpoints for barbarian in barbarians)
    assert list(battle.entities) == [mega_knight.id, *(barbarian.id for barbarian in barbarians)]
    assert mega_knight.target_id is None
    assert all(
        barbarian._death_spawn_target_immunity_elapsed_ms == 50
        for barbarian in barbarians
    )
    # Target immunity does not remove physical arena presence, so the new
    # Barbarians still apply birth-frame collision pressure.
    assert mega_knight.position == Position(9.312, 13.824)


@pytest.mark.parametrize("fast_path", [False, True])
def test_battle_ram_birth_frame_advances_released_barbarian_deploy_clock(
    fast_path,
):
    battle = BattleState(fast_path=fast_path, rng=random.Random(29))
    battle.entities.clear()
    battle.next_entity_id = 1
    ram = _spawn_one(battle, "BattleRam", 0, Position(9.0, 14.0))
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 15.0),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    ram.position = Position(9.0, 14.0)
    cannon.position = Position(9.0, 15.0)
    ram.is_charging = True
    ram.attack_cooldown = 0.0

    battle.step()

    barbarians = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Barbarian"
    ]
    assert len(barbarians) == 2
    assert all(barbarian.placement_pending for barbarian in barbarians)
    assert all(
        barbarian.deploy_delay_remaining == pytest.approx(0.95)
        for barbarian in barbarians
    )


def test_bandit_charge_is_interruptible_then_dash_is_targetable_but_invulnerable():
    battle = BattleState(rng=random.Random(31))
    bandit = _spawn_one(battle, "Bandit", 0, Position(9.0, 10.0))
    # Bandit's native minimum is an edge-to-edge gap, so include both the
    # Bandit and Knight collision radii in the center spacing.
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.8))
    hp_before = target.hitpoints

    bandit.update(battle.dt, battle)  # acquire target
    bandit.update(battle.dt, battle)  # start charge
    assert bandit._bandit_charging
    assert not bandit._bandit_dashing
    assert bandit.mechanics[0].dash_duration_ms == 800
    assert target.hitpoints == hp_before

    # The pre-dash whistle/charge is still vulnerable and a stun resets it.
    bandit_hp = bandit.hitpoints
    bandit.take_damage(1)
    bandit.apply_stun(1.0)
    assert bandit.hitpoints == bandit_hp - 1
    assert bandit.stun_timer == 1.0
    assert not bandit._bandit_charging

    bandit.stun_timer = 0.0
    bandit.target_id = target.id
    bandit.mechanics[0].on_tick(bandit, 1)
    assert bandit._bandit_charging
    bandit.mechanics[0].on_tick(bandit, 800)
    assert bandit._bandit_dashing
    assert target._is_valid_target(bandit)
    dash_hp = bandit.hitpoints
    bandit.take_damage(9999)
    bandit.apply_stun(1.0)
    assert bandit.hitpoints == dash_hp
    assert bandit.stun_timer == 0.0

    for _ in range(120):
        bandit.update(battle.dt, battle)
        if not bandit._bandit_dashing:
            break

    expected_dash_damage = bandit.card_stats.get_scaled_stat(152)
    assert hp_before - target.hitpoints == expected_dash_damage


def test_opposing_bandits_are_both_invulnerable_when_their_dashes_cross():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    first = _spawn_one(battle, "Bandit", 0, Position(9.0, 10.0))
    # Leave enough room for both movement components to advance before their
    # dash predicates run on the first update.
    second = _spawn_one(battle, "Bandit", 1, Position(9.0, 14.9))
    hp_before = (first.hitpoints, second.hitpoints)
    both_launched = False

    for _ in range(120):
        battle.step()
        if first._bandit_dashing and second._bandit_dashing:
            both_launched = True
        if both_launched and not first._bandit_dashing and not second._bandit_dashing:
            break

    assert both_launched
    assert (first.hitpoints, second.hitpoints) == hp_before


def test_enabled_runtime_traits_come_from_nested_character_data():
    battle = BattleState()
    baby_dragon = battle.card_loader.get_card("BabyDragon")
    royal_ghost = battle.card_loader.get_card("RoyalGhost")
    bowler = battle.card_loader.get_card("Bowler")
    mega_minion = battle.card_loader.get_card("MegaMinion")

    assert baby_dragon._raw_entry["summonCharacterData"]["flyingHeight"] == 3500
    assert royal_ghost._raw_entry["summonCharacterData"]["hovering"] is True
    assert (
        royal_ghost._raw_entry["summonCharacterData"][
            "allowAreaDmgWhenInvisible"
        ]
        is True
    )
    assert royal_ghost.allow_area_damage_when_invisible
    assert bowler._raw_entry["summonCharacterData"]["ignorePushback"] is True
    assert mega_minion._raw_entry["summonCharacterData"]["mass"] == 6
    assert unit_mass(mega_minion) == 6.0


def test_bandit_uses_serialized_post_landing_immunity_window():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    bandit = _spawn_one(battle, "Bandit", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.8))
    mechanic = bandit.mechanics[0]
    mechanic._launch_dash(bandit, target)
    assert mechanic.post_dash_immunity_ms == 100

    # Put the committed travel within one movement update of landing.
    bandit.position = Position(
        bandit._bandit_dash_target[0],
        bandit._bandit_dash_target[1] - 0.01,
    )
    battle.time = 10.0
    mechanic._update_dash(bandit, 50)
    assert not bandit._bandit_dashing
    hp = bandit.hitpoints

    bandit.take_damage(1)
    bandit.apply_stun(1.0)
    assert bandit.hitpoints == hp
    assert bandit.stun_timer == 1.0
    assert bandit.can_receive_forced_movement("Snowball", "knockback")

    bandit.stun_timer = 0.0
    battle.time = 10.05
    bandit.take_damage(1)
    assert bandit.hitpoints == hp

    battle.time = 10.10
    bandit.take_damage(1)
    bandit.apply_stun(1.0)
    assert bandit.hitpoints == hp - 1
    assert bandit.stun_timer == 1.0


@pytest.mark.parametrize("card_name", ["Bandit", "MegaKnight"])
def test_dash_launch_advances_in_same_frames_movement_component(card_name):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    mover = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.8))
    target.apply_stun(10.0)
    mover.target_id = target.id
    mechanic = mover.mechanics[0]
    start_y = mover.position.y

    if card_name == "Bandit":
        mechanic._start_charge(mover, target)
        mover._bandit_dash_timer = mechanic.dash_duration_ms - 50
    else:
        mechanic._start_charge(mover, target)
        mover._mk_leap_progress = mechanic.leap_duration_ms - 50

    battle.step()

    assert mover.position.y > start_y
    if card_name == "Bandit":
        assert mover._bandit_dashing
        assert mover.position.y - start_y == pytest.approx(0.5)
    else:
        assert mover._mk_leap_phase == "airborne"
        assert mover._mk_leap_progress == pytest.approx(50.0)


@pytest.mark.parametrize("fast_path", [False, True])
def test_committed_bandit_dash_finishes_without_a_hit_if_primary_dies(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    bandit = _spawn_one(battle, "Bandit", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 14.5))
    secondary = _spawn_one(battle, "Knight", 1, Position(13.0, 14.5))
    secondary.apply_stun(10.0)
    mechanic = bandit.mechanics[0]
    mechanic._launch_dash(bandit, primary)
    committed_endpoint = Position(
        bandit._bandit_dash_target[0],
        bandit._bandit_dash_target[1],
    )
    secondary_hp = secondary.hitpoints

    primary.take_damage(primary.hitpoints)
    for _ in range(20):
        battle.step()
        if not bandit._bandit_dashing:
            break

    assert not bandit._bandit_dashing
    assert bandit.position == committed_endpoint
    assert secondary.hitpoints == secondary_hp


@pytest.mark.parametrize("fast_path", [False, True])
def test_committed_mega_knight_leap_still_slams_if_primary_dies(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    mega_knight = _spawn_one(
        battle,
        "MegaKnight",
        0,
        Position(9.0, 10.0),
    )
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 14.5))
    mechanic = mega_knight.mechanics[0]
    mechanic._launch_leap(
        mega_knight,
        primary,
        mega_knight.position.distance_to(primary.position),
    )
    landing = Position(
        mega_knight._mk_leap_target[0],
        mega_knight._mk_leap_target[1],
    )
    secondary = _spawn_one(
        battle,
        "Knight",
        1,
        Position(landing.x + 2.0, landing.y),
    )
    secondary.apply_stun(10.0)
    secondary_hp = secondary.hitpoints

    primary.take_damage(primary.hitpoints)
    for _ in range(20):
        battle.step()
        if mega_knight._mk_leap_phase == "landing":
            break

    assert mega_knight._mk_leap_phase == "landing"
    assert mega_knight.position == landing
    assert secondary_hp - secondary.hitpoints == mega_knight.card_stats.get_scaled_stat(
        mechanic.jump_damage
    )


@pytest.mark.parametrize(
    ("card_name", "max_edge_range"),
    [("Bandit", 6.0), ("MegaKnight", 5.0)],
)
def test_dash_and_leap_initiation_ranges_measure_to_target_hitbox(
    card_name,
    max_edge_range,
):
    battle = BattleState()
    mover = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    target.position = Position(
        9.0,
        10.0 + max_edge_range + target.get_collision_radius() - 0.05,
    )
    mover.target_id = target.id

    mover.mechanics[0].on_tick(mover, 1)

    if card_name == "Bandit":
        assert mover._bandit_charging
    else:
        assert mover._mk_leap_phase == "charging"


@pytest.mark.parametrize(
    "card_name",
    ["Bandit", "MegaKnight"],
)
def test_dash_and_leap_minimum_range_measures_edge_to_edge_inclusively(card_name):
    battle = BattleState()
    mover = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    mechanic = mover.mechanics[0]
    minimum_range = (
        mechanic.dash_min_range
        if card_name == "Bandit"
        else mechanic.jump_min_range
    )
    minimum_center_distance = (
        minimum_range
        + mover.get_collision_radius()
        + target.get_collision_radius()
    )

    target.position = Position(9.0, 10.0 + minimum_center_distance - 0.001)
    assert mechanic._target_edge_distance(mover, target) is None

    target.position = Position(9.0, 10.0 + minimum_center_distance)
    assert mechanic._target_edge_distance(mover, target) is not None


@pytest.mark.parametrize(
    ("card_name", "maximum_range"),
    [("Bandit", 6.0), ("MegaKnight", 5.0)],
)
def test_dash_and_leap_maximum_target_edge_range_is_inclusive(
    card_name,
    maximum_range,
):
    battle = BattleState()
    mover = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    mechanic = mover.mechanics[0]
    maximum_center_distance = maximum_range + target.get_collision_radius()

    target.position = Position(9.0, 10.0 + maximum_center_distance)
    assert mechanic._target_edge_distance(mover, target) is not None

    target.position = Position(9.0, 10.0 + maximum_center_distance + 0.001)
    assert mechanic._target_edge_distance(mover, target) is None


@pytest.mark.parametrize(
    ("card_name", "max_edge_range"),
    [("Bandit", 6.0), ("MegaKnight", 5.0)],
)
def test_dash_and_leap_ranges_use_native_death_spawn_distance_allowance(
    card_name,
    max_edge_range,
):
    battle = BattleState()
    mover = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    target.position = Position(
        9.0,
        10.0 + max_edge_range + target.get_collision_radius() + 0.005,
    )
    target._native_target_distance_discount_sq_units = 400**2
    mover.target_id = target.id

    raw_edge_distance = (
        mover.position.distance_to(target.position)
        - target.get_collision_radius()
    )
    assert raw_edge_distance > max_edge_range
    assert (
        mover.native_target_distance_to(target)
        - target.get_collision_radius()
    ) < max_edge_range

    mover.mechanics[0].on_tick(mover, 1)

    if card_name == "Bandit":
        assert mover._bandit_charging
    else:
        assert mover._mk_leap_phase == "charging"


def test_diagonal_bandit_and_mega_knight_endpoints_use_native_logic_vectors():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    bandit = _spawn_one(battle, "Bandit", 0, Position(9.0, 10.0))
    mega_knight = _spawn_one(battle, "MegaKnight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(12.0, 14.0))

    # The target lies on a 3-4-5 vector. Bandit stops 1.25 tiles from its
    # center; Mega Knight stops at its 1.2 range plus the 0.5 target radius.
    bandit.mechanics[0]._launch_dash(bandit, target)
    mega_knight.mechanics[0]._launch_leap(mega_knight, target, 5.0)

    assert bandit._bandit_dash_target == (11.25, 13.0)
    assert mega_knight._mk_leap_target == (10.98, 12.64)


def test_mega_knight_uses_data_scaled_deploy_and_jump_damage_once():
    battle = BattleState(rng=random.Random(37))
    ground = _spawn_one(battle, "Knight", 1, Position(4.5, 12.0))
    air = _spawn_one(battle, "Bats", 1, Position(4.0, 12.0))
    ground_hp = ground.hitpoints
    ground.attack_cooldown = 0.0
    ground._has_attacked_once = True
    air_hp = air.hitpoints
    mega_knight = _spawn_one(battle, "MegaKnight", 0, Position(3.5, 12.0))
    assert ground_hp - ground.hitpoints == mega_knight.card_stats.get_scaled_stat(168)
    assert ground.position.x == 4.5
    for _ in range(9):
        ground.update_movement_component(battle.dt, battle)
    assert ground.position.x == pytest.approx(5.4)
    assert not ground._has_attacked_once
    assert air.hitpoints == air_hp
    assert ground.stun_timer == 0.0
    ground.take_damage(ground.hitpoints)

    # Mega Knight's native minimum is likewise measured edge to edge.
    jump_target = _spawn_one(battle, "Knight", 1, Position(3.5, 16.8))
    jump_hp = jump_target.hitpoints
    mega_knight.target_id = jump_target.id
    mega_knight.mechanics[0].on_tick(mega_knight, 33)
    assert mega_knight._special_move_active
    assert mega_knight._mk_leap_phase == "charging"
    assert mega_knight.mechanics[0].leap_duration_ms == 900
    assert mega_knight.mechanics[0].airborne_duration_ms == 800
    assert mega_knight.mechanics[0].landing_duration_ms == 300
    assert jump_target.hitpoints == jump_hp
    mega_knight_hp = mega_knight.hitpoints
    mega_knight.take_damage(1)
    mega_knight.apply_stun(1.0)
    assert mega_knight.hitpoints == mega_knight_hp - 1
    assert mega_knight.stun_timer == 1.0

    # Unlike Bandit, stun cannot cancel an initiated Mega Knight jump. It
    # freezes the anticipation in place, then the retained wind-up resumes
    # once the stun expires.
    progress_before_stun = mega_knight._mk_leap_progress
    for _ in range(20):
        mega_knight.update(battle.dt, battle)
    assert mega_knight._mk_leap_phase == "charging"
    assert mega_knight._mk_leap_progress == progress_before_stun

    for _ in range(40):
        mega_knight.update(battle.dt, battle)
        if mega_knight._mk_leap_phase == "airborne":
            break
    assert mega_knight._mk_leap_phase == "airborne"
    mega_knight.apply_stun(1.0)
    for _ in range(120):
        mega_knight.update(battle.dt, battle)
        if not mega_knight._special_move_active:
            break
    assert jump_hp - jump_target.hitpoints == mega_knight.card_stats.get_scaled_stat(210)
    assert mega_knight.stun_timer == 0.0


@pytest.mark.parametrize("fast_path", [False, True])
def test_committed_mega_knight_leap_hits_midair_cloaked_archer_queen(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    mega_knight = _spawn_one(
        battle,
        "MegaKnight",
        0,
        Position(9.0, 10.0),
    )
    queen = _spawn_one(
        battle,
        "ArcherQueen",
        1,
        Position(9.0, 14.5),
    )
    mega_knight.speed = 0.0
    queen.speed = 0.0
    mega_knight.target_id = queen.id
    mechanic = next(
        item
        for item in mega_knight.mechanics
        if type(item).__name__ == "MegaKnightSlam"
    )
    mechanic._launch_leap(
        mega_knight,
        queen,
        mega_knight.position.distance_to(queen.position),
    )
    battle.players[1].elixir = 10.0
    assert battle.activate_champion_ability(1)
    hitpoints_before = queen.hitpoints

    for _ in range(4):
        battle.step()
    assert queen._stealth_until > int(battle.time * 1000)
    assert not queen.is_targetable_by(mega_knight.player_id)
    assert mega_knight._mk_leap_phase == "airborne"

    for _ in range(12):
        battle.step()

    assert mega_knight._mk_leap_phase == "landing"
    assert hitpoints_before - queen.hitpoints == mega_knight.card_stats.get_scaled_stat(
        mechanic.jump_damage
    )


@pytest.mark.parametrize("edge_distance", [3.6, 4.9])
def test_mega_knight_jump_has_fixed_flight_landing_lock_and_pushback(edge_distance):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    mega_knight = _spawn_one(battle, "MegaKnight", 0, Position(3.5, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(3.5, 10.0))
    target.position = Position(
        3.5,
        10.0 + edge_distance + target.get_collision_radius(),
    )
    mechanic = mega_knight.mechanics[0]
    hp_before = target.hitpoints
    target_before = Position(target.position.x, target.position.y)

    mechanic._launch_leap(
        mega_knight,
        target,
        mega_knight.position.distance_to(target.position),
    )

    assert mega_knight._mk_leap_travel_duration_ms == 800
    for _ in range(15):
        mechanic.on_movement_tick(mega_knight, 50)
    assert mega_knight._mk_leap_phase == "airborne"
    assert target.hitpoints == hp_before

    mechanic.on_movement_tick(mega_knight, 50)
    assert mega_knight._mk_leap_phase == "landing"
    assert hp_before - target.hitpoints == mega_knight.card_stats.get_scaled_stat(210)
    assert target.position == target_before
    target.update_movement_component(battle.dt, battle)
    assert target_before.distance_to(target.position) == pytest.approx(0.2)
    for _ in range(8):
        target.update_movement_component(battle.dt, battle)
    assert target_before.distance_to(target.position) == pytest.approx(0.9)

    for _ in range(5):
        mechanic.on_movement_tick(mega_knight, 50)
    assert mega_knight._mk_leap_phase == "landing"
    mechanic.on_movement_tick(mega_knight, 50)
    assert mega_knight._mk_leap_phase is None
    assert not mega_knight._special_move_active


def test_mega_knight_jump_uses_wider_landing_shockwave_not_mace_splash():
    battle = BattleState(rng=random.Random(370))
    battle.entities.clear()
    battle.next_entity_id = 1
    mega_knight = _spawn_one(battle, "MegaKnight", 0, Position(9.0, 12.0))
    edge_target = _spawn_one(battle, "Knight", 1, Position(11.6, 12.0))
    hp_before = edge_target.hitpoints
    mechanic = next(
        mechanic
        for mechanic in mega_knight.mechanics
        if type(mechanic).__name__ == "MegaKnightSlam"
    )

    assert mega_knight.card_stats.area_damage_radius / 1000.0 == 1.3
    assert mechanic.slam_radius == 2.2
    mechanic._slam(
        mega_knight,
        mechanic.slam_radius,
        mechanic._scaled_damage(mega_knight, mechanic.jump_damage),
    )

    assert hp_before - edge_target.hitpoints == mega_knight.card_stats.get_scaled_stat(210)


def test_mega_knight_keeps_native_character_spawn_pushback_payload():
    battle = BattleState()
    mega_knight = battle.card_loader.get_card("MegaKnight")
    char_data = mega_knight._raw_entry["summonCharacterData"]
    mechanic = next(
        item
        for item in battle.card_loader.get_card_definition("MegaKnight").mechanics
        if type(item).__name__ == "SpawnPushback"
    )

    assert char_data["spawnPushback"] == 1000
    assert char_data["spawnPushbackRadius"] == 1000
    assert mechanic.distance_tiles == 1.0
    assert mechanic.radius_tiles == 1.0


def test_spawn_pushback_is_data_driven_and_pushes_without_damage():
    from clasher.factory.mechanic_detector import detect_mechanics_from_data

    mechanics = detect_mechanics_from_data(
        {
            "name": "SyntheticSpawner",
            "summonCharacterData": {
                "spawnPushback": 750,
                "spawnPushbackRadius": 1000,
                "attacksGround": True,
                "attacksAir": False,
            },
        }
    )
    mechanic = next(item for item in mechanics if type(item).__name__ == "SpawnPushback")

    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn_one(battle, "Knight", 0, Position(9.0, 12.0))
    nearby = _spawn_one(battle, "Knight", 1, Position(10.4, 12.0))
    heavyweight = _spawn_one(battle, "Giant", 1, Position(7.3, 12.0))
    river_jumper = _spawn_one(battle, "HogRider", 1, Position(9.0, 13.4))
    flying = _spawn_one(battle, "BabyDragon", 1, Position(9.0, 10.6))
    outside = _spawn_one(battle, "Knight", 1, Position(10.6, 12.0))
    river_jumper._river_jump_active = True
    nearby_hp = nearby.hitpoints
    heavyweight_hp = heavyweight.hitpoints
    river_jumper_hp = river_jumper.hitpoints
    flying_hp = flying.hitpoints
    outside_hp = outside.hitpoints

    mechanic.on_spawn(source)

    assert nearby.hitpoints == nearby_hp
    assert heavyweight.hitpoints == heavyweight_hp
    assert river_jumper.hitpoints == river_jumper_hp
    assert flying.hitpoints == flying_hp
    assert outside.hitpoints == outside_hp
    assert nearby._knockback_target is not None
    assert nearby.position.distance_to(nearby._knockback_target) == pytest.approx(0.75)
    # Character SpawnPushback uses the native pushback-all override, and its
    # plane predicate reads static FlyingHeight rather than the current jump
    # elevation. A heavyweight and a ground troop mid-river-jump both move.
    assert heavyweight._knockback_target is not None
    assert river_jumper._knockback_target is not None
    assert flying._knockback_target is None
    assert outside._knockback_target is None


def test_mega_knight_leap_stays_ground_target_but_rises_above_ground_effects():
    from clasher.spells import SPELL_REGISTRY
    from clasher.unit_traits import is_above_ground_surface, is_airborne_target

    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    mega_knight = _spawn_one(battle, "MegaKnight", 1, Position(9.0, 12.0))
    hog = _spawn_one(battle, "HogRider", 1, Position(4.0, 12.0))
    mega_knight._mk_leap_phase = "airborne"
    hog._river_jump_active = True

    assert not is_airborne_target(mega_knight)
    assert is_above_ground_surface(mega_knight)
    assert is_airborne_target(hog)
    assert is_above_ground_surface(hog)

    assert SPELL_REGISTRY["Log"].cast(battle, 0, Position(9.0, 10.0))
    rolling = max(
        (
            entity
            for entity in battle.entities.values()
            if type(entity).__name__ == "RollingProjectile"
        ),
        key=lambda entity: entity.id,
    )
    mega_knight_hp = mega_knight.hitpoints
    rolling.position = Position(mega_knight.position.x, mega_knight.position.y)
    rolling._deal_rolling_damage(battle)
    assert mega_knight.hitpoints == mega_knight_hp

    hog_hp = hog.hitpoints
    rolling.position = Position(hog.position.x, hog.position.y)
    rolling._deal_rolling_damage(battle)
    assert hog.hitpoints == hog_hp


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize(
    ("attacker_name", "attacker_type", "hits_jumper"),
    (
        ("Cannon", Building, False),
        ("Xbow", Building, False),
        ("Musketeer", Troop, True),
    ),
)
def test_committed_direct_projectile_survives_target_river_jump(
    fast_path,
    attacker_name,
    attacker_type,
    hits_jumper,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker_stats = battle.card_loader.get_card(attacker_name)
    assert attacker_stats is not None
    attacker = battle._spawn_entity(
        attacker_type,
        Position(9.0, 10.0),
        0,
        attacker_stats,
    )
    attacker.deploy_delay_remaining = 0.0
    attacker.placement_pending = False
    hog = _spawn_one(battle, "HogRider", 1, Position(9.0, 14.0))
    attacker._create_projectile(hog, battle)
    projectile = max(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Projectile)
        ),
        key=lambda entity: entity.id,
    )
    hitpoints_before = hog.hitpoints

    # Native Cannon capture 2934 confirms a committed direct hit survives
    # the target's jump. The projectile retains its original target-plane mask.
    hog._river_jump_active = True
    for _ in range(20):
        projectile.update(battle.dt, battle)
        if not projectile.is_alive:
            break

    assert not projectile.is_alive
    assert projectile.hits_air is hits_jumper
    assert hitpoints_before - hog.hitpoints == attacker.damage


def test_bowler_pierces_but_cannot_push_heavy_troops():
    battle = BattleState()
    bowler = _spawn_one(battle, "Bowler", 0, Position(9.0, 10.0))
    prince = _spawn_one(battle, "Prince", 1, Position(9.0, 14.0))
    knight = _spawn_one(battle, "Knight", 1, Position(9.0, 16.0))
    prince_start = Position(prince.position.x, prince.position.y)
    knight_start = Position(knight.position.x, knight.position.y)

    bowler.attack_cooldown = 0.0
    bowler.update(battle.dt, battle)
    rolling = max(
        (
            entity
            for entity in battle.entities.values()
            if type(entity).__name__ == "RollingProjectile"
        ),
        key=lambda entity: entity.id,
    )
    assert rolling.source_entity is bowler
    assert rolling.primary_target is prince
    for _ in range(120):
        rolling.update(battle.dt, battle)
        if not rolling.is_alive:
            break

    assert prince.hitpoints < prince.max_hitpoints
    assert knight.hitpoints < knight.max_hitpoints
    assert prince.position == prince_start
    assert knight.position == knight_start
    assert knight.forced_movement_active
    knight.update_movement_component(battle.dt, battle)
    assert knight.position != knight_start


def test_rolling_troop_projectile_uses_serialized_range():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, "Bowler", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    attacker.card_stats = copy.deepcopy(attacker.card_stats)
    attacker.card_stats.projectile_data["projectileRange"] = 4250

    attacker._create_projectile(target, battle)

    rolling = max(
        (
            entity
            for entity in battle.entities.values()
            if type(entity).__name__ == "RollingProjectile"
        ),
        key=lambda entity: entity.id,
    )
    assert rolling.projectile_range == 4.25


def test_projectile_crown_payload_uses_final_special_damage_for_every_shape():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, "Bowler", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    attacker.card_stats = copy.deepcopy(attacker.card_stats)
    attacker.card_stats.damage_special = 1000
    special_damage = attacker.card_stats.scaled_damage_special
    attacker.is_charging = True
    scaling = CrownTowerScaling(damage_multiplier=0.4)
    scaling.on_attach(attacker)
    attacker.mechanics.append(scaling)

    attacker._create_projectile(target, battle)

    rolling = max(
        (
            entity
            for entity in battle.entities.values()
            if type(entity).__name__ == "RollingProjectile"
        ),
        key=lambda entity: entity.id,
    )
    assert rolling.damage == special_damage
    assert rolling.crown_tower_damage == int(special_damage * 0.4)


def test_diagonal_bowler_boulder_uses_circular_projectile_radius():
    battle = BattleState()
    bowler = _spawn_one(battle, "Bowler", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(12.0, 13.0))
    lateral = _spawn_one(battle, "Knight", 1, Position(11.0, 14.0))
    lateral_before = lateral.hitpoints

    bowler.target_id = primary.id
    bowler.attack_cooldown = 0.0
    bowler.update(battle.dt, battle)
    rolling = max(
        (entity for entity in battle.entities.values() if type(entity).__name__ == "RollingProjectile"),
        key=lambda entity: entity.id,
    )
    rolling.position = Position(primary.position.x, primary.position.y)
    rolling._deal_rolling_damage(battle)

    assert lateral.hitpoints < lateral_before


def test_diagonal_bowler_launch_and_knockback_use_native_logic_vectors():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    bowler = _spawn_one(battle, "Bowler", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(12.0, 14.0))
    victim = _spawn_one(battle, "Knight", 1, Position(8.0, 9.0))

    bowler._create_projectile(primary, battle)
    rolling = max(
        (
            entity
            for entity in battle.entities.values()
            if type(entity).__name__ == "RollingProjectile"
        ),
        key=lambda entity: entity.id,
    )

    # The 3-4-5 aim vector converts Bowler's one-tile muzzle radius and
    # one-tile push to exact 600/800 logic-unit endpoint components. The
    # movement component then consumes the native 25-work push curve.
    assert rolling.position == Position(9.6, 10.8)
    rolling._apply_knockback(victim, battle)
    assert victim.position == Position(8.0, 9.0)
    victim.update_movement_component(battle.dt, battle)
    push_delta = movement_component_vector_logic_units(600, 800, 200)
    assert victim.position == Position(
        8.0 + logic_units_to_tiles(push_delta[0]),
        9.0 + logic_units_to_tiles(push_delta[1]),
    )
    for _ in range(8):
        victim.update_movement_component(battle.dt, battle)
    assert victim.position == Position(8.536, 9.715)
    assert victim.position.x * 1000 == round(victim.position.x * 1000)
    assert victim.position.y * 1000 == round(victim.position.y * 1000)


def test_bowler_uses_physical_radius_while_rolling_and_damage_radius_at_endpoint():
    battle = BattleState()
    bowler = _spawn_one(battle, "Bowler", 0, Position(9.0, 10.0))
    primary = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    path_edge = _spawn_one(battle, "Knight", 1, Position(10.6, 14.0))
    endpoint_edge = _spawn_one(battle, "Knight", 1, Position(10.6, 18.5))
    path_edge.position = Position(10.6, 14.0)
    endpoint_edge.position = Position(10.6, 18.5)
    hp_before = (path_edge.hitpoints, endpoint_edge.hitpoints)

    bowler.target_id = primary.id
    bowler.attack_cooldown = 0.0
    bowler.update(battle.dt, battle)
    rolling = max(
        (
            entity
            for entity in battle.entities.values()
            if type(entity).__name__ == "RollingProjectile"
        ),
        key=lambda entity: entity.id,
    )
    assert rolling.rolling_radius == 1.0
    assert rolling.impact_radius == 1.8

    rolling.position = Position(9.0, 14.0)
    rolling._deal_rolling_damage(battle)
    assert path_edge.hitpoints == hp_before[0]

    rolling.position = Position(9.0, 18.4)
    rolling.distance_traveled = rolling.projectile_range - 0.1
    rolling.update(1.0, battle)
    assert endpoint_edge.hitpoints == hp_before[1] - bowler.damage


def _consume_collision_vectors(battle, *troops):
    battle._resolve_troop_collisions()
    for troop in troops:
        troop.begin_movement_tick()
        troop.finish_movement_tick(battle)


def _prepare_native_avoidance_mover(troop, target, facing):
    troop._movement_target_id = target.id
    troop._facing_x_units, troop._facing_y_units = facing


def test_native_avoidance_steers_head_on_troops_before_body_contact():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    lower = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    upper = _spawn_one(battle, "Knight", 1, Position(9.0, 11.2))
    lower.position = Position(9.0, 10.0)
    upper.position = Position(9.0, 11.2)
    # Keep the collision encounter outside attack reach so route goals
    # remain ahead of both bodies under the corrected radius calculation.
    lower.range = upper.range = 0.1
    _prepare_native_avoidance_mover(lower, upper, (0, 256))
    _prepare_native_avoidance_mover(upper, lower, (0, -256))

    assert lower.position.distance_to(upper.position) > (
        lower.get_collision_radius() + upper.get_collision_radius()
    )

    lower._update_native_avoidance(battle)
    upper._update_native_avoidance(battle)
    lower._move_towards_target(upper, battle.dt, battle)
    upper._move_towards_target(lower, battle.dt, battle)

    # A centered encounter selects the native negative side. The same signed
    # avoidance applied to opposite intended directions moves the bodies onto
    # opposite world-space sides.
    assert lower._native_avoidance == -190
    assert upper._native_avoidance == -190
    assert lower.position.x < 9.0
    assert upper.position.x > 9.0
    assert lower.position.distance_to(upper.position) > (
        lower.get_collision_radius() + upper.get_collision_radius()
    )


def test_native_avoidance_rotation_uses_the_clients_fixed_point_sequence():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))

    knight._native_avoidance = -190

    # Each product is arithmetically shifted before the two terms are added,
    # then the result is normalized back to the intended movement magnitude.
    assert knight._apply_native_avoidance(0, 60, 60) == (-57, 19)
    assert knight._apply_native_avoidance(0, -60, 60) == (57, -20)


def test_native_avoidance_ignores_overtaking_troops_with_parallel_direction():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    rear = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    front = _spawn_one(battle, "Knight", 0, Position(9.0, 11.2))
    _prepare_native_avoidance_mover(rear, front, (0, 256))
    _prepare_native_avoidance_mover(front, rear, (0, 256))

    rear._update_native_avoidance(battle)

    assert rear._native_avoidance == 0


def test_native_avoidance_treats_stopped_movers_as_obstacles():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    mover = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    stopped = _spawn_one(battle, "Knight", 1, Position(9.0, 11.2))
    _prepare_native_avoidance_mover(mover, stopped, (0, 256))
    stopped._movement_target_id = None
    stopped._facing_x_units, stopped._facing_y_units = (0, 256)

    mover._update_native_avoidance(battle)

    assert mover._native_avoidance == -190


def test_native_avoidance_scan_continues_while_pushback_transport_is_installed():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    mover = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    other = _spawn_one(battle, "Knight", 1, Position(9.0, 11.2))
    _prepare_native_avoidance_mover(mover, other, (0, 256))
    _prepare_native_avoidance_mover(other, mover, (0, -256))
    mover.forced_movement_active = True
    mover._knockback_target = Position(9.0, 9.0)

    mover._update_native_avoidance(battle)

    # doPushback has its own active byte and does not toggle the movement
    # component's stop byte, so avoidance still updates for the post-push path.
    assert mover._native_avoidance == -190


def test_native_avoidance_only_compares_objects_on_the_same_height_plane():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    ground = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    air = _spawn_one(battle, "Bats", 1, Position(9.0, 11.2))
    second_air = _spawn_one(battle, "Bats", 0, Position(9.0, 12.4))
    ground.position = Position(9.0, 10.0)
    air.position = Position(9.0, 11.2)
    second_air.position = Position(9.0, 12.4)
    _prepare_native_avoidance_mover(ground, air, (0, 256))
    _prepare_native_avoidance_mover(air, second_air, (0, 256))
    _prepare_native_avoidance_mover(second_air, air, (0, -256))

    ground._update_native_avoidance(battle)
    air._update_native_avoidance(battle)

    assert ground._native_avoidance == 0
    assert air._native_avoidance == -190


def test_hovering_avoidance_uses_air_body_collision_plane():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    ghost = _spawn_one(battle, "RoyalGhost", 0, Position(9.0, 10.0))
    bats = _spawn_one(battle, "Bats", 1, Position(9.0, 11.2))
    knight = _spawn_one(battle, "Knight", 1, Position(20.0, 20.0))
    _prepare_native_avoidance_mover(ghost, bats, (0, 256))
    _prepare_native_avoidance_mover(bats, ghost, (0, -256))

    ghost._update_native_avoidance(battle)

    assert ghost._native_avoidance == -190

    ghost._native_avoidance = 0
    bats.position = Position(20.0, 20.0)
    knight.position = Position(9.0, 11.2)
    _prepare_native_avoidance_mover(ghost, knight, (0, 256))
    _prepare_native_avoidance_mover(knight, ghost, (0, -256))

    ghost._update_native_avoidance(battle)

    assert ghost._native_avoidance == 0


def test_native_avoidance_chargers_plow_through_lighter_but_yield_to_heavier_units():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    prince = _spawn_one(battle, "Prince", 0, Position(9.0, 10.0))
    skeleton = _spawn_one(battle, "Skeletons", 1, Position(9.0, 11.2))
    giant = _spawn_one(battle, "Giant", 1, Position(9.0, 11.2))
    prince.position = Position(9.0, 10.0)
    skeleton.position = Position(9.0, 11.2)
    giant.position = Position(20.0, 20.0)
    prince.is_charging = True
    _prepare_native_avoidance_mover(prince, skeleton, (0, 256))
    _prepare_native_avoidance_mover(skeleton, prince, (0, -256))
    _prepare_native_avoidance_mover(giant, prince, (0, -256))

    assert unit_mass(prince.card_stats) > unit_mass(skeleton.card_stats)
    prince._update_native_avoidance(battle)
    assert prince._native_avoidance == 0

    skeleton.position = Position(20.0, 20.0)
    giant.position = Position(9.0, 11.2)
    prince._movement_target_id = giant.id
    prince._update_native_avoidance(battle)

    assert unit_mass(prince.card_stats) <= unit_mass(giant.card_stats)
    assert prince._native_avoidance == -190


def test_native_avoidance_static_objects_adjust_an_existing_turn_then_decay():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    mover = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 11.2),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    _prepare_native_avoidance_mover(mover, target, (0, 256))
    target._movement_target_id = target.id
    target._facing_x_units, target._facing_y_units = (0, 256)
    mover._native_avoidance = 100

    mover._update_native_avoidance(battle)
    assert mover._native_avoidance == 70

    cannon.position = Position(20.0, 20.0)
    mover._update_native_avoidance(battle)
    assert mover._native_avoidance == 60


def test_native_avoidance_inherits_an_avoiding_movers_turn_side():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    mover = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    other = _spawn_one(battle, "Knight", 1, Position(8.9, 11.2))
    _prepare_native_avoidance_mover(mover, other, (0, 256))
    _prepare_native_avoidance_mover(other, mover, (0, -256))
    other._native_avoidance = 50

    mover._update_native_avoidance(battle)

    # The geometric cross product would choose the negative side here. A
    # moving obstacle already turning positive overrides that local choice.
    assert mover._native_avoidance == 190


def test_native_avoidance_preserves_intended_charge_work_not_rotated_vector_length():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    prince = _spawn_one(battle, "Prince", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    prince._native_avoidance = -190
    prince.distance_traveled = 0.0

    prince._move_towards_target(target, battle.dt, battle)

    expected_work = speed_work_for_duration(prince.speed, battle.dt)
    assert prince.distance_traveled == logic_units_to_tiles(expected_work)
    assert prince.position.x < 9.0


def test_river_jump_applies_same_plane_avoidance_but_mega_knight_jump_clears_it():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    hog = _spawn_one(battle, "HogRider", 0, Position(9.0, 10.0))
    bats = _spawn_one(battle, "Bats", 1, Position(9.0, 11.2))
    mega_knight = _spawn_one(battle, "MegaKnight", 0, Position(15.0, 10.0))
    hog._river_jump_origin = Position(9.0, 10.0)
    hog._river_jump_target = Position(9.0, 13.0)
    hog._river_jump_elapsed = 0.0
    hog._river_jump_duration = 1.0
    hog._river_jump_active = True
    hog._special_move_active = True
    _prepare_native_avoidance_mover(hog, bats, (0, 256))
    _prepare_native_avoidance_mover(bats, hog, (0, -256))

    hog._update_native_avoidance(battle)
    hog._update_river_jump(battle.dt, battle)

    assert hog._native_avoidance == -190
    assert hog.position.x < 9.0

    mega_knight._native_avoidance = 190
    mega_knight._mk_leap_phase = "airborne"
    mega_knight._update_native_avoidance(battle)
    assert mega_knight._native_avoidance == 0


def test_avoiding_air_troops_remain_clipped_to_the_native_arena_boundary():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    bats = _spawn_one(battle, "Bats", 0, Position(17.7, 10.0))
    target = _spawn_one(battle, "Bats", 1, Position(17.7, 14.0))
    bats.position = Position(17.7, 10.0)
    target.position = Position(17.7, 14.0)
    bats._native_avoidance = 190

    bats._move_towards_target(target, battle.dt, battle)

    # Native movement clips moving centers to [0, size - 0.001]; the
    # quarter-tile inset applies only to spawning.
    assert 17.75 < bats.position.x <= battle.arena.width - 0.001
    assert 0.0 <= bats.position.y <= battle.arena.height - 0.001


@pytest.mark.parametrize("fast_path", (False, True))
def test_avoiding_ground_spawn_egress_stays_clipped_to_native_boundary(
    fast_path,
):
    battle = BattleState()
    battle.fast_path = fast_path
    battle._refresh_fast_path_caches()
    gang = battle.card_loader.get_card("GoblinGang")
    assert gang is not None
    battle._spawn_troop(Position(4.5, 0.5), 1, gang)

    # The right stab Goblin deploys on the outer center boundary. Its first
    # avoidance turn points partly out of the arena while the terrain beneath
    # its center is still unwalkable, so the tile-map boundary clip must run
    # before the blocked-point egress exception.
    for _ in range(20):
        battle.step()
    # Deliberately retain a heading toward the nearby enemy tower. This
    # exercises boundary clipping under avoidance independently of whether
    # target acquisition replaces the direction on this movement frame.
    for entity in battle.entities.values():
        if isinstance(entity, Troop):
            target = entity.get_nearest_target(battle.entities)
            assert target is not None
            entity.face_towards(target.position)
    # Exercise the clip with an existing turn. Deploying friendly neighbors
    # keep their facing and no longer manufacture an opposing-traffic turn.
    right_before_step = max(
        (entity for entity in battle.entities.values()
         if isinstance(entity, Troop) and entity.card_stats.name == "Goblin_Stab"),
        key=lambda entity: entity.position.x,
    )
    right_before_step._native_avoidance = 200
    battle.step()

    stab_goblins = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Goblin_Stab"
    ]
    assert len(stab_goblins) == 3
    right = max(stab_goblins, key=lambda entity: entity.position.x)
    assert right._native_avoidance == 190
    # The target geometry affects lateral movement; the boundary invariant
    # is clipping Y while allowing the outward egress step along X.
    assert right.position.x > 5.5
    assert 0.0 <= right.position.y < 0.25
    # Moving bodies follow native movement bounds; the spawn-placement
    # predicate (is_entity_position_in_bounds) keeps its quarter-tile inset.
    assert all(
        0.0 <= entity.position.x <= battle.arena.width - 0.001
        and 0.0 <= entity.position.y <= battle.arena.height - 0.001
        for entity in stab_goblins
    )


def test_collision_pressure_caps_overlap_then_uses_directional_mass_ratio():
    battle = BattleState()
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    golem = _spawn_one(battle, "Golem", 0, Position(9.5, 10.0))
    knight.position = Position(9.0, 10.0)
    golem.position = Position(9.5, 10.0)
    _consume_collision_vectors(battle, knight, golem)

    # Overlap is first capped at 0.3. Knight's mass ratio reaches the ordinary
    # 0.15 movement-vector cap; Golem receives 0.3 * 6/20 + 0.001.
    assert 9.0 - knight.position.x == pytest.approx(0.15)
    assert golem.position.x - 9.5 == pytest.approx(0.091)


def test_multiple_collision_contacts_are_averaged_before_the_native_cap():
    battle = BattleState()
    center = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    left = _spawn_one(battle, "Skeletons", 0, Position(8.4, 10.0))
    right = _spawn_one(battle, "Skeletons", 0, Position(9.6, 10.0))
    center.position = Position(9.0, 10.0)
    left.position = Position(8.4, 10.0)
    right.position = Position(9.6, 10.0)

    _consume_collision_vectors(battle, center, left, right)

    assert center.position == Position(9.0, 10.0)
    assert left.position.x < 8.4
    assert right.position.x > 9.6


def test_ground_troops_receive_static_building_collision_pressure():
    battle = BattleState()
    tower = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building) and entity.player_id == 0
    )
    knight = _spawn_one(
        battle,
        "Knight",
        0,
        Position(tower.position.x, tower.position.y),
    )
    knight.position = Position(tower.position.x, tower.position.y)

    _consume_collision_vectors(battle, knight)

    # Native exact-center static collision sends the owner-zero mover backward.
    assert knight.position.y == pytest.approx(tower.position.y - 0.15)


def test_building_occupancy_uses_exact_deployment_and_native_movement_radii():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    cannon_stats = battle.card_loader.get_card("Cannon")
    mega_knight_stats = battle.card_loader.get_card("MegaKnight")
    assert cannon_stats is not None
    assert mega_knight_stats is not None
    cannon = battle._spawn_entity(Building, Position(9.0, 10.0), 0, cannon_stats)
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False

    assert cannon.get_collision_radius() == 0.6
    assert mega_knight_stats.collision_radius == 0.75

    # Deployment uses the complete 0.75 troop radius; exact tangency is not
    # overlap. Active movement uses the native static-object cap of 0.5.
    assert battle.is_position_occupied_by_building(
        Position(10.349, 10.0),
        mover_radius=mega_knight_stats.collision_radius,
    )
    assert not battle.is_position_occupied_by_building(
        Position(10.35, 10.0),
        mover_radius=mega_knight_stats.collision_radius,
    )
    assert battle.is_position_occupied_by_building(
        Position(10.099, 10.0),
        mover_radius=mega_knight_stats.collision_radius,
        movement_collision=True,
    )
    assert not battle.is_position_occupied_by_building(
        Position(10.1, 10.0),
        mover_radius=mega_knight_stats.collision_radius,
        movement_collision=True,
    )


def test_subnanotile_center_collision_fallback_rotates_with_player_perspective():
    lower = BattleState()
    lower_a = _spawn_one(lower, "Knight", 0, Position(9.0, 10.0))
    lower_b = _spawn_one(lower, "Skeletons", 1, Position(9.0, 10.0))
    lower_a.position = Position(9.0, 10.0)
    lower_b.position = Position(9.0 - 5e-13, 10.0)

    upper = BattleState()
    upper_a = _spawn_one(upper, "Knight", 1, Position(9.0, 22.0))
    upper_b = _spawn_one(upper, "Skeletons", 0, Position(9.0, 22.0))
    upper_a.position = Position(9.0, 22.0)
    upper_b.position = Position(9.0, 22.0)

    _consume_collision_vectors(lower, lower_a, lower_b)
    _consume_collision_vectors(upper, upper_a, upper_b)

    assert lower_a.position.x == pytest.approx(18.0 - upper_a.position.x)
    assert lower_a.position.y == pytest.approx(32.0 - upper_a.position.y)
    assert lower_b.position.x == pytest.approx(18.0 - upper_b.position.x)
    assert lower_b.position.y == pytest.approx(32.0 - upper_b.position.y)


def test_collision_pass_stabilizes_subnanotile_mirror_drift_between_ticks():
    lower = BattleState()
    upper = BattleState()
    lower_a = _spawn_one(lower, "Skeletons", 0, Position(9.0, 4.5))
    lower_b = _spawn_one(lower, "Skeletons", 0, Position(9.0, 4.5))
    upper_a = _spawn_one(upper, "Skeletons", 1, Position(9.0, 27.5))
    upper_b = _spawn_one(upper, "Skeletons", 1, Position(9.0, 27.5))
    lower_a.position = Position(8.995236868496134, 4.424275293516382)
    lower_b.position = Position(8.97287946458287, 4.37662836714382)
    upper_a.position = Position(9.004763131503859, 27.575724706483623)
    upper_b.position = Position(9.02712053541713, 27.62337163285618)

    for _ in range(20):
        _consume_collision_vectors(lower, lower_a, lower_b)
        _consume_collision_vectors(upper, upper_a, upper_b)

    assert lower_a.position.x == pytest.approx(18.0 - upper_a.position.x, abs=1e-9)
    assert lower_a.position.y == pytest.approx(32.0 - upper_a.position.y, abs=1e-9)
    assert lower_b.position.x == pytest.approx(18.0 - upper_b.position.x, abs=1e-9)
    assert lower_b.position.y == pytest.approx(32.0 - upper_b.position.y, abs=1e-9)


def test_deploying_spawn_payloads_are_targetable_and_collidable():
    battle = BattleState()
    skeleton_stats = battle.card_loader.get_card("Skeletons")
    assert skeleton_stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(Position(9.0, 10.0), 1, skeleton_stats)
    battle._spawn_unit_at_position(Position(9.0, 10.0), 1, skeleton_stats)
    skeletons = [battle.entities[entity_id] for entity_id in battle.entities.keys() - before]
    start_positions = [
        Position(entity.position.x, entity.position.y) for entity in skeletons
    ]
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 9.0))

    assert all(entity.placement_pending for entity in skeletons)
    assert all(entity.is_targetable_by(0) for entity in skeletons)
    assert knight.get_nearest_target(battle.entities) in skeletons

    _consume_collision_vectors(battle, *skeletons, knight)

    assert [entity.position for entity in skeletons] != start_positions


@pytest.mark.parametrize("card_name", ["RoyalGhost", "MegaMinion"])
def test_collision_separation_keeps_centers_on_outermost_arena_tiles(card_name):
    battle = BattleState()
    first = _spawn_one(battle, card_name, 0, Position(1.0, 10.0))
    second = _spawn_one(battle, card_name, 0, Position(1.0, 10.0))
    first.position = Position(0.3, 10.0)
    second.position = Position(0.4, 10.0)

    _consume_collision_vectors(battle, first, second)

    for troop in (first, second):
        assert 0.0 <= troop.position.x <= battle.arena.width - 0.001
        assert 0.0 <= troop.position.y <= battle.arena.height - 0.001
    # LogicTileMap::moveObject lets moving centers use the whole outer 500-unit
    # cell (0..17999 on x), so neither body is pinned to the spawn inset.
    assert first.position.x == pytest.approx(0.15)
    assert second.position.x - 0.4 == pytest.approx(0.15)


@pytest.mark.parametrize("fast_path", [False, True])
def test_air_units_collide_with_air_but_not_ground_units(fast_path):
    battle = BattleState(fast_path=fast_path)
    balloon = _spawn_one(battle, "Balloon", 0, Position(9.0, 10.0))
    mega_minion = _spawn_one(battle, "MegaMinion", 0, Position(9.2, 10.0))
    knight = _spawn_one(battle, "Knight", 0, Position(9.1, 10.0))
    balloon.position = Position(9.0, 10.0)
    mega_minion.position = Position(9.2, 10.0)
    knight.position = Position(9.1, 10.0)
    knight_start = Position(knight.position.x, knight.position.y)

    _consume_collision_vectors(battle, balloon, mega_minion, knight)

    assert balloon.position.x < 9.0
    assert mega_minion.position.x > 9.2
    assert knight.position == knight_start


@pytest.mark.parametrize("fast_path", [False, True])
def test_hovering_troops_use_air_body_collision_but_remain_ground_targets(
    fast_path,
):
    ground_battle = BattleState(fast_path=fast_path)
    ground_battle.entities.clear()
    ground_battle.next_entity_id = 1
    ground_ghost = _spawn_one(
        ground_battle,
        "RoyalGhost",
        1,
        Position(9.0, 10.0),
    )
    ground_ghost._stealth_until = 0
    knight = _spawn_one(
        ground_battle,
        "Knight",
        0,
        Position(9.2, 10.0),
    )
    ground_starts = (
        Position(ground_ghost.position.x, ground_ghost.position.y),
        Position(knight.position.x, knight.position.y),
    )

    _consume_collision_vectors(ground_battle, ground_ghost, knight)

    assert ground_ghost.position == ground_starts[0]
    assert knight.position == ground_starts[1]
    assert knight.can_attack_target(ground_ghost)

    air_battle = BattleState(fast_path=fast_path)
    air_battle.entities.clear()
    air_battle.next_entity_id = 1
    air_ghost = _spawn_one(
        air_battle,
        "RoyalGhost",
        0,
        Position(9.0, 10.0),
    )
    bats = _spawn_one(
        air_battle,
        "Bats",
        0,
        Position(9.2, 10.0),
    )

    _consume_collision_vectors(air_battle, air_ghost, bats)

    assert air_ghost.position.x < 9.0
    assert bats.position.x > 9.2

    building_battle = BattleState(fast_path=fast_path)
    building_battle.entities.clear()
    building_battle.next_entity_id = 1
    building_ghost = _spawn_one(
        building_battle,
        "RoyalGhost",
        0,
        Position(9.0, 10.0),
    )
    cannon = building_battle._spawn_entity(
        Building,
        Position(9.2, 10.0),
        0,
        building_battle.card_loader.get_card("Cannon"),
    )
    ghost_start = Position(
        building_ghost.position.x,
        building_ghost.position.y,
    )

    _consume_collision_vectors(building_battle, building_ghost)

    assert cannon.is_alive
    assert building_ghost.position == ghost_start


@pytest.mark.parametrize("fast_path", [False, True])
def test_hovering_troops_remain_on_ground_plane_for_every_attack_payload_shape(
    fast_path,
):
    from clasher.unit_traits import (
        is_above_ground_surface,
        is_airborne_target,
        uses_air_collision_plane,
    )

    def exposed_ghost(battle):
        ghost = _spawn_one(
            battle,
            "RoyalGhost",
            1,
            Position(9.0, 14.0),
        )
        ghost._stealth_until = 0
        return ghost

    direct_battle = BattleState(fast_path=fast_path)
    direct_battle.entities.clear()
    direct_battle.next_entity_id = 1
    knight = _spawn_one(
        direct_battle,
        "Knight",
        0,
        Position(9.0, 13.0),
    )
    direct_ghost = exposed_ghost(direct_battle)
    direct_hp = direct_ghost.hitpoints
    knight._deal_attack_damage(
        direct_ghost,
        knight.damage,
        direct_battle,
    )

    assert uses_air_collision_plane(direct_ghost)
    assert not is_airborne_target(direct_ghost)
    assert not is_above_ground_surface(direct_ghost)
    assert direct_hp - direct_ghost.hitpoints == knight.damage

    projectile_battle = BattleState(fast_path=fast_path)
    projectile_battle.entities.clear()
    projectile_battle.next_entity_id = 1
    cannon = projectile_battle._spawn_entity(
        Building,
        Position(9.0, 10.0),
        0,
        projectile_battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    projectile_ghost = exposed_ghost(projectile_battle)
    projectile_hp = projectile_ghost.hitpoints
    cannon._create_projectile(projectile_ghost, projectile_battle)
    cannonball = max(
        (
            entity
            for entity in projectile_battle.entities.values()
            if isinstance(entity, Projectile)
        ),
        key=lambda entity: entity.id,
    )
    cannonball.position = Position(
        cannonball.target_position.x,
        cannonball.target_position.y,
    )
    cannonball.update(projectile_battle.dt, projectile_battle)

    assert projectile_hp - projectile_ghost.hitpoints == cannon.damage

    for attacker_name, also_hits_air in (
        ("Bomber", False),
        ("BabyDragon", True),
    ):
        splash_battle = BattleState(fast_path=fast_path)
        splash_battle.entities.clear()
        splash_battle.next_entity_id = 1
        attacker = _spawn_one(
            splash_battle,
            attacker_name,
            0,
            Position(9.0, 10.0),
        )
        splash_ghost = exposed_ghost(splash_battle)
        bat = _spawn_one(
            splash_battle,
            "Bats",
            1,
            Position(9.0, 14.0),
        )
        splash_hp = splash_ghost.hitpoints
        bat_hp = bat.hitpoints
        attacker._create_projectile(splash_ghost, splash_battle)
        splash = max(
            (
                entity
                for entity in splash_battle.entities.values()
                if isinstance(entity, Projectile)
            ),
            key=lambda entity: entity.id,
        )
        splash.position = Position(
            splash.target_position.x,
            splash.target_position.y,
        )
        splash.update(splash_battle.dt, splash_battle)

        assert splash_hp - splash_ghost.hitpoints == attacker.damage
        assert bat_hp - bat.hitpoints == (
            min(bat_hp, attacker.damage) if also_hits_air else 0
        )

    rolling_battle = BattleState(fast_path=fast_path)
    rolling_battle.entities.clear()
    rolling_battle.next_entity_id = 1
    bowler = _spawn_one(
        rolling_battle,
        "Bowler",
        0,
        Position(9.0, 10.0),
    )
    rolling_ghost = exposed_ghost(rolling_battle)
    rolling_hp = rolling_ghost.hitpoints
    bowler._create_projectile(rolling_ghost, rolling_battle)
    boulder = max(
        (
            entity
            for entity in rolling_battle.entities.values()
            if type(entity).__name__ == "RollingProjectile"
        ),
        key=lambda entity: entity.id,
    )
    boulder.position = Position(
        rolling_ghost.position.x,
        rolling_ghost.position.y,
    )
    boulder._deal_rolling_damage(rolling_battle)

    assert rolling_hp - rolling_ghost.hitpoints == bowler.damage


def test_river_jumper_collides_on_air_plane_but_not_ground_plane():
    battle = BattleState()
    hog = _spawn_one(battle, "HogRider", 0, Position(9.0, 14.9))
    mega_minion = _spawn_one(battle, "MegaMinion", 0, Position(9.4, 14.9))
    knight = _spawn_one(battle, "Knight", 0, Position(9.0, 14.9))
    hog.position = Position(9.0, 14.9)
    mega_minion.position = Position(9.4, 14.9)
    knight.position = Position(9.0, 14.9)
    knight_start = Position(knight.position.x, knight.position.y)
    assert hog._try_start_river_jump(
        battle.entities[6].position,
        Position(9.0, battle.arena.RIVER_Y1),
        battle,
    )
    hog.apply_stun(0.5, source_kind="ElectroSpirit")

    _consume_collision_vectors(battle, hog, mega_minion, knight)

    assert hog.position.x < 9.0
    assert mega_minion.position.x > 9.4
    assert knight.position == knight_start


def test_river_jumper_does_not_receive_ground_building_collision():
    battle = BattleState()
    hog = _spawn_one(battle, "HogRider", 0, Position(9.0, 14.9))
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 14.9),
        1,
        cannon_stats,
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    hog.position = Position(9.0, 14.9)
    start = Position(hog.position.x, hog.position.y)
    assert hog._try_start_river_jump(
        battle.entities[6].position,
        Position(9.0, battle.arena.RIVER_Y1),
        battle,
    )

    _consume_collision_vectors(battle, hog)

    assert hog.position == start


def test_airborne_mega_knight_collides_with_air_but_not_ground_plane():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    mega_knight = _spawn_one(
        battle,
        "MegaKnight",
        0,
        Position(9.0, 12.0),
    )
    bat = _spawn_one(battle, "Bats", 1, Position(9.0, 12.0))
    knight = _spawn_one(battle, "Knight", 1, Position(9.0, 12.0))
    mega_knight._mk_leap_phase = "airborne"
    mega_knight._special_move_active = True
    starts = {
        entity.id: Position(entity.position.x, entity.position.y)
        for entity in (mega_knight, bat, knight)
    }

    _consume_collision_vectors(battle, mega_knight, bat, knight)

    assert mega_knight.position != starts[mega_knight.id]
    assert bat.position != starts[bat.id]
    assert knight.position == starts[knight.id]


@pytest.mark.parametrize("fast_path", [False, True])
def test_deploying_characters_are_present_but_cannot_act(fast_path):
    battle = BattleState(fast_path=fast_path)
    attacker = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 10.0))
    attacker.position = Position(9.0, 10.0)
    target.position = Position(9.0, 10.0)
    target.deploy_delay_remaining = 1.0
    target.placement_pending = True
    before_hp = target.hitpoints
    if fast_path:
        battle._refresh_fast_path_caches()

    assert attacker._is_valid_target(target)
    assert attacker.get_nearest_target(battle.entities) is target
    target.take_damage(100)
    target.apply_stun(1.0)
    _consume_collision_vectors(battle, attacker, target)
    assert target.hitpoints == before_hp - 100
    assert attacker.position != target.position
    assert target.stun_timer == 1.0

    target.update(0.5, battle)

    assert target.placement_pending
    assert target.deploy_delay_remaining == pytest.approx(0.5)
    assert target.stun_timer == pytest.approx(0.5)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("entity_kind", ["troop", "building"])
def test_status_clocks_advance_once_when_deployment_finishes(
    fast_path,
    entity_kind,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 0
    stats = battle.card_loader.get_card(
        "Knight" if entity_kind == "troop" else "Cannon"
    )
    assert stats is not None
    if entity_kind == "troop":
        battle._spawn_unit_at_position(Position(9.0, 12.0), 0, stats)
    else:
        battle._spawn_entity(Building, Position(9.0, 12.0), 0, stats)
    entity = next(iter(battle.entities.values()))
    entity.deploy_delay_remaining = battle.dt
    entity.placement_delay_total = battle.dt
    entity.placement_pending = True
    entity.apply_stun(0.5)
    entity.apply_slow(0.5, 0.7)
    entity.apply_haste(0.5, 1.3, 1.3, 1.3)

    battle.step()

    assert not entity.placement_pending
    assert entity.deploy_delay_remaining == 0.0
    assert entity.stun_timer == pytest.approx(0.45)
    assert entity.slow_timer == pytest.approx(0.45)
    assert entity.haste_timer == pytest.approx(0.45)

    battle.step()

    assert entity.stun_timer == pytest.approx(0.4)
    assert entity.slow_timer == pytest.approx(0.4)
    assert entity.haste_timer == pytest.approx(0.4)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("entity_kind", ["troop", "building"])
def test_deployment_completion_defers_combat_until_the_next_logic_frame(
    fast_path,
    entity_kind,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(
        "Knight" if entity_kind == "troop" else "Cannon"
    )
    assert stats is not None
    if entity_kind == "troop":
        battle._spawn_unit_at_position(Position(9.0, 12.0), 0, stats)
    else:
        battle._spawn_entity(Building, Position(9.0, 12.0), 0, stats)
    attacker = next(iter(battle.entities.values()))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 13.1))
    attacker.position = Position(9.0, 12.0)
    target.position = Position(9.0, 13.1)
    target.apply_stun(99.0)
    attacker.deploy_delay_remaining = battle.dt
    attacker.placement_delay_total = battle.dt
    attacker.placement_pending = True
    attacker.attack_cooldown = 0.0
    hp_before = target.hitpoints

    battle.step()

    assert not attacker.placement_pending
    assert target.hitpoints == hp_before
    assert not any(
        isinstance(entity, Projectile) and entity.player_id == attacker.player_id
        for entity in battle.entities.values()
    )

    battle.step()

    if entity_kind == "building":
        assert target.hitpoints == hp_before
        assert any(isinstance(e, Projectile) for e in battle.entities.values())
        battle.step()
    assert target.hitpoints == hp_before - attacker.damage


@pytest.mark.parametrize("fast_path", [False, True])
def test_spawn_payload_and_character_clock_run_on_deploy_zero_crossing(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 12.0))
    hp_before = target.hitpoints
    wizard_stats = battle.card_loader.get_card("IceWizard")
    assert wizard_stats is not None
    battle._spawn_unit_at_position(Position(9.0, 12.0), 0, wizard_stats)
    wizard = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.player_id == 0
    )
    wizard.deploy_delay_remaining = battle.dt
    wizard.placement_delay_total = battle.dt
    wizard.placement_pending = True
    wizard.attack_cooldown = 0.0

    battle.step()

    assert not wizard.placement_pending
    assert target.hitpoints == pytest.approx(
        hp_before - wizard.card_stats.get_scaled_stat(33)
    )
    assert not any(
        isinstance(entity, Projectile) and entity.player_id == wizard.player_id
        for entity in battle.entities.values()
    )

    tomb_stats = battle.card_loader.get_card("Tombstone")
    assert tomb_stats is not None
    tomb = battle._spawn_entity(
        Building,
        Position(4.0, 12.0),
        0,
        tomb_stats,
    )
    tomb.deploy_delay_remaining = battle.dt
    tomb.placement_delay_total = battle.dt
    tomb.placement_pending = True
    tomb_hp = tomb.hitpoints
    spawner = next(
        mechanic
        for mechanic in tomb.mechanics
        if type(mechanic).__name__ == "PeriodicSpawner"
    )

    battle.step()

    assert not tomb.placement_pending
    assert tomb.hitpoints == tomb_hp
    assert tomb.lifetime_elapsed == 0.0
    assert tomb.lifetime_decay_work == 0
    assert spawner.time_since_spawn_ms == pytest.approx(50.0)

    battle.step()

    assert tomb.hitpoints == tomb_hp
    assert tomb.lifetime_elapsed == pytest.approx(battle.dt)
    assert tomb.lifetime_decay_work == 88
    assert spawner.time_since_spawn_ms == pytest.approx(100.0)

    battle.step()

    assert tomb.hitpoints == tomb_hp - 1
    assert tomb.lifetime_decay_work == 76


@pytest.mark.parametrize("fast_path", [False, True])
def test_tesla_hide_clock_and_first_hit_load_start_on_deploy_zero_crossing(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    target = _spawn_one(battle, "HogRider", 1, Position(9.0, 12.0))
    target.apply_stun(99.0)
    hp_before = target.hitpoints
    tesla = battle._spawn_entity(
        Building,
        Position(9.0, 12.0),
        0,
        battle.card_loader.get_card("Tesla"),
    )
    tesla.deploy_delay_remaining = battle.dt
    tesla.placement_delay_total = battle.dt
    tesla.placement_pending = True
    tesla.attack_cooldown = tesla.get_preloaded_attack_time_seconds()
    hide = next(
        mechanic
        for mechanic in tesla.mechanics
        if type(mechanic).__name__ == "HideWhenIdle"
    )
    assert hide._phase_ms == 0.0
    assert not tesla._hidden_building

    battle.step()

    assert not tesla.placement_pending
    assert hide._phase_ms == 0.0
    assert not tesla._hidden_building
    assert target.hitpoints == hp_before
    assert tesla.attack_cooldown == pytest.approx(0.35)

    for _ in range(6):
        battle.step()
    assert target.hitpoints == hp_before
    battle.step()

    assert target.hitpoints == hp_before - tesla.damage


@pytest.mark.parametrize("fast_path", [False, True])
def test_exact_half_second_stun_blocks_ten_full_logic_frames(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn_one(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 13.1))
    attacker.position = Position(9.0, 12.0)
    target.position = Position(9.0, 13.1)
    target.apply_stun(99.0)
    attacker.attack_cooldown = 0.0
    attacker.apply_stun(0.5)
    hp_before = target.hitpoints

    for _ in range(10):
        battle.step()

    assert attacker.stun_timer == 0.0
    assert target.hitpoints == hp_before

    battle.step()

    # The explicitly ready hit survives the pause and commits on thaw.
    assert target.hitpoints == hp_before - attacker.damage
    assert attacker._ordinary_clock is not None
    assert attacker._ordinary_clock.load_remaining_ms == attacker.card_stats.load_time


@pytest.mark.parametrize("effect", ["slow", "rage"])
def test_slow_and_rage_govern_their_full_final_movement_frame(
    effect,
):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    mover = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    target.position = Position(9.0, 14.0)
    mover.target_id = target.id
    target.apply_stun(99.0)
    if effect == "slow":
        mover.apply_slow(0.5, 0.7)
    else:
        mover.apply_haste(0.5, 1.3, 1.3, 1.3)

    steps = []
    for _ in range(11):
        old_position = Position(mover.position.x, mover.position.y)
        mover.update(battle.dt, battle)
        mover.quantize_logic_position()
        steps.append(old_position.distance_to(mover.position))

    effect_work = speed_work_for_duration(
        mover.card_stats.speed * (0.7 if effect == "slow" else 1.3),
        battle.dt,
    )
    base_work = speed_work_for_duration(mover.card_stats.speed, battle.dt)
    assert all(
        effect_work - 2 <= tiles_to_logic_units(step) <= effect_work
        for step in steps[:10]
    )
    assert base_work - 2 <= tiles_to_logic_units(steps[10]) <= base_work
    if effect == "slow":
        assert steps[10] > steps[9]
    else:
        assert steps[10] < steps[9]


def test_spawner_object_clock_observes_buff_expiry_from_the_same_frame():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    witch = _spawn_one(battle, "Witch", 0, Position(9.0, 10.0))
    spawner = next(
        mechanic
        for mechanic in witch.mechanics
        if type(mechanic).__name__ == "PeriodicSpawner"
    )
    witch.apply_haste(0.05, 1.3, 1.3, 1.3)

    witch.update(battle.dt, battle)

    assert witch.haste_timer == 0.0
    assert spawner.time_since_spawn_ms == pytest.approx(50.0)


@pytest.mark.parametrize("fast_path", [False, True])
def test_building_commits_final_attack_before_lifetime_component_kills_it(
    fast_path,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 12.0),
        0,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    cannon.on_spawn()
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 12.0))
    target.apply_stun(99.0)
    cannon.position = Position(9.0, 12.0)
    target.position = Position(9.0, 12.0)
    cannon.attack_cooldown = 0.0
    cannon.hitpoints = 1.0
    cannon.lifetime_decay_work = 99
    hp_before = target.hitpoints

    battle.step()

    assert not cannon.is_alive
    assert target.hitpoints == hp_before
    assert any(isinstance(e, Projectile) for e in battle.entities.values())
    battle.step()
    assert target.hitpoints == hp_before - cannon.damage


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize(
    "card_name",
    ["BombTower", "Cannon", "InfernoTower", "Tesla", "Tombstone", "Xbow"],
)
def test_enabled_building_lifetime_components_start_after_deployment(
    fast_path,
    card_name,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None and stats.lifetime_ms is not None
    building = battle._spawn_entity(
        Building,
        Position(9.0, 12.0),
        0,
        stats,
    )
    hp_before = building.hitpoints
    deployment_frames = math.ceil(
        building.deploy_delay_remaining / battle.dt - 1e-9
    )
    decay_rate = 5000 * int(building.max_hitpoints) // stats.lifetime_ms

    for _ in range(deployment_frames):
        building.update(battle.dt, battle)

    assert not building.placement_pending
    assert building.hitpoints == hp_before
    assert building.lifetime_decay_work == 0
    assert building.lifetime_elapsed == 0.0

    building.update(battle.dt, battle)
    assert building.hitpoints == hp_before - decay_rate // 100
    assert building.lifetime_decay_work == decay_rate % 100
    assert building.lifetime_elapsed == pytest.approx(battle.dt)


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize(
    "card_name",
    ["BombTower", "Cannon", "InfernoTower", "Tesla", "Tombstone", "Xbow"],
)
def test_enabled_building_lifetimes_use_native_fixed_point_decay(
    fast_path,
    card_name,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None and stats.lifetime_ms is not None
    building = battle._spawn_entity(
        Building,
        Position(9.0, 12.0),
        0,
        stats,
    )
    building.deploy_delay_remaining = 0.0
    building.placement_pending = False
    building.on_spawn()
    decay_rate = 5000 * int(building.max_hitpoints) // stats.lifetime_ms
    death_frame = math.ceil(building.hitpoints * 100 / decay_rate)

    for _ in range(death_frame - 1):
        building.update(battle.dt, battle)

    expected_work = decay_rate * (death_frame - 1)
    assert building.is_alive
    assert building.hitpoints == building.max_hitpoints - expected_work // 100
    assert building.lifetime_decay_work == expected_work % 100

    building.update(battle.dt, battle)

    assert not building.is_alive
    assert building.hitpoints == 0.0
    assert death_frame * 50 >= stats.lifetime_ms
    assert death_frame * 50 - stats.lifetime_ms <= 100


@pytest.mark.parametrize("fast_path", [False, True])
def test_deploying_building_immediately_pulls_building_targeters(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    hog = _spawn_one(battle, "HogRider", 0, Position(9.0, 10.0))
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 14.0),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    assert cannon.placement_pending
    if fast_path:
        battle._refresh_fast_path_caches()

    assert hog.get_nearest_target(battle.entities) is cannon


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("card_name", ["Bandit", "MegaKnight"])
def test_special_dash_uses_closest_target_at_launch_without_restarting_windup(
    fast_path,
    card_name,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    mover = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    original = _spawn_one(battle, "Knight", 1, Position(12.5, 13.5))
    original.apply_stun(99.0)
    mover.target_id = original.id
    mechanic = mover.mechanics[0]

    if card_name == "Bandit":
        mechanic._start_charge(mover, original)
        mover._bandit_dash_timer = mechanic.dash_duration_ms - 50
    else:
        mechanic._start_charge(mover, original)
        mover._mk_leap_progress = mechanic.leap_duration_ms - 50

    # The closer troop appears during the final charge frame. Dash users choose
    # their victim at launch, so the accumulated wind-up must not be discarded.
    # Keep the replacement closer than the original while remaining outside
    # both cards' radius-aware native minimum dash/leap range.
    replacement = _spawn_one(battle, "Knight", 1, Position(5.8, 13.6))
    replacement.apply_stun(99.0)

    battle.step()

    assert mover.target_id == replacement.id
    if card_name == "Bandit":
        assert mover._bandit_dashing
        assert not mover._bandit_charging
        assert mover._bandit_dash_target_id == replacement.id
        assert mover._bandit_dash_target[0] < mover.position.x
    else:
        assert mover._mk_leap_phase == "airborne"
        assert mover._mk_leap_target_id == replacement.id
        assert mover._mk_leap_target[0] < mover.position.x


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("card_name", ["Bandit", "MegaKnight"])
@pytest.mark.parametrize("target_change", ["dies", "leaves_range"])
def test_special_attack_windup_cancels_when_no_launch_target_remains(
    fast_path,
    card_name,
    target_change,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    mover = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.5))
    target.apply_stun(99.0)
    mechanic = mover.mechanics[0]
    mechanic._start_charge(mover, target)

    if target_change == "dies":
        target.take_damage(target.hitpoints)
    else:
        target.position = Position(9.0, 25.0)
        battle.sync_fast_target_entity(target)

    battle.step()

    assert not mover._special_move_active
    if card_name == "Bandit":
        assert not mover._bandit_charging
        assert not mover._bandit_dashing
    else:
        assert mover._mk_leap_phase is None
    if target_change == "dies":
        assert target.id not in battle.entities
    else:
        assert target.is_alive
        assert mover.position == Position(9.0, 10.0)
