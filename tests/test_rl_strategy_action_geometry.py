import copy

import numpy as np
import pytest

from clasher.rl import strategy_bots as strategy_bots_module
from clasher.rl.common import NUM_TILES
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
    legal = np.flatnonzero(env.get_action_mask(player_id)).tolist()
    situation = strategy_bots_module._public_situation(env, player_id)
    elixir = float(env.battle.players[player_id].elixir)

    monkeypatch.setattr(
        strategy_bots_module, "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY", False
    )
    reference = [
        bot._score_action(env, player_id, action, situation, elixir)
        for action in legal
    ]
    reference_rng = copy.deepcopy(env.np_rng.bit_generator.state)
    monkeypatch.setattr(
        strategy_bots_module, "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY", True
    )
    direct = [
        bot._score_action(env, player_id, action, situation, elixir)
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
    env = SelfPlayBattleEnv(seed=9967, max_ticks=4096, engine_fast_path=engine_fast_path)
    env.reset()
    bot = StrategyBot(strategy)

    for _ in range(6):
        masks = {player_id: env.get_action_mask(player_id) for player_id in (0, 1)}
        actions = {}
        for direct in (False, True):
            monkeypatch.setattr(
                strategy_bots_module, "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY", direct
            )
            actions[direct] = {
                player_id: bot.select_action(
                    env, player_id, action_mask=masks[player_id]
                )
                for player_id in (0, 1)
            }
        assert actions[True] == actions[False]
        _, done, _ = env.step(actions[False], pre_action_masks=masks)
        if done:
            break
    assert env.fast_path_metrics()["mask_shadow_mismatches"] == 0


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
        strategy_bots_module, "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY", False
    )
    reference = bot.select_action(env, 1, action_mask=mask)
    monkeypatch.setattr(
        strategy_bots_module, "_USE_DIRECT_CANONICAL_ACTION_GEOMETRY", True
    )
    assert bot.select_action(env, 1, action_mask=mask) == reference


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
    elixir = float(env.battle.players[player_id].elixir)
    uncached = [
        bot._score_action(env, player_id, action, situation, elixir)
        for action in legal
    ]
    rng_state = copy.deepcopy(env.np_rng.bit_generator.state)
    cache: list[tuple[float, float] | None] = [None] * NUM_TILES
    cached = [
        bot._score_action(env, player_id, action, situation, elixir, cache)
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
    env = SelfPlayBattleEnv(seed=9987, max_ticks=4096, engine_fast_path=engine_fast_path)
    env.reset()
    bot = StrategyBot(strategy)
    for _ in range(6):
        masks = {player_id: env.get_action_mask(player_id) for player_id in (0, 1)}
        actions = {}
        for cached in (False, True):
            monkeypatch.setattr(
                strategy_bots_module, "_USE_CACHED_STRATEGY_TILE_FITS", cached
            )
            actions[cached] = {
                player_id: bot.select_action(
                    env, player_id, action_mask=masks[player_id]
                )
                for player_id in (0, 1)
            }
        assert actions[True] == actions[False]
        _, done, _ = env.step(actions[False], pre_action_masks=masks)
        if done:
            break
    assert env.fast_path_metrics()["mask_shadow_mismatches"] == 0
