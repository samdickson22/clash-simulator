import copy

import numpy as np

from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _legal_spend_action(env: SelfPlayBattleEnv, player_id: int) -> int:
    assert env.battle is not None
    mask = env.action_space.legal_action_mask(env.battle, player_id, fast_path=False)
    legal = np.flatnonzero(mask[: env.action_space.no_op_action])
    assert legal.size > 0
    return int(legal[0])


def test_elixir_leak_penalty_discourages_noop_at_cap():
    env = SelfPlayBattleEnv(
        decision_interval_ticks=0,
        max_ticks=9090,
        decks_path="decks.json",
        seed=321,
        mirror_match=True,
        canonical_perspective=True,
        engine_fast_path="off",
    )
    env.reset()
    assert env.battle is not None
    env.battle.players[0].elixir = 10.0
    env.battle.players[1].elixir = 10.0

    p0_spend = _legal_spend_action(env, 0)
    p1_spend = _legal_spend_action(env, 1)
    no_op = env.action_space.no_op_action

    env_a = copy.deepcopy(env)
    rewards_a, done_a, _ = env_a.step({0: no_op, 1: p1_spend})
    assert not done_a

    env_b = copy.deepcopy(env)
    rewards_b, done_b, _ = env_b.step({0: p0_spend, 1: p1_spend})
    assert not done_b

    assert rewards_b[0] > rewards_a[0]
    assert rewards_b[1] < rewards_a[1]


def test_equal_leak_keeps_zero_sum_balance():
    env = SelfPlayBattleEnv(
        decision_interval_ticks=0,
        max_ticks=9090,
        decks_path="decks.json",
        seed=654,
        mirror_match=True,
        canonical_perspective=True,
        engine_fast_path="off",
    )
    env.reset()
    assert env.battle is not None
    env.battle.players[0].elixir = 10.0
    env.battle.players[1].elixir = 10.0
    no_op = env.action_space.no_op_action

    rewards, done, _ = env.step({0: no_op, 1: no_op})
    assert not done
    assert abs((rewards[0] + rewards[1])) < 1e-9
