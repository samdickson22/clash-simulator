"""Engine calibration batch 2, huts (research/huts/REPORT.md): rules measured on native 15.535 train recordings."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.player import PlayerState


def _units(x):
    return round(x * 1000)


# Native GoblinHut SpearGoblin first frames (unpushed, radius 1200) with a stationary enemy building as the
# nearest enemy: (episode, hut side, hut tile, enemy card, enemy tile, [kid offsets from the hut, by wave]).
NATIVE_SPEAR_GOBLINS = [
    # target left of the hut (dx < 0): wave 0 at +20 degrees, wave 1 at -20
    ('v4-phase-a-1975100702', 1, (14.5, 19.5), 'Cannon', (13.5, 13.5), [(219, -1178), (-589, -1044)]),
    ('v4-phase-a-1975100977', 0, (3.5, 12.5), 'Cannon', (1.5, 19.5), [(-703, 970), (85, 1195)]),
    # target straight ahead (dx == 0): side 0 keeps its initial facing (+1), so wave 0 is at -20 degrees.
    # Native's target was an idle enemy GoblinHut; a Cannon at the same offset is used so no enemy goblins interfere.
    ('v4-phase-a-1975100721', 0, (14.5, 12.5), 'Cannon', (14.5, 19.5), [(410, 1127)]),
]


@pytest.mark.parametrize('episode,side,hut_tile,enemy,enemy_tile,native', NATIVE_SPEAR_GOBLINS, ids=lambda v: str(v))
def test_goblin_hut_spear_goblins_spawn_beside_the_nearest_enemy(episode, side, hut_tile, enemy, enemy_tile, native):
    battle = BattleState(players=[PlayerState(0, card_levels={'GoblinHut': 11, 'Cannon': 11}),
                                  PlayerState(1, card_levels={'GoblinHut': 11, 'Cannon': 11})])
    foe = 1 - side
    battle.players[foe].hand = [enemy]
    battle.players[foe].elixir = 10
    assert battle.deploy_card(foe, enemy, Position(*enemy_tile))
    for _ in range(30):
        battle.step()
    battle.players[side].hand = ['GoblinHut']
    battle.players[side].elixir = 10
    assert battle.deploy_card(side, 'GoblinHut', Position(*hut_tile))
    hut = next(e for e in battle.entities.values() if e.player_id == side and e.card_stats.name == 'GoblinHut')
    seen, first = set(), []
    for _ in range(120):
        battle.step()
        for e in battle.entities.values():
            if isinstance(e, Troop) and e.player_id == side and e.card_stats.name == 'SpearGoblin' and e.id not in seen:
                seen.add(e.id)
                first.append((_units(e.position.x) - _units(hut.position.x), _units(e.position.y) - _units(hut.position.y)))
        if len(first) >= len(native):
            break
    assert len(first) >= len(native), first
    for (x, y), (nx, ny) in zip(first, native):
        assert abs(x - nx) <= 25 and abs(y - ny) <= 25, (episode, first, native)


def test_goblinstein_doctor_shot_damage_matches_native_level11():
    # Native T1 train recordings: every doctor shot takes 135 HP (troops and crown towers alike, 501 hits; none of 92),
    # i.e. base 53 x 256%. gamedata carried 36 (-> 92).
    battle = BattleState(players=[PlayerState(0, card_levels={'Goblinstein': 11}), PlayerState(1)])
    battle.players[0].hand = ['Goblinstein']
    battle.players[0].elixir = 10
    assert battle.deploy_card(0, 'Goblinstein', Position(4.5, 10.5))
    doctor = next(e for e in battle.entities.values() if e.card_stats.name == 'Goblinstein_doctor')
    assert doctor.max_hitpoints == 721
    assert doctor.damage == 135
