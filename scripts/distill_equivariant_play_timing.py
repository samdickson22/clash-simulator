# mypy: disable-error-code="import-untyped"
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from clasher.rl.common import NUM_HAND_SLOTS
from clasher.rl.imitation import (
    _sequence_batch_inputs,
    load_corpus,
    sequence_chunks,
    split_indices,
)
from clasher.rl.model import ClasherPolicy, PolicyInputs
from scripts.distill_equivariant_slot_choice import (
    ALL_HAND_ORDERS,
    _load_policy,
    file_sha256,
    legal_slot_mask,
    permute_current_hand_batch,
    repeat_state_for_permutations,
    time_slice,
)


def top_level_probabilities(
    action_type_logits: torch.Tensor,
    action_mask: torch.Tensor,
    *,
    temperature: float,
) -> torch.Tensor:
    """Return masked play/wait/ability probabilities."""

    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("temperature must be finite and positive")
    legal_slots = legal_slot_mask(action_mask)
    special_legal = action_mask[..., -2:]
    type_legal = torch.cat([legal_slots, special_legal], dim=-1)
    type_probabilities = torch.softmax(
        (action_type_logits / temperature).masked_fill(~type_legal, -1e9),
        dim=-1,
    )
    return torch.cat(
        [
            type_probabilities[..., :NUM_HAND_SLOTS].sum(dim=-1, keepdim=True),
            type_probabilities[..., NUM_HAND_SLOTS:],
        ],
        dim=-1,
    )


def top_level_legal_mask(action_mask: torch.Tensor) -> torch.Tensor:
    return torch.cat(
        [legal_slot_mask(action_mask).any(dim=-1, keepdim=True), action_mask[..., -2:]],
        dim=-1,
    )


@torch.no_grad()
def build_teacher_timing_targets(
    teacher: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    chunks: np.ndarray,
    *,
    device: torch.device,
    sequence_batch_size: int,
    temperature: float,
    trim_entity_padding: bool,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    sample_count = int(arrays["hand_ids"].shape[0])
    targets = np.full((sample_count, 3), np.nan, dtype=np.float32)
    originals = np.full_like(targets, np.nan)
    teacher.eval()
    permutation_count = int(ALL_HAND_ORDERS.shape[0])
    started = time.monotonic()

    for start in range(0, len(chunks), sequence_batch_size):
        batch_chunks = chunks[start : start + sequence_batch_size]
        inputs = _sequence_batch_inputs(
            arrays,
            batch_chunks,
            device,
            trim_entity_padding=trim_entity_padding,
        )
        teacher_state = teacher.initial_state(inputs.batch_size, device=device)
        for step_index in range(inputs.sequence_length):
            step_inputs = time_slice(inputs, step_index)
            pre_state = teacher_state
            original_output = teacher(step_inputs, pre_state)
            teacher_state = tuple(value.detach() for value in original_output.next_state)

            permuted_inputs = permute_current_hand_batch(
                step_inputs,
                ALL_HAND_ORDERS,
            )
            permuted_output = teacher(
                permuted_inputs,
                repeat_state_for_permutations(pre_state, permutation_count),
            )
            permuted_probabilities = top_level_probabilities(
                permuted_output.action_type_logits[:, 0],
                permuted_inputs.action_mask[:, 0],
                temperature=temperature,
            ).reshape(inputs.batch_size, permutation_count, 3)
            target = permuted_probabilities.mean(dim=1)
            original = top_level_probabilities(
                original_output.action_type_logits[:, 0],
                step_inputs.action_mask[:, 0],
                temperature=temperature,
            )
            row_indices = batch_chunks[:, step_index]
            targets[row_indices] = target.cpu().numpy()
            originals[row_indices] = original.cpu().numpy()

        completed = min(start + sequence_batch_size, len(chunks))
        if completed == len(chunks) or completed % max(sequence_batch_size, 64) == 0:
            print(
                json.dumps(
                    {
                        "teacher_timing_chunks": completed,
                        "teacher_timing_total_chunks": len(chunks),
                        "elapsed_seconds": time.monotonic() - started,
                    }
                ),
                flush=True,
            )

    valid = np.isfinite(targets).all(axis=-1)
    epsilon = 1e-12
    target_np = np.clip(targets[valid], epsilon, 1.0)
    original_np = np.clip(originals[valid], epsilon, 1.0)
    metrics = {
        "covered_samples": float(valid.sum()),
        "teacher_original_symmetrized_top1_agreement": float(
            (target_np.argmax(axis=-1) == original_np.argmax(axis=-1)).mean()
        ),
        "teacher_original_to_symmetrized_kl": float(
            np.sum(
                target_np * (np.log(target_np) - np.log(original_np)), axis=-1
            ).mean()
        ),
        "symmetrized_target_entropy": float(
            -np.sum(target_np * np.log(target_np), axis=-1).mean()
        ),
        "target_seconds": float(time.monotonic() - started),
    }
    return targets, originals, metrics


def student_top_level_logits(
    model: ClasherPolicy,
    inputs: PolicyInputs,
) -> torch.Tensor:
    output = model(inputs)
    timing = output.deterministic_timing_logits
    if timing is None or model.equivariant_timing_query is None:
        raise RuntimeError("student has no equivariant timing query")
    return torch.cat([timing[..., :1], timing[..., NUM_HAND_SLOTS:]], dim=-1)


def evaluate_student_timing(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    chunks: np.ndarray,
    targets: np.ndarray,
    *,
    device: torch.device,
    sequence_batch_size: int,
    trim_entity_padding: bool,
) -> dict[str, float]:
    model.eval()
    total_cross_entropy = 0.0
    total_kl = 0.0
    top1 = 0
    count = 0
    with torch.no_grad():
        for start in range(0, len(chunks), sequence_batch_size):
            batch_chunks = chunks[start : start + sequence_batch_size]
            inputs = _sequence_batch_inputs(
                arrays,
                batch_chunks,
                device,
                trim_entity_padding=trim_entity_padding,
            )
            target = torch.as_tensor(
                targets[batch_chunks], dtype=torch.float32, device=device
            )
            legal = top_level_legal_mask(inputs.action_mask)
            valid = torch.isfinite(target).all(dim=-1) & (legal.sum(dim=-1) >= 2)
            if not bool(valid.any()):
                continue
            log_probabilities = torch.log_softmax(
                student_top_level_logits(model, inputs).masked_fill(~legal, -1e9),
                dim=-1,
            )
            selected_target = target[valid]
            selected_log = log_probabilities[valid]
            cross_entropy = -(selected_target * selected_log).sum(dim=-1)
            total_cross_entropy += float(cross_entropy.sum())
            total_kl += float(
                (
                    selected_target
                    * (selected_target.clamp_min(1e-12).log() - selected_log)
                )
                .sum(dim=-1)
                .sum()
            )
            top1 += int(
                (selected_target.argmax(dim=-1) == selected_log.argmax(dim=-1))
                .sum()
                .item()
            )
            count += int(selected_target.shape[0])
    denominator = max(1, count)
    return {
        "samples": float(count),
        "cross_entropy": total_cross_entropy / denominator,
        "kl": total_kl / denominator,
        "top1_agreement": top1 / denominator,
    }


def fit_timing_query(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    training_chunks: np.ndarray,
    validation_chunks: np.ndarray,
    targets: np.ndarray,
    *,
    device: torch.device,
    epochs: int,
    learning_rate: float,
    sequence_batch_size: int,
    trim_entity_padding: bool,
    seed: int,
    selection_metric: str,
) -> tuple[dict[str, torch.Tensor], list[dict[str, Any]]]:
    if selection_metric not in {"kl", "top1"}:
        raise ValueError("selection metric must be 'kl' or 'top1'")
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(name.startswith("equivariant_timing_query."))
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if not trainable:
        raise ValueError("student has no trainable timing query")
    optimizer = torch.optim.AdamW(trainable, lr=learning_rate)
    rng = np.random.default_rng(seed)
    history: list[dict[str, Any]] = []
    best_state = {
        name: value.detach().cpu().clone() for name, value in model.state_dict().items()
    }
    best_score = math.inf if selection_metric == "kl" else -math.inf
    control = evaluate_student_timing(
        model,
        arrays,
        validation_chunks,
        targets,
        device=device,
        sequence_batch_size=sequence_batch_size,
        trim_entity_padding=trim_entity_padding,
    )
    history.append({"epoch": 0, "validation": control})

    for epoch in range(1, epochs + 1):
        model.train()
        shuffled = training_chunks[rng.permutation(len(training_chunks))]
        loss_sum = 0.0
        sample_count = 0
        started = time.monotonic()
        for start in range(0, len(shuffled), sequence_batch_size):
            batch_chunks = shuffled[start : start + sequence_batch_size]
            inputs = _sequence_batch_inputs(
                arrays,
                batch_chunks,
                device,
                trim_entity_padding=trim_entity_padding,
            )
            target = torch.as_tensor(
                targets[batch_chunks], dtype=torch.float32, device=device
            )
            legal = top_level_legal_mask(inputs.action_mask)
            valid = torch.isfinite(target).all(dim=-1) & (legal.sum(dim=-1) >= 2)
            if not bool(valid.any()):
                continue
            log_probabilities = torch.log_softmax(
                student_top_level_logits(model, inputs).masked_fill(~legal, -1e9),
                dim=-1,
            )
            selected_target = target[valid]
            selected_log = log_probabilities[valid]
            loss = -(selected_target * selected_log).sum(dim=-1).mean()
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("non-finite timing-distillation loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            gradient_norm = nn.utils.clip_grad_norm_(trainable, 0.5)
            if not bool(torch.isfinite(gradient_norm)):
                raise FloatingPointError("non-finite timing-distillation gradient")
            optimizer.step()
            batch_count = int(selected_target.shape[0])
            loss_sum += float(loss.detach()) * batch_count
            sample_count += batch_count

        validation = evaluate_student_timing(
            model,
            arrays,
            validation_chunks,
            targets,
            device=device,
            sequence_batch_size=sequence_batch_size,
            trim_entity_padding=trim_entity_padding,
        )
        row = {
            "epoch": epoch,
            "training_cross_entropy": loss_sum / max(1, sample_count),
            "training_samples": sample_count,
            "validation": validation,
            "epoch_seconds": time.monotonic() - started,
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        score = validation["kl"] if selection_metric == "kl" else validation["top1_agreement"]
        improved = score < best_score if selection_metric == "kl" else score > best_score
        if improved:
            best_score = score
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
    return best_state, history


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-checkpoint", required=True, type=Path)
    parser.add_argument("--student-checkpoint", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--target-cache", required=True, type=Path)
    parser.add_argument("--output-checkpoint", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=1056806)
    parser.add_argument("--split-seed", type=int, default=1056801)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--sequence-length", type=int, default=8)
    parser.add_argument("--sequence-batch-size", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--selection-metric", choices=("kl", "top1"), default="top1")
    parser.add_argument("--trim-entity-padding", action="store_true")
    args = parser.parse_args()

    if args.output_checkpoint.exists() or args.manifest_out.exists():
        raise SystemExit("refusing to overwrite output checkpoint or manifest")
    device = torch.device(args.device)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    metadata, arrays = load_corpus(args.corpus)
    teacher_payload = torch.load(
        args.teacher_checkpoint, map_location=device, weights_only=False
    )
    student_payload = torch.load(
        args.student_checkpoint, map_location=device, weights_only=False
    )
    expected_tokens = tuple(metadata.token_names)
    if tuple(teacher_payload["token_names"]) != expected_tokens or tuple(
        student_payload["token_names"]
    ) != expected_tokens:
        raise SystemExit("checkpoint token vocabulary does not match corpus")
    teacher = _load_policy(teacher_payload, device=device)
    student = _load_policy(student_payload, device=device)
    if teacher.config.equivariant_slot_choice:
        raise SystemExit("teacher must be non-equivariant")
    if student.equivariant_timing_query is None:
        raise SystemExit("student has no equivariant timing query")
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)

    all_indices = np.arange(metadata.samples, dtype=np.int64)
    all_chunks = sequence_chunks(
        arrays["episode_ids"], all_indices, sequence_length=args.sequence_length
    )
    cache_metadata = {
        "schema_version": 1,
        "teacher_checkpoint_sha256": file_sha256(args.teacher_checkpoint),
        "corpus_sha256": file_sha256(args.corpus),
        "sequence_length": args.sequence_length,
        "temperature": args.temperature,
        "permutations": int(ALL_HAND_ORDERS.shape[0]),
    }
    if args.target_cache.exists():
        with np.load(args.target_cache, allow_pickle=False) as cache:
            actual_metadata = json.loads(str(cache["metadata_json"].item()))
            if actual_metadata != cache_metadata:
                raise SystemExit("teacher timing cache metadata mismatch")
            targets = cache["targets"].copy()
            originals = cache["originals"].copy()
            target_metrics = json.loads(str(cache["metrics_json"].item()))
    else:
        targets, originals, target_metrics = build_teacher_timing_targets(
            teacher,
            arrays,
            all_chunks,
            device=device,
            sequence_batch_size=args.sequence_batch_size,
            temperature=args.temperature,
            trim_entity_padding=args.trim_entity_padding,
        )
        args.target_cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            args.target_cache,
            targets=targets,
            originals=originals,
            metadata_json=np.asarray(json.dumps(cache_metadata, sort_keys=True)),
            metrics_json=np.asarray(json.dumps(target_metrics, sort_keys=True)),
        )

    training_indices, validation_indices = split_indices(
        arrays["episode_ids"],
        validation_fraction=args.validation_fraction,
        seed=args.split_seed,
    )
    training_chunks = sequence_chunks(
        arrays["episode_ids"], training_indices, sequence_length=args.sequence_length
    )
    validation_chunks = sequence_chunks(
        arrays["episode_ids"], validation_indices, sequence_length=args.sequence_length
    )
    best_state, history = fit_timing_query(
        student,
        arrays,
        training_chunks,
        validation_chunks,
        targets,
        device=device,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        sequence_batch_size=args.sequence_batch_size,
        trim_entity_padding=args.trim_entity_padding,
        seed=args.seed,
        selection_metric=args.selection_metric,
    )
    result = dict(student_payload)
    result["model_state_dict"] = best_state
    result.pop("optimizer_state_dict", None)
    result["equivariant_timing_distillation"] = {
        "schema_version": 1,
        "teacher_checkpoint": str(args.teacher_checkpoint.resolve()),
        "teacher_checkpoint_sha256": file_sha256(args.teacher_checkpoint),
        "student_initializer": str(args.student_checkpoint.resolve()),
        "student_initializer_sha256": file_sha256(args.student_checkpoint),
        "corpus": str(args.corpus.resolve()),
        "corpus_sha256": file_sha256(args.corpus),
        "target_cache": str(args.target_cache.resolve()),
        "target_cache_sha256": file_sha256(args.target_cache),
        "all_hand_permutations": int(ALL_HAND_ORDERS.shape[0]),
        "temperature": args.temperature,
        "sequence_length": args.sequence_length,
        "selection_metric": args.selection_metric,
        "target_metrics": target_metrics,
        "history": history,
    }
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, args.output_checkpoint)
    best_validation = (
        min(
            (row["validation"] for row in history),
            key=lambda metrics: metrics["kl"],
        )
        if args.selection_metric == "kl"
        else max(
            (row["validation"] for row in history),
            key=lambda metrics: metrics["top1_agreement"],
        )
    )
    manifest = {
        **result["equivariant_timing_distillation"],
        "output_checkpoint": str(args.output_checkpoint.resolve()),
        "output_checkpoint_sha256": file_sha256(args.output_checkpoint),
        "training_chunks": len(training_chunks),
        "validation_chunks": len(validation_chunks),
        "best_validation": best_validation,
    }
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
