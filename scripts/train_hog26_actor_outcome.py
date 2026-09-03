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

from clasher.rl.direct_simple_behavior import (
    DirectSimpleBehaviorCorpus,
    load_direct_simple_behavior_corpus,
)
from clasher.rl.model import ClasherPolicy, PolicyInputs
from clasher.rl.outcome_model import ActorOutcomeHead, actor_outcome_loss
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
    base_parts: list[np.ndarray] = []
    for _metadata, corpus in loaded:
        lengths = np.diff(corpus.episode_offsets).astype(np.float64)
        base_parts.append(np.repeat(1.0 / lengths, lengths.astype(np.int64)))
    weights = np.concatenate(base_parts)
    for class_index, outcome in enumerate((-1, 0, 1)):
        selected = outcomes == outcome
        current = float(weights[selected].sum())
        target = float(masses[class_index])
        if target > 0.0 and current <= 0.0:
            raise ValueError("target class mass is positive for an absent class")
        weights[selected] *= 0.0 if target == 0.0 else target / current
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
    playable = inputs.hand_ids[..., :4] != 0
    playable_weights = playable.unsqueeze(-1).to(hand.dtype)
    playable_mean = (hand[..., :4, :] * playable_weights).sum(dim=-2) / (
        playable_weights.sum(dim=-2).clamp_min(1.0)
    )
    playable_max = hand[..., :4, :].masked_fill(
        ~playable.unsqueeze(-1), -torch.inf
    ).amax(dim=-2)
    playable_max = torch.where(
        playable.any(dim=-1, keepdim=True), playable_max, 0.0
    )
    next_card = torch.where(
        (inputs.hand_ids[..., 4] != 0).unsqueeze(-1), hand[..., 4, :], 0.0
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


@torch.no_grad()
def extract_actor_features(
    model: ClasherPolicy,
    corpus: DirectSimpleBehaviorCorpus,
    *,
    device: torch.device,
    sequence_steps: int,
    feature_set: str,
) -> Tensor:
    """Replay actor state with simulator reward feedback explicitly unavailable."""

    model.eval()
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
            output = model(inputs, state)
            if output.repair_features is None:
                raise ValueError("base policy does not expose actor-visible state")
            if feature_set == "public-globals":
                selected_features = inputs.global_features[0]
            elif feature_set == "structured-summary":
                selected_features = structured_actor_summary(model, inputs)[0]
            elif feature_set == "policy-plus-public-globals":
                selected_features = torch.cat(
                    (output.repair_features[0], inputs.global_features[0]), dim=-1
                )
            else:
                raise ValueError("unknown actor outcome feature set")
            features.append(selected_features.detach().cpu())
            state = (output.next_state[0].detach(), output.next_state[1].detach())
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
        "tower_margin_mae": float((predicted_margin - margins).abs().mean()),
        "tower_margin_rmse": float((predicted_margin - margins).square().mean().sqrt()),
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
    parser.add_argument("--holdout-corpus", type=Path, action="append", default=[])
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--sequence-steps", type=int, default=128)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument(
        "--feature-set",
        choices=(
            "public-globals",
            "structured-summary",
            "policy-plus-public-globals",
        ),
        default="policy-plus-public-globals",
    )
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--margin-coefficient", type=float, default=0.25)
    parser.add_argument("--loss-class-mass", type=float, default=0.45)
    parser.add_argument("--draw-class-mass", type=float, default=0.10)
    parser.add_argument("--win-class-mass", type=float, default=0.45)
    parser.add_argument("--minimum-nll-improvement", type=float, default=0.02)
    parser.add_argument("--maximum-ece", type=float, default=0.20)
    parser.add_argument("--maximum-margin-mae", type=float, default=0.25)
    parser.add_argument("--minimum-natural-auc", type=float, default=0.60)
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
    holdout_loaded = [
        load_direct_simple_behavior_corpus(path) for path in args.holdout_corpus
    ]
    for metadata, corpus in (*train_loaded, *validation_loaded, *holdout_loaded):
        validate_outcome_corpus(metadata, corpus)
        if metadata.get("checkpoint_sha256") != file_sha256(args.base_checkpoint):
            raise ValueError("outcome corpus was collected by a different policy")
    train_seeds = {int(metadata["seed"]) for metadata, _corpus in train_loaded}
    validation_seeds = {
        int(metadata["seed"]) for metadata, _corpus in validation_loaded
    }
    holdout_seeds = {int(metadata["seed"]) for metadata, _corpus in holdout_loaded}
    if train_seeds.intersection(validation_seeds):
        raise ValueError("outcome train and validation seeds must be disjoint")
    if train_seeds.intersection(holdout_seeds) or validation_seeds.intersection(
        holdout_seeds
    ):
        raise ValueError("outcome holdout seeds must be disjoint from train/development")
    train_hashes = {file_sha256(path) for path in args.train_corpus}
    validation_hashes = {file_sha256(path) for path in args.validation_corpus}
    holdout_hashes = {file_sha256(path) for path in args.holdout_corpus}
    if train_hashes.intersection(validation_hashes):
        raise ValueError("outcome train and validation corpora must be disjoint")
    if holdout_hashes.intersection(train_hashes | validation_hashes):
        raise ValueError("outcome holdout corpora must be physically disjoint")
    train_natural_opponents = _natural_metadata_values(train_loaded, "opponents")
    validation_natural_opponents = _natural_metadata_values(
        validation_loaded, "opponents"
    )
    train_natural_decks = _natural_metadata_values(train_loaded, "opponent_decks")
    validation_natural_decks = _natural_metadata_values(
        validation_loaded, "opponent_decks"
    )
    holdout_natural_opponents = _natural_metadata_values(holdout_loaded, "opponents")
    holdout_natural_decks = _natural_metadata_values(holdout_loaded, "opponent_decks")
    opponent_overlap = train_natural_opponents & validation_natural_opponents
    deck_overlap = train_natural_decks & validation_natural_decks
    if args.require_disjoint_natural_opponents and opponent_overlap:
        raise ValueError("natural outcome train/validation opponents overlap")
    if args.require_disjoint_natural_decks and deck_overlap:
        raise ValueError("natural outcome train/validation decks overlap")
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
    state_size = int(train_features.shape[1])
    separate_draw_trunk = args.feature_set == "structured-summary"
    head = ActorOutcomeHead(
        state_size,
        args.hidden_size,
        separate_draw_trunk=separate_draw_trunk,
    ).to(device)
    optimizer = torch.optim.AdamW(
        head.parameters(), lr=args.learning_rate, weight_decay=1e-4
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
    counts = torch.bincount(train_outcomes.to(torch.long) + 1, minlength=3).float()
    prior = counts / counts.sum()
    prior_nll = float(
        -prior[(validation_outcomes.to(torch.long) + 1)].clamp_min(1e-12).log().mean()
    )
    rng = np.random.default_rng(args.seed)
    history: list[dict[str, Any]] = []
    best_nll = math.inf
    best_epoch: int | None = None
    best_state: dict[str, Tensor] | None = None
    best_metrics: dict[str, Any] | None = None
    for epoch in range(1, args.epochs + 1):
        head.train()
        order = rng.permutation(train_outcomes.numel())
        losses = []
        for start in range(0, len(order), args.batch_size):
            rows = torch.as_tensor(order[start : start + args.batch_size])
            prediction = head(train_features.index_select(0, rows).to(device))
            loss = actor_outcome_loss(
                prediction,
                train_outcomes.index_select(0, rows).to(device),
                train_margins.index_select(0, rows).to(device),
                margin_coefficient=args.margin_coefficient,
                sample_weights=train_weights.index_select(0, rows).to(device),
            )
            optimizer.zero_grad(set_to_none=True)
            loss.total.backward()
            torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.total.detach()))
        validation = metrics(
            head,
            validation_features,
            validation_outcomes,
            validation_margins,
            device=device,
        )
        row = {
            "epoch": epoch,
            "training_loss": float(np.mean(losses)),
            "validation": validation,
        }
        history.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        if float(validation["nll"]) < best_nll:
            best_nll = float(validation["nll"])
            best_epoch = epoch
            best_metrics = validation
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in head.state_dict().items()
            }
    assert (
        best_state is not None and best_metrics is not None and best_epoch is not None
    )
    head.load_state_dict(best_state)
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
    natural_metrics = source_metrics.get("natural-strategy-games")
    natural_endpoint_metrics = endpoint_source_metrics.get("natural-strategy-games")
    controlled_draw_endpoint_metrics = endpoint_source_metrics.get(
        "controlled-symmetric-draws"
    )
    natural_auc_passed = bool(
        natural_metrics is not None
        and natural_metrics["decisive_win_loss_auc"] is not None
        and float(natural_metrics["decisive_win_loss_auc"])
        >= args.minimum_natural_auc
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
        and float(
            controlled_draw_endpoint_metrics["mean_outcome_probability"]["draw"]
        )
        - float(natural_endpoint_metrics["mean_outcome_probability"]["draw"])
        >= args.minimum_controlled_draw_endpoint_probability_lift
    )
    development_passed = bool(
        prior_nll - float(best_metrics["nll"]) >= args.minimum_nll_improvement
        and float(best_metrics["ece_10"]) <= args.maximum_ece
        and float(best_metrics["tower_margin_mae"]) <= args.maximum_margin_mae
        and all(value > 0 for value in best_metrics["class_counts"].values())
        and natural_auc_passed
        and controlled_draw_passed
        and (not args.require_disjoint_natural_opponents or not opponent_overlap)
        and (not args.require_disjoint_natural_decks or not deck_overlap)
    )
    holdout_evaluation: dict[str, Any] | None = None
    holdout_prior_nll: float | None = None
    holdout_passed: bool | None = None
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
        holdout_prior_nll = float(
            -prior[(holdout_outcomes.to(torch.long) + 1)]
            .clamp_min(1e-12)
            .log()
            .mean()
        )
        holdout_overall = holdout_evaluation["overall"]
        holdout_sources = holdout_evaluation["by_source"]
        holdout_endpoints = holdout_evaluation["episode_endpoints_by_source"]
        holdout_natural = holdout_sources.get("natural-strategy-games")
        holdout_draw_endpoint = holdout_endpoints.get("controlled-symmetric-draws")
        holdout_natural_endpoint = holdout_endpoints.get("natural-strategy-games")
        holdout_passed = bool(
            holdout_prior_nll - float(holdout_overall["nll"])
            >= args.minimum_nll_improvement
            and float(holdout_overall["ece_10"]) <= args.maximum_ece
            and float(holdout_overall["tower_margin_mae"])
            <= args.maximum_margin_mae
            and all(value > 0 for value in holdout_overall["class_counts"].values())
            and holdout_natural is not None
            and holdout_natural["decisive_win_loss_auc"] is not None
            and float(holdout_natural["decisive_win_loss_auc"])
            >= args.minimum_natural_auc
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
            and (
                not args.require_disjoint_natural_decks or not holdout_deck_overlap
            )
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
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "margin_coefficient": args.margin_coefficient,
        "training_weighting": "equal-episode-then-declared-class-mass-v1",
        "target_class_mass": {
            "loss": args.loss_class_mass,
            "draw": args.draw_class_mass,
            "win": args.win_class_mass,
        },
        "actor_input_previous_reward": "forced-zero-unavailable-at-live-inference",
        "actor_input_critic_fields": False,
        "actor_feature_contract": args.feature_set,
        "trainable_parameter_count": sum(
            parameter.numel() for parameter in head.parameters()
        ),
        "train_class_prior": prior.tolist(),
        "validation_prior_nll": prior_nll,
        "best_epoch": best_epoch,
        "best_validation": best_metrics,
        "validation_by_phase": _bucket_metrics(
            head,
            validation_features,
            validation_outcomes,
            validation_margins,
            phases,
            device=device,
        ),
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
            "all_three_outcome_classes_required": True,
            "minimum_natural_decisive_auc": args.minimum_natural_auc,
            "minimum_controlled_draw_auc": args.minimum_controlled_draw_auc,
            "minimum_controlled_draw_endpoint_probability_lift": (
                args.minimum_controlled_draw_endpoint_probability_lift
            ),
            "maximum_natural_draw_probability": args.maximum_natural_draw_probability,
            "require_disjoint_natural_opponents": args.require_disjoint_natural_opponents,
            "require_disjoint_natural_decks": args.require_disjoint_natural_decks,
            "natural_opponent_overlap": sorted(opponent_overlap),
            "natural_deck_overlap": sorted(deck_overlap),
            "natural_auc_passed": natural_auc_passed,
            "controlled_draw_passed": controlled_draw_passed,
            "development_passed": development_passed,
            "holdout_passed": holdout_passed,
            "holdout_natural_opponent_overlap": sorted(holdout_opponent_overlap),
            "holdout_natural_deck_overlap": sorted(holdout_deck_overlap),
        },
        "holdout_prior_nll": holdout_prior_nll,
        "holdout_evaluation": holdout_evaluation,
        "history": history,
        "elapsed_seconds": time.monotonic() - started,
        "status": (
            ("accepted-holdout" if final_passed else "rejected-holdout")
            if holdout_loaded
            else (
                "accepted-development"
                if development_passed
                else "rejected-development"
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
        "outcome_head_state_dict": best_state,
        "training_report": report,
    }
    _atomic_checkpoint(args.output_checkpoint, result)
    print(json.dumps({"status": report["status"], "best_epoch": best_epoch}))


if __name__ == "__main__":
    main()
