import hashlib

from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _planner_trace(
    *, stable_root_candidates: bool = False
) -> tuple[list[tuple[int, int, int, int]], str]:
    env = SelfPlayBattleEnv(
        seed=2301,
        decision_interval_ticks=2,
        max_ticks=128,
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
        stable_root_candidates=stable_root_candidates,
    )
    hasher = hashlib.sha256()
    trace = []
    for _ in range(3):
        assert env.battle is not None
        before = planner._state_key(env.battle)
        actions = planner.select_actions(env.battle)
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
    return trace, hasher.hexdigest()


def test_oracle_fixed_seed_action_and_state_trace_is_exact():
    trace, digest = _planner_trace()

    assert trace == [
        (233, 107, 2, 8),
        (2304, 259, 4, 8),
        (42, 2304, 6, 9),
    ]
    assert digest == "2946b87b088a9c6df38de89fed9676329b9d2ce02142e10c564e820a9d374776"


def test_oracle_reuses_root_legal_masks_across_simulations():
    env = SelfPlayBattleEnv(seed=2301, decision_interval_ticks=1, max_ticks=64)
    env.reset(seed=2301)
    assert env.battle is not None
    root = env.battle
    original = env.action_space.legal_action_mask
    root_calls = 0

    def counted_legal_action_mask(battle, player_id, *args, **kwargs):
        nonlocal root_calls
        if battle is root:
            root_calls += 1
        return original(battle, player_id, *args, **kwargs)

    env.action_space.legal_action_mask = counted_legal_action_mask
    planner = FixedDepthThompsonOracle(
        action_space=env.action_space,
        decision_interval_ticks=1,
        plan_depth=2,
        num_simulations=5,
        rollout_action_samples=8,
        seed=901,
    )

    planner.select_actions(root)

    assert root_calls == 2


def test_stable_root_fixed_seed_action_and_state_trace_is_exact():
    trace, digest = _planner_trace(stable_root_candidates=True)

    assert trace == [
        (193, 839, 2, 13),
        (1846, 247, 4, 14),
        (2304, 2304, 6, 14),
    ]
    assert digest == "7bda01530bd8ed0b55527bddb1d54db86514363faa868901ac0f57239b2a0fee"


def test_stable_root_candidates_output_only_simulated_actions():
    env = SelfPlayBattleEnv(seed=2301, decision_interval_ticks=1, max_ticks=64)
    env.reset(seed=2301)
    assert env.battle is not None
    planner = FixedDepthThompsonOracle(
        action_space=env.action_space,
        decision_interval_ticks=1,
        plan_depth=1,
        num_simulations=5,
        rollout_action_samples=8,
        seed=901,
        stable_root_candidates=True,
    )
    simulated = {0: set(), 1: set()}
    original = planner._apply_joint_action

    def record_joint_action(battle, action0, action1):
        simulated[0].add(action0)
        simulated[1].add(action1)
        original(battle, action0, action1)

    planner._apply_joint_action = record_joint_action
    actions = planner.select_actions(env.battle)

    for player_id in (0, 1):
        assert actions[player_id] in simulated[player_id]


def test_stable_root_candidates_are_sampled_once_per_player():
    env = SelfPlayBattleEnv(seed=2301, decision_interval_ticks=1, max_ticks=64)
    env.reset(seed=2301)
    assert env.battle is not None
    planner = FixedDepthThompsonOracle(
        action_space=env.action_space,
        decision_interval_ticks=1,
        plan_depth=1,
        num_simulations=5,
        rollout_action_samples=8,
        seed=901,
        stable_root_candidates=True,
    )
    original = planner._sample_actions
    sample_calls = 0

    def counted_sample_actions(legal):
        nonlocal sample_calls
        sample_calls += 1
        return original(legal)

    planner._sample_actions = counted_sample_actions
    planner.select_actions(env.battle)

    assert sample_calls == 2
