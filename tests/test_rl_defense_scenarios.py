import random

import pytest

from clasher.rl.defense_scenarios import (
    apply_defense_scenario,
    defense_scenario_outcome,
    defense_scenario_resource_loss,
    eligible_threat_cards,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _scenario(seed: int, learner_player: int):
    env = SelfPlayBattleEnv(seed=seed)
    env.reset(seed=seed)
    assert env.battle is not None
    before = set(env.battle.entities)
    spec = apply_defense_scenario(
        env.battle,
        learner_player,
        rng=random.Random(seed + 17),
        tower_slot="left",
    )
    spawned = set(env.battle.entities) - before
    return env.battle, spec, spawned


def test_defense_scenario_is_deterministic_and_uses_the_attacker_deck():
    first, first_spec, first_spawned = _scenario(2301, 0)
    _, second_spec, second_spawned = _scenario(2301, 0)

    assert first_spec == second_spec
    assert len(first_spawned) == len(second_spawned) > 0
    assert set(first_spec.threat_cards) <= set(first.players[1].deck)
    assert set(first_spec.threat_cards) <= set(eligible_threat_cards(first, 1))
    assert first_spec.initial_danger >= 0.05
    assert first.players[0].elixir == first.players[0].max_elixir


def test_clearing_scenario_scores_better_than_losing_tower_health():
    battle, spec, spawned = _scenario(2301, 0)
    for entity_id in spawned:
        battle.entities[entity_id].hitpoints = 0.0
        battle.entities[entity_id].is_alive = False
    cleared = defense_scenario_outcome(battle, spec)

    battle.players[0].left_tower_hp *= 0.70
    damaged = defense_scenario_outcome(battle, spec)

    assert cleared == 1.0
    assert damaged < 0.0


def test_cleared_scenario_charges_elixir_but_credits_surviving_defenders():
    battle, spec, spawned = _scenario(2301, 0)
    for entity_id in spawned:
        battle.entities[entity_id].hitpoints = 0.0
        battle.entities[entity_id].is_alive = False
    efficient = defense_scenario_outcome(battle, spec)

    battle.players[0].elixir = 4.0
    spent = defense_scenario_outcome(battle, spec)
    assert defense_scenario_resource_loss(battle, spec) == pytest.approx(0.6)
    assert spent < efficient

    knight = battle.card_loader.get_card("Knight")
    assert knight is not None
    battle._spawn_troop(battle.entities[next(iter(battle.entities))].position, 0, knight)
    surviving = defense_scenario_outcome(battle, spec)
    assert surviving > spent


def test_player_one_scenario_mirrors_toward_the_upper_princess_tower():
    battle, spec, spawned = _scenario(2302, 1)

    assert spec.learner_player == 1
    assert spec.initial_danger >= 0.05
    assert all(battle.entities[entity_id].player_id == 0 for entity_id in spawned)
    assert all(battle.entities[entity_id].position.y < 25.5 for entity_id in spawned)


def test_opt_in_scenario_environment_ends_at_relative_horizon_with_zero_sum_reward():
    env = SelfPlayBattleEnv(
        seed=2301,
        learner_player_id=0,
        defense_scenario_probability=1.0,
        defense_scenario_horizon_ticks=16,
        reward_profile="defense-v2",
    )
    env.reset(seed=2301)
    assert env.defense_scenario is not None
    no_op = env.action_space.no_op_action
    masks = {player: env.get_action_mask(player) for player in (0, 1)}

    _, done, _ = env.step({0: no_op, 1: no_op}, pre_action_masks=masks)
    assert not done
    masks = {player: env.get_action_mask(player) for player in (0, 1)}
    rewards, done, _ = env.step({0: no_op, 1: no_op}, pre_action_masks=masks)

    assert done
    assert rewards[0] < 0.0
    assert rewards[0] + rewards[1] == 0.0


def test_default_environment_never_injects_a_defense_scenario():
    env = SelfPlayBattleEnv(seed=2301)
    env.reset(seed=2301)

    assert env.defense_scenario is None
