import numpy as np
import pytest

from clasher.battle import BattleState
from clasher.rl.determinism_check import compute_rollout_digest
from clasher.rl.oracle_direct_path import DirectPathFixedDepthThompsonOracle
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _public_signature(battle: BattleState):
    return (
        battle.tick,
        battle.time,
        battle.game_over,
        battle.winner,
        battle.next_entity_id,
        tuple(
            (
                player.elixir,
                tuple(player.hand),
                tuple(player.deck),
                tuple(player.cycle_queue),
                player.next_card_refill_cooldown_ms,
                player.left_tower_hp,
                player.right_tower_hp,
                player.king_tower_hp,
            )
            for player in battle.players
        ),
        tuple(
            (
                type(entity).__name__,
                entity.id,
                entity.player_id,
                entity.card_stats.name,
                entity.position.x,
                entity.position.y,
                entity.hitpoints,
                entity.target_id,
                entity.attack_cooldown,
                entity.deploy_delay_remaining,
                entity.placement_pending,
                entity.is_alive,
            )
            for entity in battle.entities.values()
        ),
    )


def _reference_step_logic_ticks(battle: BattleState, ticks: int) -> int:
    advanced = 0
    for _ in range(max(0, int(ticks))):
        if battle.game_over:
            break
        battle.step()
        advanced += 1
    return advanced


def test_batched_logic_ticks_match_repeated_steps_and_fast_caches():
    source = BattleState(fast_path=True)
    reference = source.clone()
    candidate = source.clone()

    expected_ticks = _reference_step_logic_ticks(reference, 8)
    actual_ticks = candidate.step_logic_ticks(8)

    assert actual_ticks == expected_ticks == 8
    assert _public_signature(candidate) == _public_signature(reference)
    assert candidate.rng.getstate() == reference.rng.getstate()
    assert [entity.id for entity in candidate._target_entities] == [
        entity.id for entity in reference._target_entities
    ]
    for name in (
        "_target_pos_x",
        "_target_pos_y",
        "_target_player",
        "_target_is_air",
        "_target_is_building",
        "_target_is_building_target",
        "_target_is_crown",
        "_target_is_targetable",
        "_target_requires_targetability_check",
        "_target_stealth_until",
        "_target_collision_radius",
        "_target_distance_discount_sq",
    ):
        np.testing.assert_array_equal(
            getattr(candidate, name),
            getattr(reference, name),
        )
    assert {
        cell: tuple(entity.id for entity in entities)
        for cell, entities in candidate._entity_buckets.items()
    } == {
        cell: tuple(entity.id for entity in entities)
        for cell, entities in reference._entity_buckets.items()
    }


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_batched_logic_ticks_preserve_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path,
):
    common = {
        "seed": 2301,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    candidate = BattleState.step_logic_ticks
    monkeypatch.setattr(BattleState, "step_logic_ticks", _reference_step_logic_ticks)
    reference_digest = compute_rollout_digest(**common)
    monkeypatch.setattr(BattleState, "step_logic_ticks", candidate)
    candidate_digest = compute_rollout_digest(**common)

    assert candidate_digest.sha256 == reference_digest.sha256
    assert candidate_digest.mask_shadow_mismatches == 0


def test_batched_logic_ticks_preserve_oracle_action_and_rng(monkeypatch):
    env = SelfPlayBattleEnv(
        seed=2301,
        decision_interval_ticks=8,
        max_ticks=512,
        engine_fast_path="on",
        reward_profile=DEFENSE_V2,
    )
    env.reset(seed=2301)
    assert env.battle is not None
    battle_rng_state = env.battle.rng.getstate()

    common = {
        "action_space": env.action_space,
        "decision_interval_ticks": 8,
        "plan_depth": 2,
        "num_simulations": 4,
        "rollout_action_samples": 16,
        "seed": 901,
        "reward_profile": DEFENSE_V2,
        "stable_root_candidates": True,
    }
    candidate = BattleState.step_logic_ticks
    monkeypatch.setattr(BattleState, "step_logic_ticks", _reference_step_logic_ticks)
    reference_planner = DirectPathFixedDepthThompsonOracle(**common)
    reference_actions = reference_planner.select_actions(env.battle)
    reference_rng_state = reference_planner.rng.bit_generator.state

    monkeypatch.setattr(BattleState, "step_logic_ticks", candidate)
    candidate_planner = DirectPathFixedDepthThompsonOracle(**common)
    candidate_actions = candidate_planner.select_actions(env.battle)

    assert candidate_actions == reference_actions
    assert candidate_planner.rng.bit_generator.state == reference_rng_state
    assert env.battle.rng.getstate() == battle_rng_state
