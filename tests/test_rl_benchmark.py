from clasher.battle import BattleState
from clasher.rl.benchmark import (
    _configure_target_cache_refresh,
    run_async_queue_benchmark,
    run_env_benchmark,
)


def test_target_cache_benchmark_mode_can_restore_incremental_refresh():
    incremental = BattleState._refresh_target_cache
    try:
        _configure_target_cache_refresh("rebuild")
        assert BattleState._refresh_target_cache is BattleState._rebuild_target_cache
    finally:
        _configure_target_cache_refresh("reuse")
    assert BattleState._refresh_target_cache is incremental


def test_env_benchmark_reports_positive_throughput():
    metrics = run_env_benchmark(
        seed=101,
        decisions=64,
        decks_path="decks.json",
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=True,
        engine_fast_path="off",
    )
    assert metrics["decisions"] == 64.0
    assert metrics["transitions"] == 128.0
    assert metrics["decisions_per_sec"] > 0.0
    assert metrics["transitions_per_sec"] > 0.0
    assert metrics["approx_games_per_min"] > 0.0


def test_async_queue_benchmark_reports_lag_stats():
    metrics = run_async_queue_benchmark(
        seed=202,
        num_actors=2,
        transitions_target=128,
        actor_rollout_steps=16,
        queue_size=8,
        decks_path="decks.json",
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=True,
        engine_fast_path="off",
        inference_mode="actor_local",
    )
    assert metrics["transitions"] >= 128.0
    assert metrics["decisions_per_sec"] > 0.0
    assert metrics["inference_mode"] == "actor_local"
    assert metrics["queue_lag_mean_s"] >= 0.0
    assert metrics["queue_lag_p95_s"] >= 0.0


def test_async_queue_benchmark_centralized_inference_mode():
    metrics = run_async_queue_benchmark(
        seed=303,
        num_actors=2,
        transitions_target=128,
        actor_rollout_steps=16,
        queue_size=8,
        decks_path="decks.json",
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=True,
        engine_fast_path="off",
        inference_mode="centralized",
        inference_max_batch=64,
        inference_max_wait_ms=1.0,
        hidden_size=64,
        inference_device="cpu",
    )
    assert metrics["transitions"] >= 128.0
    assert metrics["decisions_per_sec"] > 0.0
    assert metrics["inference_mode"] == "centralized"
    assert metrics["inference_device"] == "cpu"
    assert metrics["queue_lag_mean_s"] >= 0.0
