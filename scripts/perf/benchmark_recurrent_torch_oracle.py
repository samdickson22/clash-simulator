#!/usr/bin/env python3
"""Paired production-shaped recurrent rollout benchmark under oracle load.

The measured region contains a complete synchronous collection from persistent
CPU actor processes while a separate process performs a fixed amount of oracle
search.  Actor and oracle startup, plus the optional actor warmup, are excluded.
Each Python/PyTorch pair is rebuilt from the same seeds and model parameters so
the resulting ``RolloutBatch`` payloads can be compared byte-for-byte.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, fields
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import random
import re
import statistics
import subprocess
import sys
import time
import traceback
from typing import Any

import numpy as np
import torch

from clasher.battle import BattleState
from clasher.paths import decks_path as resolve_decks_path
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.parallel_rollout import ActorWorkerConfig, ParallelRolloutCollector
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import RolloutBatch


BACKENDS = ("python", "pytorch")
_BOOTSTRAP_SAMPLES = 20_000
_ROLLOUT_TELEMETRY_FIELDS = frozenset(
    {
        "simulator_tensor_ticks",
        "simulator_python_ticks",
        "simulator_shadow_checks",
        "simulator_shadow_mismatches",
        "simulator_unsupported_fallbacks",
    }
)
_SIMULATOR_COUNTERS = (
    "tensor_ticks",
    "python_ticks",
    "shadow_checks",
    "shadow_mismatches",
    "unsupported_fallbacks",
)
_KNOWN_HEAVY_PATTERNS = (
    re.compile(r"clasher\.rl\.train(?:_|\b)"),
    re.compile(r"train_(?:recurrent|selfplay|dagger_oracle)\.py"),
    re.compile(r"scripts/perf/benchmark"),
    re.compile(r"clasher\.rl\.benchmark"),
    re.compile(r"evaluate_recurrent(?:_corpus)?\.py"),
    re.compile(r"pytest[^\n]*(?:clasher|tests/)"),
    re.compile(r"(?:roadforge|/roader/)[^\n]*(?:python|pytest|solver|attempt)"),
)
_MPS_PATTERNS = (
    re.compile(r"--(?:[a-z0-9_-]*-)?device(?:=|\s+)mps\b"),
    re.compile(r"(?:mps|metal)[^\n]*(?:train|benchmark|oracle|extract)"),
    re.compile(r"(?:train|benchmark|oracle|extract)[^\n]*(?:mps|metal)"),
)
_CPU_EXECUTABLES = {
    "cargo",
    "clang",
    "clang++",
    "cc",
    "c++",
    "node",
    "python",
    "python3",
    "pytest",
    "rustc",
}


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    ppid: int
    cpu_percent: float
    command: str


def _parse_process_table(output: str) -> list[ProcessRecord]:
    records: list[ProcessRecord] = []
    for line in output.splitlines():
        parts = line.strip().split(maxsplit=3)
        if len(parts) != 4:
            continue
        try:
            records.append(
                ProcessRecord(
                    pid=int(parts[0]),
                    ppid=int(parts[1]),
                    cpu_percent=float(parts[2]),
                    command=parts[3],
                )
            )
        except ValueError:
            continue
    return records


def _related_pids(records: list[ProcessRecord], own_pid: int) -> set[int]:
    """Return this process, its ancestors, and its already-running descendants."""

    by_pid = {record.pid: record for record in records}
    related = {own_pid}
    cursor = own_pid
    while cursor in by_pid:
        parent = by_pid[cursor].ppid
        if parent <= 0 or parent in related:
            break
        related.add(parent)
        cursor = parent
    descendants = {own_pid}
    changed = True
    while changed:
        changed = False
        for record in records:
            if record.ppid in descendants and record.pid not in descendants:
                descendants.add(record.pid)
                related.add(record.pid)
                changed = True
    return related


def _process_reasons(
    record: ProcessRecord,
    *,
    high_cpu_percent: float,
) -> list[str]:
    command = record.command.lower()
    reasons: list[str] = []
    if any(pattern.search(command) for pattern in _KNOWN_HEAVY_PATTERNS):
        reasons.append("known-training-or-benchmark-workload")
    if any(pattern.search(command) for pattern in _MPS_PATTERNS):
        reasons.append("possible-mps-workload")
    executable = Path(command.split(maxsplit=1)[0]).name
    if (
        executable in _CPU_EXECUTABLES
        and record.cpu_percent >= high_cpu_percent
    ):
        reasons.append("high-cpu-worker")
    return reasons


def _find_competing_processes(
    records: list[ProcessRecord],
    *,
    own_pid: int,
    high_cpu_percent: float,
) -> list[dict[str, Any]]:
    related = _related_pids(records, own_pid)
    competing: list[dict[str, Any]] = []
    for record in records:
        if record.pid in related:
            continue
        reasons = _process_reasons(record, high_cpu_percent=high_cpu_percent)
        if reasons:
            competing.append(
                {
                    "pid": record.pid,
                    "ppid": record.ppid,
                    "cpu_percent": record.cpu_percent,
                    "reasons": reasons,
                    # Avoid emitting arbitrary command lines, which may contain
                    # credentials.  The digest still makes repeated offenders
                    # distinguishable without exposing their arguments.
                    "command_sha256": hashlib.sha256(
                        record.command.encode("utf-8", errors="replace")
                    ).hexdigest(),
                }
            )
    return competing


def _resource_guard(*, high_cpu_percent: float) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,pcpu=,command="],
            check=True,
            capture_output=True,
            text=True,
            timeout=10.0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"resource guard could not inspect processes: {exc}") from exc
    records = _parse_process_table(completed.stdout)
    if not records:
        raise RuntimeError("resource guard received an empty process table")
    competing = _find_competing_processes(
        records,
        own_pid=os.getpid(),
        high_cpu_percent=high_cpu_percent,
    )
    result = {
        "checked_processes": len(records),
        "high_cpu_percent": high_cpu_percent,
        "competing": competing,
    }
    if competing:
        raise RuntimeError(
            "resource guard found competing CPU/MPS work; no benchmark was run: "
            + json.dumps(competing, sort_keys=True)
        )
    return result


def _rollout_digest(rollout: RolloutBatch) -> str:
    hasher = hashlib.sha256()
    for field in fields(RolloutBatch):
        if field.name in _ROLLOUT_TELEMETRY_FIELDS:
            continue
        value = getattr(rollout, field.name)
        hasher.update(field.name.encode("utf-8"))
        if isinstance(value, np.ndarray):
            array = np.ascontiguousarray(value)
            hasher.update(array.dtype.str.encode("ascii"))
            hasher.update(repr(array.shape).encode("ascii"))
            hasher.update(array.tobytes())
        else:
            hasher.update(repr(value).encode("utf-8"))
    return hasher.hexdigest()


def _first_rollout_difference(
    reference: RolloutBatch,
    candidate: RolloutBatch,
) -> dict[str, Any] | None:
    for field in fields(RolloutBatch):
        if field.name in _ROLLOUT_TELEMETRY_FIELDS:
            continue
        expected = getattr(reference, field.name)
        actual = getattr(candidate, field.name)
        if isinstance(expected, np.ndarray) and isinstance(actual, np.ndarray):
            if expected.dtype != actual.dtype or expected.shape != actual.shape:
                return {
                    "field": field.name,
                    "expected_dtype": str(expected.dtype),
                    "actual_dtype": str(actual.dtype),
                    "expected_shape": list(expected.shape),
                    "actual_shape": list(actual.shape),
                }
            if expected.tobytes() != actual.tobytes():
                equal = np.equal(expected, actual)
                if np.issubdtype(expected.dtype, np.inexact):
                    equal = equal | (np.isnan(expected) & np.isnan(actual))
                unequal = np.flatnonzero((~equal).reshape(-1))
                flat_index = int(unequal[0]) if unequal.size else 0
                index = tuple(
                    int(part)
                    for part in np.unravel_index(flat_index, expected.shape)
                )
                return {
                    "field": field.name,
                    "index": list(index),
                    "expected": repr(expected[index].item()),
                    "actual": repr(actual[index].item()),
                }
        elif expected != actual:
            return {
                "field": field.name,
                "expected": repr(expected),
                "actual": repr(actual),
            }
    return None


def _metrics_with_coverage(metrics: dict[str, Any]) -> dict[str, Any]:
    counters = {name: int(metrics.get(name, 0)) for name in _SIMULATOR_COUNTERS}
    total_ticks = counters["tensor_ticks"] + counters["python_ticks"]
    return {
        **counters,
        "total_ticks": total_ticks,
        "tensor_tick_fraction": (
            counters["tensor_ticks"] / total_ticks if total_ticks else 0.0
        ),
    }


def _rollout_simulator_metrics(rollout: RolloutBatch) -> dict[str, Any]:
    return _metrics_with_coverage(
        {
            "tensor_ticks": rollout.simulator_tensor_ticks,
            "python_ticks": rollout.simulator_python_ticks,
            "shadow_checks": rollout.simulator_shadow_checks,
            "shadow_mismatches": rollout.simulator_shadow_mismatches,
            "unsupported_fallbacks": rollout.simulator_unsupported_fallbacks,
        }
    )


def _audit_paired_rows(
    rows: list[dict[str, Any]],
    *,
    expected_repetitions: int | None = None,
) -> dict[str, int]:
    repetitions = sorted({int(row["repetition"]) for row in rows})
    if expected_repetitions is not None:
        expected = list(range(expected_repetitions))
        if repetitions != expected:
            raise ValueError(
                f"repetitions must be exactly {expected}, got {repetitions}"
            )
    if not repetitions:
        raise ValueError("benchmark rows are empty")
    for repetition in repetitions:
        pair = [row for row in rows if int(row["repetition"]) == repetition]
        counts = {
            backend: sum(str(row["backend"]) == backend for row in pair)
            for backend in BACKENDS
        }
        unexpected = sorted(
            {
                str(row["backend"])
                for row in pair
                if str(row["backend"]) not in BACKENDS
            }
        )
        if counts != {backend: 1 for backend in BACKENDS} or unexpected:
            raise ValueError(
                f"repetition {repetition} must contain exactly one row per backend: "
                f"counts={counts}, unexpected={unexpected}"
            )
    expected_rows = len(repetitions) * len(BACKENDS)
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, got {len(rows)}")
    return {
        "expected_rows": expected_rows,
        "actual_rows": len(rows),
        "paired_repetitions": len(repetitions),
    }


def _paired_summary(
    rows: list[dict[str, Any]],
    *,
    expected_repetitions: int | None = None,
) -> dict[str, Any]:
    _audit_paired_rows(rows, expected_repetitions=expected_repetitions)
    gains: list[float] = []
    for repetition in sorted({int(row["repetition"]) for row in rows}):
        pair = {
            str(row["backend"]): float(row["rollout_seconds"])
            for row in rows
            if int(row["repetition"]) == repetition
        }
        if set(pair) != set(BACKENDS):
            raise ValueError(f"repetition {repetition} is missing a backend: {pair}")
        gains.append(100.0 * (pair["python"] / pair["pytorch"] - 1.0))
    samples = np.asarray(gains, dtype=np.float64)
    rng = np.random.default_rng(0)
    means = np.mean(
        rng.choice(
            samples,
            size=(_BOOTSTRAP_SAMPLES, len(samples)),
            replace=True,
        ),
        axis=1,
    )
    return {
        "values": gains,
        "median": statistics.median(gains),
        "mean": statistics.mean(gains),
        "stdev": statistics.stdev(gains) if len(gains) > 1 else 0.0,
        "positive_pairs": sum(gain > 0.0 for gain in gains),
        "pairs": len(gains),
        "mean_95_percentile_bootstrap_ci": [
            float(np.quantile(means, 0.025)),
            float(np.quantile(means, 0.975)),
        ],
    }


def _aggregate_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        name: sum(int(row.get(name, 0)) for row in metrics)
        for name in _SIMULATOR_COUNTERS
    }
    return _metrics_with_coverage(totals)


def _candidate_coverage(
    rows: list[dict[str, Any]],
    *,
    min_tensor_tick_fraction: float = 0.5,
) -> dict[str, Any]:
    if not 0.0 < min_tensor_tick_fraction <= 1.0:
        raise ValueError("min_tensor_tick_fraction must be in (0, 1]")
    candidate = [row for row in rows if row["backend"] == "pytorch"]
    if not candidate:
        raise ValueError("candidate coverage requires at least one pytorch row")
    rollout_metrics = [
        _metrics_with_coverage(row["rollout_simulator_backend_metrics"])
        for row in candidate
    ]
    oracle_metrics = [
        _metrics_with_coverage(row["oracle"]["simulator_backend_metrics"])
        for row in candidate
    ]
    rollout_rows_with_tensor_ticks = sum(
        int(metrics.get("tensor_ticks", 0)) > 0 for metrics in rollout_metrics
    )
    oracle_rows_with_tensor_ticks = sum(
        int(metrics.get("tensor_ticks", 0)) > 0 for metrics in oracle_metrics
    )
    rollout_fractions = [
        float(metrics["tensor_tick_fraction"]) for metrics in rollout_metrics
    ]
    oracle_fractions = [
        float(metrics["tensor_tick_fraction"]) for metrics in oracle_metrics
    ]
    rollout_rows_meeting_min_fraction = sum(
        fraction >= min_tensor_tick_fraction for fraction in rollout_fractions
    )
    oracle_rows_meeting_min_fraction = sum(
        fraction >= min_tensor_tick_fraction for fraction in oracle_fractions
    )
    rollout = _aggregate_metrics(rollout_metrics)
    oracle = _aggregate_metrics(oracle_metrics)
    sufficient = (
        rollout_rows_meeting_min_fraction == len(candidate)
        and oracle_rows_meeting_min_fraction == len(candidate)
    )
    return {
        "candidate_rows": len(candidate),
        "minimum_required_tensor_tick_fraction": min_tensor_tick_fraction,
        "rollout_rows_with_tensor_ticks": rollout_rows_with_tensor_ticks,
        "oracle_rows_with_tensor_ticks": oracle_rows_with_tensor_ticks,
        "rollout_rows_meeting_min_fraction": rollout_rows_meeting_min_fraction,
        "oracle_rows_meeting_min_fraction": oracle_rows_meeting_min_fraction,
        "rollout_min_observed_tensor_tick_fraction": min(rollout_fractions),
        "oracle_min_observed_tensor_tick_fraction": min(oracle_fractions),
        "rollout": rollout,
        "oracle": oracle,
        "sufficient_for_throughput_interpretation": sufficient,
    }


def _exact_differential(
    rows: list[dict[str, Any]],
    rollouts: dict[tuple[int, str], RolloutBatch],
    *,
    expected_repetitions: int,
) -> tuple[list[dict[str, Any]], bool]:
    _audit_paired_rows(rows, expected_repetitions=expected_repetitions)
    differential: list[dict[str, Any]] = []
    exact = True
    for repetition in range(expected_repetitions):
        difference = _first_rollout_difference(
            rollouts[(repetition, "python")],
            rollouts[(repetition, "pytorch")],
        )
        pair_rows = {
            backend: next(
                row
                for row in rows
                if int(row["repetition"]) == repetition
                and str(row["backend"]) == backend
            )
            for backend in BACKENDS
        }
        oracle_hashes = {
            backend: str(pair_rows[backend]["oracle"]["sha256"])
            for backend in BACKENDS
        }
        shadow_mismatches = {
            backend: {
                "rollout": int(
                    pair_rows[backend]["rollout_simulator_backend_metrics"][
                        "shadow_mismatches"
                    ]
                ),
                "oracle": int(
                    pair_rows[backend]["oracle"]["simulator_backend_metrics"][
                        "shadow_mismatches"
                    ]
                ),
            }
            for backend in BACKENDS
        }
        pair_has_shadow_mismatch = any(
            count > 0
            for by_backend in shadow_mismatches.values()
            for count in by_backend.values()
        )
        pair_exact = (
            difference is None
            and len(set(oracle_hashes.values())) == 1
            and not pair_has_shadow_mismatch
        )
        exact &= pair_exact
        differential.append(
            {
                "repetition": repetition,
                "exact": pair_exact,
                "first_rollout_difference": difference,
                "rollout_sha256": {
                    backend: _rollout_digest(rollouts[(repetition, backend)])
                    for backend in BACKENDS
                },
                "oracle_sha256": oracle_hashes,
                "shadow_mismatches": shadow_mismatches,
            }
        )
    return differential, exact


def _validation_exit_code(
    *,
    exact: bool,
    candidate_coverage: dict[str, Any],
) -> int:
    if not exact:
        return 2
    if not candidate_coverage["sufficient_for_throughput_interpretation"]:
        return 3
    return 0


def _oracle_worker(
    *,
    start_event: Any,
    result_queue: Any,
    seed: int,
    planner_seed: int,
    queries: int,
    decision_interval: int,
    plan_depth: int,
    simulations: int,
    action_samples: int,
    simulation_backend: str,
    simulation_device: str,
) -> None:
    try:
        torch.set_num_threads(1)
        battle = BattleState(rng=random.Random(seed), fast_path=True)
        battle.step_logic_ticks(decision_interval)
        planner = FixedDepthThompsonOracle(
            decision_interval_ticks=decision_interval,
            plan_depth=plan_depth,
            num_simulations=simulations,
            rollout_action_samples=action_samples,
            seed=planner_seed,
            simulation_backend=simulation_backend,
            simulation_device=simulation_device,
        )
        result_queue.put(("ready", os.getpid()))
        if not start_event.wait(timeout=120.0):
            raise TimeoutError("oracle start event was not signalled")
        hasher = hashlib.sha256()
        latencies: list[float] = []
        started = time.perf_counter()
        for query in range(queries):
            # The immutable root is cloned by the planner for every simulation;
            # querying the same fixed state keeps paired oracle load exact.
            query_started = time.perf_counter()
            actions = planner.select_actions(battle)
            latencies.append(time.perf_counter() - query_started)
            hasher.update(repr((seed, query, actions)).encode("utf-8"))
        elapsed = time.perf_counter() - started
        hasher.update(repr(planner.rng.bit_generator.state).encode("utf-8"))
        raw_simulator_metrics = planner.simulator_backend_metrics()
        result_queue.put(
            (
                "result",
                {
                    "queries": queries,
                    "seconds": elapsed,
                    "queries_per_second": queries / max(elapsed, 1e-12),
                    "latency_mean_s": statistics.mean(latencies),
                    "latency_p50_s": float(np.percentile(latencies, 50)),
                    "latency_p95_s": float(np.percentile(latencies, 95)),
                    "latency_max_s": max(latencies),
                    "sha256": hasher.hexdigest(),
                    "simulator_backend_metrics": {
                        **raw_simulator_metrics,
                        **_metrics_with_coverage(raw_simulator_metrics),
                    },
                },
            )
        )
    except BaseException:  # noqa: BLE001 - child failures must reach the parent
        result_queue.put(("error", traceback.format_exc()))


def _make_collector(
    args: argparse.Namespace,
    *,
    backend: str,
    builder: StructuredObservationBuilder,
    policy_config: PolicyConfig,
) -> ParallelRolloutCollector:
    return ParallelRolloutCollector(
        num_workers=args.num_workers,
        num_envs=args.num_envs,
        config=ActorWorkerConfig(
            decks_path=str(args.resolved_decks_path),
            token_names=builder.token_names,
            model_config=policy_config.to_dict(),
            decision_interval=args.decision_interval,
            max_ticks=args.max_ticks,
            mirror_match=args.mirror_match,
            opponent_mode="selfplay",
            opponent_pool=(),
            engine_fast_path=args.engine_fast_path,
            quiet_engine=True,
            base_seed=args.seed,
            torch_threads=args.actor_threads,
            simulation_backend=backend,
            simulation_device=args.simulation_device,
        ),
    )


def _run_variant(
    args: argparse.Namespace,
    *,
    repetition: int,
    backend: str,
    builder: StructuredObservationBuilder,
    policy_config: PolicyConfig,
    model: ClasherPolicy,
) -> tuple[dict[str, Any], RolloutBatch]:
    _resource_guard(high_cpu_percent=args.high_cpu_percent)
    collector = _make_collector(
        args,
        backend=backend,
        builder=builder,
        policy_config=policy_config,
    )
    oracle_context = mp.get_context("spawn")
    start_event = oracle_context.Event()
    result_queue = oracle_context.Queue(maxsize=2)
    process: Any = None
    try:
        if args.warmup_steps:
            collector.collect(
                model=model,
                rollout_steps=args.warmup_steps,
                policy_version=-1,
                timeout=args.timeout,
            )
        process = oracle_context.Process(
            target=_oracle_worker,
            kwargs={
                "start_event": start_event,
                "result_queue": result_queue,
                "seed": args.seed,
                "planner_seed": args.oracle_seed,
                "queries": args.oracle_queries,
                "decision_interval": args.decision_interval,
                "plan_depth": args.oracle_depth,
                "simulations": args.oracle_simulations,
                "action_samples": args.oracle_action_samples,
                "simulation_backend": backend,
                "simulation_device": args.simulation_device,
            },
            name="clasher-benchmark-oracle",
            daemon=True,
        )
        process.start()
        ready = result_queue.get(timeout=args.timeout)
        if ready[0] == "error":
            raise RuntimeError(f"oracle failed during startup:\n{ready[1]}")
        if ready[0] != "ready":
            raise RuntimeError(f"unexpected oracle startup message {ready[0]!r}")

        joint_started = time.perf_counter()
        start_event.set()
        rollout_started = time.perf_counter()
        rollout = collector.collect(
            model=model,
            rollout_steps=args.rollout_steps,
            policy_version=repetition,
            timeout=args.timeout,
        )
        rollout_seconds = time.perf_counter() - rollout_started
        oracle_message = result_queue.get(timeout=args.timeout)
        joint_seconds = time.perf_counter() - joint_started
        if oracle_message[0] == "error":
            raise RuntimeError(f"oracle failed during timing:\n{oracle_message[1]}")
        if oracle_message[0] != "result":
            raise RuntimeError(f"unexpected oracle result {oracle_message[0]!r}")
        oracle = oracle_message[1]
        process.join(timeout=10.0)
        if process.is_alive() or process.exitcode != 0:
            raise RuntimeError(
                f"oracle did not exit cleanly: alive={process.is_alive()} "
                f"exitcode={process.exitcode}"
            )
        transitions = rollout.transitions
        environment_decisions = args.num_envs * args.rollout_steps
        row = {
            "repetition": repetition,
            "backend": backend,
            "rollout_seconds": rollout_seconds,
            "joint_seconds": joint_seconds,
            "transitions": transitions,
            "environment_decisions": environment_decisions,
            "transitions_per_second": transitions / rollout_seconds,
            "environment_decisions_per_second": environment_decisions / rollout_seconds,
            "latency_ms_per_transition": 1000.0 * rollout_seconds / transitions,
            "rollout_sha256": _rollout_digest(rollout),
            "rollout_simulator_backend_metrics": _rollout_simulator_metrics(rollout),
            "oracle": oracle,
        }
        return row, rollout
    finally:
        collector.close(force=False)
        if process is not None and process.is_alive():
            process.terminate()
            process.join(timeout=10.0)
        result_queue.close()
        result_queue.join_thread()


def _summary_for_backend(
    rows: list[dict[str, Any]], backend: str
) -> dict[str, Any]:
    selected = [row for row in rows if row["backend"] == backend]
    rollout_seconds = [float(row["rollout_seconds"]) for row in selected]
    rates = [float(row["transitions_per_second"]) for row in selected]
    oracle_rates = [float(row["oracle"]["queries_per_second"]) for row in selected]
    return {
        "rollout_seconds_median": statistics.median(rollout_seconds),
        "rollout_seconds_mean": statistics.mean(rollout_seconds),
        "rollout_seconds_stdev": (
            statistics.stdev(rollout_seconds) if len(rollout_seconds) > 1 else 0.0
        ),
        "transitions_per_second_median": statistics.median(rates),
        "oracle_queries_per_second_median": statistics.median(oracle_rates),
        "rollout_hashes": sorted({str(row["rollout_sha256"]) for row in selected}),
        "oracle_hashes": sorted({str(row["oracle"]["sha256"]) for row in selected}),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Paired 12-worker recurrent rollout benchmark under oracle load"
    )
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--oracle-seed", type=int, default=901)
    parser.add_argument("--num-workers", type=int, default=12)
    parser.add_argument("--num-envs", type=int, default=64)
    parser.add_argument("--rollout-steps", type=int, default=64)
    parser.add_argument("--warmup-steps", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--actor-threads", type=int, default=1)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=2048)
    parser.add_argument("--mirror-match", action="store_true")
    parser.add_argument(
        "--engine-fast-path", choices=("off", "shadow", "on"), default="on"
    )
    parser.add_argument(
        "--simulation-device",
        choices=("cpu", "mps", "cuda"),
        default="cpu",
        help="device used by rollout and oracle PyTorch simulator kernels",
    )
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--max-entities", type=int, default=128)
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--actor-layers", type=int, default=4)
    parser.add_argument("--critic-layers", type=int, default=2)
    parser.add_argument("--memory-size", type=int, default=256)
    parser.add_argument("--oracle-queries", type=int, default=3)
    parser.add_argument("--oracle-depth", type=int, default=6)
    parser.add_argument("--oracle-simulations", type=int, default=32)
    parser.add_argument("--oracle-action-samples", type=int, default=64)
    parser.add_argument(
        "--min-tensor-tick-fraction",
        type=float,
        default=0.5,
        help=(
            "minimum tensor-tick fraction required in every candidate rollout "
            "and oracle row before throughput is interpreted"
        ),
    )
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument(
        "--high-cpu-percent",
        type=float,
        default=50.0,
        help="fail closed when an unrelated worker executable exceeds this CPU use",
    )
    parser.add_argument(
        "--resource-guard-only",
        action="store_true",
        help="inspect competing CPU/MPS work and exit without starting workers",
    )
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> None:
    positive = {
        "num_workers": args.num_workers,
        "num_envs": args.num_envs,
        "rollout_steps": args.rollout_steps,
        "repetitions": args.repetitions,
        "actor_threads": args.actor_threads,
        "decision_interval": args.decision_interval,
        "max_ticks": args.max_ticks,
        "max_entities": args.max_entities,
        "d_model": args.d_model,
        "num_heads": args.num_heads,
        "actor_layers": args.actor_layers,
        "critic_layers": args.critic_layers,
        "memory_size": args.memory_size,
        "oracle_queries": args.oracle_queries,
        "oracle_depth": args.oracle_depth,
        "oracle_simulations": args.oracle_simulations,
        "oracle_action_samples": args.oracle_action_samples,
    }
    invalid = [name for name, value in positive.items() if value <= 0]
    if invalid:
        raise ValueError(f"arguments must be positive: {', '.join(invalid)}")
    if args.warmup_steps < 0:
        raise ValueError("warmup_steps must be non-negative")
    if args.num_workers < 2 or args.num_workers > args.num_envs:
        raise ValueError("num_workers must be between 2 and num_envs")
    if args.d_model % args.num_heads:
        raise ValueError("d_model must be divisible by num_heads")
    if args.timeout <= 0 or args.high_cpu_percent <= 0:
        raise ValueError("timeout and high_cpu_percent must be positive")
    if not 0.0 < args.min_tensor_tick_fraction <= 1.0:
        raise ValueError("min_tensor_tick_fraction must be in (0, 1]")


def main() -> int:
    args = _parse_args()
    _validate_args(args)
    initial_guard = _resource_guard(high_cpu_percent=args.high_cpu_percent)
    if args.resource_guard_only:
        print(json.dumps({"resource_guard": initial_guard}, indent=2, sort_keys=True))
        return 0

    args.resolved_decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    builder = StructuredObservationBuilder(
        decks_path=args.resolved_decks_path,
        max_entities=args.max_entities,
    )
    policy_config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
        d_model=args.d_model,
        num_heads=args.num_heads,
        actor_layers=args.actor_layers,
        critic_layers=args.critic_layers,
        memory_size=args.memory_size,
    )
    torch.manual_seed(args.seed + 17)
    model = ClasherPolicy(policy_config, builder.card_stat_features).eval()

    rows: list[dict[str, Any]] = []
    rollouts: dict[tuple[int, str], RolloutBatch] = {}
    for repetition in range(args.repetitions):
        order = BACKENDS if repetition % 2 == 0 else tuple(reversed(BACKENDS))
        for backend in order:
            row, rollout = _run_variant(
                args,
                repetition=repetition,
                backend=backend,
                builder=builder,
                policy_config=policy_config,
                model=model,
            )
            rows.append(row)
            rollouts[(repetition, backend)] = rollout

    final_guard = _resource_guard(high_cpu_percent=args.high_cpu_percent)
    row_audit = _audit_paired_rows(
        rows,
        expected_repetitions=args.repetitions,
    )
    differential, exact = _exact_differential(
        rows,
        rollouts,
        expected_repetitions=args.repetitions,
    )

    candidate_coverage = _candidate_coverage(
        rows,
        min_tensor_tick_fraction=args.min_tensor_tick_fraction,
    )
    throughput_interpretable = bool(
        exact
        and candidate_coverage["sufficient_for_throughput_interpretation"]
    )
    backend_summary = (
        {backend: _summary_for_backend(rows, backend) for backend in BACKENDS}
        if throughput_interpretable
        else None
    )
    paired_summary = (
        _paired_summary(rows, expected_repetitions=args.repetitions)
        if throughput_interpretable
        else None
    )

    config = vars(args).copy()
    config["resolved_decks_path"] = str(config["resolved_decks_path"])
    report = {
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.processor(),
            "torch": torch.__version__,
        },
        "config": config,
        "resource_guard": {"initial": initial_guard, "final": final_guard},
        "row_audit": row_audit,
        "rows": rows,
        "candidate_tensor_coverage": candidate_coverage,
        "throughput_interpretable": throughput_interpretable,
        "summary": backend_summary,
        "paired_pytorch_vs_python_percent": paired_summary,
        "exact_differential": differential,
        "exact": exact,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    exit_code = _validation_exit_code(
        exact=exact,
        candidate_coverage=candidate_coverage,
    )
    if exit_code == 2:
        print("exact differential failed", file=sys.stderr)
    elif exit_code == 3:
        print(
            "insufficient candidate tensor coverage; throughput was not interpreted",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
