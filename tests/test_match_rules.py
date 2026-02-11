import os
import sys
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop


def _get_tower(battle: BattleState, player_id: int, tower: str) -> Building:
    if tower == "king":
        pos = battle.arena.BLUE_KING_TOWER if player_id == 0 else battle.arena.RED_KING_TOWER
    elif tower == "left":
        pos = battle.arena.BLUE_LEFT_TOWER if player_id == 0 else battle.arena.RED_LEFT_TOWER
    else:
        pos = battle.arena.BLUE_RIGHT_TOWER if player_id == 0 else battle.arena.RED_RIGHT_TOWER
    for entity in battle.entities.values():
        if isinstance(entity, Building) and entity.player_id == player_id:
            if entity.position.x == pos.x and entity.position.y == pos.y:
                return entity
    raise AssertionError(f"tower not found {tower} p{player_id}")


def _prepare_single_card(battle: BattleState, player_id: int, card_name: str) -> None:
    player = battle.players[player_id]
    player.elixir = 10.0
    player.hand = [card_name]
    player.deck = [card_name]
    player.cycle_queue = deque()


def test_king_tower_starts_inactive_and_activates_when_hit():
    battle = BattleState()
    blue_king = _get_tower(battle, 0, "king")
    assert getattr(blue_king, "_tower_active", True) is False
    blue_king.take_damage(1)
    assert getattr(blue_king, "_tower_active", False) is True


def test_king_tower_activates_when_princess_tower_destroyed():
    battle = BattleState()
    blue_king = _get_tower(battle, 0, "king")
    blue_left = _get_tower(battle, 0, "left")
    assert getattr(blue_king, "_tower_active", True) is False
    blue_left.take_damage(blue_left.hitpoints)
    battle.step()
    assert getattr(blue_king, "_tower_active", False) is True


def test_deploy_delay_prevents_immediate_troop_action():
    battle = BattleState()
    _prepare_single_card(battle, 0, "Knight")
    assert battle.deploy_card(0, "Knight", Position(9.0, 10.0))
    knights = [e for e in battle.entities.values() if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Knight"]
    assert len(knights) == 1
    knight = knights[0]
    assert knight.deploy_delay_remaining > 0
    start = (knight.position.x, knight.position.y)
    # Step shorter than full deploy delay.
    for _ in range(10):
        battle.step()
    assert knight.deploy_delay_remaining >= 0
    assert (knight.position.x, knight.position.y) == start


def test_miner_can_deploy_outside_normal_zone():
    battle = BattleState()
    _prepare_single_card(battle, 0, "Miner")
    # Enemy-side deployment that normal troops cannot use.
    assert battle.deploy_card(0, "Miner", Position(9.0, 24.0))


def test_cannot_deploy_non_spell_on_building_footprint():
    battle = BattleState()
    player = battle.players[0]
    player.elixir = 10.0
    player.hand = ["Cannon", "Knight"]
    player.deck = ["Cannon", "Knight"]
    player.cycle_queue = deque()
    assert battle.deploy_card(0, "Cannon", Position(9.0, 10.0))
    assert not battle.deploy_card(0, "Knight", Position(9.0, 10.0))


def test_ground_troop_does_not_move_through_building_space():
    battle = BattleState()
    p0 = battle.players[0]
    p1 = battle.players[1]
    p0.elixir = 20.0
    p1.elixir = 20.0
    p0.hand = ["Cannon", "Knight"]
    p0.deck = ["Cannon", "Knight"]
    p0.cycle_queue = deque()
    p1.hand = ["Knight"]
    p1.deck = ["Knight"]
    p1.cycle_queue = deque()

    assert battle.deploy_card(0, "Cannon", Position(9.0, 10.0))
    assert battle.deploy_card(0, "Knight", Position(9.0, 8.0))
    assert battle.deploy_card(1, "Knight", Position(9.0, 24.0))

    cannon = next(
        e for e in battle.entities.values()
        if isinstance(e, Building) and e.player_id == 0 and e.card_stats.name == "Cannon"
    )
    blue_knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Knight"
    )

    for _ in range(310):
        battle.step()
        troop_r = getattr(blue_knight.card_stats, "collision_radius", 0.5) or 0.5
        building_r = getattr(cannon.card_stats, "collision_radius", 1.0) or 1.0
        assert blue_knight.position.distance_to(cannon.position) >= (troop_r + building_r) * 0.9


def test_elixir_phase_regen_rates():
    battle = BattleState()
    player = battle.players[0]
    player.elixir = 0.0
    # Regular
    for _ in range(30):
        battle.step()
    regular = player.elixir
    # Double
    battle.time = 180.0
    player.elixir = 0.0
    for _ in range(30):
        battle.step()
    double = player.elixir
    # Triple
    battle.time = 240.0
    player.elixir = 0.0
    for _ in range(30):
        battle.step()
    triple = player.elixir
    assert regular > 0
    assert double > regular
    assert triple > double


def test_eight_card_cycle_rotates_played_card_to_back():
    battle = BattleState()
    player = battle.players[0]
    cycle = ["Knight", "Archers", "Giant", "Minions", "Musketeer", "Skeletons", "IceSpirit", "Fireball"]
    player.elixir = 10.0
    player.deck = cycle.copy()
    player.hand = cycle[:4].copy()
    player.cycle_queue = deque(cycle[4:])

    assert player.get_next_card() == "Musketeer"
    assert battle.deploy_card(0, "Knight", Position(9.0, 10.0))
    assert "Musketeer" in player.hand
    assert player.get_next_card() == "Skeletons"
    assert player.cycle_queue[-1] == "Knight"


def test_sudden_death_and_tiebreaker_damage():
    battle = BattleState()
    battle.time = 300.0
    battle._check_win_conditions()
    assert battle.sudden_death
    assert not battle.game_over

    # No crown change; force tiebreak window and uneven tower damage.
    red_left = _get_tower(battle, 1, "left")
    red_left.hitpoints -= 200
    battle.time = 360.0
    battle._check_win_conditions()
    assert battle.game_over
    assert battle.winner == 0


def test_stun_resets_attack_timer():
    battle = BattleState()
    _prepare_single_card(battle, 0, "Knight")
    assert battle.deploy_card(0, "Knight", Position(9.0, 10.0))
    knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Knight"
    )
    knight.attack_cooldown = 0.0
    knight.apply_stun(0.5)
    assert knight.attack_cooldown >= (knight.card_stats.hit_speed / 1000.0)


def test_slow_increases_attack_interval():
    battle = BattleState()
    _prepare_single_card(battle, 0, "Knight")
    assert battle.deploy_card(0, "Knight", Position(9.0, 10.0))
    knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Knight"
    )
    knight.deploy_delay_remaining = 0.0
    base_interval = knight.get_attack_interval_seconds()
    knight.apply_slow(2.0, 0.65)
    slowed_interval = knight.get_attack_interval_seconds()
    assert slowed_interval > base_interval

    for _ in range(80):
        battle.step()
    assert knight.slow_timer <= 0
    assert abs(knight.get_attack_interval_seconds() - base_interval) < 0.01


def test_enemy_ground_troops_separate_when_overlapping():
    battle = BattleState()
    knight_stats = battle.card_loader.get_card("Knight")
    assert knight_stats is not None

    battle._spawn_troop(Position(3.5, 16.0), 0, knight_stats)
    battle._spawn_troop(Position(3.5, 16.0), 1, knight_stats)

    troops = [e for e in battle.entities.values() if isinstance(e, Troop) and e.card_stats.name == "Knight"]
    assert len(troops) >= 2
    a, b = troops[0], troops[1]
    a.deploy_delay_remaining = 0.0
    b.deploy_delay_remaining = 0.0

    battle.step()
    assert a.position.distance_to(b.position) > 0


def test_ground_only_unit_cannot_attack_air():
    battle = BattleState()
    knight_stats = battle.card_loader.get_card("Knight")
    minions_stats = battle.card_loader.get_card("Minions")
    assert knight_stats is not None
    assert minions_stats is not None

    battle._spawn_troop(Position(9.0, 12.0), 0, knight_stats)
    battle._spawn_troop(Position(9.0, 13.0), 1, minions_stats)

    blue_knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Knight"
    )
    red_minions = [
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 1 and e.card_stats.name == "Minions"
    ]
    assert len(red_minions) >= 1
    for troop in [blue_knight, *red_minions]:
        troop.deploy_delay_remaining = 0.0

    minion_hp_before = [m.hitpoints for m in red_minions]
    for _ in range(120):
        battle.step()

    assert [m.hitpoints for m in red_minions] == minion_hp_before


def test_balloon_death_spawns_timed_explosive():
    battle = BattleState()
    p0 = battle.players[0]
    p0.elixir = 10.0
    p0.hand = ["Balloon"]
    p0.deck = ["Balloon"]
    p0.cycle_queue = deque()

    assert battle.deploy_card(0, "Balloon", Position(9.0, 10.0))
    balloon = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Balloon"
    )
    balloon.take_damage(balloon.hitpoints)
    battle.step()

    timed_explosives = [e for e in battle.entities.values() if type(e).__name__ == "TimedExplosive"]
    assert len(timed_explosives) >= 1
    assert timed_explosives[0].explosion_timer >= 2.5


def test_battle_ram_death_spawns_barbarians():
    battle = BattleState()
    _prepare_single_card(battle, 0, "BattleRam")
    assert battle.deploy_card(0, "BattleRam", Position(9.0, 10.0))
    ram = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "BattleRam"
    )
    ram.take_damage(ram.hitpoints)
    battle.step()
    barbarians = [
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Barbarian"
    ]
    assert len(barbarians) >= 2


def test_golem_death_spawns_golemites():
    battle = BattleState()
    _prepare_single_card(battle, 0, "Golem")
    assert battle.deploy_card(0, "Golem", Position(9.0, 10.0))
    golem = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Golem"
    )
    golem.take_damage(golem.hitpoints)
    battle.step()
    golemites = [
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Golemite"
    ]
    assert len(golemites) >= 2


def test_skeleton_barrel_death_spawns_skeletons():
    battle = BattleState()
    _prepare_single_card(battle, 0, "SkeletonBarrel")
    assert battle.deploy_card(0, "SkeletonBarrel", Position(9.0, 10.0))
    barrel = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "SkeletonBalloon"
    )
    barrel.take_damage(barrel.hitpoints)
    for _ in range(40):
        battle.step()
    skeletons = [
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Skeleton"
    ]
    assert len(skeletons) >= 1


def test_freeze_spell_immobilizes_target():
    battle = BattleState()
    p0 = battle.players[0]
    p1 = battle.players[1]
    p0.elixir = 10.0
    p1.elixir = 10.0
    p0.hand = ["Freeze"]
    p0.deck = ["Freeze"]
    p0.cycle_queue = deque()
    p1.hand = ["Knight"]
    p1.deck = ["Knight"]
    p1.cycle_queue = deque()

    assert battle.deploy_card(1, "Knight", Position(9.0, 18.0))
    knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 1 and e.card_stats.name == "Knight"
    )
    knight.deploy_delay_remaining = 0.0
    assert battle.deploy_card(0, "Freeze", Position(9.0, 18.0))

    for _ in range(15):
        battle.step()
        if knight.stun_timer > 0:
            break
    assert knight.stun_timer > 0
    assert knight.speed == 0


def test_lumberjack_death_drops_rage_buff():
    battle = BattleState()
    p0 = battle.players[0]
    p0.elixir = 20.0
    p0.hand = ["Lumberjack", "Knight"]
    p0.deck = ["Lumberjack", "Knight"]
    p0.cycle_queue = deque()
    assert battle.deploy_card(0, "Lumberjack", Position(9.0, 10.0))
    assert battle.deploy_card(0, "Knight", Position(10.0, 10.0))

    lumberjack = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "AxeMan"
    )
    ally_knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Knight"
    )
    ally_knight.deploy_delay_remaining = 0.0

    lumberjack.take_damage(lumberjack.hitpoints)
    battle.step()
    assert ally_knight.attack_speed_buff_multiplier > 1.0


def test_zap_uses_reduced_crown_tower_damage():
    battle = BattleState()
    p0 = battle.players[0]
    p0.elixir = 10.0
    p0.hand = ["Zap"]
    p0.deck = ["Zap"]
    p0.cycle_queue = deque()

    knight_stats = battle.card_loader.get_card("Knight")
    assert knight_stats is not None
    battle._spawn_troop(Position(3.5, 25.5), 1, knight_stats)
    enemy_knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 1 and e.card_stats.name == "Knight"
    )
    enemy_knight.deploy_delay_remaining = 0.0
    tower = _get_tower(battle, 1, "left")

    tower_hp_before = tower.hitpoints
    knight_hp_before = enemy_knight.hitpoints
    assert battle.deploy_card(0, "Zap", Position(3.5, 25.5))
    battle.step()

    tower_damage = tower_hp_before - tower.hitpoints
    knight_damage = knight_hp_before - enemy_knight.hitpoints
    assert knight_damage > 0
    assert tower_damage > 0
    assert tower_damage < knight_damage


def test_ice_wizard_projectile_applies_slow():
    battle = BattleState()
    p0 = battle.players[0]
    p1 = battle.players[1]
    p0.elixir = 10.0
    p1.elixir = 10.0
    p0.hand = ["IceWizard"]
    p0.deck = ["IceWizard"]
    p0.cycle_queue = deque()
    p1.hand = ["Knight"]
    p1.deck = ["Knight"]
    p1.cycle_queue = deque()

    assert battle.deploy_card(0, "IceWizard", Position(9.0, 14.0))
    assert battle.deploy_card(1, "Knight", Position(9.0, 18.0))

    red_knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 1 and e.card_stats.name == "Knight"
    )
    for _ in range(220):
        battle.step()
        if red_knight.slow_timer > 0:
            break
    assert red_knight.slow_timer > 0


def test_bandit_dash_invulnerability_blocks_damage():
    battle = BattleState()
    p0 = battle.players[0]
    p0.elixir = 10.0
    p0.hand = ["Bandit"]
    p0.deck = ["Bandit"]
    p0.cycle_queue = deque()
    assert battle.deploy_card(0, "Bandit", Position(9.0, 10.0))

    bandit = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name in {"Assassin", "Bandit"}
    )
    current_ms = int(battle.time * 1000)
    bandit._bandit_invulnerable_until = current_ms + 1000
    hp_before = bandit.hitpoints
    bandit.take_damage(999)
    assert bandit.hitpoints == hp_before


def test_witch_periodic_skeleton_spawn():
    battle = BattleState()
    p0 = battle.players[0]
    p0.elixir = 10.0
    p0.hand = ["Witch"]
    p0.deck = ["Witch"]
    p0.cycle_queue = deque()
    assert battle.deploy_card(0, "Witch", Position(9.0, 10.0))

    baseline = len([e for e in battle.entities.values() if isinstance(e, Troop) and e.player_id == 0])
    # Deploy delay (~1s) + periodic spawn interval (7s) + margin.
    for _ in range(320):
        battle.step()
    after = len([e for e in battle.entities.values() if isinstance(e, Troop) and e.player_id == 0])
    assert after > baseline


def test_tombstone_periodic_and_death_spawn():
    battle = BattleState()
    p0 = battle.players[0]
    p0.elixir = 10.0
    p0.hand = ["Tombstone"]
    p0.deck = ["Tombstone"]
    p0.cycle_queue = deque()
    assert battle.deploy_card(0, "Tombstone", Position(9.0, 10.0))

    tombstone = next(
        e for e in battle.entities.values()
        if isinstance(e, Building) and e.player_id == 0 and e.card_stats.name == "Tombstone"
    )
    baseline = len([e for e in battle.entities.values() if isinstance(e, Troop) and e.player_id == 0])
    # Deploy delay (~1s) + periodic spawn interval (3.5s) + margin.
    for _ in range(220):
        battle.step()
    spawned = len([e for e in battle.entities.values() if isinstance(e, Troop) and e.player_id == 0])
    assert spawned > baseline

    tombstone.take_damage(tombstone.hitpoints)
    battle.step()
    spawned_after_death = len([e for e in battle.entities.values() if isinstance(e, Troop) and e.player_id == 0])
    assert spawned_after_death >= spawned


def test_lava_hound_death_spawns_lava_pups():
    battle = BattleState()
    _prepare_single_card(battle, 0, "LavaHound")
    assert battle.deploy_card(0, "LavaHound", Position(9.0, 10.0))

    hound = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "LavaHound"
    )
    hound.take_damage(hound.hitpoints)
    battle.step()

    pups = [
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "LavaPups"
    ]
    assert len(pups) >= 6


def test_night_witch_periodic_and_death_bats():
    battle = BattleState()
    _prepare_single_card(battle, 0, "NightWitch")
    assert battle.deploy_card(0, "NightWitch", Position(9.0, 10.0))

    witch = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "DarkWitch"
    )
    baseline_bats = len(
        [
            e for e in battle.entities.values()
            if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name in {"Bat", "Bats"}
        ]
    )
    # Deploy delay (~1s) + 5s periodic spawn interval + margin.
    for _ in range(220):
        battle.step()
    periodic_bats = len(
        [
            e for e in battle.entities.values()
            if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name in {"Bat", "Bats"}
        ]
    )
    assert periodic_bats > baseline_bats

    witch.take_damage(witch.hitpoints)
    battle.step()
    bats_after_death = len(
        [
            e for e in battle.entities.values()
            if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name in {"Bat", "Bats"}
        ]
    )
    assert bats_after_death >= periodic_bats


def test_dark_prince_shield_absorbs_first_damage():
    battle = BattleState()
    _prepare_single_card(battle, 0, "DarkPrince")
    assert battle.deploy_card(0, "DarkPrince", Position(9.0, 10.0))

    dark_prince = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "DarkPrince"
    )
    hp_before = dark_prince.hitpoints
    dark_prince.take_damage(50)
    assert dark_prince.hitpoints == hp_before


def test_prince_charge_uses_special_damage_on_first_hit():
    battle = BattleState()
    p0 = battle.players[0]
    p1 = battle.players[1]
    p0.elixir = 10.0
    p1.elixir = 10.0
    p0.hand = ["Prince"]
    p0.deck = ["Prince"]
    p0.cycle_queue = deque()
    p1.hand = ["Giant"]
    p1.deck = ["Giant"]
    p1.cycle_queue = deque()

    assert battle.deploy_card(0, "Prince", Position(9.0, 8.0))
    giant_stats = battle.card_loader.get_card("Giant")
    assert giant_stats is not None
    battle._spawn_troop(Position(9.0, 12.0), 1, giant_stats)

    prince = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Prince"
    )
    giant = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 1 and e.card_stats.name == "Giant"
    )
    prince.deploy_delay_remaining = 0.0
    giant.deploy_delay_remaining = 0.0

    hp_before = giant.hitpoints
    for _ in range(220):
        battle.step()
        if giant.hitpoints < hp_before:
            break
    damage_dealt = hp_before - giant.hitpoints
    assert damage_dealt >= prince.damage
