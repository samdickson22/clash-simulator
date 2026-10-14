"""Engine calibration batch 1 (reports/bot/calibration/BATCH1.md): rules measured on native 15.535 recordings."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.player import PlayerState


def _battle(cards):
    return BattleState(players=[PlayerState(0, card_levels=dict.fromkeys(cards, 11)), PlayerState(1)])


def _troops(battle, pid=0):
    return [e for e in battle.entities.values() if isinstance(e, Troop) and e.player_id == pid]


# Native T1 train recordings (513 episodes): max_hp of every spirit body is 215 at level 11,
# i.e. base 84 x 256%. Our gamedata carried 90 (-> 230) for FireSpirits and ElectroSpirit.
@pytest.mark.parametrize('card', ['IceSpirit', 'FireSpirits', 'ElectroSpirit'])
def test_spirit_hitpoints_match_native_level11(card):
    battle = _battle([card])
    battle.players[0].hand = [card]
    battle.players[0].elixir = 10
    assert battle.deploy_card(0, card, Position(8.5, 10.5))
    for _ in range(40):
        battle.step()
        if _troops(battle):
            break
    spirits = _troops(battle)
    assert spirits
    assert {e.max_hitpoints for e in spirits} == {215}


def test_firespirit_hut_spawns_native_hp_spirits():
    battle = _battle(['FirespiritHut'])
    battle.players[0].hand = ['FirespiritHut']
    battle.players[0].elixir = 10
    assert battle.deploy_card(0, 'FirespiritHut', Position(8.5, 6.5))
    spirits = []
    for _ in range(400):
        battle.step()
        spirits = [e for e in _troops(battle) if 'Spirit' in getattr(e.card_stats, 'name', '')]
        if spirits:
            break
    assert spirits
    assert {e.max_hitpoints for e in spirits} == {215}


def _first_positions(card, side, tile):
    """Deploy on an empty battle; return each new unit's first position (native units) in spawn order."""
    battle = BattleState(players=[PlayerState(0, card_levels={card: 11}), PlayerState(1, card_levels={card: 11})])
    battle.players[side].hand = [card]
    battle.players[side].elixir = 10
    before = set(battle.entities)
    assert battle.deploy_card(side, card, Position(*tile))
    first = {}
    for _ in range(40):
        battle.step()
        for eid, e in battle.entities.items():
            if eid not in before and eid not in first and isinstance(e, Troop) and e.player_id == side:
                first[eid] = (round(e.position.x * 1000), round(e.position.y * 1000))
    return [first[k] for k in sorted(first)]


# Native first frames, listed in native spawn order (object id), from T1 train recordings.
# Path 2 (right lane) mirrors 5-, 6- and 15-slot rings; path 1 does not.
NATIVE_FORMATIONS = [
    ('Bats', 0, (14.5, 13.5), 'v4-phase-a-1975100704',
     [(13507, 14493), (13249, 12862), (14719, 12113), (15887, 13281), (15138, 14751)]),
    ('Bats', 1, (11.5, 29.5), 'v4-phase-a-1975100734',
     [(10507, 28507), (10249, 30138), (11719, 30887), (12887, 29719), (12138, 28249)]),
    ('Bats', 0, (1.5, 6.5), 'v4-phase-a-1975100727',
     [(2493, 7493), (2751, 5862), (1281, 5113), (250, 6281), (862, 7751)]),
    ('MinionHorde', 0, (12.5, 3.5), 'v4-phase-a-1975100762',
     [(12500, 2159), (13661, 2830), (13661, 4170), (12500, 4841), (11339, 4170), (11339, 2830)]),
    ('GoblinGang', 1, (10.5, 23.5), 'v4-phase-a-1975100736',
     [(9501, 22922), (10500, 22345), (11499, 22922), (11499, 24076), (10500, 24653), (9501, 24076)]),
]


@pytest.mark.parametrize('card,side,tile,episode,native', NATIVE_FORMATIONS, ids=lambda v: str(v))
def test_formation_matches_native_first_frame_and_order(card, side, tile, episode, native):
    ours = _first_positions(card, side, tile)
    assert len(ours) == len(native)
    for (x, y), (nx, ny) in zip(ours, native):
        assert abs(x - nx) <= 2 and abs(y - ny) <= 2, (episode, ours, native)


# Goblinstein (1 primary + 1 secondary): native monster on the tap tile, doctor one tile toward the
# centre and 3.5 tiles behind (goblinstein.md; 144 train spawns). (episode, side, tap, monster, doctor)
NATIVE_GOBLINSTEIN = [
    ('v4-phase-a-1975100707', 1, (0.5, 22.5), (499, 22499), (1499, 25999)),
    ('v4-phase-a-1975100707', 1, (14.5, 18.5), (14500, 18499), (13500, 21999)),
    ('v4-phase-a-1975100707', 0, (3.5, 13.5), (3499, 13500), (4499, 10000)),
    ('v4-phase-a-1975100715', 1, (4.5, 28.5), (4499, 28499), (5499, 31750)),  # doctor clipped at the top edge
]


# Batch 2 (research/swarm REPORT.md): side-1 ground bodies are bounded at y=31.0 unless side 0's
# princess on the anchor half is down. At ...0715 exec 5898 side 0's left princess was destroyed, so
# the doctor keeps the 31.75 edge; reproduce that tower state.
GOBLINSTEIN_DESTROYED_TOWERS = {'v4-phase-a-1975100715': [(0, 'left')]}


@pytest.mark.parametrize('episode,side,tile,monster,doctor', NATIVE_GOBLINSTEIN, ids=lambda v: str(v))
def test_goblinstein_formation_matches_native(episode, side, tile, monster, doctor, monkeypatch):
    destroyed = GOBLINSTEIN_DESTROYED_TOWERS.get(episode, [])
    if destroyed:
        real = BattleState.deploy_card

        def deploy_after_destroy(self, *a, **k):
            for pid, slot in destroyed:
                tower = next(e for e in self.entities.values()
                             if getattr(e, '_crown_tower_slot', None) == slot and e.player_id == pid)
                tower.hitpoints = 0
                self.step()
            return real(self, *a, **k)
        monkeypatch.setattr(BattleState, 'deploy_card', deploy_after_destroy)
    ours = _first_positions('Goblinstein', side, tile)
    assert len(ours) == 2
    for (x, y), (nx, ny) in zip(ours, (monster, doctor)):
        assert abs(x - nx) <= 2 and abs(y - ny) <= 2, (episode, ours)


def _hut_battle(card, hut_tile=(8.5, 6.5)):
    battle = BattleState(players=[PlayerState(0, card_levels={card: 11}), PlayerState(1, card_levels={'Knight': 11})])
    battle.players[0].hand = [card]
    battle.players[0].elixir = 10
    assert battle.deploy_card(0, card, Position(*hut_tile))
    return battle


def _first_child_tick(battle, child_filter, ticks=200):
    """Ticks from now to the first own troop matching child_filter."""
    start = battle.tick
    for _ in range(ticks):
        battle.step()
        if any(child_filter(e) for e in _troops(battle)):
            return battle.tick - start
    return None


def _enemy_knight(battle, tile):
    battle.players[1].hand = ['Knight']
    battle.players[1].elixir = 10
    assert battle.deploy_card(1, 'Knight', Position(*tile))


def test_firespirit_hut_first_spirit_at_native_1900ms():
    # Native: first spirit 38-39 ticks after the play; the harness deploys one tick early, so 39-40 here.
    tick = _first_child_tick(_hut_battle('FirespiritHut'), lambda e: 'Spirit' in e.card_stats.name)
    assert tick is not None and 38 <= tick <= 40, tick


def _spear(e):
    return e.card_stats.name == 'SpearGoblin'


def test_goblin_hut_first_spear_goblin_as_deploy_ends_when_enemy_in_range():
    # Native: first SpearGoblin 20-21 ticks after the play when an enemy is within range.
    battle = _hut_battle('GoblinHut', (8.5, 13.5))
    _enemy_knight(battle, (8.5, 18.5))  # 5 tiles away, standing still while it deploys
    tick = _first_child_tick(battle, _spear)
    assert tick is not None and 20 <= tick <= 22, tick


def test_goblin_hut_fires_on_wake_without_new_delay():
    # Native: an idle hut spawns on the tick an enemy comes within 6 tiles + both radii.
    battle = _hut_battle('GoblinHut', (8.5, 9.5))
    assert _first_child_tick(battle, _spear, ticks=120) is None  # nothing in range: asleep
    _enemy_knight(battle, (8.5, 17.5))  # deploys, then walks down toward the hut
    hut = next(e for e in battle.entities.values() if e.player_id == 0 and e.card_stats.name == 'GoblinHut')
    woke = None
    for _ in range(400):
        battle.step()
        knight = next(e for e in battle.entities.values() if e.player_id == 1 and e.card_stats.name == 'Knight')
        reach = 6.0 + hut.get_collision_radius() + knight.get_collision_radius()
        if woke is None and hut.position.distance_to(knight.position) <= reach:
            woke = battle.tick
        if any(_spear(e) for e in _troops(battle)):
            break
    assert woke is not None and battle.tick - woke <= 1, (woke, battle.tick)


@pytest.mark.parametrize('side,tile', [(0, (5.5, 25.5)), (1, (12.5, 8.5)), (0, (12.5, 20.5))])
def test_miner_surfaces_on_the_exact_tap(side, tile):
    # Native: 572/601 train Miners land exactly on the tap (no symmetric-deploy nudge).
    battle = BattleState(players=[PlayerState(0, card_levels={'Miner': 11}), PlayerState(1, card_levels={'Miner': 11})])
    battle.players[side].hand = ['Miner']
    battle.players[side].elixir = 10
    assert battle.deploy_card(side, 'Miner', Position(*tile))
    miner = next(e for e in battle.entities.values() if e.player_id == side and e.card_stats.name == 'Miner')
    for _ in range(80):
        battle.step()
        if miner.deploy_delay_remaining <= 1e-9:  # surfaced (emergence done)
            break
    assert miner.deploy_delay_remaining <= 1e-9
    assert (round(miner.position.x * 1000), round(miner.position.y * 1000)) == (round(tile[0] * 1000), round(tile[1] * 1000))


# Native Miner tunnel, ep v4-phase-a-1975100746 side 0, tap (5.5, 25.5), exec 4439: tick-after-exec -> position.
# The route goes up the x=9.25 column, diagonally to the left bridge (x=4.25), up it, then to the tap.
NATIVE_MINER_TUNNEL = {1: (9226, 4924), 4: (9243, 6874), 8: (9245, 9474), 12: (7870, 11594), 17: (5604, 13896),
                       21: (4341, 16047), 26: (4256, 19293), 32: (4255, 23193), 35: (5013, 24911), 37: (5500, 25500)}


def test_miner_tunnel_follows_native_spawn_route():
    import math
    from clasher.pathfinding import native_spawn_path_trajectory
    path = native_spawn_path_trajectory(Position(9.0, 3.0), Position(5.5, 25.5), 650, 1)
    assert path is not None and abs((len(path) - 1) - (37 + 2)) <= 1
    for tick, native in NATIVE_MINER_TUNNEL.items():
        assert math.dist(path[min(tick + 2, len(path) - 1)], native) <= 400, tick


def test_miner_lands_on_native_tick_through_deploy():
    # Through the deploy path: native lands 36-37 ticks after the play (harness issues one tick early).
    battle = BattleState(players=[PlayerState(0, card_levels={'Miner': 11}), PlayerState(1)])
    battle.players[0].hand = ['Miner']
    battle.players[0].elixir = 10
    assert battle.deploy_card(0, 'Miner', Position(5.5, 25.5))
    miner = next(e for e in battle.entities.values() if e.player_id == 0 and e.card_stats.name == 'Miner')
    start = battle.tick
    for _ in range(80):
        battle.step()
        if (round(miner.position.x * 1000), round(miner.position.y * 1000)) == (5500, 25500):
            break
    assert 36 <= battle.tick - start - 1 <= 37, battle.tick - start - 1


def test_miner_is_hit_during_emergence_like_native():
    # Native ep v4-phase-a-1975100702: Miner played at 2476 to (5.5, 25.5); both red princess
    # towers lock on during its emergence and the first arrow lands at 2532 (exec + 56).
    battle = BattleState(players=[PlayerState(0, card_levels={'Miner': 11}), PlayerState(1)])
    battle.players[0].hand = ['Miner']
    battle.players[0].elixir = 10
    assert battle.deploy_card(0, 'Miner', Position(5.5, 25.5))
    miner = next(e for e in battle.entities.values() if e.player_id == 0 and e.card_stats.name == 'Miner')
    start = battle.tick
    for _ in range(90):
        battle.step()
        if miner.hitpoints < miner.max_hitpoints:
            break
    # The full replay of ep 1975100702 reproduces every hit tick; on a fresh board the idle tower's
    # load state moves the first arrow by a tick. Before the fix it landed at +75.
    assert 55 <= battle.tick - start - 1 <= 57, battle.tick - start - 1
