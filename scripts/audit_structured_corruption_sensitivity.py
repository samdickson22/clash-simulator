from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from typing import Any

import numpy as np
import torch

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.imitation import (
    _sequence_batch_inputs,
    load_corpus,
    load_public_observation_sidecar,
)
from clasher.rl.model import ClasherPolicy
from clasher.rl.oracle_corpus import file_sha256

STATIC_ENTITY_CHANNELS = (23, 24, 25, 26, 30)
MOTION_CHANNELS = (27, 28)
TOWER_HP_CHANNELS = tuple(range(8, 14))
VARIANTS = (
    "motion_zero",
    "static_zero",
    "position_jitter",
    "hp_noise",
    "own_elixir_noise",
    "confidence_binary",
    "next_exact_from_base",
    "combined_sensor_noise",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure frozen structured-policy sensitivity to live-like corruptions"
    )
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--public-observation-sidecar", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--max-episodes", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1064201)
    parser.add_argument("--position-noise-std", type=float, default=0.01)
    parser.add_argument("--hp-noise-std", type=float, default=0.05)
    parser.add_argument("--elixir-noise-std", type=float, default=0.05)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--json-out", required=True)
    return parser.parse_args()


def _copied(arrays: dict[str, np.ndarray], *names: str) -> dict[str, np.ndarray]:
    result = dict(arrays)
    for name in names:
        result[name] = arrays[name].copy()
    return result


def _zero_entity_channels(
    arrays: dict[str, np.ndarray], channels: tuple[int, ...]
) -> dict[str, np.ndarray]:
    result = _copied(arrays, "entity_features", "entity_feature_confidence")
    result["entity_features"][..., channels] = 0.0
    result["entity_feature_confidence"][..., channels] = 0.0
    return result


def apply_corruption(
    arrays: dict[str, np.ndarray],
    *,
    exact_arrays: dict[str, np.ndarray],
    variant: str,
    seed: int,
    position_noise_std: float,
    hp_noise_std: float,
    elixir_noise_std: float,
) -> dict[str, np.ndarray]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown corruption variant {variant!r}")
    rng = np.random.default_rng(seed)

    if variant == "motion_zero":
        return _zero_entity_channels(arrays, MOTION_CHANNELS)
    if variant == "static_zero":
        return _zero_entity_channels(arrays, STATIC_ENTITY_CHANNELS)
    if variant == "next_exact_from_base":
        result = _copied(arrays, "hand_ids", "hand_id_confidence")
        result["hand_ids"][..., NUM_HAND_SLOTS] = exact_arrays["hand_ids"][
            ..., NUM_HAND_SLOTS
        ]
        result["hand_id_confidence"][..., NUM_HAND_SLOTS] = (
            result["hand_ids"][..., NUM_HAND_SLOTS] != 0
        ).astype(np.float32)
        return result
    if variant == "confidence_binary":
        result = _copied(
            arrays,
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_id_confidence",
            "global_feature_confidence",
        )
        for name in (
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_id_confidence",
            "global_feature_confidence",
        ):
            result[name] = (result[name] > 0.0).astype(np.float32)
        return result

    result = _copied(
        arrays,
        "entity_features",
        "global_features",
    )
    if variant in {"position_jitter", "combined_sensor_noise"}:
        confidence = arrays["entity_feature_confidence"][..., :2] > 0.0
        noise = rng.normal(
            0.0,
            position_noise_std,
            size=result["entity_features"][..., :2].shape,
        )
        positions = result["entity_features"][..., :2]
        positions[confidence] = np.clip(
            positions[confidence] + noise[confidence], 0.0, 1.0
        )
    if variant in {"hp_noise", "combined_sensor_noise"}:
        entity_confidence = arrays["entity_feature_confidence"][..., 9] > 0.0
        entity_noise = rng.normal(
            0.0,
            hp_noise_std,
            size=result["entity_features"][..., 9].shape,
        )
        entity_hp = result["entity_features"][..., 9]
        entity_hp[entity_confidence] = np.clip(
            entity_hp[entity_confidence] + entity_noise[entity_confidence],
            0.0,
            1.0,
        )
        tower_confidence = arrays["global_feature_confidence"][
            ..., TOWER_HP_CHANNELS
        ] > 0.0
        tower_noise = rng.normal(
            0.0,
            hp_noise_std,
            size=result["global_features"][..., TOWER_HP_CHANNELS].shape,
        )
        tower_hp = result["global_features"][..., TOWER_HP_CHANNELS]
        tower_hp[tower_confidence] = np.clip(
            tower_hp[tower_confidence] + tower_noise[tower_confidence],
            0.0,
            1.0,
        )
    if variant in {"own_elixir_noise", "combined_sensor_noise"}:
        confidence = arrays["global_feature_confidence"][..., 5] > 0.0
        noise = rng.normal(
            0.0,
            elixir_noise_std,
            size=result["global_features"][..., 5].shape,
        )
        elixir = result["global_features"][..., 5]
        elixir[confidence] = np.clip(
            elixir[confidence] + noise[confidence], 0.0, 1.0
        )
    return result


def _action_type_log_probabilities(joint: torch.Tensor) -> torch.Tensor:
    placement = joint[..., : NUM_HAND_SLOTS * NUM_TILES].reshape(
        *joint.shape[:-1], NUM_HAND_SLOTS, NUM_TILES
    )
    special = joint[..., NUM_HAND_SLOTS * NUM_TILES :]
    return torch.cat((placement.logsumexp(dim=-1), special), dim=-1)


@torch.no_grad()
def _policy_trace(
    model: ClasherPolicy,
    arrays: dict[str, np.ndarray],
    *,
    episode_ids: np.ndarray,
    device: torch.device,
) -> dict[str, np.ndarray]:
    joint_rows: list[np.ndarray] = []
    type_rows: list[np.ndarray] = []
    action_rows: list[np.ndarray] = []
    value_rows: list[np.ndarray] = []
    for episode_id in episode_ids.tolist():
        indices = np.flatnonzero(arrays["episode_ids"] == episode_id)
        inputs = _sequence_batch_inputs(
            arrays,
            indices[None, :],
            device,
            trim_entity_padding=True,
        )
        output = model(inputs)
        joint = torch.log_softmax(output.joint_logits[0], dim=-1)
        types = _action_type_log_probabilities(joint)
        actions = model._deterministic_actions(output, inputs.action_mask)[0]
        joint_rows.append(joint.cpu().numpy())
        type_rows.append(types.cpu().numpy())
        action_rows.append(actions.cpu().numpy())
        value_rows.append(output.values[0].cpu().numpy())
    return {
        "joint_log_probabilities": np.concatenate(joint_rows),
        "type_log_probabilities": np.concatenate(type_rows),
        "actions": np.concatenate(action_rows),
        "values": np.concatenate(value_rows),
    }


def _kl(reference_logp: np.ndarray, candidate_logp: np.ndarray) -> np.ndarray:
    probabilities = np.exp(reference_logp)
    finite = probabilities > 0.0
    terms = np.zeros_like(probabilities, dtype=np.float64)
    terms[finite] = probabilities[finite] * (
        reference_logp[finite] - candidate_logp[finite]
    )
    return np.asarray(terms.sum(axis=-1), dtype=np.float64)


def _comparison(
    reference: dict[str, np.ndarray], candidate: dict[str, np.ndarray]
) -> dict[str, float | int]:
    reference_actions = reference["actions"]
    candidate_actions = candidate["actions"]
    noop = NUM_HAND_SLOTS * NUM_TILES
    return {
        "rows": int(reference_actions.size),
        "joint_kl_mean": float(
            _kl(
                reference["joint_log_probabilities"],
                candidate["joint_log_probabilities"],
            ).mean()
        ),
        "action_type_kl_mean": float(
            _kl(
                reference["type_log_probabilities"],
                candidate["type_log_probabilities"],
            ).mean()
        ),
        "top_action_flips": int(np.sum(reference_actions != candidate_actions)),
        "top_action_flip_rate": float(np.mean(reference_actions != candidate_actions)),
        "reference_noop_rate": float(np.mean(reference_actions == noop)),
        "candidate_noop_rate": float(np.mean(candidate_actions == noop)),
        "value_mean_absolute_drift": float(
            np.mean(np.abs(reference["values"] - candidate["values"]))
        ),
        "value_max_absolute_drift": float(
            np.max(np.abs(reference["values"] - candidate["values"]))
        ),
    }


def main() -> None:
    args = parse_args()
    if args.max_episodes <= 0:
        raise ValueError("max episodes must be positive")
    for name, value in (
        ("position noise", args.position_noise_std),
        ("HP noise", args.hp_noise_std),
        ("elixir noise", args.elixir_noise_std),
    ):
        if value < 0.0:
            raise ValueError(f"{name} must be non-negative")

    checkpoint = resolve_path(args.checkpoint, must_exist=True)
    corpus = resolve_path(args.corpus, must_exist=True)
    sidecar = resolve_path(args.public_observation_sidecar, must_exist=True)
    decks = resolve_decks_path(args.decks_path, must_exist=True)
    device = torch.device(args.device)
    _, exact_arrays = load_corpus(corpus)
    arrays = load_public_observation_sidecar(sidecar, base_arrays=exact_arrays)
    selected_episodes = np.unique(arrays["episode_ids"])[: args.max_episodes]
    loaded = load_policy_checkpoint(checkpoint, device=device, decks_path=decks)
    loaded.model.eval()
    reference = _policy_trace(
        loaded.model,
        arrays,
        episode_ids=selected_episodes,
        device=device,
    )

    comparisons: dict[str, dict[str, float | int]] = {}
    for index, variant in enumerate(VARIANTS):
        candidate_arrays = apply_corruption(
            arrays,
            exact_arrays=exact_arrays,
            variant=variant,
            seed=args.seed + index,
            position_noise_std=args.position_noise_std,
            hp_noise_std=args.hp_noise_std,
            elixir_noise_std=args.elixir_noise_std,
        )
        candidate = _policy_trace(
            loaded.model,
            candidate_arrays,
            episode_ids=selected_episodes,
            device=device,
        )
        comparisons[variant] = _comparison(reference, candidate)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": file_sha256(checkpoint),
        "corpus": str(corpus),
        "corpus_sha256": file_sha256(corpus),
        "public_observation_sidecar": str(sidecar),
        "public_observation_sidecar_sha256": file_sha256(sidecar),
        "device": str(device),
        "seed": args.seed,
        "episodes": selected_episodes.tolist(),
        "rows": int(reference["actions"].size),
        "noise": {
            "position_std_normalized": args.position_noise_std,
            "hp_std_fraction": args.hp_noise_std,
            "elixir_std_normalized": args.elixir_noise_std,
        },
        "comparisons": comparisons,
        "interpretation": (
            "Synthetic sensitivity screen only; noise values are not empirical live "
            "calibration and cannot promote an observation design."
        ),
    }
    output = resolve_path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
