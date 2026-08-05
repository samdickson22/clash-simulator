from clasher.battle import BattleState
from clasher.rl.reward_model import (
    _tiebreak_edge_p0,
    objective_potential_p0,
    objective_win_prob_p0,
)


def test_objective_potential_is_neutral_at_start():
    battle = BattleState()
    value = objective_potential_p0(battle)
    assert abs(value) < 1e-6
    prob = objective_win_prob_p0(battle)
    assert 0.45 <= prob <= 0.55


def test_early_king_chip_is_penalized_when_both_princess_alive():
    battle = BattleState()
    base = objective_potential_p0(battle)
    battle.players[1].king_tower_hp = max(0.0, battle.players[1].king_tower_hp - 400.0)
    chipped = objective_potential_p0(battle)
    assert chipped < base


def test_princess_damage_is_rewarded():
    battle = BattleState()
    base = objective_potential_p0(battle)
    battle.players[1].left_tower_hp = max(0.0, battle.players[1].left_tower_hp - 400.0)
    pressured = objective_potential_p0(battle)
    assert pressured > base


def test_king_damage_becomes_rewarding_after_princess_falls():
    battle = BattleState()
    battle.players[1].left_tower_hp = 0.0
    no_king_chip = objective_potential_p0(battle)
    battle.players[1].king_tower_hp = max(0.0, battle.players[1].king_tower_hp - 400.0)
    king_chip = objective_potential_p0(battle)
    assert king_chip > no_king_chip


def test_destroying_enemy_princess_tower_rewards_attacker_not_defender():
    battle = BattleState()
    battle.players[1].left_tower_hp = 0.0

    assert battle.get_crown_count(0) == 1
    assert battle.get_crown_count(1) == 0
    assert objective_potential_p0(battle) > 0.0


def test_tiebreak_reward_ignores_destroyed_towers_and_compares_absolute_hp():
    battle = BattleState()
    battle.players[0].left_tower_hp = 0.0
    battle.players[1].left_tower_hp = 0.0
    battle.players[0].right_tower_hp = 1000.0
    battle.players[1].right_tower_hp = 900.0

    assert _tiebreak_edge_p0(battle) > 0.0

    # A lower percentage of the larger King Tower still wins the tiebreak
    # when its absolute HP is greater than the opposing Princess Tower.
    battle.players[0].right_tower_hp = 0.0
    battle.players[0].king_tower_hp = 1000.0
    battle.players[1].right_tower_hp = 900.0
    battle.players[1].king_tower_hp = 1200.0
    assert _tiebreak_edge_p0(battle) > 0.0
