from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import statistics
import time
from dataclasses import replace
from typing import Any

import numpy as np
import torch

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.imitation import _sequence_batch_inputs, load_corpus
from clasher.rl.model import PolicyInputs
from clasher.rl.train_recurrent import resolve_torch_device


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare dense versus trailing-padding-trimmed policy batches"
    )
    parser.add_argument("--corpus", default="datasets/human_safety_balanced_v1.npz")
    parser.add_argument(
        "--checkpoint",
        default="checkpoints/human_safety_student6m_v1/epoch1.pt",
    )
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--sequence-length", type=int, default=32)
    parser.add_argument("--batch-sequences", type=int, default=8)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def _fixed_sequence_chunks(
    episode_ids: np.ndarray,
    *,
    sequence_length: int,
    count: int,
) -> np.ndarray:
    chunks: list[np.ndarray] = []
    for episode_id in np.unique(episode_ids):
        indices = np.flatnonzero(episode_ids == episode_id)
        for start in range(0, len(indices) - sequence_length + 1, sequence_length):
            chunks.append(indices[start : start + sequence_length])
            if len(chunks) == count:
                return np.stack(chunks)
    raise ValueError(
        f"corpus has fewer than {count} complete {sequence_length}-row chunks"
    )


def _packed_width(mask: torch.Tensor) -> int:
    flat = mask.reshape(-1, mask.shape[-1])
    if bool((flat[:, 1:] & ~flat[:, :-1]).any().item()):
        raise ValueError("entity masks must pack valid rows before padding")
    return max(1, int(flat.sum(dim=-1).max().item()))


def trim_entity_padding(inputs: PolicyInputs) -> PolicyInputs:
    actor_width = _packed_width(inputs.entity_mask)
    updates: dict[str, torch.Tensor] = {
        "entity_ids": inputs.entity_ids[..., :actor_width],
        "entity_features": inputs.entity_features[..., :actor_width, :],
        "entity_mask": inputs.entity_mask[..., :actor_width],
    }
    if inputs.critic_entity_mask is not None:
        assert inputs.critic_entity_ids is not None
        assert inputs.critic_entity_features is not None
        critic_width = _packed_width(inputs.critic_entity_mask)
        updates.update(
            {
                "critic_entity_ids": inputs.critic_entity_ids[..., :critic_width],
                "critic_entity_features": inputs.critic_entity_features[
                    ..., :critic_width, :
                ],
                "critic_entity_mask": inputs.critic_entity_mask[..., :critic_width],
            }
        )
    return replace(inputs, **updates)


def sequence_batch_inputs_trimmed_numpy(
    arrays: dict[str, np.ndarray],
    chunk_indices: np.ndarray,
    device: torch.device,
) -> PolicyInputs:
    """Crop packed entity arrays before copying a sequence batch to the device."""
    selected_mask = arrays["entity_mask"][chunk_indices]
    if np.any(selected_mask[..., 1:] & ~selected_mask[..., :-1]):
        raise ValueError("entity masks must pack valid rows before padding")
    entity_width = max(1, int(np.count_nonzero(selected_mask, axis=-1).max()))

    def tensor(name: str, dtype: torch.dtype) -> torch.Tensor:
        return torch.as_tensor(arrays[name][chunk_indices], dtype=dtype, device=device)

    episode_starts = tensor("episode_starts", torch.bool).clone()
    episode_starts[:, 0] = True
    return PolicyInputs(
        entity_ids=torch.as_tensor(
            arrays["entity_ids"][chunk_indices, :entity_width],
            dtype=torch.long,
            device=device,
        ),
        entity_features=torch.as_tensor(
            arrays["entity_features"][chunk_indices, :entity_width, :],
            dtype=torch.float32,
            device=device,
        ),
        entity_mask=torch.as_tensor(
            selected_mask[..., :entity_width], dtype=torch.bool, device=device
        ),
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        action_mask=tensor("action_masks", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=tensor("previous_rewards", torch.float32),
        episode_starts=episode_starts,
    )


def _synchronize(device: torch.device) -> None:
    if device.type == "mps":
        torch.mps.synchronize()
    elif device.type == "cuda":
        torch.cuda.synchronize(device)


def main() -> None:
    args = parse_args()
    if min(args.sequence_length, args.batch_sequences, args.repetitions) <= 0:
        raise ValueError("sequence length, batch sequences, and repetitions must be positive")
    if args.warmups < 0:
        raise ValueError("warmups must be non-negative")
    device = resolve_torch_device(args.device)
    corpus_path = resolve_path(args.corpus, must_exist=True)
    _, arrays = load_corpus(corpus_path)
    chunks = _fixed_sequence_chunks(
        arrays["episode_ids"],
        sequence_length=args.sequence_length,
        count=args.batch_sequences,
    )
    full_inputs = _sequence_batch_inputs(arrays, chunks, device)
    trim_started = time.perf_counter()
    trimmed_inputs = trim_entity_padding(full_inputs)
    _synchronize(device)
    trim_seconds = time.perf_counter() - trim_started
    targets = torch.as_tensor(
        arrays["expert_actions"][chunks], dtype=torch.long, device=device
    )
    loaded = load_policy_checkpoint(
        resolve_path(args.checkpoint, must_exist=True),
        device=device,
        decks_path=resolve_decks_path(args.decks_path, must_exist=True),
    )
    model = loaded.model.train()

    with torch.no_grad():
        full_output = model(full_inputs).joint_logits
        trimmed_output = model(trimmed_inputs).joint_logits
        legal = full_inputs.action_mask
        legal_difference = (full_output[legal] - trimmed_output[legal]).abs()
        full_actions = full_output.masked_fill(~legal, -torch.inf).argmax(dim=-1)
        trimmed_actions = trimmed_output.masked_fill(~legal, -torch.inf).argmax(dim=-1)
        max_legal_logit_difference = float(legal_difference.max().item())
        action_mismatches = int((full_actions != trimmed_actions).sum().item())

    def training_step(inputs: PolicyInputs) -> float:
        started = time.perf_counter()
        model.zero_grad(set_to_none=True)
        logits = model(inputs).joint_logits
        loss = torch.nn.functional.cross_entropy(
            logits.reshape(-1, logits.shape[-1]), targets.reshape(-1)
        )
        loss.backward()
        _synchronize(device)
        return time.perf_counter() - started

    full_times: list[float] = []
    trimmed_times: list[float] = []
    total_pairs = args.warmups + args.repetitions
    for pair in range(total_pairs):
        ordered = (
            (("full", full_inputs), ("trimmed", trimmed_inputs))
            if pair % 2 == 0
            else (("trimmed", trimmed_inputs), ("full", full_inputs))
        )
        pair_times: dict[str, float] = {}
        for name, inputs in ordered:
            pair_times[name] = training_step(inputs)
        if pair >= args.warmups:
            full_times.append(pair_times["full"])
            trimmed_times.append(pair_times["trimmed"])

    def end_to_end_step(trimmed: bool) -> float:
        started = time.perf_counter()
        inputs = (
            sequence_batch_inputs_trimmed_numpy(arrays, chunks, device)
            if trimmed
            else _sequence_batch_inputs(arrays, chunks, device)
        )
        model.zero_grad(set_to_none=True)
        logits = model(inputs).joint_logits
        loss = torch.nn.functional.cross_entropy(
            logits.reshape(-1, logits.shape[-1]), targets.reshape(-1)
        )
        loss.backward()
        _synchronize(device)
        return time.perf_counter() - started

    full_end_to_end_times: list[float] = []
    trimmed_end_to_end_times: list[float] = []
    for pair in range(total_pairs):
        order = (False, True) if pair % 2 == 0 else (True, False)
        end_to_end_pair_times = {
            trimmed: end_to_end_step(trimmed) for trimmed in order
        }
        if pair >= args.warmups:
            full_end_to_end_times.append(end_to_end_pair_times[False])
            trimmed_end_to_end_times.append(end_to_end_pair_times[True])

    full_median = statistics.median(full_times)
    trimmed_median = statistics.median(trimmed_times)
    full_end_to_end_median = statistics.median(full_end_to_end_times)
    trimmed_end_to_end_median = statistics.median(trimmed_end_to_end_times)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "corpus": str(corpus_path),
        "checkpoint": str(resolve_path(args.checkpoint, must_exist=True)),
        "device": str(device),
        "sequence_length": args.sequence_length,
        "batch_sequences": args.batch_sequences,
        "full_entity_slots": int(full_inputs.entity_mask.shape[-1]),
        "trimmed_entity_slots": int(trimmed_inputs.entity_mask.shape[-1]),
        "trim_construction_seconds": trim_seconds,
        "max_legal_logit_difference": max_legal_logit_difference,
        "action_mismatches": action_mismatches,
        "warmups": args.warmups,
        "repetitions": args.repetitions,
        "full_train_step_seconds": full_times,
        "trimmed_train_step_seconds": trimmed_times,
        "full_median_train_step_seconds": full_median,
        "trimmed_median_train_step_seconds": trimmed_median,
        "speedup": full_median / trimmed_median,
        "time_reduction": 1.0 - trimmed_median / full_median,
        "full_end_to_end_seconds": full_end_to_end_times,
        "trimmed_pretransfer_end_to_end_seconds": trimmed_end_to_end_times,
        "full_median_end_to_end_seconds": full_end_to_end_median,
        "trimmed_pretransfer_median_end_to_end_seconds": (
            trimmed_end_to_end_median
        ),
        "pretransfer_end_to_end_speedup": (
            full_end_to_end_median / trimmed_end_to_end_median
        ),
        "pretransfer_end_to_end_time_reduction": (
            1.0 - trimmed_end_to_end_median / full_end_to_end_median
        ),
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        output_path = resolve_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
