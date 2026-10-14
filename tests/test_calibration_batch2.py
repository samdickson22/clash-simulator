"""Engine calibration batch 2 (reports/bot/calibration/BATCH2.md): rules measured on native 15.535 recordings."""
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.player import PlayerState


def _battle(cards):
    return BattleState(players=[PlayerState(0, card_levels=dict.fromkeys(cards, 11)), PlayerState(1)])


def _troops(battle, pid=0):
    return [e for e in battle.entities.values() if isinstance(e, Troop) and e.player_id == pid]


# Native T1 train recordings: all 696 BarbLog Barbarian bodies (data global id 34000009) have max_hp 716 at
# level 11, i.e. base 280 x 256%. Our gamedata carried 270 (-> 691).
def test_barblog_barbarian_hitpoints_match_native_level11():
    battle = _battle(['BarbLog'])
    battle.players[0].hand = ['BarbLog']
    battle.players[0].elixir = 10
    assert battle.deploy_card(0, 'BarbLog', Position(8.5, 6.5))
    barbs = []
    for _ in range(200):
        battle.step()
        barbs = [e for e in _troops(battle) if getattr(e.card_stats, 'name', '') == 'Barbarian']
        if barbs:
            break
    assert barbs
    assert {e.max_hitpoints for e in barbs} == {716}
