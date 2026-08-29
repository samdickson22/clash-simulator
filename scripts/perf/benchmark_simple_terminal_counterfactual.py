#!/usr/bin/env python3
"""Benchmark real recurrent six-way terminal continuations end to end."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.simple_pytorch_backend import (
    SimplePytorchTrainingCollector,
    load_current_client_typed_vocabulary,
)
from clasher.rl.simple_tensor_collector import SimpleTensorMaskRequest
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION


@dataclass(frozen=True)
class CounterfactualTrial:
    repetition: int
    elapsed_seconds: float
    source_rows: int
    candidates_per_source: int
    terminal_candidates: int
    continuation_decisions: int
    native_ticks: int
    terminal_candidates_per_second: float
    continuation_decisions_per_second: float
    native_ticks_per_second: float
    peak_allocated_bytes: int | None
    peak_reserved_bytes: int | None
    digest: str


def _has_marker_ancestor(event: Any, marker_name: str) -> bool:
    current = event
    while current is not None:
        if getattr(current, "name", None) == marker_name:
            return True
        current = getattr(current, "cpu_parent", None)
    return False


def _cuda_profile(
    args: argparse.Namespace,
    collector: SimplePytorchTrainingCollector,
    evaluator: Any,
    candidates: torch.Tensor,
    recurrent: dict[str, torch.Tensor],
    *,
    max_decisions: int,
) -> dict[str, Any]:
    if collector.collector.device.type != "cuda":
        raise ValueError("CUDA profiling requires --device cuda")
    marker = "simple_terminal_counterfactual"
    torch.manual_seed(args.seed + 10_000)
    torch.cuda.manual_seed_all(args.seed + 10_000)
    _synchronize(collector.collector.device)
    with (
        torch.profiler.profile(
            activities=(
                torch.profiler.ProfilerActivity.CPU,
                torch.profiler.ProfilerActivity.CUDA,
            ),
            record_shapes=False,
            profile_memory=True,
            with_stack=False,
        ) as profile,
        torch.profiler.record_function(marker),
    ):
        result = evaluator.evaluate(
            collector.collector.bridge,
            candidates,
            learner_players=torch.zeros(
                args.batch_size,
                dtype=torch.int64,
                device=collector.collector.device,
            ),
            recurrent_inputs=recurrent,
            max_decisions=max_decisions,
        )
    events = list(profile.events())
    marked_cpu = [event for event in events if _has_marker_ancestor(event, marker)]
    names = [str(getattr(event, "name", "")).lower() for event in marked_cpu]
    launches = sum(
        "cudalaunchkernel" in name
        or "cudalaunchcooperativekernel" in name
        or "cudagraphlaunch" in name
        for name in names
    )
    synchronizations = sum(
        "cudastreamsynchronize" in name or "cudadevicesynchronize" in name
        for name in names
    )
    dtoh = sum("dtoh" in str(getattr(event, "name", "")).lower() for event in events)
    cuda_device_events = sum(
        getattr(event, "device_type", None) == torch.autograd.DeviceType.CUDA
        for event in events
    )
    return {
        "host_launch_apis": launches,
        "explicit_synchronizations": synchronizations,
        "device_events": cuda_device_events,
        "dtoh_events": dtoh,
        "digest": _result_digest(result),
    }


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


def _update_digest(digest: Any, value: torch.Tensor) -> None:
    tensor = value.detach().to(device="cpu").contiguous()
    digest.update(str(tuple(tensor.shape)).encode("ascii"))
    digest.update(str(tensor.dtype).encode("ascii"))
    digest.update(tensor.numpy().tobytes())


def _result_digest(result: Any) -> str:
    digest = hashlib.sha256()
    for name in (
        "source_rows",
        "candidate_index",
        "learner_players",
        "first_actions",
        "first_action_success",
        "root_legal_masks",
        "root_public_action_masks",
        "terminal_winner",
        "terminal_value",
        "terminal_crowns",
        "terminal_tower_hp",
        "terminal_tower_damage_received",
        "decision_count",
        "native_ticks",
        "committed",
        "fallback_rows",
        "all_rows_admitted",
    ):
        _update_digest(digest, getattr(result, name))
    for descriptor in fields(result.root_actor):
        _update_digest(digest, getattr(result.root_actor, descriptor.name))
    for name, value in sorted((result.recurrent_inputs or {}).items()):
        digest.update(name.encode("utf-8"))
        _update_digest(digest, value)
    return digest.hexdigest()


def _collector(args: argparse.Namespace) -> SimplePytorchTrainingCollector:
    device = torch.device(args.device)
    torch.manual_seed(args.seed)
    vocabulary = load_current_client_typed_vocabulary(args.typed_vocabulary_path)
    builder = StructuredObservationBuilder(
        decks_path="decks.json",
        token_names=vocabulary.token_names,
        max_entities=args.max_entities,
        canonical_lane_globals=True,
    )
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
        canonical_lane_globals=True,
        d_model=args.d_model,
        num_heads=args.num_heads,
        actor_layers=1,
        critic_layers=1,
        memory_size=args.memory_size,
        dropout=0.0,
    )
    model = ClasherPolicy(config, builder.card_stat_features).to(device)
    model.eval()
    return SimplePytorchTrainingCollector(
        model=model,
        builder=builder,
        batch_size=args.batch_size,
        device=device,
        decision_interval=args.decision_interval,
        gamma=args.gamma,
        supported_decks_path=args.supported_decks_path,
        typed_vocabulary_path=args.typed_vocabulary_path,
        mirror_match=False,
    )


def _candidate_actions(
    collector: SimplePytorchTrainingCollector,
    candidate_count: int,
) -> tuple[torch.Tensor, list[int]]:
    bridge = collector.collector.bridge
    observation = bridge.observe()
    packet = collector.collector.public_mask_provider(
        SimpleTensorMaskRequest(
            observation=observation,
            decision_index=0,
            bootstrap=False,
        )
    )
    candidates = torch.full(
        (bridge.batch_size, candidate_count, 2),
        NO_OP_ACTION,
        dtype=torch.int64,
        device=bridge.device,
    )
    unique_counts: list[int] = []
    action_ids = torch.arange(
        packet.masks.shape[2], dtype=torch.int64, device=bridge.device
    )
    for row in range(bridge.batch_size):
        legal = action_ids[packet.masks[row, 0] & (action_ids != NO_OP_ACTION)][
            : candidate_count - 1
        ]
        candidates[row, 1 : 1 + legal.shape[0], 0] = legal
        unique_counts.append(1 + int(legal.shape[0]))
    return candidates, unique_counts


def _trial(
    args: argparse.Namespace,
    collector: SimplePytorchTrainingCollector,
    evaluator: Any,
    candidates: torch.Tensor,
    recurrent: dict[str, torch.Tensor],
    *,
    repetition: int,
    max_decisions: int,
) -> CounterfactualTrial:
    device = collector.collector.device
    torch.manual_seed(args.seed + 10_000)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(args.seed + 10_000)
        torch.cuda.reset_peak_memory_stats(device)
    _synchronize(device)
    started = time.perf_counter()
    result = evaluator.evaluate(
        collector.collector.bridge,
        candidates,
        learner_players=torch.zeros(args.batch_size, dtype=torch.int64, device=device),
        recurrent_inputs=recurrent,
        max_decisions=max_decisions,
    )
    _synchronize(device)
    elapsed = time.perf_counter() - started
    terminal_candidates = args.batch_size * args.candidate_count
    continuation_decisions = int(result.decision_count.sum().item())
    native_ticks = int(result.native_ticks.sum().item())
    return CounterfactualTrial(
        repetition=repetition,
        elapsed_seconds=elapsed,
        source_rows=args.batch_size,
        candidates_per_source=args.candidate_count,
        terminal_candidates=terminal_candidates,
        continuation_decisions=continuation_decisions,
        native_ticks=native_ticks,
        terminal_candidates_per_second=terminal_candidates / elapsed,
        continuation_decisions_per_second=continuation_decisions / elapsed,
        native_ticks_per_second=native_ticks / elapsed,
        peak_allocated_bytes=(
            int(torch.cuda.max_memory_allocated(device))
            if device.type == "cuda"
            else None
        ),
        peak_reserved_bytes=(
            int(torch.cuda.max_memory_reserved(device))
            if device.type == "cuda"
            else None
        ),
        digest=_result_digest(result),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "cuda", "mps"), default="cpu")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--candidate-count", type=int, default=6)
    parser.add_argument("--root-decisions", type=int, default=16)
    parser.add_argument(
        "--source-tick",
        type=int,
        help="Optional bounded smoke override after root collection",
    )
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--terminal-check-interval", type=int, default=16)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-entities", type=int, default=56)
    parser.add_argument("--d-model", type=int, default=32)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--memory-size", type=int, default=32)
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--seed", type=int, default=1165001)
    parser.add_argument(
        "--supported-decks-path",
        default="training_decks/simple_gym_supported_v1.json",
    )
    parser.add_argument(
        "--typed-vocabulary-path",
        default="reports/current_client_youtube_stable_vocabulary_v1.json",
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--profile-cuda", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1 or args.candidate_count < 2:
        raise ValueError(
            "batch size must be positive and candidates must include alternatives"
        )
    if args.root_decisions < 0 or args.repetitions < 1:
        raise ValueError("root decisions must be non-negative and repetitions positive")

    collector = _collector(args)
    model = collector.policy.model
    initial_hidden, initial_cell = model.initial_state(
        args.batch_size * 2, device=collector.collector.device
    )
    recurrent: dict[str, torch.Tensor] = {
        "hidden": initial_hidden.reshape(args.batch_size, 2, -1),
        "cell": initial_cell.reshape(args.batch_size, 2, -1),
    }
    if args.root_decisions:
        root_batch = collector.collector.collect(
            args.root_decisions,
            recurrent_inputs=recurrent,
        )
        if root_batch.bootstrap.recurrent_inputs is None:
            raise RuntimeError("root collection lost recurrent state")
        recurrent = dict(root_batch.bootstrap.recurrent_inputs)
    if args.source_tick is not None:
        if not 0 <= args.source_tick < 6_000:
            raise ValueError("source tick override must be in [0, 6000)")
        collector.collector.bridge.runtime.state.tick.fill_(args.source_tick)
    source_tick = int(collector.collector.bridge.runtime.state.tick.amin().item())
    remaining_ticks = max(1, 6_000 - source_tick)
    max_decisions = math.ceil(remaining_ticks / args.decision_interval)
    candidates, unique_candidate_counts = _candidate_actions(
        collector, args.candidate_count
    )
    evaluator = collector.create_terminal_counterfactual_evaluator(
        args.candidate_count,
        terminal_check_interval=args.terminal_check_interval,
    )

    trials = [
        _trial(
            args,
            collector,
            evaluator,
            candidates,
            recurrent,
            repetition=repetition,
            max_decisions=max_decisions,
        )
        for repetition in range(args.repetitions)
    ]
    digests = {trial.digest for trial in trials}
    if len(digests) != 1:
        raise RuntimeError("counterfactual repetitions produced different digests")
    rates = [trial.terminal_candidates_per_second for trial in trials]
    metadata = collector.checkpoint_metadata()
    report = {
        "schema_version": 1,
        "scope": "real recurrent public-mask-v2 terminal counterfactuals",
        "device": str(collector.collector.device),
        "execution_mode": metadata["execution_mode"],
        "public_action_mask_contract_version": metadata[
            "public_action_mask_contract_version"
        ],
        "public_action_mask_semantics_id": metadata["public_action_mask_semantics_id"],
        "batch_size": args.batch_size,
        "candidate_count": args.candidate_count,
        "unique_candidate_counts": unique_candidate_counts,
        "root_decisions": args.root_decisions,
        "source_tick": source_tick,
        "max_decisions": max_decisions,
        "terminal_check_interval": args.terminal_check_interval,
        "summary": {
            "minimum_terminal_candidates_per_second": min(rates),
            "median_terminal_candidates_per_second": statistics.median(rates),
            "maximum_terminal_candidates_per_second": max(rates),
            "digest": next(iter(digests)),
        },
        "trials": [asdict(trial) for trial in trials],
    }
    if args.profile_cuda:
        report["cuda_profile"] = _cuda_profile(
            args,
            collector,
            evaluator,
            candidates,
            recurrent,
            max_decisions=max_decisions,
        )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
