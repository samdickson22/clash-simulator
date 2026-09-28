from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
import platform
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyInputs

DEFAULT_ACCEPTED_CHECKPOINT = Path(
    "checkpoints/fresh_structured_causal_v1_seed1062701/"
    "resource_belief_gated_seed1063602/resource_u10_gate0.pt"
)
DEFAULT_REFERENCE_CHECKPOINT = Path("checkpoints/human_safety_student6m_u64_interp050.pt")
DEFAULT_CORPUS = Path(
    "datasets/derived/fresh_compact_cf_seed1062301/pretrain_balanced.npz"
)
HISTORICAL_ACCEPTED_6M_PATH = Path(
    "checkpoints/mechanics_slot_probe/accepted6m_zero_seed1056701/zero_adapter.pt"
)
HISTORICAL_ACCEPTED_6M_SHA256 = (
    "cf783bdef5c3ce0b529606839b3887a3e3457045394642ad72466cc3087cc305"
)

@dataclass(frozen=True)
class EntityBucket:
    name: str
    quantile: float | None
    entity_count: int
    row_index: int


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot compute a percentile of an empty sample")
    return float(np.percentile(np.asarray(values), probability * 100.0))


def parameter_partition(model: ClasherPolicy) -> dict[str, Any]:
    groups = {
        "deployable_actor_recurrent_action": 0,
        "training_only_privileged_critic": 0,
        "training_only_value_head": 0,
        "training_only_auxiliary_heads": 0,
    }
    group_names: dict[str, list[str]] = {key: [] for key in groups}
    for name, parameter in model.named_parameters():
        count = parameter.numel()
        if name.startswith("critic_encoder."):
            group = "training_only_privileged_critic"
        elif name.startswith("value_head."):
            group = "training_only_value_head"
        elif name.startswith(
            (
                "opponent_hand_head.",
                "opponent_elixir_head.",
                "public_belief_hand_head.",
            )
        ):
            group = "training_only_auxiliary_heads"
        else:
            group = "deployable_actor_recurrent_action"
        groups[group] += count
        group_names[group].append(name)
    total = sum(parameter.numel() for parameter in model.parameters())
    if sum(groups.values()) != total:
        raise AssertionError("parameter partition does not cover the model")
    return {
        "total_trainable": total,
        **groups,
        "training_only_total": total
        - groups["deployable_actor_recurrent_action"],
        "parameter_names": group_names,
    }


def select_entity_buckets(entity_mask: np.ndarray) -> list[EntityBucket]:
    if entity_mask.ndim != 2:
        raise ValueError("entity mask must have shape [samples, entities]")
    if np.any(entity_mask[:, 1:] & ~entity_mask[:, :-1]):
        raise ValueError("entity masks must pack valid entities before padding")
    counts = np.count_nonzero(entity_mask, axis=1)
    definitions: tuple[tuple[str, float | None], ...] = (
        ("small_p05", 0.05),
        ("median_p50", 0.50),
        ("p95", 0.95),
        ("crowded_max", None),
    )
    buckets: list[EntityBucket] = []
    for name, quantile in definitions:
        if quantile is None:
            target = int(counts.max())
        else:
            target = int(np.quantile(counts, quantile, method="higher"))
        candidates = np.flatnonzero(counts == target)
        if candidates.size == 0:
            raise AssertionError("selected entity-count quantile is absent")
        buckets.append(
            EntityBucket(
                name=name,
                quantile=quantile,
                entity_count=target,
                row_index=int(candidates[0]),
            )
        )
    return buckets


def _synchronize(device: torch.device) -> None:
    if device.type == "mps":
        torch.mps.synchronize()
    elif device.type == "cuda":
        torch.cuda.synchronize(device)


def _numpy_row(
    arrays: dict[str, np.ndarray], row_index: int, entity_width: int
) -> dict[str, np.ndarray]:
    return {
        "entity_ids": arrays["entity_ids"][row_index, :entity_width].copy(),
        "entity_features": arrays["entity_features"][
            row_index, :entity_width
        ].astype(np.float32, copy=True),
        "entity_mask": arrays["entity_mask"][row_index, :entity_width].copy(),
        "hand_ids": arrays["hand_ids"][row_index].copy(),
        "global_features": arrays["global_features"][row_index].copy(),
        "action_mask": arrays["action_masks"][row_index].copy(),
        "previous_actions": np.asarray(
            arrays["previous_actions"][row_index], dtype=np.int64
        ),
        "previous_rewards": np.asarray(
            arrays["previous_rewards"][row_index], dtype=np.float32
        ),
        "episode_starts": np.asarray(False, dtype=np.bool_),
    }


def materialize_inputs(
    row: dict[str, np.ndarray],
    *,
    device: torch.device,
    confidence_aware: bool,
) -> PolicyInputs:
    def tensor(name: str, dtype: torch.dtype) -> torch.Tensor:
        return torch.as_tensor(row[name], dtype=dtype, device=device).reshape(
            1, 1, *row[name].shape
        )

    inputs = PolicyInputs(
        entity_ids=tensor("entity_ids", torch.long),
        entity_features=tensor("entity_features", torch.float32),
        entity_mask=tensor("entity_mask", torch.bool),
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        action_mask=tensor("action_mask", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=tensor("previous_rewards", torch.float32),
        episode_starts=tensor("episode_starts", torch.bool),
    )
    return inputs.with_exact_actor_confidence() if confidence_aware else inputs


def benchmark_bucket(
    *,
    model: ClasherPolicy,
    row: dict[str, np.ndarray],
    device: torch.device,
    warmups: int,
    repetitions: int,
) -> dict[str, Any]:
    state = model.initial_state(1, device=device)
    inputs = materialize_inputs(
        row,
        device=device,
        confidence_aware=model.config.public_observation_confidence,
    )
    inference_ms: list[float] = []
    serialization_ms: list[float] = []
    end_to_end_ms: list[float] = []
    action_digest = hashlib.sha256()
    with torch.inference_mode():
        for _ in range(warmups):
            action, _, _, _, _ = model.act(
                inputs,
                state,
                deterministic=True,
            )
            _synchronize(device)
            action_digest.update(int(action.item()).to_bytes(8, "little"))

        for _ in range(repetitions):
            serialized_started = time.perf_counter_ns()
            current_inputs = materialize_inputs(
                row,
                device=device,
                confidence_aware=model.config.public_observation_confidence,
            )
            _synchronize(device)
            inference_started = time.perf_counter_ns()
            action, _, _, _, output = model.act(
                current_inputs,
                state,
                deterministic=True,
            )
            _synchronize(device)
            finished = time.perf_counter_ns()
            serialization_ms.append((inference_started - serialized_started) / 1e6)
            inference_ms.append((finished - inference_started) / 1e6)
            end_to_end_ms.append((finished - serialized_started) / 1e6)
            action_digest.update(int(action.item()).to_bytes(8, "little"))
            if not bool(torch.isfinite(output.joint_logits).any()):
                raise RuntimeError("policy emitted no finite action logit")

    def summary(values: list[float]) -> dict[str, float]:
        return {
            "p50_ms": statistics.median(values),
            "p95_ms": percentile(values, 0.95),
            "max_ms": max(values),
            "mean_ms": statistics.fmean(values),
        }

    stability_ratio = percentile(inference_ms, 0.95) / statistics.median(inference_ms)
    return {
        "serialization": summary(serialization_ms),
        "inference": summary(inference_ms),
        "serialization_plus_inference": summary(end_to_end_ms),
        "inference_p95_over_p50": stability_ratio,
        "stable": stability_ratio <= 2.0,
        "action_digest": action_digest.hexdigest(),
        "warmups": warmups,
        "repetitions": repetitions,
    }


def fresh_factorial_budget(
    *,
    current_client_f0_total: int,
    current_client_f0_deployable: int,
    d_model: int,
    memory_size: int,
) -> dict[str, Any]:
    repair_input = d_model + memory_size
    old_final = memory_size * 6 + 6
    gate_three = memory_size * 3 + 3
    positional_four = memory_size * 4 + 4
    special_two = memory_size * 2 + 2
    shared_pointer = repair_input * d_model
    deltas = {
        "F0_control": 0,
        "F1_gate_positional_card": gate_three + positional_four - old_final,
        "F2_control_timing_shared_pointer": special_two
        + shared_pointer
        - old_final,
        "F3_gate_shared_pointer": gate_three + shared_pointer - old_final,
    }
    arms = {
        name: {
            "total_trainable_target": current_client_f0_total + delta,
            "deployable_actor_target": current_client_f0_deployable + delta,
            "delta_vs_f0": delta,
        }
        for name, delta in deltas.items()
    }
    totals = [int(arm["total_trainable_target"]) for arm in arms.values()]
    return {
        "assumptions": {
            "shared_trunk": True,
            "three_way_gate": "Linear(memory_size, 3)",
            "positional_card_head": "Linear(memory_size, 4)",
            "shared_pointer": "Linear(d_model + memory_size, d_model, bias=False)",
            "unchanged_heatmap": True,
        },
        "arms": arms,
        "max_pairwise_spread_fraction_of_f0": (
            max(totals) - min(totals)
        )
        / current_client_f0_total,
        "within_five_percent": (max(totals) - min(totals))
        / current_client_f0_total
        <= 0.05,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit batch-one current-frame Clasher policy budgets"
    )
    parser.add_argument("--accepted-checkpoint", default=str(DEFAULT_ACCEPTED_CHECKPOINT))
    parser.add_argument("--reference-checkpoint", default=str(DEFAULT_REFERENCE_CHECKPOINT))
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--devices", default="cpu,mps")
    parser.add_argument("--warmups", type=int, default=30)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.warmups < 0 or args.repetitions <= 0 or args.torch_threads <= 0:
        raise ValueError("warmups must be nonnegative; repetitions/threads positive")
    torch.set_num_threads(args.torch_threads)
    accepted_path = resolve_path(args.accepted_checkpoint, must_exist=True)
    reference_path = resolve_path(args.reference_checkpoint, must_exist=True)
    corpus_path = resolve_path(args.corpus, must_exist=True)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    with np.load(corpus_path, allow_pickle=False) as archive:
        array_names = (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "hand_ids",
            "global_features",
            "action_masks",
            "previous_actions",
            "previous_rewards",
        )
        arrays = {name: archive[name].copy() for name in array_names}
    buckets = select_entity_buckets(arrays["entity_mask"])
    devices: list[torch.device] = []
    unavailable: list[str] = []
    for name in (part.strip() for part in args.devices.split(",") if part.strip()):
        if (name == "mps" and not torch.backends.mps.is_available()) or (
            name == "cuda" and not torch.cuda.is_available()
        ):
            unavailable.append(name)
        else:
            devices.append(torch.device(name))

    checkpoint_specs = (
        ("accepted_structured", accepted_path),
        ("available_6m_architecture_reference", reference_path),
    )
    checkpoint_audits: dict[str, Any] = {}
    measurements: list[dict[str, Any]] = []
    accepted_model_cpu: ClasherPolicy | None = None
    for label, checkpoint_path in checkpoint_specs:
        loaded_cpu = load_policy_checkpoint(
            checkpoint_path,
            device=torch.device("cpu"),
            decks_path=decks_path,
        )
        if label == "accepted_structured":
            accepted_model_cpu = loaded_cpu.model
        checkpoint_audits[label] = {
            "path": str(checkpoint_path),
            "sha256": file_sha256(checkpoint_path),
            "bytes": checkpoint_path.stat().st_size,
            "model_config": loaded_cpu.model.config.to_dict(),
            "parameters": parameter_partition(loaded_cpu.model),
        }
        del loaded_cpu
        for device in devices:
            loaded = load_policy_checkpoint(
                checkpoint_path,
                device=device,
                decks_path=decks_path,
            )
            for bucket in buckets:
                row = _numpy_row(
                    arrays,
                    bucket.row_index,
                    bucket.entity_count,
                )
                result = benchmark_bucket(
                    model=loaded.model,
                    row=row,
                    device=device,
                    warmups=args.warmups,
                    repetitions=args.repetitions,
                )
                measurements.append(
                    {
                        "checkpoint": label,
                        "device": str(device),
                        "entity_bucket": asdict(bucket),
                        "packed_entity_width": bucket.entity_count,
                        **result,
                    }
                )
            del loaded
            if device.type == "mps":
                torch.mps.empty_cache()
            elif device.type == "cuda":
                torch.cuda.empty_cache()

    assert accepted_model_cpu is not None
    accepted_partition = parameter_partition(accepted_model_cpu)
    # A current-client F0 must use the frozen 494-token typed closure.  Relative
    # to 155 tokens, the actor/critic identity embeddings and auxiliary hand
    # classifier grow linearly; all other shapes remain unchanged.
    vocabulary_delta = 494 - accepted_model_cpu.config.num_tokens
    current_client_actor_delta = vocabulary_delta * accepted_model_cpu.config.d_model
    current_client_critic_delta = vocabulary_delta * accepted_model_cpu.config.d_model
    current_client_aux_delta = vocabulary_delta * (
        accepted_model_cpu.config.memory_size + 1
    )
    current_client_f0_total = int(accepted_partition["total_trainable"]) + (
        current_client_actor_delta
        + current_client_critic_delta
        + current_client_aux_delta
    )
    current_client_f0_deployable = int(
        accepted_partition["deployable_actor_recurrent_action"]
    ) + current_client_actor_delta
    budget = fresh_factorial_budget(
        current_client_f0_total=current_client_f0_total,
        current_client_f0_deployable=current_client_f0_deployable,
        d_model=accepted_model_cpu.config.d_model,
        memory_size=accepted_model_cpu.config.memory_size,
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "torch_threads": args.torch_threads,
            "mps_available": torch.backends.mps.is_available(),
            "cuda_available": torch.cuda.is_available(),
        },
        "corpus": {
            "path": str(corpus_path),
            "sha256": file_sha256(corpus_path),
            "samples": int(arrays["entity_mask"].shape[0]),
            "buckets": [asdict(bucket) for bucket in buckets],
        },
        "historical_accepted_6m": {
            "expected_path": str(HISTORICAL_ACCEPTED_6M_PATH),
            "expected_sha256": HISTORICAL_ACCEPTED_6M_SHA256,
            "present": HISTORICAL_ACCEPTED_6M_PATH.exists(),
            "benchmark_substitute": "available_6m_architecture_reference",
            "substitute_is_not_claimed_weight_equivalent": True,
        },
        "checkpoint_audits": checkpoint_audits,
        "unavailable_devices": unavailable,
        "measurements": measurements,
        "fresh_f0_f3_parameter_budget": {
            "current_client_token_count": 494,
            "current_client_f0_total": current_client_f0_total,
            "current_client_f0_deployable": current_client_f0_deployable,
            **budget,
        },
        "live_400ms_budget": {
            "cadence_ms": 400.0,
            "tensor_serialization_p50_ms_max": 1.0,
            "tensor_serialization_p95_ms_max": 2.5,
            "ordinary_inference_p50_ms_max": 10.0,
            "ordinary_inference_p95_ms_max": 20.0,
            "crowded_inference_p50_ms_max": 15.0,
            "crowded_inference_p95_ms_max": 25.0,
            "ordinary_serialization_plus_inference_p95_ms_max": 25.0,
            "crowded_serialization_plus_inference_p95_ms_max": 30.0,
            "scope": "policy tensor ingress plus deterministic batch-one actor call",
            "excluded": [
                "vision extraction",
                "transport",
                "action dispatch",
                "online search",
            ],
            "h200_latency_inference_from_mps": False,
        },
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        output_path = resolve_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
