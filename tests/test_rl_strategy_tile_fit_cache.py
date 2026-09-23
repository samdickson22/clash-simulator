import copy

import numpy as np
import pytest

from clasher.rl import strategy_bots as strategy_bots_module
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot


@pytest.mark.parametrize("strategy", STRATEGY_NAMES)
@pytest.mark.parametrize("player_id", [0, 1])
def test_cached_strategy_tile_fits_match_uncached_scores(
    strategy: str,
    player_id: int,
) -> None:
    env = SelfPlayBattleEnv(seed=9981, max_ticks=4096, engine_fast_path="on")
    env.reset()
    assert env.battle is not None
    bot = StrategyBot(strategy)
    legal = np.flatnonzero(env.get_action_mask(player_id)).tolist()
    situation = strategy_bots_module._public_situation(env, player_id)
    features = strategy_bots_module._card_features(env, player_id)
    elixir = float(env.battle.players[player_id].elixir)

    uncached = [
        bot._score_action(env, player_id, action, situation, elixir, features)
        for action in legal
    ]
    rng_state = copy.deepcopy(env.np_rng.bit_generator.state)
    cache: list[tuple[float, float] | None] = [None] * 576
    cached = [
        bot._score_action(
            env,
            player_id,
            action,
            situation,
            elixir,
            features,
            cache,
        )
        for action in legal
    ]

    assert cached == uncached
    assert env.np_rng.bit_generator.state == rng_state
    assert sum(value is not None for value in cache) < len(legal)


@pytest.mark.parametrize("strategy", STRATEGY_NAMES)
@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_cached_strategy_tile_fits_preserve_action_trace(
    monkeypatch: pytest.MonkeyPatch,
    strategy: str,
    engine_fast_path: str,
) -> None:
    env = SelfPlayBattleEnv(
        seed=9987,
        max_ticks=4096,
        engine_fast_path=engine_fast_path,
    )
    env.reset()
    bot = StrategyBot(strategy)

    for _ in range(6):
        masks = {player_id: env.get_action_mask(player_id) for player_id in (0, 1)}
        uncached_actions = {}
        cached_actions = {}
        for player_id in (0, 1):
            monkeypatch.setattr(
                strategy_bots_module,
                "_USE_CACHED_STRATEGY_TILE_FITS",
                False,
            )
            uncached_actions[player_id] = bot.select_action(
                env,
                player_id,
                action_mask=masks[player_id],
            )
            monkeypatch.setattr(
                strategy_bots_module,
                "_USE_CACHED_STRATEGY_TILE_FITS",
                True,
            )
            cached_actions[player_id] = bot.select_action(
                env,
                player_id,
                action_mask=masks[player_id],
            )
        assert cached_actions == uncached_actions
        _, done, _ = env.step(uncached_actions, pre_action_masks=masks)
        if done:
            break
    assert env.fast_path_metrics()["mask_shadow_mismatches"] == 0
