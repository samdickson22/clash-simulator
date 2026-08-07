import os
import sys
from collections import deque

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, Building, Projectile, Troop
from clasher.spells import SPELL_REGISTRY


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


def _finish_deployment(entity: Troop | Building) -> None:
    """Advance a hand-played entity to its active state for mechanics-only tests."""
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity.on_spawn()


def _spawn_king_activation_target(battle: BattleState) -> tuple[Building, Troop]:
    blue_king = _get_tower(battle, 0, "king")
    knight_stats = battle.card_loader.get_card("Knight")
    assert knight_stats is not None
    battle._spawn_troop(Position(9.0, 7.0), 1, knight_stats)
    knight = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == 1
        and entity.card_stats.name == "Knight"
    )
    _finish_deployment(knight)
    knight.speed = 0.0
    return blue_king, knight


def _king_has_launched(battle: BattleState) -> bool:
    return any(
        isinstance(entity, Projectile) and entity.source_name == "KingTower"
        for entity in battle.entities.values()
    )


def test_default_battle_timeline_starts_on_playable_frame_with_six_elixir():
    battle = BattleState()

    assert battle.time == 0.0
    assert battle.tick == 0
    assert [player.elixir for player in battle.players] == [6.0, 6.0]


@pytest.mark.parametrize(
    ("start_time", "cooldown_ms", "cooldown_ticks"),
    ((0.0, 1000, 20), (120.0, 500, 10), (240.0, 350, 7)),
)
def test_default_timeline_delays_empty_hand_slot_refills(
    start_time,
    cooldown_ms,
    cooldown_ticks,
):
    battle = BattleState()
    player = battle.players[0]
    cycle = [
        "Knight", "Archers", "Fireball", "Cannon",
        "Giant", "Minions", "Zap", "Musketeer",
    ]
    player.elixir = 20.0
    player.hand = cycle[:4]
    player.deck = cycle.copy()
    player.cycle_queue = deque(cycle[4:])
    battle.time = start_time
    battle.tick = round(start_time / battle.dt)

    assert battle.deploy_card(0, "Knight", Position(7.0, 10.0))
    # NextSpellCooldownMS does not lock other occupied hand slots.
    assert battle.deploy_card(0, "Archers", Position(11.0, 10.0))
    assert player.hand[:2] == [None, None]

    # A zero timer lets the next player tick fill one lowest-index slot.
    battle.step()
    assert player.hand[:2] == ["Giant", None]
    assert player.next_card_refill_cooldown_ms == cooldown_ms

    for _ in range(cooldown_ticks - 1):
        battle.step()
    assert player.hand[1] is None
    assert player.next_card_refill_cooldown_ms == 50

    battle.step()
    assert player.hand[1] == "Minions"
    assert player.next_card_refill_cooldown_ms == cooldown_ms


def test_tournament_towers_use_live_tower_troop_stats_without_card_rescaling():
    battle = BattleState()
    princess = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building) and entity.card_stats.name == "Tower"
    )
    king = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building) and entity.card_stats.name == "KingTower"
    )

    assert (princess.hitpoints, princess.damage, princess.card_stats.collision_radius) == (
        3052,
        109,
        1.0,
    )
    assert (king.hitpoints, king.damage, king.card_stats.collision_radius) == (
        4824,
        109,
        1.4,
    )
    assert princess.card_stats.projectile_speed == 600
    assert king.card_stats.projectile_speed == 1000


def test_king_tower_starts_inactive_and_activates_when_hit():
    battle = BattleState()
    blue_king = _get_tower(battle, 0, "king")
    assert getattr(blue_king, "_tower_active", True) is False
    blue_king.take_damage(1)
    assert getattr(blue_king, "_tower_active", False) is True
    assert blue_king.activation_delay_remaining == 3.3
    assert blue_king.activation_first_hit_delay_remaining == 0.7
    assert blue_king.card_stats.load_time == 500
    assert blue_king.card_stats.first_hit_time == 500
    assert blue_king.attack_cooldown == 0.5


def test_building_on_destroyed_tower_footprint_cannot_resurrect_crown_hp():
    battle = BattleState()
    blue_left = _get_tower(battle, 0, "left")
    blue_left.take_damage(blue_left.hitpoints)
    battle._cleanup_dead_entities()
    assert battle.players[0].left_tower_hp == 0

    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(
        Building,
        Position(
            battle.arena.BLUE_LEFT_TOWER.x,
            battle.arena.BLUE_LEFT_TOWER.y,
        ),
        0,
        cannon_stats,
    )
    battle._update_tower_hp()

    assert cannon.hitpoints > 0
    assert battle.players[0].left_tower_hp == 0
    assert battle.get_crown_count(1) == 1


def test_king_tower_activation_takes_four_seconds_before_first_shot():
    battle = BattleState()
    blue_king, _ = _spawn_king_activation_target(battle)

    blue_king.take_damage(1)
    blue_king.update(3.99, battle)
    assert not _king_has_launched(battle)

    blue_king.update(0.01, battle)
    assert _king_has_launched(battle)


def test_short_stun_during_king_activation_does_not_change_first_shot_time():
    battle = BattleState()
    blue_king, _ = _spawn_king_activation_target(battle)

    assert SPELL_REGISTRY["Zap"].cast(
        battle,
        1,
        Position(blue_king.position.x, blue_king.position.y),
    )
    assert blue_king.stun_timer == 0.5
    for _ in range(79):
        blue_king.update(0.05, battle)
    assert not _king_has_launched(battle)

    blue_king.update(0.05, battle)
    assert _king_has_launched(battle)


def test_freeze_does_not_add_a_new_windup_after_king_activation():
    battle = BattleState()
    blue_king, _ = _spawn_king_activation_target(battle)

    assert SPELL_REGISTRY["Freeze"].cast(
        battle,
        1,
        Position(blue_king.position.x, blue_king.position.y),
    )
    freeze = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, AreaEffect) and entity.spell_name == "Freeze"
    )
    freeze.update(0.0, battle)
    assert blue_king.stun_timer == 4.0
    for _ in range(80):
        blue_king.update(0.05, battle)

    # Combat runs before status expiry on the final frozen frame. The tower
    # has nevertheless completed and armed its activation shot.
    assert not _king_has_launched(battle)
    assert blue_king.stun_timer == 0.0
    assert blue_king.attack_cooldown == 0.0

    blue_king.update(0.05, battle)
    assert _king_has_launched(battle)


def test_king_tower_activates_when_princess_tower_destroyed():
    battle = BattleState()
    blue_king = _get_tower(battle, 0, "king")
    blue_left = _get_tower(battle, 0, "left")
    assert getattr(blue_king, "_tower_active", True) is False
    blue_left.take_damage(blue_left.hitpoints)
    battle.step()
    assert getattr(blue_king, "_tower_active", False) is True


def test_king_tower_activates_when_hit_by_spell():
    battle = BattleState()
    _prepare_single_card(battle, 1, "Fireball")
    blue_king = _get_tower(battle, 0, "king")
    hp_before = blue_king.hitpoints
    assert getattr(blue_king, "_tower_active", True) is False

    assert battle.deploy_card(1, "Fireball", Position(battle.arena.BLUE_KING_TOWER.x, battle.arena.BLUE_KING_TOWER.y))
    for _ in range(120):
        battle.step()

    assert blue_king.hitpoints < hp_before
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


def test_wide_troop_cards_respect_their_serialized_edge_tile_margin():
    battle = BattleState()
    _prepare_single_card(battle, 0, "RoyalHogs")

    assert not battle.deploy_card(0, "RoyalHogs", Position(1.5, 10.5))
    assert battle.deploy_card(0, "RoyalHogs", Position(2.5, 10.5))
    hogs = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == 0
        and entity.card_stats.name == "RoyalHogs"
    ]
    assert len(hogs) == 4


def test_cannot_deploy_non_spell_on_building_footprint():
    battle = BattleState()
    player = battle.players[0]
    player.elixir = 10.0
    player.hand = ["Cannon", "Knight"]
    player.deck = ["Cannon", "Knight"]
    player.cycle_queue = deque()
    assert battle.deploy_card(0, "Cannon", Position(9.0, 10.0))
    assert not battle.deploy_card(0, "Knight", Position(9.0, 10.0))


@pytest.mark.parametrize("fast_path", [False, True])
def test_same_decision_building_commands_share_live_placement_state(fast_path):
    battle = BattleState(fast_path=fast_path)
    red_left = _get_tower(battle, 1, "left")
    red_left.take_damage(red_left.hitpoints)
    battle._update_tower_hp()

    for player_id in (0, 1):
        _prepare_single_card(battle, player_id, "Cannon")

    # Destroying the red-left tower opens this pocket to player zero while it
    # remains ordinary home territory for player one. The first accepted
    # command owns the footprint; the second command in the same decision
    # window must see it before any simulation tick runs.
    position = Position(6.5, 18.5)
    assert battle.deploy_card(0, "Cannon", position)
    assert not battle.deploy_card(1, "Cannon", position)
    assert len(
        [
            entity
            for entity in battle.entities.values()
            if (
                isinstance(entity, Building)
                and entity.is_alive
                and entity.card_stats.name == "Cannon"
            )
        ]
    ) == 1


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
    battle.time = 120.0
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
    assert player.hand[0] is None
    assert player.get_next_card() == "Musketeer"
    assert player.cycle_queue[-1] == "Knight"

    battle.step()
    assert "Musketeer" in player.hand
    assert player.get_next_card() == "Skeletons"


def test_champion_cycles_normally_and_can_be_redeployed_while_alive():
    battle = BattleState()
    player = battle.players[0]
    cycle = ["ArcherQueen", "Knight", "Skeletons", "IceSpirit", "Cannon", "Fireball", "Log", "Archers"]
    player.elixir = 10.0
    player.deck = cycle.copy()
    player.hand = cycle[:4].copy()
    player.cycle_queue = deque(cycle[4:])

    assert battle.deploy_card(0, "ArcherQueen", Position(9.0, 10.0))
    assert "ArcherQueen" not in player.hand
    assert player.cycle_queue[-1] == "ArcherQueen"

    for card_name, position in (
        ("Knight", Position(7.0, 10.0)),
        ("Skeletons", Position(11.0, 10.0)),
        ("IceSpirit", Position(6.0, 11.0)),
    ):
        player.elixir = 10.0
        assert battle.deploy_card(0, card_name, position)

    assert player.hand == [None, None, None, None]

    # The first empty slot fills immediately on the next player tick. Each
    # later slot waits one full Default-timeline refill interval.
    battle.step()
    for _ in range(3):
        for _ in range(20):
            battle.step()
    assert player.hand == ["Cannon", "Fireball", "Log", "Archers"]
    assert player.get_next_card() == "ArcherQueen"

    player.elixir = 10.0
    assert battle.deploy_card(0, "Cannon", Position(14.0, 11.0))
    for _ in range(20):
        battle.step()
    assert player.hand[0] == "ArcherQueen"

    first_queen = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == 0
        and entity.card_stats.name == "ArcherQueen"
    )
    assert first_queen.is_alive

    player.elixir = 10.0
    assert battle.deploy_card(0, "ArcherQueen", Position(9.0, 11.0))
    queens = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.player_id == 0
        and entity.card_stats.name == "ArcherQueen"
        and entity.is_alive
    ]
    assert len(queens) == 2


def test_sudden_death_and_tiebreaker_damage():
    battle = BattleState()
    battle.time = 180.0
    battle._check_win_conditions()
    assert battle.sudden_death
    assert not battle.game_over

    # No crown change; reach the 5:00 tiebreak with uneven tower health.
    red_left = _get_tower(battle, 1, "left")
    red_left.hitpoints -= 200
    battle.time = 300.0
    battle._check_win_conditions()
    assert battle.game_over
    assert battle.winner == 0


def test_tiebreaker_uses_lowest_tower_hp_when_total_damage_equal():
    battle = BattleState()
    battle.time = 300.0

    # Equal total damage (200 each), but player 1 has a lower minimum tower HP.
    blue_left = _get_tower(battle, 0, "left")
    blue_right = _get_tower(battle, 0, "right")
    red_left = _get_tower(battle, 1, "left")
    blue_left.hitpoints -= 100
    blue_right.hitpoints -= 100
    red_left.hitpoints -= 200

    battle._check_win_conditions()
    assert battle.game_over
    assert battle.winner == 0


def test_tiebreaker_exact_lowest_tower_health_tie_is_draw():
    battle = BattleState()
    battle.time = 300.0
    battle._check_win_conditions()
    assert battle.game_over
    assert battle.winner is None


def test_simultaneous_king_tower_destruction_is_a_draw():
    battle = BattleState()
    blue_king = _get_tower(battle, 0, "king")
    red_king = _get_tower(battle, 1, "king")

    blue_king.take_damage(blue_king.hitpoints)
    red_king.take_damage(red_king.hitpoints)
    battle.step()

    assert battle.game_over
    assert battle.winner is None


def test_regulation_ends_at_three_minutes_on_crown_advantage():
    battle = BattleState()
    red_left = _get_tower(battle, 1, "left")
    red_left.take_damage(red_left.hitpoints)

    battle.time = 179.999
    battle._check_win_conditions()
    assert not battle.game_over

    battle.time = 180.0
    battle._check_win_conditions()
    assert battle.game_over
    assert battle.winner == 0


def test_first_overtime_crown_advantage_ends_match_immediately():
    battle = BattleState()
    battle.time = 180.0
    battle._check_win_conditions()
    assert battle.sudden_death

    red_left = _get_tower(battle, 1, "left")
    red_left.take_damage(red_left.hitpoints)
    battle.time = 180.1
    battle._check_win_conditions()
    assert battle.game_over
    assert battle.winner == 0


def test_stun_restarts_complete_attack_cycle_and_clears_current_target_lock():
    battle = BattleState()
    _prepare_single_card(battle, 0, "Knight")
    assert battle.deploy_card(0, "Knight", Position(9.0, 10.0))
    knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Knight"
    )
    _finish_deployment(knight)
    knight.attack_cooldown = 0.17
    knight.target_id = next(
        entity.id
        for entity in battle.entities.values()
        if isinstance(entity, Building) and entity.player_id == 1
    )
    knight.apply_stun(0.5)
    assert knight.attack_cooldown == knight.get_base_attack_interval_seconds()
    assert knight.target_id is None


def test_slow_increases_attack_interval():
    battle = BattleState()
    _prepare_single_card(battle, 0, "Knight")
    assert battle.deploy_card(0, "Knight", Position(9.0, 10.0))
    knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Knight"
    )
    _finish_deployment(knight)
    base_interval = knight.get_attack_interval_seconds()
    knight.apply_slow(2.0, 0.65)
    slowed_interval = knight.get_attack_interval_seconds()
    assert slowed_interval > base_interval

    knight.attack_cooldown = 1.0
    knight._has_attacked_once = True
    knight.update(battle.dt, battle)
    # Native combat clocks truncate 50ms * 65% to 32ms of work.
    assert abs(knight.attack_cooldown - (1.0 - 0.032)) < 1e-9

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
    # This test isolates Knight's ground-only targeting. With authentic
    # edge-to-edge tower reach, the nearby friendly princess tower can
    # otherwise shoot the Minions during the observation window.
    for entity in battle.entities.values():
        if isinstance(entity, Building):
            entity.attack_cooldown = 999.0

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
    _finish_deployment(balloon)
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
    _finish_deployment(ram)
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
    _finish_deployment(golem)
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
    _finish_deployment(barrel)
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
    _finish_deployment(knight)
    assert battle.deploy_card(0, "Freeze", Position(9.0, 18.0))

    for _ in range(40):
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
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "RageBarbarian"
    )
    ally_knight = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "Knight"
    )
    _finish_deployment(lumberjack)
    _finish_deployment(ally_knight)
    damage_before = ally_knight.damage

    lumberjack.take_damage(lumberjack.hitpoints)
    assert not any(
        isinstance(entity, Troop)
        and entity.is_alive
        and entity.card_stats.name == "RageBarbarianBottle"
        for entity in battle.entities.values()
    )
    for _ in range(20):
        battle.step()
    assert not any(
        isinstance(entity, Troop)
        and entity.card_stats.name == "RageBarbarianBottle"
        for entity in battle.entities.values()
    )
    assert ally_knight.attack_speed_buff_multiplier > 1.0
    assert ally_knight.movement_speed_buff_multiplier > 1.0
    assert ally_knight.damage == damage_before


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
    enemy_knight.placement_pending = False
    enemy_knight.speed = 0.0
    tower = _get_tower(battle, 1, "left")

    tower_hp_before = tower.hitpoints
    knight_hp_before = enemy_knight.hitpoints
    assert battle.deploy_card(0, "Zap", Position(3.5, 25.5))
    for _ in range(31):
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
    bandit._bandit_dashing = True
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
    spawned_skeleton = False
    # Observe the interval rather than sampling only its endpoint: live tower
    # locks can legitimately eliminate a wave before this window closes.
    for _ in range(320):
        battle.step()
        after = len(
            [
                entity
                for entity in battle.entities.values()
                if isinstance(entity, Troop) and entity.player_id == 0
            ]
        )
        spawned_skeleton |= after > baseline
    assert spawned_skeleton


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


def test_tombstone_periodic_skeletons_move_after_spawn():
    battle = BattleState()
    p0 = battle.players[0]
    p0.elixir = 10.0
    p0.hand = ["Tombstone"]
    p0.deck = ["Tombstone"]
    p0.cycle_queue = deque()
    assert battle.deploy_card(0, "Tombstone", Position(9.0, 10.0))

    # Deploy delay (~1s) + periodic spawn interval (3.5s) + margin.
    for _ in range(220):
        battle.step()

    spawned_positions = {
        e.id: (e.position.x, e.position.y)
        for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name in {"Skeleton", "Skeletons"}
    }
    assert spawned_positions

    # Observe movement before the fragile spawned skeleton is expected to reach
    # enemy tower fire and disappear from the entity set.
    for _ in range(60):
        battle.step()

    moved = 0
    for e in battle.entities.values():
        if e.id not in spawned_positions:
            continue
        start_x, start_y = spawned_positions[e.id]
        if ((e.position.x - start_x) ** 2 + (e.position.y - start_y) ** 2) ** 0.5 > 0.2:
            moved += 1
    assert moved > 0


def test_lava_hound_death_spawns_lava_pups():
    battle = BattleState()
    _prepare_single_card(battle, 0, "LavaHound")
    assert battle.deploy_card(0, "LavaHound", Position(9.0, 10.0))

    hound = next(
        e for e in battle.entities.values()
        if isinstance(e, Troop) and e.player_id == 0 and e.card_stats.name == "LavaHound"
    )
    _finish_deployment(hound)
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
    # First wave appears one second after the deployment delay finishes.
    for _ in range(70):
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
    _finish_deployment(dark_prince)
    hp_before = dark_prince.hitpoints
    shield = next(mechanic for mechanic in dark_prince.mechanics if type(mechanic).__name__ == "Shield")
    assert shield.current_shield > 94
    dark_prince.take_damage(shield.current_shield + 500)
    assert dark_prince.hitpoints == hp_before
    assert shield.current_shield == 0


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

    # Exact center is a native Princess-Tower distance tie. Each player's
    # strict leader-array order resolves that tie to the rotationally opposite
    # lane, so use an unambiguous same-lane deployment for this charge test.
    assert battle.deploy_card(0, "Prince", Position(9.5, 10.0))
    giant_stats = battle.card_loader.get_card("Giant")
    assert giant_stats is not None
    battle._spawn_troop(Position(9.5, 18.0), 1, giant_stats)

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
    prince.placement_pending = False
    giant.placement_pending = False
    prince.on_spawn()
    giant.on_spawn()

    hp_before = giant.hitpoints
    for _ in range(220):
        battle.step()
        if giant.hitpoints < hp_before:
            break
    damage_dealt = hp_before - giant.hitpoints
    assert damage_dealt >= prince.damage
