"""Fit a tiny action-type adapter from exact terminal intervention preferences."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.model import ClasherPolicy, PolicyConfig
from scripts.add_action_type_adapter import add_action_type_adapter


@dataclass(frozen=True)
class PreferenceRows:
    state_indices: np.ndarray
    positive_types: np.ndarray
    negative_types: np.ndarray
    weights: np.ndarray
    kinds: np.ndarray


def _action_type(actions: np.ndarray) -> np.ndarray:
    placements = actions < NUM_HAND_SLOTS * NUM_TILES
    return np.where(
        placements,
        actions // NUM_TILES,
        NUM_HAND_SLOTS + (actions == NUM_HAND_SLOTS * NUM_TILES + 1),
    ).astype(np.int64, copy=False)


def _build_outcome_only_preferences(
    payload: dict[str, np.ndarray],
) -> PreferenceRows:
    """Retain the schema-v1 preference contract for older corpora."""
    base_actions = payload["base_actions"]
    best_actions = payload["best_actions"]
    candidates = payload["candidate_actions"]
    scores = payload["candidate_scores"]
    state_indices: list[int] = []
    positive_types: list[int] = []
    negative_types: list[int] = []
    weights: list[float] = []
    kinds: list[int] = []
    for state in range(len(base_actions)):
        valid = candidates[state] >= 0
        state_actions = candidates[state][valid]
        state_scores = scores[state][valid]
        base_matches = np.flatnonzero(state_actions == base_actions[state])
        if len(base_matches) != 1:
            raise ValueError("each intervention state must contain its base action once")
        base_score = float(state_scores[base_matches[0]])
        best_score = float(np.max(state_scores))
        if best_score > base_score:
            positive = int(_action_type(best_actions[state : state + 1])[0])
            negative = int(_action_type(base_actions[state : state + 1])[0])
            if positive != negative:
                state_indices.append(state)
                positive_types.append(positive)
                negative_types.append(negative)
                weights.append(1.0)
                kinds.append(1)
            continue
        if base_score != 1.0:
            continue
        positive = int(_action_type(base_actions[state : state + 1])[0])
        losing_types = sorted(
            {
                int(_action_type(np.asarray([action], dtype=np.int64))[0])
                for action, score in zip(state_actions, state_scores, strict=True)
                if float(score) < base_score
                and int(_action_type(np.asarray([action], dtype=np.int64))[0])
                != positive
            }
        )
        for negative in losing_types:
            state_indices.append(state)
            positive_types.append(positive)
            negative_types.append(negative)
            weights.append(1.0 / len(losing_types))
            kinds.append(0)
    return PreferenceRows(
        state_indices=np.asarray(state_indices, dtype=np.int64),
        positive_types=np.asarray(positive_types, dtype=np.int64),
        negative_types=np.asarray(negative_types, dtype=np.int64),
        weights=np.asarray(weights, dtype=np.float32),
        kinds=np.asarray(kinds, dtype=np.int8),
    )


def _candidate_order(
    outcome: float,
    crowns: int,
    tower_damage: float,
) -> tuple[float, int, float]:
    return outcome, crowns, tower_damage


def build_preferences(payload: dict[str, np.ndarray]) -> PreferenceRows:
    """Build base-relative action-type preferences from exact terminal labels."""
    lexicographic_arrays = {
        "candidate_crown_differences",
        "candidate_tower_damage_differences",
        "candidate_valid",
    }
    if not lexicographic_arrays.issubset(payload):
        return _build_outcome_only_preferences(payload)

    base_actions = payload["base_actions"]
    candidates = payload["candidate_actions"]
    valid = payload["candidate_valid"]
    outcomes = payload["candidate_scores"]
    crowns = payload["candidate_crown_differences"]
    tower_damage = payload["candidate_tower_damage_differences"]
    state_indices: list[int] = []
    positive_types: list[int] = []
    negative_types: list[int] = []
    weights: list[float] = []
    kinds: list[int] = []
    for state in range(len(base_actions)):
        state_candidates = np.flatnonzero(valid[state])
        base_matches = state_candidates[
            candidates[state, state_candidates] == base_actions[state]
        ]
        if len(base_matches) != 1:
            raise ValueError("each intervention state must contain its base action once")
        base_index = int(base_matches[0])
        base_type = int(
            _action_type(base_actions[state : state + 1])[0]
        )
        base_order = _candidate_order(
            float(outcomes[state, base_index]),
            int(crowns[state, base_index]),
            float(tower_damage[state, base_index]),
        )
        for candidate_index in state_candidates.tolist():
            if candidate_index == base_index:
                continue
            candidate_type = int(
                _action_type(
                    candidates[state, candidate_index : candidate_index + 1]
                )[0]
            )
            if candidate_type == base_type:
                continue
            candidate_order = _candidate_order(
                float(outcomes[state, candidate_index]),
                int(crowns[state, candidate_index]),
                float(tower_damage[state, candidate_index]),
            )
            if candidate_order == base_order:
                continue
            candidate_is_better = candidate_order > base_order
            positive_type, negative_type = (
                (candidate_type, base_type)
                if candidate_is_better
                else (base_type, candidate_type)
            )
            if candidate_order[0] != base_order[0]:
                weight = 4.0
            elif candidate_order[1] != base_order[1]:
                weight = 2.0
            else:
                damage_gap = abs(candidate_order[2] - base_order[2])
                weight = 1.0 + min(
                    1.0,
                    float(np.log1p(damage_gap) / 8.0),
                )
            state_indices.append(state)
            positive_types.append(positive_type)
            negative_types.append(negative_type)
            weights.append(weight)
            kinds.append(1 if candidate_is_better else 0)
    return PreferenceRows(
        state_indices=np.asarray(state_indices, dtype=np.int64),
        positive_types=np.asarray(positive_types, dtype=np.int64),
        negative_types=np.asarray(negative_types, dtype=np.int64),
        weights=np.asarray(weights, dtype=np.float32),
        kinds=np.asarray(kinds, dtype=np.int8),
    )


def concatenate_preferences(
    first: PreferenceRows,
    second: PreferenceRows,
    *,
    second_state_offset: int,
) -> PreferenceRows:
    if second_state_offset < 0:
        raise ValueError("second state offset must be nonnegative")
    return PreferenceRows(
        state_indices=np.concatenate(
            (first.state_indices, second.state_indices + second_state_offset)
        ),
        positive_types=np.concatenate(
            (first.positive_types, second.positive_types)
        ),
        negative_types=np.concatenate(
            (first.negative_types, second.negative_types)
        ),
        weights=np.concatenate((first.weights, second.weights)),
        kinds=np.concatenate((first.kinds, second.kinds)),
    )


def _preference_metrics(
    logits: Tensor,
    rows: PreferenceRows,
    mask: np.ndarray,
) -> dict[str, float | int]:
    selected = np.flatnonzero(mask)
    if not len(selected):
        return {"pairs": 0, "states": 0, "accuracy": 0.0, "mean_margin": 0.0}
    state = torch.as_tensor(rows.state_indices[selected], device=logits.device)
    positive = torch.as_tensor(rows.positive_types[selected], device=logits.device)
    negative = torch.as_tensor(rows.negative_types[selected], device=logits.device)
    margins = logits[state, positive] - logits[state, negative]
    return {
        "pairs": len(selected),
        "states": len(np.unique(rows.state_indices[selected])),
        "accuracy": float((margins > 0.0).float().mean()),
        "mean_margin": float(margins.mean()),
    }


def _split_metrics(
    logits: Tensor,
    rows: PreferenceRows,
    mask: np.ndarray,
) -> dict[str, dict[str, float | int]]:
    return {
        "overall": _preference_metrics(logits, rows, mask),
        "corrective": _preference_metrics(
            logits,
            rows,
            mask & (rows.kinds == 1),
        ),
        "safety": _preference_metrics(
            logits,
            rows,
            mask & (rows.kinds == 0),
        ),
    }


def _balanced_accuracy(
    metrics: dict[str, dict[str, float | int]],
) -> tuple[float, float]:
    corrective = metrics["corrective"]
    safety = metrics["safety"]
    if int(corrective["pairs"]) == 0 or int(safety["pairs"]) == 0:
        raise ValueError("each split requires corrective and safety preferences")
    return (
        min(float(corrective["accuracy"]), float(safety["accuracy"])),
        (float(corrective["accuracy"]) + float(safety["accuracy"])) / 2.0,
    )


def _expand_placement_timing_logits(delta: Tensor) -> Tensor:
    if delta.ndim != 2 or delta.shape[1] != 1:
        raise ValueError("placement timing delta must have shape [batch, 1]")
    return torch.cat(
        (
            delta.expand(-1, NUM_HAND_SLOTS),
            torch.zeros(
                (delta.shape[0], 2),
                dtype=delta.dtype,
                device=delta.device,
            ),
        ),
        dim=-1,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--validation-corpus", type=Path)
    parser.add_argument("--epochs", type=int, default=500)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--l2-weight", type=float, default=1e-3)
    parser.add_argument("--validation-modulus", type=int, default=5)
    parser.add_argument("--validation-remainder", type=int, default=4)
    parser.add_argument("--placement-timing-only", action="store_true")
    parser.add_argument("--adapter-scale", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=1053501)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.epochs <= 0 or args.validation_modulus <= 1 or args.torch_threads <= 0:
        raise ValueError(
            "epochs and torch threads must be positive and validation modulus "
            "must exceed one"
        )
    if not 0.0 <= args.adapter_scale <= 1.0:
        raise ValueError("adapter scale must be between zero and one")
    torch.set_num_threads(args.torch_threads)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device(args.device)
    with np.load(args.corpus, allow_pickle=False) as source:
        payload = {name: np.asarray(source[name]) for name in source.files}
    preferences = build_preferences(payload)
    explicit_validation_pairs: np.ndarray | None = None
    if args.validation_corpus is not None:
        with np.load(args.validation_corpus, allow_pickle=False) as source:
            validation_payload = {
                name: np.asarray(source[name]) for name in source.files
            }
        validation_preferences = build_preferences(validation_payload)
        if payload["features"].shape[1:] != validation_payload["features"].shape[1:]:
            raise ValueError("training and validation feature shapes differ")
        training_pair_count = len(preferences.state_indices)
        training_state_count = len(payload["features"])
        preferences = concatenate_preferences(
            preferences,
            validation_preferences,
            second_state_offset=training_state_count,
        )
        payload["features"] = np.concatenate(
            (payload["features"], validation_payload["features"]),
            axis=0,
        )
        explicit_validation_pairs = np.arange(len(preferences.state_indices)) >= (
            training_pair_count
        )
    if not len(preferences.state_indices):
        raise ValueError("counterfactual corpus has no decisive or safety preferences")
    policy_payload: dict[str, Any] = torch.load(
        args.policy,
        map_location="cpu",
        weights_only=False,
    )
    upgraded = add_action_type_adapter(policy_payload)
    config = PolicyConfig.from_dict(upgraded["model_config"])
    card_stats = upgraded["model_state_dict"][
        "actor_encoder.card_stat_features"
    ].numpy()
    model = ClasherPolicy(config, card_stats).to(device)
    model.load_state_dict(upgraded["model_state_dict"])
    model.eval()
    assert model.action_type_adapter is not None
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    features = torch.as_tensor(payload["features"], device=device)
    if args.placement_timing_only:
        trained_adapter: nn.Linear = nn.Linear(features.shape[-1], 1).to(device)
        nn.init.zeros_(trained_adapter.weight)
        nn.init.zeros_(trained_adapter.bias)
    else:
        trained_adapter = model.action_type_adapter
        for parameter in trained_adapter.parameters():
            parameter.requires_grad_(True)

    def current_adapter_logits() -> Tensor:
        output = trained_adapter(features)
        return (
            _expand_placement_timing_logits(output)
            if args.placement_timing_only
            else output
        )

    with torch.no_grad():
        base_logits = model.action_type_head(features)
    if explicit_validation_pairs is None:
        game_ids = payload["game_ids"]
        state_validation = (
            game_ids % args.validation_modulus == args.validation_remainder
        )
        train_pairs = ~state_validation[preferences.state_indices]
        validation_pairs = state_validation[preferences.state_indices]
    else:
        validation_pairs = explicit_validation_pairs
        train_pairs = ~validation_pairs
    if not np.any(train_pairs) or not np.any(validation_pairs):
        raise ValueError("preference split requires nonempty train and validation pairs")
    optimizer = torch.optim.AdamW(
        trained_adapter.parameters(),
        lr=args.learning_rate,
        weight_decay=0.0,
    )
    state_indices = torch.as_tensor(preferences.state_indices, device=device)
    positive = torch.as_tensor(preferences.positive_types, device=device)
    negative = torch.as_tensor(preferences.negative_types, device=device)
    pair_weights = torch.as_tensor(preferences.weights, device=device)
    train_mask = torch.as_tensor(train_pairs, device=device)
    with torch.no_grad():
        initial_logits = base_logits + current_adapter_logits()
        initial_train_metrics = _split_metrics(
            initial_logits,
            preferences,
            train_pairs,
        )
        initial_validation_metrics = _split_metrics(
            initial_logits,
            preferences,
            validation_pairs,
        )
        initial_train_worst, initial_train_balanced = _balanced_accuracy(
            initial_train_metrics
        )
        initial_validation_worst, initial_validation_balanced = _balanced_accuracy(
            initial_validation_metrics
        )
    best_score = (
        initial_validation_worst,
        initial_validation_balanced,
        initial_train_worst,
        initial_train_balanced,
        0.0,
    )
    best_state: dict[str, Tensor] = {
        name: value.detach().cpu().clone()
        for name, value in trained_adapter.state_dict().items()
    }
    best_epoch = 0
    epochs: list[dict[str, Any]] = []
    for epoch in range(1, args.epochs + 1):
        optimizer.zero_grad(set_to_none=True)
        adapter_output = current_adapter_logits()
        logits = base_logits + adapter_output
        margins = logits[state_indices, positive] - logits[state_indices, negative]
        preference_losses = nn.functional.softplus(-margins)
        preference_loss = (
            preference_losses[train_mask] * pair_weights[train_mask]
        ).sum() / pair_weights[train_mask].sum()
        l2_loss = torch.zeros((), dtype=features.dtype, device=device)
        for parameter in trained_adapter.parameters():
            l2_loss = l2_loss + parameter.square().mean()
        loss = preference_loss + args.l2_weight * l2_loss
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            logits = base_logits + current_adapter_logits()
            train_metrics = _split_metrics(logits, preferences, train_pairs)
            validation_metrics = _split_metrics(
                logits,
                preferences,
                validation_pairs,
            )
            train_worst, train_balanced = _balanced_accuracy(train_metrics)
            validation_worst, validation_balanced = _balanced_accuracy(
                validation_metrics
            )
        score = (
            validation_worst,
            validation_balanced,
            train_worst,
            train_balanced,
            -float(l2_loss.detach()),
        )
        if score > best_score:
            best_score = score
            best_epoch = epoch
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in trained_adapter.state_dict().items()
            }
        if epoch == 1 or epoch % 25 == 0 or epoch == args.epochs:
            epochs.append(
                {
                    "epoch": epoch,
                    "loss": float(loss.detach()),
                    "preference_loss": float(preference_loss.detach()),
                    "l2_loss": float(l2_loss.detach()),
                    "train": train_metrics,
                    "validation": validation_metrics,
                }
            )
    trained_adapter.load_state_dict(best_state)
    with torch.no_grad():
        for parameter in trained_adapter.parameters():
            parameter.mul_(args.adapter_scale)
    if args.placement_timing_only:
        with torch.no_grad():
            model.action_type_adapter.weight.zero_()
            model.action_type_adapter.bias.zero_()
            model.action_type_adapter.weight[:NUM_HAND_SLOTS].copy_(
                trained_adapter.weight.expand(NUM_HAND_SLOTS, -1)
            )
            model.action_type_adapter.bias[:NUM_HAND_SLOTS].copy_(
                trained_adapter.bias.expand(NUM_HAND_SLOTS)
            )
    else:
        # ``trained_adapter`` is the model's action-type adapter in this mode.
        assert trained_adapter is model.action_type_adapter
    upgraded["model_state_dict"] = {
        name: value.detach().cpu() for name, value in model.state_dict().items()
    }
    upgraded["terminal_counterfactual_adapter"] = {
        "schema_version": 1,
        "source_policy": str(args.policy.resolve()),
        "source_corpus": str(args.corpus.resolve()),
        "seed": args.seed,
        "learning_rate": args.learning_rate,
        "l2_weight": args.l2_weight,
        "adapter_scale": args.adapter_scale,
        "torch_threads": args.torch_threads,
        "best_epoch": best_epoch,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(upgraded, args.output)
    with torch.no_grad():
        final_logits = base_logits + current_adapter_logits()
    report = {
        "schema_version": 1,
        "policy": str(args.policy.resolve()),
        "corpus": str(args.corpus.resolve()),
        "validation_corpus": (
            str(args.validation_corpus.resolve())
            if args.validation_corpus is not None
            else None
        ),
        "seed": args.seed,
        "learning_rate": args.learning_rate,
        "l2_weight": args.l2_weight,
        "adapter_scale": args.adapter_scale,
        "torch_threads": args.torch_threads,
        "adapter_mode": (
            "placement-timing-only"
            if args.placement_timing_only
            else "unconstrained-action-type"
        ),
        "preference_pairs": len(preferences.state_indices),
        "corrective_pairs": int(np.sum(preferences.kinds == 1)),
        "safety_pairs": int(np.sum(preferences.kinds == 0)),
        "initial_train": initial_train_metrics,
        "initial_validation": initial_validation_metrics,
        "train": _split_metrics(final_logits, preferences, train_pairs),
        "validation": _split_metrics(
            final_logits,
            preferences,
            validation_pairs,
        ),
        "best_epoch": best_epoch,
        "epochs": epochs,
        "adapter_parameter_count": sum(
            parameter.numel() for parameter in trained_adapter.parameters()
        ),
        "adapter_weight_norm": float(model.action_type_adapter.weight.norm()),
        "adapter_bias_norm": float(model.action_type_adapter.bias.norm()),
        "output": str(args.output.resolve()),
        "output_sha256": _sha256(args.output),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
