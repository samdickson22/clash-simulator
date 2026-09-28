# mypy: disable-error-code="import-untyped"
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import time
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.imitation import (
    _sequence_batch_inputs,
    load_corpus,
    sequence_chunks,
    split_indices,
)
from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs

ALL_HAND_ORDERS = torch.tensor(
    list(itertools.permutations(range(NUM_HAND_SLOTS))),
    dtype=torch.long,
)
PLACEMENT_ACTIONS = NUM_HAND_SLOTS * NUM_TILES


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def time_slice(inputs: PolicyInputs, index: int) -> PolicyInputs:
    payload: dict[str, torch.Tensor | None] = {}
    for field in fields(PolicyInputs):
        value = getattr(inputs, field.name)
        payload[field.name] = None if value is None else value[:, index : index + 1]
    return PolicyInputs(**payload)  # type: ignore[arg-type]


def permute_current_hand_batch(
    inputs: PolicyInputs,
    orders: torch.Tensor = ALL_HAND_ORDERS,
) -> PolicyInputs:
    """Expand single-step inputs across current-hand permutations.

    ``orders[p, slot]`` is the original slot moved into the new physical slot.
    Public history, next card, previous action, and recurrent state stay fixed.
    """

    if inputs.sequence_length != 1:
        raise ValueError("current-hand permutation requires one time step")
    if orders.ndim != 2 or orders.shape[1] != NUM_HAND_SLOTS:
        raise ValueError("orders must have shape [permutations, four slots]")
    expected = list(range(NUM_HAND_SLOTS))
    if any(sorted(row.tolist()) != expected for row in orders.cpu()):
        raise ValueError("each order row must be a four-slot permutation")

    batch_size = inputs.batch_size
    permutation_count = int(orders.shape[0])
    payload: dict[str, torch.Tensor | None] = {}
    for field in fields(PolicyInputs):
        value = getattr(inputs, field.name)
        if value is None:
            payload[field.name] = None
            continue
        payload[field.name] = (
            value.unsqueeze(1)
            .expand(batch_size, permutation_count, *value.shape[1:])
            .reshape(batch_size * permutation_count, *value.shape[1:])
            .clone()
        )

    device_orders = orders.to(inputs.hand_ids.device)
    hand_ids = payload["hand_ids"]
    assert hand_ids is not None
    original_hand = inputs.hand_ids[:, 0, :NUM_HAND_SLOTS]
    hand_ids[:, 0, :NUM_HAND_SLOTS] = original_hand[:, device_orders].reshape(
        batch_size * permutation_count,
        NUM_HAND_SLOTS,
    )

    hand_confidence = payload["hand_id_confidence"]
    if hand_confidence is not None:
        assert inputs.hand_id_confidence is not None
        original_confidence = inputs.hand_id_confidence[:, 0, :NUM_HAND_SLOTS]
        hand_confidence[:, 0, :NUM_HAND_SLOTS] = original_confidence[
            :, device_orders
        ].reshape(batch_size * permutation_count, NUM_HAND_SLOTS)

    action_mask = payload["action_mask"]
    assert action_mask is not None
    original_placements = inputs.action_mask[
        :, 0, :PLACEMENT_ACTIONS
    ].reshape(batch_size, NUM_HAND_SLOTS, NUM_TILES)
    action_mask[:, 0, :PLACEMENT_ACTIONS] = original_placements[
        :, device_orders
    ].reshape(batch_size * permutation_count, PLACEMENT_ACTIONS)

    critic_cards = payload["critic_card_ids"]
    if critic_cards is not None:
        assert inputs.critic_card_ids is not None
        original_critic = inputs.critic_card_ids[:, 0, :NUM_HAND_SLOTS]
        critic_cards[:, 0, :NUM_HAND_SLOTS] = original_critic[
            :, device_orders
        ].reshape(batch_size * permutation_count, NUM_HAND_SLOTS)

    return PolicyInputs(**payload)  # type: ignore[arg-type]


def repeat_state_for_permutations(
    state: tuple[torch.Tensor, torch.Tensor],
    permutation_count: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    return tuple(
        value.unsqueeze(1)
        .expand(value.shape[0], permutation_count, value.shape[1])
        .reshape(value.shape[0] * permutation_count, value.shape[1])
        .clone()
        for value in state
    )  # type: ignore[return-value]


def legal_slot_mask(action_mask: torch.Tensor) -> torch.Tensor:
    return action_mask[..., :PLACEMENT_ACTIONS].reshape(
        *action_mask.shape[:-1], NUM_HAND_SLOTS, NUM_TILES
    ).any(dim=-1)


def conditional_slot_probabilities(
    slot_logits: torch.Tensor,
    legal_slots: torch.Tensor,
    *,
    temperature: float,
) -> torch.Tensor:
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("temperature must be finite and positive")
    masked = (slot_logits / temperature).masked_fill(~legal_slots, -1e9)
    probabilities = torch.softmax(masked, dim=-1)
    return probabilities * legal_slots.to(probabilities.dtype)


def canonicalize_permuted_slot_probabilities(
    probabilities: torch.Tensor,
    orders: torch.Tensor,
) -> torch.Tensor:
    """Map probabilities from physical permuted slots back to original cards."""

    if probabilities.ndim != 3 or probabilities.shape[-1] != NUM_HAND_SLOTS:
        raise ValueError("probabilities must have shape [batch, permutations, four]")
    if probabilities.shape[1] != orders.shape[0]:
        raise ValueError("probability and permutation counts differ")
    canonical = torch.zeros_like(probabilities)
    index = orders.to(probabilities.device).unsqueeze(0).expand(
        probabilities.shape[0], -1, -1
    )
    canonical.scatter_(dim=-1, index=index, src=probabilities)
    return canonical


def _load_policy(
    payload: dict[str, Any],
    *,
    device: torch.device,
) -> ClasherPolicy:
    config = PolicyConfig.from_dict(payload["model_config"])
    card_stats = payload["model_state_dict"].get("actor_encoder.card_stat_features")
    if not isinstance(card_stats, (np.ndarray, torch.Tensor)):
        raise TypeError("checkpoint has no actor card-stat buffer")
    model = ClasherPolicy(config, card_stats).to(device)
    model.load_state_dict(payload["model_state_dict"])
    return model


@torch.no_grad()
def build_teacher_targets(
    teacher: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    chunks: np.ndarray,
    *,
    device: torch.device,
    sequence_batch_size: int,
    temperature: float,
    trim_entity_padding: bool,
    orders: torch.Tensor = ALL_HAND_ORDERS,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Return exact all-permutation teacher distributions for corpus rows."""

    sample_count = int(arrays["hand_ids"].shape[0])
    targets = np.full((sample_count, NUM_HAND_SLOTS), np.nan, dtype=np.float32)
    originals = np.full_like(targets, np.nan)
    teacher.eval()
    permutation_count = int(orders.shape[0])
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

            permuted_inputs = permute_current_hand_batch(step_inputs, orders)
            permuted_state = repeat_state_for_permutations(
                pre_state,
                permutation_count,
            )
            permuted_output = teacher(permuted_inputs, permuted_state)
            permuted_legal = legal_slot_mask(permuted_inputs.action_mask[:, 0])
            permuted_probabilities = conditional_slot_probabilities(
                permuted_output.action_type_logits[:, 0, :NUM_HAND_SLOTS],
                permuted_legal,
                temperature=temperature,
            ).reshape(inputs.batch_size, permutation_count, NUM_HAND_SLOTS)
            canonical = canonicalize_permuted_slot_probabilities(
                permuted_probabilities,
                orders,
            ).mean(dim=1)

            original_legal = legal_slot_mask(step_inputs.action_mask[:, 0])
            original_probabilities = conditional_slot_probabilities(
                original_output.action_type_logits[:, 0, :NUM_HAND_SLOTS],
                original_legal,
                temperature=temperature,
            )
            row_indices = batch_chunks[:, step_index]
            targets[row_indices] = canonical.cpu().numpy()
            originals[row_indices] = original_probabilities.cpu().numpy()

        completed = min(start + sequence_batch_size, len(chunks))
        if completed == len(chunks) or completed % max(sequence_batch_size, 64) == 0:
            print(
                json.dumps(
                    {
                        "teacher_target_chunks": completed,
                        "teacher_target_total_chunks": len(chunks),
                        "elapsed_seconds": time.monotonic() - started,
                    }
                ),
                flush=True,
            )

    valid = np.isfinite(targets).all(axis=1)
    legal = arrays["action_masks"][:, :PLACEMENT_ACTIONS].reshape(
        sample_count, NUM_HAND_SLOTS, NUM_TILES
    ).any(axis=-1)
    informative = valid & (legal.sum(axis=-1) >= 2)
    epsilon = 1e-12
    target = np.clip(targets[informative], epsilon, 1.0)
    original = np.clip(originals[informative], epsilon, 1.0)
    metrics = {
        "covered_samples": float(valid.sum()),
        "informative_samples": float(informative.sum()),
        "teacher_original_symmetrized_top1_agreement": float(
            (target.argmax(axis=-1) == original.argmax(axis=-1)).mean()
        ),
        "teacher_original_to_symmetrized_kl": float(
            np.sum(target * (np.log(target) - np.log(original)), axis=-1).mean()
        ),
        "symmetrized_target_entropy": float(
            -np.sum(target * np.log(target), axis=-1).mean()
        ),
        "target_seconds": float(time.monotonic() - started),
    }
    return targets, originals, metrics


def evaluate_student(
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
    total_kl = 0.0
    total_cross_entropy = 0.0
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
            output = model(inputs)
            legal = legal_slot_mask(inputs.action_mask)
            target = torch.as_tensor(
                targets[batch_chunks], dtype=torch.float32, device=device
            )
            valid = torch.isfinite(target).all(dim=-1) & (legal.sum(dim=-1) >= 2)
            if not bool(valid.any()):
                continue
            log_probabilities = torch.log_softmax(
                output.action_type_logits[..., :NUM_HAND_SLOTS].masked_fill(
                    ~legal, -1e9
                ),
                dim=-1,
            )
            selected_target = target[valid]
            selected_log = log_probabilities[valid]
            cross_entropy = -(selected_target * selected_log).sum(dim=-1)
            target_log = selected_target.clamp_min(1e-12).log()
            total_cross_entropy += float(cross_entropy.sum())
            total_kl += float(
                (selected_target * (target_log - selected_log)).sum(dim=-1).sum()
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


def fit_student(
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
    trainable_prefixes = (
        "mechanics_slot_choice_query.",
        "semantic_slot_choice_query.",
    )
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(name.startswith(trainable_prefixes))
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if not trainable:
        raise ValueError("student has no trainable equivariant card query")
    optimizer = torch.optim.AdamW(trainable, lr=learning_rate)
    rng = np.random.default_rng(seed)
    history: list[dict[str, Any]] = []
    best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    best_score = math.inf if selection_metric == "kl" else -math.inf

    control = evaluate_student(
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
            legal = legal_slot_mask(inputs.action_mask)
            valid = torch.isfinite(target).all(dim=-1) & (legal.sum(dim=-1) >= 2)
            if not bool(valid.any()):
                continue
            output = model(inputs)
            log_probabilities = torch.log_softmax(
                output.action_type_logits[..., :NUM_HAND_SLOTS].masked_fill(
                    ~legal, -1e9
                ),
                dim=-1,
            )
            selected_target = target[valid]
            selected_log = log_probabilities[valid]
            loss = -(selected_target * selected_log).sum(dim=-1).mean()
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("non-finite distillation loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            gradient_norm = nn.utils.clip_grad_norm_(trainable, 0.5)
            if not bool(torch.isfinite(gradient_norm)):
                raise FloatingPointError("non-finite distillation gradient norm")
            optimizer.step()
            batch_count = int(selected_target.shape[0])
            loss_sum += float(loss.detach()) * batch_count
            sample_count += batch_count

        validation = evaluate_student(
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
    parser.add_argument("--seed", type=int, default=1056804)
    parser.add_argument("--split-seed", type=int, default=1056801)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--sequence-length", type=int, default=8)
    parser.add_argument("--sequence-batch-size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--selection-metric", choices=("kl", "top1"), default="kl")
    parser.add_argument("--trim-entity-padding", action="store_true")
    args = parser.parse_args()

    if args.output_checkpoint.exists() or args.manifest_out.exists():
        raise SystemExit("refusing to overwrite output checkpoint or manifest")
    if args.sequence_length <= 1 or args.sequence_batch_size <= 0:
        raise SystemExit("sequence length must exceed one and batch size must be positive")
    if args.epochs <= 0 or args.learning_rate <= 0.0:
        raise SystemExit("epochs and learning rate must be positive")

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
    if tuple(teacher_payload["token_names"]) != expected_tokens:
        raise SystemExit("teacher token vocabulary does not match corpus")
    if tuple(student_payload["token_names"]) != expected_tokens:
        raise SystemExit("student token vocabulary does not match corpus")

    teacher = _load_policy(teacher_payload, device=device)
    student = _load_policy(student_payload, device=device)
    if teacher.config.equivariant_slot_choice:
        raise SystemExit("teacher must be the accepted non-equivariant policy")
    if not student.config.equivariant_slot_choice:
        raise SystemExit("student must use structural equivariant slot choice")
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)

    all_indices = np.arange(metadata.samples, dtype=np.int64)
    all_chunks = sequence_chunks(
        arrays["episode_ids"], all_indices, sequence_length=args.sequence_length
    )
    teacher_sha = file_sha256(args.teacher_checkpoint)
    corpus_sha = file_sha256(args.corpus)
    cache_metadata = {
        "schema_version": 1,
        "teacher_checkpoint_sha256": teacher_sha,
        "corpus_sha256": corpus_sha,
        "sequence_length": args.sequence_length,
        "temperature": args.temperature,
        "permutations": int(ALL_HAND_ORDERS.shape[0]),
    }
    if args.target_cache.exists():
        with np.load(args.target_cache, allow_pickle=False) as cache:
            actual_metadata = json.loads(str(cache["metadata_json"].item()))
            if actual_metadata != cache_metadata:
                raise SystemExit("teacher target cache metadata mismatch")
            targets = cache["targets"].copy()
            originals = cache["originals"].copy()
            target_metrics = json.loads(str(cache["metrics_json"].item()))
    else:
        targets, originals, target_metrics = build_teacher_targets(
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
        arrays["episode_ids"],
        training_indices,
        sequence_length=args.sequence_length,
    )
    validation_chunks = sequence_chunks(
        arrays["episode_ids"],
        validation_indices,
        sequence_length=args.sequence_length,
    )
    best_state, history = fit_student(
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
    student.load_state_dict(best_state)

    result = dict(student_payload)
    result["model_state_dict"] = best_state
    result.pop("optimizer_state_dict", None)
    result["equivariant_slot_distillation"] = {
        "schema_version": 1,
        "teacher_checkpoint": str(args.teacher_checkpoint.resolve()),
        "teacher_checkpoint_sha256": teacher_sha,
        "student_initializer": str(args.student_checkpoint.resolve()),
        "student_initializer_sha256": file_sha256(args.student_checkpoint),
        "corpus": str(args.corpus.resolve()),
        "corpus_sha256": corpus_sha,
        "target_cache": str(args.target_cache.resolve()),
        "target_cache_sha256": file_sha256(args.target_cache),
        "all_hand_permutations": int(ALL_HAND_ORDERS.shape[0]),
        "temperature": args.temperature,
        "selection_metric": args.selection_metric,
        "sequence_length": args.sequence_length,
        "trainable_prefixes": [
            "mechanics_slot_choice_query.",
            "semantic_slot_choice_query.",
        ],
        "target_metrics": target_metrics,
        "history": history,
    }
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, args.output_checkpoint)
    manifest = {
        **result["equivariant_slot_distillation"],
        "output_checkpoint": str(args.output_checkpoint.resolve()),
        "output_checkpoint_sha256": file_sha256(args.output_checkpoint),
        "training_chunks": len(training_chunks),
        "validation_chunks": len(validation_chunks),
        "best_validation": (
            min(
                (row["validation"] for row in history),
                key=lambda metrics: metrics["kl"],
            )
            if args.selection_metric == "kl"
            else max(
                (row["validation"] for row in history),
                key=lambda metrics: metrics["top1_agreement"],
            )
        ),
    }
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
