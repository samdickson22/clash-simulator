from __future__ import annotations

from collections import deque
import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState, SERVER_ACTION_DELAY_SECONDS
from clasher.entities import (
    AreaEffect,
    Building,
    Graveyard,
    Projectile,
    RollingProjectile,
    SpawnProjectile,
    TimedExplosive,
    Troop,
)
from clasher.logic_math import native_percent_damage
from clasher.spells import DirectDamageSpell, SPELL_REGISTRY
from clasher.unit_traits import unit_mass


def _enemy_princess_tower(battle: BattleState) -> Building:
    return next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 1
        and entity.card_stats.name == "Tower"
    )


def _spawn_enemy_troop(battle: BattleState, name: str, position: Position) -> Troop:
    before = set(battle.entities)
    battle._spawn_troop(position, 1, battle.card_loader.get_card(name))
    troop = battle.entities[max(set(battle.entities) - before)]
    assert isinstance(troop, Troop)
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    return troop


def _prepare_card(battle: BattleState, name: str) -> None:
    player = battle.players[0]
    player.elixir = 10.0
    player.hand = [name]
    player.deck = [name]
    player.cycle_queue = deque()


def _enemy_golemites(battle: BattleState) -> list[Troop]:
    return [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == 1
        and entity.card_stats.name == "Golemite"
    ]


def _fully_hide_tesla(tesla: Building) -> None:
    hide = next(
        mechanic
        for mechanic in tesla.mechanics
        if type(mechanic).__name__ == "HideWhenIdle"
    )
    hide._phase_ms = float(hide.hide_delay_ms)
    tesla._hidden_building = True
    tesla._special_move_active = True
    tesla.target_id = None
    battle = tesla.battle_state
    if battle is not None:
        battle.sync_fast_target_entity(tesla)
    assert tesla._hidden_building


@pytest.mark.parametrize(
    ("damage", "multiplier", "expected"),
    (
        (179, 0.30, 54),
        # Python round/floor produce 54 here; every native data getter uses
        # the add-99 ceiling path and therefore produces 55.
        (181, 0.30, 55),
        (1, 0.01, 1),
        (181, 0.0, 0),
        (181, 1.0, 181),
    ),
)
def test_native_damage_percentages_use_shared_integer_ceiling(
    damage,
    multiplier,
    expected,
):
    assert native_percent_damage(damage, multiplier) == expected


def test_native_percentage_ceiling_reaches_direct_projectile_and_area_payloads():
    battle = BattleState()
    tower = _enemy_princess_tower(battle)
    tower_before = tower.hitpoints

    direct = DirectDamageSpell(
        name="NativePercentProbe",
        mana_cost=0,
        radius=1.0,
        damage=181,
        crown_tower_damage_multiplier=0.30,
    )
    assert direct.cast(battle, 0, tower.position)
    assert tower_before - tower.hitpoints == 55

    tower.hitpoints = tower_before
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(tower.position.x, tower.position.y),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=181,
        range=1.0,
        sight_range=1.0,
        target_position=Position(tower.position.x, tower.position.y),
        primary_target=tower,
        crown_tower_damage_multiplier=0.30,
    )
    projectile.update(battle.dt, battle)
    assert tower_before - tower.hitpoints == 55

    tower.hitpoints = tower_before
    area = AreaEffect(
        id=battle.next_entity_id + 1,
        position=Position(tower.position.x, tower.position.y),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=181,
        range=1.0,
        sight_range=1.0,
        duration=battle.dt,
        radius=1.0,
        damage_tick_interval=battle.dt,
        max_damage_ticks=1,
        damage_on_spawn=True,
        crown_tower_damage_multiplier=0.30,
    )
    area.update(battle.dt, battle)
    assert tower_before - tower.hitpoints == 55

    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 20.0),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    cannon_before = cannon.hitpoints
    area.position = Position(cannon.position.x, cannon.position.y)
    area.damage_ticks_applied = 0
    area.next_damage_time = 0.0
    area.time_alive = 0.0
    area.is_alive = True
    area.building_damage_multiplier = 0.30
    area.update(battle.dt, battle)
    assert cannon_before - cannon.hitpoints == 55


def test_zap_status_pass_includes_birth_tick_death_spawns_without_redamage():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    golem = _spawn_enemy_troop(battle, "Golem", Position(9.0, 14.0))
    zap = SPELL_REGISTRY["Zap"]
    golem.hitpoints = zap.damage

    assert zap.cast(battle, 0, golem.position)

    golemites = _enemy_golemites(battle)
    assert len(golemites) == 2
    assert all(entity.hitpoints == entity.max_hitpoints for entity in golemites)
    assert all(entity.stun_timer == zap.stun_duration for entity in golemites)


def test_freeze_status_pass_includes_birth_tick_death_spawns_without_redamage():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    golem = _spawn_enemy_troop(battle, "Golem", Position(9.0, 14.0))
    freeze = SPELL_REGISTRY["Freeze"]
    golem.hitpoints = freeze.damage

    assert freeze.cast(battle, 0, golem.position)
    area = next(
        entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)
    )
    area.update(battle.dt, battle)

    golemites = _enemy_golemites(battle)
    assert len(golemites) == 2
    assert all(entity.hitpoints == entity.max_hitpoints for entity in golemites)
    assert all(entity.stun_timer > 0.0 for entity in golemites)
    assert all(entity.slow_multiplier == 0.0 for entity in golemites)


def test_snowball_status_pass_includes_birth_tick_death_spawns_without_redamage():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    golem = _spawn_enemy_troop(battle, "Golem", Position(9.0, 14.0))
    snowball = SPELL_REGISTRY["Snowball"]
    golem.hitpoints = snowball.damage

    assert snowball.cast(battle, 0, golem.position)
    projectile = next(
        entity for entity in battle.entities.values() if isinstance(entity, Projectile)
    )
    projectile.position = Position(
        projectile.target_position.x,
        projectile.target_position.y,
    )
    projectile.update(battle.dt, battle)

    golemites = _enemy_golemites(battle)
    assert len(golemites) == 2
    assert all(entity.hitpoints == entity.max_hitpoints for entity in golemites)
    assert all(entity.slow_timer == snowball.slow_duration for entity in golemites)
    assert all(entity.slow_multiplier == snowball.slow_multiplier for entity in golemites)


def test_poison_exact_tangent_is_excluded_for_both_player_mirrors():
    upper = BattleState()
    lower = BattleState()
    barbarian_stats = upper.card_loader.get_card("BarbarianBarrel")
    assert barbarian_stats is not None
    barbarian_data = (
        barbarian_stats.card_definition.raw["projectileData"]
        ["spawnProjectileData"]["spawnCharacterData"]
    )
    barbarian_stats = upper._create_card_stats_from_data(
        barbarian_data,
        "Barbarian",
    )

    upper._spawn_unit_at_position(
        Position(14.5, 23.50000000000002),
        1,
        barbarian_stats,
        snap_to_valid=False,
    )
    lower._spawn_unit_at_position(
        Position(3.5, 8.49999999999998),
        0,
        barbarian_stats,
        snap_to_valid=False,
    )
    upper_barbarian = upper.entities[max(upper.entities)]
    lower_barbarian = lower.entities[max(lower.entities)]
    upper_barbarian.deploy_delay_remaining = 0.0
    lower_barbarian.deploy_delay_remaining = 0.0
    upper_barbarian.placement_pending = False
    lower_barbarian.placement_pending = False

    SPELL_REGISTRY["Poison"].cast(upper, 0, Position(14.5, 27.5))
    SPELL_REGISTRY["Poison"].cast(lower, 1, Position(3.5, 4.5))
    upper_effect = next(
        entity for entity in upper.entities.values() if isinstance(entity, AreaEffect)
    )
    lower_effect = next(
        entity for entity in lower.entities.values() if isinstance(entity, AreaEffect)
    )
    upper_effect.update(upper.dt, upper)
    lower_effect.update(lower.dt, lower)

    assert upper_barbarian.slow_timer == 0.0
    assert lower_barbarian.slow_timer == 0.0


def test_native_area_intersection_uses_rounded_building_corners():
    battle = BattleState()
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 16.0),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    radius = cannon.get_collision_radius()
    corner_offset = radius + SPELL_REGISTRY["Zap"].radius * 0.7
    impact = Position(
        cannon.position.x + corner_offset,
        cannon.position.y + corner_offset,
    )
    before = cannon.hitpoints

    # The center is outside the circumscribed character-style circle, but the
    # Zap circle overlaps the rounded corner of the building's native square.
    assert cannon.position.distance_to(impact) > radius + SPELL_REGISTRY["Zap"].radius
    assert SPELL_REGISTRY["Zap"].cast(battle, 0, impact)

    assert cannon.hitpoints == before - SPELL_REGISTRY["Zap"].damage


def test_native_area_intersection_excludes_exact_character_tangent():
    battle = BattleState()
    knight = _spawn_enemy_troop(battle, "Knight", Position(9.0, 12.0))
    zap = SPELL_REGISTRY["Zap"]
    impact = Position(
        knight.position.x + knight.get_collision_radius() + zap.radius,
        knight.position.y,
    )
    before = knight.hitpoints

    assert not zap.cast(battle, 0, impact)

    assert knight.hitpoints == before


def test_hidden_tesla_uses_serialized_area_affects_hidden_flag():
    def hidden_tesla() -> tuple[BattleState, Building]:
        battle = BattleState()
        battle.entities.clear()
        battle.next_entity_id = 1
        tesla = battle._spawn_entity(
            Building,
            Position(9.0, 12.0),
            1,
            battle.card_loader.get_card("Tesla"),
        )
        tesla.deploy_delay_remaining = 0.0
        tesla.placement_pending = False
        tesla.on_spawn()
        _fully_hide_tesla(tesla)
        assert tesla._hidden_building
        return battle, tesla

    for spell_name in ("Zap", "Fireball", "Poison"):
        battle, tesla = hidden_tesla()
        before = tesla.hitpoints
        cast_result = SPELL_REGISTRY[spell_name].cast(
            battle,
            0,
            Position(tesla.position.x, tesla.position.y),
        )
        assert bool(cast_result) == (spell_name != "Zap")
        for effect in list(battle.entities.values()):
            if effect is tesla:
                continue
            if isinstance(effect, Projectile):
                effect.position = Position(
                    effect.target_position.x,
                    effect.target_position.y,
                )
            effect.update(battle.dt, battle)
        assert tesla.hitpoints == before
        assert tesla.stun_timer == 0.0

    freeze_battle, frozen_tesla = hidden_tesla()
    freeze_before = frozen_tesla.hitpoints
    assert SPELL_REGISTRY["Freeze"].cast(
        freeze_battle,
        0,
        frozen_tesla.position,
    )
    freeze_effect = next(
        entity
        for entity in freeze_battle.entities.values()
        if isinstance(entity, AreaEffect)
    )
    assert SPELL_REGISTRY["Freeze"].affects_hidden
    assert freeze_effect.affects_hidden
    freeze_effect.update(freeze_battle.dt, freeze_battle)
    assert freeze_before - frozen_tesla.hitpoints == SPELL_REGISTRY["Freeze"].damage
    assert frozen_tesla.stun_timer == pytest.approx(
        SPELL_REGISTRY["Freeze"].duration
    )
    assert frozen_tesla._hidden_building

    quake_battle, quake_tesla = hidden_tesla()
    quake_before = quake_tesla.hitpoints
    assert SPELL_REGISTRY["Earthquake"].cast(
        quake_battle,
        0,
        quake_tesla.position,
    )
    quake_effect = next(
        entity
        for entity in quake_battle.entities.values()
        if isinstance(entity, AreaEffect)
    )
    assert SPELL_REGISTRY["Earthquake"].affects_hidden
    assert quake_effect.affects_hidden
    for _ in range(20):
        quake_effect.update(quake_battle.dt, quake_battle)
    assert quake_tesla.hitpoints < quake_before
    assert quake_tesla.slow_timer > 0.0
    assert quake_tesla._hidden_building


@pytest.mark.parametrize(
    ("name", "damage", "tower_damage"),
    [
        ("Arrows", 122, 25),
        ("Fireball", 688, 172),
        ("Freeze", 148, 37),
        ("Snowball", 179, 45),
        ("Poison", 92, 21),
        ("Rocket", 1484, 342),
        ("Log", 268, 35),
        ("Zap", 192, 48),
        ("BarbLog", 232, 232),
        ("RoyalDelivery", 437, None),
        ("Tornado", 84, 25),
    ],
)
def test_enabled_spell_payloads_use_current_level_11_values(name, damage, tower_damage):
    spell = SPELL_REGISTRY[name]
    payload_damage = getattr(spell, "damage_per_hit", spell.damage)
    assert payload_damage == damage
    assert getattr(spell, "crown_tower_damage", None) == tower_damage


def test_area_projectile_hits_enabled_invisible_troops_without_targeting_them():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    queen = _spawn_enemy_troop(
        battle,
        "ArcherQueen",
        Position(9.0, 14.0),
    )
    ghost = _spawn_enemy_troop(
        battle,
        "RoyalGhost",
        Position(10.0, 14.0),
    )
    queen._stealth_until = ghost._stealth_until = 2**31 - 1
    before = (queen.hitpoints, ghost.hitpoints)

    assert queen.card_stats.allow_area_damage_when_invisible
    assert ghost.card_stats.allow_area_damage_when_invisible
    assert not queen.is_targetable_by(0)
    assert not ghost.is_targetable_by(0)
    impact = Position(9.5, 14.0)
    assert SPELL_REGISTRY["Fireball"].cast(battle, 0, impact)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and getattr(entity, "spell_name", "") == "Fireball"
    )
    projectile.position = Position(impact.x, impact.y)
    projectile.update(battle.dt, battle)

    assert before[0] - queen.hitpoints == SPELL_REGISTRY["Fireball"].damage
    assert before[1] - ghost.hitpoints == SPELL_REGISTRY["Fireball"].damage


def test_invisible_area_damage_eligibility_comes_from_character_payload():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    target = _spawn_enemy_troop(
        battle,
        "Knight",
        Position(9.0, 14.0),
    )
    target._stealth_until = 2**31 - 1
    hp_before = target.hitpoints

    assert not target.card_stats.allow_area_damage_when_invisible
    SPELL_REGISTRY["Zap"].cast(battle, 0, target.position)
    assert target.hitpoints == hp_before

    target.card_stats.allow_area_damage_when_invisible = True
    SPELL_REGISTRY["Zap"].cast(battle, 0, target.position)
    assert hp_before - target.hitpoints == SPELL_REGISTRY["Zap"].damage


def test_played_spell_waits_for_universal_server_action_delay():
    battle = BattleState()
    _prepare_card(battle, "Fireball")

    assert battle.deploy_card(0, "Fireball", Position(9.0, 20.0))
    assert not any(
        isinstance(entity, Projectile)
        and getattr(entity, "spell_name", "") == "Fireball"
        for entity in battle.entities.values()
    )
    assert not battle.can_fast_forward_idle()

    while battle.time + battle.dt < SERVER_ACTION_DELAY_SECONDS:
        battle.step()
    assert not any(
        isinstance(entity, Projectile)
        and getattr(entity, "spell_name", "") == "Fireball"
        for entity in battle.entities.values()
    )

    battle.step()
    assert any(
        isinstance(entity, Projectile)
        and getattr(entity, "spell_name", "") == "Fireball"
        for entity in battle.entities.values()
    )


def test_graveyard_first_skeleton_uses_published_total_delay_from_card_play():
    battle = BattleState()
    _prepare_card(battle, "Graveyard")
    assert battle.deploy_card(0, "Graveyard", Position(9.0, 20.0))

    while battle.time + battle.dt < 2.2:
        battle.step()
    assert not any(
        isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
        for entity in battle.entities.values()
    )

    battle.step()
    skeleton = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    )
    # The native ActionSpawnToLocation fires at 2.2 seconds and gives its
    # Skeleton a separate 500 ms deploy. The birth frame consumes 50 ms.
    assert skeleton.deploy_delay_remaining == pytest.approx(0.45)
    assert skeleton.placement_pending
    assert skeleton.attack_cooldown == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("name", "troop_damage", "tower_damage", "ticks"),
    [
        ("Poison", 736, 168, 8),
        ("Earthquake", 252, 147, 3),
        ("Freeze", 148, 37, 1),
        ("Tornado", 84, 25, 1),
    ],
)
def test_area_spells_deal_exact_discrete_totals(name, troop_damage, tower_damage, ticks):
    battle = BattleState()
    tower = _enemy_princess_tower(battle)
    troop = _spawn_enemy_troop(battle, "Knight", tower.position)
    tower_before = tower.hitpoints
    troop_before = troop.hitpoints
    troop.apply_stun(20.0)

    assert SPELL_REGISTRY[name].cast(battle, 0, tower.position)
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )
    while (
        area.is_alive
        or troop._periodic_damage_effects
        or tower._periodic_damage_effects
    ):
        battle.step()

    assert troop_before - troop.hitpoints == troop_damage
    assert tower_before - tower.hitpoints == tower_damage
    if not area.target_local_damage:
        assert area.damage_ticks_applied == ticks


def test_tornado_waits_for_its_serialized_hit_frequency_before_one_damage_hit():
    battle = BattleState()
    target = Position(9.0, 20.0)
    troop = _spawn_enemy_troop(battle, "Knight", target)
    hitpoints_before = troop.hitpoints

    assert SPELL_REGISTRY["Tornado"].cast(battle, 0, target)
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )

    for _ in range(11):
        battle.step()
    assert troop.hitpoints == hitpoints_before
    assert area.damage_ticks_applied == 0

    battle.step()
    assert hitpoints_before - troop.hitpoints == 84
    assert troop._periodic_damage_effects

    while area.is_alive:
        battle.step()
    assert hitpoints_before - troop.hitpoints == 84
    assert not troop._periodic_damage_effects
    assert area.damage_ticks_applied == 0


@pytest.mark.parametrize("fast_path", [False, True])
def test_tornado_damages_archer_queen_during_cloak_activation(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    queen = _spawn_enemy_troop(
        battle,
        "ArcherQueen",
        Position(9.0, 20.0),
    )
    battle.players[1].elixir = 10.0
    assert SPELL_REGISTRY["Tornado"].cast(
        battle,
        0,
        queen.position,
    )
    assert battle.activate_champion_ability(1)
    hitpoints_before = queen.hitpoints

    for _ in range(4):
        battle.step()
    assert queen._stealth_until > int(battle.time * 1000)
    assert not queen.is_targetable_by(0)

    for _ in range(8):
        battle.step()

    assert (
        hitpoints_before - queen.hitpoints
        == SPELL_REGISTRY["Tornado"].damage_per_hit
    )


def test_poison_damage_clock_starts_on_first_target_scan_and_lingers_after_exit():
    battle = BattleState()
    center = Position(9.0, 20.0)
    troop = _spawn_enemy_troop(battle, "Knight", center)
    troop.apply_stun(20.0)
    before = troop.hitpoints

    assert SPELL_REGISTRY["Poison"].cast(battle, 0, center)
    for _ in range(5):
        battle.step()
    assert battle.time == pytest.approx(0.25)
    assert troop.hitpoints == before
    assert troop._periodic_damage_effects

    # Leaving after the first AEO application does not discard the attached
    # one-second CharacterBuff or reset its target-local hit phase.
    troop.position = Position(17.0, 20.0)
    for _ in range(19):
        battle.step()
    assert battle.time == pytest.approx(1.2)
    assert troop.hitpoints == before

    battle.step()
    assert battle.time == pytest.approx(1.25)
    assert before - troop.hitpoints == 92
    assert not troop._periodic_damage_effects


@pytest.mark.parametrize("fast_path", [False, True])
def test_overlapping_poisons_keep_independent_target_local_hit_phases(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    center = Position(9.0, 20.0)
    troop = _spawn_enemy_troop(battle, "Golem", center)
    troop.apply_stun(20.0)
    before = troop.hitpoints

    assert SPELL_REGISTRY["Poison"].cast(battle, 0, center)
    for _ in range(10):
        battle.step()
    assert SPELL_REGISTRY["Poison"].cast(battle, 0, center)

    hit_times = []
    while (
        any(
            isinstance(entity, AreaEffect) and entity.is_alive
            for entity in battle.entities.values()
        )
        or troop._periodic_damage_effects
    ):
        hp_before_tick = troop.hitpoints
        battle.step()
        if troop.hitpoints < hp_before_tick:
            hit_times.append(round(battle.time, 2))

    assert hit_times == [
        1.25,
        1.75,
        2.25,
        2.75,
        3.25,
        3.75,
        4.25,
        4.75,
        5.25,
        5.75,
        6.25,
        6.75,
        7.25,
        7.75,
        8.25,
        8.75,
    ]
    assert before - troop.hitpoints == 16 * SPELL_REGISTRY["Poison"].damage
    assert battle.time == pytest.approx(9.25)
    assert not troop._periodic_damage_effects


def test_tornado_late_target_uses_its_own_clock_but_parent_caps_the_buff():
    battle = BattleState()
    center = Position(9.0, 20.0)
    troop = _spawn_enemy_troop(battle, "Knight", Position(17.0, 20.0))
    later = _spawn_enemy_troop(battle, "Knight", Position(17.0, 21.0))
    troop.apply_stun(20.0)
    later.apply_stun(20.0)
    before = troop.hitpoints
    later_before = later.hitpoints

    assert SPELL_REGISTRY["Tornado"].cast(battle, 0, center)
    for _ in range(9):
        battle.step()
    troop.position = Position(center.x, center.y)
    battle.step()  # 500 ms AEO scan attaches the first target's buff.
    later.position = Position(center.x, center.y)

    # The 500 ms entrant receives its first local hit exactly as the 1050 ms
    # parent expires. A target first scanned at 550 ms cannot finish its clock
    # before that hard parent boundary.
    for _ in range(10):
        battle.step()
    assert battle.time == pytest.approx(1.0)
    assert troop.hitpoints == before
    battle.step()
    assert battle.time == pytest.approx(1.05)
    assert before - troop.hitpoints == 84
    assert later.hitpoints == later_before
    assert not troop._periodic_damage_effects
    assert not later._periodic_damage_effects


@pytest.mark.parametrize(
    ("name", "first_effect_time"),
    [
        ("Earthquake", 0.1),
        ("Poison", 0.25),
    ],
)
def test_periodic_area_buffs_wait_for_their_serialized_aeo_hit_speed(
    name,
    first_effect_time,
):
    battle = BattleState()
    target = Position(9.0, 20.0)
    troop = _spawn_enemy_troop(battle, "Knight", target)

    assert SPELL_REGISTRY[name].cast(battle, 0, target)
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )

    elapsed = 0.0
    while elapsed + 0.05 < first_effect_time - 1e-9:
        area.update(0.05, battle)
        elapsed += 0.05
        assert troop.slow_timer == 0.0

    area.update(0.05, battle)
    assert troop.slow_timer == pytest.approx(area.slow_refresh_duration)


def test_earthquake_uses_distinct_troop_building_and_crown_payloads():
    battle = BattleState()
    target = Position(9.0, 20.0)
    troop = _spawn_enemy_troop(battle, "Knight", target)
    cannon = battle._spawn_entity(Building, target, 1, battle.card_loader.get_card("Cannon"))
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    cannon.hitpoints = cannon.max_hitpoints = 2000
    tower = _enemy_princess_tower(battle)
    tower.position = Position(target.x, target.y)
    before = (troop.hitpoints, cannon.hitpoints, tower.hitpoints)

    assert SPELL_REGISTRY["Earthquake"].cast(battle, 0, target)
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )
    while area.is_alive:
        area.update(0.05, battle)

    assert before[0] - troop.hitpoints == 84 * 3
    assert before[1] - cannon.hitpoints == 287 * 3
    assert before[2] - tower.hitpoints == 49 * 3


def test_earthquake_compact_ground_only_payload_does_not_hit_air():
    battle = BattleState()
    target = Position(9.0, 20.0)
    ground = _spawn_enemy_troop(battle, "Knight", target)
    air = _spawn_enemy_troop(battle, "BabyDragon", target)
    before = (ground.hitpoints, air.hitpoints)

    assert SPELL_REGISTRY["Earthquake"].cast(battle, 0, target)
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )
    while area.is_alive:
        area.update(0.05, battle)

    assert before[0] - ground.hitpoints == 84 * 3
    assert air.hitpoints == before[1]


def test_poison_and_earthquake_are_movement_only_slows():
    for name, expected in (("Poison", 0.85), ("Earthquake", 0.5)):
        battle = BattleState()
        troop = _spawn_enemy_troop(battle, "Witch", Position(9.0, 20.0))
        base_speed = troop.speed
        assert SPELL_REGISTRY[name].cast(battle, 0, troop.position)
        area = max(
            (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
            key=lambda entity: entity.id,
        )
        area.update(area.effect_tick_interval, battle)
        assert troop.speed == pytest.approx(base_speed * expected)
        assert troop.attack_speed_debuff_multiplier == 1.0
        assert troop.spawn_speed_debuff_multiplier == 1.0


@pytest.mark.parametrize(
    ("name", "first_effect_time"),
    [("Poison", 0.25), ("Earthquake", 0.1)],
)
def test_area_movement_slow_uses_serialized_one_second_falloff(
    name,
    first_effect_time,
):
    battle = BattleState()
    target = Position(9.0, 20.0)
    troop = _spawn_enemy_troop(battle, "Knight", target)
    assert SPELL_REGISTRY[name].cast(battle, 0, target)
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )

    area.update(first_effect_time, battle)
    assert troop.slow_timer == pytest.approx(1.0)
    troop.position = Position(17.0, 20.0)
    troop.update_status_effects(0.99)
    assert troop.slow_timer == pytest.approx(0.01)
    troop.update_status_effects(0.02)
    assert troop.slow_timer == 0.0


def test_earthquake_caps_its_final_slow_refresh_to_source_lifetime():
    battle = BattleState()
    target = Position(9.0, 20.0)
    troop = _spawn_enemy_troop(battle, "Knight", target)
    assert SPELL_REGISTRY["Earthquake"].cast(battle, 0, target)
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )

    area.time_alive = 2.8
    area.next_effect_time = 2.9
    area.update(0.1, battle)
    assert troop.slow_timer == pytest.approx(0.1)

    troop._slow_effects.clear()
    troop._recompute_slow_state()
    area.update(0.1, battle)
    assert troop.slow_timer == 0.0
    assert not area.is_alive


def test_overlapping_slows_expire_independently():
    battle = BattleState()
    troop = _spawn_enemy_troop(battle, "Knight", Position(9.0, 20.0))
    base_speed = troop.speed
    troop.apply_slow(2.0, 0.7)
    troop.apply_slow(0.5, 0.5)
    assert troop.speed == pytest.approx(base_speed * 0.5)

    troop.update_status_effects(0.6)
    assert troop.speed == pytest.approx(base_speed * 0.7)
    assert troop.attack_speed_debuff_multiplier == pytest.approx(0.7)

    troop.update_status_effects(1.5)
    assert troop.speed == pytest.approx(base_speed)
    assert troop.attack_speed_debuff_multiplier == 1.0


def _resolve_projectile_wave(
    projectiles: list[Projectile],
    battle: BattleState,
) -> None:
    for projectile in projectiles:
        projectile.launch_delay = 0.0
        projectile.position = Position(
            projectile.target_position.x,
            projectile.target_position.y,
        )
    for projectile in projectiles:
        projectile.update(0.01, battle)


def test_arrows_create_three_linked_ten_projectile_waves():
    battle = BattleState(rng=random.Random(0))
    target = Position(9.0, 20.0)
    troop = _spawn_enemy_troop(battle, "Knight", target)
    before = troop.hitpoints
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, target)

    projectiles = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and getattr(entity, "spell_name", "") == "Arrows"
    ]
    assert len(projectiles) == 30
    waves = [
        projectiles[index:index + 10]
        for index in range(0, len(projectiles), 10)
    ]
    assert [
        wave[0].launch_delay
        for wave in waves
    ] == pytest.approx([0.0, 0.2, 0.4])
    assert all(projectile.splash_radius == 1.4 for projectile in projectiles)
    assert all(
        len({id(projectile.damage_group_hit_entity_ids) for projectile in wave})
        == 1
        for wave in waves
    )
    assert len({
        id(wave[0].damage_group_hit_entity_ids)
        for wave in waves
    }) == 3

    for wave_number, wave in enumerate(waves, start=1):
        _resolve_projectile_wave(wave, battle)
        # Several 1.4-tile areas overlap the center, but linked projectiles
        # share a hit set and therefore apply only one hit per wave.
        assert before - troop.hitpoints == 122 * wave_number


def test_arrows_grouped_ring_geometry_is_deterministic_and_rerolled_per_wave():
    first = BattleState(rng=random.Random(0))
    second = BattleState(rng=random.Random(0))
    target = Position(9.0, 20.0)
    assert SPELL_REGISTRY["Arrows"].cast(first, 0, target)
    assert SPELL_REGISTRY["Arrows"].cast(second, 1, target)

    def offsets(battle: BattleState) -> list[tuple[float, float]]:
        return [
            (
                round(entity.target_position.x - target.x, 3),
                round(entity.target_position.y - target.y, 3),
            )
            for entity in battle.entities.values()
            if isinstance(entity, Projectile)
            and getattr(entity, "spell_name", "") == "Arrows"
        ]

    expected_first_wave = [
        (0.245, -0.804),
        (3.077, -0.675),
        (1.748, 2.498),
        (-0.163, 2.056),
        (-0.501, 2.172),
        (-1.721, 0.594),
        (-2.118, -1.659),
        (-1.517, -2.761),
        (1.187, -2.918),
        (1.991, -2.441),
    ]
    first_offsets = offsets(first)
    assert first_offsets[:10] == expected_first_wave
    assert first_offsets == [
        (-offset_x, -offset_y)
        for offset_x, offset_y in offsets(second)
    ]
    assert first_offsets[:10] != first_offsets[10:20]
    assert first_offsets[10:20] != first_offsets[20:30]


def test_arrows_small_areas_preserve_native_gaps_inside_cast_radius():
    battle = BattleState(rng=random.Random(0))
    target = Position(9.0, 20.0)
    # This Knight is well inside the old 3.5-tile blanket circle, but lies in
    # a deterministic gap between the first wave's linked 1.4-tile areas.
    troop = _spawn_enemy_troop(
        battle,
        "Knight",
        Position(target.x + 1.6, target.y + 0.55),
    )
    before = troop.hitpoints
    assert SPELL_REGISTRY["Arrows"].cast(battle, 0, target)
    first_wave = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
        and getattr(entity, "spell_name", "") == "Arrows"
    ][:10]
    _resolve_projectile_wave(first_wave, battle)
    assert troop.hitpoints == before


def test_tornado_damages_but_never_moves_buildings():
    battle = BattleState()
    cannon = battle._spawn_entity(
        Building,
        Position(12.0, 20.0),
        1,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    original = Position(cannon.position.x, cannon.position.y)
    assert SPELL_REGISTRY["Tornado"].cast(battle, 0, Position(9.0, 20.0))
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )
    while area.is_alive:
        battle.step()
    assert cannon.position == original
    assert cannon.hitpoints < cannon.max_hitpoints


def test_tornado_controlled_vector_moves_stunned_troops_on_the_next_tick():
    stunned_battle = BattleState()
    stunned = _spawn_enemy_troop(stunned_battle, "Knight", Position(12.0, 20.0))
    stunned.apply_stun(2.0)
    assert SPELL_REGISTRY["Tornado"].cast(
        stunned_battle,
        0,
        Position(9.0, 20.0),
    )
    stunned_tornado = next(
        entity
        for entity in stunned_battle.entities.values()
        if isinstance(entity, AreaEffect) and entity.is_tornado
    )
    stunned_start = Position(stunned.position.x, stunned.position.y)
    stunned_battle.step()
    # Area-effect object ticks run after movement components and only queue the
    # controlled vector for the following frame.
    assert stunned.position == stunned_start
    stunned_battle.step()

    expected_tick_pull = stunned.card_stats.speed / 1000.0 * 3.6
    assert stunned_start.x - stunned.position.x == pytest.approx(expected_tick_pull)
    assert stunned.hitpoints == stunned.max_hitpoints

    # Pull is continuous from the first frame, while damage waits for the
    # The object applies the buff at 50 ms; its 550 ms target-local clock then
    # completes at 600 ms.
    for _ in range(10):
        stunned_battle.step()
    assert stunned.max_hitpoints - stunned.hitpoints == 84


@pytest.mark.parametrize("fast_path", [False, True])
def test_tornado_pull_stops_out_of_range_crown_tower_attacks(fast_path):
    battle = BattleState(fast_path=fast_path)
    musketeer_stats = battle.card_loader.get_card("Musketeer")
    assert musketeer_stats is not None
    before = set(battle.entities)
    battle._spawn_troop(Position(3.5, 19.0), 0, musketeer_stats)
    musketeer = battle.entities[max(set(battle.entities) - before)]
    assert isinstance(musketeer, Troop)
    musketeer.deploy_delay_remaining = 0.0
    musketeer.placement_pending = False

    tower = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 1
        and entity.card_stats.name == "Tower"
        and entity.position.x < 9.0
    )
    musketeer.target_id = tower.id
    musketeer.attack_cooldown = 0.0
    assert musketeer.is_within_attack_clock_reach(tower)
    assert SPELL_REGISTRY["Tornado"].cast(
        battle,
        1,
        Position(3.5, 16.0),
    )
    tornado = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, AreaEffect) and entity.is_tornado
    )

    battle.step()
    assert any(
        isinstance(entity, Projectile)
        and entity.player_id == musketeer.player_id
        for entity in battle.entities.values()
    )
    while tower.hitpoints == tower.max_hitpoints:
        battle.step()
    hitpoints_after_committed_shot = tower.hitpoints

    while tornado.is_alive:
        battle.step()

    assert not musketeer.is_within_attack_clock_reach(tower)
    assert tower.hitpoints == hitpoints_after_committed_shot
    assert not any(
        isinstance(entity, Projectile)
        and entity.player_id == musketeer.player_id
        for entity in battle.entities.values()
    )


def test_tornado_pulls_airborne_river_jumper_without_resetting_landing():
    battle = BattleState()
    hog = _spawn_enemy_troop(battle, "HogRider", Position(9.0, 17.1))
    assert hog._try_start_river_jump(
        Position(9.0, 12.0),
        Position(9.0, 16.9),
        battle,
    )
    landing = Position(hog._river_jump_target.x, hog._river_jump_target.y)

    assert SPELL_REGISTRY["Tornado"].cast(battle, 0, Position(12.0, 16.0))
    battle.step()  # Tornado queues its controlled vector after Hog moves.
    x_before_pull = hog.position.x
    battle.step()  # Hog advances, then the queued air-capable pull applies.

    assert hog._river_jump_active
    assert hog.position.x > x_before_pull
    assert hog._river_jump_target == landing
    while hog._river_jump_active:
        battle.step()
    assert hog.position == landing


def test_tornado_pull_uses_base_speed_not_mass_or_active_speed_modifiers():
    first_tick_displacements = {}
    for name in ("MiniPekka", "Golem"):
        battle = BattleState()
        center = Position(9.0, 20.0)
        troop = _spawn_enemy_troop(battle, name, Position(14.4, 20.0))
        troop.apply_stun(2.0)
        troop.apply_slow(2.0, 0.5)
        start_x = troop.position.x
        assert SPELL_REGISTRY["Tornado"].cast(battle, 0, center)
        battle.step()
        battle.step()
        first_tick_displacements[name] = start_x - troop.position.x

    assert first_tick_displacements["MiniPekka"] == pytest.approx(90 / 1000 * 3.6)
    assert first_tick_displacements["Golem"] == pytest.approx(45 / 1000 * 3.6)


def test_tornado_moves_falling_skeleton_container_but_not_stationary_death_bomb():
    for card_name, should_move in (("SkeletonBarrel", True), ("Balloon", False)):
        battle = BattleState()
        source = _spawn_enemy_troop(battle, card_name, Position(12.0, 20.0))
        source.take_damage(source.hitpoints)
        payload = next(
            entity
            for entity in battle.entities.values()
            if isinstance(entity, TimedExplosive)
        )
        start = Position(payload.position.x, payload.position.y)

        assert SPELL_REGISTRY["Tornado"].cast(battle, 0, Position(9.0, 20.0))
        battle.step()
        battle.step()

        assert (payload.position != start) is should_move
        assert payload.is_alive


def test_tornado_displaces_committed_skeleton_barrel_during_contact_countdown():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    barrel = _spawn_enemy_troop(
        battle,
        "SkeletonBarrel",
        Position(9.0, 14.0),
    )
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 14.8),
        0,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    barrel.attack_cooldown = 0.0
    barrel.update_combat_component(battle.dt, battle)
    contact = Position(barrel.position.x, barrel.position.y)

    assert barrel.kamikaze_primed
    assert barrel.kamikaze_timer_remaining == pytest.approx(0.5)
    assert SPELL_REGISTRY["Tornado"].cast(
        battle,
        0,
        Position(12.0, 14.0),
    )

    # Attraction is queued in the object phase for the next movement frame.
    battle.step()
    assert barrel.position == contact
    assert barrel.kamikaze_timer_remaining == pytest.approx(0.45)
    battle.step()
    assert barrel.position.x > contact.x
    assert barrel.kamikaze_timer_remaining == pytest.approx(0.4)

    for _ in range(8):
        battle.step()

    assert not barrel.is_alive
    container = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, TimedExplosive)
    )
    assert container.position.x > barrel.position.x
    assert container.time_alive == pytest.approx(0.05)


def test_freeze_snapshots_targets_and_does_not_affect_late_entrants():
    battle = BattleState()
    center = Position(9.0, 20.0)
    first = _spawn_enemy_troop(battle, "Knight", center)

    assert SPELL_REGISTRY["Freeze"].cast(battle, 0, center)
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )
    area.update(0.05, battle)
    assert first.stun_timer == pytest.approx(area.duration)

    # Leaving the circle does not end Freeze early.
    first.position = Position(1.0, 1.0)
    first.update_status_effects(1.0)
    area.update(1.0, battle)
    assert first.stun_timer == pytest.approx(area.duration - 1.0)

    # The lingering visual area is not an aura: troops entering or deploying
    # after impact are unaffected.
    late = _spawn_enemy_troop(battle, "Knight", center)
    area.update(0.05, battle)
    assert late.stun_timer == 0.0


def test_death_spawned_troops_inherit_their_frozen_parents_expiry():
    battle = BattleState()
    center = Position(9.0, 20.0)
    golem = _spawn_enemy_troop(battle, "Golem", center)

    assert SPELL_REGISTRY["Freeze"].cast(battle, 0, center)
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )
    area.update(0.05, battle)
    battle.time = 1.0
    golem.update_status_effects(1.0)
    golem.take_damage(golem.hitpoints)

    golemites = [
        entity
        for entity in battle.entities.values()
        if (
            isinstance(entity, Troop)
            and entity.player_id == golem.player_id
            and entity.card_stats.name == "Golemite"
        )
    ]
    assert len(golemites) == 2
    assert all(child.stun_timer == pytest.approx(3.0) for child in golemites)
    assert all(child.slow_timer == pytest.approx(3.0) for child in golemites)
    assert all(child.slow_multiplier == 0.0 for child in golemites)
    assert all(child.freeze_expiry_time == pytest.approx(4.0) for child in golemites)


def test_staggered_death_spawns_do_not_inherit_freeze():
    battle = BattleState()
    center = Position(9.0, 20.0)
    ram = _spawn_enemy_troop(battle, "BattleRam", center)

    assert SPELL_REGISTRY["Freeze"].cast(battle, 0, center)
    area = max(
        (entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)),
        key=lambda entity: entity.id,
    )
    area.update(0.05, battle)
    battle.time = 1.0
    ram.update_status_effects(1.0)
    ram.take_damage(ram.hitpoints)

    barbarians = [
        entity
        for entity in battle.entities.values()
        if (
            isinstance(entity, Troop)
            and entity.player_id == ram.player_id
            and entity.card_stats.name == "Barbarian"
        )
    ]
    assert len(barbarians) == 2
    assert all(
        child.deploy_delay_remaining == pytest.approx(1.0)
        for child in barbarians
    )
    assert all(child.stun_timer == 0.0 for child in barbarians)
    assert all(child.freeze_expiry_time == 0.0 for child in barbarians)


def test_freeze_popped_character_container_carries_expiry_to_children():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    center = Position(9.0, 14.0)
    barrel = _spawn_enemy_troop(battle, "SkeletonBarrel", center)
    freeze = SPELL_REGISTRY["Freeze"]
    barrel.hitpoints = freeze.damage

    assert freeze.cast(battle, 0, center)
    area = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, AreaEffect)
    )
    area.update(battle.dt, battle)

    container = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, TimedExplosive)
    )
    assert container.carries_freeze_to_children
    assert container.freeze_expiry_time == pytest.approx(freeze.duration)
    assert container.stun_timer == 0.0

    battle.time = container.explosion_timer
    container.update(container.explosion_timer, battle)

    skeletons = [
        entity
        for entity in battle.entities.values()
        if (
            isinstance(entity, Troop)
            and entity.player_id == barrel.player_id
            and entity.card_stats.name == "Skeleton"
        )
    ]
    expected_remaining = freeze.duration - container.explosion_timer
    assert len(skeletons) == 7
    assert not container.is_alive
    assert all(
        skeleton.stun_timer == pytest.approx(expected_remaining)
        for skeleton in skeletons
    )
    assert all(
        skeleton.slow_timer == pytest.approx(expected_remaining)
        for skeleton in skeletons
    )
    assert all(skeleton.slow_multiplier == 0.0 for skeleton in skeletons)
    assert all(
        skeleton.freeze_expiry_time == pytest.approx(freeze.duration)
        for skeleton in skeletons
    )


def test_pre_frozen_parent_passes_expiry_through_character_container():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    center = Position(9.0, 14.0)
    barrel = _spawn_enemy_troop(battle, "SkeletonBarrel", center)
    freeze = SPELL_REGISTRY["Freeze"]

    assert freeze.cast(battle, 0, center)
    area = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, AreaEffect)
    )
    area.update(battle.dt, battle)
    battle.time = 1.0
    barrel.update_status_effects(1.0)
    barrel.take_damage(barrel.hitpoints)

    container = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, TimedExplosive)
    )
    assert container.freeze_expiry_time == pytest.approx(freeze.duration)
    assert container.stun_timer == 0.0

    battle.time += container.explosion_timer
    container.update(container.explosion_timer, battle)

    skeletons = [
        entity
        for entity in battle.entities.values()
        if (
            isinstance(entity, Troop)
            and entity.player_id == barrel.player_id
            and entity.card_stats.name == "Skeleton"
        )
    ]
    expected_remaining = freeze.duration - battle.time
    assert len(skeletons) == 7
    assert all(
        skeleton.stun_timer == pytest.approx(expected_remaining)
        for skeleton in skeletons
    )
    assert all(
        skeleton.slow_timer == pytest.approx(expected_remaining)
        for skeleton in skeletons
    )
    assert all(skeleton.slow_multiplier == 0.0 for skeleton in skeletons)
    assert all(
        skeleton.freeze_expiry_time == pytest.approx(freeze.duration)
        for skeleton in skeletons
    )


def test_snowball_respects_heavy_mass_but_log_pushes_heavy_troops():
    battle = BattleState()
    knight = _spawn_enemy_troop(battle, "Knight", Position(8.5, 20.0))
    prince = _spawn_enemy_troop(battle, "Prince", Position(11.5, 20.0))
    knight_start = Position(knight.position.x, knight.position.y)
    prince_start = Position(prince.position.x, prince.position.y)

    assert SPELL_REGISTRY["Snowball"].cast(battle, 0, Position(10.0, 20.0))
    snowball = max(
        (entity for entity in battle.entities.values() if isinstance(entity, Projectile)),
        key=lambda entity: entity.id,
    )
    snowball.position = Position(10.0, 20.0)
    snowball.update(0.01, battle)
    assert knight.forced_movement_active
    knight.update_movement_component(battle.dt, battle)
    assert knight.position != knight_start
    assert prince.position == prince_start

    log_battle = BattleState()
    heavy = _spawn_enemy_troop(log_battle, "Prince", Position(9.0, 11.0))
    start_y = heavy.position.y
    assert SPELL_REGISTRY["Log"].cast(log_battle, 0, Position(9.0, 10.0))
    rolling = max(
        (
            entity
            for entity in log_battle.entities.values()
            if type(entity).__name__ == "RollingProjectile"
        ),
        key=lambda entity: entity.id,
    )
    for _ in range(120):
        rolling.update(log_battle.dt, log_battle)
        if heavy.id in rolling.hit_entities:
            break
    heavy.update_movement_component(log_battle.dt, log_battle)
    assert heavy.position.y > start_y


@pytest.mark.parametrize("name", ["Log", "BarbLog"])
def test_rolling_spell_cast_delay_uses_data_speed_and_king_tower_distance(name):
    lower = BattleState()
    upper = BattleState()
    lower_target = Position(9.0, 10.0)
    upper_target = Position(9.0, 22.0)

    assert SPELL_REGISTRY[name].cast(lower, 0, lower_target)
    assert SPELL_REGISTRY[name].cast(upper, 1, upper_target)
    lower_projectile = max(
        (entity for entity in lower.entities.values() if isinstance(entity, RollingProjectile)),
        key=lambda entity: entity.id,
    )
    upper_projectile = max(
        (entity for entity in upper.entities.values() if isinstance(entity, RollingProjectile)),
        key=lambda entity: entity.id,
    )
    expected_radius = 1.95 if name == "Log" else 1.3
    assert lower_projectile.rolling_radius == expected_radius
    assert lower_projectile.radius_y == 0.6

    casting_speed = 360.0 / 50.0
    expected = lower.arena.BLUE_KING_TOWER.distance_to(lower_target) / casting_speed
    assert lower_projectile.spawn_delay == pytest.approx(expected)
    assert upper_projectile.spawn_delay == pytest.approx(expected)

    farther_target = Position(9.0, 14.0)
    assert SPELL_REGISTRY[name].cast(lower, 0, farther_target)
    farther_projectile = max(
        (entity for entity in lower.entities.values() if isinstance(entity, RollingProjectile)),
        key=lambda entity: entity.id,
    )
    assert farther_projectile.spawn_delay == pytest.approx(
        lower.arena.BLUE_KING_TOWER.distance_to(farther_target) / casting_speed
    )
    assert farther_projectile.spawn_delay > lower_projectile.spawn_delay


@pytest.mark.parametrize("name", ["Log", "BarbLog"])
def test_rolling_spell_cast_delay_honors_native_minimum_travel_distance(name):
    battle = BattleState()
    king = battle.arena.BLUE_KING_TOWER
    target = Position(king.x, king.y + 1.0)

    spell = SPELL_REGISTRY[name]
    assert spell.casting_min_distance == 3.0
    assert spell.cast(battle, 0, target)
    rolling = max(
        (entity for entity in battle.entities.values() if isinstance(entity, RollingProjectile)),
        key=lambda entity: entity.id,
    )

    assert rolling.position == target
    assert rolling.spawn_delay == pytest.approx(3.0 / (360.0 / 50.0))


def test_rolling_projectile_hits_a_character_that_is_still_deploying():
    battle = BattleState()
    target = _spawn_enemy_troop(battle, "Knight", Position(9.0, 11.0))
    target.placement_pending = True
    target.deploy_delay_remaining = 1.0
    before_hp = target.hitpoints
    before_position = Position(target.position.x, target.position.y)

    assert SPELL_REGISTRY["Log"].cast(battle, 0, Position(9.0, 10.0))
    rolling = max(
        (entity for entity in battle.entities.values() if isinstance(entity, RollingProjectile)),
        key=lambda entity: entity.id,
    )
    rolling.position = Position(target.position.x, target.position.y)
    rolling._deal_rolling_damage(battle)
    assert target.hitpoints < before_hp
    assert target.position == before_position
    assert target.forced_movement_active
    target.update_movement_component(battle.dt, battle)
    assert target.position != before_position
    assert target.id in rolling.hit_entities


def test_rolling_projectile_hit_starts_pushback_in_next_movement_phase():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    target = _spawn_enemy_troop(battle, "Knight", Position(9.0, 11.0))
    start = Position(target.position.x, target.position.y)
    rolling = RollingProjectile(
        id=battle.next_entity_id,
        position=Position(target.position.x, target.position.y),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=1,
        range=1.0,
        sight_range=0,
        travel_speed=0.0,
        projectile_range=1.0,
        spawn_delay=0.0,
        knockback_distance=1.5,
        knockback_ignores_mass=True,
    )
    rolling.spell_name = "Log"
    battle.entities[rolling.id] = rolling
    battle.next_entity_id += 1

    battle.step()

    assert target.position == start
    assert target.forced_movement_active

    battle.step()

    assert target.position == Position(start.x, start.y + 0.25)


def test_rolling_pushback_all_is_loaded_from_projectile_data():
    results = {}
    for spell_name in ("Log", "BarbarianBarrel"):
        battle = BattleState()
        golem = _spawn_enemy_troop(
            battle,
            "Golem",
            Position(9.0, 11.0),
        )
        spell = SPELL_REGISTRY[spell_name]
        assert spell.cast(battle, 0, Position(9.0, 10.0))
        rolling = max(
            (
                entity
                for entity in battle.entities.values()
                if isinstance(entity, RollingProjectile)
            ),
            key=lambda entity: entity.id,
        )
        rolling.position = Position(golem.position.x, golem.position.y)
        rolling._deal_rolling_damage(battle)
        results[spell_name] = (
            spell.knockback_ignores_mass,
            golem.forced_movement_active,
        )

    assert results == {
        "Log": (True, True),
        "BarbarianBarrel": (False, False),
    }


@pytest.mark.parametrize("fast_path", [False, True])
def test_log_pushback_cancels_mega_knight_pre_jump_charge(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1

    before = set(battle.entities)
    battle._spawn_troop(
        Position(9.0, 14.0),
        0,
        battle.card_loader.get_card("MegaKnight"),
    )
    mega_knight = battle.entities[max(set(battle.entities) - before)]
    mega_knight.deploy_delay_remaining = 0.0
    mega_knight.placement_pending = False
    target = _spawn_enemy_troop(
        battle,
        "Knight",
        Position(9.0, 18.5),
    )
    mega_knight.target_id = target.id
    mechanic = next(
        mechanic
        for mechanic in mega_knight.mechanics
        if type(mechanic).__name__ == "MegaKnightSlam"
    )
    mechanic._start_charge(mega_knight, target)
    mega_knight._mk_leap_progress = 400.0

    assert SPELL_REGISTRY["Log"].cast(
        battle,
        1,
        Position(9.0, 15.0),
    )
    rolling = max(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, RollingProjectile)
        ),
        key=lambda entity: entity.id,
    )
    rolling.spawn_delay = 0.0
    for _ in range(10):
        rolling.update(battle.dt, battle)
        if mega_knight.id in rolling.hit_entities:
            break

    assert mega_knight.id in rolling.hit_entities
    assert mega_knight.forced_movement_active
    assert mega_knight._mk_leap_phase is None
    assert mega_knight._mk_leap_progress == 0.0
    assert not mega_knight._special_move_active


@pytest.mark.parametrize("fast_path", [False, True])
def test_log_pushback_cancels_bandit_pre_dash_charge(fast_path):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1

    before = set(battle.entities)
    battle._spawn_troop(
        Position(9.0, 14.0),
        0,
        battle.card_loader.get_card("Bandit"),
    )
    bandit = battle.entities[max(set(battle.entities) - before)]
    bandit.deploy_delay_remaining = 0.0
    bandit.placement_pending = False
    target = _spawn_enemy_troop(
        battle,
        "Knight",
        Position(9.0, 18.5),
    )
    bandit.target_id = target.id
    mechanic = next(
        mechanic
        for mechanic in bandit.mechanics
        if type(mechanic).__name__ == "BanditDash"
    )
    mechanic._start_charge(bandit, target)
    bandit._bandit_dash_timer = 400.0

    assert SPELL_REGISTRY["Log"].cast(
        battle,
        1,
        Position(9.0, 15.0),
    )
    rolling = max(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, RollingProjectile)
        ),
        key=lambda entity: entity.id,
    )
    rolling.spawn_delay = 0.0
    for _ in range(10):
        rolling.update(battle.dt, battle)
        if bandit.id in rolling.hit_entities:
            break

    assert bandit.id in rolling.hit_entities
    assert bandit.forced_movement_active
    assert not bandit._bandit_charging
    assert not bandit._bandit_dashing
    assert bandit._bandit_dash_timer == 0.0
    assert not bandit._special_move_active


def test_log_passes_under_air_troops_and_ignores_spell_entities():
    battle = BattleState()
    balloon = _spawn_enemy_troop(battle, "Balloon", Position(9.0, 11.0))
    enemy_effect = AreaEffect(
        id=battle.next_entity_id,
        position=Position(9.0, 11.0),
        player_id=1,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=1,
        range=1,
        sight_range=1,
    )
    battle.entities[enemy_effect.id] = enemy_effect
    battle.next_entity_id += 1
    balloon_hp = balloon.hitpoints

    assert SPELL_REGISTRY["Log"].cast(battle, 0, Position(9.0, 10.0))
    rolling = max(
        (entity for entity in battle.entities.values() if isinstance(entity, RollingProjectile)),
        key=lambda entity: entity.id,
    )
    rolling.position = Position(9.0, 11.0)
    rolling._deal_rolling_damage(battle)

    assert balloon.hitpoints == balloon_hp
    assert balloon.id not in rolling.hit_entities
    assert enemy_effect.is_alive
    assert enemy_effect.id not in rolling.hit_entities


def test_rolling_projectile_resolves_damage_at_exact_range_endpoint():
    battle = BattleState()
    target = _spawn_enemy_troop(battle, "Knight", Position(9.0, 11.0))
    before = target.hitpoints
    rolling = RollingProjectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=50,
        range=0.0,
        sight_range=0,
        travel_speed=200.0,
        projectile_range=1.0,
        spawn_delay=0.0,
        radius_y=0.0,
        knockback_distance=0.0,
    )
    battle.entities[rolling.id] = rolling

    rolling.update(0.3, battle)

    assert not rolling.is_alive
    assert target.hitpoints == before - 50


def test_rolling_projectile_rectangular_boundary_tolerates_subnanotile_drift():
    battle = BattleState()
    target = _spawn_enemy_troop(
        battle,
        "Knight",
        Position(10.5000000005, 10.0),
    )
    rolling = RollingProjectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=None,
        hitpoints=1,
        max_hitpoints=1,
        damage=100,
        range=1.0,
        sight_range=0,
        radius_y=0.0,
    )

    assert rolling._hitbox_overlaps_with_rolling_path(target)


def test_snowball_cannot_damage_slow_or_push_bandit_during_dash_travel():
    battle = BattleState()
    bandit = _spawn_enemy_troop(battle, "Bandit", Position(9.0, 20.0))
    bandit._bandit_dashing = True
    bandit._special_move_active = True
    before_hp = bandit.hitpoints
    before_position = Position(bandit.position.x, bandit.position.y)

    assert SPELL_REGISTRY["Snowball"].cast(battle, 0, bandit.position)
    projectile = max(
        (entity for entity in battle.entities.values() if isinstance(entity, Projectile)),
        key=lambda entity: entity.id,
    )
    projectile.position = Position(bandit.position.x, bandit.position.y)
    projectile.update(0.01, battle)

    assert bandit.hitpoints == before_hp
    assert bandit.position == before_position
    assert bandit.slow_timer == 0.0


@pytest.mark.parametrize("card_name", ["IceSpirit", "ElectroSpirit"])
def test_snowball_cannot_affect_a_committed_spirit_jump(card_name):
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    spirit = _spawn_enemy_troop(
        battle,
        card_name,
        Position(9.0, 14.0),
    )
    before = set(battle.entities)
    battle._spawn_troop(
        Position(9.0, 15.5),
        0,
        battle.card_loader.get_card("Knight"),
    )
    target = battle.entities[max(set(battle.entities) - before)]
    assert isinstance(target, Troop)
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target.apply_stun(99.0)
    spirit.target_id = target.id
    spirit.attack_cooldown = 0.0

    battle.step()

    assert spirit._special_move_active
    before_hp = spirit.hitpoints
    before_position = Position(spirit.position.x, spirit.position.y)
    assert not spirit.can_receive_effect("Snowball")
    assert not spirit.can_receive_forced_movement("Snowball", "knockback")

    assert SPELL_REGISTRY["Snowball"].cast(battle, 0, spirit.position)
    projectile = max(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Projectile)
        ),
        key=lambda entity: entity.id,
    )
    projectile.position = Position(spirit.position.x, spirit.position.y)
    projectile.update(0.01, battle)

    assert spirit.hitpoints == before_hp
    assert spirit.position == before_position
    assert spirit._knockback_target is None
    assert spirit.slow_timer == 0.0


def test_territory_restricted_spells_share_deployment_validation():
    for name in ("Log", "BarbarianBarrel", "RoyalDelivery"):
        battle = BattleState()
        _prepare_card(battle, name)
        assert not battle.deploy_card(0, name, Position(9.0, 20.0))
        assert battle.deploy_card(0, name, Position(9.0, 10.0))

    battle = BattleState()
    _prepare_card(battle, "Tornado")
    assert battle.deploy_card(0, "Tornado", Position(9.0, 20.0))


def test_barbarian_barrel_spawn_keeps_current_one_second_deploy_time():
    battle = BattleState()
    assert SPELL_REGISTRY["BarbLog"].spawn_deploy_delay == 1.0
    assert SPELL_REGISTRY["BarbLog"].cast(battle, 0, Position(9.0, 10.0))
    projectile = next(
        entity
        for entity in battle.entities.values()
        if type(entity).__name__ == "RollingProjectile"
    )
    while projectile.is_alive:
        projectile.update(0.05, battle)

    barbarian = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == 0
        and entity.card_stats.name == "Barbarian"
    )
    assert (barbarian.max_hitpoints, barbarian.damage) == (691, 192)
    assert (
        barbarian.card_stats.hit_speed,
        barbarian.card_stats.load_time,
        barbarian.card_stats.first_hit_time,
    ) == (
        1400,
        1000,
        400,
    )
    assert barbarian.deploy_delay_remaining == pytest.approx(1.0)
    assert barbarian.placement_pending

    position = Position(barbarian.position.x, barbarian.position.y)
    barbarian.update(0.99, battle)
    assert barbarian.position == position
    assert barbarian.deploy_delay_remaining == pytest.approx(0.01)


def test_barbarian_barrel_endpoint_spawn_keeps_projectile_impact_coordinate():
    positions = []
    for player_id, target in (
        (1, Position(11.5, 21.5)),
        (0, Position(6.5, 10.5)),
    ):
        battle = BattleState()
        battle.entities.clear()
        battle.next_entity_id = 1
        assert SPELL_REGISTRY["BarbLog"].cast(battle, player_id, target)
        barrel = next(
            entity
            for entity in battle.entities.values()
            if type(entity).__name__ == "RollingProjectile"
        )
        while barrel.is_alive:
            barrel.update(battle.dt, battle)
        barbarian = next(
            entity for entity in battle.entities.values() if isinstance(entity, Troop)
        )
        positions.append(barbarian.position)

    assert positions[0] == Position(11.5, 17.0)
    assert positions[1] == Position(6.5, 15.0)
    assert positions[0] == Position(18.0 - positions[1].x, 32.0 - positions[1].y)


def test_royal_delivery_spawns_current_shielded_recruit_after_impact():
    battle = BattleState()
    _prepare_card(battle, "RoyalDelivery")
    assert battle.deploy_card(0, "RoyalDelivery", Position(9.0, 10.0))
    # One second of server action delay plus the serialized two-second fall.
    for _ in range(95):
        battle.step()

    recruit = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == 0
        and entity.card_stats.name == "DeliveryRecruit"
    )
    shield = next(mechanic for mechanic in recruit.mechanics if type(mechanic).__name__ == "Shield")
    assert recruit.max_hitpoints == 547
    assert recruit.damage == 133
    assert unit_mass(recruit.card_stats) == 5.0
    assert shield.current_shield == 240

    while recruit.placement_pending:
        battle.step()
    recruit.take_damage(100)
    assert shield.current_shield == 140
    assert recruit.hitpoints == recruit.max_hitpoints


def test_royal_delivery_damage_and_death_effects_precede_recruit_spawn():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    target = Position(9.0, 10.0)
    golem = _spawn_enemy_troop(battle, "Golem", target)
    delivery = SPELL_REGISTRY["RoyalDelivery"]
    golem.hitpoints = delivery.damage

    assert delivery.cast(battle, 0, target)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, SpawnProjectile)
    )
    projectile.update(delivery.impact_delay, battle)

    golemites = _enemy_golemites(battle)
    recruit = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == 0
        and entity.card_stats.name == "DeliveryRecruit"
    )
    shield = next(
        mechanic
        for mechanic in recruit.mechanics
        if type(mechanic).__name__ == "Shield"
    )
    assert len(golemites) == 2
    assert max(entity.id for entity in golemites) < recruit.id
    assert shield.current_shield == shield.max_shield
    assert recruit.hitpoints == recruit.max_hitpoints
    assert recruit._knockback_target is None


def test_royal_delivery_serialized_area_ignores_buildings_but_hits_troops():
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    target = Position(9.0, 10.0)
    troop = _spawn_enemy_troop(battle, "Knight", target)
    cannon = battle._spawn_entity(
        Building,
        target,
        1,
        battle.card_loader.get_card("Cannon"),
    )
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    cannon.on_spawn()
    troop_hp = troop.hitpoints
    cannon_hp = cannon.hitpoints
    delivery = SPELL_REGISTRY["RoyalDelivery"]

    assert delivery.ignore_buildings
    assert delivery.cast(battle, 0, target)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, SpawnProjectile)
    )
    assert projectile.ignore_buildings
    projectile.update(delivery.impact_delay, battle)

    assert troop_hp - troop.hitpoints == delivery.damage
    assert cannon.hitpoints == cannon_hp
    assert any(
        isinstance(entity, Troop)
        and entity.player_id == 0
        and entity.card_stats.name == "DeliveryRecruit"
        for entity in battle.entities.values()
    )


def test_royal_delivery_uses_payload_spawn_time_for_recruit_action_delay():
    battle = BattleState()
    target = Position(9.0, 10.0)
    assert SPELL_REGISTRY["RoyalDelivery"].cast(battle, 0, target)

    # The falling payload is scheduled at 2050 ms, one native logic frame
    # after the area's nominal two-second lifetime.
    assert SPELL_REGISTRY["RoyalDelivery"].impact_delay == pytest.approx(2.05)
    for _ in range(40):
        battle.step()
    assert not any(
        isinstance(entity, Troop)
        and entity.card_stats.name == "DeliveryRecruit"
        for entity in battle.entities.values()
    )

    battle.step()
    recruit = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.card_stats.name == "DeliveryRecruit"
    )
    # The area object creates the Recruit during the manager's object phase.
    # The dynamically extended object loop then ticks the new character in
    # that same frame, consuming 50 ms of its serialized 250 ms action delay.
    assert recruit.deploy_delay_remaining == pytest.approx(0.20)
    assert recruit.placement_pending

    position = Position(recruit.position.x, recruit.position.y)
    recruit.update(0.19, battle)
    assert recruit.deploy_delay_remaining == pytest.approx(0.01)
    assert recruit.position == position


def test_graveyard_uses_live_delay_count_radius_and_fixed_sequence():
    battle = BattleState()
    target = Position(9.0, 16.0)
    assert SPELL_REGISTRY["Graveyard"].cast(battle, 0, target)
    graveyard = next(
        entity for entity in battle.entities.values() if isinstance(entity, Graveyard)
    )

    # Direct Spell.cast starts after the universal one-second server action
    # delay, leaving 1.2 seconds of the published 2.2-second total here.
    assert graveyard.initial_spawn_delay == 1.2
    assert graveyard.spawn_deadlines == (
        1.2,
        1.7,
        2.3,
        2.8,
        3.4,
        3.9,
        4.5,
        5.0,
        5.5,
        6.1,
        6.6,
        7.2,
    )
    assert graveyard.max_skeletons == 12
    assert graveyard.spawn_radius == 4.0
    assert len(graveyard.spawn_offsets) == 12

    graveyard.update(1.19, battle)
    assert graveyard.skeletons_spawned == 0
    graveyard.update(0.01, battle)
    first = max(
        (entity for entity in battle.entities.values() if isinstance(entity, Troop)),
        key=lambda entity: entity.id,
    )
    assert first.position == Position(5.5, 16.0)
    assert (first.hitpoints, first.damage) == (81, 81)
    assert first.card_stats.hit_speed == 1100
    assert first.deploy_delay_remaining == 0.5
    assert first.placement_pending
    assert first.attack_cooldown == pytest.approx(0.5)

    # One large update must consume every elapsed fixed deadline without
    # changing the live total or sequence.
    graveyard.update(6.0, battle)
    skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    ]
    assert graveyard.skeletons_spawned == 12
    assert len(skeletons) == 12
    assert skeletons[-1].position == Position(6.5, 13.5)


def test_graveyard_pattern_rotates_for_the_opposite_player():
    positions: list[list[Position]] = []
    for player_id in (0, 1):
        battle = BattleState()
        assert SPELL_REGISTRY["Graveyard"].cast(battle, player_id, Position(9.0, 16.0))
        graveyard = next(
            entity for entity in battle.entities.values() if isinstance(entity, Graveyard)
        )
        graveyard.update(1.7, battle)
        positions.append(
            [
                entity.position
                for entity in battle.entities.values()
                if isinstance(entity, Troop) and entity.player_id == player_id
            ]
        )

    assert len(positions[0]) == len(positions[1]) == 2
    for lower, upper in zip(positions[0], positions[1]):
        # The action expressions orient Y by team but orient X only from the
        # cast center's arena half.
        assert lower.x - 9.0 == pytest.approx(upper.x - 9.0)
        assert lower.y - 16.0 == pytest.approx(-(upper.y - 16.0))


def test_graveyard_children_keep_projectile_spawn_points_in_water_and_at_edges():
    center_battle = BattleState()
    assert SPELL_REGISTRY["Graveyard"].cast(
        center_battle,
        0,
        Position(9.0, 16.0),
    )
    center_graveyard = next(
        entity
        for entity in center_battle.entities.values()
        if isinstance(entity, Graveyard)
    )
    center_graveyard.update(1.7, center_battle)
    center_skeletons = [
        entity
        for entity in center_battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    ]

    # The first fixed spawn lies on non-bridge river terrain. Native
    # projectile children stay at that requested point instead of being
    # searched onto the lower bank.
    assert center_skeletons[0].position == Position(5.5, 16.0)

    edge_battle = BattleState()
    assert SPELL_REGISTRY["Graveyard"].cast(
        edge_battle,
        0,
        Position(0.5, 16.0),
    )
    edge_graveyard = next(
        entity
        for entity in edge_battle.entities.values()
        if isinstance(entity, Graveyard)
    )
    edge_graveyard.update(1.2, edge_battle)
    edge_skeletons = [
        entity
        for entity in edge_battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    ]

    # The first requested x is negative. LogicBattle::spawnObject clamps the
    # center to 250 logic units and performs no collision-radius or terrain
    # relocation after that clamp.
    assert edge_skeletons[0].position == Position(0.25, 16.0)

    right_battle = BattleState()
    assert SPELL_REGISTRY["Graveyard"].cast(
        right_battle,
        0,
        Position(17.5, 16.0),
    )
    right_graveyard = next(
        entity
        for entity in right_battle.entities.values()
        if isinstance(entity, Graveyard)
    )
    right_graveyard.update(1.2, right_battle)
    right_skeleton = next(
        entity
        for entity in right_battle.entities.values()
        if isinstance(entity, Troop) and entity.card_stats.name == "Skeleton"
    )
    # X expressions mirror only when the cast center is strictly right of the
    # arena midpoint, then receive the symmetric outer-bound clamp.
    assert right_skeleton.position == Position(17.75, 16.0)


@pytest.mark.parametrize("player_id", [0, 1])
def test_graveyard_children_path_out_of_native_water_spawn_points(player_id):
    battle = BattleState()
    assert SPELL_REGISTRY["Graveyard"].cast(
        battle,
        player_id,
        Position(9.0, 16.0),
    )
    graveyard = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Graveyard)
    )
    graveyard.update(1.7, battle)
    skeletons = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.card_stats.name == "Skeleton"
        and entity.player_id == player_id
    ]
    water_skeleton = skeletons[0]
    start = Position(water_skeleton.position.x, water_skeleton.position.y)
    assert not battle.arena.is_walkable(start)

    graveyard.is_alive = False
    for skeleton in skeletons:
        if skeleton is not water_skeleton:
            skeleton.is_alive = False
    for _ in range(80):
        battle.step()

    assert water_skeleton.position != start
    assert battle.arena.is_walkable(water_skeleton.position)


def test_goblin_barrel_lands_in_a_fixed_player_relative_triangle():
    target = Position(9.0, 20.0)
    assert SPELL_REGISTRY["GoblinBarrel"].spawn_const_priority
    positions: list[list[Position]] = []
    for player_id in (0, 1):
        battle = BattleState()
        battle.rng.seed(19)
        assert SPELL_REGISTRY["GoblinBarrel"].cast(battle, player_id, target)
        barrel = max(
            (entity for entity in battle.entities.values() if isinstance(entity, SpawnProjectile)),
            key=lambda entity: entity.id,
        )
        rng_before = battle.rng.getstate()
        barrel.position = Position(target.x, target.y)
        barrel.update(0.01, battle)
        assert battle.rng.getstate() == rng_before

        goblins = [
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Troop) and entity.player_id == player_id
        ]
        assert len(goblins) == 3
        assert all(goblin.max_hitpoints == 202 for goblin in goblins)
        assert all(goblin.damage == 120 for goblin in goblins)
        assert all(unit_mass(goblin.card_stats) == 2.0 for goblin in goblins)
        assert all(goblin.deploy_delay_remaining == 1.1 for goblin in goblins)
        assert all(goblin.attack_cooldown == 0.4 for goblin in goblins)
        assert [
            goblin._native_target_distance_discount_sq_units
            for goblin in goblins
        ] == [(index * 80) ** 2 for index in range(3)]
        positions.append([goblin.position for goblin in goblins])

    assert positions[0] == [
        Position(9.0, 20.577),
        Position(9.499, 19.712),
        Position(8.501, 19.712),
    ]
    assert positions[1] == [
        Position(9.0, 19.423),
        Position(9.499, 20.288),
        Position(8.501, 20.288),
    ]


@pytest.mark.parametrize(
    ("player_id", "target"),
    [
        (0, Position(2.5, 23.5)),
        (1, Position(2.5, 8.5)),
    ],
)
def test_goblin_barrel_diagonal_arrival_uses_native_integer_distance(
    player_id,
    target,
):
    battle = BattleState()
    assert SPELL_REGISTRY["GoblinBarrel"].cast(battle, player_id, target)
    barrel = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, SpawnProjectile)
    )

    for _ in range(54):
        barrel.update(battle.dt, battle)
    assert barrel.is_alive
    assert not any(
        isinstance(entity, Troop) and entity.player_id == player_id
        for entity in battle.entities.values()
    )

    barrel.update(battle.dt, battle)
    assert not barrel.is_alive
    assert len(
        [
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Troop) and entity.player_id == player_id
        ]
    ) == 3


@pytest.mark.parametrize("player_id", [0, 1])
def test_goblin_barrel_payload_can_land_and_spawn_in_native_water(player_id):
    target = Position(9.0, 16.0)
    battle = BattleState()

    assert not battle.arena.is_walkable(target)
    assert SPELL_REGISTRY["GoblinBarrel"].cast(battle, player_id, target)
    barrel = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, SpawnProjectile)
    )
    barrel.position = Position(target.x, target.y)
    barrel.update(0.01, battle)

    goblins = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.player_id == player_id
    ]
    assert len(goblins) == 3
    assert any(not battle.arena.is_walkable(goblin.position) for goblin in goblins)


def test_edge_payload_formations_use_native_quarter_tile_spawn_clamp():
    for player_id in (0, 1):
        for target_x in (0.5, 17.5):
            battle = BattleState()
            target = Position(target_x, 20.0)
            assert SPELL_REGISTRY["GoblinBarrel"].cast(battle, player_id, target)
            barrel = next(
                entity
                for entity in battle.entities.values()
                if isinstance(entity, SpawnProjectile)
            )
            barrel.position = Position(target.x, target.y)
            barrel.update(0.01, battle)

            goblins = [
                entity
                for entity in battle.entities.values()
                if isinstance(entity, Troop) and entity.player_id == player_id
            ]
            assert len(goblins) == 3
            for goblin in goblins:
                assert 0.25 <= goblin.position.x <= battle.arena.width - 0.25
                assert 0.25 <= goblin.position.y <= battle.arena.height - 0.25
            edge_x = 0.25 if target_x == 0.5 else 17.75
            assert any(goblin.position.x == edge_x for goblin in goblins)
