#!/usr/bin/env python3
"""Distill a retained hazard policy's actions into a factorized mode gate."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as F

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def action_modes(actions: Tensor) -> Tensor:
    placement_actions = NUM_HAND_SLOTS * NUM_TILES
    return torch.where(
        actions < placement_actions,
        torch.zeros_like(actions),
        1 + (actions == placement_actions + 1).long(),
    )


def mode_logits(output: Any) -> Tensor:
    timing = output.deterministic_timing_logits
    if timing is None or timing.shape[-1] != NUM_HAND_SLOTS + 2:
        raise ValueError("factorized play gate emitted no deterministic timing logits")
    return torch.stack(
        [timing[..., 0], timing[..., NUM_HAND_SLOTS], timing[..., NUM_HAND_SLOTS + 1]],
        dim=-1,
    )


def episode_sequences(episode_ids: np.ndarray) -> list[np.ndarray]:
    sequences: list[np.ndarray] = []
    for episode_id in np.unique(episode_ids):
        rows = np.flatnonzero(episode_ids == episode_id)
        if not len(rows) or np.any(np.diff(rows) != 1):
            raise ValueError("each behavior episode must be nonempty and contiguous")
        sequences.append(rows)
    if not sequences:
        raise ValueError("behavior corpus has no episodes")
    return sequences


def sequence_inputs(
    arrays: dict[str, np.ndarray],
    rows: np.ndarray,
    device: torch.device,
) -> PolicyInputs:
    def tensor(name: str, dtype: torch.dtype | None = None) -> Tensor:
        return torch.as_tensor(
            arrays[name][rows][None], device=device, dtype=dtype
        )

    entity_mask = tensor("entity_mask", torch.bool)
    max_count = int(entity_mask.sum(dim=-1).max().item())
    inputs = PolicyInputs(
        entity_ids=tensor("entity_ids", torch.long)[..., :max_count],
        entity_features=tensor("entity_features", torch.float32)[..., :max_count, :],
        entity_mask=entity_mask[..., :max_count],
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        action_mask=tensor("action_masks", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=tensor("previous_rewards", torch.float32),
        episode_starts=tensor("episode_starts", torch.bool),
        entity_id_confidence=tensor("entity_id_confidence", torch.float32)[
            ..., :max_count
        ],
        entity_feature_confidence=tensor(
            "entity_feature_confidence", torch.float32
        )[
            ..., :max_count, :
        ],
        hand_id_confidence=tensor("hand_id_confidence", torch.float32),
        global_feature_confidence=tensor("global_feature_confidence", torch.float32),
    )
    inputs.episode_starts[0, 0] = bool(arrays["episode_starts"][rows[0]])
    return inputs


def load_corpus(path: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    with np.load(path, allow_pickle=False) as archive:
        if "metadata_json" not in archive.files:
            raise ValueError("behavior corpus has no metadata")
        metadata = json.loads(str(archive["metadata_json"].item()))
        arrays = {
            name: archive[name].copy()
            for name in archive.files
            if name != "metadata_json"
        }
    required = {
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
        "action_masks",
        "previous_actions",
        "previous_rewards",
        "episode_starts",
        "expert_actions",
        "episode_ids",
        "entity_id_confidence",
        "entity_feature_confidence",
        "hand_id_confidence",
        "global_feature_confidence",
    }
    missing = sorted(required.difference(arrays))
    if missing:
        raise ValueError(f"behavior corpus is missing arrays: {missing}")
    return metadata, arrays


def load_model(payload: dict[str, Any], device: torch.device) -> ClasherPolicy:
    config = PolicyConfig.from_dict(payload["model_config"])
    if config.deterministic_hierarchy != "play-gate" or config.play_hazard_enabled:
        raise ValueError("distillation checkpoint is not a hazard-free play gate")
    state = payload["model_state_dict"]
    card_stats = torch.as_tensor(state["actor_encoder.card_stat_features"])
    semantic = state.get("actor_encoder.semantic_card_features")
    if semantic is not None:
        card_stats = torch.cat([card_stats, torch.as_tensor(semantic)], dim=-1)
    model = ClasherPolicy(config, card_stats).to(device)
    model.load_state_dict(state, strict=True)
    return model


def _empty_confusion() -> np.ndarray:
    return np.zeros((3, 3), dtype=np.int64)


def metrics_from_confusion(confusion: np.ndarray) -> dict[str, Any]:
    if confusion.shape != (3, 3):
        raise ValueError("mode confusion must be 3x3")
    support = confusion.sum(axis=1)
    predicted = confusion.sum(axis=0)
    correct = np.diag(confusion)
    recall = np.divide(
        correct,
        support,
        out=np.zeros(3, dtype=np.float64),
        where=support > 0,
    )
    precision = np.divide(
        correct,
        predicted,
        out=np.zeros(3, dtype=np.float64),
        where=predicted > 0,
    )
    play_f1 = (
        0.0
        if precision[0] + recall[0] == 0.0
        else 2.0 * precision[0] * recall[0] / (precision[0] + recall[0])
    )
    return {
        "confusion": confusion.tolist(),
        "rows": int(confusion.sum()),
        "accuracy": float(correct.sum() / max(1, confusion.sum())),
        "play_precision": float(precision[0]),
        "play_recall": float(recall[0]),
        "play_f1": float(play_f1),
        "wait_accuracy": float(recall[1]),
        "ability_accuracy": float(recall[2]),
        "support": {
            "play": int(support[0]),
            "wait": int(support[1]),
            "ability": int(support[2]),
        },
    }


@torch.no_grad()
def evaluate(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    sequences: list[np.ndarray],
    *,
    device: torch.device,
    sequence_length: int,
) -> dict[str, Any]:
    model.eval()
    mode_confusion = _empty_confusion()
    exact_correct = 0
    loss_sum = 0.0
    rows_seen = 0
    for episode in sequences:
        state = model.initial_state(1, device=device)
        for offset in range(0, len(episode), sequence_length):
            chunk = episode[offset : offset + sequence_length]
            inputs = sequence_inputs(arrays, chunk, device)
            output = model(inputs, state)
            state = tuple(value.detach() for value in output.next_state)
            actions = torch.as_tensor(
                arrays["expert_actions"][chunk], dtype=torch.long, device=device
            )
            targets = action_modes(actions)
            logits = mode_logits(output)[0]
            loss_sum += float(F.cross_entropy(logits, targets, reduction="sum"))
            predictions = logits.argmax(dim=-1)
            np.add.at(
                mode_confusion,
                (targets.cpu().numpy(), predictions.cpu().numpy()),
                1,
            )
            predicted_actions = model._deterministic_actions(
                output,
                inputs.action_mask,
            )[0]
            exact_correct += int((predicted_actions == actions).sum())
            rows_seen += len(chunk)
    if rows_seen == 0:
        raise ValueError("evaluation saw no behavior rows")
    result = metrics_from_confusion(mode_confusion)
    result["cross_entropy"] = loss_sum / rows_seen
    result["exact_action_accuracy"] = exact_correct / rows_seen
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--train-corpus", type=Path, required=True)
    parser.add_argument("--validation-corpus", type=Path, required=True)
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--seed", type=int, default=1196001)
    parser.add_argument("--epochs", type=int, default=32)
    parser.add_argument("--sequence-length", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument(
        "--play-weight",
        type=float,
        default=16.0,
        help="bounded rare-play weight selected by the held-out 4/16/32 screen",
    )
    parser.add_argument("--minimum-exact-accuracy", type=float, default=0.85)
    parser.add_argument("--minimum-play-recall", type=float, default=0.60)
    parser.add_argument("--minimum-wait-accuracy", type=float, default=0.90)
    args = parser.parse_args()
    if args.output_checkpoint.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite distillation output")
    if args.epochs < 1 or args.sequence_length < 2 or args.learning_rate <= 0.0:
        raise ValueError("training arguments are invalid")
    if args.play_weight <= 0.0:
        raise ValueError("play weight must be positive")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.set_num_threads(1)
    device = torch.device(args.device)
    payload = torch.load(
        args.initial_checkpoint, map_location=device, weights_only=False
    )
    model = load_model(payload, device)
    train_metadata, train_arrays = load_corpus(args.train_corpus)
    validation_metadata, validation_arrays = load_corpus(args.validation_corpus)
    expected_tokens = tuple(payload["token_names"])
    if tuple(train_metadata["token_names"]) != expected_tokens or tuple(
        validation_metadata["token_names"]
    ) != expected_tokens:
        raise ValueError("behavior corpus vocabulary differs from checkpoint")
    train_sequences = episode_sequences(train_arrays["episode_ids"])
    validation_sequences = episode_sequences(validation_arrays["episode_ids"])

    trainable_names: list[str] = []
    trainable: list[nn.Parameter] = []
    for name, parameter in model.named_parameters():
        enabled = name.startswith("hierarchical_mode_gate.")
        parameter.requires_grad_(enabled)
        if enabled:
            trainable_names.append(name)
            trainable.append(parameter)
    if not trainable:
        raise ValueError("checkpoint has no hierarchical mode gate parameters")
    optimizer = torch.optim.AdamW(
        trainable,
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    class_weights = torch.tensor(
        [args.play_weight, 1.0, 1.0], dtype=torch.float32, device=device
    )
    initial = evaluate(
        model,
        validation_arrays,
        validation_sequences,
        device=device,
        sequence_length=args.sequence_length,
    )
    history: list[dict[str, Any]] = [{"epoch": 0, "validation": initial}]
    best_epoch = 0
    best_metrics = initial
    best_state: dict[str, Tensor] | None = None
    rng = np.random.default_rng(args.seed)

    for epoch in range(1, args.epochs + 1):
        model.train()
        loss_sum = 0.0
        chunks = 0
        gradient_max = 0.0
        started = time.monotonic()
        for position in rng.permutation(len(train_sequences)):
            episode = train_sequences[int(position)]
            state = model.initial_state(1, device=device)
            for offset in range(0, len(episode), args.sequence_length):
                chunk = episode[offset : offset + args.sequence_length]
                inputs = sequence_inputs(train_arrays, chunk, device)
                output = model(inputs, state)
                state = tuple(value.detach() for value in output.next_state)
                actions = torch.as_tensor(
                    train_arrays["expert_actions"][chunk],
                    dtype=torch.long,
                    device=device,
                )
                targets = action_modes(actions)
                loss = F.cross_entropy(
                    mode_logits(output)[0],
                    targets,
                    weight=class_weights,
                )
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError("non-finite mode distillation loss")
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                gradient = nn.utils.clip_grad_norm_(trainable, 1.0)
                if not bool(torch.isfinite(gradient)):
                    raise FloatingPointError("non-finite mode gate gradient")
                optimizer.step()
                loss_sum += float(loss.detach())
                gradient_max = max(gradient_max, float(gradient.detach()))
                chunks += 1
        validation = evaluate(
            model,
            validation_arrays,
            validation_sequences,
            device=device,
            sequence_length=args.sequence_length,
        )
        eligible = bool(
            validation["exact_action_accuracy"] >= args.minimum_exact_accuracy
            and validation["play_recall"] >= args.minimum_play_recall
            and validation["wait_accuracy"] >= args.minimum_wait_accuracy
        )
        row = {
            "epoch": epoch,
            "training": {
                "loss": loss_sum / max(1, chunks),
                "chunks": chunks,
                "gradient_norm_max": gradient_max,
                "seconds": time.monotonic() - started,
            },
            "validation": validation,
            "eligible": eligible,
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        score = (
            validation["exact_action_accuracy"],
            validation["play_f1"],
            -validation["cross_entropy"],
        )
        best_score = (
            best_metrics["exact_action_accuracy"],
            best_metrics["play_f1"],
            -best_metrics["cross_entropy"],
        )
        if eligible and (best_state is None or score > best_score):
            best_epoch = epoch
            best_metrics = validation
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }

    report = {
        "schema": "clasher.hog26.playgate-distillation.v1",
        "initial_checkpoint": str(args.initial_checkpoint.resolve()),
        "initial_checkpoint_sha256": file_sha256(args.initial_checkpoint),
        "train_corpus": str(args.train_corpus.resolve()),
        "train_corpus_sha256": file_sha256(args.train_corpus),
        "validation_corpus": str(args.validation_corpus.resolve()),
        "validation_corpus_sha256": file_sha256(args.validation_corpus),
        "seed": args.seed,
        "epochs": args.epochs,
        "sequence_length": args.sequence_length,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "play_weight": args.play_weight,
        "trainable_parameter_names": trainable_names,
        "trainable_parameter_count": sum(value.numel() for value in trainable),
        "train_episodes": len(train_sequences),
        "validation_episodes": len(validation_sequences),
        "selection_gate": {
            "minimum_exact_accuracy": args.minimum_exact_accuracy,
            "minimum_play_recall": args.minimum_play_recall,
            "minimum_wait_accuracy": args.minimum_wait_accuracy,
        },
        "initial_validation": initial,
        "best_epoch": best_epoch,
        "best_validation": best_metrics,
        "history": history,
        "selected_nonzero_epoch": best_state is not None,
        "output_checkpoint": (
            str(args.output_checkpoint.resolve()) if best_state is not None else None
        ),
    }
    if best_state is not None:
        result = dict(payload)
        result["model_state_dict"] = best_state
        result.pop("optimizer_state_dict", None)
        result["playgate_distillation"] = report
        args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
        torch.save(result, args.output_checkpoint)
        report["output_checkpoint_sha256"] = file_sha256(args.output_checkpoint)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if best_state is None:
        raise SystemExit("no play-gate epoch passed the held-out behavior gate")


if __name__ == "__main__":
    main()
