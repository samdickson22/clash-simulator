#!/usr/bin/env python3
"""Guarded paired production rollout-plus-oracle benchmark.

The default shape mirrors the documented 64-environment, 12-worker recurrent
rollout.  The command refuses to time a candidate while competing Clasher,
Rust, or RoadForge compute is present, while oracle backend ingress is absent,
or when exact/zero-fallback evidence cannot be collected.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import os
import platform
import pstats
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from multiprocessing import get_context
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch

from clasher.paths import decks_path as resolve_decks_path
from clasher.rl import train_recurrent as train_recurrent_module
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.production_benchmark import (
    CANDIDATE_BACKEND,
    REFERENCE_BACKEND,
    BenchmarkLease,
    BenchmarkLeaseError,
    aggregate_backend_metrics,
    canonical_digest,
    competing_benchmark_processes,
    oracle_backend_capability,
    paired_bootstrap_summary,
    paired_order,
    sanitized_process_evidence,
    semantic_rollout_digest,
    write_json_report,
)
from clasher.rl.resource_guard import ResourceGuardError, guard_training_resources
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import RolloutBatch
from clasher.torch_sim.diagnostics import battle_snapshot


@dataclass(frozen=True)
class RolloutConfig:
    decks_path: str
    seed: int
    num_envs: int
    num_workers: int
    rollout_steps: int
    decision_interval: int
    max_ticks: int
    actor_threads: int
    engine_fast_path: str


@dataclass(frozen=True)
class OracleConfig:
    decks_path: str
    seed: int
    planner_seed: int
    states: int
    state_stride: int
    decision_interval: int
    max_ticks: int
    plan_depth: int
    simulations: int
    action_samples: int
    engine_fast_path: str


class BenchmarkAdmissionError(RuntimeError):
    def __init__(self, admission: dict[str, Any]) -> None:
        self.admission = admission
        super().__init__(str(admission["reason"]))


_WORKER_MODEL: ClasherPolicy | None = None
_WORKER_BUILDER: StructuredObservationBuilder | None = None
_WORKER_MODEL_KEY: tuple[str, int] | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/pytorch_production_benchmark.json")
    parser.add_argument("--profile-dir")
    parser.add_argument(
        "--lease-path", default="/tmp/clasher-production-benchmark.lock"
    )
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--planner-seed", type=int, default=901)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmup-pairs", type=int, default=1)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--bootstrap-samples", type=int, default=20_000)
    parser.add_argument("--num-envs", type=int, default=64)
    parser.add_argument("--actor-workers", type=int, default=12)
    parser.add_argument("--actor-threads", type=int, default=1)
    parser.add_argument("--rollout-steps", type=int, default=64)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=9090)
    parser.add_argument("--oracle-states", type=int, default=3)
    parser.add_argument("--oracle-state-stride", type=int, default=4)
    parser.add_argument("--planner-depth", type=int, default=10)
    parser.add_argument("--planner-simulations", type=int, default=48)
    parser.add_argument("--planner-action-samples", type=int, default=96)
    parser.add_argument(
        "--engine-fast-path", choices=("off", "shadow", "on"), default="on"
    )
    parser.add_argument(
        "--resource-policy",
        choices=("skip", "fail"),
        default="skip",
        help="write a blocked report or exit nonzero when admission fails",
    )
    parser.add_argument("--resource-reserve-cpus", type=int, default=0)
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> None:
    positive = (
        "repetitions",
        "bootstrap_samples",
        "num_envs",
        "actor_workers",
        "actor_threads",
        "rollout_steps",
        "decision_interval",
        "max_ticks",
        "oracle_states",
        "oracle_state_stride",
        "planner_depth",
        "planner_simulations",
        "planner_action_samples",
    )
    for name in positive:
        if int(getattr(args, name)) <= 0:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    if args.actor_workers > args.num_envs:
        raise ValueError("--actor-workers cannot exceed --num-envs")
    if args.warmup_pairs < 0:
        raise ValueError("--warmup-pairs must be non-negative")
    if args.resource_reserve_cpus < 0:
        raise ValueError("--resource-reserve-cpus must be non-negative")


def _git_metadata() -> dict[str, str]:
    def command(*arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    return {
        "commit": command("rev-parse", "HEAD"),
        "tree": command("rev-parse", "HEAD^{tree}"),
        "status_porcelain_sha256": hashlib.sha256(
            command("status", "--porcelain=v1").encode("utf-8")
        ).hexdigest(),
    }


def _machine_metadata() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "logical_cpus": os.cpu_count(),
        "mps_available": torch.backends.mps.is_available(),
    }


def _admit_resources(args: argparse.Namespace) -> dict[str, Any]:
    blockers = competing_benchmark_processes()
    if blockers:
        return {
            "admitted": False,
            "reason": "competing production compute is active",
            "blockers": sanitized_process_evidence(blockers),
        }
    try:
        allocation = guard_training_resources(
            learner_device="mps",
            actor_device="cpu",
            actor_workers=args.actor_workers,
            actor_threads=args.actor_threads,
            reserve_cpus=args.resource_reserve_cpus,
            auto_uses_mps=torch.backends.mps.is_available(),
        )
    except ResourceGuardError as error:
        return {"admitted": False, "reason": str(error), "blockers": []}
    return {
        "admitted": True,
        "logical_cpus": allocation.logical_cpus,
        "requested_actor_cpu_slots": allocation.requested_actor_cpu_slots,
        "available_actor_cpu_slots": allocation.available_actor_cpu_slots,
        "blockers": [],
    }


def _model_and_builder(
    config: RolloutConfig,
) -> tuple[ClasherPolicy, StructuredObservationBuilder]:
    global _WORKER_BUILDER, _WORKER_MODEL, _WORKER_MODEL_KEY
    key = (config.decks_path, 128)
    if (
        _WORKER_MODEL is not None
        and _WORKER_BUILDER is not None
        and _WORKER_MODEL_KEY == key
    ):
        return _WORKER_MODEL, _WORKER_BUILDER
    builder = StructuredObservationBuilder(
        decks_path=config.decks_path, max_entities=128
    )
    policy_config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
    )
    torch.manual_seed(91)
    model = ClasherPolicy(policy_config, builder.card_stat_features).eval()
    _WORKER_MODEL = model
    _WORKER_BUILDER = builder
    _WORKER_MODEL_KEY = key
    return model, builder


def _rollout_digest(rollout: RolloutBatch, envs: list[SelfPlayBattleEnv]) -> str:
    return semantic_rollout_digest(
        vars(rollout),
        [battle_snapshot(env.battle) for env in envs if env.battle is not None],
    )


def _run_rollout_shard(
    config: RolloutConfig,
    backend: str,
    worker_id: int,
    profile_path: str | None = None,
) -> dict[str, Any]:
    torch.set_num_threads(config.actor_threads)
    model, builder = _model_and_builder(config)
    env_indices = tuple(range(worker_id, config.num_envs, config.num_workers))
    envs = [
        SelfPlayBattleEnv(
            seed=config.seed + env_index * 1009,
            decks_path=config.decks_path,
            decision_interval_ticks=config.decision_interval,
            max_ticks=config.max_ticks,
            engine_fast_path=config.engine_fast_path,
            simulation_backend=backend,
        )
        for env_index in env_indices
    ]
    for env, env_index in zip(envs, env_indices):
        env._structured_obs_builder = builder
        env.reset(seed=config.seed + env_index * 1009)
    agents = len(envs)
    no_op = envs[0].action_space.no_op_action
    zeros = np.zeros((agents,), dtype=np.float32)
    starts = np.ones((agents,), dtype=np.bool_)
    torch.manual_seed(config.seed + 1_000_003 * (worker_id + 1))

    def collect() -> Any:
        return train_recurrent_module.collect_rollout_stationary_opponents(
            envs=envs,
            learner_players=tuple(env_index % 2 for env_index in env_indices),
            builder=builder,
            model=model,
            device=torch.device("cpu"),
            rollout_steps=config.rollout_steps,
            recurrent_state=model.initial_state(agents),
            previous_actions=np.full((agents,), no_op, dtype=np.int64),
            previous_rewards=zeros.copy(),
            episode_starts=starts.copy(),
            opponent_model=None,
            opponent_recurrent_state=None,
            opponent_previous_actions=np.full((agents,), no_op, dtype=np.int64),
            opponent_previous_rewards=zeros.copy(),
            opponent_episode_starts=starts.copy(),
            quiet_engine=True,
        )

    profiler = cProfile.Profile() if profile_path is not None else None
    started = time.perf_counter()
    result = profiler.runcall(collect) if profiler is not None else collect()
    seconds = time.perf_counter() - started
    rollout = result[0]
    simulator_metrics = rollout.simulator_metrics
    if not simulator_metrics:
        raise RuntimeError(
            "production rollout transported no simulator_metrics; "
            "backend coverage is unavailable"
        )
    if profiler is not None:
        assert profile_path is not None
        profiler.dump_stats(profile_path)
    metrics = aggregate_backend_metrics((simulator_metrics,))
    return {
        "worker_id": worker_id,
        "seconds": seconds,
        "sha256": _rollout_digest(rollout, envs),
        "backend_metrics": metrics,
        "simulator_metrics": simulator_metrics,
        "env_indices": env_indices,
    }


def _run_rollout_leg(
    pool: ProcessPoolExecutor,
    config: RolloutConfig,
    backend: str,
    *,
    profile_dir: Path | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    futures = [
        pool.submit(
            _run_rollout_shard,
            config,
            backend,
            worker_id,
            (
                str(profile_dir / f"rollout_{backend}_worker_{worker_id}.prof")
                if profile_dir is not None
                else None
            ),
        )
        for worker_id in range(config.num_workers)
    ]
    shards = sorted(
        (future.result() for future in futures), key=lambda row: row["worker_id"]
    )
    seconds = time.perf_counter() - started
    metrics = aggregate_backend_metrics(row["backend_metrics"] for row in shards)
    return {
        "backend": backend,
        "seconds": seconds,
        "decisions_per_second": config.num_envs * config.rollout_steps / seconds,
        "sha256": canonical_digest(
            (f"worker[{row['worker_id']}]", row["sha256"]) for row in shards
        ),
        "backend_metrics": metrics,
        "shard_seconds": [float(row["seconds"]) for row in shards],
    }


def _oracle_snapshots(config: OracleConfig) -> list[Any]:
    env = SelfPlayBattleEnv(
        seed=config.seed,
        decks_path=config.decks_path,
        decision_interval_ticks=config.decision_interval,
        max_ticks=config.max_ticks,
        engine_fast_path=config.engine_fast_path,
    )
    env.reset(seed=config.seed)
    rng = np.random.default_rng(config.seed + 1_000_003)
    snapshots = []
    decisions = (config.states - 1) * config.state_stride + 1
    for decision in range(decisions):
        assert env.battle is not None
        if decision % config.state_stride == 0:
            snapshots.append(env.battle.clone())
        if len(snapshots) == config.states:
            break
        masks = {player: env.get_action_mask(player) for player in (0, 1)}
        actions = {
            player: int(rng.choice(np.flatnonzero(masks[player]))) for player in (0, 1)
        }
        env.step(actions, pre_action_masks=masks)
    return snapshots


def _run_oracle_leg(
    config: OracleConfig,
    snapshots: list[Any],
    backend: str,
    *,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    # This constructor call is intentionally unreachable on ae5c08e2. The
    # capability preflight refuses measurement until the production planner
    # owns explicit backend routing and reports executor counters.
    planner = FixedDepthThompsonOracle(
        decision_interval_ticks=config.decision_interval,
        plan_depth=config.plan_depth,
        num_simulations=config.simulations,
        rollout_action_samples=config.action_samples,
        seed=config.planner_seed,
        simulation_backend=backend,  # type: ignore[call-arg]
    )
    evidence: list[tuple[str, Any]] = []

    def measure() -> None:
        for index, battle in enumerate(snapshots):
            before = battle_snapshot(battle)
            actions = planner.select_actions(battle)
            after = battle_snapshot(battle)
            evidence.extend(
                (
                    (f"state[{index}].before", before),
                    (f"state[{index}].actions", actions),
                    (f"state[{index}].after", after),
                )
            )

    profiler = cProfile.Profile() if profile_path is not None else None
    started = time.perf_counter()
    if profiler is None:
        measure()
    else:
        profiler.runcall(measure)
        profiler.dump_stats(str(profile_path))
    seconds = time.perf_counter() - started
    evidence.append(("planner_rng", planner.rng.bit_generator.state))
    metrics_method = getattr(planner, "simulator_backend_metrics", None)
    if not callable(metrics_method):
        raise TypeError("oracle planner did not expose simulator_backend_metrics")
    metrics = aggregate_backend_metrics((metrics_method(),))
    return {
        "backend": backend,
        "seconds": seconds,
        "labels_per_second": len(snapshots) / seconds,
        "sha256": canonical_digest(evidence),
        "backend_metrics": metrics,
    }


def _blocked_payload(
    args: argparse.Namespace,
    *,
    reason: str,
    admission: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "blocked",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "admission": admission,
        "git": _git_metadata(),
        "machine": _machine_metadata(),
        "config": vars(args),
        "speed_claim": None,
    }


def _profile_summary(profile_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(profile_dir.glob("*.prof")):
        stats = pstats.Stats(str(path))
        raw_stats = cast(
            dict[Any, tuple[int, int, float, float, Any]],
            vars(stats)["stats"],
        )
        primitive_calls = sum(value[0] for value in raw_stats.values())
        total_calls = sum(value[1] for value in raw_stats.values())
        total_seconds = sum(value[2] for value in raw_stats.values())
        rows.append(
            {
                "path": str(path.resolve()),
                "total_calls": total_calls,
                "primitive_calls": primitive_calls,
                "total_seconds": total_seconds,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return rows


def main() -> int:
    args = _parse_args()
    _validate_args(args)
    output = Path(args.out).expanduser().resolve()
    lease = BenchmarkLease(args.lease_path)
    try:
        lease.acquire()
    except BenchmarkLeaseError as error:
        admission = {
            "admitted": False,
            "reason": str(error),
            "blockers": [],
            "lease_path": str(lease.path),
        }
        payload = _blocked_payload(
            args,
            reason=str(error),
            admission=admission,
        )
        write_json_report(output, payload)
        print(json.dumps(payload, sort_keys=True))
        return 0 if args.resource_policy == "skip" else 3
    try:
        return _run_with_lease(args, output, lease.path)
    except BenchmarkAdmissionError as error:
        admission = {**error.admission, "lease_path": str(lease.path)}
        payload = _blocked_payload(
            args,
            reason=str(error),
            admission=admission,
        )
        write_json_report(output, payload)
        print(json.dumps(payload, sort_keys=True))
        return 0 if args.resource_policy == "skip" else 3
    finally:
        lease.release()


def _run_with_lease(
    args: argparse.Namespace,
    output: Path,
    lease_path: Path,
) -> int:
    admission = {**_admit_resources(args), "lease_path": str(lease_path)}
    if not admission["admitted"]:
        payload = _blocked_payload(
            args,
            reason=str(admission["reason"]),
            admission=admission,
        )
        write_json_report(output, payload)
        print(json.dumps(payload, sort_keys=True))
        return 0 if args.resource_policy == "skip" else 3

    oracle_capability = oracle_backend_capability(FixedDepthThompsonOracle)
    if not oracle_capability.available:
        payload = _blocked_payload(
            args,
            reason=str(oracle_capability.reason),
            admission=admission,
        )
        write_json_report(output, payload)
        print(json.dumps(payload, sort_keys=True))
        return 0 if args.resource_policy == "skip" else 4

    rollout_config = RolloutConfig(
        decks_path=str(resolve_decks_path(args.decks_path, must_exist=True)),
        seed=args.seed,
        num_envs=args.num_envs,
        num_workers=args.actor_workers,
        rollout_steps=args.rollout_steps,
        decision_interval=args.decision_interval,
        max_ticks=args.max_ticks,
        actor_threads=args.actor_threads,
        engine_fast_path=args.engine_fast_path,
    )
    oracle_config = OracleConfig(
        decks_path=rollout_config.decks_path,
        seed=args.seed,
        planner_seed=args.planner_seed,
        states=args.oracle_states,
        state_stride=args.oracle_state_stride,
        decision_interval=args.decision_interval,
        max_ticks=args.max_ticks,
        plan_depth=args.planner_depth,
        simulations=args.planner_simulations,
        action_samples=args.planner_action_samples,
        engine_fast_path=args.engine_fast_path,
    )
    profile_dir = (
        Path(args.profile_dir).expanduser().resolve()
        if args.profile_dir is not None
        else None
    )
    if profile_dir is not None:
        profile_dir.mkdir(parents=True, exist_ok=True)

    rollout_rows: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []
    combined_rows: list[dict[str, Any]] = []
    snapshots = _oracle_snapshots(oracle_config)
    context = get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=args.actor_workers,
        mp_context=context,
    ) as pool:
        for warmup in range(args.warmup_pairs):
            for backend in paired_order(warmup):
                _admit_or_raise(args)
                _run_rollout_leg(pool, rollout_config, backend)
                _admit_or_raise(args)
                _run_oracle_leg(oracle_config, snapshots, backend)
                _admit_or_raise(args)
        for repetition in range(args.repetitions):
            by_backend: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
            for backend in paired_order(repetition):
                _admit_or_raise(args)
                rollout = _run_rollout_leg(pool, rollout_config, backend)
                _admit_or_raise(args)
                oracle = _run_oracle_leg(oracle_config, snapshots, backend)
                _admit_or_raise(args)
                rollout["repetition"] = repetition
                oracle["repetition"] = repetition
                rollout_rows.append(rollout)
                oracle_rows.append(oracle)
                by_backend[backend] = (rollout, oracle)
            for backend in (REFERENCE_BACKEND, CANDIDATE_BACKEND):
                rollout, oracle = by_backend[backend]
                combined_rows.append(
                    {
                        "backend": backend,
                        "repetition": repetition,
                        "seconds": float(rollout["seconds"]) + float(oracle["seconds"]),
                        "sha256": canonical_digest(
                            (
                                ("rollout", rollout["sha256"]),
                                ("oracle", oracle["sha256"]),
                            )
                        ),
                        "backend_metrics": aggregate_backend_metrics(
                            (rollout["backend_metrics"], oracle["backend_metrics"])
                        ),
                    }
                )
        if profile_dir is not None:
            for backend in (REFERENCE_BACKEND, CANDIDATE_BACKEND):
                _admit_or_raise(args)
                _run_rollout_leg(pool, rollout_config, backend, profile_dir=profile_dir)
                _admit_or_raise(args)
                _run_oracle_leg(
                    oracle_config,
                    snapshots,
                    backend,
                    profile_path=profile_dir / f"oracle_{backend}.prof",
                )
                _admit_or_raise(args)

    summaries = {
        "rollout": paired_bootstrap_summary(
            rollout_rows,
            bootstrap_seed=args.bootstrap_seed,
            bootstrap_samples=args.bootstrap_samples,
        ),
        "oracle": paired_bootstrap_summary(
            oracle_rows,
            bootstrap_seed=args.bootstrap_seed,
            bootstrap_samples=args.bootstrap_samples,
        ),
        "combined": paired_bootstrap_summary(
            combined_rows,
            bootstrap_seed=args.bootstrap_seed,
            bootstrap_samples=args.bootstrap_samples,
        ),
    }
    valid = all(summary["valid_for_speed_claim"] for summary in summaries.values())
    meets_2x = valid and summaries["combined"]["meets_2x_with_95_percent_confidence"]
    payload = {
        "status": "complete" if valid else "invalid",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "admission": admission,
        "git": _git_metadata(),
        "machine": _machine_metadata(),
        "config": vars(args),
        "rows": {
            "rollout": rollout_rows,
            "oracle": oracle_rows,
            "combined": combined_rows,
        },
        "summary": summaries,
        "profiles": _profile_summary(profile_dir) if profile_dir is not None else [],
        "speed_claim": "at-least-2x" if meets_2x else None,
    }
    write_json_report(output, payload)
    print(json.dumps(payload, sort_keys=True))
    return 0 if valid else 5


def _admit_or_raise(args: argparse.Namespace) -> None:
    admission = _admit_resources(args)
    if not admission["admitted"]:
        admission["reason"] = (
            f"resource admission changed around timed leg: {admission['reason']}"
        )
        raise BenchmarkAdmissionError(admission)


if __name__ == "__main__":
    raise SystemExit(main())
