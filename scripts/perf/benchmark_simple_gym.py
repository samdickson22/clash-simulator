#!/usr/bin/env python3
"""Absolute-throughput benchmark for the unified practical tensor Gym.

Catalog compilation and runtime construction happen outside the timer.  The
measured window contains only action selection and ``SimpleGymRuntime``'s
native action/combat/outcome/projection tick.  Repetitions rebuild the same
seeded runtime and must produce identical transition digests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch

from clasher.rl.deck_pool import load_deck_pool
from clasher.torch_sim.simple_cuda_graph import SimpleCudaGraphRunner
from clasher.torch_sim.simple_standard import (
    STANDARD_REGULATION_TICK,
    STANDARD_TIEBREAK_TICK,
)

# Support both ``python -m scripts.perf.benchmark_simple_gym`` and executing
# this file directly from the repository checkout.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.validate_simple_full_matches import (
    build_simple_runtime,
    select_actions,
    supported_simple_decks,
    update_step_digest,
)


@dataclass(frozen=True)
class SimpleBenchmarkTrial:
    repetition: int
    elapsed_seconds: float
    batch_size: int
    measured_ticks: int
    row_ticks: int
    committed_rows: int
    native_ticks: int
    terminal_rows: int
    row_ticks_per_second: float
    actor_transitions_per_second: float
    peak_device_memory_bytes: int | None
    digest: str


@dataclass(frozen=True)
class CudaProfileEvidence:
    kernel_launches: int
    explicit_host_synchronizations: int
    launch_gate_lt_1000: bool
    zero_explicit_host_sync: bool


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


def _run_trial(
    args: argparse.Namespace,
    *,
    decks: list[list[str]],
    repetition: int,
) -> tuple[SimpleBenchmarkTrial, str]:
    runtime = build_simple_runtime(
        seed=args.seed,
        decks=decks,
        batch_size=args.batch_size,
        device=args.device,
        max_entities=args.max_entities,
        max_effects=args.max_effects,
        regulation_ticks=STANDARD_REGULATION_TICK,
        tiebreak_ticks=STANDARD_TIEBREAK_TICK,
        supported_only=True,
    )
    observation = runtime.observe()
    for _ in range(args.warmup_ticks):
        actions = select_actions(observation.legal_mask, args.policy)
        observation = runtime.step_tick(actions).observation
    step_tick = runtime.step_tick
    if bool(getattr(args, "cuda_graph", False)):
        example_actions = select_actions(observation.legal_mask, args.policy)
        step_tick = SimpleCudaGraphRunner(runtime, example_actions).step_tick

    _synchronize(runtime.device)
    if runtime.device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(runtime.device)
    committed_snapshots: list[torch.Tensor] = []
    native_snapshots: list[torch.Tensor] = []
    done_snapshots: list[torch.Tensor] = []
    started = time.perf_counter()
    for _ in range(args.measured_ticks):
        actions = select_actions(observation.legal_mask, args.policy)
        step = step_tick(actions)
        if bool(getattr(args, "cuda_graph", False)):
            # Graph outputs reuse fixed addresses. Preserve each tick so the
            # all-native/committed gate covers the complete measured window.
            committed_snapshots.append(step.committed.clone())
            native_snapshots.append(step.native_ticks.clone())
            done_snapshots.append(step.done.clone())
        else:
            # Eager result tensors are newly allocated each tick. Keeping their
            # references adds no device operation to the measured native path.
            committed_snapshots.append(step.committed)
            native_snapshots.append(step.native_ticks)
            done_snapshots.append(step.done)
        observation = step.observation
    _synchronize(runtime.device)
    elapsed = time.perf_counter() - started

    row_ticks = args.batch_size * args.measured_ticks
    committed_rows = int(torch.stack(committed_snapshots).sum().item())
    native_ticks = int(torch.stack(native_snapshots).sum().item())
    terminal_rows = int(torch.stack(done_snapshots).sum().item())
    if elapsed <= 0:
        raise RuntimeError("simple Gym benchmark timer did not advance")
    if committed_rows != row_ticks or native_ticks != row_ticks:
        raise RuntimeError("simple Gym benchmark window was not fully native")
    if terminal_rows:
        raise RuntimeError("simple Gym benchmark window contains terminal rows")
    peak_memory = (
        int(torch.cuda.max_memory_allocated(runtime.device))
        if runtime.device.type == "cuda"
        else None
    )
    return (
        SimpleBenchmarkTrial(
            repetition=repetition,
            elapsed_seconds=elapsed,
            batch_size=args.batch_size,
            measured_ticks=args.measured_ticks,
            row_ticks=row_ticks,
            committed_rows=committed_rows,
            native_ticks=native_ticks,
            terminal_rows=terminal_rows,
            row_ticks_per_second=row_ticks / elapsed,
            actor_transitions_per_second=(row_ticks * 2) / elapsed,
            peak_device_memory_bytes=peak_memory,
            digest=_replay_digest(args, decks),
        ),
        str(runtime.device),
    )


def _replay_digest(args: argparse.Namespace, decks: list[list[str]]) -> str:
    """Hash an identical full transition window outside the timed region."""

    runtime = build_simple_runtime(
        seed=args.seed,
        decks=decks,
        batch_size=args.batch_size,
        device=args.device,
        max_entities=args.max_entities,
        max_effects=args.max_effects,
        regulation_ticks=STANDARD_REGULATION_TICK,
        tiebreak_ticks=STANDARD_TIEBREAK_TICK,
        supported_only=True,
    )
    observation = runtime.observe()
    for _ in range(args.warmup_ticks):
        actions = select_actions(observation.legal_mask, args.policy)
        observation = runtime.step_tick(actions).observation
    step_tick = runtime.step_tick
    if bool(getattr(args, "cuda_graph", False)):
        example_actions = select_actions(observation.legal_mask, args.policy)
        step_tick = SimpleCudaGraphRunner(runtime, example_actions).step_tick
    digest = hashlib.sha256()
    for _ in range(args.measured_ticks):
        actions = select_actions(observation.legal_mask, args.policy)
        step = step_tick(actions)
        update_step_digest(digest, step, actions)
        observation = step.observation
    return digest.hexdigest()


def _has_marker_ancestor(event: Any, marker_name: str) -> bool:
    current = event
    while current is not None:
        if getattr(current, "name", None) == marker_name:
            return True
        current = getattr(current, "cpu_parent", None)
    return False


def _is_cuda_launch_api_event(event: Any) -> bool:
    """Return whether a profiler CPU event submits GPU work.

    Recent Kineto/PyTorch releases do not attach CUDA device events to the
    ``record_function`` CPU ancestry that submitted them.  Counting marked
    ``DeviceType.CUDA`` events therefore reports the annotation kernel itself
    (usually one) instead of the thousands of launches made by an eager tick.
    CUDA runtime launch API events do retain that ancestry and are the correct
    quantity for the host-launch gate.
    """

    name = str(getattr(event, "name", "")).lower()
    return (
        "cudalaunchkernel" in name
        or "cudalaunchcooperativekernel" in name
        or "cudagraphlaunch" in name
    )


def _profile_cuda_tick(args: argparse.Namespace, decks: list[list[str]]) -> CudaProfileEvidence:
    if args.device != "cuda" or not torch.cuda.is_available():
        raise ValueError("CUDA profiling requires --device cuda on a CUDA host")
    runtime = build_simple_runtime(
        seed=args.seed,
        decks=decks,
        batch_size=args.batch_size,
        device=args.device,
        max_entities=args.max_entities,
        max_effects=args.max_effects,
        regulation_ticks=STANDARD_REGULATION_TICK,
        tiebreak_ticks=STANDARD_TIEBREAK_TICK,
        supported_only=True,
    )
    observation = runtime.observe()
    for _ in range(max(1, args.warmup_ticks)):
        actions = select_actions(observation.legal_mask, args.policy)
        observation = runtime.step_tick(actions).observation
    step_tick = runtime.step_tick
    if bool(getattr(args, "cuda_graph", False)):
        example_actions = select_actions(observation.legal_mask, args.policy)
        step_tick = SimpleCudaGraphRunner(runtime, example_actions).step_tick
    _synchronize(runtime.device)

    marker = "simple_gym_measured_tick"
    with torch.profiler.profile(
        activities=(
            torch.profiler.ProfilerActivity.CPU,
            torch.profiler.ProfilerActivity.CUDA,
        ),
        record_shapes=False,
        profile_memory=False,
        with_stack=False,
    ) as profile:
        with torch.profiler.record_function(marker):
            actions = select_actions(observation.legal_mask, args.policy)
            step_tick(actions)

    events = list(profile.events())
    launches = sum(
        1
        for event in events
        if _has_marker_ancestor(event, marker) and _is_cuda_launch_api_event(event)
    )
    synchronization_names = (
        "cudadevicesynchronize",
        "cudastreamsynchronize",
        "cudaeventsynchronize",
        "cudacontextsynchronize",
    )
    synchronizations = sum(
        1
        for event in events
        if _has_marker_ancestor(event, marker)
        and any(name in str(getattr(event, "name", "")).lower() for name in synchronization_names)
    )
    return CudaProfileEvidence(
        kernel_launches=launches,
        explicit_host_synchronizations=synchronizations,
        launch_gate_lt_1000=launches < 1_000,
        zero_explicit_host_sync=synchronizations == 0,
    )


def _resolve_preset(args: argparse.Namespace) -> argparse.Namespace:
    defaults = {
        "smoke": (2, 1, 4, 2),
        "profile": (128, 10, 100, 3),
    }
    batch_size, warmup, measured, repetitions = defaults[args.preset]
    args.batch_size = args.batch_size or batch_size
    if args.warmup_ticks is None:
        args.warmup_ticks = warmup
    args.measured_ticks = args.measured_ticks or measured
    args.repetitions = args.repetitions or repetitions
    return args


def benchmark(args: argparse.Namespace) -> dict[str, object]:
    args = _resolve_preset(args)
    if bool(getattr(args, "cuda_graph", False)) and args.device != "cuda":
        raise ValueError("--cuda-graph requires --device cuda")
    if min(
        args.batch_size,
        args.measured_ticks,
        args.repetitions,
        args.max_entities,
        args.max_effects,
    ) < 1 or args.warmup_ticks < 0:
        raise ValueError("benchmark sizes must be positive and warmup non-negative")
    if args.warmup_ticks + args.measured_ticks >= STANDARD_TIEBREAK_TICK:
        raise ValueError("benchmark window must end before the tiebreak boundary")
    candidate_decks = [list(deck) for deck in load_deck_pool(args.decks_path)]
    decks = supported_simple_decks(candidate_decks, device=args.device)
    trials_and_devices = [
        _run_trial(args, decks=decks, repetition=repetition)
        for repetition in range(args.repetitions)
    ]
    trials = [trial for trial, _device in trials_and_devices]
    device = trials_and_devices[0][1]
    digests = {trial.digest for trial in trials}
    if len(digests) != 1:
        raise RuntimeError("simple Gym benchmark replay is nondeterministic")

    rates = [trial.row_ticks_per_second for trial in trials]
    median_rate = statistics.median(rates)
    minimum_rate = float(getattr(args, "min_row_ticks_per_second", 1.0))
    throughput_gate = median_rate >= minimum_rate
    if not throughput_gate:
        raise RuntimeError(
            f"median throughput {median_rate:.3f} row-ticks/s is below gate "
            f"{minimum_rate:.3f}"
        )
    cuda_profile = (
        _profile_cuda_tick(args, decks)
        if bool(getattr(args, "profile_cuda", False))
        else None
    )
    if cuda_profile is not None and not (
        cuda_profile.launch_gate_lt_1000 and cuda_profile.zero_explicit_host_sync
    ):
        raise RuntimeError(
            "simple Gym CUDA tick exceeded launch/synchronization gates: "
            f"launches={cuda_profile.kernel_launches}, "
            f"host_sync={cuda_profile.explicit_host_synchronizations}"
        )

    return {
        "schema_version": 1,
        "engine": "SimpleGymRuntime",
        "execution_mode": (
            "cuda-graph" if bool(getattr(args, "cuda_graph", False)) else "eager"
        ),
        "preset": args.preset,
        "device": device,
        "policy": args.policy,
        "seed": args.seed,
        "deck_pool": {
            "candidate_decks": len(candidate_decks),
            "supported_decks": len(decks),
            "rejected_decks": len(candidate_decks) - len(decks),
        },
        "acceptance": {
            "deterministic_replay": True,
            "all_rows_committed": True,
            "all_row_ticks_native": True,
            "zero_fallback": True,
            "no_terminal_rows_in_window": True,
            "absolute_throughput_gate": True,
            "cuda_launches_lt_1000": (
                cuda_profile.launch_gate_lt_1000 if cuda_profile is not None else None
            ),
            "cuda_zero_explicit_host_sync": (
                cuda_profile.zero_explicit_host_sync if cuda_profile is not None else None
            ),
            "python_parity_evaluated": False,
            "speedup_evaluated": False,
        },
        "throughput_gate": {"minimum_row_ticks_per_second": minimum_rate},
        "median": {
            "elapsed_seconds": statistics.median(
                trial.elapsed_seconds for trial in trials
            ),
            "row_ticks_per_second": median_rate,
            "actor_transitions_per_second": statistics.median(
                trial.actor_transitions_per_second for trial in trials
            ),
        },
        "cuda_profile": asdict(cuda_profile) if cuda_profile is not None else None,
        "trials": [asdict(trial) for trial in trials],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=("smoke", "profile"), default="smoke")
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--seed", type=int, default=202_608_264)
    parser.add_argument("--policy", choices=("noop", "first-legal"), default="first-legal")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--warmup-ticks", type=int)
    parser.add_argument("--measured-ticks", type=int)
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--max-entities", type=int, default=128)
    parser.add_argument("--max-effects", type=int, default=128)
    parser.add_argument("--min-row-ticks-per-second", type=float, default=1.0)
    parser.add_argument("--profile-cuda", action="store_true")
    parser.add_argument(
        "--cuda-graph",
        action="store_true",
        help="capture the fixed-shape CUDA tick and replay it as one graph launch",
    )
    parser.add_argument("--out", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = benchmark(args)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out is None:
        print(encoded, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
