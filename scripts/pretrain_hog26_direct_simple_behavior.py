#!/usr/bin/env python3
"""Pretrain a factorized Hog actor from complete direct-Simple behavior."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
from numpy.typing import NDArray
from torch import Tensor, nn
from torch.nn import functional as F

from clasher.rl.direct_simple_behavior import (
    DirectSimpleBehaviorCorpus,
    RecurrentBehaviorWindow,
    load_direct_simple_behavior_corpus,
    recurrent_behavior_windows,
)
from clasher.rl.event_policy import (
    ABILITY_ACTION,
    continuous_time_action_distribution,
    deterministic_event_actions,
    raw_rate_from_interval_probability,
)
from clasher.rl.hierarchical_imitation import (
    PLACEMENT_ACTIONS,
    HierarchicalImitationConfig,
    factor_public_action_mask,
    hierarchical_masked_imitation_loss,
    labels_from_flat_actions,
)
from clasher.rl.model import ClasherPolicy, PolicyConfig
from scripts.pretrain_hog26_factorized_policy import actor_parameters, batch_inputs

SCHEMA = "clasher.hog26.direct-simple-behavior-pretrain.v2"
CORPUS_SCHEMA = "clasher.hog26.direct-simple-behavior.v2"
State = tuple[Tensor, Tensor]


def select_trainable_parameters(
    model: ClasherPolicy, scope: str
) -> tuple[list[str], list[nn.Parameter]]:
    """Select the smallest honest distillation surface for each experiment arm."""

    if scope == "actor":
        return actor_parameters(model)
    if scope not in {"mode-only", "mode-bias-only"}:
        raise ValueError(f"unknown trainable scope: {scope}")
    names: list[str] = []
    parameters: list[nn.Parameter] = []
    for name, parameter in model.named_parameters():
        enabled = name.startswith("hierarchical_mode_gate.") and (
            scope == "mode-only" or name == "hierarchical_mode_gate.2.bias"
        )
        parameter.requires_grad_(enabled)
        if enabled:
            names.append(name)
            parameters.append(parameter)
    if not parameters:
        raise ValueError("mode-only distillation found no hierarchical mode gate")
    return names, parameters


@torch.no_grad()
def initialize_constant_event_mode(model: ClasherPolicy, probability: float) -> None:
    """Fit the natural-frequency constant Bernoulli baseline in closed form."""

    if model.config.deterministic_hierarchy != "event":
        raise ValueError("constant event initialization requires event hierarchy")
    if not 0.0 < probability < 1.0:
        raise ValueError("constant event probability must be in (0, 1)")
    gate = model.hierarchical_mode_gate
    if gate is None or not isinstance(gate[-1], nn.Linear):
        raise ValueError("event hierarchy has no linear mode output")
    output = gate[-1]
    output.weight.zero_()
    output.bias.copy_(
        torch.as_tensor(
            [math.log(probability), math.log1p(-probability), 0.0],
            dtype=output.bias.dtype,
            device=output.bias.device,
        )
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_model(
    checkpoint: Path, device: torch.device
) -> tuple[dict[str, Any], ClasherPolicy]:
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    config = PolicyConfig.from_dict(payload["model_config"])
    state = payload["model_state_dict"]
    card_stats = torch.as_tensor(state["actor_encoder.card_stat_features"])
    semantic = state.get("actor_encoder.semantic_card_features")
    if semantic is not None:
        card_stats = torch.cat([card_stats, torch.as_tensor(semantic)], dim=-1)
    model = ClasherPolicy(config, card_stats).to(device)
    model.load_state_dict(state, strict=True)
    return payload, model


def load_student(
    checkpoint: Path, device: torch.device
) -> tuple[dict[str, Any], ClasherPolicy]:
    payload, model = load_model(checkpoint, device)
    config = model.config
    if (
        config.deterministic_hierarchy not in {"play-gate", "event"}
        or not config.hierarchical_mode_gate_enabled
        or not config.equivariant_slot_choice
        or config.play_hazard_enabled
        or config.action_value_head_enabled
    ):
        raise ValueError("initializer is not the fresh factorized control architecture")
    if config.dropout != 0.0:
        raise ValueError("exact recurrent replay currently requires zero dropout")
    return payload, model


def load_teacher_identity(checkpoint: Path) -> tuple[dict[str, Any], PolicyConfig]:
    """Load only the frozen teacher identity, never replay its policy boundary."""

    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    config = PolicyConfig.from_dict(payload["model_config"])
    if config.deterministic_hierarchy != "hazard" or not config.play_hazard_enabled:
        raise ValueError("behavior teacher must use corrected recurrent hazard timing")
    return payload, config


def _initial_state_for_episodes(
    model: ClasherPolicy,
    corpus: DirectSimpleBehaviorCorpus,
    episodes: list[int],
    *,
    device: torch.device,
) -> State:
    state = model.initial_state(len(episodes), device=device)
    expected_hidden = torch.as_tensor(
        corpus.initial_hidden[episodes], dtype=state[0].dtype, device=device
    )
    expected_cell = torch.as_tensor(
        corpus.initial_cell[episodes], dtype=state[1].dtype, device=device
    )
    if not torch.equal(state[0], expected_hidden) or not torch.equal(
        state[1], expected_cell
    ):
        raise ValueError("corpus reset state differs from the student architecture")
    return cast(State, state)


def _forward_loss(
    model: ClasherPolicy,
    corpus: DirectSimpleBehaviorCorpus,
    rows: NDArray[np.int64],
    state: State,
    *,
    device: torch.device,
    initial_event_hazard: Tensor | None = None,
    event_threshold: float = math.log(2.0),
) -> tuple[Tensor, State, dict[str, float | int], Tensor | None]:
    inputs = batch_inputs(corpus.arrays, rows, device)
    output = model(inputs, state)
    actions = torch.as_tensor(
        corpus.arrays["actions"][rows], dtype=torch.long, device=device
    ).reshape(-1)
    trusted = torch.ones_like(actions, dtype=torch.bool)
    placement = actions < PLACEMENT_ACTIONS
    labels = labels_from_flat_actions(
        actions,
        decision_trusted=trusted,
        card_trusted=placement,
        tile_trusted=placement,
    )
    flat_mask = inputs.action_mask.reshape(-1, inputs.action_mask.shape[-1])
    masks = factor_public_action_mask(flat_mask)
    action_type = output.action_type_logits.reshape(-1, 6)
    decision_logits = torch.cat(
        [torch.logsumexp(action_type[:, :4], dim=-1, keepdim=True), action_type[:, 4:]],
        dim=-1,
    )
    if "play_hazard_probabilities" not in corpus.arrays:
        raise ValueError("behavior corpus lacks original-boundary hazard probabilities")
    teacher_probability = torch.as_tensor(
        corpus.arrays["play_hazard_probabilities"][rows],
        dtype=decision_logits.dtype,
        device=device,
    ).reshape(-1)
    if model.config.deterministic_hierarchy == "event":
        if output.hierarchical_mode_logits is None:
            raise ValueError("event student did not expose raw mode logits")
        mode_probability = torch.softmax(
            output.hierarchical_mode_logits[..., :2], dim=-1
        )[..., 0].reshape(-1)
    else:
        mode_probability = torch.softmax(
            decision_logits.masked_fill(~masks.decision, -torch.inf), dim=-1
        )[:, 0]
    timing_loss = F.binary_cross_entropy(mode_probability, teacher_probability)
    breakdown = hierarchical_masked_imitation_loss(
        decision_logits,
        action_type[:, :4],
        output.location_logits.reshape(-1, 4, 576),
        masks,
        labels,
        config=HierarchicalImitationConfig(decision_loss_coef=0.0),
    )
    with torch.no_grad():
        next_event_hazard: Tensor | None = None
        if initial_event_hazard is None:
            predictions = model._deterministic_actions(
                output,
                inputs.action_mask,
                force_play=(
                    torch.zeros(
                        inputs.action_mask.shape[:2],
                        dtype=torch.bool,
                        device=device,
                    )
                    if model.config.deterministic_hierarchy == "event"
                    else None
                ),
            ).reshape(-1)
        elif model.config.deterministic_hierarchy == "event":
            force_play, next_event_hazard = model._event_mode_force_gate(
                output,
                inputs.action_mask,
                initial_event_hazard,
            )
            predictions = model._deterministic_actions(
                output,
                inputs.action_mask,
                force_play=force_play,
            ).reshape(-1)
        else:
            if bool(inputs.action_mask[..., ABILITY_ACTION].any()):
                raise ValueError(
                    "Hog behavior hazard decoding does not support abilities"
                )
            batch, steps = inputs.action_mask.shape[:2]
            interval_probability = mode_probability.reshape(batch, steps).clamp_max(
                1.0 - torch.finfo(mode_probability.dtype).eps
            )
            delta_seconds = torch.full_like(interval_probability, 0.4)
            raw_play_rate = raw_rate_from_interval_probability(
                interval_probability, delta_seconds
            )
            distribution = continuous_time_action_distribution(
                raw_play_rate,
                torch.full_like(raw_play_rate, -torch.inf),
                output.action_type_logits[..., :4],
                output.location_logits,
                inputs.action_mask,
                delta_seconds,
            )
            decoded, next_event_hazard = deterministic_event_actions(
                distribution,
                initial_event_hazard,
                episode_starts=inputs.episode_starts,
                threshold=event_threshold,
            )
            predictions = decoded.reshape(-1)
        decision_prediction = torch.where(
            predictions < PLACEMENT_ACTIONS,
            torch.zeros_like(predictions),
            torch.where(
                predictions == PLACEMENT_ACTIONS,
                torch.ones_like(predictions),
                torch.full_like(predictions, 2),
            ),
        )
        play = labels.decision_target == 0
        wait = labels.decision_target == 1
        card_prediction = (
            action_type[:, :4].masked_fill(~masks.card, -torch.inf).argmax(dim=-1)
        )
        tile_rows = torch.nonzero(placement, as_tuple=False).flatten()
        if tile_rows.numel():
            target_cards = labels.card_target.index_select(0, tile_rows)
            local_rows = torch.arange(tile_rows.numel(), device=device)
            tile_logits = output.location_logits.reshape(-1, 4, 576).index_select(
                0, tile_rows
            )[local_rows, target_cards]
            tile_mask = masks.tile.index_select(0, tile_rows)[local_rows, target_cards]
            tile_predictions = tile_logits.masked_fill(~tile_mask, -torch.inf).argmax(
                dim=-1
            )
            tile_correct = int(
                (
                    tile_predictions == labels.tile_target.index_select(0, tile_rows)
                ).sum()
            )
        else:
            tile_correct = 0
    play_targets = play.to(mode_probability.dtype)
    total = timing_loss + breakdown.card + breakdown.tile
    return (
        total,
        output.next_state,
        {
            "decision_loss": float(timing_loss.detach()),
            "card_loss": float(breakdown.card.detach()),
            "tile_loss": float(breakdown.tile.detach()),
            "rows": int(actions.numel()),
            "plays": int(play.sum()),
            "waits": int(wait.sum()),
            "exact_correct": int((predictions == actions).sum()),
            "play_true_positive": int(((decision_prediction == 0) & play).sum()),
            "play_false_positive": int(((decision_prediction == 0) & wait).sum()),
            "wait_correct": int(((decision_prediction == 1) & wait).sum()),
            "card_correct": int(
                ((card_prediction == labels.card_target) & placement).sum()
            ),
            "tile_correct": tile_correct,
            "play_probability_sum": float(mode_probability.detach().sum()),
            "play_brier_sum": float(
                (mode_probability - teacher_probability).square().sum()
            ),
            "hard_event_brier_sum": float(
                (mode_probability - play_targets).square().sum()
            ),
            "teacher_probability_sum": float(teacher_probability.sum()),
        },
        next_event_hazard,
    )


def _aggregate_metrics(parts: list[dict[str, float | int]]) -> dict[str, float]:
    counts = {
        key: sum(int(part[key]) for part in parts)
        for key in (
            "rows",
            "plays",
            "waits",
            "exact_correct",
            "play_true_positive",
            "play_false_positive",
            "wait_correct",
            "card_correct",
            "tile_correct",
        )
    }
    decision_loss = sum(
        float(part["decision_loss"]) * int(part["rows"]) for part in parts
    )
    card_loss = sum(float(part["card_loss"]) * int(part["plays"]) for part in parts)
    tile_loss = sum(float(part["tile_loss"]) * int(part["plays"]) for part in parts)
    predicted_plays = counts["play_true_positive"] + counts["play_false_positive"]
    precision = counts["play_true_positive"] / max(1, predicted_plays)
    recall = counts["play_true_positive"] / max(1, counts["plays"])
    return {
        "loss": (
            decision_loss / max(1, counts["rows"])
            + card_loss / max(1, counts["plays"])
            + tile_loss / max(1, counts["plays"])
        ),
        "decision_loss": decision_loss / max(1, counts["rows"]),
        "card_loss": card_loss / max(1, counts["plays"]),
        "tile_loss": tile_loss / max(1, counts["plays"]),
        "rows": float(counts["rows"]),
        "plays": float(counts["plays"]),
        "waits": float(counts["waits"]),
        "exact_action_accuracy": counts["exact_correct"] / max(1, counts["rows"]),
        "play_precision": precision,
        "play_recall": recall,
        "play_f1": 2.0 * precision * recall / max(1e-12, precision + recall),
        "wait_accuracy": counts["wait_correct"] / max(1, counts["waits"]),
        "balanced_timing_accuracy": 0.5
        * (recall + counts["wait_correct"] / max(1, counts["waits"])),
        "predicted_play_rate": predicted_plays / max(1, counts["rows"]),
        "teacher_play_rate": counts["plays"] / max(1, counts["rows"]),
        "mean_play_probability": sum(
            float(part["play_probability_sum"]) for part in parts
        )
        / max(1, counts["rows"]),
        "play_brier": sum(float(part["play_brier_sum"]) for part in parts)
        / max(1, counts["rows"]),
        "hard_event_brier": sum(float(part["hard_event_brier_sum"]) for part in parts)
        / max(1, counts["rows"]),
        "mean_teacher_play_probability": sum(
            float(part["teacher_probability_sum"]) for part in parts
        )
        / max(1, counts["rows"]),
        "card_accuracy": counts["card_correct"] / max(1, counts["plays"]),
        "tile_accuracy": counts["tile_correct"] / max(1, counts["plays"]),
    }


@torch.no_grad()
def evaluate(
    model: ClasherPolicy,
    corpus: DirectSimpleBehaviorCorpus,
    *,
    device: torch.device,
    sequence_steps: int,
    event_threshold: float,
) -> dict[str, float]:
    model.eval()
    parts: list[dict[str, float | int]] = []
    for episode in range(corpus.episode_count):
        state = _initial_state_for_episodes(model, corpus, [episode], device=device)
        event_hazard = torch.zeros(1, dtype=state[0].dtype, device=device)
        begin = int(corpus.episode_offsets[episode])
        end = int(corpus.episode_offsets[episode + 1])
        for start in range(begin, end, sequence_steps):
            rows = np.arange(start, min(end, start + sequence_steps), dtype=np.int64)[
                None, :
            ]
            _loss, state, metrics, next_event_hazard = _forward_loss(
                model,
                corpus,
                rows,
                state,
                device=device,
                initial_event_hazard=event_hazard,
                event_threshold=event_threshold,
            )
            assert next_event_hazard is not None
            event_hazard = next_event_hazard
            state = (state[0].detach(), state[1].detach())
            parts.append(metrics)
    return _aggregate_metrics(parts)


@torch.no_grad()
def build_state_cache(
    model: ClasherPolicy,
    corpus: DirectSimpleBehaviorCorpus,
    windows: tuple[RecurrentBehaviorWindow, ...],
    *,
    device: torch.device,
) -> dict[tuple[int, int], State]:
    """Cache exact epoch-start student state at every burn-in boundary."""

    model.eval()
    boundaries: dict[int, set[int]] = defaultdict(set)
    for window in windows:
        boundaries[window.episode].update((window.context_start, window.train_start))
    cache: dict[tuple[int, int], State] = {}
    for episode in range(corpus.episode_count):
        begin = int(corpus.episode_offsets[episode])
        state = _initial_state_for_episodes(model, corpus, [episode], device=device)
        cursor = begin
        for boundary in sorted(boundaries[episode]):
            if boundary < cursor:
                raise ValueError("recurrent cache boundaries are not monotonic")
            if boundary > cursor:
                rows = np.arange(cursor, boundary, dtype=np.int64)[None, :]
                inputs = batch_inputs(corpus.arrays, rows, device)
                state = model(inputs, state).next_state
                state = (state[0].detach(), state[1].detach())
            cache[(episode, boundary)] = (
                state[0].detach().clone(),
                state[1].detach().clone(),
            )
            cursor = boundary
    return cache


@torch.no_grad()
def audit_burn_in(
    model: ClasherPolicy,
    corpus: DirectSimpleBehaviorCorpus,
    windows: tuple[RecurrentBehaviorWindow, ...],
    cache: dict[tuple[int, int], State],
    *,
    device: torch.device,
    maximum_windows: int = 64,
) -> float:
    """Prove cached-state plus causal prefix reaches the full replay state."""

    model.eval()
    maximum_error = 0.0
    checked = 0
    for window in windows:
        if window.burn_in_rows == 0:
            continue
        state = cache[(window.episode, window.context_start)]
        rows = np.arange(window.context_start, window.train_start, dtype=np.int64)[
            None, :
        ]
        reached = model(batch_inputs(corpus.arrays, rows, device), state).next_state
        expected = cache[(window.episode, window.train_start)]
        maximum_error = max(
            maximum_error,
            float((reached[0] - expected[0]).abs().max()),
            float((reached[1] - expected[1]).abs().max()),
        )
        checked += 1
        if checked >= maximum_windows:
            break
    if checked == 0:
        raise ValueError("burn-in audit found no prefixed recurrent windows")
    return maximum_error


def train_epoch(
    model: ClasherPolicy,
    corpus: DirectSimpleBehaviorCorpus,
    windows: tuple[RecurrentBehaviorWindow, ...],
    cache: dict[tuple[int, int], State],
    optimizer: torch.optim.Optimizer,
    trainable: list[nn.Parameter],
    *,
    device: torch.device,
    batch_windows: int,
    rng: np.random.Generator,
) -> dict[str, float]:
    model.train()
    groups: dict[tuple[int, int], list[RecurrentBehaviorWindow]] = defaultdict(list)
    for window in windows:
        groups[(window.burn_in_rows, window.train_rows)].append(window)
    group_keys = list(groups)
    rng.shuffle(group_keys)
    losses: list[float] = []
    gradient_max = 0.0
    for key in group_keys:
        group = groups[key]
        rng.shuffle(group)
        for start in range(0, len(group), batch_windows):
            selected = group[start : start + batch_windows]
            hidden = torch.cat(
                [cache[(row.episode, row.context_start)][0] for row in selected],
                dim=0,
            )
            cell = torch.cat(
                [cache[(row.episode, row.context_start)][1] for row in selected],
                dim=0,
            )
            state = (hidden, cell)
            if key[0] > 0:
                prefix_rows = np.stack(
                    [
                        np.arange(row.context_start, row.train_start, dtype=np.int64)
                        for row in selected
                    ]
                )
                with torch.no_grad():
                    state = model(
                        batch_inputs(corpus.arrays, prefix_rows, device), state
                    ).next_state
                state = (state[0].detach(), state[1].detach())
            train_rows = np.stack(
                [
                    np.arange(row.train_start, row.end, dtype=np.int64)
                    for row in selected
                ]
            )
            loss, _next_state, _metrics, _next_event_hazard = _forward_loss(
                model, corpus, train_rows, state, device=device
            )
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("direct behavior loss became non-finite")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            gradient = nn.utils.clip_grad_norm_(trainable, 1.0)
            if not bool(torch.isfinite(gradient)):
                raise FloatingPointError("direct behavior gradient became non-finite")
            optimizer.step()
            losses.append(float(loss.detach()))
            gradient_max = max(gradient_max, float(gradient))
    return {
        "loss": float(np.mean(losses)),
        "batches": float(len(losses)),
        "gradient_norm_max": gradient_max,
    }


def _eligible(metrics: dict[str, float], args: argparse.Namespace) -> bool:
    return bool(
        metrics["play_precision"] >= args.minimum_play_precision
        and metrics["play_recall"] >= args.minimum_play_recall
        and metrics["wait_accuracy"] >= args.minimum_wait_accuracy
        and metrics["card_accuracy"] >= args.minimum_card_accuracy
        and metrics["tile_accuracy"] >= args.minimum_tile_accuracy
        and metrics["exact_action_accuracy"] >= args.minimum_exact_action_accuracy
    )


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
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--teacher-checkpoint", type=Path, required=True)
    parser.add_argument("--train-corpus", type=Path, required=True)
    parser.add_argument("--validation-corpus", type=Path, required=True)
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--train-steps", type=int, default=64)
    parser.add_argument("--burn-in-steps", type=int, default=32)
    parser.add_argument("--batch-windows", type=int, default=8)
    parser.add_argument(
        "--trainable-scope",
        choices=("mode-bias-only", "mode-only", "actor"),
        default="mode-only",
    )
    parser.add_argument("--initialize-constant-event-mode", action="store_true")
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--minimum-play-precision", type=float, default=0.70)
    parser.add_argument("--minimum-play-recall", type=float, default=0.70)
    parser.add_argument("--minimum-wait-accuracy", type=float, default=0.95)
    parser.add_argument("--minimum-card-accuracy", type=float, default=0.85)
    parser.add_argument("--minimum-tile-accuracy", type=float, default=0.20)
    parser.add_argument("--minimum-exact-action-accuracy", type=float, default=0.80)
    args = parser.parse_args()
    if args.output_checkpoint.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite direct behavior pretraining artifacts")
    if args.epochs < 1 or args.batch_windows < 1 or args.learning_rate <= 0.0:
        raise ValueError("invalid direct behavior training settings")
    if args.burn_in_steps < 1:
        raise ValueError("direct recurrent pretraining requires positive burn-in")
    for name in (
        "minimum_play_precision",
        "minimum_play_recall",
        "minimum_wait_accuracy",
        "minimum_card_accuracy",
        "minimum_tile_accuracy",
        "minimum_exact_action_accuracy",
    ):
        if not 0.0 <= float(getattr(args, name)) <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device(args.device)
    payload, model = load_student(args.initial_checkpoint, device)
    teacher_payload, teacher_config = load_teacher_identity(args.teacher_checkpoint)
    event_threshold = (
        teacher_config.play_hazard_threshold
        if model.config.deterministic_hierarchy == "event"
        else -math.log1p(-teacher_config.play_hazard_threshold)
    )
    train_metadata, train_corpus = load_direct_simple_behavior_corpus(args.train_corpus)
    validation_metadata, validation_corpus = load_direct_simple_behavior_corpus(
        args.validation_corpus
    )
    expected_tokens = tuple(payload["token_names"])
    if (
        tuple(train_metadata["token_names"]) != expected_tokens
        or tuple(validation_metadata["token_names"]) != expected_tokens
    ):
        raise ValueError(
            "direct behavior corpus vocabulary differs from the initializer"
        )
    for name, metadata in (
        ("training", train_metadata),
        ("validation", validation_metadata),
    ):
        if metadata.get("schema") != CORPUS_SCHEMA:
            raise ValueError(f"{name} corpus uses an unknown behavior schema")
        if metadata.get("initial_recurrent_state") != (
            "exact-model-reset-state-per-episode"
        ):
            raise ValueError(f"{name} corpus lacks exact recurrent reset authority")
        if metadata.get("teacher_factor_authority") != (
            "original-one-step-policy-boundary"
        ):
            raise ValueError(
                f"{name} corpus lacks original-boundary teacher-factor authority"
            )
    for key in ("checkpoint_sha256", "opponents"):
        if train_metadata.get(key) != validation_metadata.get(key):
            raise ValueError(f"training and validation behavior {key} differ")
    teacher_sha256 = file_sha256(args.teacher_checkpoint)
    if train_metadata.get("checkpoint_sha256") != teacher_sha256:
        raise ValueError("behavior corpus was not collected by the requested teacher")
    if validation_metadata.get("checkpoint_sha256") != teacher_sha256:
        raise ValueError("validation behavior used a different frozen teacher")
    if tuple(teacher_payload["token_names"]) != expected_tokens:
        raise ValueError("teacher and student vocabularies differ")
    if teacher_config.num_tokens != model.config.num_tokens:
        raise ValueError("teacher and student vocabularies differ")
    train_backend = train_metadata.get("simulation_backend_metadata")
    validation_backend = validation_metadata.get("simulation_backend_metadata")
    if not isinstance(train_backend, dict) or not isinstance(validation_backend, dict):
        raise TypeError("behavior corpora lack simulator metadata")
    if train_backend.get("metadata_digest") != validation_backend.get(
        "metadata_digest"
    ):
        raise ValueError("training and validation simulator contracts differ")
    if file_sha256(args.train_corpus) == file_sha256(args.validation_corpus):
        raise ValueError("training and validation behavior corpora must be disjoint")
    if train_metadata.get("seed") == validation_metadata.get("seed"):
        raise ValueError("training and validation behavior seeds must differ")
    for name, corpus in (
        ("training", train_corpus),
        ("validation", validation_corpus),
    ):
        if "play_hazard_probabilities" not in corpus.arrays:
            raise ValueError(f"{name} corpus lacks original-boundary hazard factors")
        probabilities = np.asarray(corpus.arrays["play_hazard_probabilities"])
        if probabilities.shape != (corpus.row_count,):
            raise ValueError(f"{name} hazard-factor shape differs from behavior rows")
        if not np.isfinite(probabilities).all() or bool(
            ((probabilities < 0.0) | (probabilities >= 1.0)).any()
        ):
            raise ValueError(f"{name} corpus contains invalid hazard factors")
    constant_event_probability: float | None = None
    if args.initialize_constant_event_mode:
        constant_event_probability = float(
            np.mean(train_corpus.arrays["play_hazard_probabilities"])
        )
        initialize_constant_event_mode(model, constant_event_probability)
    train_windows = recurrent_behavior_windows(
        train_corpus.episode_offsets,
        train_steps=args.train_steps,
        burn_in_steps=args.burn_in_steps,
    )
    trainable_names, trainable = select_trainable_parameters(
        model, args.trainable_scope
    )
    optimizer = torch.optim.AdamW(
        trainable, lr=args.learning_rate, weight_decay=args.weight_decay
    )
    initial = evaluate(
        model,
        validation_corpus,
        device=device,
        sequence_steps=args.train_steps,
        event_threshold=event_threshold,
    )
    initial_eligible = _eligible(initial, args)
    history: list[dict[str, Any]] = [
        {"epoch": 0, "validation": initial, "eligible": initial_eligible}
    ]
    best_score = (
        (
            initial["play_f1"],
            initial["balanced_timing_accuracy"],
            initial["exact_action_accuracy"],
            -initial["loss"],
        )
        if initial_eligible
        else (-math.inf, -math.inf, -math.inf, -math.inf)
    )
    best_state: dict[str, Tensor] | None = (
        {
            name: value.detach().cpu().clone()
            for name, value in model.state_dict().items()
        }
        if initial_eligible
        else None
    )
    best_epoch: int | None = 0 if initial_eligible else None
    best_validation: dict[str, float] | None = initial if initial_eligible else None
    rng = np.random.default_rng(args.seed)
    for epoch in range(1, args.epochs + 1):
        started = time.monotonic()
        cache = build_state_cache(model, train_corpus, train_windows, device=device)
        burn_in_max_error = audit_burn_in(
            model, train_corpus, train_windows, cache, device=device
        )
        if burn_in_max_error > 1e-6:
            raise RuntimeError("burn-in replay differs from the full recurrent trace")
        training = train_epoch(
            model,
            train_corpus,
            train_windows,
            cache,
            optimizer,
            trainable,
            device=device,
            batch_windows=args.batch_windows,
            rng=rng,
        )
        validation = evaluate(
            model,
            validation_corpus,
            device=device,
            sequence_steps=args.train_steps,
            event_threshold=event_threshold,
        )
        eligible = _eligible(validation, args)
        row = {
            "epoch": epoch,
            "training": training,
            "validation": validation,
            "burn_in_max_abs_error": burn_in_max_error,
            "elapsed_seconds": time.monotonic() - started,
            "eligible": eligible,
        }
        history.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        score = (
            validation["play_f1"],
            validation["balanced_timing_accuracy"],
            validation["exact_action_accuracy"],
            -validation["loss"],
        )
        if eligible and score > best_score:
            best_score = score
            best_epoch = epoch
            best_validation = validation
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
    report = {
        "schema": SCHEMA,
        "initial_checkpoint": str(args.initial_checkpoint.resolve()),
        "initial_checkpoint_sha256": file_sha256(args.initial_checkpoint),
        "teacher_checkpoint": str(args.teacher_checkpoint.resolve()),
        "teacher_checkpoint_sha256": teacher_sha256,
        "train_corpus": str(args.train_corpus.resolve()),
        "train_corpus_sha256": file_sha256(args.train_corpus),
        "validation_corpus": str(args.validation_corpus.resolve()),
        "validation_corpus_sha256": file_sha256(args.validation_corpus),
        "seed": args.seed,
        "device": str(device),
        "epochs": args.epochs,
        "train_steps": args.train_steps,
        "burn_in_steps": args.burn_in_steps,
        "batch_windows": args.batch_windows,
        "trainable_scope": args.trainable_scope,
        "constant_event_initialization": args.initialize_constant_event_mode,
        "constant_event_probability_from_training_only": constant_event_probability,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "timing_sample_weight": 1.0,
        "natural_frequency_timing": True,
        "timing_target": "original-boundary-positive-weight-corrected-teacher-hazard",
        "event_hazard_threshold": event_threshold,
        "event_probability_threshold": teacher_config.play_hazard_threshold,
        "event_accumulator_representation": (
            "probability"
            if model.config.deterministic_hierarchy == "event"
            else "hazard"
        ),
        "train_teacher_play_probability": {
            "minimum": float(np.min(train_corpus.arrays["play_hazard_probabilities"])),
            "mean": float(np.mean(train_corpus.arrays["play_hazard_probabilities"])),
            "maximum": float(np.max(train_corpus.arrays["play_hazard_probabilities"])),
        },
        "validation_teacher_play_probability": {
            "minimum": float(
                np.min(validation_corpus.arrays["play_hazard_probabilities"])
            ),
            "mean": float(
                np.mean(validation_corpus.arrays["play_hazard_probabilities"])
            ),
            "maximum": float(
                np.max(validation_corpus.arrays["play_hazard_probabilities"])
            ),
        },
        "selection_gates": {
            "minimum_play_precision": args.minimum_play_precision,
            "minimum_play_recall": args.minimum_play_recall,
            "minimum_wait_accuracy": args.minimum_wait_accuracy,
            "minimum_card_accuracy": args.minimum_card_accuracy,
            "minimum_tile_accuracy": args.minimum_tile_accuracy,
            "minimum_exact_action_accuracy": args.minimum_exact_action_accuracy,
        },
        "train_windows": len(train_windows),
        "trainable_parameter_count": sum(value.numel() for value in trainable),
        "trainable_parameter_names": trainable_names,
        "initial_validation": initial,
        "best_epoch": best_epoch,
        "best_validation": best_validation,
        "history": history,
        "status": "accepted-offline" if best_state is not None else "rejected-offline",
        "output_checkpoint": (
            str(args.output_checkpoint.resolve()) if best_state is not None else None
        ),
        "closed_loop_gate_pending": best_state is not None,
    }
    _atomic_json(args.report, report)
    if best_state is None:
        raise SystemExit("no direct behavior epoch passed the offline gates")
    output_payload = dict(payload)
    output_payload["model_state_dict"] = best_state
    output_payload.pop("optimizer_state_dict", None)
    output_payload["direct_simple_behavior_pretraining"] = report
    output_payload["update"] = 0
    output_payload["total_transitions"] = 0
    _atomic_checkpoint(args.output_checkpoint, output_payload)
    print(json.dumps({"status": report["status"], "best_epoch": best_epoch}))


if __name__ == "__main__":
    main()
