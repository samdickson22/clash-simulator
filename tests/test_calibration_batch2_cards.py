"""Engine calibration batch 2, cards topic (research/cards/REPORT.md on 127x03).

1. Rascals deploy stagger. Native 15.535 train recordings: the Rascal girls start walking 2 and 4 ticks after the
   boy (move-start ages 20/22/24 in native object-id order), which is the 100 ms summonDeployDelay every other
   multi-unit card has; our gamedata had none, so all three started at 20 and the second girl was pushed on her
   first frame. Positions below are native rows (native units) at ages from the play's first frame, observed in
   train episodes where the native group was isolated through age 27.
2. Firecracker recoil ends the started hit. After a shot's recoil, a native Firecracker whose target is now beyond
   attack reach walks straight back toward it on the first frame after the push (velocity 90/tick) and stops when
   back in reach; ours stood still in the started-hit leash and later fired from the recoil position.
"""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.player import PlayerState


def _track(card, side, tile, ages):
    """Deploy on an empty battle with the harness timing (issue one tick before the native execution tick)
    and return {entity id: {age: (x, y)}} for the new troops; age 0 is the frame after the first step."""
    battle = BattleState(players=[PlayerState(0, card_levels={card: 11}), PlayerState(1, card_levels={card: 11})])
    battle.players[side].hand = [card]
    battle.players[side].elixir = 10
    before = set(battle.entities)
    assert battle.deploy_card(side, card, Position(*tile))
    out = {}
    for age in range(max(ages) + 1):
        battle.step()
        for eid, e in battle.entities.items():
            if eid not in before and isinstance(e, Troop) and e.player_id == side and age in ages:
                out.setdefault(eid, {})[age] = (round(e.position.x * 1000), round(e.position.y * 1000))
    return out


# (episode, side, tap tile, native members in native id order (boy, girl, girl): first frame, last standing
# position before walking, and native move-start age = first frame that differs from the previous one).
NATIVE_RASCALS = [
    ('v4-phase-a-1975100700', 0, (1.5, 6.5), [
        ((1499, 8231), (1499, 8231), 20), ((276, 5277), (276, 5277), 22), ((2722, 5277), (2642, 5151), 24)]),
    ('v4-phase-a-1975100796', 1, (14.5, 22.5), [
        ((14500, 20768), (14500, 20768), 20), ((15723, 23722), (15723, 23722), 22), ((13277, 23722), (13277, 23722), 24)]),
    ('v4-phase-a-1975100820', 1, (3.5, 30.5), [
        ((3499, 28768), (3499, 28768), 20), ((2276, 31000), (2276, 31000), 22), ((4722, 31000), (4722, 31000), 24)]),
]


@pytest.mark.parametrize('episode,side,tile,native', NATIVE_RASCALS, ids=lambda v: str(v))
def test_rascals_girls_deploy_staggered_like_native(episode, side, tile, native):
    ours = _track('Rascals', side, tile, range(30))
    assert len(ours) == 3, ours
    for first, standing, start in native:
        # pair each native member with our body that has the same first frame
        rows = min(ours.values(), key=lambda r: abs(r[0][0] - first[0]) + abs(r[0][1] - first[1]))
        assert abs(rows[0][0] - first[0]) <= 2 and abs(rows[0][1] - first[1]) <= 2, (episode, rows[0], first)
        moved = next(a for a in range(1, 30) if rows[a] != rows[a - 1] and a >= 12)
        assert moved == start, (episode, first, moved, start)
        assert abs(rows[start - 1][0] - standing[0]) <= 2 and abs(rows[start - 1][1] - standing[1]) <= 2, (episode, rows[start - 1], standing)


def _firecracker_vs_tower(ticks=330):
    """Side-0 Firecracker on the left bridge lane shooting the side-1 left princess tower (empty battle). Its
    hitpoints are raised so the tower cannot kill it: only the attack clock and movement are under test."""
    battle = BattleState(players=[PlayerState(0, card_levels={'Firecracker': 11}), PlayerState(1, card_levels={'Firecracker': 11})])
    while battle.tick < 400:
        battle.step()
    battle.players[0].hand = ['Firecracker']
    battle.players[0].elixir = 10
    assert battle.deploy_card(0, 'Firecracker', Position(3.5, 13.5))
    fc = max(battle.entities.values(), key=lambda e: e.id)
    fc.hitpoints = fc.max_hitpoints = 10 ** 6
    shots, rows, pushing = [], {}, False
    for _ in range(ticks):
        battle.step()
        if fc._knockback_target is not None and not pushing:
            shots.append(battle.tick)
        pushing = fc._knockback_target is not None
        rows[battle.tick] = round(fc.position.y * 1000)
    return shots, rows


def test_firecracker_fires_59_ticks_apart_like_native():
    """Native train Firecrackers: consecutive launches at the same target are 59 ticks apart (77/86; ours 60 in
    318/336), because the recoil stops the hit and the restarted hit is credited with the weapon's loaded work
    (rich snapshots: attackTimelineMs 550 on the first frame after the push)."""
    shots, _ = _firecracker_vs_tower()
    assert len(shots) >= 4, shots
    assert [b - a for a, b in zip(shots, shots[1:])][:3] == [59, 59, 59], shots


def test_firecracker_walks_back_into_reach_after_recoil():
    """The recoil carries the Firecracker from 7.44 to 8.32 tiles from the tower (reach 7.5). Native (e.g. ep
    …0730, shot 2570; train: 31/34 aligned shots with the target 7.5-9 tiles away after the recoil) walks back
    at 90 units/tick from the first frame after the push and stands in reach by +20; ours used to stand at the
    recoil end and fire the next shot from there, drifting further back with every shot."""
    shots, rows = _firecracker_vs_tower(200)
    shot = shots[0]
    recoil_end = rows[shot + 8]
    assert rows[shot - 1] - recoil_end > 800
    assert rows[shot + 12] - rows[shot + 9] >= 3 * 85
    assert rows[shot + 22] - recoil_end >= 800
    assert rows[shot + 22] == rows[shot + 21]  # back in reach: standing
    assert abs(rows[shots[1] - 1] - rows[shot - 1]) <= 50  # second shot from (about) the first shot's spot
