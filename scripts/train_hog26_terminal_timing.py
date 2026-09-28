#!/usr/bin/env python3
"""Repair only the retained Hog policy's play-hazard timing head."""

# mypy: disable-error-code="import-untyped,no-any-return"

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as F

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.model import ClasherPolicy, PolicyConfig
from scripts.distill_hog26_playgate import (
    episode_sequences,
    load_corpus,
    sequence_inputs,
)

PLACEMENT_ACTIONS = NUM_HAND_SLOTS * NUM_TILES


@dataclass(frozen=True)
class TimingTable:
    root_rows: np.ndarray
    targets_play: np.ndarray
    parent_play: np.ndarray
    weights: np.ndarray

    @property
    def corrective(self) -> np.ndarray:
        return self.targets_play != self.parent_play


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_timing_table(path: Path) -> TimingTable:
    with np.load(path, allow_pickle=False) as archive:
        required = {
            "terminal_timing_root_rows",
            "terminal_timing_targets_play",
            "terminal_timing_parent_play",
            "terminal_timing_weights",
        }
        missing = sorted(required.difference(archive.files))
        if missing:
            raise ValueError(f"terminal timing corpus is missing arrays: {missing}")
        table = TimingTable(
            root_rows=archive["terminal_timing_root_rows"].copy(),
            targets_play=archive["terminal_timing_targets_play"].copy(),
            parent_play=archive["terminal_timing_parent_play"].copy(),
            weights=archive["terminal_timing_weights"].copy(),
        )
    count = int(table.root_rows.size)
    if any(value.shape != (count,) for value in (
        table.targets_play,
        table.parent_play,
        table.weights,
    )):
        raise ValueError("terminal timing arrays have inconsistent shapes")
    if count == 0 or len(np.unique(table.root_rows)) != count:
        raise ValueError("terminal timing roots must be nonempty and unique")
    if not np.isfinite(table.weights).all() or bool((table.weights <= 0.0).any()):
        raise ValueError("terminal timing weights must be finite and positive")
    return table


def _load_model(payload: dict[str, Any], device: torch.device) -> ClasherPolicy:
    config = PolicyConfig.from_dict(payload["model_config"])
    if not config.play_hazard_enabled or config.deterministic_hierarchy != "hazard":
        raise ValueError("terminal timing repair requires a hazard policy")
    state = payload["model_state_dict"]
    card_stats = torch.as_tensor(state["actor_encoder.card_stat_features"])
    semantic = state.get("actor_encoder.semantic_card_features")
    if semantic is not None:
        card_stats = torch.cat([card_stats, torch.as_tensor(semantic)], dim=-1)
    model = ClasherPolicy(config, card_stats).to(device)
    model.load_state_dict(state, strict=True)
    return model


def _teacher_forced_state(
    model: ClasherPolicy,
    output: Any,
    expert_play: Tensor,
) -> tuple[Tensor, Tensor]:
    if output.play_hazard_logits is None:
        raise ValueError("hazard policy emitted no hazard logits")
    probability = torch.sigmoid(
        output.play_hazard_logits[:, -1]
        - math.log(model.config.play_hazard_positive_weight)
    )
    prior = output.next_state[0][:, -1]
    accumulated = 1.0 - (1.0 - prior) * (1.0 - probability)
    stored = torch.where(expert_play, torch.zeros_like(accumulated), accumulated)
    hidden = output.next_state[0].clone()
    hidden[:, -1] = stored
    return hidden.detach(), output.next_state[1].detach()


@torch.no_grad()
def deterministic_trace(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    sequences: list[np.ndarray],
    *,
    device: torch.device,
) -> np.ndarray:
    model.eval()
    predicted = np.full(arrays["expert_actions"].shape, -1, dtype=np.int64)
    for episode in sequences:
        state = model.initial_state(1, device=device)
        for row in episode.tolist():
            inputs = sequence_inputs(arrays, np.asarray([row]), device)
            actions, _log_prob, _values, state, _output = model.act(
                inputs, state, deterministic=True
            )
            predicted[row] = int(actions[0, 0].item())
    if bool((predicted < 0).any()):
        raise RuntimeError("deterministic timing trace missed corpus rows")
    return predicted


def timing_metrics(
    predicted_actions: np.ndarray,
    expert_actions: np.ndarray,
    table: TimingTable,
) -> dict[str, Any]:
    predicted_play = predicted_actions[table.root_rows] < PLACEMENT_ACTIONS
    timing_correct = predicted_play == table.targets_play
    corrective = table.corrective
    safety = ~corrective
    timing_rows = np.zeros(expert_actions.shape, dtype=np.bool_)
    timing_rows[table.root_rows] = True
    nonroot = ~timing_rows

    def accuracy(values: np.ndarray) -> float:
        return float(values.mean()) if values.size else 0.0

    return {
        "rows": int(expert_actions.size),
        "exact_action_accuracy": accuracy(predicted_actions == expert_actions),
        "nonroot_rows": int(nonroot.sum()),
        "nonroot_exact_action_accuracy": accuracy(
            (predicted_actions == expert_actions)[nonroot]
        ),
        "timing_roots": int(table.root_rows.size),
        "timing_accuracy": accuracy(timing_correct),
        "corrective_roots": int(corrective.sum()),
        "corrective_accuracy": accuracy(timing_correct[corrective]),
        "safety_roots": int(safety.sum()),
        "safety_accuracy": accuracy(timing_correct[safety]),
        "predicted_play_rate": float(predicted_play.mean()),
        "target_play_rate": float(table.targets_play.mean()),
    }


def evaluate(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    sequences: list[np.ndarray],
    table: TimingTable,
    *,
    device: torch.device,
) -> dict[str, Any]:
    return timing_metrics(
        deterministic_trace(model, arrays, sequences, device=device),
        arrays["expert_actions"],
        table,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--train-corpus", type=Path, required=True)
    parser.add_argument("--validation-corpus", type=Path, required=True)
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--seed", type=int, default=1233001)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--behavior-coef", type=float, default=1.0)
    parser.add_argument("--terminal-timing-coef", type=float, default=0.5)
    parser.add_argument("--root-behavior-weight", type=float, default=0.25)
    parser.add_argument("--maximum-nonroot-exact-regression", type=float, default=0.01)
    parser.add_argument("--maximum-safety-regression", type=float, default=0.01)
    parser.add_argument("--minimum-corrective-improvement", type=float, default=0.25)
    args = parser.parse_args()
    if args.output_checkpoint.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite terminal timing output")
    if args.epochs < 1 or args.learning_rate <= 0.0:
        raise ValueError("terminal timing training arguments are invalid")
    if args.behavior_coef < 0.0 or args.terminal_timing_coef <= 0.0:
        raise ValueError("terminal timing coefficients are invalid")
    if not 0.0 <= args.root_behavior_weight <= 1.0:
        raise ValueError("root behavior weight must be in [0, 1]")

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.set_num_threads(1)
    device = torch.device(args.device)
    payload = torch.load(args.initial_checkpoint, map_location=device, weights_only=False)
    model = _load_model(payload, device)
    train_metadata, train_arrays = load_corpus(args.train_corpus)
    validation_metadata, validation_arrays = load_corpus(args.validation_corpus)
    expected_tokens = tuple(payload["token_names"])
    if tuple(train_metadata["token_names"]) != expected_tokens or tuple(
        validation_metadata["token_names"]
    ) != expected_tokens:
        raise ValueError("terminal timing corpus vocabulary differs from checkpoint")
    train_sequences = episode_sequences(train_arrays["episode_ids"])
    validation_sequences = episode_sequences(validation_arrays["episode_ids"])
    train_table = load_timing_table(args.train_corpus)
    validation_table = load_timing_table(args.validation_corpus)

    trainable_names: list[str] = []
    trainable: list[nn.Parameter] = []
    for name, parameter in model.named_parameters():
        enabled = name.startswith("play_hazard_head.")
        parameter.requires_grad_(enabled)
        if enabled:
            trainable_names.append(name)
            trainable.append(parameter)
    if not trainable:
        raise ValueError("checkpoint has no play-hazard head parameters")
    optimizer = torch.optim.AdamW(
        trainable, lr=args.learning_rate, weight_decay=args.weight_decay
    )
    positive_weight = torch.tensor(
        model.config.play_hazard_positive_weight,
        dtype=torch.float32,
        device=device,
    )
    train_timing_by_row = {
        int(row): (bool(target), float(weight))
        for row, target, weight in zip(
            train_table.root_rows.tolist(),
            train_table.targets_play.tolist(),
            train_table.weights.tolist(),
            strict=True,
        )
    }

    initial = evaluate(
        model,
        validation_arrays,
        validation_sequences,
        validation_table,
        device=device,
    )
    history: list[dict[str, Any]] = [{"epoch": 0, "validation": initial}]
    best_epoch = 0
    best_metrics = initial
    best_state: dict[str, Tensor] | None = None
    rng = np.random.default_rng(args.seed)

    for epoch in range(1, args.epochs + 1):
        model.train()
        totals = {"loss": 0.0, "behavior": 0.0, "terminal_timing": 0.0}
        steps = 0
        gradient_max = 0.0
        started = time.monotonic()
        for position in rng.permutation(len(train_sequences)):
            episode = train_sequences[int(position)]
            state = model.initial_state(1, device=device)
            for row in episode.tolist():
                inputs = sequence_inputs(train_arrays, np.asarray([row]), device)
                output = model(inputs, state)
                if output.play_hazard_logits is None:
                    raise ValueError("hazard policy emitted no hazard logits")
                raw_logit = output.play_hazard_logits[0, 0]
                expert_action = int(train_arrays["expert_actions"][row])
                expert_play = torch.tensor(
                    expert_action < PLACEMENT_ACTIONS,
                    dtype=torch.bool,
                    device=device,
                )
                behavior = F.binary_cross_entropy_with_logits(
                    raw_logit.reshape(1),
                    expert_play.to(torch.float32).reshape(1),
                    pos_weight=positive_weight,
                )
                timing = raw_logit * 0.0
                behavior_weight = 1.0
                terminal_target = train_timing_by_row.get(row)
                if terminal_target is not None:
                    target_play, terminal_weight = terminal_target
                    target = torch.tensor(
                        target_play, dtype=torch.float32, device=device
                    )
                    timing = terminal_weight * F.binary_cross_entropy_with_logits(
                        raw_logit.reshape(1),
                        target.reshape(1),
                        pos_weight=positive_weight,
                    )
                    behavior_weight = args.root_behavior_weight
                loss = (
                    args.behavior_coef * behavior_weight * behavior
                    + args.terminal_timing_coef * timing
                )
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError("non-finite terminal timing loss")
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                gradient = nn.utils.clip_grad_norm_(trainable, 1.0)
                if not bool(torch.isfinite(gradient)):
                    raise FloatingPointError("non-finite terminal timing gradient")
                optimizer.step()
                totals["loss"] += float(loss.detach())
                totals["behavior"] += float(behavior.detach())
                totals["terminal_timing"] += float(timing.detach())
                gradient_max = max(gradient_max, float(gradient.detach()))
                steps += 1
                state = _teacher_forced_state(model, output, expert_play.reshape(1))

        validation = evaluate(
            model,
            validation_arrays,
            validation_sequences,
            validation_table,
            device=device,
        )
        eligible = bool(
            validation["nonroot_exact_action_accuracy"]
            >= initial["nonroot_exact_action_accuracy"]
            - args.maximum_nonroot_exact_regression
            and validation["safety_accuracy"]
            >= initial["safety_accuracy"] - args.maximum_safety_regression
            and validation["corrective_accuracy"]
            >= initial["corrective_accuracy"] + args.minimum_corrective_improvement
        )
        row = {
            "epoch": epoch,
            "training": {
                **{key: value / max(1, steps) for key, value in totals.items()},
                "steps": steps,
                "gradient_norm_max": gradient_max,
                "seconds": time.monotonic() - started,
            },
            "validation": validation,
            "eligible": eligible,
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        score = (
            validation["corrective_accuracy"],
            validation["safety_accuracy"],
            validation["nonroot_exact_action_accuracy"],
        )
        best_score = (
            best_metrics["corrective_accuracy"],
            best_metrics["safety_accuracy"],
            best_metrics["nonroot_exact_action_accuracy"],
        )
        if eligible and (best_state is None or score > best_score):
            best_epoch = epoch
            best_metrics = validation
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }

    report = {
        "schema": "clasher.hog26.terminal-timing-repair.v1",
        "initial_checkpoint": str(args.initial_checkpoint.resolve()),
        "initial_checkpoint_sha256": file_sha256(args.initial_checkpoint),
        "train_corpus": str(args.train_corpus.resolve()),
        "train_corpus_sha256": file_sha256(args.train_corpus),
        "validation_corpus": str(args.validation_corpus.resolve()),
        "validation_corpus_sha256": file_sha256(args.validation_corpus),
        "seed": args.seed,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "behavior_coef": args.behavior_coef,
        "terminal_timing_coef": args.terminal_timing_coef,
        "root_behavior_weight": args.root_behavior_weight,
        "trainable_parameter_names": trainable_names,
        "trainable_parameter_count": sum(value.numel() for value in trainable),
        "train_timing_roots": int(train_table.root_rows.size),
        "validation_timing_roots": int(validation_table.root_rows.size),
        "selection_gate": {
            "maximum_nonroot_exact_regression": args.maximum_nonroot_exact_regression,
            "maximum_safety_regression": args.maximum_safety_regression,
            "minimum_corrective_improvement": args.minimum_corrective_improvement,
        },
        "initial_validation": initial,
        "best_epoch": best_epoch,
        "best_validation": best_metrics,
        "history": history,
        "selected_nonzero_epoch": best_state is not None,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    if best_state is None:
        report["output_checkpoint"] = None
        report["output_checkpoint_sha256"] = None
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        raise SystemExit("no terminal timing epoch passed held-out gates")

    model.load_state_dict(best_state, strict=True)
    result = dict(payload)
    result["model_state_dict"] = model.state_dict()
    result["terminal_timing_repair"] = report
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, args.output_checkpoint)
    report["output_checkpoint"] = str(args.output_checkpoint.resolve())
    report["output_checkpoint_sha256"] = file_sha256(args.output_checkpoint)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
