from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.imitation import load_corpus, load_public_observation_sidecar
from clasher.rl.oracle_corpus import file_sha256
from clasher.rl.train_recurrent import resolve_torch_device
from scripts.evaluate_recurrent_corpus import _checkpoint_metrics


@dataclass(frozen=True)
class TimingWeights:
    weights: NDArray[np.float64]
    evaluable: NDArray[np.bool_]
    episode_rows: list[dict[str, Any]]
    summary: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit TV Royale play/no-op timing with replay-duration importance "
            "weights instead of the intentionally case-controlled corpus ratio"
        )
    )
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--public-observation-sidecar", required=True)
    parser.add_argument("--game-manifest-root", required=True)
    parser.add_argument("--checkpoint", action="append", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument(
        "--device", choices=["auto", "cpu", "mps", "cuda"], default="auto"
    )
    parser.add_argument("--source-frame-hz", type=float, default=10.0)
    parser.add_argument("--policy-decision-hz", type=float, default=4.0)
    parser.add_argument("--json-out", default=None)
    return parser.parse_args()


def load_replay_frame_counts(root: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for path in sorted(root.glob("*/*/manifest.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        replay = str(payload.get("replay", path.parent.name))
        frames = int(payload["frames"])
        if frames <= 0:
            raise ValueError(f"non-positive frame count in {path}")
        if replay in result and result[replay] != frames:
            raise ValueError(f"conflicting frame counts for replay {replay}")
        result[replay] = frames
    if not result:
        raise ValueError(f"no game manifests found below {root}")
    return result


def build_duration_weights(
    *,
    expert_actions: NDArray[np.integer[Any]],
    episode_ids: NDArray[np.integer[Any]],
    source_replays: NDArray[np.str_],
    replay_frame_counts: dict[str, int],
    source_frame_hz: float,
    policy_decision_hz: float,
) -> TimingWeights:
    if source_frame_hz <= 0.0 or policy_decision_hz <= 0.0:
        raise ValueError("frame and decision rates must be positive")
    if not (
        expert_actions.shape == episode_ids.shape == source_replays.shape
        and expert_actions.ndim == 1
    ):
        raise ValueError("timing arrays must be aligned one-dimensional rows")

    noop_action = NUM_HAND_SLOTS * NUM_TILES
    unsupported = (expert_actions > noop_action) | (expert_actions < 0)
    if np.any(unsupported):
        raise ValueError(
            "TV Royale timing audit supports placement and no-op labels only"
        )
    expert_play = expert_actions < noop_action
    weights = np.zeros(expert_actions.shape, dtype=np.float64)
    evaluable = np.zeros(expert_actions.shape, dtype=np.bool_)
    episode_rows: list[dict[str, Any]] = []
    total_opportunities = 0
    total_plays = 0
    total_retained_noops = 0
    evaluable_opportunities = 0
    evaluable_plays = 0
    noop_weights: list[float] = []

    for episode_id in np.unique(episode_ids):
        indices = np.flatnonzero(episode_ids == episode_id)
        replays = np.unique(source_replays[indices])
        if replays.size != 1:
            raise ValueError(f"episode {episode_id} does not map to exactly one replay")
        replay = str(replays[0])
        if replay not in replay_frame_counts:
            raise ValueError(f"no manifest frame count for replay {replay}")
        retained_plays = int(np.count_nonzero(expert_play[indices]))
        retained_noops = int(indices.size - retained_plays)
        opportunities = max(
            int(indices.size),
            math.ceil(
                replay_frame_counts[replay]
                * policy_decision_hz
                / source_frame_hz
            ),
        )
        noop_opportunities = opportunities - retained_plays
        noop_weight: float | None = None
        is_evaluable = retained_noops > 0
        if is_evaluable:
            noop_weight = noop_opportunities / retained_noops
            weights[indices[expert_play[indices]]] = 1.0
            weights[indices[~expert_play[indices]]] = noop_weight
            evaluable[indices] = True
            evaluable_opportunities += opportunities
            evaluable_plays += retained_plays
            noop_weights.append(noop_weight)

        total_opportunities += opportunities
        total_plays += retained_plays
        total_retained_noops += retained_noops
        episode_rows.append(
            {
                "episode_id": int(episode_id),
                "replay": replay,
                "source_frames": replay_frame_counts[replay],
                "estimated_decision_opportunities": opportunities,
                "retained_plays": retained_plays,
                "retained_noops": retained_noops,
                "noop_importance_weight": noop_weight,
                "evaluable": is_evaluable,
            }
        )

    summary = {
        "episodes": len(episode_rows),
        "evaluable_episodes": int(sum(row["evaluable"] for row in episode_rows)),
        "episodes_without_retained_noop": int(
            sum(not row["evaluable"] for row in episode_rows)
        ),
        "retained_rows": int(expert_actions.size),
        "retained_plays": total_plays,
        "retained_noops": total_retained_noops,
        "estimated_decision_opportunities": total_opportunities,
        "estimated_noop_opportunities": total_opportunities - total_plays,
        "duration_estimated_human_play_rate": total_plays / total_opportunities,
        "evaluable_duration_estimated_human_play_rate": (
            evaluable_plays / evaluable_opportunities
            if evaluable_opportunities
            else 0.0
        ),
        "noop_importance_weight_mean": (
            float(np.mean(noop_weights)) if noop_weights else 0.0
        ),
        "noop_importance_weight_median": (
            float(np.median(noop_weights)) if noop_weights else 0.0
        ),
        "noop_importance_weight_min": min(noop_weights, default=0.0),
        "noop_importance_weight_max": max(noop_weights, default=0.0),
    }
    return TimingWeights(
        weights=weights,
        evaluable=evaluable,
        episode_rows=episode_rows,
        summary=summary,
    )


def _weighted_mean(values: NDArray[np.generic], weights: NDArray[np.float64]) -> float:
    return float(np.average(values.astype(np.float64, copy=False), weights=weights))


def weighted_checkpoint_metrics(
    *,
    chosen_actions: NDArray[np.integer[Any]],
    play_probabilities: NDArray[np.floating[Any]],
    expert_actions: NDArray[np.integer[Any]],
    timing: TimingWeights,
) -> dict[str, float | int]:
    selected = timing.evaluable
    weights = timing.weights[selected]
    if not np.any(selected) or float(weights.sum()) <= 0.0:
        raise ValueError("no duration-weighted timing rows are evaluable")
    noop_action = NUM_HAND_SLOTS * NUM_TILES
    target_play = expert_actions[selected] < noop_action
    chosen_play = chosen_actions[selected] < noop_action
    probabilities = np.asarray(play_probabilities[selected], dtype=np.float64)
    probabilities = np.clip(probabilities, 1e-9, 1.0 - 1e-9)
    binary_nll = -(
        target_play * np.log(probabilities)
        + (~target_play) * np.log1p(-probabilities)
    )
    return {
        "weighted_rows": int(selected.sum()),
        "weighted_effective_decisions": float(weights.sum()),
        "weighted_target_play_rate": _weighted_mean(target_play, weights),
        "weighted_predicted_play_rate": _weighted_mean(chosen_play, weights),
        "weighted_mean_play_probability": _weighted_mean(probabilities, weights),
        "weighted_play_noop_accuracy": _weighted_mean(
            target_play == chosen_play, weights
        ),
        "weighted_play_recall": _weighted_mean(
            chosen_play[target_play], weights[target_play]
        ),
        "weighted_noop_recall": _weighted_mean(
            ~chosen_play[~target_play], weights[~target_play]
        ),
        "weighted_binary_nll": _weighted_mean(binary_nll, weights),
        "weighted_brier": _weighted_mean(
            (probabilities - target_play.astype(np.float64)) ** 2,
            weights,
        ),
    }


def main() -> None:
    args = parse_args()
    corpus_path = resolve_path(args.corpus, must_exist=True)
    sidecar_path = resolve_path(args.public_observation_sidecar, must_exist=True)
    manifest_root = resolve_path(args.game_manifest_root, must_exist=True)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    _, base_arrays = load_corpus(corpus_path)
    arrays = load_public_observation_sidecar(sidecar_path, base_arrays=base_arrays)
    with np.load(sidecar_path, allow_pickle=False) as sidecar:
        source_replays = np.asarray(sidecar["source_replays"]).copy()
    timing = build_duration_weights(
        expert_actions=arrays["expert_actions"],
        episode_ids=arrays["episode_ids"],
        source_replays=source_replays,
        replay_frame_counts=load_replay_frame_counts(manifest_root),
        source_frame_hz=args.source_frame_hz,
        policy_decision_hz=args.policy_decision_hz,
    )
    device = resolve_torch_device(args.device)
    checkpoint_results: list[dict[str, Any]] = []
    for value in args.checkpoint:
        checkpoint_path = resolve_path(value, must_exist=True)
        diagnostics: dict[str, np.ndarray] = {}
        unweighted, chosen = _checkpoint_metrics(
            checkpoint_path,
            arrays=arrays,
            device=device,
            decks_path=decks_path,
            diagnostics=diagnostics,
        )
        checkpoint_results.append(
            {
                "checkpoint": str(checkpoint_path),
                "checkpoint_sha256": file_sha256(checkpoint_path),
                "unweighted_case_controlled": unweighted,
                "duration_weighted": weighted_checkpoint_metrics(
                    chosen_actions=chosen,
                    play_probabilities=diagnostics["play_probabilities"],
                    expert_actions=arrays["expert_actions"],
                    timing=timing,
                ),
            }
        )
    payload = {
        "schema": "tv-royale-duration-weighted-action-timing-v1",
        "corpus": str(corpus_path),
        "corpus_sha256": file_sha256(corpus_path),
        "public_observation_sidecar": str(sidecar_path),
        "public_observation_sidecar_sha256": file_sha256(sidecar_path),
        "game_manifest_root": str(manifest_root),
        "source_frame_hz": args.source_frame_hz,
        "policy_decision_hz": args.policy_decision_hz,
        "device": str(device),
        "timing": timing.summary,
        "episodes": timing.episode_rows,
        "checkpoints": checkpoint_results,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        output_path = resolve_path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    torch.set_grad_enabled(False)
    main()
