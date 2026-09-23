import copy

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.reward_model import (
    DEFENSE_V2,
    OBJECTIVE_V1,
    _board_value_edge_p0,
    _tiebreak_edge_p0,
    _tower_danger_edge_p0,
    objective_potential_p0,
    objective_win_prob_p0,
    potential_breakdown_p0,
    reward_potential_p0,
)


def _spawn_troop(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = copy.deepcopy(battle.card_loader.get_card(card_name))
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    troop = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    return troop


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


def test_legacy_objective_profile_is_unchanged_by_board_units():
    battle = BattleState()
    base = reward_potential_p0(battle, OBJECTIVE_V1)
    _spawn_troop(battle, "Knight", 0, Position(9.0, 24.0))

    assert reward_potential_p0(battle, OBJECTIVE_V1) == base
    assert objective_potential_p0(battle) == base


def test_defense_profile_values_remaining_board_health_without_card_name_rules():
    battle = BattleState()
    troop = _spawn_troop(battle, "Knight", 0, Position(9.0, 20.0))
    troop.card_stats.name = "SyntheticFutureTroop"

    full_value = _board_value_edge_p0(battle)
    troop.hitpoints *= 0.25
    damaged_value = _board_value_edge_p0(battle)

    assert full_value > damaged_value > 0.0
    assert reward_potential_p0(battle, DEFENSE_V2) > reward_potential_p0(
        battle,
        OBJECTIVE_V1,
    )


def test_tower_danger_increases_as_enemy_ground_threat_approaches():
    battle = BattleState()
    threat = _spawn_troop(battle, "Knight", 1, Position(3.5, 20.0))
    far_danger = _tower_danger_edge_p0(battle)
    threat.position = Position(3.5, 8.0)
    near_danger = _tower_danger_edge_p0(battle)

    assert near_danger < far_danger <= 0.0


def test_defense_potential_does_not_read_internal_target_ids():
    battle = BattleState()
    threat = _spawn_troop(battle, "Knight", 1, Position(3.5, 8.0))
    before = reward_potential_p0(battle, DEFENSE_V2)

    threat.target_id = 987_654_321

    assert reward_potential_p0(battle, DEFENSE_V2) == before


def test_removing_enemy_push_gives_one_telescoping_defensive_improvement():
    battle = BattleState()
    threat = _spawn_troop(battle, "Knight", 1, Position(3.5, 8.0))
    before = reward_potential_p0(battle, DEFENSE_V2)
    threat.hitpoints = 0.0
    threat.is_alive = False
    after = reward_potential_p0(battle, DEFENSE_V2)

    assert after > before
    # A potential is a state function: observing the same cleared state again
    # cannot manufacture another reward.
    assert reward_potential_p0(battle, DEFENSE_V2) == after


def test_defense_components_are_antisymmetric_under_identical_mirror_deployments():
    battle = BattleState()
    _spawn_troop(battle, "Knight", 0, Position(3.5, 20.0))
    _spawn_troop(battle, "Knight", 1, Position(14.5, 12.0))
    breakdown = potential_breakdown_p0(battle)

    assert abs(breakdown.board_value) < 1e-9
    assert abs(breakdown.tower_danger) < 1e-9
