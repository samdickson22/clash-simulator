"""Fit a small public action ranker from exact terminal counterfactuals."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor

from clasher.rl.action_value import (
    ActionValueConfig,
    PublicActionValueHead,
    public_action_value_checkpoint,
)
from clasher.rl.counterfactual_corpus import terminal_candidate_order

OUTCOME_PRIORITY = 3
CROWN_PRIORITY = 2
DAMAGE_PRIORITY = 1


@dataclass(frozen=True)
class PreferenceRows:
    state_indices: np.ndarray
    positive_indices: np.ndarray
    negative_indices: np.ndarray
    priorities: np.ndarray
    weights: np.ndarray


def bootstrap_pair_indices_by_state(
    preferences: PreferenceRows,
    pair_indices: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Bootstrap whole intervention roots while keeping their pairs together."""

    pairs = np.asarray(pair_indices, dtype=np.int64)
    if pairs.ndim != 1 or np.any(pairs < 0) or np.any(
        pairs >= len(preferences.state_indices)
    ):
        raise ValueError("bootstrap pair indices are invalid")
    eligible_states = np.unique(preferences.state_indices[pairs])
    if not len(eligible_states):
        raise ValueError("bootstrap requires at least one preference root")
    sampled_states = rng.choice(
        eligible_states,
        size=len(eligible_states),
        replace=True,
    )
    by_state = {
        int(state): pairs[preferences.state_indices[pairs] == state]
        for state in eligible_states
    }
    sampled_pairs = np.concatenate(
        [by_state[int(state)] for state in sampled_states]
    )
    return sampled_pairs, sampled_states


def root_priority_normalized_weights(preferences: PreferenceRows) -> np.ndarray:
    """Give every intervention root unit mass within each terminal priority."""

    normalized = np.zeros_like(preferences.weights, dtype=np.float32)
    for state in np.unique(preferences.state_indices):
        state_mask = preferences.state_indices == state
        for priority in (OUTCOME_PRIORITY, CROWN_PRIORITY, DAMAGE_PRIORITY):
            selected = state_mask & (preferences.priorities == priority)
            denominator = float(preferences.weights[selected].sum())
            if denominator > 0.0:
                normalized[selected] = preferences.weights[selected] / denominator
    return normalized


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source_policy_manifest(
    manifest: dict[str, Any],
    *,
    source_policy_sha256: str,
) -> None:
    schema = manifest.get("schema")
    if schema not in {
        "clasher.hog26_terminal_counterfactual_10k.v1",
        "clasher.hog26_phase_stratified_terminal_cf.v1",
    }:
        raise ValueError("unsupported terminal counterfactual run manifest")
    if schema == "clasher.hog26_phase_stratified_terminal_cf.v1" and (
        manifest.get("structured_state_contract")
        != "public-actor-v2-action-time-recurrence"
        or manifest.get("best_action_order")
        != "outcome-crowns-tower-damage-v1"
        or manifest.get("query_schedule")
        != "phase-stratified-uniform-plus-screened-overtime-v1"
    ):
        raise ValueError("phase-stratified terminal manifest contract changed")
    manifest_hashes = set(dict(manifest.get("inputs", {})).values())
    if source_policy_sha256 not in manifest_hashes:
        raise ValueError("source policy is not an authority in the corpus manifest")


def _candidate_order(
    outcome: float,
    crowns: int,
    tower_damage: float,
) -> tuple[float, int, float]:
    ordered = terminal_candidate_order(outcome, crowns, tower_damage)
    return float(ordered[0]), int(ordered[1]), float(ordered[2])


def build_preferences(payload: dict[str, np.ndarray]) -> PreferenceRows:
    valid = payload["candidate_valid"]
    outcomes = payload["candidate_scores"]
    crowns = payload["candidate_crown_differences"]
    tower_damage = payload["candidate_tower_damage_differences"]
    states: list[int] = []
    positives: list[int] = []
    negatives: list[int] = []
    priorities: list[int] = []
    weights: list[float] = []
    for state in range(valid.shape[0]):
        candidates = np.flatnonzero(valid[state])
        for left_position, left in enumerate(candidates):
            for right in candidates[left_position + 1 :]:
                left_order = _candidate_order(
                    float(outcomes[state, left]),
                    int(crowns[state, left]),
                    float(tower_damage[state, left]),
                )
                right_order = _candidate_order(
                    float(outcomes[state, right]),
                    int(crowns[state, right]),
                    float(tower_damage[state, right]),
                )
                if left_order == right_order:
                    continue
                positive, negative = (
                    (left, right) if left_order > right_order else (right, left)
                )
                if left_order[0] != right_order[0]:
                    priority = OUTCOME_PRIORITY
                    weight = 4.0
                elif left_order[1] != right_order[1]:
                    priority = CROWN_PRIORITY
                    weight = 2.0
                else:
                    priority = DAMAGE_PRIORITY
                    damage_gap = abs(left_order[2] - right_order[2])
                    weight = 1.0 + min(1.0, float(np.log1p(damage_gap) / 8.0))
                if negative == 0 and positive != 0:
                    weight *= 3.0
                elif positive == 0 and negative != 0:
                    weight *= 1.5
                states.append(state)
                positives.append(int(positive))
                negatives.append(int(negative))
                priorities.append(priority)
                weights.append(weight)
    return PreferenceRows(
        state_indices=np.asarray(states, dtype=np.int64),
        positive_indices=np.asarray(positives, dtype=np.int64),
        negative_indices=np.asarray(negatives, dtype=np.int64),
        priorities=np.asarray(priorities, dtype=np.int8),
        weights=np.asarray(weights, dtype=np.float32),
    )


def base_relative_preferences(preferences: PreferenceRows) -> PreferenceRows:
    """Keep only candidate-versus-base comparisons used by the controller.

    Candidate slot zero is the frozen policy action by corpus contract.  This
    screen deliberately removes candidate-versus-candidate pairs, which the
    deployed controller never observes without also comparing both candidates
    to that same base action.
    """

    selected = (preferences.positive_indices == 0) | (
        preferences.negative_indices == 0
    )
    if not np.any(selected):
        raise ValueError("base-relative preference screen has no pairs")
    return PreferenceRows(
        state_indices=preferences.state_indices[selected],
        positive_indices=preferences.positive_indices[selected],
        negative_indices=preferences.negative_indices[selected],
        priorities=preferences.priorities[selected],
        weights=preferences.weights[selected],
    )


def _tensor(array: np.ndarray, device: torch.device) -> Tensor:
    return torch.as_tensor(array, device=device)


def priority_balanced_pairwise_loss(
    margins: Tensor,
    weights: Tensor,
    priorities: Tensor,
) -> Tensor:
    """Normalize terminal outcome, crown, and damage supervision separately."""

    if margins.ndim != 1 or weights.shape != margins.shape:
        raise ValueError("pairwise margins and weights must be matching vectors")
    if priorities.shape != margins.shape:
        raise ValueError("pairwise priorities must match margins")
    losses = torch.nn.functional.softplus(-margins) * weights
    components = []
    present = []
    for priority in (OUTCOME_PRIORITY, CROWN_PRIORITY, DAMAGE_PRIORITY):
        selected = priorities == priority
        selected_weights = weights * selected
        denominator = selected_weights.sum()
        components.append(
            (losses * selected).sum() / denominator.clamp_min(1e-9)
        )
        present.append((denominator > 0.0).to(margins.dtype))
    component_tensor = torch.stack(components)
    present_tensor = torch.stack(present)
    return (component_tensor * present_tensor).sum() / present_tensor.sum().clamp_min(1.0)


def _score_pair_batch(
    head: PublicActionValueHead,
    payload: dict[str, np.ndarray],
    preferences: PreferenceRows,
    rows: np.ndarray,
    device: torch.device,
) -> tuple[Tensor, Tensor]:
    states = preferences.state_indices[rows]
    state_features = _tensor(payload["features"][states], device).float()
    if head.config.base_relative_interactions:
        scores = head(
            state_features,
            _tensor(payload["candidate_card_features"][states], device).float(),
            _tensor(payload["candidate_tile_features"][states], device).float(),
            _tensor(payload["candidate_kinds"][states], device).long(),
            _tensor(
                payload["candidate_policy_log_probabilities"][states],
                device,
            ).float(),
            _tensor(
                payload["candidate_policy_type_log_probabilities"][states],
                device,
            ).float(),
        )
        positive_indices = _tensor(
            preferences.positive_indices[rows],
            device,
        ).long()
        negative_indices = _tensor(
            preferences.negative_indices[rows],
            device,
        ).long()
        return (
            scores.gather(1, positive_indices[:, None]).squeeze(1),
            scores.gather(1, negative_indices[:, None]).squeeze(1),
        )
    candidates = np.stack(
        (
            preferences.positive_indices[rows],
            preferences.negative_indices[rows],
        ),
        axis=1,
    )
    row_index = states[:, None]
    scores = head(
        state_features,
        _tensor(payload["candidate_card_features"][row_index, candidates], device).float(),
        _tensor(payload["candidate_tile_features"][row_index, candidates], device).float(),
        _tensor(payload["candidate_kinds"][row_index, candidates], device).long(),
        _tensor(
            payload["candidate_policy_log_probabilities"][row_index, candidates],
            device,
        ).float(),
        _tensor(
            payload["candidate_policy_type_log_probabilities"][row_index, candidates],
            device,
        ).float(),
    )
    return scores[:, 0], scores[:, 1]


@torch.no_grad()
def _preference_metrics(
    head: PublicActionValueHead,
    payload: dict[str, np.ndarray],
    preferences: PreferenceRows,
    rows: np.ndarray,
    device: torch.device,
    batch_size: int,
) -> dict[str, Any]:
    differences: list[np.ndarray] = []
    losses: list[np.ndarray] = []
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        positive, negative = _score_pair_batch(
            head,
            payload,
            preferences,
            batch,
            device,
        )
        difference = positive - negative
        differences.append(difference.cpu().numpy())
        weights = _tensor(preferences.weights[batch], device)
        losses.append(
            (torch.nn.functional.softplus(-difference) * weights).cpu().numpy()
        )
    all_differences = np.concatenate(differences)
    all_losses = np.concatenate(losses)
    metrics: dict[str, Any] = {
        "pairs": len(rows),
        "accuracy": float(np.mean(all_differences > 0.0)),
        "mean_weighted_loss": float(np.mean(all_losses)),
    }
    for priority, name in (
        (OUTCOME_PRIORITY, "outcome"),
        (CROWN_PRIORITY, "crown"),
        (DAMAGE_PRIORITY, "damage"),
    ):
        selected = preferences.priorities[rows] == priority
        metrics[f"{name}_pairs"] = int(selected.sum())
        metrics[f"{name}_accuracy"] = (
            float(np.mean(all_differences[selected] > 0.0))
            if np.any(selected)
            else None
        )
    return metrics


@torch.no_grad()
def _state_metrics(
    head: PublicActionValueHead,
    payload: dict[str, np.ndarray],
    state_indices: np.ndarray,
    device: torch.device,
    batch_size: int,
) -> dict[str, Any]:
    selected_actions: list[int] = []
    for start in range(0, len(state_indices), batch_size):
        rows = state_indices[start : start + batch_size]
        scores = head(
            _tensor(payload["features"][rows], device).float(),
            _tensor(payload["candidate_card_features"][rows], device).float(),
            _tensor(payload["candidate_tile_features"][rows], device).float(),
            _tensor(payload["candidate_kinds"][rows], device).long(),
            _tensor(payload["candidate_policy_log_probabilities"][rows], device).float(),
            _tensor(
                payload["candidate_policy_type_log_probabilities"][rows],
                device,
            ).float(),
        )
        valid = _tensor(payload["candidate_valid"][rows], device)
        scores = scores.masked_fill(~valid, -torch.inf)
        selected_actions.extend(scores.argmax(dim=1).cpu().tolist())

    optimal = 0
    base_improvement_states = 0
    selected_base_improvements = 0
    base_optimal_states = 0
    preserved_base = 0
    for state, selected in zip(state_indices.tolist(), selected_actions, strict=True):
        valid_candidates = np.flatnonzero(payload["candidate_valid"][state])
        orders = [
            _candidate_order(
                float(payload["candidate_scores"][state, candidate]),
                int(payload["candidate_crown_differences"][state, candidate]),
                float(
                    payload["candidate_tower_damage_differences"][state, candidate]
                ),
            )
            for candidate in valid_candidates
        ]
        best_order = max(orders)
        selected_order = _candidate_order(
            float(payload["candidate_scores"][state, selected]),
            int(payload["candidate_crown_differences"][state, selected]),
            float(payload["candidate_tower_damage_differences"][state, selected]),
        )
        base_order = orders[0]
        optimal += selected_order == best_order
        if best_order > base_order:
            base_improvement_states += 1
            selected_base_improvements += selected_order > base_order
        else:
            base_optimal_states += 1
            preserved_base += selected == 0
    return {
        "states": len(state_indices),
        "optimal_action_rate": optimal / max(1, len(state_indices)),
        "base_improvement_states": base_improvement_states,
        "base_improvement_recall": (
            selected_base_improvements / base_improvement_states
            if base_improvement_states
            else None
        ),
        "base_optimal_states": base_optimal_states,
        "exact_base_preservation_rate": (
            preserved_base / base_optimal_states if base_optimal_states else None
        ),
    }


@torch.no_grad()
def _state_scores(
    head: PublicActionValueHead,
    payload: dict[str, np.ndarray],
    state_indices: np.ndarray,
    device: torch.device,
    batch_size: int,
) -> np.ndarray:
    rows: list[np.ndarray] = []
    for start in range(0, len(state_indices), batch_size):
        batch = state_indices[start : start + batch_size]
        scores = head(
            _tensor(payload["features"][batch], device).float(),
            _tensor(payload["candidate_card_features"][batch], device).float(),
            _tensor(payload["candidate_tile_features"][batch], device).float(),
            _tensor(payload["candidate_kinds"][batch], device).long(),
            _tensor(
                payload["candidate_policy_log_probabilities"][batch],
                device,
            ).float(),
            _tensor(
                payload["candidate_policy_type_log_probabilities"][batch],
                device,
            ).float(),
        )
        valid = _tensor(payload["candidate_valid"][batch], device)
        rows.append(scores.masked_fill(~valid, -torch.inf).cpu().numpy())
    return np.concatenate(rows, axis=0)


def _calibrate_score_gain(
    *,
    scores: np.ndarray,
    payload: dict[str, np.ndarray],
    state_indices: np.ndarray,
) -> tuple[float, list[dict[str, Any]]]:
    best_candidates = scores.argmax(axis=1)
    gaps = scores[np.arange(len(scores)), best_candidates] - scores[:, 0]
    thresholds = [0.0, *sorted({float(gap) for gap in gaps if gap > 0.0})]
    thresholds.append(max(thresholds) + 1e-6)
    sweep: list[dict[str, Any]] = []
    for threshold in thresholds:
        overrides = 0
        improvements = {"outcome": 0, "crown": 0, "damage": 0}
        regressions = {"outcome": 0, "crown": 0, "damage": 0}
        optimal = 0
        for row, state in enumerate(state_indices.tolist()):
            candidate = int(best_candidates[row]) if gaps[row] > threshold else 0
            overrides += candidate != 0
            base_order = _candidate_order(
                float(payload["candidate_scores"][state, 0]),
                int(payload["candidate_crown_differences"][state, 0]),
                float(payload["candidate_tower_damage_differences"][state, 0]),
            )
            selected_order = _candidate_order(
                float(payload["candidate_scores"][state, candidate]),
                int(payload["candidate_crown_differences"][state, candidate]),
                float(
                    payload["candidate_tower_damage_differences"][state, candidate]
                ),
            )
            if selected_order != base_order:
                if selected_order[0] != base_order[0]:
                    kind = "outcome"
                elif selected_order[1] != base_order[1]:
                    kind = "crown"
                else:
                    kind = "damage"
                target = improvements if selected_order > base_order else regressions
                target[kind] += 1
            valid_candidates = np.flatnonzero(payload["candidate_valid"][state])
            best_order = max(
                _candidate_order(
                    float(payload["candidate_scores"][state, item]),
                    int(payload["candidate_crown_differences"][state, item]),
                    float(
                        payload["candidate_tower_damage_differences"][state, item]
                    ),
                )
                for item in valid_candidates
            )
            optimal += selected_order == best_order
        sweep.append(
            {
                "threshold": threshold,
                "overrides": overrides,
                "improvements": improvements,
                "regressions": regressions,
                "optimal_action_rate": optimal / max(1, len(state_indices)),
            }
        )
    safe = [
        row
        for row in sweep
        if sum(int(value) for value in row["regressions"].values()) == 0
    ]
    selected = max(
        safe,
        key=lambda row: (
            sum(int(value) for value in row["improvements"].values()),
            float(row["optimal_action_rate"]),
            -int(row["overrides"]),
            float(row["threshold"]),
        ),
    )
    return float(selected["threshold"]), sweep


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--corpus-report", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path)
    parser.add_argument("--source-policy", type=Path)
    parser.add_argument("--validation-corpus", type=Path)
    parser.add_argument("--validation-corpus-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1060301)
    parser.add_argument("--validation-fraction", type=float, default=0.25)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--bootstrap-train-roots", action="store_true")
    parser.add_argument("--priority-balanced-loss", action="store_true")
    parser.add_argument("--root-balanced-loss", action="store_true")
    parser.add_argument("--base-relative-only", action="store_true")
    parser.add_argument("--base-relative-interactions", action="store_true")
    parser.add_argument("--state-hidden-size", type=int, default=128)
    parser.add_argument("--action-hidden-size", type=int, default=128)
    parser.add_argument("--hidden-size", type=int, default=128)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    args = parser.parse_args()
    if not 0.0 < args.validation_fraction < 1.0:
        raise ValueError("validation fraction must be between zero and one")
    if min(
        args.state_hidden_size,
        args.action_hidden_size,
        args.hidden_size,
        args.torch_threads,
    ) <= 0:
        raise ValueError("action-value sizes and torch threads must be positive")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.torch_threads)
    device = torch.device(args.device)
    with np.load(args.corpus, allow_pickle=False) as source:
        train_payload = {name: np.asarray(source[name]) for name in source.files}
    corpus_report = json.loads(args.corpus_report.read_text())
    if int(corpus_report.get("schema_version", 0)) != 2:
        raise ValueError("unsupported terminal counterfactual corpus schema")
    train_preferences = build_preferences(train_payload)
    if args.base_relative_only:
        train_preferences = base_relative_preferences(train_preferences)
    unique_train_games = np.unique(train_payload["game_ids"])
    rng = np.random.default_rng(args.seed)
    if (args.validation_corpus is None) != (
        args.validation_corpus_report is None
    ):
        raise ValueError(
            "validation corpus and validation corpus report must be supplied together"
        )
    if (args.source_policy is None) != (args.corpus_manifest is None):
        raise ValueError(
            "source policy and corpus manifest must be supplied together"
        )
    if args.validation_corpus is not None:
        assert args.validation_corpus_report is not None
        with np.load(args.validation_corpus, allow_pickle=False) as source:
            validation_payload = {
                name: np.asarray(source[name]) for name in source.files
            }
        validation_corpus_report = json.loads(
            args.validation_corpus_report.read_text()
        )
        if int(validation_corpus_report.get("schema_version", 0)) != 2:
            raise ValueError("unsupported validation counterfactual corpus schema")
        if corpus_report["policy"] != validation_corpus_report["policy"]:
            raise ValueError("train and validation corpus policies do not match")
        validation_preferences = build_preferences(validation_payload)
        if args.base_relative_only:
            validation_preferences = base_relative_preferences(
                validation_preferences
            )
        train_states = np.arange(train_payload["features"].shape[0])
        validation_states = np.arange(validation_payload["features"].shape[0])
        train_pairs = np.arange(len(train_preferences.state_indices))
        validation_pairs = np.arange(len(validation_preferences.state_indices))
        validation_games = np.unique(validation_payload["game_ids"])
        validation_source = str(args.validation_corpus.resolve())
        validation_source_sha256 = _sha256(args.validation_corpus)
    else:
        shuffled_games = rng.permutation(unique_train_games)
        validation_games_count = max(
            1,
            min(
                len(unique_train_games) - 1,
                round(len(unique_train_games) * args.validation_fraction),
            ),
        )
        validation_games = shuffled_games[:validation_games_count]
        validation_states_mask = np.isin(
            train_payload["game_ids"], validation_games
        )
        train_states = np.flatnonzero(~validation_states_mask)
        validation_states = np.flatnonzero(validation_states_mask)
        train_pairs = np.flatnonzero(
            np.isin(train_preferences.state_indices, train_states)
        )
        validation_pairs = np.flatnonzero(
            np.isin(train_preferences.state_indices, validation_states)
        )
        validation_payload = train_payload
        validation_preferences = train_preferences
        validation_source = str(args.corpus.resolve())
        validation_source_sha256 = _sha256(args.corpus)
    if not len(train_pairs) or not len(validation_pairs):
        raise ValueError("both train and validation splits need preference pairs")
    if args.bootstrap_train_roots:
        fit_train_pairs, bootstrap_states = bootstrap_pair_indices_by_state(
            train_preferences,
            train_pairs,
            rng,
        )
    else:
        fit_train_pairs = train_pairs
        bootstrap_states = np.unique(train_preferences.state_indices[train_pairs])

    config = ActionValueConfig(
        state_size=int(train_payload["features"].shape[1]),
        card_feature_size=int(train_payload["candidate_card_features"].shape[2]),
        tile_feature_size=int(train_payload["candidate_tile_features"].shape[2]),
        state_hidden_size=args.state_hidden_size,
        action_hidden_size=args.action_hidden_size,
        hidden_size=args.hidden_size,
        base_relative_interactions=args.base_relative_interactions,
    )
    validation_dimensions = (
        int(validation_payload["features"].shape[1]),
        int(validation_payload["candidate_card_features"].shape[2]),
        int(validation_payload["candidate_tile_features"].shape[2]),
    )
    if validation_dimensions != (
        config.state_size,
        config.card_feature_size,
        config.tile_feature_size,
    ):
        raise ValueError("train and validation corpus feature dimensions do not match")
    head = PublicActionValueHead(config).to(device)
    optimizer = torch.optim.AdamW(
        head.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    best_score = (-1.0, -1.0, -1.0, -1.0, -1.0, float("-inf"))
    best_epoch = 0
    best_state: dict[str, Tensor] | None = None
    stale = 0
    history: list[dict[str, Any]] = []
    fit_pair_weights = (
        root_priority_normalized_weights(train_preferences)
        if args.root_balanced_loss
        else train_preferences.weights
    )
    for epoch in range(1, args.epochs + 1):
        head.train()
        permutation = rng.permutation(fit_train_pairs)
        epoch_losses: list[float] = []
        for start in range(0, len(permutation), args.batch_size):
            batch = permutation[start : start + args.batch_size]
            positive, negative = _score_pair_batch(
                head,
                train_payload,
                train_preferences,
                batch,
                device,
            )
            weights = _tensor(fit_pair_weights[batch], device)
            margins = positive - negative
            if args.priority_balanced_loss:
                loss = priority_balanced_pairwise_loss(
                    margins,
                    weights,
                    _tensor(train_preferences.priorities[batch], device),
                )
            else:
                loss = (torch.nn.functional.softplus(-margins) * weights).mean()
            if not torch.isfinite(loss):
                raise FloatingPointError(
                    f"non-finite action-value loss at epoch {epoch}"
                )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
            optimizer.step()
            epoch_losses.append(float(loss.item()))
        head.eval()
        validation = _preference_metrics(
            head,
            validation_payload,
            validation_preferences,
            validation_pairs,
            device,
            args.batch_size,
        )
        validation_states_metrics = _state_metrics(
            head,
            validation_payload,
            validation_states,
            device,
            args.batch_size,
        )
        base_recall = validation_states_metrics["base_improvement_recall"]
        base_preservation = validation_states_metrics[
            "exact_base_preservation_rate"
        ]
        selection_score = (
            0.5 * float(validation_states_metrics["optimal_action_rate"])
            + 0.3 * float(1.0 if base_recall is None else base_recall)
            + 0.2
            * float(1.0 if base_preservation is None else base_preservation)
        )
        outcome_accuracy = validation["outcome_accuracy"]
        if outcome_accuracy is None:
            raise ValueError("validation split has no terminal-outcome pairs")
        history.append(
            {
                "epoch": epoch,
                "train_loss": float(np.mean(epoch_losses)),
                "validation_accuracy": validation["accuracy"],
                "validation_loss": validation["mean_weighted_loss"],
                "validation_optimal_action_rate": validation_states_metrics[
                    "optimal_action_rate"
                ],
                "validation_base_improvement_recall": base_recall,
                "validation_base_preservation": base_preservation,
                "selection_score": selection_score,
                "selection_outcome_balance": min(
                    float(outcome_accuracy), selection_score
                ),
            }
        )
        accuracy = float(validation["accuracy"])
        validation_loss = float(validation["mean_weighted_loss"])
        score = (
            min(float(outcome_accuracy), selection_score),
            0.5 * (float(outcome_accuracy) + selection_score),
            float(outcome_accuracy),
            selection_score,
            accuracy,
            -validation_loss,
        )
        improved = score > best_score
        if improved:
            best_score = score
            best_epoch = epoch
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in head.state_dict().items()
            }
            stale = 0
        else:
            stale += 1
        if epoch == 1 or epoch % 10 == 0 or improved:
            print(json.dumps(history[-1], sort_keys=True), flush=True)
        if stale >= args.patience:
            break
    assert best_state is not None
    head.load_state_dict(best_state)
    head.eval()
    train_metrics = _preference_metrics(
        head,
        train_payload,
        train_preferences,
        train_pairs,
        device,
        args.batch_size,
    )
    validation_metrics = _preference_metrics(
        head,
        validation_payload,
        validation_preferences,
        validation_pairs,
        device,
        args.batch_size,
    )
    train_state_metrics = _state_metrics(
        head, train_payload, train_states, device, args.batch_size
    )
    validation_state_metrics = _state_metrics(
        head, validation_payload, validation_states, device, args.batch_size
    )
    validation_scores = _state_scores(
        head,
        validation_payload,
        validation_states,
        device,
        args.batch_size,
    )
    minimum_score_gain, calibration_sweep = _calibrate_score_gain(
        scores=validation_scores,
        payload=validation_payload,
        state_indices=validation_states,
    )
    corpus_sha256 = _sha256(args.corpus)
    source_policy = str(corpus_report["policy"])
    source_policy_sha256: str | None = None
    if args.source_policy is not None:
        assert args.corpus_manifest is not None
        corpus_manifest = json.loads(args.corpus_manifest.read_text())
        source_policy_sha256 = _sha256(args.source_policy)
        validate_source_policy_manifest(
            corpus_manifest,
            source_policy_sha256=source_policy_sha256,
        )
        source_policy = str(args.source_policy.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        public_action_value_checkpoint(
            head=head,
            source_policy=source_policy,
            source_policy_sha256=source_policy_sha256,
            corpus_sha256=corpus_sha256,
            minimum_score_gain=minimum_score_gain,
        ),
        args.output,
    )
    report = {
        "schema_version": 1,
        "seed": args.seed,
        "corpus": str(args.corpus.resolve()),
        "corpus_sha256": corpus_sha256,
        "source_policy": source_policy,
        "source_policy_sha256": source_policy_sha256,
        "states": int(train_payload["features"].shape[0]),
        "games": len(unique_train_games),
        "preferences": len(train_preferences.state_indices),
        "parameters": sum(parameter.numel() for parameter in head.parameters()),
        "bootstrap_train_roots": args.bootstrap_train_roots,
        "priority_balanced_loss": args.priority_balanced_loss,
        "root_balanced_loss": args.root_balanced_loss,
        "base_relative_only": args.base_relative_only,
        "base_relative_interactions": args.base_relative_interactions,
        "fit_preference_pairs": len(fit_train_pairs),
        "fit_root_draws": len(bootstrap_states),
        "fit_unique_roots": len(np.unique(bootstrap_states)),
        "config": config.__dict__,
        "best_epoch": best_epoch,
        "minimum_score_gain": minimum_score_gain,
        "calibration_sweep": calibration_sweep,
        "train": {**train_metrics, **train_state_metrics},
        "validation": {**validation_metrics, **validation_state_metrics},
        "validation_corpus": validation_source,
        "validation_corpus_sha256": validation_source_sha256,
        "validation_games": validation_games.tolist(),
        "history": history,
        "checkpoint": str(args.output.resolve()),
        "checkpoint_sha256": _sha256(args.output),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("best_epoch", "train", "validation")}, sort_keys=True))


if __name__ == "__main__":
    main()
