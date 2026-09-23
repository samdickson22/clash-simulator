import copy

import numpy as np
import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.legacy_model import MaskedPolicyValueNet
from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.train_dagger_oracle import (
    DaggerReplayBuffer,
    _collect_dagger_data,
    _supervised_update,
)


def test_oracle_planner_actions_are_legal():
    env = SelfPlayBattleEnv(decision_interval_ticks=4, max_ticks=256, seed=3)
    env.reset()
    planner = FixedDepthThompsonOracle(
        action_space=env.action_space,
        decision_interval_ticks=env.decision_interval_ticks,
        plan_depth=2,
        num_simulations=3,
        rollout_action_samples=24,
        seed=5,
    )
    assert env.battle is not None
    actions = planner.select_actions(env.battle)
    for player_id in (0, 1):
        mask = env.get_action_mask(player_id)
        assert bool(mask[actions[player_id]])


def test_oracle_planner_uses_explicit_reward_profile():
    battle = BattleState()
    stats = copy.deepcopy(battle.card_loader.get_card("Knight"))
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(Position(9.0, 20.0), 0, stats)
    troop = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False

    objective = FixedDepthThompsonOracle()._evaluate_state_prob(battle)[0]
    defensive = FixedDepthThompsonOracle(
        reward_profile=DEFENSE_V2
    )._evaluate_state_prob(battle)[0]

    assert defensive > objective


def test_oracle_planner_rejects_unknown_reward_profile():
    with pytest.raises(ValueError, match="unknown reward profile"):
        FixedDepthThompsonOracle(reward_profile="tower-race-v0")


def test_dagger_collect_and_supervised_update_smoke():
    rng = np.random.default_rng(7)
    env = SelfPlayBattleEnv(decision_interval_ticks=4, max_ticks=256, seed=7)
    env.reset()
    obs0 = env.get_observation(0)
    model = MaskedPolicyValueNet(
        board_channels=obs0.board.shape[0],
        hud_size=obs0.hud.shape[0],
        num_actions=env.action_space.num_actions,
        hidden_size=64,
        recurrent=False,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    planner = FixedDepthThompsonOracle(
        action_space=env.action_space,
        decision_interval_ticks=env.decision_interval_ticks,
        plan_depth=2,
        num_simulations=2,
        rollout_action_samples=16,
        seed=9,
    )
    replay = DaggerReplayBuffer(capacity=256)

    stats = _collect_dagger_data(
        env=env,
        planner=planner,
        model=model,
        replay=replay,
        rng=rng,
        device=torch.device("cpu"),
        decisions=6,
        beta=1.0,
        quiet_engine=True,
    )
    assert len(replay) > 0
    assert stats["oracle_exec_ratio"] > 0.9

    update_stats = _supervised_update(
        model=model,
        optimizer=optimizer,
        replay=replay,
        rng=rng,
        device=torch.device("cpu"),
        epochs=1,
        batch_size=32,
        steps_per_epoch=1,
    )
    assert update_stats["loss"] >= 0.0
