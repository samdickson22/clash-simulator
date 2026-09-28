import copy

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.reward_model import (
    DEFENSE_V2,
    DEFENSE_V3,
    OBJECTIVE_V1,
    DefenseOutcomeTracker,
    _board_value_edge_p0,
    _tiebreak_edge_p0,
    _tower_danger_edge_p0,
    objective_potential_p0,
    objective_win_prob_p0,
    potential_breakdown_p0,
    reward_potential_p0,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv


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


def test_defense_v3_strengthens_exposed_king_survival_signal():
    battle = BattleState()
    battle.players[0].left_tower_hp = 0.0
    before_v2 = reward_potential_p0(battle, DEFENSE_V2)
    before_v3 = reward_potential_p0(battle, DEFENSE_V3)

    battle.players[0].king_tower_hp -= 400.0
    delta_v2 = reward_potential_p0(battle, DEFENSE_V2) - before_v2
    delta_v3 = reward_potential_p0(battle, DEFENSE_V3) - before_v3

    assert delta_v3 < delta_v2 < 0.0


def test_defense_v3_strengthens_immediate_tower_danger_signal():
    battle = BattleState()
    threat = _spawn_troop(battle, "Knight", 1, Position(3.5, 20.0))
    far_v2 = reward_potential_p0(battle, DEFENSE_V2)
    far_v3 = reward_potential_p0(battle, DEFENSE_V3)

    threat.position = Position(3.5, 8.0)
    danger_delta_v2 = reward_potential_p0(battle, DEFENSE_V2) - far_v2
    danger_delta_v3 = reward_potential_p0(battle, DEFENSE_V3) - far_v3

    assert danger_delta_v3 < danger_delta_v2 < 0.0


def test_defense_components_are_antisymmetric_under_identical_mirror_deployments():
    battle = BattleState()
    _spawn_troop(battle, "Knight", 0, Position(3.5, 20.0))
    _spawn_troop(battle, "Knight", 1, Position(14.5, 12.0))
    breakdown = potential_breakdown_p0(battle)

    assert abs(breakdown.board_value) < 1e-9
    assert abs(breakdown.tower_danger) < 1e-9


def test_defense_outcome_rewards_one_clean_clearance_event():
    battle = BattleState()
    threat = _spawn_troop(battle, "Knight", 1, Position(3.5, 8.0))
    tracker = DefenseOutcomeTracker()

    opened = tracker.advance(battle)
    assert opened.started == {0: True, 1: False}
    assert opened.player_rewards == {0: 0.0, 1: 0.0}

    battle.tick += 8
    threat.hitpoints = 0.0
    threat.is_alive = False
    cleared = tracker.advance(battle)
    assert cleared.resolved == {0: True, 1: False}
    assert cleared.player_rewards[0] > 0.0
    assert cleared.edge_p0 > 0.0

    # The same dead threat cannot manufacture another outcome reward.
    repeated = tracker.advance(battle)
    assert repeated.resolved == {0: False, 1: False}
    assert repeated.player_rewards == {0: 0.0, 1: 0.0}


def test_defense_outcome_times_out_once_and_requires_clearance_to_rearm():
    battle = BattleState()
    first_threat = _spawn_troop(battle, "Knight", 1, Position(3.5, 8.0))
    tracker = DefenseOutcomeTracker(horizon_ticks=80)
    tracker.advance(battle)

    battle.tick += 80
    timed_out = tracker.advance(battle)
    assert timed_out.resolved == {0: True, 1: False}
    assert timed_out.player_rewards[0] < 0.0

    battle.tick += 8
    lingering = tracker.advance(battle)
    assert lingering.started == {0: False, 1: False}
    assert lingering.resolved == {0: False, 1: False}

    first_threat.hitpoints = 0.0
    first_threat.is_alive = False
    tracker.advance(battle)
    _spawn_troop(battle, "Knight", 1, Position(3.5, 8.0))
    reopened = tracker.advance(battle)
    assert reopened.started == {0: True, 1: False}


def test_destroyed_tower_cannot_look_like_successful_danger_clearance():
    battle = BattleState()
    threat = _spawn_troop(battle, "Knight", 1, Position(3.5, 8.0))
    tracker = DefenseOutcomeTracker()
    tracker.advance(battle)

    battle.tick += 8
    threat.hitpoints = 0.0
    threat.is_alive = False
    battle.players[0].left_tower_hp = 0.0
    resolved = tracker.advance(battle)

    assert resolved.resolved[0]
    assert resolved.player_rewards[0] < 0.0


def test_mirrored_clean_defenses_have_zero_event_edge():
    battle = BattleState()
    threat_to_p0 = _spawn_troop(battle, "Knight", 1, Position(3.5, 8.0))
    threat_to_p1 = _spawn_troop(battle, "Knight", 0, Position(14.5, 24.0))
    tracker = DefenseOutcomeTracker()

    opened = tracker.advance(battle)
    assert opened.started == {0: True, 1: True}

    battle.tick += 8
    for threat in (threat_to_p0, threat_to_p1):
        threat.hitpoints = 0.0
        threat.is_alive = False
    resolved = tracker.advance(battle)

    assert resolved.player_rewards[0] == resolved.player_rewards[1]
    assert resolved.edge_p0 == 0.0


def test_env_lazily_builds_checkpoint_compatible_canonical_lane_globals():
    env = SelfPlayBattleEnv(canonical_lane_globals=True)

    assert env.structured_obs_builder.canonical_lane_globals is True
