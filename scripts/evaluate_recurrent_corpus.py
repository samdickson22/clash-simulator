from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.common import BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.imitation import (
    _sequence_batch_inputs,
    load_corpus,
    load_public_observation_sidecar,
)
from clasher.rl.oracle_corpus import file_sha256
from clasher.rl.train_recurrent import resolve_torch_device


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate V2 checkpoints on complete recurrent corpus episodes"
    )
    parser.add_argument("--corpus", required=True)
    parser.add_argument(
        "--public-observation-sidecar",
        default=None,
        help="aligned confidence-aware public-state v2 observations",
    )
    parser.add_argument("--checkpoint", action="append", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument(
        "--max-episodes",
        type=int,
        default=None,
        help="deterministic bounded episode sample for rapid evidence gates",
    )
    parser.add_argument("--episode-seed", type=int, default=2301)
    parser.add_argument(
        "--exclude-max-episodes",
        type=int,
        default=None,
        help="exclude the deterministic sample selected from the full episode set",
    )
    parser.add_argument(
        "--exclude-episode-seed",
        type=int,
        default=None,
        help="seed of the deterministic episode sample to exclude",
    )
    parser.add_argument(
        "--episode-id",
        action="append",
        type=int,
        default=None,
        help="evaluate an explicit corpus episode ID; repeat for a fixed subset",
    )
    parser.add_argument(
        "--device", choices=["auto", "cpu", "mps", "cuda"], default="auto"
    )
    parser.add_argument("--json-out", default=None)
    return parser.parse_args()


def _select_episode_ids(
    episode_ids: np.ndarray,
    *,
    max_episodes: int | None,
    episode_seed: int,
    exclude_max_episodes: int | None,
    exclude_episode_seed: int | None,
    explicit_episode_ids: list[int] | None = None,
) -> np.ndarray:
    selected = np.unique(episode_ids)
    if explicit_episode_ids:
        if max_episodes is not None or exclude_max_episodes is not None:
            raise ValueError(
                "explicit episode IDs are incompatible with sampled/excluded episodes"
            )
        requested = np.unique(np.asarray(explicit_episode_ids, dtype=selected.dtype))
        missing = np.setdiff1d(requested, selected, assume_unique=True)
        if missing.size:
            raise ValueError(f"unknown explicit episode IDs: {missing.tolist()}")
        return requested
    if (exclude_max_episodes is None) != (exclude_episode_seed is None):
        raise ValueError(
            "exclude max episodes and exclude episode seed require each other"
        )
    if exclude_max_episodes is not None:
        if exclude_max_episodes <= 0 or exclude_max_episodes >= selected.size:
            raise ValueError("exclude max episodes must leave a nonempty complement")
        rng = np.random.default_rng(exclude_episode_seed)
        excluded = rng.choice(
            selected,
            size=exclude_max_episodes,
            replace=False,
        )
        selected = np.setdiff1d(selected, excluded, assume_unique=True)
    if max_episodes is not None:
        if max_episodes <= 0:
            raise ValueError("max episodes must be positive")
        if max_episodes < selected.size:
            rng = np.random.default_rng(episode_seed)
            selected = np.sort(
                rng.choice(selected, size=max_episodes, replace=False)
            )
    return selected


def _action_type_log_probs(joint_log_probs: torch.Tensor) -> torch.Tensor:
    """Aggregate normalized joint-action log probabilities by public action type."""
    placement = joint_log_probs[:, : NUM_HAND_SLOTS * NUM_TILES].reshape(
        -1, NUM_HAND_SLOTS, NUM_TILES
    )
    special = joint_log_probs[:, NUM_HAND_SLOTS * NUM_TILES :]
    return torch.cat([placement.logsumexp(dim=-1), special], dim=-1)


def _binary_ranking_metrics(
    scores: np.ndarray, labels: np.ndarray
) -> dict[str, float]:
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.bool_)
    if scores.shape != labels.shape or scores.ndim != 1:
        raise ValueError("binary ranking inputs must be aligned vectors")
    positives = int(labels.sum())
    negatives = int((~labels).sum())
    if positives == 0 or negatives == 0:
        return {"roc_auc": 0.0, "average_precision": 0.0}
    order = np.argsort(scores, kind="stable")
    sorted_scores = scores[order]
    ranks = np.empty(scores.size, dtype=np.float64)
    start = 0
    while start < sorted_scores.size:
        stop = start + 1
        while stop < sorted_scores.size and sorted_scores[stop] == sorted_scores[start]:
            stop += 1
        ranks[order[start:stop]] = (start + 1 + stop) / 2.0
        start = stop
    rank_sum = float(ranks[labels].sum())
    roc_auc = (
        rank_sum - positives * (positives + 1) / 2.0
    ) / (positives * negatives)
    descending = np.argsort(-scores, kind="stable")
    sorted_labels = labels[descending]
    cumulative = np.cumsum(sorted_labels, dtype=np.int64)
    positive_positions = np.flatnonzero(sorted_labels)
    average_precision = float(
        np.mean(cumulative[positive_positions] / (positive_positions + 1))
    )
    return {"roc_auc": float(roc_auc), "average_precision": average_precision}


def _checkpoint_metrics(
    checkpoint_path: Path,
    *,
    arrays: dict[str, np.ndarray],
    device: torch.device,
    decks_path: Path,
    diagnostics: dict[str, np.ndarray] | None = None,
) -> tuple[dict[str, Any], np.ndarray]:
    loaded = load_policy_checkpoint(
        checkpoint_path, device=device, decks_path=decks_path
    )
    episode_ids = arrays["episode_ids"]
    expert_actions = arrays["expert_actions"]
    supervision_valid = np.asarray(
        arrays.get(
            "expert_action_supervision_valid",
            np.ones_like(expert_actions, dtype=np.bool_),
        ),
        dtype=np.bool_,
    )
    if supervision_valid.shape != expert_actions.shape:
        raise ValueError("expert-action supervision validity shape mismatch")
    if not np.any(supervision_valid):
        raise ValueError("recurrent corpus contains no supervised actions")
    chosen_actions = np.empty_like(expert_actions)
    marginal_types = np.empty_like(expert_actions)
    conditional_slots = np.empty_like(expert_actions)
    play_probabilities = np.empty(expert_actions.shape, dtype=np.float64)
    action_type_nll_rows = np.empty(expert_actions.shape, dtype=np.float64)
    negative_log_likelihood = 0.0
    action_type_negative_log_likelihood = 0.0
    conditional_location_negative_log_likelihood = 0.0
    placement_samples = 0
    action_type_correct = 0
    correct_slot_placements = 0
    within_one_tile = 0
    within_two_tiles = 0

    with torch.no_grad():
        for episode_id in np.unique(episode_ids):
            indices = np.flatnonzero(episode_ids == episode_id)
            if indices.size == 0 or np.any(np.diff(indices) != 1):
                raise ValueError("corpus episode samples must be contiguous")
            inputs = _sequence_batch_inputs(arrays, indices[None, :], device)
            output = loaded.model(inputs)
            logits = output.joint_logits[0]
            masks = inputs.action_mask[0]
            targets = torch.as_tensor(
                expert_actions[indices], dtype=torch.long, device=device
            )
            selected = torch.as_tensor(
                supervision_valid[indices], dtype=torch.bool, device=device
            )
            log_probs = torch.log_softmax(
                logits.masked_fill(~masks, -torch.inf), dim=-1
            )
            target_joint_log_probs = log_probs.gather(
                1, targets[:, None]
            ).squeeze(1)
            negative_log_likelihood -= float(
                target_joint_log_probs[selected].sum().item()
            )
            action_type_log_probs = _action_type_log_probs(log_probs)
            marginal_types[indices] = action_type_log_probs.argmax(dim=-1).cpu().numpy()
            conditional_slots[indices] = (
                action_type_log_probs[:, :NUM_HAND_SLOTS].argmax(dim=-1).cpu().numpy()
            )
            if output.play_hazard_logits is None:
                scored_play_probability = (
                    action_type_log_probs[:, :NUM_HAND_SLOTS]
                    .logsumexp(dim=-1)
                    .exp()
                )
            else:
                scored_play_probability = torch.sigmoid(
                    output.play_hazard_logits[0]
                    - math.log(loaded.model.config.play_hazard_positive_weight)
                )
            play_probabilities[indices] = (
                scored_play_probability.cpu().numpy()
            )
            target_types = torch.where(
                targets < NUM_HAND_SLOTS * NUM_TILES,
                targets // NUM_TILES,
                NUM_HAND_SLOTS + (targets == NUM_HAND_SLOTS * NUM_TILES + 1).long(),
            )
            target_type_log_probs = action_type_log_probs.gather(
                1, target_types[:, None]
            ).squeeze(1)
            action_type_nll_rows[indices] = (
                -target_type_log_probs.detach().cpu().numpy()
            )
            action_type_negative_log_likelihood -= float(
                target_type_log_probs[selected].sum().item()
            )
            target_placements = targets < NUM_HAND_SLOTS * NUM_TILES
            supervised_placements = target_placements & selected
            conditional_location_negative_log_likelihood -= float(
                (
                    target_joint_log_probs[supervised_placements]
                    - target_type_log_probs[supervised_placements]
                )
                .sum()
                .item()
            )
            placement_samples += int(supervised_placements.sum().item())
            # Match live deterministic inference exactly. A flat joint argmax
            # is not equivalent: every placement type's probability is split
            # over its legal tiles, which can make no-op win even when a hand
            # slot has the highest action-type logit.
            force_play = None
            if loaded.model.config.play_hazard_enabled:
                force_play, _ = loaded.model._play_hazard_force_gate(
                    output,
                    inputs.action_mask,
                    torch.zeros((1,), dtype=logits.dtype, device=device),
                )
            chosen = loaded.model._deterministic_actions(
                output,
                inputs.action_mask,
                force_play=force_play,
            )[0]
            chosen_numpy = chosen.cpu().numpy()
            chosen_actions[indices] = chosen_numpy

            expert_types = np.where(
                expert_actions[indices] < NUM_HAND_SLOTS * NUM_TILES,
                expert_actions[indices] // NUM_TILES,
                NUM_HAND_SLOTS
                + (expert_actions[indices] == NUM_HAND_SLOTS * NUM_TILES + 1),
            )
            chosen_types = np.where(
                chosen_numpy < NUM_HAND_SLOTS * NUM_TILES,
                chosen_numpy // NUM_TILES,
                NUM_HAND_SLOTS + (chosen_numpy == NUM_HAND_SLOTS * NUM_TILES + 1),
            )
            selected_numpy = supervision_valid[indices]
            action_type_correct += int(
                np.sum(expert_types[selected_numpy] == chosen_types[selected_numpy])
            )

            placement = (
                selected_numpy
                & (expert_actions[indices] < NUM_HAND_SLOTS * NUM_TILES)
                & (chosen_numpy < NUM_HAND_SLOTS * NUM_TILES)
                & (expert_types == chosen_types)
            )
            if np.any(placement):
                expert_tiles = expert_actions[indices][placement] % NUM_TILES
                chosen_tiles = chosen_numpy[placement] % NUM_TILES
                dx = np.abs(expert_tiles % BOARD_WIDTH - chosen_tiles % BOARD_WIDTH)
                dy = np.abs(expert_tiles // BOARD_WIDTH - chosen_tiles // BOARD_WIDTH)
                distance = np.sqrt(dx * dx + dy * dy)
                correct_slot_placements += int(distance.size)
                within_one_tile += int(np.sum(distance <= 1.0))
                within_two_tiles += int(np.sum(distance <= 2.0))

    expert_actions_scored = expert_actions[supervision_valid]
    chosen_actions_scored = chosen_actions[supervision_valid]
    marginal_types_scored = marginal_types[supervision_valid]
    conditional_slots_scored = conditional_slots[supervision_valid]
    play_probabilities_scored = play_probabilities[supervision_valid]
    samples = int(expert_actions_scored.size)
    noop_action = NUM_HAND_SLOTS * NUM_TILES
    expert_types = _action_types(expert_actions_scored)
    chosen_types = _action_types(chosen_actions_scored)
    expert_play = expert_actions_scored < noop_action
    chosen_play = chosen_actions_scored < noop_action
    expert_noop = expert_actions_scored == noop_action
    chosen_noop = chosen_actions_scored == noop_action
    play_count = int(expert_play.sum())
    noop_count = int(expert_noop.sum())
    predicted_play_count = int(chosen_play.sum())
    true_positive_plays = int(np.sum(expert_play & chosen_play))
    play_precision = (
        true_positive_plays / predicted_play_count if predicted_play_count else 0.0
    )
    play_recall = true_positive_plays / play_count if play_count else 0.0
    play_f1 = (
        2.0 * play_precision * play_recall / (play_precision + play_recall)
        if play_precision + play_recall > 0.0
        else 0.0
    )
    binary_correct = (expert_play & chosen_play) | (expert_noop & chosen_noop)
    play_targets = expert_play.astype(np.float64)
    play_brier = float(
        np.mean((play_probabilities_scored - play_targets) ** 2)
    )
    play_ranking = _binary_ranking_metrics(
        play_probabilities_scored, expert_play
    )
    play_ece = 0.0
    for lower in np.linspace(0.0, 0.9, 10):
        upper = lower + 0.1
        selected = (play_probabilities_scored >= lower) & (
            play_probabilities_scored <= upper
            if upper >= 1.0
            else play_probabilities_scored < upper
        )
        if np.any(selected):
            play_ece += float(np.mean(selected)) * abs(
                float(np.mean(play_probabilities_scored[selected]))
                - float(np.mean(play_targets[selected]))
            )
    if diagnostics is not None:
        diagnostics.update(
            {
                "action_type_nll": action_type_nll_rows,
                "marginal_action_types": marginal_types.copy(),
                "play_probabilities": play_probabilities.copy(),
            }
        )
    return (
        {
            "checkpoint": str(checkpoint_path),
            "checkpoint_sha256": file_sha256(checkpoint_path),
            "checkpoint_update": int(loaded.checkpoint.get("update", 0)),
            "samples": samples,
            "recurrent_context_samples": int(expert_actions.size),
            "episodes": int(np.unique(episode_ids).size),
            "joint_nll": negative_log_likelihood / samples,
            "action_type_nll": action_type_negative_log_likelihood / samples,
            "conditional_location_nll": (
                conditional_location_negative_log_likelihood / placement_samples
                if placement_samples
                else 0.0
            ),
            "placement_samples": placement_samples,
            "exact_accuracy": float(
                np.mean(chosen_actions_scored == expert_actions_scored)
            ),
            "action_type_accuracy": action_type_correct / samples,
            "marginal_action_type_accuracy": float(
                np.mean(marginal_types_scored == expert_types)
            ),
            "play_samples": play_count,
            "noop_samples": noop_count,
            "play_precision": play_precision,
            "play_recall": play_recall,
            "play_f1": play_f1,
            "noop_recall": (
                float(np.mean(chosen_noop[expert_noop])) if noop_count else 0.0
            ),
            "play_noop_accuracy": float(np.mean(binary_correct)),
            "predicted_play_rate": float(np.mean(chosen_play)),
            "marginal_predicted_play_rate": float(
                np.mean(marginal_types_scored < NUM_HAND_SLOTS)
            ),
            "expert_play_rate": float(np.mean(expert_play)),
            "play_probability_mean": float(np.mean(play_probabilities_scored)),
            "play_brier": play_brier,
            "play_roc_auc": play_ranking["roc_auc"],
            "play_average_precision": play_ranking["average_precision"],
            "play_ece_10_bin": play_ece,
            "played_card_slot_accuracy": (
                float(np.mean(chosen_types[expert_play] == expert_types[expert_play]))
                if play_count
                else 0.0
            ),
            "conditional_card_slot_accuracy": _conditional_card_slot_accuracy(
                conditional_slots_scored,
                expert_actions_scored,
            ),
            "correct_slot_placements": correct_slot_placements,
            "within_one_tile_accuracy": (
                within_one_tile / correct_slot_placements
                if correct_slot_placements
                else 0.0
            ),
            "within_two_tiles_accuracy": (
                within_two_tiles / correct_slot_placements
                if correct_slot_placements
                else 0.0
            ),
        },
        chosen_actions,
    )


def _action_types(actions: np.ndarray) -> NDArray[np.int64]:
    return np.asarray(
        np.where(
            actions < NUM_HAND_SLOTS * NUM_TILES,
            actions // NUM_TILES,
            NUM_HAND_SLOTS + (actions == NUM_HAND_SLOTS * NUM_TILES + 1),
        ),
        dtype=np.int64,
    )


def _conditional_card_slot_accuracy(
    conditional_slots: np.ndarray,
    expert_actions: np.ndarray,
) -> float:
    """Score card choice independently of the policy's play/wait threshold."""
    expert_types = _action_types(expert_actions)
    expert_play = expert_actions < NUM_HAND_SLOTS * NUM_TILES
    if not np.any(expert_play):
        return 0.0
    return float(np.mean(conditional_slots[expert_play] == expert_types[expert_play]))


def _placement_tolerance(
    actions: np.ndarray,
    expert_actions: np.ndarray,
    *,
    radius: float,
) -> NDArray[np.bool_]:
    expert_types = _action_types(expert_actions)
    chosen_types = _action_types(actions)
    expert_placement = expert_actions < NUM_HAND_SLOTS * NUM_TILES
    chosen_placement = actions < NUM_HAND_SLOTS * NUM_TILES
    same_slot = expert_types == chosen_types
    expert_tiles = expert_actions % NUM_TILES
    chosen_tiles = actions % NUM_TILES
    dx = np.abs(expert_tiles % BOARD_WIDTH - chosen_tiles % BOARD_WIDTH)
    dy = np.abs(expert_tiles // BOARD_WIDTH - chosen_tiles // BOARD_WIDTH)
    return np.asarray(
        expert_placement
        & chosen_placement
        & same_slot
        & (np.sqrt(dx * dx + dy * dy) <= radius),
        dtype=np.bool_,
    )


def _paired_metrics(
    reference: np.ndarray,
    chosen: np.ndarray,
    expert_actions: np.ndarray,
) -> dict[str, int]:
    result = {"action_changes_vs_first": int(np.sum(chosen != reference))}
    comparisons = {
        "exact": (reference == expert_actions, chosen == expert_actions),
        "action_type": (
            _action_types(reference) == _action_types(expert_actions),
            _action_types(chosen) == _action_types(expert_actions),
        ),
        "within_one_tile": (
            _placement_tolerance(reference, expert_actions, radius=1.0),
            _placement_tolerance(chosen, expert_actions, radius=1.0),
        ),
        "within_two_tiles": (
            _placement_tolerance(reference, expert_actions, radius=2.0),
            _placement_tolerance(chosen, expert_actions, radius=2.0),
        ),
    }
    for name, (before, after) in comparisons.items():
        result[f"{name}_improvements_vs_first"] = int(np.sum(~before & after))
        result[f"{name}_regressions_vs_first"] = int(np.sum(before & ~after))
    return result


def _temporal_play_metrics(
    chosen_actions: np.ndarray,
    expert_actions: np.ndarray,
    arrays: dict[str, np.ndarray],
    supervision_valid: np.ndarray,
    *,
    tolerance_frames: int,
    require_same_card: bool,
) -> dict[str, float | int]:
    if tolerance_frames < 0:
        raise ValueError("temporal tolerance must be non-negative")
    if "source_frames" in arrays:
        frames = np.asarray(arrays["source_frames"], dtype=np.int64)
    else:
        frames = np.arange(expert_actions.size, dtype=np.int64)
    replay_groups = np.asarray(
        arrays.get("source_replays", arrays["episode_ids"])
    ).astype(str)
    actor_groups = np.asarray(
        arrays.get("source_actor_ids", arrays["episode_ids"])
    ).astype(str)
    if not (
        frames.shape
        == replay_groups.shape
        == actor_groups.shape
        == expert_actions.shape
        == supervision_valid.shape
    ):
        raise ValueError("temporal metric provenance arrays are not aligned")
    no_op = NUM_HAND_SLOTS * NUM_TILES
    expert_play = supervision_valid & (expert_actions < no_op)
    predicted_play = supervision_valid & (chosen_actions < no_op)
    matched_expert: set[int] = set()
    matched_prediction: set[int] = set()
    candidates: list[tuple[int, int, int]] = []
    group_values = np.char.add(np.char.add(replay_groups, ":"), actor_groups)
    for group in np.unique(group_values):
        expert_rows = np.flatnonzero((group_values == group) & expert_play)
        predicted_rows = np.flatnonzero((group_values == group) & predicted_play)
        for predicted in predicted_rows.tolist():
            for expert in expert_rows.tolist():
                distance = abs(int(frames[predicted]) - int(frames[expert]))
                if distance > tolerance_frames:
                    continue
                if require_same_card and (
                    chosen_actions[predicted] // NUM_TILES
                    != expert_actions[expert] // NUM_TILES
                ):
                    continue
                candidates.append((distance, predicted, expert))
    for _, predicted, expert in sorted(candidates):
        if predicted in matched_prediction or expert in matched_expert:
            continue
        matched_prediction.add(predicted)
        matched_expert.add(expert)
    predicted_count = int(predicted_play.sum())
    expert_count = int(expert_play.sum())
    matched = len(matched_expert)
    precision = matched / predicted_count if predicted_count else 0.0
    recall = matched / expert_count if expert_count else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall > 0.0
        else 0.0
    )
    return {
        "matched": matched,
        "predicted": predicted_count,
        "expert": expert_count,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def main() -> None:
    args = parse_args()
    device = resolve_torch_device(args.device)
    corpus_path = resolve_path(args.corpus, must_exist=True)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    metadata, arrays = load_corpus(corpus_path)
    public_sidecar = (
        resolve_path(args.public_observation_sidecar, must_exist=True)
        if args.public_observation_sidecar
        else None
    )
    if public_sidecar is not None:
        arrays = load_public_observation_sidecar(
            public_sidecar,
            base_arrays=arrays,
        )
    evaluated_episode_ids = _select_episode_ids(
        arrays["episode_ids"],
        max_episodes=args.max_episodes,
        episode_seed=args.episode_seed,
        exclude_max_episodes=args.exclude_max_episodes,
        exclude_episode_seed=args.exclude_episode_seed,
        explicit_episode_ids=args.episode_id,
    )
    selected = np.isin(arrays["episode_ids"], evaluated_episode_ids)
    arrays = {
        name: values[selected]
        if values.ndim > 0 and values.shape[0] == selected.size
        else values
        for name, values in arrays.items()
    }
    results: list[dict[str, Any]] = []
    actions: list[np.ndarray] = []
    for value in args.checkpoint:
        metrics, chosen = _checkpoint_metrics(
            resolve_path(value, must_exist=True),
            arrays=arrays,
            device=device,
            decks_path=decks_path,
        )
        results.append(metrics)
        actions.append(chosen)
        supervision_valid = np.asarray(
            arrays.get(
                "expert_action_supervision_valid",
                np.ones_like(arrays["expert_actions"], dtype=np.bool_),
            ),
            dtype=np.bool_,
        )
        for seconds, tolerance_frames in ((1, 10), (2, 20)):
            metrics[f"play_within_{seconds}s"] = _temporal_play_metrics(
                chosen,
                arrays["expert_actions"],
                arrays,
                supervision_valid,
                tolerance_frames=tolerance_frames,
                require_same_card=False,
            )
            metrics[f"same_card_play_within_{seconds}s"] = (
                _temporal_play_metrics(
                    chosen,
                    arrays["expert_actions"],
                    arrays,
                    supervision_valid,
                    tolerance_frames=tolerance_frames,
                    require_same_card=True,
                )
            )
    if actions:
        supervision_valid = np.asarray(
            arrays.get(
                "expert_action_supervision_valid",
                np.ones_like(arrays["expert_actions"], dtype=np.bool_),
            ),
            dtype=np.bool_,
        )
        reference = actions[0]
        for metrics, chosen in zip(results, actions, strict=True):
            metrics.update(
                _paired_metrics(
                    reference[supervision_valid],
                    chosen[supervision_valid],
                    arrays["expert_actions"][supervision_valid],
                )
            )
    payload = {
        "schema_version": 1,
        "corpus": str(corpus_path),
        "corpus_sha256": file_sha256(corpus_path),
        "corpus_samples": metadata.samples,
        "evaluated_samples": int(
            np.asarray(
                arrays.get(
                    "expert_action_supervision_valid",
                    np.ones_like(arrays["expert_actions"], dtype=np.bool_),
                ),
                dtype=np.bool_,
            ).sum()
        ),
        "recurrent_context_samples": int(arrays["expert_actions"].size),
        "evaluated_episodes": int(evaluated_episode_ids.size),
        "episode_seed": args.episode_seed,
        "exclude_max_episodes": args.exclude_max_episodes,
        "exclude_episode_seed": args.exclude_episode_seed,
        "explicit_episode_ids": (
            [int(value) for value in evaluated_episode_ids]
            if args.episode_id
            else None
        ),
        "public_observation_sidecar": (
            str(public_sidecar) if public_sidecar is not None else None
        ),
        "public_observation_sidecar_sha256": (
            file_sha256(public_sidecar) if public_sidecar is not None else None
        ),
        "device": str(device),
        "results": results,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        output_path = resolve_path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
