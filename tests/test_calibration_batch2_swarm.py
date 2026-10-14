"""Engine calibration batch 2, swarm topic: side-1 back-row deploy bound (research/swarm/REPORT.md).

Native 15.535 train recordings: a side-1 ground body whose spawn point lies above y=31.0 is born at
y=31.000 (single troops and every formation member), unless side 0's princess tower on the anchor's
half is destroyed. Side 0's mirror row and air bodies are not bounded. Positions are native units.
"""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.player import PlayerState


def _destroy_tower(battle, player_id, slot):
    tower = next(e for e in battle.entities.values()
                 if isinstance(e, Building) and e.player_id == player_id
                 and getattr(e, '_crown_tower_slot', None) == slot)
    tower.hitpoints = 0
    battle.step()
    assert getattr(battle.players[player_id], f'{slot}_tower_hp') <= 0


def _first_positions(card, side, tile, destroyed=()):
    """Deploy on an otherwise empty battle; each new body's first position (native units), sorted."""
    battle = BattleState(players=[PlayerState(0, card_levels={card: 11}), PlayerState(1, card_levels={card: 11})])
    for pid, slot in destroyed:
        _destroy_tower(battle, pid, slot)
    battle.players[side].hand = [card]
    battle.players[side].elixir = 10
    before = set(battle.entities)
    assert battle.deploy_card(side, card, Position(*tile))
    first = {}
    for _ in range(40):
        battle.step()
        for eid, e in battle.entities.items():
            if eid not in before and eid not in first and isinstance(e, (Troop, Building)) and e.player_id == side:
                first[eid] = (round(e.position.x * 1000), round(e.position.y * 1000))
        if first:
            break
    return sorted(first.values())


def _assert_matches(ours, native, case):
    assert len(ours) == len(native), (case, ours)
    for (x, y), (nx, ny) in zip(ours, sorted(native)):
        assert abs(x - nx) <= 2 and abs(y - ny) <= 2, (case, ours, sorted(native))


# (episode, card, side, tap tile, native first frame). All observed on the play's execution tick (lag 0)
# with all three side-0 towers standing. Ours before the change: 31499 for the single troops and
# 31750 for the Goblin Gang / Archers back rows.
NATIVE_BOUNDED = [
    ('v4-phase-a-1975100731', 'Knight', 1, (9.5, 31.5), [(9500, 31000)]),
    ('v4-phase-a-1975100801', 'Valkyrie', 1, (10.5, 31.5), [(10500, 31000)]),
    ('v4-phase-a-1975100861', 'Princess', 1, (7.5, 31.5), [(7499, 31000)]),
    ('v4-phase-a-1975101325', 'ElectroSpirit', 1, (7.5, 31.5), [(7499, 31000)]),
    ('v4-phase-a-1975100834', 'GoblinGang', 1, (9.5, 31.5),
     [(8501, 30772), (8501, 31000), (9500, 30345), (9500, 31000), (10499, 30922), (10499, 31000)]),
    ('v4-phase-a-1975100862', 'GoblinGang', 1, (11.5, 31.5),
     [(10501, 30772), (10501, 31000), (11500, 30345), (11500, 31000), (12499, 30922), (12499, 31000)]),
    ('v4-phase-a-1975101062', 'Archers', 1, (11.5, 31.5), [(10999, 31000), (12000, 31000)]),
]


@pytest.mark.parametrize('episode,card,side,tile,native', NATIVE_BOUNDED, ids=lambda v: str(v))
def test_side1_back_row_ground_bodies_born_at_native_31000(episode, card, side, tile, native):
    _assert_matches(_first_positions(card, side, tile), native, episode)


# Guards that hold before and after the change: air bodies keep the 31.75 edge, side 0 keeps y=0.346.
NATIVE_UNBOUNDED = [
    ('v4-phase-a-1975100905', 'BabyDragon', 1, (11.5, 31.5), [(11500, 31500)]),
    ('v4-phase-a-1975100886', 'Bats', 1, (10.5, 31.5),
     [(9249, 31750), (9507, 30507), (10719, 31750), (11138, 30249), (11887, 31719)]),
    ('v4-phase-a-1975100745', 'GoblinGang', 0, (13.5, 1.5),
     [(12501, 923), (12501, 2077), (13500, 346), (13500, 2654), (14499, 923), (14499, 2077)]),
]


@pytest.mark.parametrize('episode,card,side,tile,native', NATIVE_UNBOUNDED, ids=lambda v: str(v))
def test_air_and_side0_back_rows_are_not_bounded(episode, card, side, tile, native):
    _assert_matches(_first_positions(card, side, tile), native, episode)


# The bound is lifted on the half whose side-0 princess tower is down (side 1 holds that pocket):
# ep ...0847 tick 2898, side-0 right princess destroyed, Skeletons keep the 31.75 edge.
def test_side1_back_row_bound_lifted_when_that_halfs_enemy_princess_is_down():
    ours = _first_positions('Skeletons', 1, (9.5, 31.5), destroyed=[(0, 'right')])
    _assert_matches(ours, [(8801, 31750), (9542, 30835), (10199, 31750)], 'v4-phase-a-1975100847')
    # ...but not on the other half: the left princess still stands for an x < 9 anchor.
    ours = _first_positions('Knight', 1, (7.5, 31.5), destroyed=[(0, 'right')])
    assert ours == [(7499, 31000)]
