from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import io
import multiprocessing as mp
import queue
import time
from typing import Any, Dict, List

import numpy as np

from clasher.paths import decks_path as resolve_decks_path
from clasher.rl.selfplay_env import SelfPlayBattleEnv


@contextmanager
def _maybe_silence_stdio(enabled: bool):
    if not enabled:
        yield
        return
    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        yield


def _random_legal_action(env: SelfPlayBattleEnv, player_id: int, rng: np.random.Generator) -> int:
    assert env.battle is not None
    return env.action_space.random_legal_action(env.battle, player_id=player_id, rng=rng)


def run_env_benchmark(
    *,
    seed: int,
    decisions: int,
    decks_path: str,
    decision_interval: int,
    max_ticks: int,
    mirror_match: bool,
    quiet_engine: bool,
) -> Dict[str, float]:
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        seed=seed,
        mirror_match=mirror_match,
        canonical_perspective=True,
    )
    rng = np.random.default_rng(seed + 77)
    with _maybe_silence_stdio(quiet_engine):
        env.reset()

    episodes = 0
    start = time.perf_counter()
    for _ in range(decisions):
        action0 = _random_legal_action(env, 0, rng)
        action1 = _random_legal_action(env, 1, rng)
        with _maybe_silence_stdio(quiet_engine):
            _, done, _ = env.step({0: action0, 1: action1})
        if done:
            episodes += 1
            with _maybe_silence_stdio(quiet_engine):
                env.reset()
    elapsed = max(1e-9, time.perf_counter() - start)

    transitions = decisions * 2
    decisions_per_sec = decisions / elapsed
    transitions_per_sec = transitions / elapsed
    approx_games_per_min = decisions_per_sec / (max_ticks / decision_interval) * 60.0
    return {
        "elapsed_s": elapsed,
        "decisions": float(decisions),
        "transitions": float(transitions),
        "episodes_finished": float(episodes),
        "decisions_per_sec": decisions_per_sec,
        "transitions_per_sec": transitions_per_sec,
        "approx_games_per_min": approx_games_per_min,
    }


def _actor_rollout_worker(
    actor_id: int,
    seed: int,
    decks_path: str,
    decision_interval: int,
    max_ticks: int,
    mirror_match: bool,
    quiet_engine: bool,
    actor_rollout_steps: int,
    out_queue: mp.Queue,
    stop_event: mp.Event,
) -> None:
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        seed=seed + actor_id * 17_411,
        mirror_match=mirror_match,
        canonical_perspective=True,
    )
    rng = np.random.default_rng(seed + actor_id * 99_991)
    with _maybe_silence_stdio(quiet_engine):
        env.reset()

    while not stop_event.is_set():
        local_decisions = 0
        local_episodes = 0
        for _ in range(actor_rollout_steps):
            action0 = _random_legal_action(env, 0, rng)
            action1 = _random_legal_action(env, 1, rng)
            with _maybe_silence_stdio(quiet_engine):
                _, done, _ = env.step({0: action0, 1: action1})
            local_decisions += 1
            if done:
                local_episodes += 1
                with _maybe_silence_stdio(quiet_engine):
                    env.reset()
        out_queue.put(
            {
                "actor_id": actor_id,
                "produced_at": time.perf_counter(),
                "decisions": local_decisions,
                "transitions": local_decisions * 2,
                "episodes_finished": local_episodes,
            }
        )


def run_async_queue_benchmark(
    *,
    seed: int,
    num_actors: int,
    transitions_target: int,
    actor_rollout_steps: int,
    queue_size: int,
    decks_path: str,
    decision_interval: int,
    max_ticks: int,
    mirror_match: bool,
    quiet_engine: bool,
) -> Dict[str, float]:
    ctx = mp.get_context("spawn")
    out_queue = ctx.Queue(maxsize=queue_size)
    stop_event = ctx.Event()
    actors: List[mp.Process] = []
    for actor_id in range(num_actors):
        proc = ctx.Process(
            target=_actor_rollout_worker,
            args=(
                actor_id,
                seed,
                decks_path,
                decision_interval,
                max_ticks,
                mirror_match,
                quiet_engine,
                actor_rollout_steps,
                out_queue,
                stop_event,
            ),
            daemon=True,
        )
        proc.start()
        actors.append(proc)

    lags: List[float] = []
    transitions = 0
    decisions = 0
    episodes = 0
    t0 = time.perf_counter()
    try:
        while transitions < transitions_target:
            try:
                batch = out_queue.get(timeout=10.0)
            except queue.Empty as exc:
                dead = [(idx, p.exitcode) for idx, p in enumerate(actors) if not p.is_alive()]
                raise RuntimeError(f"queue timeout waiting for actor batches dead={dead}") from exc
            now = time.perf_counter()
            lags.append(max(0.0, now - float(batch["produced_at"])))
            transitions += int(batch["transitions"])
            decisions += int(batch["decisions"])
            episodes += int(batch["episodes_finished"])
    finally:
        stop_event.set()
        for proc in actors:
            proc.join(timeout=2)
        for proc in actors:
            if proc.is_alive():
                proc.terminate()
        for proc in actors:
            proc.join(timeout=1)

    elapsed = max(1e-9, time.perf_counter() - t0)
    lag_arr = np.asarray(lags, dtype=np.float64) if lags else np.asarray([0.0], dtype=np.float64)
    return {
        "elapsed_s": elapsed,
        "decisions": float(decisions),
        "transitions": float(transitions),
        "episodes_finished": float(episodes),
        "decisions_per_sec": decisions / elapsed,
        "transitions_per_sec": transitions / elapsed,
        "queue_lag_mean_s": float(lag_arr.mean()),
        "queue_lag_p50_s": float(np.percentile(lag_arr, 50)),
        "queue_lag_p95_s": float(np.percentile(lag_arr, 95)),
        "queue_lag_max_s": float(lag_arr.max()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RL benchmark suite")
    sub = parser.add_subparsers(dest="cmd", required=True)

    env_p = sub.add_parser("env", help="Single-process environment throughput benchmark")
    env_p.add_argument("--seed", type=int, default=101)
    env_p.add_argument("--decisions", type=int, default=4096)
    env_p.add_argument("--decks-path", type=str, default="decks.json")
    env_p.add_argument("--decision-interval", type=int, default=8)
    env_p.add_argument("--max-ticks", type=int, default=9090)
    env_p.add_argument("--mirror-match", action="store_true")
    env_p.add_argument("--quiet-engine", action="store_true")

    async_p = sub.add_parser("async-queue", help="Actor queue throughput/lag benchmark")
    async_p.add_argument("--seed", type=int, default=101)
    async_p.add_argument("--num-actors", type=int, default=6)
    async_p.add_argument("--transitions", type=int, default=8192)
    async_p.add_argument("--actor-rollout-steps", type=int, default=128)
    async_p.add_argument("--queue-size", type=int, default=32)
    async_p.add_argument("--decks-path", type=str, default="decks.json")
    async_p.add_argument("--decision-interval", type=int, default=8)
    async_p.add_argument("--max-ticks", type=int, default=9090)
    async_p.add_argument("--mirror-match", action="store_true")
    async_p.add_argument("--quiet-engine", action="store_true")

    return parser.parse_args()


def _print_metrics(prefix: str, metrics: Dict[str, float]) -> None:
    parts = [f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in metrics.items()]
    print(f"{prefix} " + " ".join(parts))


def main() -> None:
    args = _parse_args()
    resolved_decks = resolve_decks_path(args.decks_path, must_exist=True)

    if args.cmd == "env":
        metrics = run_env_benchmark(
            seed=args.seed,
            decisions=args.decisions,
            decks_path=str(resolved_decks),
            decision_interval=args.decision_interval,
            max_ticks=args.max_ticks,
            mirror_match=args.mirror_match,
            quiet_engine=args.quiet_engine,
        )
        _print_metrics("benchmark=env", metrics)
        return

    if args.cmd == "async-queue":
        metrics = run_async_queue_benchmark(
            seed=args.seed,
            num_actors=args.num_actors,
            transitions_target=args.transitions,
            actor_rollout_steps=args.actor_rollout_steps,
            queue_size=args.queue_size,
            decks_path=str(resolved_decks),
            decision_interval=args.decision_interval,
            max_ticks=args.max_ticks,
            mirror_match=args.mirror_match,
            quiet_engine=args.quiet_engine,
        )
        _print_metrics("benchmark=async-queue", metrics)
        return

    raise RuntimeError(f"unknown benchmark cmd: {args.cmd}")


if __name__ == "__main__":
    main()
