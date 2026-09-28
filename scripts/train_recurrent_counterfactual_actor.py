"""Train an actor end to end on recurrent terminal-counterfactual trajectories."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import copy
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
from clasher.rl.imitation import _sequence_batch_inputs, load_corpus
from clasher.rl.imitation_objective import (
    SpatialImitationConfig,
    build_token_spatial_semantics,
    factorized_spatial_imitation_loss,
)
from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs
from clasher.rl.structured_obs import StructuredObservationBuilder
from scripts.fit_terminal_counterfactual_adapter import (
    PreferenceRows,
    build_preferences,
)


@dataclass(frozen=True)
class ChunkPreferences:
    state_indices: Tensor
    positive_types: Tensor
    negative_types: Tensor
    weights: Tensor
    kinds: Tensor

    @property
    def count(self) -> int:
        return int(self.state_indices.numel())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_model(payload: dict[str, Any], *, device: torch.device) -> ClasherPolicy:
    config = PolicyConfig.from_dict(payload["model_config"])
    state = payload["model_state_dict"]
    card_stats = state.get("actor_encoder.card_stat_features")
    if not isinstance(card_stats, (np.ndarray, torch.Tensor)):
        raise TypeError("checkpoint has no actor card-stat buffer")
    semantic_stats = state.get("actor_encoder.semantic_card_features")
    if semantic_stats is not None:
        if not isinstance(semantic_stats, (np.ndarray, torch.Tensor)):
            raise TypeError("checkpoint semantic card-stat buffer is invalid")
        card_stats = torch.cat(
            [torch.as_tensor(card_stats), torch.as_tensor(semantic_stats)],
            dim=-1,
        )
    model = ClasherPolicy(config, card_stats).to(device)
    model.load_state_dict(state)
    return model


def _load_counterfactual_arrays(path: Path) -> tuple[np.ndarray, PreferenceRows]:
    with np.load(path, allow_pickle=False) as archive:
        root_rows = archive["counterfactual_root_rows"].copy()
        payload = {
            name.removeprefix("root_"): archive[name].copy()
            for name in archive.files
            if name.startswith("root_")
        }
    if not len(root_rows):
        raise ValueError("trajectory corpus has no counterfactual roots")
    preferences = build_preferences(payload)
    if not len(preferences.state_indices):
        raise ValueError("trajectory corpus has no counterfactual preferences")
    if np.any(preferences.state_indices < 0) or np.any(
        preferences.state_indices >= len(root_rows)
    ):
        raise ValueError("counterfactual preference state is outside root table")
    return root_rows.astype(np.int64, copy=False), preferences


def _candidate_order(
    outcome: float,
    crowns: int,
    tower_damage: float,
) -> tuple[float, int, float]:
    return outcome, crowns, tower_damage


def _build_action_preferences(
    payload: dict[str, np.ndarray],
    *,
    decisive_only: bool = False,
    minimum_crown_gap: int = 0,
    minimum_tower_damage_gap: float = 0.0,
) -> PreferenceRows:
    """Build exact base-relative preferences without discarding placement tiles."""

    required = {
        "base_actions",
        "candidate_actions",
        "candidate_valid",
        "candidate_scores",
        "candidate_crown_differences",
        "candidate_tower_damage_differences",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"action-level counterfactual arrays are missing: {missing}")
    base_actions = payload["base_actions"]
    candidates = payload["candidate_actions"]
    valid = payload["candidate_valid"]
    outcomes = payload["candidate_scores"]
    crowns = payload["candidate_crown_differences"]
    tower_damage = payload["candidate_tower_damage_differences"]
    state_indices: list[int] = []
    positive_actions: list[int] = []
    negative_actions: list[int] = []
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
        base_action = int(base_actions[state])
        base_order = _candidate_order(
            float(outcomes[state, base_index]),
            int(crowns[state, base_index]),
            float(tower_damage[state, base_index]),
        )
        for candidate_index in state_candidates.tolist():
            candidate_action = int(candidates[state, candidate_index])
            if candidate_action == base_action:
                continue
            candidate_order = _candidate_order(
                float(outcomes[state, candidate_index]),
                int(crowns[state, candidate_index]),
                float(tower_damage[state, candidate_index]),
            )
            if candidate_order == base_order:
                continue
            if decisive_only and candidate_order[0] == base_order[0]:
                continue
            outcome_gap = candidate_order[0] - base_order[0]
            crown_gap = candidate_order[1] - base_order[1]
            damage_gap = candidate_order[2] - base_order[2]
            if outcome_gap == 0.0:
                if crown_gap != 0:
                    if abs(crown_gap) < minimum_crown_gap:
                        continue
                elif abs(damage_gap) < minimum_tower_damage_gap:
                    continue
            candidate_is_better = candidate_order > base_order
            positive, negative = (
                (candidate_action, base_action)
                if candidate_is_better
                else (base_action, candidate_action)
            )
            if candidate_order[0] != base_order[0]:
                weight = 4.0
            elif candidate_order[1] != base_order[1]:
                weight = 2.0
            else:
                damage_gap = abs(candidate_order[2] - base_order[2])
                weight = 1.0 + min(1.0, float(np.log1p(damage_gap) / 8.0))
            state_indices.append(state)
            positive_actions.append(positive)
            negative_actions.append(negative)
            weights.append(weight)
            kinds.append(1 if candidate_is_better else 0)
    return PreferenceRows(
        state_indices=np.asarray(state_indices, dtype=np.int64),
        positive_types=np.asarray(positive_actions, dtype=np.int64),
        negative_types=np.asarray(negative_actions, dtype=np.int64),
        weights=np.asarray(weights, dtype=np.float32),
        kinds=np.asarray(kinds, dtype=np.int8),
    )


def _load_counterfactual_arrays_with_level(
    path: Path,
    *,
    action_level: bool,
    decisive_only: bool = False,
    minimum_crown_gap: int = 0,
    minimum_tower_damage_gap: float = 0.0,
) -> tuple[np.ndarray, PreferenceRows]:
    with np.load(path, allow_pickle=False) as archive:
        root_rows = archive["counterfactual_root_rows"].copy()
        payload = {
            name.removeprefix("root_"): archive[name].copy()
            for name in archive.files
            if name.startswith("root_")
        }
    if not len(root_rows):
        raise ValueError("trajectory corpus has no counterfactual roots")
    preferences = (
        _build_action_preferences(
            payload,
            decisive_only=decisive_only,
            minimum_crown_gap=minimum_crown_gap,
            minimum_tower_damage_gap=minimum_tower_damage_gap,
        )
        if action_level
        else build_preferences(payload)
    )
    if not len(preferences.state_indices):
        raise ValueError("trajectory corpus has no counterfactual preferences")
    if np.any(preferences.state_indices < 0) or np.any(
        preferences.state_indices >= len(root_rows)
    ):
        raise ValueError("counterfactual preference state is outside root table")
    return root_rows.astype(np.int64, copy=False), preferences


def episode_sequences(episode_ids: np.ndarray) -> list[np.ndarray]:
    sequences: list[np.ndarray] = []
    for episode_id in np.unique(episode_ids):
        rows = np.flatnonzero(episode_ids == episode_id)
        if not len(rows):
            continue
        if np.any(np.diff(rows) != 1):
            raise ValueError("trajectory episode rows must be contiguous")
        sequences.append(rows)
    if not sequences:
        raise ValueError("trajectory corpus has no episodes")
    return sequences


def chunk_preferences(
    rows: PreferenceRows,
    root_rows: np.ndarray,
    *,
    start: int,
    stop: int,
    device: torch.device,
) -> ChunkPreferences:
    trajectory_rows = root_rows[rows.state_indices]
    selected = np.flatnonzero(
        (trajectory_rows >= start) & (trajectory_rows < stop)
    )
    return ChunkPreferences(
        state_indices=torch.as_tensor(
            trajectory_rows[selected] - start,
            dtype=torch.long,
            device=device,
        ),
        positive_types=torch.as_tensor(
            rows.positive_types[selected], dtype=torch.long, device=device
        ),
        negative_types=torch.as_tensor(
            rows.negative_types[selected], dtype=torch.long, device=device
        ),
        weights=torch.as_tensor(
            rows.weights[selected], dtype=torch.float32, device=device
        ),
        kinds=torch.as_tensor(
            rows.kinds[selected], dtype=torch.int8, device=device
        ),
    )


def pairwise_preference_loss(
    action_type_logits: Tensor,
    preferences: ChunkPreferences,
) -> Tensor:
    if action_type_logits.ndim != 2:
        raise ValueError("action type logits must have shape [time, types]")
    if preferences.count == 0:
        return action_type_logits.sum() * 0.0
    positive = action_type_logits[
        preferences.state_indices, preferences.positive_types
    ]
    negative = action_type_logits[
        preferences.state_indices, preferences.negative_types
    ]
    return (
        F.softplus(-(positive - negative)) * preferences.weights
    ).sum() / preferences.weights.sum().clamp_min(1e-8)


def hazard_preference_loss(
    current_logits: Tensor,
    reference_logits: Tensor,
    preferences: ChunkPreferences,
) -> Tensor:
    """Move only placement-vs-wait hazard margins relative to the parent."""

    if current_logits.ndim != 1 or reference_logits.shape != current_logits.shape:
        raise ValueError("hazard logits must be equally shaped rank-one tensors")
    if preferences.count == 0:
        return current_logits.sum() * 0.0
    placement_actions = NUM_HAND_SLOTS * NUM_TILES
    positive_placement = preferences.positive_types < placement_actions
    negative_placement = preferences.negative_types < placement_actions
    crossing = positive_placement != negative_placement
    if not bool(crossing.any()):
        return current_logits.sum() * 0.0
    state_indices = preferences.state_indices[crossing]
    direction = torch.where(
        positive_placement[crossing],
        torch.ones_like(state_indices, dtype=current_logits.dtype),
        -torch.ones_like(state_indices, dtype=current_logits.dtype),
    )
    all_delta = current_logits - reference_logits
    delta = all_delta[state_indices] - all_delta.mean()
    weights = preferences.weights[crossing]
    losses = F.softplus(-(direction * delta))
    crossing_kinds = preferences.kinds[crossing]
    strata: list[Tensor] = []
    for kind in (0, 1):
        selected = crossing_kinds == kind
        if bool(selected.any()):
            strata.append(
                (losses[selected] * weights[selected]).sum()
                / weights[selected].sum().clamp_min(1e-8)
            )
    return torch.stack(strata).mean()


def _sequence_inputs(
    arrays: dict[str, np.ndarray],
    rows: np.ndarray,
    device: torch.device,
    *,
    trim_entity_padding: bool,
) -> PolicyInputs:
    inputs = _sequence_batch_inputs(
        arrays,
        rows.reshape(1, -1),
        device,
        trim_entity_padding=trim_entity_padding,
    )
    inputs.episode_starts[0, 0] = bool(arrays["episode_starts"][rows[0]])
    return inputs


def _masked_action_type_predictions(
    logits: Tensor,
    action_mask: Tensor,
) -> Tensor:
    placement = action_mask[..., :-2].reshape(
        *action_mask.shape[:-1], NUM_HAND_SLOTS, -1
    )
    legal_types = torch.cat(
        [placement.any(dim=-1), action_mask[..., -2:]], dim=-1
    )
    return logits.masked_fill(~legal_types, -torch.inf).argmax(dim=-1)


def _action_types(actions: Tensor) -> Tensor:
    placement_actions = NUM_HAND_SLOTS * NUM_TILES
    return torch.where(
        actions < placement_actions,
        actions // NUM_TILES,
        NUM_HAND_SLOTS + (actions == placement_actions + 1).long(),
    )


@torch.no_grad()
def evaluate(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    sequences: list[np.ndarray],
    root_rows: np.ndarray,
    preferences: PreferenceRows,
    *,
    device: torch.device,
    sequence_length: int,
    trim_entity_padding: bool,
    spatial_config: SpatialImitationConfig,
    spatial_semantics: Any,
    action_level_preferences: bool = False,
    reference_model: ClasherPolicy | None = None,
    hazard_counterfactual: bool = False,
) -> dict[str, Any]:
    if hazard_counterfactual and reference_model is None:
        raise ValueError("hazard counterfactual evaluation requires a reference model")
    model.eval()
    if reference_model is not None:
        reference_model.eval()
    behavior_loss_sum = 0.0
    behavior_rows = 0
    type_correct = 0
    exact_correct = 0
    hazard_squared_error_sum = 0.0
    hazard_absolute_error_sum = 0.0
    margins: list[np.ndarray] = []
    kinds: list[np.ndarray] = []
    root_cursor_rows = root_rows[preferences.state_indices]

    for episode in sequences:
        state = model.initial_state(1, device=device)
        reference_state = (
            reference_model.initial_state(1, device=device)
            if reference_model is not None
            else None
        )
        for offset in range(0, len(episode), sequence_length):
            chunk = episode[offset : offset + sequence_length]
            inputs = _sequence_inputs(
                arrays,
                chunk,
                device,
                trim_entity_padding=trim_entity_padding,
            )
            output = model(inputs, state)
            state = tuple(value.detach() for value in output.next_state)
            reference_output = None
            if reference_model is not None:
                assert reference_state is not None
                reference_output = reference_model(inputs, reference_state)
                reference_state = tuple(
                    value.detach() for value in reference_output.next_state
                )
            logits = output.joint_logits[0]
            targets = torch.as_tensor(
                arrays["expert_actions"][chunk],
                dtype=torch.long,
                device=device,
            )
            breakdown = factorized_spatial_imitation_loss(
                logits,
                targets,
                inputs.action_mask[0],
                inputs.hand_ids[0],
                spatial_semantics,
                config=spatial_config,
                reduction="sum",
            )
            behavior_loss_sum += float(breakdown.total)
            behavior_rows += len(chunk)
            type_predictions = _masked_action_type_predictions(
                output.action_type_logits[0], inputs.action_mask[0]
            )
            type_correct += int((type_predictions == _action_types(targets)).sum())
            exact_predictions = logits.masked_fill(
                ~inputs.action_mask[0], -torch.inf
            ).argmax(dim=-1)
            exact_correct += int((exact_predictions == targets).sum())
            if hazard_counterfactual:
                if output.play_hazard_logits is None or (
                    reference_output is None
                    or reference_output.play_hazard_logits is None
                ):
                    raise ValueError("hazard counterfactual model has no hazard logits")
                hazard_delta = (
                    output.play_hazard_logits[0]
                    - reference_output.play_hazard_logits[0]
                )
                hazard_squared_error_sum += float(hazard_delta.square().sum())
                hazard_absolute_error_sum += float(hazard_delta.abs().sum())

            selected = np.flatnonzero(
                (root_cursor_rows >= int(chunk[0]))
                & (root_cursor_rows <= int(chunk[-1]))
            )
            if len(selected):
                local = torch.as_tensor(
                    root_cursor_rows[selected] - int(chunk[0]),
                    dtype=torch.long,
                    device=device,
                )
                positive = torch.as_tensor(
                    preferences.positive_types[selected],
                    dtype=torch.long,
                    device=device,
                )
                negative = torch.as_tensor(
                    preferences.negative_types[selected],
                    dtype=torch.long,
                    device=device,
                )
                if hazard_counterfactual:
                    assert reference_output is not None
                    assert output.play_hazard_logits is not None
                    assert reference_output.play_hazard_logits is not None
                    placement_actions = NUM_HAND_SLOTS * NUM_TILES
                    positive_placement = positive < placement_actions
                    negative_placement = negative < placement_actions
                    crossing = positive_placement != negative_placement
                    if bool(crossing.any()):
                        direction = torch.where(
                            positive_placement[crossing],
                            torch.ones_like(
                                local[crossing],
                                dtype=output.play_hazard_logits.dtype,
                            ),
                            -torch.ones_like(
                                local[crossing],
                                dtype=output.play_hazard_logits.dtype,
                            ),
                        )
                        chunk_delta = (
                            output.play_hazard_logits[0]
                            - reference_output.play_hazard_logits[0]
                        )
                        delta = (
                            chunk_delta[local[crossing]] - chunk_delta.mean()
                        )
                        margins.append(
                            (direction * delta).float().cpu().numpy()
                        )
                        kinds.append(preferences.kinds[selected][crossing.cpu().numpy()])
                else:
                    preference_logits = (
                        output.joint_logits[0]
                        if action_level_preferences
                        else output.action_type_logits[0]
                    )
                    margins.append(
                        (
                            preference_logits[local, positive]
                            - preference_logits[local, negative]
                        )
                        .float()
                        .cpu()
                        .numpy()
                    )
                    kinds.append(preferences.kinds[selected])

    if not margins or behavior_rows == 0:
        raise ValueError("evaluation did not cover behavior rows and preferences")
    all_margins = np.concatenate(margins)
    all_kinds = np.concatenate(kinds)

    def preference_metrics(mask: np.ndarray) -> dict[str, float | int]:
        selected = all_margins[mask]
        return {
            "pairs": int(mask.sum()),
            "accuracy": float((selected > 0.0).mean()) if len(selected) else 0.0,
            "mean_margin": float(selected.mean()) if len(selected) else 0.0,
        }

    result: dict[str, Any] = {
        "behavior": {
            "rows": behavior_rows,
            "spatial_loss": behavior_loss_sum / behavior_rows,
            "action_type_accuracy": type_correct / behavior_rows,
            "exact_action_accuracy": exact_correct / behavior_rows,
        },
        "preferences": {
            "overall": preference_metrics(np.ones(len(all_kinds), dtype=np.bool_)),
            "corrective": preference_metrics(all_kinds == 1),
            "safety": preference_metrics(all_kinds == 0),
        },
    }
    if hazard_counterfactual:
        result["behavior"]["hazard_logit_rmse"] = float(
            np.sqrt(hazard_squared_error_sum / behavior_rows)
        )
        result["behavior"]["hazard_logit_mae"] = (
            hazard_absolute_error_sum / behavior_rows
        )
    return result


def _actor_trainable(name: str, prefixes: tuple[str, ...] = ()) -> bool:
    if prefixes:
        return name.startswith(prefixes)
    return not name.startswith(
        (
            "critic_encoder.",
            "value_head.",
            "opponent_hand_head.",
            "opponent_elixir_head.",
        )
    )


def _eligible(
    metrics: dict[str, Any],
    initial: dict[str, Any],
    *,
    maximum_safety_regression: float,
    maximum_behavior_regression: float,
    minimum_corrective_improvement: float,
    behavior_accuracy_key: str = "action_type_accuracy",
) -> bool:
    return bool(
        metrics["preferences"]["safety"]["accuracy"]
        >= initial["preferences"]["safety"]["accuracy"]
        - maximum_safety_regression
        and metrics["behavior"][behavior_accuracy_key]
        >= initial["behavior"][behavior_accuracy_key]
        - maximum_behavior_regression
        and metrics["preferences"]["corrective"]["accuracy"]
        >= initial["preferences"]["corrective"]["accuracy"]
        + minimum_corrective_improvement
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--train-corpus", type=Path, required=True)
    parser.add_argument("--validation-corpus", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--torch-threads", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1062401)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--sequence-length", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--behavior-coef", type=float, default=1.0)
    parser.add_argument("--counterfactual-coef", type=float, default=0.3)
    parser.add_argument("--root-behavior-weight", type=float, default=0.25)
    parser.add_argument("--maximum-safety-regression", type=float, default=0.01)
    parser.add_argument("--maximum-behavior-regression", type=float, default=0.01)
    parser.add_argument("--minimum-corrective-improvement", type=float, default=0.01)
    parser.add_argument("--minimum-crown-gap", type=int, default=0)
    parser.add_argument("--minimum-tower-damage-gap", type=float, default=0.0)
    parser.add_argument("--maximum-hazard-logit-rmse", type=float, default=0.10)
    parser.add_argument("--minimum-hazard-safety-accuracy", type=float, default=0.50)
    parser.add_argument("--trim-entity-padding", action="store_true")
    parser.add_argument(
        "--action-level-preferences",
        action="store_true",
        help="rank exact flat actions so same-card placement alternatives are retained",
    )
    parser.add_argument(
        "--decisive-only",
        action="store_true",
        help="use only terminal win/loss preference pairs, excluding crown/damage ties",
    )
    parser.add_argument(
        "--hazard-counterfactual",
        action="store_true",
        help="fit parent-relative placement-vs-wait preferences on the hazard head",
    )
    parser.add_argument(
        "--trainable-prefix",
        action="append",
        default=[],
        help="restrict optimization to this parameter-name prefix; repeat as needed",
    )
    args = parser.parse_args()
    if args.output_checkpoint.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite output checkpoint or report")
    if args.epochs <= 0 or args.sequence_length <= 1 or args.torch_threads <= 0:
        raise ValueError("epochs, sequence length, and thread count are invalid")
    if args.learning_rate <= 0.0 or args.weight_decay < 0.0:
        raise ValueError("optimizer settings are invalid")
    if args.behavior_coef < 0.0 or args.counterfactual_coef <= 0.0:
        raise ValueError("loss coefficients are invalid")
    if not 0.0 <= args.root_behavior_weight <= 1.0:
        raise ValueError("root behavior weight must be between zero and one")
    if args.decisive_only and not args.action_level_preferences:
        raise ValueError("decisive-only requires action-level preferences")
    if args.hazard_counterfactual and not args.action_level_preferences:
        raise ValueError("hazard counterfactual training requires action-level pairs")
    if args.minimum_crown_gap < 0 or args.minimum_tower_damage_gap < 0.0:
        raise ValueError("counterfactual margin thresholds must be nonnegative")
    if args.maximum_hazard_logit_rmse < 0.0 or not (
        0.0 <= args.minimum_hazard_safety_accuracy <= 1.0
    ):
        raise ValueError("hazard selection gates are invalid")

    torch.set_num_threads(args.torch_threads)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device(args.device)
    payload = torch.load(
        args.initial_checkpoint, map_location=device, weights_only=False
    )
    model = _load_model(payload, device=device)
    reference_model = copy.deepcopy(model).eval() if args.hazard_counterfactual else None
    if reference_model is not None:
        for parameter in reference_model.parameters():
            parameter.requires_grad_(False)
    train_metadata, train_arrays = load_corpus(args.train_corpus)
    validation_metadata, validation_arrays = load_corpus(args.validation_corpus)
    expected_tokens = tuple(payload["token_names"])
    if tuple(train_metadata.token_names) != expected_tokens or tuple(
        validation_metadata.token_names
    ) != expected_tokens:
        raise ValueError("trajectory corpus token vocabulary does not match policy")
    if train_metadata.max_entities != model.config.max_entities or (
        validation_metadata.max_entities != model.config.max_entities
    ):
        raise ValueError("trajectory corpus entity width does not match policy")

    train_root_rows, train_preferences = _load_counterfactual_arrays_with_level(
        args.train_corpus,
        action_level=args.action_level_preferences,
        decisive_only=args.decisive_only,
        minimum_crown_gap=args.minimum_crown_gap,
        minimum_tower_damage_gap=args.minimum_tower_damage_gap,
    )
    validation_root_rows, validation_preferences = _load_counterfactual_arrays_with_level(
        args.validation_corpus,
        action_level=args.action_level_preferences,
        decisive_only=args.decisive_only,
        minimum_crown_gap=args.minimum_crown_gap,
        minimum_tower_damage_gap=args.minimum_tower_damage_gap,
    )
    train_sequences = episode_sequences(train_arrays["episode_ids"])
    validation_sequences = episode_sequences(validation_arrays["episode_ids"])
    spatial_config = SpatialImitationConfig()
    builder = StructuredObservationBuilder(
        decks_path=args.decks_path,
        token_names=expected_tokens,
        max_entities=model.config.max_entities,
        card_semantics_version=model.config.card_semantics_version,
        canonical_lane_globals=model.config.canonical_lane_globals,
    )
    spatial_semantics = build_token_spatial_semantics(
        builder, device=device, config=spatial_config
    )

    trainable_prefixes = tuple(str(value) for value in args.trainable_prefix)
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(_actor_trainable(name, trainable_prefixes))
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    trainable_names = [
        name for name, parameter in model.named_parameters() if parameter.requires_grad
    ]
    if not trainable_names:
        raise ValueError("trainable prefixes matched no actor parameters")
    if trainable_prefixes and any(
        not any(name.startswith(prefix) for name in trainable_names)
        for prefix in trainable_prefixes
    ):
        raise ValueError("at least one trainable prefix matched no actor parameters")
    if args.hazard_counterfactual and any(
        not name.startswith(("play_hazard_head.", "play_hazard_adapter."))
        for name in trainable_names
    ):
        raise ValueError("hazard counterfactual mode may train only hazard parameters")
    optimizer = torch.optim.AdamW(
        trainable,
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )

    initial = evaluate(
        model,
        validation_arrays,
        validation_sequences,
        validation_root_rows,
        validation_preferences,
        device=device,
        sequence_length=args.sequence_length,
        trim_entity_padding=args.trim_entity_padding,
        spatial_config=spatial_config,
        spatial_semantics=spatial_semantics,
        action_level_preferences=args.action_level_preferences,
        reference_model=reference_model,
        hazard_counterfactual=args.hazard_counterfactual,
    )
    history: list[dict[str, Any]] = [{"epoch": 0, "validation": initial}]
    best_state = {
        name: value.detach().cpu().clone() for name, value in model.state_dict().items()
    }
    best_metrics = initial
    best_epoch = 0
    rng = np.random.default_rng(args.seed)
    root_row_set = set(train_root_rows.tolist())

    for epoch in range(1, args.epochs + 1):
        model.train()
        order = rng.permutation(len(train_sequences))
        behavior_sum = 0.0
        preference_sum = 0.0
        loss_sum = 0.0
        chunks = 0
        pair_chunks = 0
        gradient_norm_max = 0.0
        started = time.monotonic()
        for episode_position in order:
            episode = train_sequences[int(episode_position)]
            state = model.initial_state(1, device=device)
            reference_state = (
                reference_model.initial_state(1, device=device)
                if reference_model is not None
                else None
            )
            for offset in range(0, len(episode), args.sequence_length):
                chunk = episode[offset : offset + args.sequence_length]
                inputs = _sequence_inputs(
                    train_arrays,
                    chunk,
                    device,
                    trim_entity_padding=args.trim_entity_padding,
                )
                output = model(inputs, state)
                state = tuple(value.detach() for value in output.next_state)
                reference_output = None
                if reference_model is not None:
                    assert reference_state is not None
                    with torch.no_grad():
                        reference_output = reference_model(inputs, reference_state)
                    reference_state = tuple(
                        value.detach() for value in reference_output.next_state
                    )
                targets = torch.as_tensor(
                    train_arrays["expert_actions"][chunk],
                    dtype=torch.long,
                    device=device,
                )
                breakdown = factorized_spatial_imitation_loss(
                    output.joint_logits[0],
                    targets,
                    inputs.action_mask[0],
                    inputs.hand_ids[0],
                    spatial_semantics,
                    config=spatial_config,
                    reduction="none",
                )
                behavior_weights = torch.as_tensor(
                    [
                        args.root_behavior_weight if int(row) in root_row_set else 1.0
                        for row in chunk
                    ],
                    dtype=torch.float32,
                    device=device,
                )
                if args.hazard_counterfactual:
                    if output.play_hazard_logits is None or (
                        reference_output is None
                        or reference_output.play_hazard_logits is None
                    ):
                        raise ValueError("hazard counterfactual model has no hazard logits")
                    hazard_error = (
                        output.play_hazard_logits[0]
                        - reference_output.play_hazard_logits[0]
                    ).square()
                    behavior_loss = (
                        hazard_error * behavior_weights
                    ).sum() / behavior_weights.sum().clamp_min(1e-8)
                else:
                    behavior_loss = (
                        breakdown.total * behavior_weights
                    ).sum() / behavior_weights.sum().clamp_min(1e-8)
                chunk_rows = chunk_preferences(
                    train_preferences,
                    train_root_rows,
                    start=int(chunk[0]),
                    stop=int(chunk[-1]) + 1,
                    device=device,
                )
                if args.hazard_counterfactual:
                    assert output.play_hazard_logits is not None
                    assert reference_output is not None
                    assert reference_output.play_hazard_logits is not None
                    preference_loss = hazard_preference_loss(
                        output.play_hazard_logits[0],
                        reference_output.play_hazard_logits[0],
                        chunk_rows,
                    )
                else:
                    preference_logits = (
                        output.joint_logits[0]
                        if args.action_level_preferences
                        else output.action_type_logits[0]
                    )
                    preference_loss = pairwise_preference_loss(
                        preference_logits, chunk_rows
                    )
                loss = (
                    args.behavior_coef * behavior_loss
                    + args.counterfactual_coef * preference_loss
                )
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError("non-finite recurrent counterfactual loss")
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                gradient_norm = nn.utils.clip_grad_norm_(trainable, 0.5)
                if not bool(torch.isfinite(gradient_norm)):
                    raise FloatingPointError(
                        "non-finite recurrent counterfactual gradient norm"
                    )
                optimizer.step()
                chunks += 1
                pair_chunks += int(chunk_rows.count > 0)
                behavior_sum += float(behavior_loss.detach())
                preference_sum += float(preference_loss.detach())
                loss_sum += float(loss.detach())
                gradient_norm_max = max(
                    gradient_norm_max, float(gradient_norm.detach())
                )

        validation = evaluate(
            model,
            validation_arrays,
            validation_sequences,
            validation_root_rows,
            validation_preferences,
            device=device,
            sequence_length=args.sequence_length,
            trim_entity_padding=args.trim_entity_padding,
            spatial_config=spatial_config,
            spatial_semantics=spatial_semantics,
            action_level_preferences=args.action_level_preferences,
            reference_model=reference_model,
            hazard_counterfactual=args.hazard_counterfactual,
        )
        if args.hazard_counterfactual:
            safety = validation["preferences"]["safety"]
            eligible = bool(
                validation["preferences"]["corrective"]["accuracy"]
                >= initial["preferences"]["corrective"]["accuracy"]
                + args.minimum_corrective_improvement
                and validation["behavior"]["hazard_logit_rmse"]
                <= args.maximum_hazard_logit_rmse
                and (
                    safety["pairs"] == 0
                    or safety["accuracy"] >= args.minimum_hazard_safety_accuracy
                )
            )
        else:
            eligible = _eligible(
                validation,
                initial,
                maximum_safety_regression=args.maximum_safety_regression,
                maximum_behavior_regression=args.maximum_behavior_regression,
                minimum_corrective_improvement=args.minimum_corrective_improvement,
                behavior_accuracy_key=(
                    "exact_action_accuracy"
                    if args.action_level_preferences
                    else "action_type_accuracy"
                ),
            )
        row = {
            "epoch": epoch,
            "training": {
                "chunks": chunks,
                "preference_chunks": pair_chunks,
                "loss": loss_sum / max(1, chunks),
                "behavior_loss": behavior_sum / max(1, chunks),
                "preference_loss": preference_sum / max(1, pair_chunks),
                "gradient_norm_max": gradient_norm_max,
                "seconds": time.monotonic() - started,
            },
            "validation": validation,
            "eligible": eligible,
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        if args.hazard_counterfactual:
            candidate_score = (
                validation["preferences"]["corrective"]["accuracy"],
                validation["preferences"]["overall"]["mean_margin"],
                -validation["behavior"]["hazard_logit_rmse"],
            )
            best_score = (
                best_metrics["preferences"]["corrective"]["accuracy"],
                best_metrics["preferences"]["overall"]["mean_margin"],
                -best_metrics["behavior"]["hazard_logit_rmse"],
            )
        else:
            candidate_score = (
                validation["preferences"]["corrective"]["accuracy"],
                validation["preferences"]["overall"]["accuracy"],
                -validation["behavior"]["spatial_loss"],
            )
            best_score = (
                best_metrics["preferences"]["corrective"]["accuracy"],
                best_metrics["preferences"]["overall"]["accuracy"],
                -best_metrics["behavior"]["spatial_loss"],
            )
        if eligible and (best_epoch == 0 or candidate_score > best_score):
            best_epoch = epoch
            best_metrics = validation
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }

    result = dict(payload)
    result["model_state_dict"] = best_state
    result.pop("optimizer_state_dict", None)
    result["update"] = 0
    result["total_transitions"] = 0
    result["recurrent_counterfactual_actor"] = {
        "schema_version": 1,
        "initial_checkpoint": str(args.initial_checkpoint.resolve()),
        "initial_checkpoint_sha256": file_sha256(args.initial_checkpoint),
        "train_corpus": str(args.train_corpus.resolve()),
        "train_corpus_sha256": file_sha256(args.train_corpus),
        "validation_corpus": str(args.validation_corpus.resolve()),
        "validation_corpus_sha256": file_sha256(args.validation_corpus),
        "trainable_parameter_names": trainable_names,
        "trainable_parameter_count": sum(value.numel() for value in trainable),
        "seed": args.seed,
        "epochs": args.epochs,
        "sequence_length": args.sequence_length,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "behavior_coef": args.behavior_coef,
        "counterfactual_coef": args.counterfactual_coef,
        "root_behavior_weight": args.root_behavior_weight,
        "action_level_preferences": args.action_level_preferences,
        "decisive_only": args.decisive_only,
        "minimum_crown_gap": args.minimum_crown_gap,
        "minimum_tower_damage_gap": args.minimum_tower_damage_gap,
        "hazard_counterfactual": args.hazard_counterfactual,
        "trainable_prefixes": list(trainable_prefixes),
        "selection_gate": {
            "maximum_safety_regression": args.maximum_safety_regression,
            "maximum_behavior_regression": args.maximum_behavior_regression,
            "minimum_corrective_improvement": args.minimum_corrective_improvement,
            "maximum_hazard_logit_rmse": args.maximum_hazard_logit_rmse,
            "minimum_hazard_safety_accuracy": args.minimum_hazard_safety_accuracy,
            "behavior_accuracy_key": (
                "exact_action_accuracy"
                if args.action_level_preferences
                else "action_type_accuracy"
            ),
        },
        "best_epoch": best_epoch,
        "initial_validation": initial,
        "best_validation": best_metrics,
        "history": history,
    }
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, args.output_checkpoint)
    report = {
        **result["recurrent_counterfactual_actor"],
        "output_checkpoint": str(args.output_checkpoint.resolve()),
        "output_checkpoint_sha256": file_sha256(args.output_checkpoint),
        "model_parameter_count": sum(value.numel() for value in model.parameters()),
        "train_episodes": len(train_sequences),
        "validation_episodes": len(validation_sequences),
        "train_roots": len(train_root_rows),
        "validation_roots": len(validation_root_rows),
        "selected_nonzero_epoch": best_epoch > 0,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
