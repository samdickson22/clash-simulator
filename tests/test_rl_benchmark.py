from clasher.rl.benchmark import run_async_queue_benchmark, run_env_benchmark


def test_env_benchmark_reports_positive_throughput():
    metrics = run_env_benchmark(
        seed=101,
        decisions=64,
        decks_path="decks.json",
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=True,
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
    )
    assert metrics["transitions"] >= 128.0
    assert metrics["decisions_per_sec"] > 0.0
    assert metrics["queue_lag_mean_s"] >= 0.0
    assert metrics["queue_lag_p95_s"] >= 0.0
