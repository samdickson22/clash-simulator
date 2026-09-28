"""Fit a public set-based action ranker from exact terminal interventions."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor

from clasher.rl.structured_action_value import (
    PublicStructuredActionValueHead,
    StructuredActionValueConfig,
    public_structured_action_value_checkpoint,
)
from scripts.fit_public_action_value import (
    CROWN_PRIORITY,
    DAMAGE_PRIORITY,
    OUTCOME_PRIORITY,
    PreferenceRows,
    _calibrate_score_gain,
    _candidate_order,
    build_preferences,
    priority_balanced_pairwise_loss,
    root_priority_normalized_weights,
)

REQUIRED_STRUCTURED_ARRAYS = (
    "structured_entity_ids",
    "structured_entity_features",
    "structured_entity_mask",
    "structured_hand_ids",
    "structured_global_features",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as source:
        payload = {name: np.asarray(source[name]) for name in source.files}
    missing = sorted(set(REQUIRED_STRUCTURED_ARRAYS).difference(payload))
    if missing:
        raise ValueError(f"structured action-value corpus is missing {missing}")
    return payload


def _tensor(array: np.ndarray, device: torch.device) -> Tensor:
    return torch.as_tensor(array, device=device)


def _require_finite_named_tensors(
    tensors: list[tuple[str, Tensor | None]],
    *,
    kind: str,
) -> None:
    invalid = [
        name
        for name, value in tensors
        if value is not None and not bool(torch.isfinite(value).all().item())
    ]
    if invalid:
        raise FloatingPointError(
            f"structured action-value fit produced non-finite {kind}: "
            + ", ".join(invalid[:8])
        )


def _structured_state_sizes(
    train: dict[str, np.ndarray],
    validation: dict[str, np.ndarray],
    *,
    contract: str,
) -> tuple[int, int, int]:
    if train["features"].ndim != 2 or validation["features"].ndim != 2:
        raise ValueError("structured pooled features must be rank two")
    if train["features"].shape[1] != validation["features"].shape[1]:
        raise ValueError("structured train and validation feature widths differ")
    if contract == "public-actor-v1":
        return int(train["features"].shape[1]), 0, 0
    if contract != "public-actor-v2-action-time-recurrence":
        raise ValueError("unsupported structured state contract")
    required = (
        "structured_recurrent_cell",
        "structured_previous_play_hazard",
    )
    for payload, name in ((train, "train"), (validation, "validation")):
        missing = set(required).difference(payload)
        if missing:
            raise ValueError(f"structured v2 {name} corpus is missing {sorted(missing)}")
        if payload["structured_recurrent_cell"].ndim != 2:
            raise ValueError(f"structured v2 {name} recurrent cell is not rank two")
        if payload["structured_previous_play_hazard"].ndim != 2:
            raise ValueError(f"structured v2 {name} play hazard is not rank two")
    recurrent_cell_size = int(train["structured_recurrent_cell"].shape[1])
    play_hazard_size = int(
        train["structured_previous_play_hazard"].shape[1]
    )
    expected_tail_shapes = (recurrent_cell_size, play_hazard_size)
    validation_tail_shapes = (
        int(validation["structured_recurrent_cell"].shape[1]),
        int(validation["structured_previous_play_hazard"].shape[1]),
    )
    if expected_tail_shapes != validation_tail_shapes:
        raise ValueError("structured v2 train and validation recurrent widths differ")
    if recurrent_cell_size <= 0 or play_hazard_size != 1:
        raise ValueError("structured v2 recurrent dimensions are invalid")
    state_size = int(train["features"].shape[1]) - recurrent_cell_size
    if state_size <= 0:
        raise ValueError("structured action-value pooled state width is invalid")
    for payload, name in ((train, "train"), (validation, "validation")):
        if not np.array_equal(
            payload["features"][:, state_size:],
            payload["structured_recurrent_cell"],
        ):
            raise ValueError(
                f"structured v2 {name} pooled recurrent tail disagrees with snapshot"
            )
    return state_size, recurrent_cell_size, play_hazard_size


def _score_states(
    head: PublicStructuredActionValueHead,
    payload: dict[str, np.ndarray],
    states: np.ndarray,
    device: torch.device,
) -> Tensor:
    masks = payload["structured_entity_mask"][states]
    maximum_entities = max(1, int(masks.sum(axis=1).max(initial=0)))
    recurrent_cell = (
        _tensor(payload["structured_recurrent_cell"][states], device).float()
        if head.config.recurrent_cell_size
        else None
    )
    previous_play_hazard = (
        _tensor(
            payload["structured_previous_play_hazard"][states], device
        ).float()
        if head.config.play_hazard_size
        else None
    )
    scores: Tensor = head(
        _tensor(
            payload["features"][states, : head.config.state_size], device
        ).float(),
        _tensor(
            payload["structured_entity_ids"][states, :maximum_entities],
            device,
        ).long(),
        _tensor(
            payload["structured_entity_features"][states, :maximum_entities],
            device,
        ).float(),
        _tensor(masks[:, :maximum_entities], device).bool(),
        _tensor(payload["structured_hand_ids"][states], device).long(),
        _tensor(payload["structured_global_features"][states], device).float(),
        _tensor(payload["candidate_card_features"][states], device).float(),
        _tensor(payload["candidate_tile_features"][states], device).float(),
        _tensor(payload["candidate_kinds"][states], device).long(),
        _tensor(
            payload["candidate_policy_log_probabilities"][states], device
        ).float(),
        _tensor(
            payload["candidate_policy_type_log_probabilities"][states],
            device,
        ).float(),
        recurrent_cell,
        previous_play_hazard,
    )
    return scores


def _pairs_by_state(preferences: PreferenceRows) -> dict[int, np.ndarray]:
    result: dict[int, list[int]] = {}
    for row, state in enumerate(preferences.state_indices.tolist()):
        result.setdefault(int(state), []).append(row)
    return {
        state: np.asarray(rows, dtype=np.int64) for state, rows in result.items()
    }


def _batch_pair_coordinates(
    states: np.ndarray,
    by_state: dict[int, np.ndarray],
    preferences: PreferenceRows,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    pair_positions: list[np.ndarray] = []
    pair_rows: list[np.ndarray] = []
    for position, state in enumerate(states.tolist()):
        rows = by_state[int(state)]
        pair_positions.append(np.full(len(rows), position, dtype=np.int64))
        pair_rows.append(rows)
    positions = np.concatenate(pair_positions)
    rows = np.concatenate(pair_rows)
    return (
        positions,
        preferences.positive_indices[rows],
        preferences.negative_indices[rows],
        rows,
    )


@torch.no_grad()
def _all_scores(
    head: PublicStructuredActionValueHead,
    payload: dict[str, np.ndarray],
    device: torch.device,
    batch_size: int,
) -> np.ndarray:
    result = []
    states = np.arange(len(payload["features"]), dtype=np.int64)
    for start in range(0, len(states), batch_size):
        batch = states[start : start + batch_size]
        scores = _score_states(head, payload, batch, device)
        valid = _tensor(payload["candidate_valid"][batch], device).bool()
        result.append(scores.masked_fill(~valid, -torch.inf).cpu().numpy())
    return np.concatenate(result, axis=0)


def _pair_metrics(
    scores: np.ndarray,
    preferences: PreferenceRows,
    state_indices: np.ndarray | None = None,
) -> dict[str, Any]:
    rows = np.arange(len(preferences.state_indices))
    if state_indices is not None:
        rows = rows[np.isin(preferences.state_indices, state_indices)]
    if not len(rows):
        raise ValueError("structured action-value split has no preference pairs")
    differences = (
        scores[
            preferences.state_indices[rows],
            preferences.positive_indices[rows],
        ]
        - scores[
            preferences.state_indices[rows],
            preferences.negative_indices[rows],
        ]
    )
    metrics: dict[str, Any] = {
        "pairs": len(rows),
        "accuracy": float(np.mean(differences > 0.0)),
    }
    for priority, name in (
        (OUTCOME_PRIORITY, "outcome"),
        (CROWN_PRIORITY, "crown"),
        (DAMAGE_PRIORITY, "damage"),
    ):
        selected = preferences.priorities[rows] == priority
        metrics[f"{name}_pairs"] = int(selected.sum())
        metrics[f"{name}_accuracy"] = (
            float(np.mean(differences[selected] > 0.0))
            if np.any(selected)
            else None
        )
    return metrics


def _state_metrics(
    scores: np.ndarray,
    payload: dict[str, np.ndarray],
    state_indices: np.ndarray | None = None,
) -> dict[str, Any]:
    if state_indices is None:
        state_indices = np.arange(len(scores), dtype=np.int64)
    if not len(state_indices):
        raise ValueError("structured action-value split has no states")
    selected = scores[state_indices].argmax(axis=1)
    optimal = 0
    improvement_states = 0
    improvements = 0
    base_optimal_states = 0
    preserved = 0
    for state, candidate in zip(
        state_indices.tolist(), selected.tolist(), strict=True
    ):
        valid = np.flatnonzero(payload["candidate_valid"][state])
        orders = [
            _candidate_order(
                float(payload["candidate_scores"][state, item]),
                int(payload["candidate_crown_differences"][state, item]),
                float(
                    payload["candidate_tower_damage_differences"][state, item]
                ),
            )
            for item in valid
        ]
        selected_order = _candidate_order(
            float(payload["candidate_scores"][state, candidate]),
            int(payload["candidate_crown_differences"][state, candidate]),
            float(payload["candidate_tower_damage_differences"][state, candidate]),
        )
        base_order = orders[0]
        optimal += selected_order == max(orders)
        if max(orders) > base_order:
            improvement_states += 1
            improvements += selected_order > base_order
        else:
            base_optimal_states += 1
            preserved += candidate == 0
    return {
        "states": len(state_indices),
        "optimal_action_rate": optimal / len(state_indices),
        "base_improvement_states": improvement_states,
        "base_improvement_recall": improvements / max(1, improvement_states),
        "base_optimal_states": base_optimal_states,
        "exact_base_preservation_rate": preserved / max(1, base_optimal_states),
    }


def _split_validation_states(
    payload: dict[str, np.ndarray],
    *,
    seed: int,
) -> tuple[dict[str, np.ndarray], dict[str, list[int]]]:
    """Split external validation games into selection/calibration/holdout.

    The final holdout must not influence epoch selection or controller threshold
    calibration.  Games, rather than individual roots, are the independence
    unit because every game contributes several correlated decision roots.
    """

    game_ids = np.asarray(payload["game_ids"], dtype=np.int64)
    unique_games = np.unique(game_ids)
    if len(unique_games) < 10:
        raise ValueError(
            "structured external validation needs at least ten games for a "
            "three-way game-disjoint gate"
        )
    shuffled = np.random.default_rng(seed).permutation(unique_games)
    selection_count = max(1, round(0.30 * len(shuffled)))
    calibration_count = max(1, round(0.30 * len(shuffled)))
    if selection_count + calibration_count >= len(shuffled):
        raise ValueError("structured validation is too small for holdout games")
    games = {
        "selection": shuffled[:selection_count],
        "calibration": shuffled[
            selection_count : selection_count + calibration_count
        ],
        "holdout": shuffled[selection_count + calibration_count :],
    }
    states = {
        name: np.flatnonzero(np.isin(game_ids, values)).astype(np.int64)
        for name, values in games.items()
    }
    if any(not len(values) for values in states.values()):
        raise ValueError("structured validation produced an empty split")
    return states, {
        name: sorted(int(value) for value in values.tolist())
        for name, values in games.items()
    }


def _threshold_metrics(
    *,
    scores: np.ndarray,
    payload: dict[str, np.ndarray],
    state_indices: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    """Evaluate one already-selected threshold without tuning on these rows."""

    split_scores = scores[state_indices]
    best_candidates = split_scores.argmax(axis=1)
    gaps = (
        split_scores[np.arange(len(split_scores)), best_candidates]
        - split_scores[:, 0]
    )
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
    return {
        "threshold": threshold,
        "states": len(state_indices),
        "overrides": overrides,
        "improvements": improvements,
        "regressions": regressions,
        "optimal_action_rate": optimal / len(state_indices),
    }


def _game_cluster_bootstrap_metrics(
    *,
    scores: np.ndarray,
    payload: dict[str, np.ndarray],
    preferences: PreferenceRows,
    state_indices: np.ndarray,
    seed: int,
    samples: int = 10_000,
) -> dict[str, Any]:
    """Bootstrap whole games so correlated roots remain one sampling unit."""

    if samples <= 0:
        raise ValueError("cluster bootstrap samples must be positive")
    selected_games = np.asarray(payload["game_ids"][state_indices], dtype=np.int64)
    games = np.unique(selected_games)
    if len(games) < 2:
        raise ValueError("cluster bootstrap requires at least two games")
    game_positions = {int(game): index for index, game in enumerate(games)}

    pair_rows = np.flatnonzero(np.isin(preferences.state_indices, state_indices))
    differences = (
        scores[
            preferences.state_indices[pair_rows],
            preferences.positive_indices[pair_rows],
        ]
        - scores[
            preferences.state_indices[pair_rows],
            preferences.negative_indices[pair_rows],
        ]
    )
    pair_games = np.asarray(
        payload["game_ids"][preferences.state_indices[pair_rows]],
        dtype=np.int64,
    )

    def grouped_counts(selected: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        numerators = np.zeros(len(games), dtype=np.int64)
        denominators = np.zeros(len(games), dtype=np.int64)
        for game, correct in zip(
            pair_games[selected].tolist(),
            (differences[selected] > 0.0).tolist(),
            strict=True,
        ):
            position = game_positions[int(game)]
            numerators[position] += int(correct)
            denominators[position] += 1
        return numerators, denominators

    overall_numerator, overall_denominator = grouped_counts(
        np.ones(len(pair_rows), dtype=np.bool_)
    )
    outcome_numerator, outcome_denominator = grouped_counts(
        preferences.priorities[pair_rows] == OUTCOME_PRIORITY
    )

    model_candidates = scores[state_indices].argmax(axis=1)
    optimal_correct = np.zeros(len(state_indices), dtype=np.bool_)
    for row, (state, candidate) in enumerate(
        zip(state_indices.tolist(), model_candidates.tolist(), strict=True)
    ):
        valid = np.flatnonzero(payload["candidate_valid"][state])
        selected_order = _candidate_order(
            float(payload["candidate_scores"][state, candidate]),
            int(payload["candidate_crown_differences"][state, candidate]),
            float(payload["candidate_tower_damage_differences"][state, candidate]),
        )
        best_order = max(
            _candidate_order(
                float(payload["candidate_scores"][state, item]),
                int(payload["candidate_crown_differences"][state, item]),
                float(payload["candidate_tower_damage_differences"][state, item]),
            )
            for item in valid
        )
        optimal_correct[row] = selected_order == best_order
    optimal_numerator = np.zeros(len(games), dtype=np.int64)
    optimal_denominator = np.zeros(len(games), dtype=np.int64)
    for game, correct in zip(
        selected_games.tolist(), optimal_correct.tolist(), strict=True
    ):
        position = game_positions[int(game)]
        optimal_numerator[position] += int(correct)
        optimal_denominator[position] += 1

    rng = np.random.default_rng(seed)
    def interval(
        numerator: np.ndarray,
        denominator: np.ndarray,
    ) -> tuple[list[float], int]:
        eligible = np.flatnonzero(denominator > 0)
        if not len(eligible):
            raise ValueError("cluster bootstrap metric has no observations")
        draws = eligible[
            rng.integers(0, len(eligible), size=(samples, len(eligible)))
        ]
        sampled_denominator = denominator[draws].sum(axis=1)
        values = numerator[draws].sum(axis=1) / sampled_denominator
        return (
            [
                float(np.quantile(values, 0.025)),
                float(np.quantile(values, 0.975)),
            ],
            len(eligible),
        )

    accuracy_interval, accuracy_games = interval(
        overall_numerator, overall_denominator
    )
    outcome_interval, outcome_games = interval(
        outcome_numerator, outcome_denominator
    )
    optimal_interval, optimal_games = interval(
        optimal_numerator, optimal_denominator
    )

    return {
        "schema": "clasher.game_cluster_bootstrap.v1",
        "seed": seed,
        "samples": samples,
        "games": len(games),
        "accuracy_games": accuracy_games,
        "accuracy_ci95": accuracy_interval,
        "outcome_accuracy_games": outcome_games,
        "outcome_accuracy_ci95": outcome_interval,
        "optimal_action_rate_games": optimal_games,
        "optimal_action_rate_ci95": optimal_interval,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--corpus-report", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--validation-corpus", type=Path, required=True)
    parser.add_argument("--validation-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1169001)
    parser.add_argument("--validation-split-seed", type=int, default=1169102)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--patience", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=96)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--d-model", type=int, default=96)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--hidden-size", type=int, default=192)
    parser.add_argument("--disable-identity-residual", action="store_true")
    parser.add_argument("--torch-threads", type=int, default=4)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    args = parser.parse_args()
    if min(args.epochs, args.patience, args.batch_size, args.torch_threads) <= 0:
        raise ValueError("structured action-value fit sizes must be positive")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.torch_threads)
    device = torch.device(args.device)

    train = _load(args.corpus)
    validation = _load(args.validation_corpus)
    train_report = json.loads(args.corpus_report.read_text())
    validation_report = json.loads(args.validation_report.read_text())
    structured_contract = train_report.get("structured_state_contract")
    if structured_contract not in {
        "public-actor-v1",
        "public-actor-v2-action-time-recurrence",
    } or validation_report.get("structured_state_contract") != structured_contract:
        raise ValueError("structured action-value reports lack public actor authority")
    if train_report["policy"] != validation_report["policy"]:
        raise ValueError("structured train and validation policies differ")
    manifest = json.loads(args.corpus_manifest.read_text())
    expected_order = "outcome-crowns-tower-damage-v1"
    if (
        train_report.get("best_action_order") != expected_order
        or validation_report.get("best_action_order") != expected_order
        or manifest.get("best_action_order") != expected_order
    ):
        raise ValueError("structured terminal preference order changed")
    policy_sha256 = _sha256(args.policy)
    if policy_sha256 not in set(dict(manifest["inputs"]).values()):
        raise ValueError("structured source policy is absent from corpus authority")
    policy_payload: dict[str, Any] = torch.load(
        args.policy,
        map_location="cpu",
        weights_only=False,
    )
    card_stats = policy_payload["model_state_dict"][
        "actor_encoder.card_stat_features"
    ].float()
    state_size, recurrent_cell_size, play_hazard_size = _structured_state_sizes(
        train,
        validation,
        contract=str(structured_contract),
    )
    config = StructuredActionValueConfig(
        state_size=state_size,
        entity_feature_size=int(train["structured_entity_features"].shape[2]),
        global_feature_size=int(train["structured_global_features"].shape[1]),
        entity_card_feature_size=int(card_stats.shape[1]),
        card_feature_size=int(train["candidate_card_features"].shape[2]),
        tile_feature_size=int(train["candidate_tile_features"].shape[2]),
        visible_card_slots=int(train["structured_hand_ids"].shape[1]),
        d_model=args.d_model,
        num_heads=args.num_heads,
        num_layers=args.num_layers,
        hidden_size=args.hidden_size,
        identity_residual=not args.disable_identity_residual,
        recurrent_cell_size=recurrent_cell_size,
        play_hazard_size=play_hazard_size,
    )
    head = PublicStructuredActionValueHead(config, card_stats).to(device)
    train_preferences = build_preferences(train)
    validation_preferences = build_preferences(validation)
    validation_splits, validation_games = _split_validation_states(
        validation,
        seed=args.validation_split_seed,
    )
    selection_states = validation_splits["selection"]
    calibration_states = validation_splits["calibration"]
    holdout_states = validation_splits["holdout"]
    train_by_state = _pairs_by_state(train_preferences)
    train_states = np.asarray(sorted(train_by_state), dtype=np.int64)
    rng = np.random.default_rng(args.seed)
    fit_states = rng.choice(train_states, size=len(train_states), replace=True)
    weights = root_priority_normalized_weights(train_preferences)
    optimizer = torch.optim.AdamW(
        head.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    best_score = (-float("inf"),) * 6
    best_state: dict[str, Tensor] | None = None
    best_epoch = 0
    stale = 0
    history = []
    for epoch in range(1, args.epochs + 1):
        head.train()
        epoch_losses = []
        epoch_states = rng.permutation(fit_states)
        for start in range(0, len(fit_states), args.batch_size):
            states = epoch_states[start : start + args.batch_size]
            positions, positive, negative, pair_rows = _batch_pair_coordinates(
                states,
                train_by_state,
                train_preferences,
            )
            scores = _score_states(head, train, states, device)
            position_tensor = _tensor(positions, device).long()
            margins = scores[position_tensor, _tensor(positive, device).long()]
            margins = margins - scores[
                position_tensor,
                _tensor(negative, device).long(),
            ]
            loss = priority_balanced_pairwise_loss(
                margins,
                _tensor(weights[pair_rows], device).float(),
                _tensor(train_preferences.priorities[pair_rows], device).long(),
            )
            _require_finite_named_tensors([("loss", loss)], kind="loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                head.parameters(),
                1.0,
                error_if_nonfinite=True,
            )
            _require_finite_named_tensors(
                [(name, parameter.grad) for name, parameter in head.named_parameters()],
                kind="gradients",
            )
            optimizer.step()
            _require_finite_named_tensors(
                list(head.named_parameters()),
                kind="parameters",
            )
            epoch_losses.append(float(loss.detach()))
        head.eval()
        validation_scores = _all_scores(
            head, validation, device, args.batch_size
        )
        pair_metrics = _pair_metrics(
            validation_scores,
            validation_preferences,
            selection_states,
        )
        state_metrics = _state_metrics(
            validation_scores,
            validation,
            selection_states,
        )
        outcome_accuracy = float(pair_metrics["outcome_accuracy"])
        overall_accuracy = float(pair_metrics["accuracy"])
        optimal_action_rate = float(state_metrics["optimal_action_rate"])
        selection_score = (
            0.5 * optimal_action_rate
            + 0.3 * float(state_metrics["base_improvement_recall"])
            + 0.2 * float(state_metrics["exact_base_preservation_rate"])
        )
        gate_balance = min(
            overall_accuracy / 0.62,
            outcome_accuracy / 0.67,
            optimal_action_rate / 0.41990950226244345,
        )
        score = (
            gate_balance,
            min(outcome_accuracy, selection_score),
            0.5 * (outcome_accuracy + selection_score),
            outcome_accuracy,
            selection_score,
            overall_accuracy,
        )
        history.append(
            {
                "epoch": epoch,
                "train_loss": float(np.mean(epoch_losses)),
                "selection": {**pair_metrics, **state_metrics},
                "selection_score": selection_score,
                "gate_balance": gate_balance,
            }
        )
        if score > best_score:
            best_score = score
            best_epoch = epoch
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in head.state_dict().items()
            }
            stale = 0
        else:
            stale += 1
        if epoch == 1 or epoch % 10 == 0 or stale == 0:
            print(json.dumps(history[-1], sort_keys=True), flush=True)
        if stale >= args.patience:
            break
    if best_state is None:
        raise ValueError("structured action-value fit never produced a checkpoint")
    head.load_state_dict(best_state)
    head.eval()
    train_scores = _all_scores(head, train, device, args.batch_size)
    validation_scores = _all_scores(head, validation, device, args.batch_size)
    train_metrics = {
        **_pair_metrics(train_scores, train_preferences),
        **_state_metrics(train_scores, train),
    }
    selection_metrics = {
        **_pair_metrics(
            validation_scores, validation_preferences, selection_states
        ),
        **_state_metrics(validation_scores, validation, selection_states),
    }
    calibration_metrics = {
        **_pair_metrics(
            validation_scores, validation_preferences, calibration_states
        ),
        **_state_metrics(validation_scores, validation, calibration_states),
    }
    holdout_metrics = {
        **_pair_metrics(
            validation_scores, validation_preferences, holdout_states
        ),
        **_state_metrics(validation_scores, validation, holdout_states),
    }
    minimum_score_gain, calibration_sweep = _calibrate_score_gain(
        scores=validation_scores[calibration_states],
        payload=validation,
        state_indices=calibration_states,
    )
    holdout_threshold_metrics = _threshold_metrics(
        scores=validation_scores,
        payload=validation,
        state_indices=holdout_states,
        threshold=minimum_score_gain,
    )
    holdout_cluster_bootstrap = _game_cluster_bootstrap_metrics(
        scores=validation_scores,
        payload=validation,
        preferences=validation_preferences,
        state_indices=holdout_states,
        seed=args.validation_split_seed + 1,
    )
    corpus_sha256 = _sha256(args.corpus)
    checkpoint = public_structured_action_value_checkpoint(
        head=head,
        source_policy=str(args.policy.resolve()),
        source_policy_sha256=policy_sha256,
        corpus_sha256=corpus_sha256,
        minimum_score_gain=minimum_score_gain,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, args.output)
    report = {
        "schema": "clasher.public_structured_action_value_fit.v2",
        "seed": args.seed,
        "corpus": str(args.corpus.resolve()),
        "corpus_sha256": corpus_sha256,
        "validation_corpus": str(args.validation_corpus.resolve()),
        "validation_corpus_sha256": _sha256(args.validation_corpus),
        "source_policy": str(args.policy.resolve()),
        "source_policy_sha256": policy_sha256,
        "fit_contract": {
            "device": device.type,
            "torch_version": torch.__version__,
            "epochs_requested": args.epochs,
            "patience": args.patience,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "torch_threads": args.torch_threads,
        },
        "config": config.__dict__,
        "parameters": sum(parameter.numel() for parameter in head.parameters()),
        "best_epoch": best_epoch,
        "minimum_score_gain": minimum_score_gain,
        "calibration_sweep": calibration_sweep,
        "validation_split_contract": {
            "schema": "clasher.game_disjoint_selection_calibration_holdout.v1",
            "seed": args.validation_split_seed,
            "games": validation_games,
            "states": {
                name: len(values)
                for name, values in validation_splits.items()
            },
        },
        "train": train_metrics,
        "selection": selection_metrics,
        "calibration": calibration_metrics,
        "validation": holdout_metrics,
        "holdout_threshold_metrics": holdout_threshold_metrics,
        "holdout_cluster_bootstrap": holdout_cluster_bootstrap,
        "history": history,
        "checkpoint": str(args.output.resolve()),
        "checkpoint_sha256": _sha256(args.output),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "best_epoch": best_epoch,
                "train": train_metrics,
                "selection": selection_metrics,
                "calibration": calibration_metrics,
                "validation": holdout_metrics,
                "holdout_threshold_metrics": holdout_threshold_metrics,
                "holdout_cluster_bootstrap": holdout_cluster_bootstrap,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
