# mypy: disable-error-code="import-untyped"
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.imitation import (
    _sequence_batch_inputs,
    load_corpus,
    split_indices,
)
from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs, PolicyOutput
from scripts.distill_equivariant_slot_choice import (
    permute_current_hand_batch,
    repeat_state_for_permutations,
)

PLACEMENT_ACTIONS = NUM_HAND_SLOTS * NUM_TILES
NUM_ACTIONS = PLACEMENT_ACTIONS + 2
ALL_HAND_ORDERS = torch.tensor(
    list(itertools.permutations(range(NUM_HAND_SLOTS))),
    dtype=torch.long,
)
DEFAULT_TRAINABLE_PREFIXES = (
    "action_type_head.",
    "semantic_slot_choice_query.",
    "mechanics_slot_choice_query.",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_policy(payload: dict[str, Any], *, device: torch.device) -> ClasherPolicy:
    config = PolicyConfig.from_dict(payload["model_config"])
    card_stats = payload["model_state_dict"].get("actor_encoder.card_stat_features")
    if not isinstance(card_stats, (np.ndarray, torch.Tensor)):
        raise TypeError("checkpoint has no actor card-stat buffer")
    model = ClasherPolicy(config, card_stats).to(device)
    model.load_state_dict(payload["model_state_dict"])
    return model


def canonicalize_permuted_joint_probabilities(
    probabilities: Tensor,
    orders: Tensor = ALL_HAND_ORDERS,
) -> Tensor:
    """Map physical-slot action probabilities back to original card slots."""

    if probabilities.ndim != 3 or probabilities.shape[-1] != NUM_ACTIONS:
        raise ValueError(
            "probabilities must have shape [batch, permutations, actions]"
        )
    if orders.ndim != 2 or orders.shape[1] != NUM_HAND_SLOTS:
        raise ValueError("orders must have shape [permutations, four slots]")
    if probabilities.shape[1] != orders.shape[0]:
        raise ValueError("probability and permutation counts differ")

    batch_size, permutation_count, _ = probabilities.shape
    physical = probabilities[..., :PLACEMENT_ACTIONS].reshape(
        batch_size,
        permutation_count,
        NUM_HAND_SLOTS,
        NUM_TILES,
    )
    canonical = torch.zeros_like(physical)
    index = (
        orders.to(probabilities.device)
        .view(1, permutation_count, NUM_HAND_SLOTS, 1)
        .expand(batch_size, -1, -1, NUM_TILES)
    )
    canonical.scatter_(dim=2, index=index, src=physical)
    return torch.cat(
        [
            canonical.reshape(batch_size, permutation_count, PLACEMENT_ACTIONS),
            probabilities[..., PLACEMENT_ACTIONS:],
        ],
        dim=-1,
    )


def masked_joint_probabilities(
    output: PolicyOutput,
    action_mask: Tensor,
    *,
    temperature: float,
) -> Tensor:
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("temperature must be finite and positive")
    logits = output.joint_logits[:, 0] / temperature
    mask = action_mask[:, 0]
    return torch.softmax(logits.masked_fill(~mask, -torch.inf), dim=-1)


def soft_cross_entropy(target: Tensor, log_probabilities: Tensor) -> Tensor:
    """Return per-row soft cross entropy without evaluating ``0 * -inf``."""

    if target.shape != log_probabilities.shape:
        raise ValueError("target and log-probability shapes must match")
    contributions = torch.where(
        target > 0.0,
        target * log_probabilities,
        torch.zeros_like(target),
    )
    return -contributions.sum(dim=-1)


def soft_kl(target: Tensor, log_probabilities: Tensor) -> Tensor:
    """Return KL(target || policy) with exact support-aware zero handling."""

    if target.shape != log_probabilities.shape:
        raise ValueError("target and log-probability shapes must match")
    contributions = torch.where(
        target > 0.0,
        target * (target.clamp_min(torch.finfo(target.dtype).tiny).log() - log_probabilities),
        torch.zeros_like(target),
    )
    return contributions.sum(dim=-1)


@torch.no_grad()
def symmetrized_teacher_step(
    teacher: ClasherPolicy,
    inputs: PolicyInputs,
    state: tuple[Tensor, Tensor],
    *,
    temperature: float,
    orders: Tensor = ALL_HAND_ORDERS,
) -> tuple[Tensor, Tensor, tuple[Tensor, Tensor]]:
    """Evaluate one exact recurrent teacher state under every current-hand order."""

    if inputs.batch_size != 1 or inputs.sequence_length != 1:
        raise ValueError("teacher step requires one recurrent state and one time step")
    original_output = teacher(inputs, state)
    original = masked_joint_probabilities(
        original_output,
        inputs.action_mask,
        temperature=temperature,
    )
    permuted_inputs = permute_current_hand_batch(inputs, orders)
    permuted_state = repeat_state_for_permutations(state, int(orders.shape[0]))
    permuted_output = teacher(permuted_inputs, permuted_state)
    permuted = masked_joint_probabilities(
        permuted_output,
        permuted_inputs.action_mask,
        temperature=temperature,
    ).reshape(1, int(orders.shape[0]), NUM_ACTIONS)
    symmetrized = canonicalize_permuted_joint_probabilities(
        permuted,
        orders,
    ).mean(dim=1)
    return (
        symmetrized,
        original,
        tuple(value.detach() for value in original_output.next_state),
    )


def episode_sequences(
    episode_ids: np.ndarray,
    indices: Iterable[int] | np.ndarray,
) -> list[np.ndarray]:
    """Return complete, contiguous episode rows selected by an episode split."""

    selected = np.asarray(list(indices), dtype=np.int64)
    if selected.ndim != 1 or selected.size == 0:
        raise ValueError("episode selection must be a non-empty vector")
    allowed = np.zeros(len(episode_ids), dtype=np.bool_)
    allowed[selected] = True
    sequences: list[np.ndarray] = []
    for episode_id in np.unique(episode_ids[selected]):
        rows = np.flatnonzero((episode_ids == episode_id) & allowed)
        if rows.size == 0:
            continue
        if np.any(np.diff(rows) != 1):
            raise ValueError("selected episode rows must be contiguous")
        all_rows = np.flatnonzero(episode_ids == episode_id)
        if not np.array_equal(rows, all_rows):
            raise ValueError("episode split must retain or exclude whole episodes")
        sequences.append(rows)
    if not sequences:
        raise ValueError("episode split contains no complete episodes")
    return sequences


def _single_step_inputs(
    arrays: dict[str, np.ndarray],
    index: int,
    device: torch.device,
    *,
    trim_entity_padding: bool,
) -> PolicyInputs:
    inputs = _sequence_batch_inputs(
        arrays,
        np.asarray([[index]], dtype=np.int64),
        device,
        trim_entity_padding=trim_entity_padding,
    )
    inputs.episode_starts[0, 0] = bool(arrays["episode_starts"][index])
    return inputs


def _sequence_inputs(
    arrays: dict[str, np.ndarray],
    indices: np.ndarray,
    device: torch.device,
    *,
    trim_entity_padding: bool,
) -> PolicyInputs:
    inputs = _sequence_batch_inputs(
        arrays,
        indices.reshape(1, -1),
        device,
        trim_entity_padding=trim_entity_padding,
    )
    inputs.episode_starts[0, 0] = bool(arrays["episode_starts"][indices[0]])
    return inputs


@torch.no_grad()
def build_teacher_targets(
    teacher: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    *,
    device: torch.device,
    temperature: float,
    trim_entity_padding: bool,
    progress_interval: int = 256,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Build exact full-action targets while carrying teacher state per episode."""

    sample_count = int(arrays["hand_ids"].shape[0])
    targets = np.full((sample_count, NUM_ACTIONS), np.nan, dtype=np.float32)
    originals = np.full_like(targets, np.nan)
    teacher.eval()
    started = time.monotonic()
    completed = 0
    all_rows = np.arange(sample_count, dtype=np.int64)
    for rows in episode_sequences(arrays["episode_ids"], all_rows):
        state = teacher.initial_state(1, device=device)
        for index in rows:
            inputs = _single_step_inputs(
                arrays,
                int(index),
                device,
                trim_entity_padding=trim_entity_padding,
            )
            target, original, state = symmetrized_teacher_step(
                teacher,
                inputs,
                state,
                temperature=temperature,
            )
            targets[index] = target[0].float().cpu().numpy()
            originals[index] = original[0].float().cpu().numpy()
            completed += 1
            if completed % progress_interval == 0 or completed == sample_count:
                print(
                    json.dumps(
                        {
                            "teacher_target_rows": completed,
                            "teacher_target_total_rows": sample_count,
                            "elapsed_seconds": time.monotonic() - started,
                        }
                    ),
                    flush=True,
                )

    if not np.isfinite(targets).all() or not np.isfinite(originals).all():
        raise FloatingPointError("teacher target construction left non-finite rows")
    legal = np.asarray(arrays["action_masks"], dtype=np.bool_)
    if np.any(targets[~legal] != 0.0) or np.any(originals[~legal] != 0.0):
        raise ValueError("teacher targets assign mass to illegal actions")
    if not np.allclose(targets.sum(axis=-1), 1.0, atol=2e-6):
        raise ValueError("symmetrized teacher distributions do not sum to one")
    if not np.allclose(originals.sum(axis=-1), 1.0, atol=2e-6):
        raise ValueError("original teacher distributions do not sum to one")

    informative = legal.sum(axis=-1) > 1
    epsilon = 1e-12
    selected_target = np.clip(targets[informative], epsilon, 1.0)
    selected_original = np.clip(originals[informative], epsilon, 1.0)
    placement_target = targets[:, :PLACEMENT_ACTIONS].sum(axis=-1)
    placement_original = originals[:, :PLACEMENT_ACTIONS].sum(axis=-1)
    metrics = {
        "samples": float(sample_count),
        "episodes": float(np.unique(arrays["episode_ids"]).size),
        "informative_samples": float(informative.sum()),
        "teacher_original_symmetrized_top1_agreement": float(
            (targets[informative].argmax(axis=-1) == originals[informative].argmax(axis=-1)).mean()
        ),
        "teacher_original_to_symmetrized_kl": float(
            np.sum(
                selected_target
                * (np.log(selected_target) - np.log(selected_original)),
                axis=-1,
            ).mean()
        ),
        "symmetrized_target_entropy": float(
            -np.sum(selected_target * np.log(selected_target), axis=-1).mean()
        ),
        "symmetrized_mean_play_mass": float(placement_target.mean()),
        "original_mean_play_mass": float(placement_original.mean()),
        "target_seconds": float(time.monotonic() - started),
    }
    return targets, originals, metrics


def _soft_target_metrics(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    sequences: list[np.ndarray],
    targets: np.ndarray,
    *,
    device: torch.device,
    sequence_length: int,
    trim_entity_padding: bool,
) -> dict[str, float]:
    model.eval()
    total_cross_entropy = 0.0
    total_kl = 0.0
    top1 = 0
    count = 0
    with torch.no_grad():
        for rows in sequences:
            state = model.initial_state(1, device=device)
            for start in range(0, len(rows), sequence_length):
                chunk = rows[start : start + sequence_length]
                inputs = _sequence_inputs(
                    arrays,
                    chunk,
                    device,
                    trim_entity_padding=trim_entity_padding,
                )
                output = model(inputs, state)
                state = tuple(value.detach() for value in output.next_state)
                legal = inputs.action_mask[0]
                informative = legal.sum(dim=-1) > 1
                if not bool(informative.any()):
                    continue
                log_probabilities = torch.log_softmax(
                    output.joint_logits[0].masked_fill(~legal, -torch.inf),
                    dim=-1,
                )[informative]
                selected = torch.as_tensor(
                    targets[chunk], dtype=torch.float32, device=device
                )[informative]
                cross_entropy = soft_cross_entropy(selected, log_probabilities)
                total_cross_entropy += float(cross_entropy.sum())
                total_kl += float(soft_kl(selected, log_probabilities).sum())
                top1 += int(
                    (selected.argmax(dim=-1) == log_probabilities.argmax(dim=-1))
                    .sum()
                    .item()
                )
                count += int(selected.shape[0])
    if count == 0:
        raise ValueError("evaluation split contains no informative decisions")
    return {
        "samples": float(count),
        "cross_entropy": total_cross_entropy / count,
        "kl": total_kl / count,
        "top1_agreement": top1 / count,
    }


def fit_student(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    training_sequences: list[np.ndarray],
    validation_sequences: list[np.ndarray],
    targets: np.ndarray,
    *,
    device: torch.device,
    epochs: int,
    learning_rate: float,
    sequence_length: int,
    trim_entity_padding: bool,
    seed: int,
    trainable_prefixes: tuple[str, ...],
) -> tuple[dict[str, Tensor], list[dict[str, Any]]]:
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(
            any(name.startswith(prefix) for prefix in trainable_prefixes)
        )
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    trainable_names = [
        name for name, parameter in model.named_parameters() if parameter.requires_grad
    ]
    if not trainable:
        raise ValueError("student has no trainable parameters")
    optimizer = torch.optim.AdamW(trainable, lr=learning_rate)
    rng = np.random.default_rng(seed)
    history: list[dict[str, Any]] = []
    best_state = {
        name: value.detach().cpu().clone() for name, value in model.state_dict().items()
    }
    best_kl = math.inf

    control = _soft_target_metrics(
        model,
        arrays,
        validation_sequences,
        targets,
        device=device,
        sequence_length=sequence_length,
        trim_entity_padding=trim_entity_padding,
    )
    history.append(
        {
            "epoch": 0,
            "validation": control,
            "trainable_parameter_names": trainable_names,
        }
    )
    best_kl = control["kl"]

    for epoch in range(1, epochs + 1):
        model.train()
        order = rng.permutation(len(training_sequences))
        loss_sum = 0.0
        sample_count = 0
        gradient_norm_max = 0.0
        started = time.monotonic()
        for episode_position in order:
            rows = training_sequences[int(episode_position)]
            state = model.initial_state(1, device=device)
            for start in range(0, len(rows), sequence_length):
                chunk = rows[start : start + sequence_length]
                inputs = _sequence_inputs(
                    arrays,
                    chunk,
                    device,
                    trim_entity_padding=trim_entity_padding,
                )
                output = model(inputs, state)
                state = tuple(value.detach() for value in output.next_state)
                legal = inputs.action_mask[0]
                informative = legal.sum(dim=-1) > 1
                if not bool(informative.any()):
                    continue
                selected_target = torch.as_tensor(
                    targets[chunk], dtype=torch.float32, device=device
                )[informative]
                selected_log = torch.log_softmax(
                    output.joint_logits[0].masked_fill(~legal, -torch.inf),
                    dim=-1,
                )[informative]
                loss = soft_cross_entropy(selected_target, selected_log).mean()
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError("non-finite symmetry DAgger loss")
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                gradient_norm = nn.utils.clip_grad_norm_(trainable, 0.5)
                if not bool(torch.isfinite(gradient_norm)):
                    raise FloatingPointError(
                        "non-finite symmetry DAgger gradient norm"
                    )
                optimizer.step()
                count = int(selected_target.shape[0])
                loss_sum += float(loss.detach()) * count
                sample_count += count
                gradient_norm_max = max(gradient_norm_max, float(gradient_norm))

        validation = _soft_target_metrics(
            model,
            arrays,
            validation_sequences,
            targets,
            device=device,
            sequence_length=sequence_length,
            trim_entity_padding=trim_entity_padding,
        )
        row = {
            "epoch": epoch,
            "training_cross_entropy": loss_sum / max(1, sample_count),
            "training_samples": sample_count,
            "gradient_norm_max": gradient_norm_max,
            "validation": validation,
            "epoch_seconds": time.monotonic() - started,
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        if validation["kl"] < best_kl:
            best_kl = validation["kl"]
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
    return best_state, history


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fit an exactly slot-equivariant student on its own recurrent states "
            "using a full-action teacher averaged over all 24 current-hand orders"
        )
    )
    parser.add_argument("--teacher-checkpoint", required=True, type=Path)
    parser.add_argument("--student-checkpoint", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--target-cache", required=True, type=Path)
    parser.add_argument("--output-checkpoint", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--seed", type=int, default=1056901)
    parser.add_argument("--split-seed", type=int, default=1056902)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--sequence-length", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--trim-entity-padding", action="store_true")
    parser.add_argument(
        "--trainable-prefix",
        action="append",
        default=[],
        help="repeat to override the default timing plus structural-card heads",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for path in (args.teacher_checkpoint, args.student_checkpoint, args.corpus):
        if not path.is_file():
            raise SystemExit(f"missing required input: {path}")
    if args.output_checkpoint.exists() or args.manifest_out.exists():
        raise SystemExit("refusing to overwrite output checkpoint or manifest")
    if args.epochs <= 0 or args.sequence_length <= 1:
        raise SystemExit("epochs must be positive and sequence length must exceed one")
    if args.learning_rate <= 0.0:
        raise SystemExit("learning rate must be positive")

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
        raise SystemExit("student must be exactly slot equivariant")
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)

    teacher_sha = file_sha256(args.teacher_checkpoint)
    student_sha = file_sha256(args.student_checkpoint)
    corpus_sha = file_sha256(args.corpus)
    cache_metadata = {
        "schema_version": 1,
        "teacher_checkpoint_sha256": teacher_sha,
        "student_state_corpus_sha256": corpus_sha,
        "temperature": args.temperature,
        "permutations": int(ALL_HAND_ORDERS.shape[0]),
        "recurrent_state": "exact_episode_order",
        "target": "full_masked_joint_action_distribution",
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
            device=device,
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
    training_sequences = episode_sequences(arrays["episode_ids"], training_indices)
    validation_sequences = episode_sequences(arrays["episode_ids"], validation_indices)
    trainable_prefixes = tuple(args.trainable_prefix) or DEFAULT_TRAINABLE_PREFIXES
    best_state, history = fit_student(
        student,
        arrays,
        training_sequences,
        validation_sequences,
        targets,
        device=device,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        sequence_length=args.sequence_length,
        trim_entity_padding=args.trim_entity_padding,
        seed=args.seed,
        trainable_prefixes=trainable_prefixes,
    )
    student.load_state_dict(best_state)

    result = dict(student_payload)
    result["model_state_dict"] = best_state
    result.pop("optimizer_state_dict", None)
    result["student_state_symmetry_dagger"] = {
        "schema_version": 1,
        "teacher_checkpoint": str(args.teacher_checkpoint.resolve()),
        "teacher_checkpoint_sha256": teacher_sha,
        "student_initializer": str(args.student_checkpoint.resolve()),
        "student_initializer_sha256": student_sha,
        "student_state_corpus": str(args.corpus.resolve()),
        "student_state_corpus_sha256": corpus_sha,
        "target_cache": str(args.target_cache.resolve()),
        "target_cache_sha256": file_sha256(args.target_cache),
        "target_metrics": target_metrics,
        "all_hand_permutations": int(ALL_HAND_ORDERS.shape[0]),
        "temperature": args.temperature,
        "recurrent_state": "exact_episode_order",
        "sequence_length": args.sequence_length,
        "trainable_prefixes": list(trainable_prefixes),
        "history": history,
    }
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, args.output_checkpoint)
    manifest = {
        **result["student_state_symmetry_dagger"],
        "output_checkpoint": str(args.output_checkpoint.resolve()),
        "output_checkpoint_sha256": file_sha256(args.output_checkpoint),
        "training_episodes": len(training_sequences),
        "validation_episodes": len(validation_sequences),
        "best_validation": min(
            (row["validation"] for row in history),
            key=lambda metrics: metrics["kl"],
        ),
    }
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
