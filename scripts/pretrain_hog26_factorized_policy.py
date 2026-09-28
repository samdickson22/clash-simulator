#!/usr/bin/env python3
"""Pretrain a fresh factorized Hog policy on trusted recurrent behavior rows."""

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
from numpy.typing import NDArray
from torch import Tensor, nn

from clasher.rl.hierarchical_imitation import (
    PLACEMENT_ACTIONS,
    HierarchicalImitationConfig,
    factor_public_action_mask,
    hierarchical_masked_imitation_loss,
    labels_from_flat_actions,
)
from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs

REPORT_SCHEMA = "clasher.hog26.fresh-factorized-pretrain.v1"
EXCLUDED_PREFIXES = (
    "critic_encoder.",
    "value_head.",
    "opponent_hand_head.",
    "opponent_elixir_head.",
    "action_value_head.",
    "action_value_policy_gate",
)


def load_behavior_corpus(path: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
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
    }
    missing = sorted(required.difference(arrays))
    if missing:
        raise ValueError(f"behavior corpus is missing arrays: {missing}")
    confidence_names = {
        "entity_id_confidence",
        "entity_feature_confidence",
        "hand_id_confidence",
        "global_feature_confidence",
    }
    present = confidence_names.intersection(arrays)
    if present and present != confidence_names:
        raise ValueError("behavior corpus has a partial confidence contract")
    if not present:
        entity_confidence = arrays["entity_mask"].astype(np.float32)
        arrays["entity_id_confidence"] = entity_confidence
        arrays["entity_feature_confidence"] = np.broadcast_to(
            entity_confidence[..., None], arrays["entity_features"].shape
        ).astype(np.float32, copy=True)
        arrays["hand_id_confidence"] = (arrays["hand_ids"] != 0).astype(np.float32)
        arrays["global_feature_confidence"] = np.ones(
            arrays["global_features"].shape, dtype=np.float32
        )
        metadata = {**metadata, "confidence_authority": "exact-simulator-derived"}
    return metadata, arrays


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fixed_sequence_chunks(
    episode_ids: NDArray[np.integer[Any]], sequence_length: int
) -> NDArray[np.int64]:
    if sequence_length < 2:
        raise ValueError("sequence length must be at least two")
    chunks: list[NDArray[np.int64]] = []
    for episode_id in np.unique(episode_ids):
        rows = np.flatnonzero(episode_ids == episode_id).astype(np.int64, copy=False)
        if not len(rows) or bool((np.diff(rows) != 1).any()):
            raise ValueError("each imitation episode must be nonempty and contiguous")
        for start in range(0, len(rows) - sequence_length + 1, sequence_length):
            chunks.append(rows[start : start + sequence_length])
    if not chunks:
        raise ValueError("corpus contains no complete recurrent chunks")
    return np.stack(chunks)


def batch_inputs(
    arrays: dict[str, np.ndarray], rows: NDArray[np.int64], device: torch.device
) -> PolicyInputs:
    def tensor(name: str, dtype: torch.dtype) -> Tensor:
        return torch.as_tensor(arrays[name][rows], dtype=dtype, device=device)

    entity_mask = tensor("entity_mask", torch.bool)
    max_count = int(entity_mask.sum(dim=-1).max())
    return PolicyInputs(
        entity_ids=tensor("entity_ids", torch.long)[..., :max_count],
        entity_features=tensor("entity_features", torch.float32)[..., :max_count, :],
        entity_mask=entity_mask[..., :max_count],
        hand_ids=tensor("hand_ids", torch.long),
        global_features=tensor("global_features", torch.float32),
        action_mask=tensor("action_masks", torch.bool),
        previous_actions=tensor("previous_actions", torch.long),
        previous_rewards=torch.zeros(rows.shape, dtype=torch.float32, device=device),
        episode_starts=tensor("episode_starts", torch.bool),
        entity_id_confidence=tensor("entity_id_confidence", torch.float32)[
            ..., :max_count
        ],
        entity_feature_confidence=tensor("entity_feature_confidence", torch.float32)[
            ..., :max_count, :
        ],
        hand_id_confidence=tensor("hand_id_confidence", torch.float32),
        global_feature_confidence=tensor("global_feature_confidence", torch.float32),
    )


def actor_parameters(model: ClasherPolicy) -> tuple[list[str], list[nn.Parameter]]:
    names: list[str] = []
    parameters: list[nn.Parameter] = []
    for name, parameter in model.named_parameters():
        enabled = not name.startswith(EXCLUDED_PREFIXES)
        parameter.requires_grad_(enabled)
        if enabled:
            names.append(name)
            parameters.append(parameter)
    if not parameters:
        raise ValueError("fresh actor pretraining selected no parameters")
    return names, parameters


def _targets(
    arrays: dict[str, np.ndarray], rows: NDArray[np.int64], device: torch.device
) -> tuple[Tensor, Tensor, Tensor, Tensor]:
    actions = torch.as_tensor(
        arrays["expert_actions"][rows], dtype=torch.long, device=device
    )
    decision = torch.as_tensor(
        arrays["expert_action_supervision_valid"][rows],
        dtype=torch.bool,
        device=device,
    )
    card = torch.as_tensor(
        arrays["expert_card_supervision_valid"][rows],
        dtype=torch.bool,
        device=device,
    )
    tile = torch.as_tensor(
        arrays["expert_tile_supervision_valid"][rows],
        dtype=torch.bool,
        device=device,
    )
    return actions.reshape(-1), decision.reshape(-1), card.reshape(-1), tile.reshape(-1)


def _batch_loss(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    rows: NDArray[np.int64],
    *,
    device: torch.device,
    play_weight: float,
) -> tuple[Tensor, dict[str, float]]:
    inputs = batch_inputs(arrays, rows, device)
    output = model(inputs, model.initial_state(rows.shape[0], device=device))
    actions, decision_trusted, card_trusted, tile_trusted = _targets(
        arrays, rows, device
    )
    flat_mask = inputs.action_mask.reshape(-1, inputs.action_mask.shape[-1])
    masks = factor_public_action_mask(flat_mask)
    labels = labels_from_flat_actions(
        actions,
        decision_trusted=decision_trusted,
        card_trusted=card_trusted,
        tile_trusted=tile_trusted,
    )
    action_type = output.action_type_logits.reshape(-1, 6)
    decision_logits = torch.cat(
        [torch.logsumexp(action_type[:, :4], dim=-1, keepdim=True), action_type[:, 4:]],
        dim=-1,
    )
    decision_weights = torch.where(
        actions < PLACEMENT_ACTIONS,
        torch.full_like(actions, play_weight, dtype=torch.float32),
        torch.ones_like(actions, dtype=torch.float32),
    )
    breakdown = hierarchical_masked_imitation_loss(
        decision_logits,
        action_type[:, :4],
        output.location_logits.reshape(-1, 4, 576),
        masks,
        labels,
        config=HierarchicalImitationConfig(),
        decision_sample_weights=decision_weights,
    )
    with torch.no_grad():
        predicted = model._deterministic_actions(output, inputs.action_mask).reshape(-1)
        trusted = decision_trusted
        exact_correct = int(((predicted == actions) & trusted).sum())
        decision_prediction = decision_logits.masked_fill(
            ~masks.decision, -torch.inf
        ).argmax(dim=-1)
        decision_correct = int(
            (
                (decision_prediction == labels.decision_target)
                & labels.decision_trusted
            ).sum()
        )
        play = labels.decision_trusted & (labels.decision_target == 0)
        wait = labels.decision_trusted & (labels.decision_target == 1)
        play_correct = int(((decision_prediction == 0) & play).sum())
        wait_correct = int(((decision_prediction == 1) & wait).sum())
        card_prediction = (
            action_type[:, :4].masked_fill(~masks.card, -torch.inf).argmax(dim=-1)
        )
        card_correct = int(
            ((card_prediction == labels.card_target) & labels.card_trusted).sum()
        )
        tile_rows = torch.nonzero(labels.tile_trusted, as_tuple=False).flatten()
        if tile_rows.numel():
            tile_cards = labels.card_target.index_select(0, tile_rows)
            local_rows = torch.arange(tile_rows.numel(), device=device)
            selected_tiles = output.location_logits.reshape(-1, 4, 576).index_select(
                0, tile_rows
            )[local_rows, tile_cards]
            selected_mask = masks.tile.index_select(0, tile_rows)[
                local_rows, tile_cards
            ]
            tile_prediction = selected_tiles.masked_fill(
                ~selected_mask, -torch.inf
            ).argmax(dim=-1)
            tile_correct = int(
                (tile_prediction == labels.tile_target.index_select(0, tile_rows)).sum()
            )
        else:
            tile_correct = 0
    return breakdown.total, {
        "decision_loss": float(breakdown.decision.detach()),
        "card_loss": float(breakdown.card.detach()),
        "tile_loss": float(breakdown.tile.detach()),
        "exact_correct": exact_correct,
        "decision_correct": decision_correct,
        "play_correct": play_correct,
        "wait_correct": wait_correct,
        "card_correct": card_correct,
        "tile_correct": tile_correct,
        "exact_rows": int(trusted.sum()),
        "play_rows": int(play.sum()),
        "wait_rows": int(wait.sum()),
        "decision_rows": int(breakdown.decision_count),
        "card_rows": int(breakdown.card_count),
        "tile_rows": int(breakdown.tile_count),
    }


@torch.no_grad()
def evaluate(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    chunks: NDArray[np.int64],
    *,
    device: torch.device,
    batch_sequences: int,
    play_weight: float,
) -> dict[str, float]:
    model.eval()
    losses: dict[str, float] = {
        "loss": 0.0,
        "decision_loss": 0.0,
        "card_loss": 0.0,
        "tile_loss": 0.0,
    }
    counts = {
        name: 0
        for name in (
            "exact_correct",
            "decision_correct",
            "play_correct",
            "wait_correct",
            "card_correct",
            "tile_correct",
            "exact_rows",
            "decision_rows",
            "play_rows",
            "wait_rows",
            "card_rows",
            "tile_rows",
        )
    }
    batches = 0
    for start in range(0, len(chunks), batch_sequences):
        rows = chunks[start : start + batch_sequences]
        loss, metrics = _batch_loss(
            model, arrays, rows, device=device, play_weight=play_weight
        )
        losses["loss"] += float(loss)
        for name in losses.keys() - {"loss"}:
            losses[name] += metrics[name]
        for name in counts:
            counts[name] += int(metrics[name])
        batches += 1
    result = {name: value / max(1, batches) for name, value in losses.items()}
    result.update(
        {
            "exact_action_accuracy": counts["exact_correct"]
            / max(1, counts["exact_rows"]),
            "decision_accuracy": counts["decision_correct"]
            / max(1, counts["decision_rows"]),
            "play_recall": counts["play_correct"] / max(1, counts["play_rows"]),
            "wait_accuracy": counts["wait_correct"] / max(1, counts["wait_rows"]),
            "card_accuracy": counts["card_correct"] / max(1, counts["card_rows"]),
            "tile_accuracy": counts["tile_correct"] / max(1, counts["tile_rows"]),
            **{
                name: float(value)
                for name, value in counts.items()
                if name.endswith("_rows")
            },
        }
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--train-corpus", type=Path, required=True)
    parser.add_argument("--validation-corpus", type=Path, required=True)
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--seed", type=int, default=1241001)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--sequence-length", type=int, default=64)
    parser.add_argument("--batch-sequences", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--play-weight", type=float, default=8.0)
    parser.add_argument("--minimum-decision-accuracy", type=float, default=0.85)
    parser.add_argument("--minimum-play-recall", type=float, default=0.60)
    parser.add_argument("--minimum-wait-accuracy", type=float, default=0.85)
    parser.add_argument("--minimum-card-accuracy", type=float, default=0.90)
    parser.add_argument("--minimum-tile-accuracy", type=float, default=0.20)
    parser.add_argument("--minimum-exact-action-accuracy", type=float, default=0.80)
    args = parser.parse_args()
    if args.output_checkpoint.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite factorized pretraining output")
    if args.epochs < 1 or args.batch_sequences < 1 or args.learning_rate <= 0.0:
        raise ValueError("invalid pretraining settings")
    if args.play_weight <= 0.0:
        raise ValueError("play weight must be positive")
    thresholds = {
        "decision_accuracy": args.minimum_decision_accuracy,
        "play_recall": args.minimum_play_recall,
        "wait_accuracy": args.minimum_wait_accuracy,
        "card_accuracy": args.minimum_card_accuracy,
        "tile_accuracy": args.minimum_tile_accuracy,
        "exact_action_accuracy": args.minimum_exact_action_accuracy,
    }
    if any(not 0.0 <= value <= 1.0 for value in thresholds.values()):
        raise ValueError("pretraining behavior gates must be in [0, 1]")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.set_num_threads(1)
    device = torch.device(args.device)
    payload = torch.load(
        args.initial_checkpoint, map_location=device, weights_only=False
    )
    config = PolicyConfig.from_dict(payload["model_config"])
    if (
        config.deterministic_hierarchy != "play-gate"
        or not config.hierarchical_mode_gate_enabled
        or not config.equivariant_slot_choice
        or config.action_value_head_enabled
    ):
        raise ValueError("initializer is not the fresh factorized control architecture")
    state = payload["model_state_dict"]
    card_stats = torch.as_tensor(state["actor_encoder.card_stat_features"])
    semantic = state.get("actor_encoder.semantic_card_features")
    if semantic is not None:
        card_stats = torch.cat([card_stats, torch.as_tensor(semantic)], dim=-1)
    model = ClasherPolicy(config, card_stats).to(device)
    model.load_state_dict(state, strict=True)
    train_metadata, train_arrays = load_behavior_corpus(args.train_corpus)
    validation_metadata, validation_arrays = load_behavior_corpus(
        args.validation_corpus
    )
    expected_tokens = tuple(payload["token_names"])
    if (
        tuple(train_metadata["token_names"]) != expected_tokens
        or tuple(validation_metadata["token_names"]) != expected_tokens
    ):
        raise ValueError("pretraining corpus vocabulary differs from initializer")
    required = {
        "expert_action_supervision_valid",
        "expert_card_supervision_valid",
        "expert_tile_supervision_valid",
    }
    for name, arrays in (("train", train_arrays), ("validation", validation_arrays)):
        missing = sorted(required.difference(arrays))
        if missing:
            raise ValueError(f"{name} corpus lacks trusted component labels: {missing}")
    train_chunks = fixed_sequence_chunks(
        train_arrays["episode_ids"], args.sequence_length
    )
    validation_chunks = fixed_sequence_chunks(
        validation_arrays["episode_ids"], args.sequence_length
    )
    trainable_names, trainable = actor_parameters(model)
    optimizer = torch.optim.AdamW(
        trainable, lr=args.learning_rate, weight_decay=args.weight_decay
    )
    initial = evaluate(
        model,
        validation_arrays,
        validation_chunks,
        device=device,
        batch_sequences=args.batch_sequences,
        play_weight=args.play_weight,
    )
    history: list[dict[str, Any]] = [{"epoch": 0, "validation": initial}]
    best_state: dict[str, Tensor] | None = None
    best_score = (-1.0, -1.0, -float("inf"))
    best_epoch = 0
    best_validation: dict[str, float] | None = None
    rng = np.random.default_rng(args.seed)
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = rng.permutation(len(train_chunks))
        total_loss = 0.0
        batches = 0
        gradient_max = 0.0
        started = time.monotonic()
        for start in range(0, len(order), args.batch_sequences):
            rows = train_chunks[order[start : start + args.batch_sequences]]
            loss, _metrics = _batch_loss(
                model,
                train_arrays,
                rows,
                device=device,
                play_weight=args.play_weight,
            )
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError(
                    "factorized pretraining loss became non-finite"
                )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            gradient = nn.utils.clip_grad_norm_(trainable, 1.0)
            if not bool(torch.isfinite(gradient)):
                raise FloatingPointError(
                    "factorized pretraining gradient became non-finite"
                )
            optimizer.step()
            total_loss += float(loss.detach())
            gradient_max = max(gradient_max, float(gradient))
            batches += 1
        validation = evaluate(
            model,
            validation_arrays,
            validation_chunks,
            device=device,
            batch_sequences=args.batch_sequences,
            play_weight=args.play_weight,
        )
        row = {
            "epoch": epoch,
            "training": {
                "loss": total_loss / max(1, batches),
                "batches": batches,
                "gradient_norm_max": gradient_max,
                "seconds": time.monotonic() - started,
            },
            "validation": validation,
            "eligible": all(
                validation[name] >= minimum
                for name, minimum in thresholds.items()
            ),
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        score = (
            validation["exact_action_accuracy"],
            validation["tile_accuracy"],
            -validation["loss"],
        )
        if row["eligible"] and score > best_score:
            best_score = score
            best_epoch = epoch
            best_validation = validation
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
    if best_state is None:
        raise SystemExit("no factorized pretraining epoch passed held-out behavior gates")
    assert best_validation is not None
    report = {
        "schema": REPORT_SCHEMA,
        "initial_checkpoint": str(args.initial_checkpoint.resolve()),
        "initial_checkpoint_sha256": file_sha256(args.initial_checkpoint),
        "train_corpus": str(args.train_corpus.resolve()),
        "train_corpus_sha256": file_sha256(args.train_corpus),
        "validation_corpus": str(args.validation_corpus.resolve()),
        "validation_corpus_sha256": file_sha256(args.validation_corpus),
        "seed": args.seed,
        "epochs": args.epochs,
        "sequence_length": args.sequence_length,
        "batch_sequences": args.batch_sequences,
        "learning_rate": args.learning_rate,
        "play_weight": args.play_weight,
        "selection_gates": thresholds,
        "train_chunks": len(train_chunks),
        "validation_chunks": len(validation_chunks),
        "trainable_parameter_count": sum(value.numel() for value in trainable),
        "trainable_parameter_names": trainable_names,
        "initial_validation": initial,
        "best_epoch": best_epoch,
        "best_validation": best_validation,
        "history": history,
        "development_only": True,
        "output_checkpoint": str(args.output_checkpoint.resolve()),
    }
    result = dict(payload)
    result["model_state_dict"] = best_state
    result.pop("optimizer_state_dict", None)
    result["factorized_pretraining"] = report
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, args.output_checkpoint)
    report["output_checkpoint_sha256"] = file_sha256(args.output_checkpoint)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
