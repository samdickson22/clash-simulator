#!/usr/bin/env python3
"""Screen a small causal public-memory head for terminal tower margin."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor
from torch.nn import functional as F
from torch.nn.utils.rnn import pad_sequence

from clasher.rl.direct_simple_behavior import (
    DirectSimpleBehaviorCorpus,
    load_direct_simple_behavior_corpus,
)
from clasher.rl.temporal_margin import ActorTemporalMarginHead
from scripts.pretrain_hog26_direct_simple_behavior import load_model
from scripts.train_hog26_actor_outcome import (
    _atomic_checkpoint,
    _atomic_json,
    episode_balanced_row_weights,
    extract_actor_features,
    file_sha256,
    phase_balanced_row_indices,
    validate_outcome_corpus,
)

SCHEMA = "clasher.hog26.temporal-margin-screen.v1"


def episode_slices(
    loaded: list[tuple[dict[str, Any], DirectSimpleBehaviorCorpus]],
) -> list[slice]:
    result: list[slice] = []
    cursor = 0
    for _metadata, corpus in loaded:
        for begin, end in zip(
            corpus.episode_offsets[:-1], corpus.episode_offsets[1:], strict=True
        ):
            result.append(slice(cursor + int(begin), cursor + int(end)))
        cursor += corpus.row_count
    return result


def extract_group(
    model: torch.nn.Module,
    loaded: list[tuple[dict[str, Any], DirectSimpleBehaviorCorpus]],
    *,
    device: torch.device,
    sequence_steps: int,
) -> tuple[Tensor, Tensor, list[slice]]:
    features = torch.cat(
        [
            extract_actor_features(
                model,  # type: ignore[arg-type]
                corpus,
                device=device,
                sequence_steps=sequence_steps,
                feature_set="structured-summary",
            )
            for _metadata, corpus in loaded
        ]
    )
    margins = torch.cat(
        [
            torch.as_tensor(corpus.arrays["terminal_tower_margins"])
            for _metadata, corpus in loaded
        ]
    ).to(torch.float32)
    return features, margins, episode_slices(loaded)


def public_current_margin(features: Tensor) -> Tensor:
    public = features[..., -18:]
    return (public[..., 8:11].sum(-1) - public[..., 11:14].sum(-1)) / 3.0


@torch.no_grad()
def predict_sequences(
    head: ActorTemporalMarginHead,
    features: Tensor,
    episodes: list[slice],
    *,
    device: torch.device,
) -> Tensor:
    head.eval()
    predictions = []
    for rows in episodes:
        prediction, _memory = head(features[rows].unsqueeze(0).to(device))
        predictions.append(prediction[0].cpu())
    return torch.cat(predictions)


def margin_metrics(
    prediction: Tensor,
    target: Tensor,
    features: Tensor,
    loaded: list[tuple[dict[str, Any], DirectSimpleBehaviorCorpus]],
) -> dict[str, Any]:
    rows = phase_balanced_row_indices(loaded)
    selected_prediction = prediction.index_select(0, rows)
    selected_target = target.index_select(0, rows)
    selected_current = public_current_margin(features).index_select(0, rows)
    progress = features[:, -18].index_select(0, rows)

    def summarize(mask: Tensor) -> dict[str, float | int]:
        predicted_mae = float(
            (selected_prediction[mask] - selected_target[mask]).abs().mean()
        )
        baseline_mae = float(
            (selected_current[mask] - selected_target[mask]).abs().mean()
        )
        return {
            "rows": int(mask.sum()),
            "tower_margin_mae": predicted_mae,
            "tower_margin_baseline_mae": baseline_mae,
            "tower_margin_mae_improvement": baseline_mae - predicted_mae,
        }

    by_phase = {}
    for phase, low, high in (
        ("early", 0.0, 1 / 3),
        ("middle", 1 / 3, 2 / 3),
        ("late", 2 / 3, 1.01),
    ):
        by_phase[phase] = summarize((progress >= low) & (progress < high))
    return {
        "phase_balanced": summarize(torch.ones_like(progress, dtype=torch.bool)),
        "phase_balanced_by_phase": by_phase,
    }


def selection_key(metrics: dict[str, Any]) -> tuple[int, float, float]:
    overall = metrics["phase_balanced"]
    phases = metrics["phase_balanced_by_phase"]
    passed = bool(
        float(overall["tower_margin_mae_improvement"]) >= 0.005
        and all(
            float(values["tower_margin_mae_improvement"]) >= -0.01
            for values in phases.values()
        )
    )
    return (
        int(passed),
        float(overall["tower_margin_mae_improvement"]),
        -float(overall["tower_margin_mae"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-checkpoint", type=Path, required=True)
    parser.add_argument("--train-corpus", type=Path, action="append", required=True)
    parser.add_argument(
        "--validation-corpus", type=Path, action="append", required=True
    )
    parser.add_argument("--diagnostic-corpus", type=Path, action="append", required=True)
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--episode-batch-size", type=int, default=24)
    parser.add_argument("--sequence-steps", type=int, default=128)
    parser.add_argument("--projection-size", type=int, default=32)
    parser.add_argument("--memory-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--residual-scale", type=float, default=0.5)
    parser.add_argument("--progress-power", type=float, default=6.0)
    args = parser.parse_args()
    if args.report.exists() or args.output_checkpoint.exists():
        raise SystemExit("refusing to overwrite temporal margin artifacts")
    if min(
        args.epochs,
        args.episode_batch_size,
        args.sequence_steps,
        args.projection_size,
        args.memory_size,
    ) < 1:
        raise ValueError("temporal margin training sizes must be positive")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device(args.device)
    base_payload, base_model = load_model(args.base_checkpoint, device)

    def load(paths: list[Path]) -> list[tuple[dict[str, Any], DirectSimpleBehaviorCorpus]]:
        result = [load_direct_simple_behavior_corpus(path) for path in paths]
        for metadata, corpus in result:
            validate_outcome_corpus(metadata, corpus)
            if metadata.get("checkpoint_sha256") != file_sha256(args.base_checkpoint):
                raise ValueError("temporal margin corpus belongs to another policy")
        return result

    train_loaded = load(args.train_corpus)
    validation_loaded = load(args.validation_corpus)
    diagnostic_loaded = load(args.diagnostic_corpus)
    path_groups = (args.train_corpus, args.validation_corpus, args.diagnostic_corpus)
    hash_groups = [{file_sha256(path) for path in paths} for paths in path_groups]
    if any(hash_groups[left] & hash_groups[right] for left, right in ((0, 1), (0, 2), (1, 2))):
        raise ValueError("temporal margin corpus groups must be physically disjoint")

    started = time.monotonic()
    train_features, train_margins, train_episodes = extract_group(
        base_model, train_loaded, device=device, sequence_steps=args.sequence_steps
    )
    validation_features, validation_margins, validation_episodes = extract_group(
        base_model, validation_loaded, device=device, sequence_steps=args.sequence_steps
    )
    diagnostic_features, diagnostic_margins, diagnostic_episodes = extract_group(
        base_model, diagnostic_loaded, device=device, sequence_steps=args.sequence_steps
    )
    head = ActorTemporalMarginHead(
        int(train_features.shape[-1]),
        projection_size=args.projection_size,
        memory_size=args.memory_size,
        residual_scale=args.residual_scale,
        progress_power=args.progress_power,
    ).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    weights = episode_balanced_row_weights(train_loaded, phase_balanced=True)
    generator = np.random.default_rng(args.seed)

    initial_prediction = predict_sequences(
        head, validation_features, validation_episodes, device=device
    )
    initial_metrics = margin_metrics(
        initial_prediction, validation_margins, validation_features, validation_loaded
    )
    history = [{"epoch": 0, "training_loss": None, "validation": initial_metrics}]
    best_epoch = 0
    best_metrics = initial_metrics
    best_key = selection_key(initial_metrics)
    best_state = {name: value.detach().cpu().clone() for name, value in head.state_dict().items()}

    for epoch in range(1, args.epochs + 1):
        head.train()
        order = generator.permutation(len(train_episodes))
        losses = []
        for start in range(0, len(order), args.episode_batch_size):
            selected = [train_episodes[int(index)] for index in order[start : start + args.episode_batch_size]]
            feature_batch = pad_sequence(
                [train_features[rows] for rows in selected], batch_first=True
            ).to(device)
            target_batch = pad_sequence(
                [train_margins[rows] for rows in selected], batch_first=True
            ).to(device)
            weight_batch = pad_sequence(
                [weights[rows] for rows in selected], batch_first=True
            ).to(device)
            prediction, _memory = head(feature_batch)
            row_loss = F.smooth_l1_loss(prediction, target_batch, reduction="none")
            loss = (row_loss * weight_batch).sum() / weight_batch.sum()
            if not bool(torch.isfinite(loss)):
                raise RuntimeError("temporal margin loss became non-finite")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach()))
        validation_prediction = predict_sequences(
            head, validation_features, validation_episodes, device=device
        )
        validation = margin_metrics(
            validation_prediction,
            validation_margins,
            validation_features,
            validation_loaded,
        )
        row = {
            "epoch": epoch,
            "training_loss": float(np.mean(losses)),
            "validation": validation,
        }
        history.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        key = selection_key(validation)
        if key > best_key:
            best_key = key
            best_epoch = epoch
            best_metrics = validation
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in head.state_dict().items()
            }

    head.load_state_dict(best_state)
    diagnostic_prediction = predict_sequences(
        head, diagnostic_features, diagnostic_episodes, device=device
    )
    diagnostic_metrics = margin_metrics(
        diagnostic_prediction,
        diagnostic_margins,
        diagnostic_features,
        diagnostic_loaded,
    )
    report = {
        "schema": SCHEMA,
        "status": "diagnostic-only",
        "opened_diagnostic_not_promotion_evidence": True,
        "base_checkpoint": str(args.base_checkpoint.resolve()),
        "base_checkpoint_sha256": file_sha256(args.base_checkpoint),
        "train_corpora": [str(path.resolve()) for path in args.train_corpus],
        "train_corpus_sha256": [file_sha256(path) for path in args.train_corpus],
        "validation_corpora": [str(path.resolve()) for path in args.validation_corpus],
        "validation_corpus_sha256": [file_sha256(path) for path in args.validation_corpus],
        "diagnostic_corpora": [str(path.resolve()) for path in args.diagnostic_corpus],
        "diagnostic_corpus_sha256": [file_sha256(path) for path in args.diagnostic_corpus],
        "seed": args.seed,
        "device": str(device),
        "input_size": head.input_size,
        "projection_size": head.projection_size,
        "memory_size": head.memory_size,
        "residual_scale": head.residual_scale,
        "progress_power": head.progress_power,
        "trainable_parameters": sum(parameter.numel() for parameter in head.parameters()),
        "best_epoch": best_epoch,
        "best_validation": best_metrics,
        "opened_diagnostic": diagnostic_metrics,
        "selection_used_opened_diagnostic": False,
        "history": history,
        "elapsed_seconds": time.monotonic() - started,
    }
    _atomic_json(args.report, report)
    _atomic_checkpoint(
        args.output_checkpoint,
        {
            "schema": SCHEMA,
            "base_model_config": base_payload["model_config"],
            "model_config": {
                "input_size": head.input_size,
                "projection_size": head.projection_size,
                "memory_size": head.memory_size,
                "residual_scale": head.residual_scale,
                "progress_power": head.progress_power,
            },
            "state_dict": best_state,
            "report": report,
        },
    )
    print(json.dumps({"best_epoch": best_epoch, "diagnostic": diagnostic_metrics}))


if __name__ == "__main__":
    main()
