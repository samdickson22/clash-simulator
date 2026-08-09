import copy
import hashlib
from types import MethodType

import numpy as np
import pytest

from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.oracle_sampling import sample_action_subset
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _reference_sample_action_subset(
    legal_actions: np.ndarray,
    *,
    sample_limit: int,
    no_op_action: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if legal_actions.size <= sample_limit:
        return legal_actions

    selected = {int(no_op_action)}
    other = legal_actions[legal_actions != no_op_action]
    needed = max(0, sample_limit - len(selected))
    if needed > 0 and other.size > 0:
        picks = rng.choice(
            other,
            size=min(needed, other.size),
            replace=False,
        )
        selected.update(int(action) for action in picks.tolist())
    return np.asarray(sorted(selected), dtype=np.int64)


@pytest.mark.parametrize(
    ("legal_actions", "sample_limit", "no_op_action"),
    [
        (np.asarray([0, 4, 8], dtype=np.int64), 8, 8),
        (np.asarray([0, 4, 8], dtype=np.int64), 1, 8),
        (np.asarray([0, 4, 8], dtype=np.int64), 2, 8),
        (np.asarray([0, 4, 8], dtype=np.int64), 0, 8),
        (np.asarray([0, 4, 9], dtype=np.int64), 2, 8),
        (np.asarray([8], dtype=np.int64), 0, 8),
        (np.arange(0, 2306, 3, dtype=np.int64), 64, 2304),
    ],
)
def test_sample_action_subset_matches_reference_output_and_rng_state(
    legal_actions: np.ndarray,
    sample_limit: int,
    no_op_action: int,
):
    reference_rng = np.random.default_rng(2301)
    candidate_rng = np.random.default_rng(2301)

    reference = _reference_sample_action_subset(
        legal_actions,
        sample_limit=sample_limit,
        no_op_action=no_op_action,
        rng=reference_rng,
    )
    candidate = sample_action_subset(
        legal_actions,
        sample_limit=sample_limit,
        no_op_action=no_op_action,
        rng=candidate_rng,
    )

    np.testing.assert_array_equal(candidate, reference)
    assert candidate_rng.bit_generator.state == reference_rng.bit_generator.state
    if legal_actions.size <= sample_limit:
        assert candidate is legal_actions


def _planner_trace(*, optimized_sampling: bool) -> tuple[list[tuple[int, int, int]], str]:
    env = SelfPlayBattleEnv(
        seed=2301,
        decision_interval_ticks=2,
        max_ticks=64,
        engine_fast_path="on",
        reward_profile=DEFENSE_V2,
    )
    env.reset(seed=2301)
    planner = FixedDepthThompsonOracle(
        action_space=env.action_space,
        decision_interval_ticks=2,
        plan_depth=2,
        num_simulations=4,
        rollout_action_samples=16,
        seed=901,
        reward_profile=DEFENSE_V2,
        stable_root_candidates=True,
    )
    if optimized_sampling:

        def optimized(self, legal_actions):
            return sample_action_subset(
                legal_actions,
                sample_limit=self.rollout_action_samples,
                no_op_action=self.action_space.no_op_action,
                rng=self.rng,
            )

        planner._sample_actions = MethodType(optimized, planner)

    hasher = hashlib.sha256()
    trace: list[tuple[int, int, int]] = []
    for _ in range(3):
        assert env.battle is not None
        before = planner._state_key(env.battle)
        input_rng_state = copy.deepcopy(env.battle.rng.getstate())
        actions = planner.select_actions(env.battle)
        assert env.battle.rng.getstate() == input_rng_state
        rewards, done, _ = env.step(actions)
        assert env.battle is not None
        after = planner._state_key(env.battle)
        hasher.update(
            repr(
                (
                    actions[0],
                    actions[1],
                    before,
                    after,
                    rewards[0],
                    rewards[1],
                    done,
                    planner.rng.bit_generator.state,
                )
            ).encode()
        )
        trace.append((actions[0], actions[1], env.battle.tick))
    return trace, hasher.hexdigest()


def test_optimized_sampling_preserves_joint_planner_actions_states_and_rng():
    reference_trace, reference_digest = _planner_trace(optimized_sampling=False)
    candidate_trace, candidate_digest = _planner_trace(optimized_sampling=True)

    assert candidate_trace == reference_trace
    assert candidate_digest == reference_digest
