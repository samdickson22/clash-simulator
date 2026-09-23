import copy

import numpy as np
import pytest

from clasher.rl import strategy_bots as strategy_bots_module
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot


@pytest.mark.parametrize("strategy", STRATEGY_NAMES)
@pytest.mark.parametrize("player_id", [0, 1])
def test_direct_strategy_action_geometry_matches_decoded_scores(
    monkeypatch: pytest.MonkeyPatch,
    strategy: str,
    player_id: int,
) -> None:
    env = SelfPlayBattleEnv(seed=9961, max_ticks=4096, engine_fast_path="on")
    env.reset()
    assert env.battle is not None
    bot = StrategyBot(strategy)
    mask = env.get_action_mask(player_id)
    legal = np.flatnonzero(mask).tolist()
    situation = strategy_bots_module._public_situation(env, player_id)
    features = strategy_bots_module._card_features(env, player_id)
    elixir = float(env.battle.players[player_id].elixir)

    monkeypatch.setattr(
        strategy_bots_module,
        "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY",
        False,
    )
    reference = [
        bot._score_action(env, player_id, action, situation, elixir, features)
        for action in legal
    ]
    reference_rng = copy.deepcopy(env.np_rng.bit_generator.state)
    monkeypatch.setattr(
        strategy_bots_module,
        "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY",
        True,
    )
    direct = [
        bot._score_action(env, player_id, action, situation, elixir, features)
        for action in legal
    ]

    assert direct == reference
    assert env.np_rng.bit_generator.state == reference_rng


@pytest.mark.parametrize("strategy", STRATEGY_NAMES)
@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_direct_strategy_action_geometry_preserves_fixed_action_trace(
    monkeypatch: pytest.MonkeyPatch,
    strategy: str,
    engine_fast_path: str,
) -> None:
    env = SelfPlayBattleEnv(
        seed=9967,
        max_ticks=4096,
        engine_fast_path=engine_fast_path,
    )
    env.reset()
    bot = StrategyBot(strategy)

    for _ in range(6):
        masks = {player_id: env.get_action_mask(player_id) for player_id in (0, 1)}
        reference_actions = {}
        direct_actions = {}
        for player_id in (0, 1):
            monkeypatch.setattr(
                strategy_bots_module,
                "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY",
                False,
            )
            reference_actions[player_id] = bot.select_action(
                env,
                player_id,
                action_mask=masks[player_id],
            )
            monkeypatch.setattr(
                strategy_bots_module,
                "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY",
                True,
            )
            direct_actions[player_id] = bot.select_action(
                env,
                player_id,
                action_mask=masks[player_id],
            )
        assert direct_actions == reference_actions
        _, done, _ = env.step(reference_actions, pre_action_masks=masks)
        if done:
            break
    metrics = env.fast_path_metrics()
    assert metrics["mask_shadow_mismatches"] == 0


@pytest.mark.parametrize("strategy", STRATEGY_NAMES)
def test_direct_strategy_action_geometry_falls_back_for_world_action_ids(
    monkeypatch: pytest.MonkeyPatch,
    strategy: str,
) -> None:
    env = SelfPlayBattleEnv(
        seed=9973,
        canonical_perspective=False,
        max_ticks=4096,
        engine_fast_path="on",
    )
    env.reset()
    assert env.battle is not None
    env.battle.players[1].elixir = 10.0
    bot = StrategyBot(strategy)
    mask = env.get_action_mask(1)

    monkeypatch.setattr(
        strategy_bots_module,
        "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY",
        False,
    )
    reference = bot.select_action(env, 1, action_mask=mask)
    monkeypatch.setattr(
        strategy_bots_module,
        "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY",
        True,
    )

    assert bot.select_action(env, 1, action_mask=mask) == reference
