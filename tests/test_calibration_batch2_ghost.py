"""Engine calibration batch 2, Royal Ghost (research/ghost/REPORT.md): rules measured on native 15.535 T1 train recordings."""
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.kinematics import logic_time_milliseconds
from clasher.player import PlayerState

CARDS = ('Ghost', 'Knight', 'Skeletons')


def _battle():
    return BattleState(players=[PlayerState(0, card_levels=dict.fromkeys(CARDS, 11)),
                                PlayerState(1, card_levels=dict.fromkeys(CARDS, 11))])


def _deploy(battle, side, card, tile):
    before = set(battle.entities)
    battle.players[side].hand = [card]
    battle.players[side].elixir = 10
    assert battle.deploy_card(side, card, Position(*tile))
    return before


def _new_troops(battle, before, side, name=None):
    return [e for k, e in sorted(battle.entities.items()) if k not in before and isinstance(e, Troop)
            and e.player_id == side and (name is None or name in getattr(e.card_stats, 'name', ''))]


def _xy(e):
    return round(e.position.x * 1000), round(e.position.y * 1000)


def _hidden(battle, e):
    return int(getattr(e, '_stealth_until', 0) or 0) > logic_time_milliseconds(battle.time)


# Native: a Ghost walks the LogicPathFinder grid route (cell-centre headings), not a straight hover line.
# Train episode v4-phase-a-1975100700, side 0, tap (9.5, 14.5), first frame 3293, no unit within 3 tiles:
# after its deploy it leaves on an exact 45-degree diagonal (+63, +63 per tick) toward the right lane.
# Keyed by movement ticks since it started walking (native frames 3313..3321). Our in-fixture replay
# matches these frames exactly; native turns north at 3322 (likely a retarget), so later frames are not used.
NATIVE_GHOST_WALK = ('v4-phase-a-1975100700', 0, (9.5, 14.5),
                     {2: (9626, 14626), 3: (9689, 14689), 5: (9815, 14815), 6: (9878, 14878), 7: (9941, 14941),
                      10: (10130, 15130)})


def test_ghost_walks_native_grid_route():
    _, side, tap, native = NATIVE_GHOST_WALK
    battle = _battle()
    before = _deploy(battle, side, 'Ghost', tap)
    ghost, start, track = None, None, []
    for _ in range(60):
        battle.step()
        ghost = ghost or (_new_troops(battle, before, side, 'Ghost') or [None])[0]
        if ghost is None:
            continue
        pos = _xy(ghost)
        if start is None:
            start = pos
        if track or pos != start:
            track.append(pos)
    assert start == (9500, 14500)
    for steps, (x, y) in native.items():
        sx, sy = track[steps - 1]
        assert abs(sx - x) <= 2 and abs(sy - y) <= 2, (steps, track[steps - 1], (x, y))


# Native: the Ghost's body is on the ground collision plane. Over 708 train Ghosts, a ground troop sits
# within 600 units of it in 0.4% of near ticks (Knight 0.5%, Minions 29.6%), and deploying Ghosts are
# pushed off bodies they land on (e.g. v4-phase-a-1975100702 Ghost 5000014 moves 474 units during its
# deploy). Our engine had it on the air plane, passing through ground troops.
def test_ghost_is_pushed_by_a_ground_troop_it_lands_on():
    battle = _battle()
    k_before = _deploy(battle, 0, 'Knight', (9.5, 6.5))
    battle.step()
    knight = _new_troops(battle, k_before, 0, 'Knight')[0]
    g_before = _deploy(battle, 0, 'Ghost', (9.5, 6.5))
    ghost = None
    for _ in range(14):  # both still deploying (1000 ms): only body pressure can move them
        battle.step()
        ghost = ghost or (_new_troops(battle, g_before, 0, 'Ghost') or [None])[0]
    assert ghost is not None
    gx, gy = _xy(ghost)
    kx, ky = _xy(knight)
    assert ((gx - kx) ** 2 + (gy - ky) ** 2) ** 0.5 >= 300


# Native re-hide: measured from the last stationary frame before a Ghost walks again after its last hit,
# train Ghosts are visible at +36..39 (29/29), hidden in 11/20 at +40..41 and 185/186 at >= +42.
# The fade timer therefore restarts when the attack state ends (movement restarts, typically 4-5 ticks
# after the hit); ours restarted it at the hit and re-hid at +34..35.
def test_ghost_rehides_2000ms_after_it_walks_again():
    battle = _battle()
    g_before = _deploy(battle, 0, 'Ghost', (3.5, 13.5))
    s_before = _deploy(battle, 1, 'Skeletons', (3.5, 18.5))
    ghost, hit, last_still, hide, prev = None, None, None, None, None
    for _ in range(300):
        battle.step()
        ghost = ghost or (_new_troops(battle, g_before, 0, 'Ghost') or [None])[0]
        if ghost is None:
            continue
        pos = _xy(ghost)
        skeletons = [e for e in _new_troops(battle, s_before, 1) if e.is_alive]
        if hit is None and not _hidden(battle, ghost) and ghost.deploy_delay_remaining <= 0:
            hit = battle.tick
        elif hit is not None and last_still is None and not skeletons and prev is not None and pos != prev:
            last_still = battle.tick - 1
        elif last_still is not None and _hidden(battle, ghost):
            hide = battle.tick
            break
        prev = pos
    assert hit is not None and last_still is not None and hide is not None
    assert 40 <= hide - last_still <= 41, (hit, last_still, hide)
