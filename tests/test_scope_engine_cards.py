"""Scalar smoke tests for engine-scope (S122) card fixes, PLAN 2a.

Numbers are level-11 scalings of the native decoded-logic catalog values
(see src/clasher/scope_spells.py, cards/kamikaze_spirits.py,
cards/elixir_collector.py, balance._goblin_drill_entry).
"""

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.deck_pool import apply_ordered_deck_to_player
from clasher.spells import SPELL_REGISTRY
from clasher.unit_traits import is_airborne_target

FILL = ["Knight", "Archers", "Giant", "Minions", "Musketeer", "Zap", "Cannon", "Skeletons", "Goblins", "IceSpirit"]


def _battle(own, opp=("Knight",)):
    battle = BattleState()
    apply_ordered_deck_to_player(battle.players[0], (list(own) + [c for c in FILL if c not in own])[:8])
    apply_ordered_deck_to_player(battle.players[1], (list(opp) + [c for c in FILL if c not in opp])[:8])
    battle.players[0].elixir = 10.0
    battle.players[1].elixir = 10.0
    return battle


def _units(battle, player_id, name=None):
    return [
        e for e in battle.entities.values()
        if e.player_id == player_id and isinstance(e, (Troop, Building)) and e.is_alive
        and e.card_stats.name not in ("Tower", "KingTower")
        and (name is None or e.card_stats.name == name)
    ]


def _crown(battle, player_id, slot):
    return next(e for e in battle.entities.values() if getattr(e, "_crown_tower_slot", None) == slot and e.player_id == player_id)


def _steps(battle, n):
    for _ in range(n):
        battle.step()


def test_vines_snares_three_highest_hp_targets_and_grounds_air():
    spell = SPELL_REGISTRY["Vines"]
    assert (spell.dot_damage, spell.crown_dot_damage, spell.radius) == (153.0, 35.0, 2.5)
    battle = _battle(["Vines"], ["Knight", "Minions"])
    assert battle.deploy_card(1, "Knight", Position(8.5, 20.5))
    assert battle.deploy_card(1, "Minions", Position(9.5, 20.5))
    _steps(battle, 30)
    knight = _units(battle, 1, "Knight")[0]
    minions = _units(battle, 1, "Minion") or _units(battle, 1, "Minions")
    hp0 = knight.hitpoints
    assert battle.deploy_card(0, "Vines", Position(9.0, 19.5))
    _steps(battle, 26)  # selection at 0.9 s, actions at +0/50/150 ms
    assert knight.stun_timer > 0
    grounded = [m for m in minions if getattr(m, "_vines_grounded", False)]
    assert len(grounded) == 2  # knight + 2 minions = 3 targets
    assert all(not is_airborne_target(m) for m in grounded)
    _steps(battle, 39)
    assert hp0 - knight.hitpoints == 2 * 153
    assert all(not m.is_alive for m in grounded)  # 306 > 230


def test_vines_on_crown_tower_uses_crown_damage():
    battle = _battle(["Vines"])
    tower = _crown(battle, 1, "left")
    hp0 = tower.hitpoints
    assert battle.deploy_card(0, "Vines", Position(3.5, 25.5))
    _steps(battle, 80)
    assert hp0 - tower.hitpoints == 2 * 35


def test_void_damage_tiers_by_target_count():
    spell = SPELL_REGISTRY["DarkMagic"]
    assert spell.pulse_times == (1.5, 2.5, 3.5)
    assert spell.tier_damage == (340.0, 160.0, 76.0)
    assert spell.tier_crown_damage == (48.0, 25.0, 17.0)
    # Single crown-tower target: three heavy pulses.
    battle = _battle(["DarkMagic"])
    tower = _crown(battle, 1, "left")
    hp0 = tower.hitpoints
    assert battle.deploy_card(0, "DarkMagic", Position(3.5, 25.5))
    _steps(battle, 100)
    assert hp0 - tower.hitpoints == 3 * 48


def test_void_splits_damage_over_many_targets():
    battle = _battle(["DarkMagic"], ["Skeletons", "Knight"])
    assert battle.deploy_card(1, "Skeletons", Position(9.5, 22.5))
    assert battle.deploy_card(1, "Knight", Position(9.5, 23.5))
    _steps(battle, 2)
    knight = _units(battle, 1, "Knight")[0]
    skeletons = _units(battle, 1, "Skeleton") or _units(battle, 1, "Skeletons")
    for unit in [knight, *skeletons]:
        unit.apply_stun(5.0)
        unit.apply_slow(5.0, 0.0)
    hp0 = knight.hitpoints
    assert battle.deploy_card(0, "DarkMagic", Position(9.5, 22.5))
    _steps(battle, 40)  # first pulse at 1.5 s + 100 ms, second at 2.6 s
    assert hp0 - knight.hitpoints == 160  # 4 targets -> medium tier


def test_goblin_curse_dot_and_conversion():
    spell = SPELL_REGISTRY["GoblinCurse"]
    assert (spell.dot_damage, spell.crown_dot_damage, spell.radius, spell.duration) == (35.0, 10.0, 3.0, 6.0)
    battle = _battle(["GoblinCurse"], ["Knight"])
    assert battle.deploy_card(1, "Knight", Position(9.5, 18.5))
    _steps(battle, 10)
    knight = _units(battle, 1, "Knight")[0]
    assert battle.deploy_card(0, "GoblinCurse", Position(9.5, 18.0))
    _steps(battle, 4)
    assert not _units(battle, 0, "Goblin")
    knight.take_damage(knight.hitpoints)
    _steps(battle, 2)
    goblins = _units(battle, 0, "Goblin")
    assert len(goblins) == 1 and goblins[0].player_id == 0
    assert goblins[0].hitpoints == 202


def test_goblin_curse_no_conversion_after_buff_expired():
    battle = _battle(["GoblinCurse"], ["Knight"])
    assert battle.deploy_card(1, "Knight", Position(9.5, 18.5))
    _steps(battle, 10)
    knight = _units(battle, 1, "Knight")[0]
    assert battle.deploy_card(0, "GoblinCurse", Position(9.5, 18.0))
    _steps(battle, 3)
    knight.position = Position(9.5, 10.5)  # leave the field
    _steps(battle, 6)
    knight.take_damage(knight.hitpoints)
    _steps(battle, 2)
    assert not _units(battle, 0, "Goblin")


def _heal_scenario(with_heal):
    battle = _battle(["Heal", "Giant"], ["Knight"])
    assert battle.deploy_card(0, "Giant", Position(9.5, 14.5))
    assert battle.deploy_card(1, "Knight", Position(9.5, 18.5))
    _steps(battle, 60)
    giant = _units(battle, 0, "Giant")[0]
    knight = _units(battle, 1, "Knight")[0]
    giant.hitpoints -= 1000
    if with_heal:
        assert battle.deploy_card(0, "Heal", Position(9.5, 12.5))
    _steps(battle, 120)
    return battle, giant, knight


def test_heal_spirit_is_a_kamikaze_troop_that_heals():
    assert "Heal" not in SPELL_REGISTRY
    battle, giant, knight = _heal_scenario(True)
    assert battle.card_loader.get_card("Heal").card_type == "Troop"
    _, control_giant, control_knight = _heal_scenario(False)
    assert not _units(battle, 0, "Heal")
    assert control_knight.hitpoints - knight.hitpoints == 110  # 43 base at L11
    assert giant.hitpoints - control_giant.hitpoints == 400  # 4 x int(401 x 0.25)


def test_fire_spirit_is_kamikaze():
    battle = _battle(["FireSpirits"], ["Knight"])
    assert battle.deploy_card(1, "Knight", Position(9.5, 18.5))
    _steps(battle, 20)
    knight = _units(battle, 1, "Knight")[0]
    hp0 = knight.hitpoints
    assert battle.deploy_card(0, "FireSpirits", Position(9.5, 13.5))
    _steps(battle, 120)
    assert not _units(battle, 0, "FireSpirits")
    assert hp0 - knight.hitpoints == 207


def test_elixir_collector_generates_elixir_and_pays_on_death():
    battle = _battle(["Elixir Collector"])
    assert battle.deploy_card(0, "Elixir Collector", Position(9.5, 9.5))
    collector = _units(battle, 0)[0]
    gains = []
    for _ in range(int(100 / 0.05)):
        before = battle.players[0].elixir
        battle.players[0].elixir = 0.0
        battle.step()
        if battle.players[0].elixir >= 0.9:
            gains.append(round(battle.time, 2))
        battle.players[0].elixir = before
    assert len(gains) == 8  # 7 x 13 s over the 93 s lifetime + 1 on expiry
    assert abs((gains[1] - gains[0]) - 13.0) < 1e-6
    assert not collector.is_alive


def test_goblin_drill_digs_to_enemy_side_and_spawns_goblins():
    battle = _battle(["GoblinDrill"])
    stats = battle.card_loader.get_card("GoblinDrill")
    assert stats.card_type == "Building" and stats.can_deploy_on_enemy_side
    assert battle.deploy_card(0, "GoblinDrill", Position(3.5, 21.5))
    drill = _units(battle, 0, "GoblinDrill")[0]
    assert drill.position.y < 6  # starts at the King Tower
    _steps(battle, 90)
    assert abs(drill.position.y - 21.0) < 1.0 and drill.deploy_delay_remaining == 0
    _steps(battle, 120)
    assert len([e for e in battle.entities.values() if e.player_id == 0 and getattr(e.card_stats, "name", "") == "Goblin"]) >= 3


def test_goblin_drill_emergence_damages_nearby_enemies():
    battle = _battle(["GoblinDrill"], ["Knight"])
    assert battle.deploy_card(1, "Knight", Position(14.5, 22.5))
    assert battle.deploy_card(0, "GoblinDrill", Position(14.5, 21.5))
    _steps(battle, 2)
    knight = _units(battle, 1, "Knight")[0]
    drill = _units(battle, 0, "GoblinDrill")[0]
    knight.apply_stun(10.0)
    knight.apply_slow(10.0, 0.0)
    losses = []
    for _ in range(100):
        before = knight.hitpoints
        battle.step()
        losses.append((drill.deploy_delay_remaining == 0, before - knight.hitpoints))
    # GoblinDrillDamage: 33 base -> 84 at L11 on emergence.
    assert (True, 84) in losses
    assert all(loss == 0 for emerged, loss in losses if not emerged)


def test_berserker_deals_damage_and_native_masses():
    from clasher.unit_traits import unit_mass

    battle = _battle(["Berserker"], ["Knight"])
    assert battle.deploy_card(0, "Berserker", Position(9.5, 14.5))
    assert battle.deploy_card(1, "Knight", Position(9.5, 17.5))
    berserker = _units(battle, 0, "Berserker")[0]
    knight = _units(battle, 1, "Knight")[0]
    assert berserker.range > 0 and unit_mass(berserker.card_stats) == 2
    hits = []
    for _ in range(120):
        before = knight.hitpoints
        battle.step()
        if before != knight.hitpoints:
            hits.append((battle.tick, before - knight.hitpoints))
    assert hits and all(dmg == 102 for _, dmg in hits)  # 40 base at L11
    assert len({b[0] - a[0] for a, b in zip(hits, hits[1:])} - {12}) == 0  # 600 ms


def test_furnace_walks_and_spawns_deploying_kamikaze_spirits():
    from clasher.mechanics.shared import PeriodicSpawner

    battle = _battle(["FirespiritHut"])
    assert battle.deploy_card(0, "FirespiritHut", Position(3.5, 4.5))
    furnace = _units(battle, 0, "FirespiritHut")[0]
    assert isinstance(furnace, Troop) and not isinstance(furnace, Building)
    initial_y = furnace.position.y
    _steps(battle, 50)
    assert furnace.position.y > initial_y
    production = next(m for m in furnace.mechanics if isinstance(m, PeriodicSpawner))
    assert (production.spawn_interval_ms, production.first_spawn_delay_ms) == (5000, 3050)
    # Exercise the production clock without troop combat hiding the children.
    production.time_since_spawn_ms = 0
    production.on_object_tick(furnace, 3000)
    assert not _units(battle, 0, "FireSpirits")
    production.on_object_tick(furnace, 50)
    spirit = _units(battle, 0, "FireSpirits")[0]
    assert spirit.deploy_delay_remaining == 0.5
    assert spirit.card_stats.summon_character_data["kamikaze"]
    production.on_object_tick(furnace, 5000)
    assert len(_units(battle, 0, "FireSpirits")) == 2


def test_miner_retains_live_runtime_crown_damage():
    # runtime-update and device-update-backup 15.535.86 both specify -80%;
    # the older decoded APK file says -75% and must not replace this value.
    battle = _battle(["Miner"])
    assert battle.deploy_card(0, "Miner", Position(2.5, 23.5))
    tower = _crown(battle, 1, "left")
    losses = []
    for _ in range(220):
        before = tower.hitpoints
        battle.step()
        if tower.hitpoints < before:
            losses.append(before - tower.hitpoints)
    assert len(losses) >= 2 and set(losses) == {39}


def test_goblin_hut_sleeps_wakes_spawns_and_resets_after_enemy_leaves():
    from clasher.cards.goblin_hut import GoblinHutProduction

    battle = _battle(["GoblinHut"])
    assert battle.deploy_card(0, "GoblinHut", Position(9.5, 10.5))
    hut = _units(battle, 0, "GoblinHut")[0]
    _steps(battle, 100)
    assert not _units(battle, 0, "SpearGoblin")
    production = next(m for m in hut.mechanics if isinstance(m, GoblinHutProduction))
    battle._spawn_unit_at_position(Position(9.5, 15.5), 1, battle.card_loader.get_card("Knight"), deploy_delay_override=0)
    knight = _units(battle, 1, "Knight")[0]
    knight.position = Position(9.5, 15.5)  # exact wake-range fixture, after terrain snapping
    production.on_object_tick(hut, 950)
    assert not _units(battle, 0, "SpearGoblin")
    production.on_object_tick(hut, 50)
    goblin = _units(battle, 0, "SpearGoblin")[0]
    assert goblin.deploy_delay_remaining == 0.5 and goblin.hitpoints == 133
    assert abs(goblin.position.distance_to(hut.position) - 1.2) < 0.003
    assert goblin.position.y > hut.position.y
    production.on_object_tick(hut, 2200)
    assert len(_units(battle, 0, "SpearGoblin")) == 2
    knight.position = Position(9.5, 25.5)
    production.on_object_tick(hut, 5000)
    assert len(_units(battle, 0, "SpearGoblin")) == 2
    knight.position = Position(9.5, 15.5)
    production.on_object_tick(hut, 950)
    assert len(_units(battle, 0, "SpearGoblin")) == 2
    production.on_object_tick(hut, 50)
    assert len(_units(battle, 0, "SpearGoblin")) == 3


def test_mighty_miner_ability_switches_lane_and_leaves_delayed_bomb():
    from clasher.entities import TimedExplosive

    battle = _battle(["MightyMiner"])
    assert battle.deploy_card(0, "MightyMiner", Position(3.5, 10.5))
    _steps(battle, 25)
    miner = _units(battle, 0, "MightyMiner")[0]
    before = Position(miner.position.x, miner.position.y)
    elixir = battle.players[0].elixir
    assert battle.can_activate_champion_ability(0)
    assert battle.activate_champion_ability(0)
    assert battle.players[0].elixir == elixir - 1
    assert not battle.activate_champion_ability(0)
    _steps(battle, 9)
    assert not any(isinstance(e, TimedExplosive) for e in battle.entities.values())
    _steps(battle, 1)
    bomb = next(e for e in battle.entities.values() if isinstance(e, TimedExplosive))
    assert bomb.position.distance_to(before) < 0.01
    assert (bomb.explosion_damage, bomb.explosion_radius, bomb.knockback_distance) == (332, 3, 1.8)
    assert not miner.is_targetable_by(1)
    hp = miner.hitpoints
    miner.take_damage(100, source_kind="Fireball")
    assert miner.hitpoints == hp
    _steps(battle, 50)
    assert miner.position.x > 12 and miner.is_targetable_by(1)
    assert not bomb.is_alive
    assert not battle.can_activate_champion_ability(0)


def test_goblinstein_tether_uses_doctor_ownership_geometry_and_live_damage():
    from clasher.cards.c56_champions import GoblinsteinTether

    battle = _battle(["Goblinstein"])
    assert battle.deploy_card(0, "Goblinstein", Position(7.5, 10.5))
    _steps(battle, 25)
    doctor = _units(battle, 0, "Goblinstein_doctor")[0]
    monster = _units(battle, 0, "Goblinstein")[0]
    tether = next(m for m in doctor.mechanics if isinstance(m, GoblinsteinTether))
    assert tether.monster_id == monster.id
    doctor.position = Position(7.5, 10.5)
    monster.position = Position(7.5, 15.5)
    battle._spawn_unit_at_position(Position(7.5, 12.5), 1, battle.card_loader.get_card("Knight"), deploy_delay_override=0, snap_to_valid=False)
    knight = _units(battle, 1, "Knight")[0]
    hp = knight.hitpoints
    before = battle.players[0].elixir
    assert battle.activate_champion_ability(0)
    assert battle.players[0].elixir == before - 2
    # Drive only the ability clock so ordinary attacks cannot hide pulse damage.
    for tick in range(1, 81):
        battle.time += 0.05
        tether.on_object_tick(doctor, 50)
    assert hp - knight.hitpoints == 8 * 94  # live base 37 at L11
    battle.time += 0.05
    tether.on_object_tick(doctor, 50)
    assert not tether.ability.is_active and not battle.can_activate_champion_ability(0)
    monster.take_damage(monster.hitpoints)
    tether.on_object_tick(doctor, 0)
    assert tether.anchor == monster.position
    doctor.take_damage(doctor.hitpoints)
    assert not battle.can_activate_champion_ability(0)


def test_goblin_hut_does_not_wake_for_effect_containers():
    from clasher.entities import TimedExplosive
    from clasher.cards.goblin_hut import GoblinHutProduction

    battle = _battle(["GoblinHut"])
    assert battle.deploy_card(0, "GoblinHut", Position(9.5, 10.5))
    _steps(battle, 30)
    hut = _units(battle, 0, "GoblinHut")[0]
    bomb = TimedExplosive(id=battle.next_entity_id, position=Position(9.5, 12.5), player_id=1,
                          card_stats=battle.card_loader.get_card("Balloon"), hitpoints=1, max_hitpoints=1,
                          damage=0, range=0, sight_range=0)
    battle.entities[bomb.id] = bomb
    battle.next_entity_id += 1
    production = next(m for m in hut.mechanics if isinstance(m, GoblinHutProduction))
    production.on_object_tick(hut, 5000)
    assert not _units(battle, 0, "SpearGoblin")
