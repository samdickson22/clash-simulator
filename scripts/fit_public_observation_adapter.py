from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.imitation import (
    _sequence_batch_inputs,
    load_corpus,
    load_policy_state_with_confidence_upgrade,
    load_public_observation_sidecar,
    sequence_chunks,
    split_indices,
)
from clasher.rl.model import ClasherPolicy, PolicyOutput
from clasher.rl.oracle_corpus import file_sha256
from clasher.rl.train_recurrent import (
    factorized_policy_anchor_kl,
    policy_anchor_kl,
    resolve_learner_device,
)

CONFIDENCE_PREFIXES = (
    "actor_encoder.card_confidence_projection.",
    "actor_encoder.entity_confidence_projection.",
    "actor_encoder.global_confidence_projection.",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Distill an exact-state policy into its confidence-aware public "
            "observation adapter while freezing every legacy parameter"
        )
    )
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--public-observation-sidecar", required=True)
    parser.add_argument("--initial-checkpoint", required=True)
    parser.add_argument("--output-checkpoint", required=True)
    parser.add_argument("--control-checkpoint", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--split-seed", type=int, required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--sequence-length", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--joint-kl-coef", type=float, default=1.0)
    parser.add_argument("--type-kl-coef", type=float, default=1.0)
    parser.add_argument("--location-kl-coef", type=float, default=0.25)
    parser.add_argument(
        "--device", choices=("auto", "cpu", "mps", "cuda"), default="auto"
    )
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> None:
    if args.epochs <= 0 or args.batch_size <= 0 or args.sequence_length <= 1:
        raise ValueError("epochs, batch size, and sequence length must be positive")
    if args.learning_rate <= 0.0:
        raise ValueError("learning rate must be positive")
    if not 0.0 < args.validation_fraction < 1.0:
        raise ValueError("validation fraction must be between zero and one")
    coefficients = (args.joint_kl_coef, args.type_kl_coef, args.location_kl_coef)
    if any(value < 0.0 for value in coefficients) or not any(coefficients):
        raise ValueError("KL coefficients must be non-negative with one positive")


def _build_student(
    *,
    checkpoint_path: Path,
    device: torch.device,
    decks_path: Path,
) -> tuple[ClasherPolicy, ClasherPolicy, dict[str, Any]]:
    loaded = load_policy_checkpoint(
        checkpoint_path,
        device=device,
        decks_path=decks_path,
    )
    teacher = loaded.model
    if teacher.config.public_observation_confidence:
        raise ValueError("initial checkpoint is already confidence-aware")
    student_config = replace(
        teacher.config,
        public_observation_confidence=True,
    )
    student = ClasherPolicy(
        student_config,
        loaded.builder.card_stat_features,
    ).to(device)
    load_policy_state_with_confidence_upgrade(
        student,
        loaded.checkpoint["model_state_dict"],
        upgrade_legacy_confidence=True,
    )
    teacher.eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    for name, parameter in student.named_parameters():
        parameter.requires_grad_(name.startswith(CONFIDENCE_PREFIXES))
    return teacher, student, loaded.checkpoint


def _distillation_loss(
    student_output: PolicyOutput,
    teacher_output: PolicyOutput,
    action_mask: torch.Tensor,
    *,
    joint_coef: float,
    type_coef: float,
    location_coef: float,
) -> torch.Tensor:
    loss: torch.Tensor = joint_coef * policy_anchor_kl(
        student_output.joint_logits,
        teacher_output.joint_logits,
    )
    if type_coef:
        loss = loss + type_coef * factorized_policy_anchor_kl(
            student_output,
            teacher_output,
            action_mask,
            component="type",
        )
    if location_coef:
        loss = loss + location_coef * factorized_policy_anchor_kl(
            student_output,
            teacher_output,
            action_mask,
            component="location",
        )
    return loss


@torch.no_grad()
def evaluate_adapter(
    *,
    teacher: ClasherPolicy,
    student: ClasherPolicy,
    exact_arrays: dict[str, np.ndarray],
    public_arrays: dict[str, np.ndarray],
    chunks: np.ndarray,
    device: torch.device,
    batch_size: int,
) -> dict[str, float]:
    teacher.eval()
    student.eval()
    batch_sequences = max(1, batch_size // chunks.shape[1])
    totals = {
        "joint_kl": 0.0,
        "type_kl": 0.0,
        "location_kl": 0.0,
        "action_matches": 0.0,
        "teacher_plays": 0.0,
        "student_plays": 0.0,
        "tokens": 0.0,
    }
    for start in range(0, len(chunks), batch_sequences):
        indices = chunks[start : start + batch_sequences]
        exact_inputs = _sequence_batch_inputs(exact_arrays, indices, device)
        public_inputs = _sequence_batch_inputs(public_arrays, indices, device)
        teacher_output = teacher(exact_inputs)
        student_output = student(public_inputs)
        mask = public_inputs.action_mask
        tokens = float(indices.size)
        totals["joint_kl"] += float(
            policy_anchor_kl(
                student_output.joint_logits,
                teacher_output.joint_logits,
            )
        ) * tokens
        totals["type_kl"] += float(
            factorized_policy_anchor_kl(
                student_output,
                teacher_output,
                mask,
                component="type",
            )
        ) * tokens
        totals["location_kl"] += float(
            factorized_policy_anchor_kl(
                student_output,
                teacher_output,
                mask,
                component="location",
            )
        ) * tokens
        teacher_actions = teacher._deterministic_actions(teacher_output, mask)
        student_actions = student._deterministic_actions(student_output, mask)
        totals["action_matches"] += float(
            (teacher_actions == student_actions).count_nonzero()
        )
        placement_actions = student.num_actions - 2
        totals["teacher_plays"] += float(
            (teacher_actions < placement_actions).count_nonzero()
        )
        totals["student_plays"] += float(
            (student_actions < placement_actions).count_nonzero()
        )
        totals["tokens"] += tokens
    denominator = max(1.0, totals["tokens"])
    return {
        "joint_kl": totals["joint_kl"] / denominator,
        "type_kl": totals["type_kl"] / denominator,
        "location_kl": totals["location_kl"] / denominator,
        "deterministic_action_agreement": totals["action_matches"] / denominator,
        "teacher_play_rate": totals["teacher_plays"] / denominator,
        "student_play_rate": totals["student_plays"] / denominator,
        "tokens": totals["tokens"],
    }


def _checkpoint_payload(
    *,
    source: dict[str, Any],
    model: ClasherPolicy,
    args: argparse.Namespace,
    metrics: dict[str, float],
    trained: bool,
) -> dict[str, Any]:
    payload = dict(source)
    payload["model_config"] = model.config.to_dict()
    payload["model_state_dict"] = model.state_dict()
    payload.pop("optimizer_state_dict", None)
    payload["public_observation_adapter"] = {
        "schema_version": 1,
        "trained": trained,
        "initial_checkpoint": str(Path(args.initial_checkpoint).resolve()),
        "corpus": str(Path(args.corpus).resolve()),
        "public_observation_sidecar": str(
            Path(args.public_observation_sidecar).resolve()
        ),
        "seed": args.seed,
        "split_seed": args.split_seed,
        "epochs": args.epochs if trained else 0,
        "learning_rate": args.learning_rate,
        "sequence_length": args.sequence_length,
        "joint_kl_coef": args.joint_kl_coef,
        "type_kl_coef": args.type_kl_coef,
        "location_kl_coef": args.location_kl_coef,
        "metrics": metrics,
    }
    return payload


def fit_adapter(args: argparse.Namespace) -> dict[str, Any]:
    _validate_args(args)
    device = resolve_learner_device(args.device)
    corpus_path = resolve_path(args.corpus, must_exist=True)
    sidecar_path = resolve_path(args.public_observation_sidecar, must_exist=True)
    checkpoint_path = resolve_path(args.initial_checkpoint, must_exist=True)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    metadata, exact_arrays = load_corpus(corpus_path)
    public_arrays = load_public_observation_sidecar(
        sidecar_path,
        base_arrays=exact_arrays,
    )
    teacher, student, source_checkpoint = _build_student(
        checkpoint_path=checkpoint_path,
        device=device,
        decks_path=decks_path,
    )
    if tuple(source_checkpoint["token_names"]) != tuple(metadata.token_names):
        raise ValueError("checkpoint and corpus token vocabularies do not match")
    train_indices, validation_indices = split_indices(
        exact_arrays["episode_ids"],
        validation_fraction=args.validation_fraction,
        seed=args.split_seed,
    )
    train_chunks = sequence_chunks(
        exact_arrays["episode_ids"],
        train_indices,
        sequence_length=args.sequence_length,
    )
    validation_chunks = sequence_chunks(
        exact_arrays["episode_ids"],
        validation_indices,
        sequence_length=args.sequence_length,
    )
    control_metrics = evaluate_adapter(
        teacher=teacher,
        student=student,
        exact_arrays=exact_arrays,
        public_arrays=public_arrays,
        chunks=validation_chunks,
        device=device,
        batch_size=args.batch_size,
    )
    control_path = resolve_path(args.control_checkpoint)
    control_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        _checkpoint_payload(
            source=source_checkpoint,
            model=student,
            args=args,
            metrics=control_metrics,
            trained=False,
        ),
        control_path,
    )

    parameters = [parameter for parameter in student.parameters() if parameter.requires_grad]
    if not parameters:
        raise ValueError("confidence adapter selected no trainable parameters")
    optimizer = torch.optim.AdamW(parameters, lr=args.learning_rate)
    rng = np.random.default_rng(args.seed)
    torch.manual_seed(args.seed)
    batch_sequences = max(1, args.batch_size // args.sequence_length)
    started = time.monotonic()
    for epoch in range(args.epochs):
        student.train()
        order = rng.permutation(len(train_chunks))
        for start in range(0, len(order), batch_sequences):
            indices = train_chunks[order[start : start + batch_sequences]]
            exact_inputs = _sequence_batch_inputs(exact_arrays, indices, device)
            public_inputs = _sequence_batch_inputs(public_arrays, indices, device)
            with torch.no_grad():
                teacher_output = teacher(exact_inputs)
            student_output = student(public_inputs)
            loss = _distillation_loss(
                student_output,
                teacher_output,
                public_inputs.action_mask,
                joint_coef=args.joint_kl_coef,
                type_coef=args.type_kl_coef,
                location_coef=args.location_kl_coef,
            )
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("public observation distillation loss is non-finite")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            gradient_norm = nn.utils.clip_grad_norm_(parameters, 0.5)
            if not bool(torch.isfinite(gradient_norm)):
                raise FloatingPointError("public observation adapter gradient is non-finite")
            optimizer.step()
        print(
            json.dumps(
                {
                    "completed_epoch": epoch + 1,
                    "epochs": args.epochs,
                    "elapsed_seconds": round(time.monotonic() - started, 1),
                }
            ),
            flush=True,
        )

    endpoint_metrics = evaluate_adapter(
        teacher=teacher,
        student=student,
        exact_arrays=exact_arrays,
        public_arrays=public_arrays,
        chunks=validation_chunks,
        device=device,
        batch_size=args.batch_size,
    )
    output_path = resolve_path(args.output_checkpoint)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        _checkpoint_payload(
            source=source_checkpoint,
            model=student,
            args=args,
            metrics=endpoint_metrics,
            trained=True,
        ),
        output_path,
    )
    manifest = {
        "schema_version": 1,
        "objective": "exact-to-public-policy-distillation-v1",
        "device": str(device),
        "corpus": str(corpus_path),
        "corpus_sha256": file_sha256(corpus_path),
        "public_observation_sidecar": str(sidecar_path),
        "public_observation_sidecar_sha256": file_sha256(sidecar_path),
        "initial_checkpoint": str(checkpoint_path),
        "initial_checkpoint_sha256": file_sha256(checkpoint_path),
        "control_checkpoint": str(control_path),
        "control_checkpoint_sha256": file_sha256(control_path),
        "output_checkpoint": str(output_path),
        "output_checkpoint_sha256": file_sha256(output_path),
        "train_sequences": len(train_chunks),
        "validation_sequences": len(validation_chunks),
        "config": {
            key: value
            for key, value in vars(args).items()
            if key not in {"corpus", "public_observation_sidecar", "initial_checkpoint"}
        },
        "control_metrics": control_metrics,
        "endpoint_metrics": endpoint_metrics,
    }
    return manifest


def main() -> None:
    args = parse_args()
    manifest = fit_adapter(args)
    output = resolve_path(args.manifest_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
