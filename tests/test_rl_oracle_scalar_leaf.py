import copy
from types import MethodType
from unittest.mock import patch

import pytest

from clasher.rl.oracle_direct_path import DirectPathFixedDepthThompsonOracle
from clasher.rl.oracle_planner import FixedDepthThompsonOracle, _PlayerBandit
from clasher.rl.oracle_sampling import sample_action_subset
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _single_label(
    planner_type,
    *,
    stable_root_candidates: bool,
) -> tuple[
    tuple[dict[int, int], list[tuple[int, float]], tuple, object, dict],
    tuple,
    object,
]:
    env = SelfPlayBattleEnv(
        seed=2301,
        decision_interval_ticks=2,
        max_ticks=128,
        engine_fast_path="on",
        reward_profile=DEFENSE_V2,
    )
    env.reset(seed=2301)
    assert env.battle is not None
    planner = planner_type(
        action_space=env.action_space,
        decision_interval_ticks=2,
        plan_depth=2,
        num_simulations=4,
        rollout_action_samples=16,
        seed=901,
        reward_profile=DEFENSE_V2,
        stable_root_candidates=stable_root_candidates,
    )

    def optimized_sampling(self, legal_actions):
        return sample_action_subset(
            legal_actions,
            sample_limit=self.rollout_action_samples,
            no_op_action=self.action_space.no_op_action,
            rng=self.rng,
        )

    planner._sample_actions = MethodType(optimized_sampling, planner)
    updates: list[tuple[int, float]] = []
    original_update = _PlayerBandit.update

    def record_update(self, action: int, reward_prob: float) -> None:
        updates.append((int(action), float(reward_prob)))
        original_update(self, action, reward_prob)

    input_key = planner._state_key(env.battle)
    input_rng_state = copy.deepcopy(env.battle.rng.getstate())
    with patch.object(_PlayerBandit, "update", record_update):
        actions = planner.select_actions(env.battle)

    return (
        actions,
        updates,
        planner._state_key(env.battle),
        copy.deepcopy(env.battle.rng.getstate()),
        copy.deepcopy(planner.rng.bit_generator.state),
    ), input_key, input_rng_state


@pytest.mark.parametrize("stable_root_candidates", [False, True])
def test_scalar_leaf_preserves_every_backup_value_and_rng(
    stable_root_candidates: bool,
):
    reference, reference_key, reference_battle_rng = _single_label(
        FixedDepthThompsonOracle,
        stable_root_candidates=stable_root_candidates,
    )
    candidate, candidate_key, candidate_battle_rng = _single_label(
        DirectPathFixedDepthThompsonOracle,
        stable_root_candidates=stable_root_candidates,
    )

    assert candidate == reference
    assert candidate_key == reference_key
    assert candidate_battle_rng == reference_battle_rng


def test_scalar_leaf_keeps_dictionary_evaluator_compatible_but_unused():
    env = SelfPlayBattleEnv(seed=2301, max_ticks=64, reward_profile=DEFENSE_V2)
    env.reset(seed=2301)
    assert env.battle is not None
    planner = DirectPathFixedDepthThompsonOracle(
        action_space=env.action_space,
        decision_interval_ticks=1,
        plan_depth=1,
        num_simulations=1,
        rollout_action_samples=4,
        seed=901,
        reward_profile=DEFENSE_V2,
        stable_root_candidates=True,
    )

    public_values = planner._evaluate_state_prob(env.battle)
    assert isinstance(public_values, dict)
    assert public_values == {
        0: planner._evaluate_state_prob_p0(env.battle),
        1: 1.0 - planner._evaluate_state_prob_p0(env.battle),
    }
    with patch.object(
        planner,
        "_evaluate_state_prob",
        side_effect=AssertionError("dictionary evaluator used internally"),
    ):
        planner.select_actions(env.battle)
