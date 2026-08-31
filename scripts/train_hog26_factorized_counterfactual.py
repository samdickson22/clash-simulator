#!/usr/bin/env python3
"""Train factorized Hog play/card/tile heads on value-ranked root actions."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
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
    action_modes,
    episode_sequences,
    load_corpus,
    metrics_from_confusion,
    mode_logits,
    sequence_inputs,
)

DEFAULT_TRAINABLE_PREFIXES = (
    "hierarchical_mode_gate.",
    "action_type_head.",
    "semantic_slot_choice_query.",
    "mechanics_slot_choice_query.",
    "card_query.",
    "tile_decoder.",
    "tile_key.",
    "location_bias.",
)
ROOT_POLICY_INPUT_KEYS = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
    "action_masks",
    "previous_actions",
    "previous_rewards",
    "episode_starts",
)


@dataclass(frozen=True)
class PreferenceTable:
    root_rows: np.ndarray
    positive_actions: np.ndarray
    negative_actions: np.ndarray
    weights: np.ndarray
    corrective: np.ndarray

    @property
    def count(self) -> int:
        return int(self.root_rows.size)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def root_policy_input_fingerprints(
    arrays: dict[str, np.ndarray], root_rows: np.ndarray
) -> set[str]:
    missing = sorted(set(ROOT_POLICY_INPUT_KEYS).difference(arrays))
    if missing:
        raise ValueError(f"corpus is missing policy-input arrays: {missing}")
    rows = np.unique(np.asarray(root_rows, dtype=np.int64))
    row_count = int(arrays[ROOT_POLICY_INPUT_KEYS[0]].shape[0])
    if bool(((rows < 0) | (rows >= row_count)).any()):
        raise ValueError("counterfactual root row is outside the corpus")
    fingerprints: set[str] = set()
    for row in rows.tolist():
        digest = hashlib.sha256()
        for key in ROOT_POLICY_INPUT_KEYS:
            value = np.ascontiguousarray(arrays[key][row])
            digest.update(key.encode())
            digest.update(value.dtype.str.encode())
            digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
            digest.update(value.tobytes())
        fingerprints.add(digest.hexdigest())
    return fingerprints


def load_preferences(
    path: Path,
    *,
    preserve_behavior_gate: bool = False,
) -> PreferenceTable:
    with np.load(path, allow_pickle=False) as archive:
        required = {
            "counterfactual_root_rows",
            "root_base_actions",
            "root_candidate_actions",
            "root_candidate_valid",
            "root_candidate_scores",
            "root_candidate_outcomes",
        }
        missing = sorted(required.difference(archive.files))
        if missing:
            raise ValueError(f"counterfactual corpus is missing arrays: {missing}")
        root_rows = archive["counterfactual_root_rows"].copy()
        base_actions = archive["root_base_actions"].copy()
        candidates = archive["root_candidate_actions"].copy()
        valid = archive["root_candidate_valid"].copy()
        scores = archive["root_candidate_scores"].copy()
        outcomes = archive["root_candidate_outcomes"].copy()
    if (
        candidates.shape != valid.shape
        or candidates.shape != scores.shape
        or candidates.shape != outcomes.shape
    ):
        raise ValueError("counterfactual candidate arrays have inconsistent shapes")
    if root_rows.shape != base_actions.shape or len(root_rows) != len(candidates):
        raise ValueError("counterfactual root table has inconsistent shapes")

    rows_out: list[int] = []
    positive: list[int] = []
    negative: list[int] = []
    weights: list[float] = []
    corrective: list[bool] = []
    for root_index, root_row in enumerate(root_rows.tolist()):
        selected = np.flatnonzero(valid[root_index])
        base_matches = selected[candidates[root_index, selected] == base_actions[root_index]]
        if base_matches.size != 1:
            raise ValueError("each counterfactual root must contain its base action once")
        base_index = int(base_matches[0])
        base_score = float(scores[root_index, base_index])
        base_outcome = int(outcomes[root_index, base_index])
        for candidate_index in selected.tolist():
            action = int(candidates[root_index, candidate_index])
            if action == int(base_actions[root_index]):
                continue
            if preserve_behavior_gate and (
                (action < NUM_HAND_SLOTS * NUM_TILES)
                != (int(base_actions[root_index]) < NUM_HAND_SLOTS * NUM_TILES)
            ):
                continue
            gap = float(scores[root_index, candidate_index]) - base_score
            outcome_gap = int(outcomes[root_index, candidate_index]) - base_outcome
            if outcome_gap == 0 and gap == 0.0:
                continue
            candidate_better = outcome_gap > 0 or (outcome_gap == 0 and gap > 0.0)
            rows_out.append(int(root_row))
            positive.append(action if candidate_better else int(base_actions[root_index]))
            negative.append(int(base_actions[root_index]) if candidate_better else action)
            weights.append(
                4.0 if outcome_gap != 0 else 1.0 + min(3.0, abs(gap) * 10.0)
            )
            corrective.append(candidate_better)
    if not rows_out:
        raise ValueError("counterfactual corpus produces no strict preferences")
    return PreferenceTable(
        root_rows=np.asarray(rows_out, dtype=np.int64),
        positive_actions=np.asarray(positive, dtype=np.int64),
        negative_actions=np.asarray(negative, dtype=np.int64),
        weights=np.asarray(weights, dtype=np.float32),
        corrective=np.asarray(corrective, dtype=np.bool_),
    )


def preference_metrics(margins: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    selected = margins[mask]
    return {
        "pairs": int(mask.sum()),
        "accuracy": float((selected > 0.0).mean()) if len(selected) else 0.0,
        "mean_margin": float(selected.mean()) if len(selected) else 0.0,
    }


def chunk_preferences(
    table: PreferenceTable,
    *,
    start: int,
    stop: int,
    device: torch.device,
) -> tuple[Tensor, Tensor, Tensor, Tensor]:
    selected = np.flatnonzero((table.root_rows >= start) & (table.root_rows < stop))
    return (
        torch.as_tensor(table.root_rows[selected] - start, dtype=torch.long, device=device),
        torch.as_tensor(table.positive_actions[selected], dtype=torch.long, device=device),
        torch.as_tensor(table.negative_actions[selected], dtype=torch.long, device=device),
        torch.as_tensor(table.weights[selected], dtype=torch.float32, device=device),
    )


@torch.no_grad()
def evaluate(
    model: Any,
    arrays: dict[str, np.ndarray],
    sequences: list[np.ndarray],
    preferences: PreferenceTable,
    *,
    device: torch.device,
    sequence_length: int,
    preserve_behavior_gate: bool = False,
) -> dict[str, Any]:
    model.eval()
    confusion = np.zeros((3, 3), dtype=np.int64)
    exact_correct = 0
    non_root_exact_correct = 0
    non_root_rows = 0
    nll_sum = 0.0
    rows_seen = 0
    all_margins: list[np.ndarray] = []
    all_corrective: list[np.ndarray] = []
    intervention_root_rows = np.unique(preferences.root_rows)
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
            logits = output.joint_logits[0]
            nll_sum += float(F.cross_entropy(logits, actions, reduction="sum"))
            force_play = (
                (actions < NUM_HAND_SLOTS * NUM_TILES).unsqueeze(0)
                if preserve_behavior_gate
                else None
            )
            predicted_actions = model._deterministic_actions(
                output,
                inputs.action_mask,
                force_play=force_play,
            )[0]
            exact_correct += int((predicted_actions == actions).sum())
            intervention_rows = torch.as_tensor(
                np.isin(chunk, intervention_root_rows),
                dtype=torch.bool,
                device=device,
            )
            preserved = ~intervention_rows
            non_root_exact_correct += int(
                ((predicted_actions == actions) & preserved).sum()
            )
            non_root_rows += int(preserved.sum())
            targets = action_modes(actions)
            predictions = (
                action_modes(predicted_actions)
                if preserve_behavior_gate
                else mode_logits(output)[0].argmax(dim=-1)
            )
            np.add.at(confusion, (targets.cpu().numpy(), predictions.cpu().numpy()), 1)
            selected = np.flatnonzero(
                (preferences.root_rows >= int(chunk[0]))
                & (preferences.root_rows <= int(chunk[-1]))
            )
            if len(selected):
                local = torch.as_tensor(
                    preferences.root_rows[selected] - int(chunk[0]),
                    dtype=torch.long,
                    device=device,
                )
                positive = torch.as_tensor(
                    preferences.positive_actions[selected], dtype=torch.long, device=device
                )
                negative = torch.as_tensor(
                    preferences.negative_actions[selected], dtype=torch.long, device=device
                )
                margins = logits[local, positive] - logits[local, negative]
                all_margins.append(margins.float().cpu().numpy())
                all_corrective.append(preferences.corrective[selected])
            rows_seen += len(chunk)
    if not all_margins or rows_seen == 0:
        raise ValueError("evaluation did not cover behavior and preference rows")
    margins = np.concatenate(all_margins)
    corrective = np.concatenate(all_corrective)
    behavior = metrics_from_confusion(confusion)
    behavior["nll"] = nll_sum / rows_seen
    behavior["exact_action_accuracy"] = exact_correct / rows_seen
    behavior["non_root_exact_action_accuracy"] = (
        non_root_exact_correct / max(1, non_root_rows)
    )
    behavior["non_root_rows"] = non_root_rows
    return {
        "behavior": behavior,
        "preferences": {
            "overall": preference_metrics(margins, np.ones(len(margins), dtype=np.bool_)),
            "corrective": preference_metrics(margins, corrective),
            "safety": preference_metrics(margins, ~corrective),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--train-corpus", type=Path, required=True)
    parser.add_argument("--validation-corpus", type=Path, required=True)
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--seed", type=int, default=1197001)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--sequence-length", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--behavior-coef", type=float, default=1.0)
    parser.add_argument("--counterfactual-coef", type=float, default=0.2)
    parser.add_argument("--root-behavior-weight", type=float, default=0.25)
    parser.add_argument("--maximum-exact-regression", type=float, default=0.01)
    parser.add_argument("--maximum-safety-regression", type=float, default=0.01)
    parser.add_argument("--minimum-corrective-improvement", type=float, default=0.05)
    parser.add_argument("--trainable-prefix", action="append", default=[])
    parser.add_argument(
        "--preserve-behavior-gate",
        action="store_true",
        help=(
            "keep the source hazard play/wait gate fixed and train only "
            "same-mode complete-action preferences"
        ),
    )
    args = parser.parse_args()
    if args.output_checkpoint.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite factorized repair output")
    if args.epochs < 1 or args.sequence_length < 2 or args.learning_rate <= 0.0:
        raise ValueError("training arguments are invalid")
    if args.behavior_coef < 0.0 or args.counterfactual_coef <= 0.0:
        raise ValueError("loss coefficients are invalid")
    if not 0.0 <= args.root_behavior_weight <= 1.0:
        raise ValueError("root behavior weight must be in [0, 1]")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.set_num_threads(1)
    device = torch.device(args.device)
    payload = torch.load(args.initial_checkpoint, map_location=device, weights_only=False)
    config = PolicyConfig.from_dict(payload["model_config"])
    if args.preserve_behavior_gate:
        if not config.play_hazard_enabled:
            raise ValueError("behavior-gate preservation requires a hazard policy")
    elif config.deterministic_hierarchy != "play-gate" or config.play_hazard_enabled:
        raise ValueError("factorized repair requires a hazard-free play gate")
    state = payload["model_state_dict"]
    card_stats = torch.as_tensor(state["actor_encoder.card_stat_features"])
    semantic = state.get("actor_encoder.semantic_card_features")
    if semantic is not None:
        card_stats = torch.cat([card_stats, torch.as_tensor(semantic)], dim=-1)
    model = ClasherPolicy(config, card_stats).to(device)
    model.load_state_dict(state, strict=True)
    train_metadata, train_arrays = load_corpus(args.train_corpus)
    validation_metadata, validation_arrays = load_corpus(args.validation_corpus)
    expected_tokens = tuple(payload["token_names"])
    if tuple(train_metadata["token_names"]) != expected_tokens or tuple(
        validation_metadata["token_names"]
    ) != expected_tokens:
        raise ValueError("counterfactual corpus vocabulary differs from checkpoint")
    train_sequences = episode_sequences(train_arrays["episode_ids"])
    validation_sequences = episode_sequences(validation_arrays["episode_ids"])
    train_preferences = load_preferences(
        args.train_corpus,
        preserve_behavior_gate=args.preserve_behavior_gate,
    )
    validation_preferences = load_preferences(
        args.validation_corpus,
        preserve_behavior_gate=args.preserve_behavior_gate,
    )
    train_root_fingerprints = root_policy_input_fingerprints(
        train_arrays, train_preferences.root_rows
    )
    validation_root_fingerprints = root_policy_input_fingerprints(
        validation_arrays, validation_preferences.root_rows
    )
    overlapping_root_fingerprints = sorted(
        train_root_fingerprints.intersection(validation_root_fingerprints)
    )
    if overlapping_root_fingerprints:
        raise ValueError(
            "train and validation share exact policy-input roots: "
            f"{len(overlapping_root_fingerprints)}"
        )
    prefixes = tuple(args.trainable_prefix or DEFAULT_TRAINABLE_PREFIXES)
    trainable: list[nn.Parameter] = []
    trainable_names: list[str] = []
    for name, parameter in model.named_parameters():
        enabled = name.startswith(prefixes)
        parameter.requires_grad_(enabled)
        if enabled:
            trainable.append(parameter)
            trainable_names.append(name)
    if not trainable:
        raise ValueError("trainable prefixes matched no parameters")
    optimizer = torch.optim.AdamW(trainable, lr=args.learning_rate, weight_decay=args.weight_decay)
    initial = evaluate(
        model,
        validation_arrays,
        validation_sequences,
        validation_preferences,
        device=device,
        sequence_length=args.sequence_length,
        preserve_behavior_gate=args.preserve_behavior_gate,
    )
    history: list[dict[str, Any]] = [{"epoch": 0, "validation": initial}]
    best_epoch = 0
    best_metrics = initial
    best_state: dict[str, Tensor] | None = None
    root_set = set(train_preferences.root_rows.tolist())
    rng = np.random.default_rng(args.seed)

    for epoch in range(1, args.epochs + 1):
        model.train()
        totals = {"loss": 0.0, "behavior": 0.0, "preference": 0.0, "chunks": 0}
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
                    train_arrays["expert_actions"][chunk], dtype=torch.long, device=device
                )
                per_row = F.cross_entropy(output.joint_logits[0], actions, reduction="none")
                behavior_weights = torch.as_tensor(
                    [args.root_behavior_weight if int(row) in root_set else 1.0 for row in chunk],
                    dtype=torch.float32,
                    device=device,
                )
                behavior_loss = (per_row * behavior_weights).sum() / behavior_weights.sum().clamp_min(1e-8)
                local, positive, negative, weights = chunk_preferences(
                    train_preferences,
                    start=int(chunk[0]),
                    stop=int(chunk[-1]) + 1,
                    device=device,
                )
                if local.numel():
                    margins = output.joint_logits[0][local, positive] - output.joint_logits[0][local, negative]
                    preference_loss = (F.softplus(-margins) * weights).sum() / weights.sum().clamp_min(1e-8)
                else:
                    preference_loss = output.joint_logits.sum() * 0.0
                loss = args.behavior_coef * behavior_loss + args.counterfactual_coef * preference_loss
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError("non-finite factorized repair loss")
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                gradient = nn.utils.clip_grad_norm_(trainable, 0.5)
                if not bool(torch.isfinite(gradient)):
                    raise FloatingPointError("non-finite factorized repair gradient")
                optimizer.step()
                totals["loss"] += float(loss.detach())
                totals["behavior"] += float(behavior_loss.detach())
                totals["preference"] += float(preference_loss.detach())
                totals["chunks"] += 1
                gradient_max = max(gradient_max, float(gradient.detach()))
        validation = evaluate(
            model,
            validation_arrays,
            validation_sequences,
            validation_preferences,
            device=device,
            sequence_length=args.sequence_length,
            preserve_behavior_gate=args.preserve_behavior_gate,
        )
        eligible = bool(
            validation["behavior"]["non_root_exact_action_accuracy"]
            >= initial["behavior"]["non_root_exact_action_accuracy"]
            - args.maximum_exact_regression
            and validation["preferences"]["safety"]["accuracy"]
            >= initial["preferences"]["safety"]["accuracy"] - args.maximum_safety_regression
            and validation["preferences"]["corrective"]["accuracy"]
            >= initial["preferences"]["corrective"]["accuracy"]
            + args.minimum_corrective_improvement
        )
        row = {
            "epoch": epoch,
            "training": {
                **{key: value / max(1, totals["chunks"]) for key, value in totals.items() if key != "chunks"},
                "chunks": int(totals["chunks"]),
                "gradient_norm_max": gradient_max,
                "seconds": time.monotonic() - started,
            },
            "validation": validation,
            "eligible": eligible,
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        score = (
            validation["preferences"]["corrective"]["accuracy"],
            validation["preferences"]["overall"]["accuracy"],
            validation["behavior"]["exact_action_accuracy"],
        )
        best_score = (
            best_metrics["preferences"]["corrective"]["accuracy"],
            best_metrics["preferences"]["overall"]["accuracy"],
            best_metrics["behavior"]["exact_action_accuracy"],
        )
        if eligible and (best_state is None or score > best_score):
            best_epoch = epoch
            best_metrics = validation
            best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}

    report = {
        "schema": "clasher.hog26.factorized-counterfactual.v1",
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
        "counterfactual_coef": args.counterfactual_coef,
        "root_behavior_weight": args.root_behavior_weight,
        "preserve_behavior_gate": args.preserve_behavior_gate,
        "trainable_prefixes": list(prefixes),
        "trainable_parameter_names": trainable_names,
        "trainable_parameter_count": sum(value.numel() for value in trainable),
        "train_preferences": train_preferences.count,
        "validation_preferences": validation_preferences.count,
        "selection_gate": {
            "maximum_exact_regression": args.maximum_exact_regression,
            "exact_behavior_scope": "non_counterfactual_root_rows",
            "maximum_safety_regression": args.maximum_safety_regression,
            "minimum_corrective_improvement": args.minimum_corrective_improvement,
        },
        "initial_validation": initial,
        "best_epoch": best_epoch,
        "best_validation": best_metrics,
        "history": history,
        "selected_nonzero_epoch": best_state is not None,
        "output_checkpoint": str(args.output_checkpoint.resolve()) if best_state is not None else None,
    }
    if best_state is not None:
        result = dict(payload)
        result["model_state_dict"] = best_state
        result.pop("optimizer_state_dict", None)
        result["factorized_counterfactual"] = report
        args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
        torch.save(result, args.output_checkpoint)
        report["output_checkpoint_sha256"] = file_sha256(args.output_checkpoint)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if best_state is None:
        raise SystemExit("no factorized repair epoch passed held-out gates")


if __name__ == "__main__":
    main()
