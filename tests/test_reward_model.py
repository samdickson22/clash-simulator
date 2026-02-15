from clasher.battle import BattleState
from clasher.rl.reward_model import objective_potential_p0, objective_win_prob_p0


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
