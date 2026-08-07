import pytest

from clasher.rl.parallel_rollout import (
    ActorWorkerConfig,
    OpponentSpec,
    opponent_spec_for_worker,
)


def _config(
    mode: str, pool: tuple[OpponentSpec, ...]
) -> ActorWorkerConfig:
    return ActorWorkerConfig(
        decks_path="decks.json",
        token_names=(),
        model_config={},
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        opponent_mode=mode,
        opponent_pool=pool,
        engine_fast_path="on",
        quiet_engine=True,
        base_seed=23,
        torch_threads=1,
    )


def test_league_opponents_are_distributed_round_robin_across_workers():
    pool = (
        OpponentSpec(kind="random"),
        OpponentSpec(kind="checkpoint", checkpoint="update800.pt"),
        OpponentSpec(kind="checkpoint", checkpoint="update1300.pt"),
    )
    config = _config("league", pool)

    assigned = tuple(opponent_spec_for_worker(config, worker) for worker in range(12))

    assert assigned == pool * 4


def test_selfplay_has_no_stationary_opponent_spec():
    assert opponent_spec_for_worker(_config("selfplay", ()), 0) is None


def test_stationary_mode_requires_an_opponent_pool():
    with pytest.raises(ValueError, match="requires a pool"):
        opponent_spec_for_worker(_config("league", ()), 0)


def test_opponent_spec_rejects_inconsistent_payloads():
    with pytest.raises(ValueError, match="random opponent cannot"):
        OpponentSpec(kind="random", checkpoint="not-used.pt")
    with pytest.raises(ValueError, match="requires a path"):
        OpponentSpec(kind="checkpoint")
