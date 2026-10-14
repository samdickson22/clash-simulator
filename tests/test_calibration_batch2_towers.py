"""Calibration batch 2, towers topic: crown-tower damage timing and amounts from native T1 train recordings."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.player import PlayerState


def _battle(card, side=0):
    players = [PlayerState(0), PlayerState(1)]
    players[side] = PlayerState(side, card_levels={card: 11})
    battle = BattleState(players=players)
    battle.players[side].hand = [card]
    battle.players[side].elixir = 10
    return battle


def _red_left_princess(battle):
    return next(
        e for e in battle.entities.values()
        if e.player_id == 1 and e.card_stats.name == 'Tower' and e.position.x < 9
    )


def _tower_drops(battle, tower, ticks):
    drops, hp = [], tower.hitpoints
    for _ in range(ticks):
        battle.step()
        if tower.hitpoints != hp:
            drops.append((battle.tick, round(hp - tower.hitpoints)))
            hp = tower.hitpoints
    return drops


def test_miner_emergence_clock_starts_on_arrival_tick():
    # Native rich phaseRuntime of train Miners: deployRemainingMs = 950 - 50 * (ticks since the first frame
    # at the tap), so the arrival tick already reads 950 (e.g. ep 1975100702: first frame at (5500, 25500)
    # at 2512..2513, deployRemainingMs 150 at 2528). Ours held 1000 there and surfaced a tick late.
    battle = _battle('Miner')
    assert battle.deploy_card(0, 'Miner', Position(5.5, 25.5))
    miner = next(e for e in battle.entities.values() if e.player_id == 0 and e.card_stats.name == 'Miner')
    for _ in range(80):
        battle.step()
        if (round(miner.position.x * 1000), round(miner.position.y * 1000)) == (5500, 25500):
            break
    else:
        pytest.fail('Miner never reached its tap')
    assert miner.deploy_delay_remaining == pytest.approx(0.95)


def test_miner_first_crown_tower_hit_one_tick_after_old_timing():
    # Native: first 39-damage crown-tower hit at exec+65 on every exactly sampled train play (exec+64..66,
    # one tick earlier than ours in each). On a fresh board ours now lands it 66 ticks after deploy_card
    # (67 before the fix); the replay harness, which issues at exec-1, gives exec+65 like native.
    battle = _battle('Miner')
    tower = _red_left_princess(battle)
    start = battle.tick
    assert battle.deploy_card(0, 'Miner', Position(5.5, 25.5))
    drops = _tower_drops(battle, tower, 90)
    assert drops and drops[0][1] == 39
    assert drops[0][0] - start == 66, drops[0][0] - start


@pytest.mark.parametrize('card, child, native_ms', [
    ('GoblinBarrel', 'Goblin', 1100),       # 496 exact-spawn rich samples, all 1100
    ('BarbLog', 'Barbarian', 1000),         # 176 samples
    ('RoyalDelivery', 'DeliveryRecruit', 250),  # 103 samples
])
def test_projectile_spawned_troop_keeps_full_deploy_on_spawn_tick(card, child, native_ms):
    # Native troops created by a projectile impact read their full configured deployRemainingMs on the spawn
    # tick (ordinary card deploys read 950 = one step consumed, as ours does). Ours consumed a step at impact.
    battle = _battle(card)
    assert battle.deploy_card(0, card, Position(9.5, 10.5))
    seen = set(battle.entities)
    for _ in range(140):
        battle.step()
        new = [battle.entities[i] for i in set(battle.entities) - seen]
        seen |= set(battle.entities)
        kids = [e for e in new if isinstance(e, Troop) and e.card_stats.name == child]
        if kids:
            for kid in kids:
                assert kid.deploy_delay_remaining == pytest.approx(native_ms / 1000.0), card
            return
    pytest.fail(f'{card} never spawned {child}')


def test_wallbreaker_blast_matches_native_281():
    # Native: Wall Breaker blasts drop 281 HP from crown towers (458 drops) and from troops (83) at level 11
    # = 110 x 256%; ours had 137 x 256% = 350.
    battle = _battle('Wallbreakers')
    tower = _red_left_princess(battle)
    assert battle.deploy_card(0, 'Wallbreakers', Position(3.5, 14.5))
    drops = _tower_drops(battle, tower, 200)
    assert drops, 'no blast reached the tower'
    assert all(d == 281 for _, d in drops), drops


def test_poison_crown_tower_pulse_is_22():
    # Native: crown towers drop 22 per Poison pulse (e.g. ep 1975100700 3052 -> 3030 -> 3008 -> 2986);
    # 92 x 23% with native ceiling arithmetic. Ours had 21.
    battle = _battle('Poison')
    tower = _red_left_princess(battle)
    assert battle.deploy_card(0, 'Poison', Position(3.5, 25.5))
    drops = _tower_drops(battle, tower, 60)
    assert drops and all(d == 22 for _, d in drops), drops

