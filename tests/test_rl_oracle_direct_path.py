import copy
import hashlib
from types import MethodType

import pytest

from clasher.rl.oracle_direct_path import DirectPathFixedDepthThompsonOracle
from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.oracle_sampling import sample_action_subset
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _planner_trace(
    planner_type,
    *,
    stable_root_candidates: bool,
) -> tuple[list[tuple[int, int, int, int]], str, dict]:
    env = SelfPlayBattleEnv(
        seed=2301,
        decision_interval_ticks=2,
        max_ticks=128,
        engine_fast_path="on",
        reward_profile=DEFENSE_V2,
    )
    env.reset(seed=2301)
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
    hasher = hashlib.sha256()
    trace: list[tuple[int, int, int, int]] = []
    for _ in range(3):
        assert env.battle is not None
        before = planner._state_key(env.battle)
        input_state = copy.deepcopy(env.battle.get_state_summary())
        input_rng_state = copy.deepcopy(env.battle.rng.getstate())
        actions = planner.select_actions(env.battle)
        assert env.battle.get_state_summary() == input_state
        assert env.battle.rng.getstate() == input_rng_state
        assert planner._state_key(env.battle) == before
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
                )
            ).encode()
        )
        trace.append(
            (actions[0], actions[1], env.battle.tick, len(env.battle.entities))
        )
    return trace, hasher.hexdigest(), copy.deepcopy(planner.rng.bit_generator.state)


@pytest.mark.parametrize(
    ("stable_root_candidates", "expected_trace", "expected_digest"),
    [
        (
            False,
            [(233, 107, 2, 8), (2304, 259, 4, 8), (42, 2304, 6, 9)],
            "2946b87b088a9c6df38de89fed9676329b9d2ce02142e10c564e820a9d374776",
        ),
        (
            True,
            [(193, 839, 2, 13), (1846, 247, 4, 14), (2304, 2304, 6, 14)],
            "7bda01530bd8ed0b55527bddb1d54db86514363faa868901ac0f57239b2a0fee",
        ),
    ],
)
def test_direct_path_preserves_labels_battle_states_rng_and_hashes(
    stable_root_candidates: bool,
    expected_trace: list[tuple[int, int, int, int]],
    expected_digest: str,
):
    reference = _planner_trace(
        FixedDepthThompsonOracle,
        stable_root_candidates=stable_root_candidates,
    )
    candidate = _planner_trace(
        DirectPathFixedDepthThompsonOracle,
        stable_root_candidates=stable_root_candidates,
    )

    assert reference == candidate
    assert candidate[0] == expected_trace
    assert candidate[1] == expected_digest
