#!/usr/bin/env python3
"""Train a frozen-policy actor-visible complete-outcome prediction head."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from torch import Tensor
from torch.nn import functional as F

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.direct_simple_behavior import (
    DirectSimpleBehaviorCorpus,
    load_direct_simple_behavior_corpus,
)
from clasher.rl.model import ClasherPolicy, PolicyInputs
from clasher.rl.outcome_model import (
    ActorOutcomeHead,
    actor_outcome_loss,
    outcome_state_sha256,
)
from scripts.pretrain_hog26_direct_simple_behavior import load_model
from scripts.pretrain_hog26_factorized_policy import batch_inputs

SCHEMA = "clasher.hog26.actor-outcome-training.v1"
CORPUS_SCHEMA = "clasher.hog26.complete-outcome-corpus.v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _episode_rows(corpus: DirectSimpleBehaviorCorpus, values: np.ndarray) -> np.ndarray:
    if values.shape[:1] != (corpus.episode_count,):
        raise ValueError("episode metadata does not align with corpus")
    return np.repeat(values, np.diff(corpus.episode_offsets), axis=0)


def _outcome_source(metadata: dict[str, Any]) -> str:
    """Classify old and new corpora without silently treating controls as natural."""

    explicit = metadata.get("outcome_source")
    if explicit is not None:
        return str(explicit)
    if metadata.get("symmetric_draw_source") is True:
        return "controlled-symmetric-draws"
    return "natural-strategy-games"


def _natural_metadata_values(
    loaded: list[tuple[dict[str, Any], DirectSimpleBehaviorCorpus]], key: str
) -> set[str]:
    values: set[str] = set()
    for metadata, _corpus in loaded:
        if _outcome_source(metadata) != "natural-strategy-games":
            continue
        raw = metadata.get(key)
        if not isinstance(raw, list):
            raise TypeError(f"natural outcome corpus lacks {key}")
        values.update(str(value) for value in raw)
    return values


def episode_class_balanced_row_weights(
    loaded: list[tuple[dict[str, Any], DirectSimpleBehaviorCorpus]],
    *,
    target_class_mass: tuple[float, float, float],
    phase_balanced: bool = False,
) -> Tensor:
    """Give episodes equal mass, then set declared loss/draw/win training mass."""

    masses = np.asarray(target_class_mass, dtype=np.float64)
    if (
        masses.shape != (3,)
        or not np.isfinite(masses).all()
        or bool((masses < 0).any())
    ):
        raise ValueError("target class mass must contain three nonnegative values")
    if not np.isclose(masses.sum(), 1.0):
        raise ValueError("target class mass must sum to one")
    outcomes = np.concatenate(
        [
            np.asarray(corpus.arrays["final_outcomes"], dtype=np.int64)
            for _metadata, corpus in loaded
        ]
    )
    weights = (
        episode_balanced_row_weights(loaded, phase_balanced=phase_balanced)
        .numpy()
        .astype(np.float64)
    )
    for class_index, outcome in enumerate((-1, 0, 1)):
        selected = outcomes == outcome
        current = float(weights[selected].sum())
        target = float(masses[class_index])
        if target > 0.0 and current <= 0.0:
            raise ValueError("target class mass is positive for an absent class")
        weights[selected] *= 0.0 if target == 0.0 else target / current
    weights *= len(weights) / weights.sum()
    return torch.as_tensor(weights, dtype=torch.float32)


def episode_balanced_row_weights(
    loaded: list[tuple[dict[str, Any], DirectSimpleBehaviorCorpus]],
    *,
    phase_balanced: bool = False,
) -> Tensor:
    """Give every game equal mass, optionally equalizing its reached phases."""

    parts: list[np.ndarray] = []
    for _metadata, corpus in loaded:
        if not phase_balanced:
            lengths = np.diff(corpus.episode_offsets).astype(np.float64)
            parts.append(np.repeat(1.0 / lengths, lengths.astype(np.int64)))
            continue
        progress = np.asarray(corpus.arrays["global_features"][:, 0])
        corpus_weights = np.zeros(corpus.row_count, dtype=np.float64)
        for begin, end in zip(
            corpus.episode_offsets[:-1], corpus.episode_offsets[1:], strict=True
        ):
            episode_progress = progress[begin:end]
            phase_ids = np.minimum((episode_progress * 3.0).astype(np.int64), 2)
            reached = np.unique(phase_ids)
            for phase in reached:
                rows = np.flatnonzero(phase_ids == phase)
                corpus_weights[int(begin) + rows] = 1.0 / (
                    float(reached.size) * float(rows.size)
                )
        parts.append(corpus_weights)
    weights = np.concatenate(parts)
    weights *= len(weights) / weights.sum()
    return torch.as_tensor(weights, dtype=torch.float32)


def validate_outcome_corpus(
    metadata: dict[str, Any], corpus: DirectSimpleBehaviorCorpus
) -> None:
    if metadata.get("schema") != CORPUS_SCHEMA:
        raise ValueError("unknown complete-outcome corpus schema")
    if metadata.get("label_authority") != (
        "undiscounted-terminal-winner-and-post-action-public-tower-fractions-v1"
    ):
        raise ValueError("corpus lacks undiscounted public outcome authority")
    if metadata.get("actor_input_excludes_outcome_labels") is not True:
        raise ValueError("corpus does not separate future labels from actor inputs")
    if any(name.startswith("critic_") for name in corpus.arrays):
        raise ValueError("actor outcome corpus contains privileged critic inputs")
    required_rows = {
        "final_outcomes",
        "terminal_tower_margins",
        "next_global_features",
        "terminal_winners",
    }
    required_episodes = {
        "episode_opponent_indices",
        "episode_learner_players",
        "episode_final_outcomes",
        "episode_terminal_tower_margins",
    }
    if not required_rows.issubset(corpus.arrays):
        raise ValueError("corpus lacks complete row outcome labels")
    if not required_episodes.issubset(corpus.episode_arrays):
        raise ValueError("corpus lacks complete episode outcome labels")
    outcomes = np.asarray(corpus.arrays["final_outcomes"])
    margins = np.asarray(corpus.arrays["terminal_tower_margins"])
    if outcomes.shape != (corpus.row_count,) or not bool(
        np.isin(outcomes, (-1, 0, 1)).all()
    ):
        raise ValueError("row outcomes must be -1, 0, or 1")
    if margins.shape != (corpus.row_count,) or not np.isfinite(margins).all():
        raise ValueError("row terminal margins must be finite")
    if not np.array_equal(
        outcomes,
        _episode_rows(corpus, corpus.episode_arrays["episode_final_outcomes"]),
    ):
        raise ValueError("row outcomes differ from complete episode labels")
    if not np.array_equal(
        margins,
        _episode_rows(corpus, corpus.episode_arrays["episode_terminal_tower_margins"]),
    ):
        raise ValueError("row margins differ from complete episode labels")


def structured_actor_summary(model: ClasherPolicy, inputs: PolicyInputs) -> Tensor:
    """Pool public entities and mechanics without learned identity shortcuts."""

    stat = model.actor_encoder.card_stat_features
    semantic = model.actor_encoder.semantic_card_features
    descriptors = torch.cat((stat, semantic), dim=-1)
    entity_descriptors = descriptors[inputs.entity_ids]
    entity_rows = torch.cat((inputs.entity_features, entity_descriptors), dim=-1)

    def masked_pool(selected: Tensor) -> tuple[Tensor, Tensor]:
        weights = selected.unsqueeze(-1).to(entity_rows.dtype)
        count = weights.sum(dim=-2).clamp_min(1.0)
        mean = (entity_rows * weights).sum(dim=-2) / count
        maximum = entity_rows.masked_fill(~selected.unsqueeze(-1), -torch.inf).amax(
            dim=-2
        )
        maximum = torch.where(selected.any(dim=-1, keepdim=True), maximum, 0.0)
        return mean, maximum

    visible = inputs.entity_mask
    own_mean, own_max = masked_pool(visible & (inputs.entity_features[..., 2] > 0.5))
    enemy_mean, enemy_max = masked_pool(
        visible & (inputs.entity_features[..., 3] > 0.5)
    )
    hand = descriptors[inputs.hand_ids]
    playable = inputs.hand_ids[..., :NUM_HAND_SLOTS] != 0
    playable_weights = playable.unsqueeze(-1).to(hand.dtype)
    playable_mean = (hand[..., :NUM_HAND_SLOTS, :] * playable_weights).sum(
        dim=-2
    ) / playable_weights.sum(dim=-2).clamp_min(1.0)
    playable_max = (
        hand[..., :NUM_HAND_SLOTS, :]
        .masked_fill(~playable.unsqueeze(-1), -torch.inf)
        .amax(dim=-2)
    )
    playable_max = torch.where(playable.any(dim=-1, keepdim=True), playable_max, 0.0)
    next_card = torch.where(
        (inputs.hand_ids[..., NUM_HAND_SLOTS] != 0).unsqueeze(-1),
        hand[..., NUM_HAND_SLOTS, :],
        0.0,
    )
    return torch.cat(
        (
            own_mean,
            own_max,
            enemy_mean,
            enemy_max,
            playable_mean,
            playable_max,
            next_card,
            inputs.global_features,
        ),
        dim=-1,
    )


def compact_tactical_summary(model: ClasherPolicy, inputs: PolicyInputs) -> Tensor:
    """Summarize public geometry and hand mechanics without card identities."""

    flat_size = inputs.batch_size * inputs.sequence_length
    hand_ids = inputs.hand_ids.reshape(flat_size, -1)[:, :NUM_HAND_SLOTS]
    hand_stats = model.actor_encoder.card_stat_features[hand_ids].reshape(flat_size, -1)
    hand_known = (hand_ids != 0).to(hand_stats.dtype)
    entity = inputs.entity_features.reshape(
        flat_size, inputs.entity_features.shape[-2], -1
    )
    valid = inputs.entity_mask.reshape(flat_size, -1)
    own_troop = valid & (entity[..., 2] > 0.5) & (entity[..., 4] > 0.5)
    enemy_troop = valid & (entity[..., 3] > 0.5) & (entity[..., 4] > 0.5)
    own_building = valid & (entity[..., 2] > 0.5) & (entity[..., 5] > 0.5)
    enemy_building = valid & (entity[..., 3] > 0.5) & (entity[..., 5] > 0.5)
    x = entity[..., 0]
    y = entity[..., 1]
    hp = entity[..., 9]
    left = x < 0.5

    def count(mask: Tensor, scale: float) -> Tensor:
        return mask.sum(dim=-1, dtype=entity.dtype) / scale

    def mean(value: Tensor, mask: Tensor) -> Tensor:
        weights = mask.to(entity.dtype)
        total = (value * weights).sum(dim=-1)
        denominator = weights.sum(dim=-1)
        return torch.where(
            denominator > 0,
            total / denominator.clamp_min(1.0),
            torch.full_like(total, 0.5),
        )

    def front(mask: Tensor, *, enemy: bool) -> Tensor:
        fill = 1.0 if enemy else 0.0
        selected = y.masked_fill(~mask, fill)
        extreme = selected.amin(dim=-1) if enemy else selected.amax(dim=-1)
        return torch.where(mask.any(dim=-1), extreme, torch.full_like(extreme, 0.5))

    entity_summary = torch.stack(
        (
            count(own_troop, 8.0),
            count(enemy_troop, 8.0),
            count(own_building, 4.0),
            count(enemy_building, 4.0),
            count(own_troop & left, 4.0),
            count(own_troop & ~left, 4.0),
            count(enemy_troop & left, 4.0),
            count(enemy_troop & ~left, 4.0),
            count(enemy_troop & (y < 0.5), 4.0),
            count(own_troop & (y > 0.5), 4.0),
            mean(x, own_troop),
            mean(y, own_troop),
            mean(hp, own_troop),
            mean(x, enemy_troop),
            mean(y, enemy_troop),
            mean(hp, enemy_troop),
            front(own_troop & left, enemy=False),
            front(own_troop & ~left, enemy=False),
            front(enemy_troop & left, enemy=True),
            front(enemy_troop & ~left, enemy=True),
        ),
        dim=-1,
    )
    previous_actions = inputs.previous_actions.reshape(flat_size)
    previous_types = torch.where(
        previous_actions < NUM_HAND_SLOTS * NUM_TILES,
        torch.div(previous_actions, NUM_TILES, rounding_mode="floor"),
        NUM_HAND_SLOTS + previous_actions - NUM_HAND_SLOTS * NUM_TILES,
    ).clamp(0, NUM_HAND_SLOTS + 1)
    previous_one_hot = F.one_hot(previous_types, num_classes=NUM_HAND_SLOTS + 2).to(
        hand_stats.dtype
    )
    return torch.cat(
        (
            inputs.global_features.reshape(flat_size, -1)[:, :6],
            hand_stats,
            hand_known,
            entity_summary,
            previous_one_hot,
        ),
        dim=-1,
    )


@torch.no_grad()
def extract_actor_features(
    model: ClasherPolicy,
    corpus: DirectSimpleBehaviorCorpus,
    *,
    device: torch.device,
    sequence_steps: int,
    feature_set: str,
) -> Tensor:
    """Extract current public summaries or replay the frozen recurrent policy."""

    model.eval()
    if feature_set == "public-globals":
        return torch.as_tensor(
            np.asarray(corpus.arrays["global_features"], dtype=np.float32)
        ).clone()
    features: list[Tensor] = []
    for episode in range(corpus.episode_count):
        state = model.initial_state(1, device=device)
        expected_hidden = torch.as_tensor(
            corpus.initial_hidden[episode : episode + 1],
            dtype=state[0].dtype,
            device=device,
        )
        expected_cell = torch.as_tensor(
            corpus.initial_cell[episode : episode + 1],
            dtype=state[1].dtype,
            device=device,
        )
        if not torch.equal(state[0], expected_hidden) or not torch.equal(
            state[1], expected_cell
        ):
            raise ValueError("outcome corpus reset state differs from checkpoint")
        begin = int(corpus.episode_offsets[episode])
        end = int(corpus.episode_offsets[episode + 1])
        for start in range(begin, end, sequence_steps):
            rows = np.arange(start, min(end, start + sequence_steps), dtype=np.int64)[
                None, :
            ]
            inputs = batch_inputs(corpus.arrays, rows, device)
            inputs = replace(
                inputs,
                previous_rewards=torch.zeros_like(inputs.previous_rewards),
            )
            if feature_set in {"structured-summary", "structured-residual"}:
                selected_features = structured_actor_summary(model, inputs)[0]
            elif feature_set == "robust-residual":
                robust = compact_tactical_summary(model, inputs)
                selected_features = torch.cat(
                    (robust, inputs.global_features[0]), dim=-1
                )
            elif feature_set == "policy-plus-public-globals":
                output = model(inputs, state)
                if output.repair_features is None:
                    raise ValueError("base policy does not expose actor-visible state")
                selected_features = torch.cat(
                    (output.repair_features[0], inputs.global_features[0]), dim=-1
                )
                state = (output.next_state[0].detach(), output.next_state[1].detach())
            else:
                raise ValueError("unknown actor outcome feature set")
            features.append(selected_features.detach().cpu())
    result = torch.cat(features, dim=0)
    if result.shape[0] != corpus.row_count:
        raise ValueError("actor feature extraction lost outcome rows")
    return result


def _ece(probabilities: Tensor, targets: Tensor, bins: int = 10) -> float:
    confidence, prediction = probabilities.max(dim=1)
    correct = prediction == targets
    total = max(1, targets.numel())
    value = torch.zeros((), dtype=probabilities.dtype)
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        selected = (confidence >= low) & (
            confidence <= high if index == bins - 1 else confidence < high
        )
        if bool(selected.any()):
            value += (
                selected.sum()
                / total
                * (confidence[selected].mean() - correct[selected].float().mean()).abs()
            )
    return float(value)


def _binary_auc(labels: Tensor, scores: Tensor) -> float | None:
    labels = labels.to(torch.bool)
    positives = int(labels.sum())
    negatives = int((~labels).sum())
    if positives == 0 or negatives == 0:
        return None
    comparisons = scores[labels][:, None] - scores[~labels][None, :]
    return float(((comparisons > 0).float() + 0.5 * (comparisons == 0)).mean())


def bootstrap_binary_auc(
    labels: np.ndarray,
    scores: np.ndarray,
    *,
    seed: int,
    replicates: int,
    clusters: np.ndarray | None = None,
) -> dict[str, float | int] | None:
    """Return a deterministic AUC interval over rows or independent clusters."""

    binary = np.asarray(labels, dtype=np.bool_)
    values = np.asarray(scores, dtype=np.float64)
    if binary.ndim != 1 or values.shape != binary.shape or replicates < 1:
        raise ValueError("bootstrap labels/scores/replicates are invalid")
    cluster_values = None if clusters is None else np.asarray(clusters)
    if cluster_values is not None and cluster_values.shape != binary.shape:
        raise ValueError("bootstrap clusters do not match labels")
    if not np.isfinite(values).all() or not binary.any() or binary.all():
        return None

    def auc(sample_labels: np.ndarray, sample_scores: np.ndarray) -> float:
        positive = sample_scores[sample_labels]
        negative = sample_scores[~sample_labels]
        differences = positive[:, None] - negative[None, :]
        return float(((differences > 0) + 0.5 * (differences == 0)).mean())

    point = auc(binary, values)
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    unique_clusters = (
        np.arange(binary.size) if cluster_values is None else np.unique(cluster_values)
    )
    cluster_rows = [
        (
            np.asarray([int(cluster)], dtype=np.int64)
            if cluster_values is None
            else np.flatnonzero(cluster_values == cluster)
        )
        for cluster in unique_clusters
    ]
    for _ in range(replicates):
        sampled_clusters = rng.integers(0, len(cluster_rows), size=len(cluster_rows))
        rows = np.concatenate([cluster_rows[index] for index in sampled_clusters])
        sampled_labels = binary[rows]
        if sampled_labels.any() and not sampled_labels.all():
            estimates.append(auc(sampled_labels, values[rows]))
    if len(estimates) < max(1, replicates // 2):
        return None
    interval = np.asarray(estimates, dtype=np.float64)
    return {
        "point": point,
        "lower_95": float(np.quantile(interval, 0.025)),
        "upper_95": float(np.quantile(interval, 0.975)),
        "valid_replicates": len(estimates),
        "requested_replicates": replicates,
        "independent_clusters": len(cluster_rows),
    }


@torch.no_grad()
def phase_auc_confidence_intervals(
    head: ActorOutcomeHead,
    features: Tensor,
    outcomes: Tensor,
    phases: np.ndarray,
    *,
    device: torch.device,
    seed: int,
    replicates: int,
    clusters: np.ndarray | None = None,
) -> dict[str, dict[str, float | int] | None]:
    """Bootstrap decisive AUC on phase samples, optionally by matchup cluster."""

    probabilities = head(features.to(device)).outcome_logits.softmax(dim=-1).cpu()
    utility = (probabilities[:, 2] - probabilities[:, 0]).numpy()
    labels = outcomes.cpu().numpy()
    cluster_values = None if clusters is None else np.asarray(clusters)
    if cluster_values is not None and cluster_values.shape != labels.shape:
        raise ValueError("phase AUC clusters do not match outcome rows")
    result: dict[str, dict[str, float | int] | None] = {}
    for index, phase in enumerate(("early", "middle", "late")):
        selected = (phases == phase) & (labels != 0)
        result[phase] = bootstrap_binary_auc(
            labels[selected] == 1,
            utility[selected],
            seed=seed + index,
            replicates=replicates,
            clusters=(None if cluster_values is None else cluster_values[selected]),
        )
    return result


def all_phase_auc_confidence_passed(
    intervals: dict[str, dict[str, float | int] | None],
    *,
    minimum_lower_95: float,
    minimum_clusters: int,
) -> bool:
    """Require both above-chance confidence and enough independent matchups."""

    return all(
        intervals.get(phase) is not None
        and float(intervals[phase]["lower_95"]) > minimum_lower_95  # type: ignore[index]
        and int(intervals[phase]["independent_clusters"])  # type: ignore[index]
        >= minimum_clusters
        for phase in ("early", "middle", "late")
    )


def outcome_epoch_selection_key(
    validation: dict[str, Any],
    *,
    acceptance_passed: bool,
    by_phase: dict[str, dict[str, Any]] | None = None,
) -> tuple[int, float, float, float]:
    """Prefer the strongest worst phase before aggregate ranking/calibration."""

    decisive_auc = validation["decisive_win_loss_auc"]
    phase_aucs = (
        [
            by_phase.get(phase, {}).get("decisive_win_loss_auc")
            for phase in ("early", "middle", "late")
        ]
        if by_phase is not None
        else []
    )
    minimum_phase_auc = (
        min(float(value) for value in phase_aucs if value is not None)
        if len(phase_aucs) == 3 and all(value is not None for value in phase_aucs)
        else -math.inf
    )
    return (
        int(acceptance_passed),
        minimum_phase_auc,
        float(decisive_auc) if decisive_auc is not None else -math.inf,
        -float(validation["nll"]),
    )


def margin_epoch_selection_key(
    validation: dict[str, Any],
    *,
    acceptance_passed: bool,
) -> tuple[int, float, float]:
    """Prefer aggregate improvement only among all-phase-valid margin epochs."""

    return (
        int(acceptance_passed),
        float(validation["tower_margin_mae_improvement"]),
        -float(validation["tower_margin_mae"]),
    )


@torch.no_grad()
def fit_probability_shrinkage(
    head: ActorOutcomeHead,
    features: Tensor,
    outcomes: Tensor,
    *,
    device: torch.device,
) -> float:
    """Fit rank-preserving shrinkage on a physically separate calibration set."""

    if outcomes.numel() < 2 or not bool(
        torch.isin(outcomes, torch.tensor([-1, 0, 1])).all()
    ):
        raise ValueError("probability calibration outcomes are invalid")
    head.set_probability_shrinkage(1.0)
    probabilities = head(features.to(device)).outcome_logits.exp()
    prior = head.outcome_probability_prior.to(device=device, dtype=probabilities.dtype)
    shrinkages = torch.linspace(0.0, 1.0, 401, device=device, dtype=probabilities.dtype)
    candidates = (
        shrinkages[:, None, None] * probabilities.unsqueeze(0)
        + (1.0 - shrinkages[:, None, None]) * prior[None, None, :]
    )
    targets = (outcomes.to(device=device, dtype=torch.long) + 1)[None, :, None]
    selected = candidates.gather(2, targets.expand(shrinkages.numel(), -1, 1))
    losses = -selected.squeeze(-1).clamp_min(1e-12).log().mean(dim=1)
    shrinkage = float(shrinkages[int(losses.argmin())].cpu())
    head.set_probability_shrinkage(shrinkage)
    return shrinkage


def all_phase_decisive_auc_passed(
    by_phase: dict[str, dict[str, Any]], minimum_auc: float
) -> bool:
    """Require evidence above chance in every decision-relevant game phase."""

    return all(
        phase in by_phase
        and by_phase[phase]["decisive_win_loss_auc"] is not None
        and float(by_phase[phase]["decisive_win_loss_auc"]) >= minimum_auc
        for phase in ("early", "middle", "late")
    )


def all_phase_margin_nonregression_passed(
    by_phase: dict[str, dict[str, Any]], maximum_regression: float
) -> bool:
    return all(
        phase in by_phase
        and float(by_phase[phase]["tower_margin_mae_improvement"])
        >= -maximum_regression
        for phase in ("early", "middle", "late")
    )


@torch.no_grad()
def metrics(
    head: ActorOutcomeHead,
    features: Tensor,
    outcomes: Tensor,
    margins: Tensor,
    *,
    device: torch.device,
) -> dict[str, Any]:
    head.eval()
    prediction = head(features.to(device))
    target = outcomes.to(device=device, dtype=torch.long) + 1
    probabilities = prediction.outcome_logits.softmax(dim=-1).cpu()
    target_cpu = target.cpu()
    one_hot = F.one_hot(target_cpu, num_classes=3).to(probabilities.dtype)
    selected = probabilities.gather(1, target_cpu[:, None]).squeeze(1)
    predicted_margin = prediction.terminal_tower_margin.cpu()
    public_globals = features[..., -18:]
    baseline_margin = (
        public_globals[..., 8:11].sum(dim=-1) - public_globals[..., 11:14].sum(dim=-1)
    ) / 3.0
    baseline_margin_mae = float((baseline_margin - margins).abs().mean())
    predicted_margin_mae = float((predicted_margin - margins).abs().mean())
    labels = ("loss", "draw", "win")
    decisive = target_cpu != 1
    decisive_auc = (
        _binary_auc(
            target_cpu[decisive] == 2,
            (probabilities[decisive, 2] - probabilities[decisive, 0]),
        )
        if bool(decisive.any())
        else None
    )
    return {
        "rows": int(target.numel()),
        "class_counts": {
            label: int((target_cpu == index).sum())
            for index, label in enumerate(labels)
        },
        "nll": float(-selected.clamp_min(1e-12).log().mean()),
        "brier": float((probabilities - one_hot).square().sum(dim=1).mean()),
        "accuracy": float((probabilities.argmax(dim=1) == target_cpu).float().mean()),
        "ece_10": _ece(probabilities, target_cpu),
        "auc_one_vs_rest": {
            label: _binary_auc(target_cpu == index, probabilities[:, index])
            for index, label in enumerate(labels)
        },
        "decisive_win_loss_auc": decisive_auc,
        "mean_outcome_probability": {
            label: float(probabilities[:, index].mean())
            for index, label in enumerate(labels)
        },
        "tower_margin_mae": predicted_margin_mae,
        "tower_margin_rmse": float((predicted_margin - margins).square().mean().sqrt()),
        "tower_margin_baseline_mae": baseline_margin_mae,
        "tower_margin_mae_improvement": baseline_margin_mae - predicted_margin_mae,
    }


def _bucket_metrics(
    head: ActorOutcomeHead,
    features: Tensor,
    outcomes: Tensor,
    margins: Tensor,
    groups: NDArray[np.str_],
    *,
    device: torch.device,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for group in sorted(set(groups.tolist())):
        rows = torch.as_tensor(np.flatnonzero(groups == group), dtype=torch.long)
        result[group] = metrics(
            head,
            features.index_select(0, rows),
            outcomes.index_select(0, rows),
            margins.index_select(0, rows),
            device=device,
        )
    return result


def phase_balanced_row_indices(
    loaded: list[tuple[dict[str, Any], DirectSimpleBehaviorCorpus]],
) -> Tensor:
    """Select at most one representative row per episode and game phase."""

    selected: list[int] = []
    row_offset = 0
    bins = (
        (0.0, 1.0 / 3.0, 1.0 / 6.0),
        (1.0 / 3.0, 2.0 / 3.0, 0.5),
        (2.0 / 3.0, math.inf, 5.0 / 6.0),
    )
    for _metadata, corpus in loaded:
        progress = np.asarray(corpus.arrays["global_features"][:, 0])
        for begin, end in zip(
            corpus.episode_offsets[:-1], corpus.episode_offsets[1:], strict=True
        ):
            episode_progress = progress[begin:end]
            for lower, upper, center in bins:
                candidates = np.flatnonzero(
                    (episode_progress >= lower) & (episode_progress < upper)
                )
                if candidates.size:
                    nearest = candidates[
                        np.argmin(np.abs(episode_progress[candidates] - center))
                    ]
                    selected.append(row_offset + int(begin) + int(nearest))
        row_offset += corpus.row_count
    if not selected:
        raise ValueError("validation corpora contain no phase-balanced rows")
    return torch.as_tensor(selected, dtype=torch.long)


def phase_balanced_matchup_clusters(
    loaded: list[tuple[dict[str, Any], DirectSimpleBehaviorCorpus]],
) -> np.ndarray:
    """Name the seed/style/deck/ordinal cluster for every selected phase row."""

    clusters: list[str] = []
    for metadata, corpus in loaded:
        source = _outcome_source(metadata)
        seed = int(metadata["seed"])
        progress = np.asarray(corpus.arrays["global_features"][:, 0])
        opponents = [str(value) for value in metadata.get("opponents", [])]
        decks = [str(value) for value in metadata.get("opponent_decks", [])]
        for episode, (begin, end) in enumerate(
            zip(corpus.episode_offsets[:-1], corpus.episode_offsets[1:], strict=True)
        ):
            if source == "natural-strategy-games":
                opponent_index = int(
                    corpus.episode_arrays["episode_opponent_indices"][episode]
                )
                deck_index = int(
                    corpus.episode_arrays["episode_opponent_deck_indices"][episode]
                )
                opponent = opponents[opponent_index]
                deck = decks[deck_index]
            else:
                opponent = "<controlled-draw>"
                deck = "<controlled-draw>"
            ordinal = int(corpus.episode_ordinals[episode])
            cluster = f"{source}|{seed}|{opponent}|{deck}|{ordinal}"
            episode_progress = progress[begin:end]
            for lower, upper in (
                (0.0, 1.0 / 3.0),
                (1.0 / 3.0, 2.0 / 3.0),
                (2.0 / 3.0, math.inf),
            ):
                if bool(
                    ((episode_progress >= lower) & (episode_progress < upper)).any()
                ):
                    clusters.append(cluster)
    result = np.asarray(clusters, dtype=np.str_)
    if result.shape != (phase_balanced_row_indices(loaded).numel(),):
        raise ValueError("phase-balanced matchup clusters lost rows")
    return result


def _evaluation_breakdowns(
    head: ActorOutcomeHead,
    features: Tensor,
    outcomes: Tensor,
    margins: Tensor,
    loaded: list[tuple[dict[str, Any], DirectSimpleBehaviorCorpus]],
    *,
    device: torch.device,
) -> dict[str, Any]:
    phase_fraction = np.concatenate(
        [
            np.asarray(corpus.arrays["global_features"][:, 0])
            for _metadata, corpus in loaded
        ]
    )
    phases = np.where(
        phase_fraction < 1.0 / 3.0,
        "early",
        np.where(phase_fraction < 2.0 / 3.0, "middle", "late"),
    )
    opponents = np.concatenate(
        [
            np.asarray(metadata["opponents"], dtype=np.str_)[
                _episode_rows(
                    corpus,
                    corpus.episode_arrays["episode_opponent_indices"],
                )
            ]
            for metadata, corpus in loaded
        ]
    )
    seats = np.concatenate(
        [
            _episode_rows(
                corpus,
                corpus.episode_arrays["episode_learner_players"],
            ).astype(str)
            for _metadata, corpus in loaded
        ]
    )
    sources = np.concatenate(
        [
            np.full(corpus.row_count, _outcome_source(metadata), dtype="<U32")
            for metadata, corpus in loaded
        ]
    )
    row_offsets = np.cumsum(
        [0] + [corpus.row_count for _metadata, corpus in loaded[:-1]]
    )
    endpoint_rows = torch.as_tensor(
        np.concatenate(
            [
                corpus.episode_offsets[1:] - 1 + row_offset
                for row_offset, (_metadata, corpus) in zip(
                    row_offsets, loaded, strict=True
                )
            ]
        ),
        dtype=torch.long,
    )
    opponent_decks = np.concatenate(
        [
            (
                np.asarray(metadata["opponent_decks"], dtype=np.str_)[
                    _episode_rows(
                        corpus,
                        corpus.episode_arrays["episode_opponent_deck_indices"],
                    )
                ]
                if "episode_opponent_deck_indices" in corpus.episode_arrays
                and "opponent_decks" in metadata
                else np.full(corpus.row_count, "<controlled-draw>", dtype="<U32")
            )
            for metadata, corpus in loaded
        ]
    )
    endpoint_sources = sources[endpoint_rows.numpy()]
    endpoint_features = features.index_select(0, endpoint_rows)
    endpoint_outcomes = outcomes.index_select(0, endpoint_rows)
    endpoint_margins = margins.index_select(0, endpoint_rows)
    phase_rows = phase_balanced_row_indices(loaded)
    phase_features = features.index_select(0, phase_rows)
    phase_outcomes = outcomes.index_select(0, phase_rows)
    phase_margins = margins.index_select(0, phase_rows)
    phase_groups = phases[phase_rows.numpy()]
    phase_sources = sources[phase_rows.numpy()]
    return {
        "overall": metrics(head, features, outcomes, margins, device=device),
        "by_phase": _bucket_metrics(
            head, features, outcomes, margins, phases, device=device
        ),
        "by_opponent": _bucket_metrics(
            head, features, outcomes, margins, opponents, device=device
        ),
        "by_seat": _bucket_metrics(
            head, features, outcomes, margins, seats, device=device
        ),
        "by_source": _bucket_metrics(
            head, features, outcomes, margins, sources, device=device
        ),
        "by_opponent_deck": _bucket_metrics(
            head, features, outcomes, margins, opponent_decks, device=device
        ),
        "by_opponent_and_deck": _bucket_metrics(
            head,
            features,
            outcomes,
            margins,
            np.char.add(np.char.add(opponents, "|"), opponent_decks),
            device=device,
        ),
        "phase_balanced": metrics(
            head,
            phase_features,
            phase_outcomes,
            phase_margins,
            device=device,
        ),
        "phase_balanced_by_phase": _bucket_metrics(
            head,
            phase_features,
            phase_outcomes,
            phase_margins,
            phase_groups,
            device=device,
        ),
        "phase_balanced_by_source": _bucket_metrics(
            head,
            phase_features,
            phase_outcomes,
            phase_margins,
            phase_sources,
            device=device,
        ),
        "episode_endpoints": metrics(
            head,
            endpoint_features,
            endpoint_outcomes,
            endpoint_margins,
            device=device,
        ),
        "episode_endpoints_by_source": _bucket_metrics(
            head,
            endpoint_features,
            endpoint_outcomes,
            endpoint_margins,
            endpoint_sources,
            device=device,
        ),
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".json",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".pt",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
    try:
        torch.save(payload, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-checkpoint", type=Path, required=True)
    parser.add_argument("--train-corpus", type=Path, action="append", required=True)
    parser.add_argument(
        "--validation-corpus", type=Path, action="append", required=True
    )
    parser.add_argument("--calibration-corpus", type=Path, action="append", default=[])
    parser.add_argument("--holdout-corpus", type=Path, action="append", default=[])
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--sequence-steps", type=int, default=128)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--structured-residual-scale", type=float, default=0.25)
    parser.add_argument("--margin-residual-scale", type=float, default=0.0)
    parser.add_argument("--initialize-public-checkpoint", type=Path, default=None)
    parser.add_argument(
        "--minimum-structured-residual-auc-gain", type=float, default=0.0
    )
    parser.add_argument(
        "--feature-set",
        choices=(
            "public-globals",
            "structured-summary",
            "structured-residual",
            "robust-residual",
            "policy-plus-public-globals",
        ),
        default="policy-plus-public-globals",
    )
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--margin-coefficient", type=float, default=0.25)
    parser.add_argument("--phase-balanced-outcome-training", action="store_true")
    parser.add_argument("--phase-balanced-margin-training", action="store_true")
    parser.add_argument("--loss-class-mass", type=float, default=0.45)
    parser.add_argument("--draw-class-mass", type=float, default=0.10)
    parser.add_argument("--win-class-mass", type=float, default=0.45)
    parser.add_argument("--minimum-nll-improvement", type=float, default=0.02)
    parser.add_argument("--maximum-ece", type=float, default=0.20)
    parser.add_argument("--maximum-margin-mae", type=float, default=0.25)
    parser.add_argument("--minimum-margin-mae-improvement", type=float, default=0.005)
    parser.add_argument(
        "--maximum-phase-margin-mae-regression", type=float, default=0.01
    )
    parser.add_argument("--minimum-natural-auc", type=float, default=0.60)
    parser.add_argument("--minimum-natural-phase-auc", type=float, default=0.55)
    parser.add_argument("--minimum-phase-auc-lower-bound", type=float, default=0.50)
    parser.add_argument("--phase-auc-bootstrap-replicates", type=int, default=2000)
    parser.add_argument("--minimum-phase-bootstrap-clusters", type=int, default=8)
    parser.add_argument("--minimum-controlled-draw-auc", type=float, default=0.80)
    parser.add_argument(
        "--minimum-controlled-draw-endpoint-probability-lift",
        type=float,
        default=0.03,
    )
    parser.add_argument("--maximum-natural-draw-probability", type=float, default=0.10)
    parser.add_argument("--require-disjoint-natural-opponents", action="store_true")
    parser.add_argument("--require-disjoint-natural-decks", action="store_true")
    args = parser.parse_args()
    if args.output_checkpoint.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite actor-outcome artifacts")
    if min(args.epochs, args.batch_size, args.sequence_steps, args.hidden_size) < 1:
        raise ValueError("actor-outcome training sizes must be positive")
    if args.structured_residual_scale < 0.0:
        raise ValueError("structured residual scale must be nonnegative")
    if args.margin_residual_scale < 0.0:
        raise ValueError("margin residual scale must be nonnegative")
    if args.minimum_structured_residual_auc_gain < 0.0:
        raise ValueError("structured residual AUC gain must be nonnegative")
    if args.minimum_margin_mae_improvement < 0.0:
        raise ValueError("margin MAE improvement must be nonnegative")
    if args.maximum_phase_margin_mae_regression < 0.0:
        raise ValueError("phase margin MAE regression must be nonnegative")
    if args.phase_auc_bootstrap_replicates < 100:
        raise ValueError("phase AUC bootstrap needs at least 100 replicates")
    if args.minimum_phase_bootstrap_clusters < 2:
        raise ValueError("phase AUC bootstrap needs at least two clusters")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device(args.device)
    payload, model = load_model(args.base_checkpoint, device)
    train_loaded = [
        load_direct_simple_behavior_corpus(path) for path in args.train_corpus
    ]
    validation_loaded = [
        load_direct_simple_behavior_corpus(path) for path in args.validation_corpus
    ]
    calibration_loaded = [
        load_direct_simple_behavior_corpus(path) for path in args.calibration_corpus
    ]
    holdout_loaded = [
        load_direct_simple_behavior_corpus(path) for path in args.holdout_corpus
    ]
    for metadata, corpus in (
        *train_loaded,
        *calibration_loaded,
        *validation_loaded,
        *holdout_loaded,
    ):
        validate_outcome_corpus(metadata, corpus)
        if metadata.get("checkpoint_sha256") != file_sha256(args.base_checkpoint):
            raise ValueError("outcome corpus was collected by a different policy")
    train_seeds = {int(metadata["seed"]) for metadata, _corpus in train_loaded}
    validation_seeds = {
        int(metadata["seed"]) for metadata, _corpus in validation_loaded
    }
    calibration_seeds = {
        int(metadata["seed"]) for metadata, _corpus in calibration_loaded
    }
    holdout_seeds = {int(metadata["seed"]) for metadata, _corpus in holdout_loaded}
    if train_seeds.intersection(validation_seeds | calibration_seeds):
        raise ValueError("outcome train and validation seeds must be disjoint")
    if validation_seeds.intersection(calibration_seeds):
        raise ValueError("outcome calibration and validation seeds must be disjoint")
    if (
        train_seeds.intersection(holdout_seeds)
        or validation_seeds.intersection(holdout_seeds)
        or calibration_seeds.intersection(holdout_seeds)
    ):
        raise ValueError(
            "outcome holdout seeds must be disjoint from train/development"
        )
    train_hashes = {file_sha256(path) for path in args.train_corpus}
    validation_hashes = {file_sha256(path) for path in args.validation_corpus}
    calibration_hashes = {file_sha256(path) for path in args.calibration_corpus}
    holdout_hashes = {file_sha256(path) for path in args.holdout_corpus}
    if train_hashes.intersection(validation_hashes | calibration_hashes):
        raise ValueError("outcome train and validation corpora must be disjoint")
    if validation_hashes.intersection(calibration_hashes):
        raise ValueError("outcome calibration and validation corpora must be disjoint")
    if holdout_hashes.intersection(
        train_hashes | calibration_hashes | validation_hashes
    ):
        raise ValueError("outcome holdout corpora must be physically disjoint")
    train_natural_opponents = _natural_metadata_values(train_loaded, "opponents")
    validation_natural_opponents = _natural_metadata_values(
        validation_loaded, "opponents"
    )
    calibration_natural_opponents = _natural_metadata_values(
        calibration_loaded, "opponents"
    )
    train_natural_decks = _natural_metadata_values(train_loaded, "opponent_decks")
    validation_natural_decks = _natural_metadata_values(
        validation_loaded, "opponent_decks"
    )
    calibration_natural_decks = _natural_metadata_values(
        calibration_loaded, "opponent_decks"
    )
    holdout_natural_opponents = _natural_metadata_values(holdout_loaded, "opponents")
    holdout_natural_decks = _natural_metadata_values(holdout_loaded, "opponent_decks")
    opponent_overlap = train_natural_opponents & validation_natural_opponents
    deck_overlap = train_natural_decks & validation_natural_decks
    calibration_opponent_overlap = (
        train_natural_opponents & calibration_natural_opponents
    )
    calibration_deck_overlap = train_natural_decks & calibration_natural_decks
    if args.require_disjoint_natural_opponents and opponent_overlap:
        raise ValueError("natural outcome train/validation opponents overlap")
    if args.require_disjoint_natural_decks and deck_overlap:
        raise ValueError("natural outcome train/validation decks overlap")
    if args.require_disjoint_natural_opponents and calibration_opponent_overlap:
        raise ValueError("natural outcome train/calibration opponents overlap")
    if args.require_disjoint_natural_decks and calibration_deck_overlap:
        raise ValueError("natural outcome train/calibration decks overlap")
    holdout_opponent_overlap = train_natural_opponents & holdout_natural_opponents
    holdout_deck_overlap = train_natural_decks & holdout_natural_decks
    if args.require_disjoint_natural_opponents and holdout_opponent_overlap:
        raise ValueError("natural outcome train/holdout opponents overlap")
    if args.require_disjoint_natural_decks and holdout_deck_overlap:
        raise ValueError("natural outcome train/holdout decks overlap")
    started = time.monotonic()
    train_features = torch.cat(
        [
            extract_actor_features(
                model,
                corpus,
                device=device,
                sequence_steps=args.sequence_steps,
                feature_set=args.feature_set,
            )
            for _metadata, corpus in train_loaded
        ],
        dim=0,
    )
    validation_features = torch.cat(
        [
            extract_actor_features(
                model,
                corpus,
                device=device,
                sequence_steps=args.sequence_steps,
                feature_set=args.feature_set,
            )
            for _metadata, corpus in validation_loaded
        ],
        dim=0,
    )
    calibration_features = (
        torch.cat(
            [
                extract_actor_features(
                    model,
                    corpus,
                    device=device,
                    sequence_steps=args.sequence_steps,
                    feature_set=args.feature_set,
                )
                for _metadata, corpus in calibration_loaded
            ],
            dim=0,
        )
        if calibration_loaded
        else None
    )
    holdout_features = (
        torch.cat(
            [
                extract_actor_features(
                    model,
                    corpus,
                    device=device,
                    sequence_steps=args.sequence_steps,
                    feature_set=args.feature_set,
                )
                for _metadata, corpus in holdout_loaded
            ],
            dim=0,
        )
        if holdout_loaded
        else None
    )
    for name, feature_rows in (
        ("train", train_features),
        ("calibration", calibration_features),
        ("validation", validation_features),
        ("holdout", holdout_features),
    ):
        if feature_rows is not None and not bool(torch.isfinite(feature_rows).all()):
            raise ValueError(f"{name} actor features contain non-finite values")
    state_size = int(train_features.shape[1])
    separate_draw_trunk = args.feature_set == "structured-summary"
    structured_residual_scale = (
        args.structured_residual_scale
        if args.feature_set in {"structured-residual", "robust-residual"}
        else 0.0
    )
    head = ActorOutcomeHead(
        state_size,
        args.hidden_size,
        separate_draw_trunk=separate_draw_trunk,
        structured_residual_scale=structured_residual_scale,
        margin_residual_scale=args.margin_residual_scale,
    ).to(device)
    public_initialization_sha256: str | None = None
    if args.initialize_public_checkpoint is not None:
        if args.feature_set not in {"structured-residual", "robust-residual"}:
            raise ValueError(
                "public initialization is only valid for structured residual"
            )
        initialized = torch.load(
            args.initialize_public_checkpoint, map_location="cpu", weights_only=False
        )
        initialized_report = initialized.get("training_report")
        if (
            initialized.get("schema") != SCHEMA
            or initialized.get("base_checkpoint_sha256")
            != file_sha256(args.base_checkpoint)
            or initialized.get("state_size") != 18
            or not isinstance(initialized_report, dict)
            or initialized_report.get("status")
            not in {"accepted-development", "accepted-holdout"}
            or initialized_report.get("actor_feature_contract") != "public-globals"
            or initialized_report.get("selection_gates", {}).get(
                "natural_phase_auc_passed"
            )
            is not True
            or initialized_report.get("selection_gates", {}).get(
                "phase_auc_confidence_passed"
            )
            is not True
        ):
            raise ValueError(
                "public initialization checkpoint is not accepted/compatible"
            )
        initialized_state = initialized["outcome_head_state_dict"]
        current_state = head.state_dict()
        global_prefixes = (
            "trunk.",
            "draw.",
            "decisive_win.",
            "margin_trunk.",
        )
        for name, value in initialized_state.items():
            if name.startswith(global_prefixes):
                if (
                    name not in current_state
                    or current_state[name].shape != value.shape
                ):
                    raise ValueError("public initialization architecture changed")
                current_state[name] = value
        head.load_state_dict(current_state, strict=True)
        for name, parameter in head.named_parameters():
            if name.startswith(global_prefixes):
                parameter.requires_grad_(False)
        public_initialization_sha256 = file_sha256(args.initialize_public_checkpoint)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in head.parameters() if parameter.requires_grad],
        lr=args.learning_rate,
        weight_decay=1e-4,
    )
    train_outcomes = torch.cat(
        [
            torch.as_tensor(corpus.arrays["final_outcomes"])
            for _metadata, corpus in train_loaded
        ]
    )
    train_margins = torch.cat(
        [
            torch.as_tensor(corpus.arrays["terminal_tower_margins"])
            for _metadata, corpus in train_loaded
        ]
    )
    target_class_mass = (
        args.loss_class_mass,
        args.draw_class_mass,
        args.win_class_mass,
    )
    train_weights = episode_class_balanced_row_weights(
        train_loaded,
        target_class_mass=target_class_mass,
        phase_balanced=args.phase_balanced_outcome_training,
    )
    margin_train_weights = episode_balanced_row_weights(
        train_loaded, phase_balanced=args.phase_balanced_margin_training
    )
    validation_outcomes = torch.cat(
        [
            torch.as_tensor(corpus.arrays["final_outcomes"])
            for _metadata, corpus in validation_loaded
        ]
    )
    validation_margins = torch.cat(
        [
            torch.as_tensor(corpus.arrays["terminal_tower_margins"])
            for _metadata, corpus in validation_loaded
        ]
    )
    calibration_outcomes = (
        torch.cat(
            [
                torch.as_tensor(corpus.arrays["final_outcomes"])
                for _metadata, corpus in calibration_loaded
            ]
        )
        if calibration_loaded
        else None
    )
    holdout_outcomes = (
        torch.cat(
            [
                torch.as_tensor(corpus.arrays["final_outcomes"])
                for _metadata, corpus in holdout_loaded
            ]
        )
        if holdout_loaded
        else None
    )
    holdout_margins = (
        torch.cat(
            [
                torch.as_tensor(corpus.arrays["terminal_tower_margins"])
                for _metadata, corpus in holdout_loaded
            ]
        )
        if holdout_loaded
        else None
    )
    train_episode_outcomes = torch.cat(
        [
            torch.as_tensor(corpus.episode_arrays["episode_final_outcomes"])
            for _metadata, corpus in train_loaded
        ]
    )
    counts = torch.bincount(
        train_episode_outcomes.to(torch.long) + 1, minlength=3
    ).float()
    prior = counts / counts.sum()
    head.set_prior_calibration(
        prior.to(device),
        torch.as_tensor(target_class_mass, dtype=prior.dtype, device=device),
    )
    calibration_rows = (
        phase_balanced_row_indices(calibration_loaded) if calibration_loaded else None
    )

    def recalibrate_probabilities() -> float:
        if calibration_rows is None:
            head.set_probability_shrinkage(1.0)
            return 1.0
        assert calibration_features is not None and calibration_outcomes is not None
        return fit_probability_shrinkage(
            head,
            calibration_features.index_select(0, calibration_rows),
            calibration_outcomes.index_select(0, calibration_rows),
            device=device,
        )

    current_shrinkage = recalibrate_probabilities()
    validation_phase_rows = phase_balanced_row_indices(validation_loaded)
    validation_phase_outcomes = validation_outcomes.index_select(
        0, validation_phase_rows
    )
    prior_nll = float(
        -prior[(validation_phase_outcomes.to(torch.long) + 1)]
        .clamp_min(1e-12)
        .log()
        .mean()
    )
    rng = np.random.default_rng(args.seed)
    initial_breakdowns = _evaluation_breakdowns(
        head,
        validation_features,
        validation_outcomes,
        validation_margins,
        validation_loaded,
        device=device,
    )
    initial_validation = initial_breakdowns["phase_balanced"]
    structured_baseline_auc = (
        float(initial_validation["decisive_win_loss_auc"])
        if args.feature_set in {"structured-residual", "robust-residual"}
        and args.initialize_public_checkpoint is not None
        else None
    )
    history: list[dict[str, Any]] = [
        {
            "epoch": 0,
            "training_loss": None,
            "validation": initial_validation,
            "all_row_validation": initial_breakdowns["overall"],
            "outcome_gate_passed": False,
            "margin_gate_passed": False,
            "development_gate_passed": False,
            "probability_shrinkage": current_shrinkage,
        }
    ]
    best_key = outcome_epoch_selection_key(
        initial_validation,
        acceptance_passed=False,
        by_phase=initial_breakdowns["phase_balanced_by_phase"],
    )
    best_epoch: int | None = 0
    best_state: dict[str, Tensor] | None = {
        name: value.detach().cpu().clone() for name, value in head.state_dict().items()
    }
    best_metrics: dict[str, Any] | None = initial_validation
    best_margin_epoch = 0
    best_margin_key = margin_epoch_selection_key(
        initial_validation, acceptance_passed=False
    )
    best_margin_state = {
        name: value.detach().cpu().clone()
        for name, value in head.state_dict().items()
        if name.startswith("margin_trunk.")
    }
    for epoch in range(1, args.epochs + 1):
        head.train()
        order = rng.permutation(train_outcomes.numel())
        losses = []
        for start in range(0, len(order), args.batch_size):
            rows = torch.as_tensor(order[start : start + args.batch_size])
            prediction = head(
                train_features.index_select(0, rows).to(device), calibrated=False
            )
            loss = actor_outcome_loss(
                prediction,
                train_outcomes.index_select(0, rows).to(device),
                train_margins.index_select(0, rows).to(device),
                margin_coefficient=args.margin_coefficient,
                sample_weights=train_weights.index_select(0, rows).to(device),
                margin_sample_weights=margin_train_weights.index_select(0, rows).to(
                    device
                ),
            )
            if not bool(torch.isfinite(loss.total)):
                raise RuntimeError("actor outcome loss became non-finite")
            optimizer.zero_grad(set_to_none=True)
            loss.total.backward()
            torch.nn.utils.clip_grad_norm_(
                head.parameters(), 1.0, error_if_nonfinite=True
            )
            optimizer.step()
            losses.append(float(loss.total.detach()))
        current_shrinkage = recalibrate_probabilities()
        epoch_breakdowns = _evaluation_breakdowns(
            head,
            validation_features,
            validation_outcomes,
            validation_margins,
            validation_loaded,
            device=device,
        )
        validation = epoch_breakdowns["phase_balanced"]
        epoch_sources = epoch_breakdowns["phase_balanced_by_source"]
        epoch_phases = epoch_breakdowns["phase_balanced_by_phase"]
        epoch_endpoints = epoch_breakdowns["episode_endpoints_by_source"]
        epoch_natural = epoch_sources.get("natural-strategy-games")
        epoch_natural_endpoint = epoch_endpoints.get("natural-strategy-games")
        epoch_draw_endpoint = epoch_endpoints.get("controlled-symmetric-draws")
        epoch_natural_auc_passed = bool(
            epoch_natural is not None
            and epoch_natural["decisive_win_loss_auc"] is not None
            and float(epoch_natural["decisive_win_loss_auc"])
            >= args.minimum_natural_auc
        )
        epoch_natural_phase_auc_passed = all_phase_decisive_auc_passed(
            epoch_phases, args.minimum_natural_phase_auc
        )
        epoch_controlled_draw_passed = bool(
            validation["auc_one_vs_rest"]["draw"] is not None
            and float(validation["auc_one_vs_rest"]["draw"])
            >= args.minimum_controlled_draw_auc
            and epoch_natural is not None
            and float(epoch_natural["mean_outcome_probability"]["draw"])
            <= args.maximum_natural_draw_probability
            and epoch_natural_endpoint is not None
            and epoch_draw_endpoint is not None
            and float(epoch_draw_endpoint["mean_outcome_probability"]["draw"])
            - float(epoch_natural_endpoint["mean_outcome_probability"]["draw"])
            >= args.minimum_controlled_draw_endpoint_probability_lift
        )
        epoch_outcome_passed = bool(
            prior_nll - float(validation["nll"]) >= args.minimum_nll_improvement
            and float(validation["ece_10"]) <= args.maximum_ece
            and all(value > 0 for value in validation["class_counts"].values())
            and epoch_natural_auc_passed
            and epoch_natural_phase_auc_passed
            and epoch_controlled_draw_passed
            and (not args.require_disjoint_natural_opponents or not opponent_overlap)
            and (not args.require_disjoint_natural_decks or not deck_overlap)
            and (
                structured_baseline_auc is None
                or float(validation["decisive_win_loss_auc"])
                >= structured_baseline_auc + args.minimum_structured_residual_auc_gain
            )
        )
        epoch_margin_passed = bool(
            float(validation["tower_margin_mae"]) <= args.maximum_margin_mae
            and float(validation["tower_margin_mae_improvement"])
            >= args.minimum_margin_mae_improvement
            and all_phase_margin_nonregression_passed(
                epoch_phases, args.maximum_phase_margin_mae_regression
            )
        )
        row = {
            "epoch": epoch,
            "training_loss": float(np.mean(losses)),
            "validation": validation,
            "all_row_validation": epoch_breakdowns["overall"],
            "outcome_gate_passed": epoch_outcome_passed,
            "margin_gate_passed": epoch_margin_passed,
            "development_gate_passed": epoch_outcome_passed and epoch_margin_passed,
            "probability_shrinkage": current_shrinkage,
        }
        history.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        selection_key = outcome_epoch_selection_key(
            validation,
            acceptance_passed=epoch_outcome_passed,
            by_phase=epoch_phases,
        )
        if selection_key > best_key:
            best_key = selection_key
            best_epoch = epoch
            best_metrics = validation
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in head.state_dict().items()
            }
        margin_selection_key = margin_epoch_selection_key(
            validation, acceptance_passed=epoch_margin_passed
        )
        if margin_selection_key > best_margin_key:
            best_margin_key = margin_selection_key
            best_margin_epoch = epoch
            best_margin_state = {
                name: value.detach().cpu().clone()
                for name, value in head.state_dict().items()
                if name.startswith("margin_trunk.")
            }
    assert (
        best_state is not None and best_metrics is not None and best_epoch is not None
    )
    head.load_state_dict(best_state)
    if best_margin_state:
        combined_state = head.state_dict()
        combined_state.update(best_margin_state)
        head.load_state_dict(combined_state, strict=True)
    phase_fraction = np.concatenate(
        [
            np.asarray(corpus.arrays["global_features"][:, 0])
            for _metadata, corpus in validation_loaded
        ]
    )
    phases = np.where(
        phase_fraction < 1.0 / 3.0,
        "early",
        np.where(phase_fraction < 2.0 / 3.0, "middle", "late"),
    )
    opponents = np.concatenate(
        [
            np.asarray(metadata["opponents"], dtype=np.str_)[
                _episode_rows(
                    corpus,
                    corpus.episode_arrays["episode_opponent_indices"],
                )
            ]
            for metadata, corpus in validation_loaded
        ]
    )
    seats = np.concatenate(
        [
            _episode_rows(
                corpus,
                corpus.episode_arrays["episode_learner_players"],
            ).astype(str)
            for _metadata, corpus in validation_loaded
        ]
    )
    sources = np.concatenate(
        [
            np.full(corpus.row_count, _outcome_source(metadata), dtype="<U32")
            for metadata, corpus in validation_loaded
        ]
    )
    endpoint_rows = torch.as_tensor(
        np.concatenate(
            [
                corpus.episode_offsets[1:] - 1 + row_offset
                for row_offset, (_metadata, corpus) in zip(
                    np.cumsum(
                        [0]
                        + [
                            previous.row_count
                            for _previous_metadata, previous in validation_loaded[:-1]
                        ]
                    ),
                    validation_loaded,
                    strict=True,
                )
            ]
        ),
        dtype=torch.long,
    )
    opponent_decks = np.concatenate(
        [
            (
                np.asarray(metadata["opponent_decks"], dtype=np.str_)[
                    _episode_rows(
                        corpus,
                        corpus.episode_arrays["episode_opponent_deck_indices"],
                    )
                ]
                if "episode_opponent_deck_indices" in corpus.episode_arrays
                and "opponent_decks" in metadata
                else np.full(corpus.row_count, "<controlled-draw>", dtype="<U32")
            )
            for metadata, corpus in validation_loaded
        ]
    )
    source_metrics = _bucket_metrics(
        head,
        validation_features,
        validation_outcomes,
        validation_margins,
        sources,
        device=device,
    )
    phase_metrics = _bucket_metrics(
        head,
        validation_features,
        validation_outcomes,
        validation_margins,
        phases,
        device=device,
    )
    phase_balanced_features = validation_features.index_select(0, validation_phase_rows)
    phase_balanced_outcomes = validation_outcomes.index_select(0, validation_phase_rows)
    phase_balanced_margins = validation_margins.index_select(0, validation_phase_rows)
    phase_balanced_sources = sources[validation_phase_rows.numpy()]
    phase_balanced_groups = phases[validation_phase_rows.numpy()]
    phase_balanced_metrics = metrics(
        head,
        phase_balanced_features,
        phase_balanced_outcomes,
        phase_balanced_margins,
        device=device,
    )
    phase_balanced_source_metrics = _bucket_metrics(
        head,
        phase_balanced_features,
        phase_balanced_outcomes,
        phase_balanced_margins,
        phase_balanced_sources,
        device=device,
    )
    phase_balanced_phase_metrics = _bucket_metrics(
        head,
        phase_balanced_features,
        phase_balanced_outcomes,
        phase_balanced_margins,
        phase_balanced_groups,
        device=device,
    )
    best_metrics = phase_balanced_metrics
    best_state = {
        name: value.detach().cpu().clone() for name, value in head.state_dict().items()
    }
    validation_phase_auc_confidence = phase_auc_confidence_intervals(
        head,
        phase_balanced_features,
        phase_balanced_outcomes,
        phase_balanced_groups,
        device=device,
        seed=args.seed + 10_000,
        replicates=args.phase_auc_bootstrap_replicates,
        clusters=phase_balanced_matchup_clusters(validation_loaded),
    )
    phase_auc_confidence_passed = all_phase_auc_confidence_passed(
        validation_phase_auc_confidence,
        minimum_lower_95=args.minimum_phase_auc_lower_bound,
        minimum_clusters=args.minimum_phase_bootstrap_clusters,
    )
    endpoint_sources = sources[endpoint_rows.numpy()]
    endpoint_metrics = metrics(
        head,
        validation_features.index_select(0, endpoint_rows),
        validation_outcomes.index_select(0, endpoint_rows),
        validation_margins.index_select(0, endpoint_rows),
        device=device,
    )
    endpoint_source_metrics = _bucket_metrics(
        head,
        validation_features.index_select(0, endpoint_rows),
        validation_outcomes.index_select(0, endpoint_rows),
        validation_margins.index_select(0, endpoint_rows),
        endpoint_sources,
        device=device,
    )
    natural_metrics = phase_balanced_source_metrics.get("natural-strategy-games")
    natural_endpoint_metrics = endpoint_source_metrics.get("natural-strategy-games")
    controlled_draw_endpoint_metrics = endpoint_source_metrics.get(
        "controlled-symmetric-draws"
    )
    natural_auc_passed = bool(
        natural_metrics is not None
        and natural_metrics["decisive_win_loss_auc"] is not None
        and float(natural_metrics["decisive_win_loss_auc"]) >= args.minimum_natural_auc
    )
    natural_phase_auc_passed = all_phase_decisive_auc_passed(
        phase_balanced_phase_metrics, args.minimum_natural_phase_auc
    )
    controlled_draw_passed = bool(
        best_metrics["auc_one_vs_rest"]["draw"] is not None
        and float(best_metrics["auc_one_vs_rest"]["draw"])
        >= args.minimum_controlled_draw_auc
        and natural_metrics is not None
        and float(natural_metrics["mean_outcome_probability"]["draw"])
        <= args.maximum_natural_draw_probability
        and natural_endpoint_metrics is not None
        and controlled_draw_endpoint_metrics is not None
        and float(controlled_draw_endpoint_metrics["mean_outcome_probability"]["draw"])
        - float(natural_endpoint_metrics["mean_outcome_probability"]["draw"])
        >= args.minimum_controlled_draw_endpoint_probability_lift
    )
    development_passed = bool(
        prior_nll - float(best_metrics["nll"]) >= args.minimum_nll_improvement
        and float(best_metrics["ece_10"]) <= args.maximum_ece
        and float(best_metrics["tower_margin_mae"]) <= args.maximum_margin_mae
        and float(best_metrics["tower_margin_mae_improvement"])
        >= args.minimum_margin_mae_improvement
        and all_phase_margin_nonregression_passed(
            phase_balanced_phase_metrics, args.maximum_phase_margin_mae_regression
        )
        and all(value > 0 for value in best_metrics["class_counts"].values())
        and natural_auc_passed
        and natural_phase_auc_passed
        and phase_auc_confidence_passed
        and controlled_draw_passed
        and (not args.require_disjoint_natural_opponents or not opponent_overlap)
        and (not args.require_disjoint_natural_decks or not deck_overlap)
        and (
            structured_baseline_auc is None
            or float(best_metrics["decisive_win_loss_auc"])
            >= structured_baseline_auc + args.minimum_structured_residual_auc_gain
        )
    )
    holdout_evaluation: dict[str, Any] | None = None
    holdout_prior_nll: float | None = None
    holdout_passed: bool | None = None
    holdout_phase_auc_confidence: dict[str, dict[str, float | int] | None] | None = None
    holdout_phase_confidence_passed: bool | None = None
    if holdout_loaded:
        assert (
            holdout_features is not None
            and holdout_outcomes is not None
            and holdout_margins is not None
        )
        holdout_evaluation = _evaluation_breakdowns(
            head,
            holdout_features,
            holdout_outcomes,
            holdout_margins,
            holdout_loaded,
            device=device,
        )
        holdout_phase_rows = phase_balanced_row_indices(holdout_loaded)
        holdout_phase_outcomes = holdout_outcomes.index_select(0, holdout_phase_rows)
        holdout_phase_progress = np.concatenate(
            [
                np.asarray(corpus.arrays["global_features"][:, 0])
                for _metadata, corpus in holdout_loaded
            ]
        )[holdout_phase_rows.numpy()]
        holdout_phase_groups = np.where(
            holdout_phase_progress < 1.0 / 3.0,
            "early",
            np.where(holdout_phase_progress < 2.0 / 3.0, "middle", "late"),
        )
        holdout_phase_auc_confidence = phase_auc_confidence_intervals(
            head,
            holdout_features.index_select(0, holdout_phase_rows),
            holdout_phase_outcomes,
            holdout_phase_groups,
            device=device,
            seed=args.seed + 20_000,
            replicates=args.phase_auc_bootstrap_replicates,
            clusters=phase_balanced_matchup_clusters(holdout_loaded),
        )
        holdout_phase_confidence_passed = all_phase_auc_confidence_passed(
            holdout_phase_auc_confidence,
            minimum_lower_95=args.minimum_phase_auc_lower_bound,
            minimum_clusters=args.minimum_phase_bootstrap_clusters,
        )
        holdout_prior_nll = float(
            -prior[(holdout_phase_outcomes.to(torch.long) + 1)]
            .clamp_min(1e-12)
            .log()
            .mean()
        )
        holdout_overall = holdout_evaluation["phase_balanced"]
        holdout_phases = holdout_evaluation["phase_balanced_by_phase"]
        holdout_sources = holdout_evaluation["phase_balanced_by_source"]
        holdout_endpoints = holdout_evaluation["episode_endpoints_by_source"]
        holdout_natural = holdout_sources.get("natural-strategy-games")
        holdout_draw_endpoint = holdout_endpoints.get("controlled-symmetric-draws")
        holdout_natural_endpoint = holdout_endpoints.get("natural-strategy-games")
        holdout_passed = bool(
            holdout_prior_nll - float(holdout_overall["nll"])
            >= args.minimum_nll_improvement
            and float(holdout_overall["ece_10"]) <= args.maximum_ece
            and float(holdout_overall["tower_margin_mae"]) <= args.maximum_margin_mae
            and float(holdout_overall["tower_margin_mae_improvement"])
            >= args.minimum_margin_mae_improvement
            and all_phase_margin_nonregression_passed(
                holdout_phases, args.maximum_phase_margin_mae_regression
            )
            and all(value > 0 for value in holdout_overall["class_counts"].values())
            and holdout_natural is not None
            and holdout_natural["decisive_win_loss_auc"] is not None
            and float(holdout_natural["decisive_win_loss_auc"])
            >= args.minimum_natural_auc
            and all_phase_decisive_auc_passed(
                holdout_phases, args.minimum_natural_phase_auc
            )
            and holdout_phase_confidence_passed
            and holdout_overall["auc_one_vs_rest"]["draw"] is not None
            and float(holdout_overall["auc_one_vs_rest"]["draw"])
            >= args.minimum_controlled_draw_auc
            and float(holdout_natural["mean_outcome_probability"]["draw"])
            <= args.maximum_natural_draw_probability
            and holdout_draw_endpoint is not None
            and holdout_natural_endpoint is not None
            and float(holdout_draw_endpoint["mean_outcome_probability"]["draw"])
            - float(holdout_natural_endpoint["mean_outcome_probability"]["draw"])
            >= args.minimum_controlled_draw_endpoint_probability_lift
            and (
                not args.require_disjoint_natural_opponents
                or not holdout_opponent_overlap
            )
            and (not args.require_disjoint_natural_decks or not holdout_deck_overlap)
        )
    final_passed = development_passed and (
        holdout_passed if holdout_passed is not None else True
    )
    report = {
        "schema": SCHEMA,
        "base_checkpoint": str(args.base_checkpoint.resolve()),
        "base_checkpoint_sha256": file_sha256(args.base_checkpoint),
        "train_corpora": [str(path.resolve()) for path in args.train_corpus],
        "train_corpus_sha256": [file_sha256(path) for path in args.train_corpus],
        "calibration_corpora": [
            str(path.resolve()) for path in args.calibration_corpus
        ],
        "calibration_corpus_sha256": [
            file_sha256(path) for path in args.calibration_corpus
        ],
        "validation_corpora": [str(path.resolve()) for path in args.validation_corpus],
        "validation_corpus_sha256": [
            file_sha256(path) for path in args.validation_corpus
        ],
        "holdout_corpora": [str(path.resolve()) for path in args.holdout_corpus],
        "holdout_corpus_sha256": [file_sha256(path) for path in args.holdout_corpus],
        "seed": args.seed,
        "device": str(device),
        "state_size": state_size,
        "hidden_size": args.hidden_size,
        "separate_draw_trunk": separate_draw_trunk,
        "structured_residual_scale": structured_residual_scale,
        "margin_residual_scale": args.margin_residual_scale,
        "outcome_head_state_sha256": outcome_state_sha256(best_state),
        "public_initialization_checkpoint": (
            str(args.initialize_public_checkpoint.resolve())
            if args.initialize_public_checkpoint is not None
            else None
        ),
        "public_initialization_sha256": public_initialization_sha256,
        "structured_baseline_decisive_auc": structured_baseline_auc,
        "minimum_structured_residual_auc_gain": (
            args.minimum_structured_residual_auc_gain
        ),
        "epoch_selection": "maximin-phase-then-decisive-auc-among-point-gate-passes-v1",
        "margin_epoch_selection": "maximum-mae-improvement-among-all-phase-gate-passes-v1",
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "margin_coefficient": args.margin_coefficient,
        "outcome_training_weighting": (
            "equal-episode-equal-reached-phase-then-declared-class-mass-v1"
            if args.phase_balanced_outcome_training
            else "equal-episode-then-declared-class-mass-v1"
        ),
        "margin_training_weighting": (
            "equal-episode-equal-reached-phase-v1"
            if args.phase_balanced_margin_training
            else "equal-episode-v1"
        ),
        "target_class_mass": {
            "loss": args.loss_class_mass,
            "draw": args.draw_class_mass,
            "win": args.win_class_mass,
        },
        "probability_calibration": (
            "factorized-training-mass-prior-plus-rank-preserving-shrinkage-v1"
            if calibration_loaded
            else "factorized-training-mass-to-empirical-episode-prior-v1"
        ),
        "probability_shrinkage": float(head.probability_shrinkage.cpu()),
        "actor_input_previous_reward": "forced-zero-unavailable-at-live-inference",
        "actor_input_critic_fields": False,
        "actor_feature_contract": args.feature_set,
        "trainable_parameter_count": sum(
            parameter.numel()
            for parameter in head.parameters()
            if parameter.requires_grad
        ),
        "train_class_prior": prior.tolist(),
        "validation_prior_nll": prior_nll,
        "best_epoch": best_epoch,
        "best_outcome_epoch": best_epoch,
        "best_margin_epoch": best_margin_epoch,
        "best_validation": best_metrics,
        "validation_all_rows": metrics(
            head,
            validation_features,
            validation_outcomes,
            validation_margins,
            device=device,
        ),
        "validation_phase_balanced": phase_balanced_metrics,
        "validation_phase_balanced_by_phase": phase_balanced_phase_metrics,
        "validation_phase_balanced_by_source": phase_balanced_source_metrics,
        "validation_phase_auc_confidence": validation_phase_auc_confidence,
        "validation_by_phase": phase_metrics,
        "validation_by_opponent": _bucket_metrics(
            head,
            validation_features,
            validation_outcomes,
            validation_margins,
            opponents,
            device=device,
        ),
        "validation_by_seat": _bucket_metrics(
            head,
            validation_features,
            validation_outcomes,
            validation_margins,
            seats,
            device=device,
        ),
        "validation_by_source": source_metrics,
        "validation_episode_endpoints": endpoint_metrics,
        "validation_episode_endpoints_by_source": endpoint_source_metrics,
        "validation_by_opponent_deck": _bucket_metrics(
            head,
            validation_features,
            validation_outcomes,
            validation_margins,
            opponent_decks,
            device=device,
        ),
        "validation_by_opponent_and_deck": _bucket_metrics(
            head,
            validation_features,
            validation_outcomes,
            validation_margins,
            np.char.add(np.char.add(opponents, "|"), opponent_decks),
            device=device,
        ),
        "selection_gates": {
            "minimum_nll_improvement_over_train_prior": args.minimum_nll_improvement,
            "maximum_ece_10": args.maximum_ece,
            "maximum_tower_margin_mae": args.maximum_margin_mae,
            "minimum_tower_margin_mae_improvement": (
                args.minimum_margin_mae_improvement
            ),
            "maximum_phase_tower_margin_mae_regression": (
                args.maximum_phase_margin_mae_regression
            ),
            "all_three_outcome_classes_required": True,
            "minimum_natural_decisive_auc": args.minimum_natural_auc,
            "minimum_natural_phase_decisive_auc": args.minimum_natural_phase_auc,
            "minimum_phase_auc_lower_95": args.minimum_phase_auc_lower_bound,
            "phase_auc_bootstrap_replicates": args.phase_auc_bootstrap_replicates,
            "minimum_phase_bootstrap_clusters": (args.minimum_phase_bootstrap_clusters),
            "phase_auc_bootstrap_unit": "seed-style-deck-ordinal-cluster-v1",
            "minimum_controlled_draw_auc": args.minimum_controlled_draw_auc,
            "minimum_controlled_draw_endpoint_probability_lift": (
                args.minimum_controlled_draw_endpoint_probability_lift
            ),
            "maximum_natural_draw_probability": args.maximum_natural_draw_probability,
            "require_disjoint_natural_opponents": args.require_disjoint_natural_opponents,
            "require_disjoint_natural_decks": args.require_disjoint_natural_decks,
            "natural_opponent_overlap": sorted(opponent_overlap),
            "natural_deck_overlap": sorted(deck_overlap),
            "calibration_natural_opponent_overlap": sorted(
                calibration_opponent_overlap
            ),
            "calibration_natural_deck_overlap": sorted(calibration_deck_overlap),
            "natural_auc_passed": natural_auc_passed,
            "natural_phase_auc_passed": natural_phase_auc_passed,
            "phase_auc_confidence_passed": phase_auc_confidence_passed,
            "controlled_draw_passed": controlled_draw_passed,
            "development_passed": development_passed,
            "holdout_passed": holdout_passed,
            "holdout_natural_opponent_overlap": sorted(holdout_opponent_overlap),
            "holdout_natural_deck_overlap": sorted(holdout_deck_overlap),
        },
        "holdout_prior_nll": holdout_prior_nll,
        "holdout_evaluation": holdout_evaluation,
        "holdout_phase_auc_confidence": holdout_phase_auc_confidence,
        "holdout_phase_confidence_passed": holdout_phase_confidence_passed,
        "history": history,
        "elapsed_seconds": time.monotonic() - started,
        "status": (
            ("accepted-holdout" if final_passed else "rejected-holdout")
            if holdout_loaded
            else (
                "accepted-development" if development_passed else "rejected-development"
            )
        ),
        "counterfactual_ranking_gate_pending": final_passed,
        "output_checkpoint": (
            str(args.output_checkpoint.resolve()) if final_passed else None
        ),
    }
    _atomic_json(args.report, report)
    if not final_passed:
        raise SystemExit("actor-visible outcome head failed development gates")
    result = {
        "schema": SCHEMA,
        "base_checkpoint_sha256": file_sha256(args.base_checkpoint),
        "base_model_config": payload["model_config"],
        "token_names": payload["token_names"],
        "state_size": state_size,
        "hidden_size": args.hidden_size,
        "separate_draw_trunk": separate_draw_trunk,
        "structured_residual_scale": structured_residual_scale,
        "margin_residual_scale": args.margin_residual_scale,
        "public_initialization_sha256": public_initialization_sha256,
        "outcome_head_state_dict": best_state,
        "training_report": report,
    }
    _atomic_checkpoint(args.output_checkpoint, result)
    print(json.dumps({"status": report["status"], "best_epoch": best_epoch}))


if __name__ == "__main__":
    main()
