from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import multiprocessing as mp
import queue
import time
from typing import Any, Dict, List

import numpy as np
import torch

from clasher.battle import STANDARD_MATCH_TICKS, BattleState
from clasher.paths import decks_path as resolve_decks_path
from clasher.rl.inference_server import InferenceServer
from clasher.rl.legacy_model import MaskedPolicyValueNet
from clasher.rl.selfplay_env import SelfPlayBattleEnv


class _NullWriter:
    def write(self, _value):
        return 0

    def flush(self):
        return None


_NULL_WRITER = _NullWriter()
_INCREMENTAL_TARGET_CACHE_REFRESH = BattleState._refresh_target_cache


def _configure_target_cache_refresh(mode: str) -> None:
    implementation = (
        BattleState._rebuild_target_cache
        if mode == "rebuild"
        else _INCREMENTAL_TARGET_CACHE_REFRESH
    )
    BattleState._refresh_target_cache = implementation  # type: ignore[method-assign]


@contextmanager
def _maybe_silence_stdio(enabled: bool):
    if not enabled:
        yield
        return
    with redirect_stdout(_NULL_WRITER), redirect_stderr(_NULL_WRITER):
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
    engine_fast_path: str = "off",
    simulation_backend: str = "python",
    simulation_device: str = "cpu",
    target_cache_refresh: str = "reuse",
) -> Dict[str, float | str]:
    _configure_target_cache_refresh(target_cache_refresh)
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        seed=seed,
        mirror_match=mirror_match,
        canonical_perspective=True,
        engine_fast_path=engine_fast_path,
        simulation_backend=simulation_backend,
        simulation_device=simulation_device,
    )
    rng = np.random.default_rng(seed + 77)
    with _maybe_silence_stdio(quiet_engine):
        env.reset()

    episodes = 0
    start = time.perf_counter()
    with _maybe_silence_stdio(quiet_engine):
        for _ in range(decisions):
            action0 = _random_legal_action(env, 0, rng)
            action1 = _random_legal_action(env, 1, rng)
            _, done, _ = env.step({0: action0, 1: action1})
            if done:
                episodes += 1
                env.reset()
    elapsed = max(1e-9, time.perf_counter() - start)

    transitions = decisions * 2
    decisions_per_sec = decisions / elapsed
    transitions_per_sec = transitions / elapsed
    approx_games_per_min = decisions_per_sec / (max_ticks / decision_interval) * 60.0
    return {
        "elapsed_s": elapsed,
        "simulation_backend": simulation_backend,
        "simulation_device": simulation_device,
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
    engine_fast_path: str,
    simulation_backend: str,
    simulation_device: str,
    target_cache_refresh: str,
    actor_rollout_steps: int,
    out_queue: mp.Queue,
    stop_event: mp.Event,
) -> None:
    _configure_target_cache_refresh(target_cache_refresh)
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        seed=seed + actor_id * 17_411,
        mirror_match=mirror_match,
        canonical_perspective=True,
        engine_fast_path=engine_fast_path,
        simulation_backend=simulation_backend,
        simulation_device=simulation_device,
    )
    rng = np.random.default_rng(seed + actor_id * 99_991)
    with _maybe_silence_stdio(quiet_engine):
        env.reset()

    while not stop_event.is_set():
        local_decisions = 0
        local_episodes = 0
        with _maybe_silence_stdio(quiet_engine):
            for _ in range(actor_rollout_steps):
                action0 = _random_legal_action(env, 0, rng)
                action1 = _random_legal_action(env, 1, rng)
                _, done, _ = env.step({0: action0, 1: action1})
                local_decisions += 1
                if done:
                    local_episodes += 1
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


def _actor_rollout_worker_centralized(
    actor_id: int,
    seed: int,
    decks_path: str,
    decision_interval: int,
    max_ticks: int,
    mirror_match: bool,
    quiet_engine: bool,
    engine_fast_path: str,
    simulation_backend: str,
    simulation_device: str,
    target_cache_refresh: str,
    actor_rollout_steps: int,
    out_queue: mp.Queue,
    stop_event: mp.Event,
    request_queue: mp.Queue,
    response_queue: mp.Queue,
) -> None:
    _configure_target_cache_refresh(target_cache_refresh)
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        seed=seed + actor_id * 17_411,
        mirror_match=mirror_match,
        canonical_perspective=True,
        engine_fast_path=engine_fast_path,
        simulation_backend=simulation_backend,
        simulation_device=simulation_device,
    )
    with _maybe_silence_stdio(quiet_engine):
        env.reset()

    next_request_id = 0
    pending: Dict[int, Dict[str, Any]] = {}

    def _request_actions(board_np: np.ndarray, hud_np: np.ndarray, mask_np: np.ndarray) -> np.ndarray:
        nonlocal next_request_id
        req_id = next_request_id
        next_request_id += 1
        request_queue.put(
            {
                "actor_id": actor_id,
                "request_id": req_id,
                "boards": board_np.astype(np.float32, copy=False),
                "huds": hud_np.astype(np.float32, copy=False),
                "masks": mask_np.astype(np.bool_, copy=False),
            }
        )
        while True:
            if req_id in pending:
                msg = pending.pop(req_id)
                return np.asarray(msg["actions"], dtype=np.int64)
            msg = response_queue.get()
            other_id = int(msg["request_id"])
            if other_id == req_id:
                return np.asarray(msg["actions"], dtype=np.int64)
            pending[other_id] = msg

    while not stop_event.is_set():
        local_decisions = 0
        local_episodes = 0
        with _maybe_silence_stdio(quiet_engine):
            for _ in range(actor_rollout_steps):
                obs0 = env.get_observation(0)
                obs1 = env.get_observation(1)
                mask0 = env.get_action_mask(0)
                mask1 = env.get_action_mask(1)
                board_np = np.stack([obs0.board, obs1.board], axis=0)
                hud_np = np.stack([obs0.hud, obs1.hud], axis=0)
                mask_np = np.stack([mask0, mask1], axis=0)
                actions = _request_actions(board_np, hud_np, mask_np)
                action_by_player = {0: int(actions[0]), 1: int(actions[1])}
                _, done, _ = env.step(action_by_player)
                local_decisions += 1
                if done:
                    local_episodes += 1
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
    engine_fast_path: str = "off",
    simulation_backend: str = "python",
    simulation_device: str = "cpu",
    target_cache_refresh: str = "reuse",
    inference_mode: str = "actor_local",
    inference_max_batch: int = 2048,
    inference_max_wait_ms: float = 2.0,
    hidden_size: int = 256,
    inference_device: str = "cpu",
) -> Dict[str, float | str]:
    ctx = mp.get_context("spawn")
    out_queue = ctx.Queue(maxsize=queue_size)
    stop_event = ctx.Event()
    actors: List[mp.Process] = []
    inference_server: InferenceServer | None = None
    request_queue: mp.Queue | None = None
    response_queues: List[mp.Queue] | None = None

    if inference_mode == "centralized":
        if inference_device == "auto":
            if torch.backends.mps.is_available():
                inference_device_obj = torch.device("mps")
            elif torch.cuda.is_available():
                inference_device_obj = torch.device("cuda")
            else:
                inference_device_obj = torch.device("cpu")
        else:
            inference_device_obj = torch.device(inference_device)
        meta_env = SelfPlayBattleEnv(
            decision_interval_ticks=decision_interval,
            max_ticks=max_ticks,
            decks_path=decks_path,
            seed=seed,
            mirror_match=mirror_match,
            canonical_perspective=True,
            engine_fast_path=engine_fast_path,
            simulation_backend=simulation_backend,
            simulation_device=simulation_device,
        )
        with _maybe_silence_stdio(quiet_engine):
            meta_env.reset()
        obs0 = meta_env.get_observation(0)
        num_actions = meta_env.action_space.num_actions
        model = MaskedPolicyValueNet(
            board_channels=obs0.board.shape[0],
            hud_size=obs0.hud.shape[0],
            num_actions=num_actions,
            hidden_size=hidden_size,
            recurrent=False,
        ).to(inference_device_obj)
        model.eval()
        request_queue = ctx.Queue(maxsize=max(queue_size, num_actors * 2))
        response_queues = [ctx.Queue(maxsize=4) for _ in range(num_actors)]
        inference_server = InferenceServer(
            model=model,
            device=inference_device_obj,
            request_queue=request_queue,
            response_queues={idx: q for idx, q in enumerate(response_queues)},
            max_batch=inference_max_batch,
            max_wait_ms=inference_max_wait_ms,
        )
        inference_server.start()

    for actor_id in range(num_actors):
        if inference_mode == "centralized":
            assert request_queue is not None and response_queues is not None
            proc = ctx.Process(
                target=_actor_rollout_worker_centralized,
                args=(
                    actor_id,
                    seed,
                    decks_path,
                    decision_interval,
                    max_ticks,
                    mirror_match,
                    quiet_engine,
                    engine_fast_path,
                    simulation_backend,
                    simulation_device,
                    target_cache_refresh,
                    actor_rollout_steps,
                    out_queue,
                    stop_event,
                    request_queue,
                    response_queues[actor_id],
                ),
                daemon=True,
            )
        else:
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
                    engine_fast_path,
                    simulation_backend,
                    simulation_device,
                    target_cache_refresh,
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
        if inference_server is not None:
            inference_server.stop()
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
        "simulation_backend": simulation_backend,
        "simulation_device": simulation_device,
        "decisions": float(decisions),
        "transitions": float(transitions),
        "episodes_finished": float(episodes),
        "inference_mode": inference_mode,
        "inference_max_batch": float(inference_max_batch),
        "inference_max_wait_ms": float(inference_max_wait_ms),
        "inference_device": inference_device,
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
    env_p.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    env_p.add_argument("--mirror-match", action="store_true")
    env_p.add_argument("--quiet-engine", action="store_true")
    env_p.add_argument("--engine-fast-path", choices=["off", "shadow", "on"], default="off")
    env_p.add_argument(
        "--simulation-backend",
        choices=["python", "pytorch-shadow", "pytorch"],
        default="python",
    )
    env_p.add_argument(
        "--simulation-device", choices=["cpu", "mps", "cuda"], default="cpu"
    )
    env_p.add_argument(
        "--target-cache-refresh", choices=["rebuild", "reuse"], default="reuse"
    )

    async_p = sub.add_parser("async-queue", help="Actor queue throughput/lag benchmark")
    async_p.add_argument("--seed", type=int, default=101)
    async_p.add_argument("--num-actors", type=int, default=6)
    async_p.add_argument("--transitions", type=int, default=8192)
    async_p.add_argument("--actor-rollout-steps", type=int, default=128)
    async_p.add_argument("--queue-size", type=int, default=32)
    async_p.add_argument("--decks-path", type=str, default="decks.json")
    async_p.add_argument("--decision-interval", type=int, default=8)
    async_p.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    async_p.add_argument("--mirror-match", action="store_true")
    async_p.add_argument("--quiet-engine", action="store_true")
    async_p.add_argument("--engine-fast-path", choices=["off", "shadow", "on"], default="off")
    async_p.add_argument(
        "--simulation-backend",
        choices=["python", "pytorch-shadow", "pytorch"],
        default="python",
    )
    async_p.add_argument(
        "--simulation-device", choices=["cpu", "mps", "cuda"], default="cpu"
    )
    async_p.add_argument(
        "--target-cache-refresh", choices=["rebuild", "reuse"], default="reuse"
    )
    async_p.add_argument("--inference-mode", choices=["actor_local", "centralized"], default="actor_local")
    async_p.add_argument("--inference-max-batch", type=int, default=2048)
    async_p.add_argument("--inference-max-wait-ms", type=float, default=2.0)
    async_p.add_argument("--hidden-size", type=int, default=256)
    async_p.add_argument("--inference-device", choices=["auto", "cpu", "mps", "cuda"], default="cpu")

    return parser.parse_args()


def _print_metrics(prefix: str, metrics: Dict[str, float | str]) -> None:
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
            engine_fast_path=args.engine_fast_path,
            simulation_backend=args.simulation_backend,
            simulation_device=args.simulation_device,
            target_cache_refresh=args.target_cache_refresh,
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
            engine_fast_path=args.engine_fast_path,
            simulation_backend=args.simulation_backend,
            simulation_device=args.simulation_device,
            target_cache_refresh=args.target_cache_refresh,
            inference_mode=args.inference_mode,
            inference_max_batch=args.inference_max_batch,
            inference_max_wait_ms=args.inference_max_wait_ms,
            hidden_size=args.hidden_size,
            inference_device=args.inference_device,
        )
        _print_metrics("benchmark=async-queue", metrics)
        return

    raise RuntimeError(f"unknown benchmark cmd: {args.cmd}")


if __name__ == "__main__":
    main()
