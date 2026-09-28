from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Any

import numpy as np

from clasher.paths import resolve_path
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from clasher.rl.public_action_mask import (
    PUBLIC_ACTION_MASK_CONTRACT_VERSION,
    PublicActionMaskBuilder,
    PublicActionMaskInput,
)
from clasher.rl.public_observation import (
    PUBLIC_OBSERVATION_SCHEMA_VERSION,
    REAL_PLAY_FEATURE_CONTRACT_VERSION,
    PublicObservationDegradationProfile,
    degrade_simulator_public_observation,
)
from clasher.rl.structured_obs import ActorObservation, StructuredObservationBuilder


def parse_args() -> argparse.Namespace:
    defaults = PublicObservationDegradationProfile()
    parser = argparse.ArgumentParser(
        description=(
            "Build a confidence-aware public-state v2 sidecar from an exact "
            "simulator imitation corpus"
        )
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--max-samples", type=int)
    for name, value in asdict(defaults).items():
        parser.add_argument(f"--{name.replace('_', '-')}", type=float, default=value)
    return parser.parse_args()


def _optional_rows(
    arrays: dict[str, np.ndarray],
    name: str,
    samples: int,
    *,
    dtype: np.dtype[Any],
) -> np.ndarray:
    value = arrays.get(name)
    if value is None:
        return np.zeros((samples, 0), dtype=dtype)
    if value.shape[0] < samples:
        raise ValueError(f"{name} has fewer rows than the requested sidecar")
    return value[:samples]


def build_public_sidecar(
    *,
    arrays: dict[str, np.ndarray],
    profile: PublicObservationDegradationProfile,
    seed: int,
    max_samples: int | None,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    required = (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "hand_ids",
        "global_features",
    )
    missing = [name for name in required if name not in arrays]
    if missing:
        raise ValueError(f"input corpus is missing arrays: {missing}")
    available = int(arrays["entity_ids"].shape[0])
    if max_samples is not None and max_samples <= 0:
        raise ValueError("max_samples must be positive")
    samples = available if max_samples is None else min(available, max_samples)
    for name in required:
        if arrays[name].shape[0] < samples:
            raise ValueError(f"{name} has fewer than {samples} rows")
    history_ids = _optional_rows(
        arrays, "opponent_history_ids", samples, dtype=np.dtype(np.int64)
    )
    history_ages = _optional_rows(
        arrays, "opponent_history_ages", samples, dtype=np.dtype(np.float32)
    )
    seen_ids = _optional_rows(
        arrays, "opponent_seen_card_ids", samples, dtype=np.dtype(np.int64)
    )
    if history_ages.shape != history_ids.shape:
        raise ValueError("opponent history ids/ages shapes differ")

    output_lists: dict[str, list[np.ndarray]] = {
        name: []
        for name in (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_ids",
            "hand_id_confidence",
            "global_features",
            "global_feature_confidence",
            "opponent_history_ids",
            "opponent_history_ages",
            "opponent_history_confidence",
            "opponent_seen_card_ids",
            "opponent_seen_card_confidence",
            "action_masks",
        )
    }
    rng = np.random.default_rng(seed)
    token_names: tuple[str, ...] | None = None
    metadata_json = arrays.get("metadata_json")
    if metadata_json is not None:
        metadata = json.loads(str(metadata_json.item()))
        raw_token_names = metadata.get("token_names")
        if raw_token_names is not None:
            token_names = tuple(str(name) for name in raw_token_names)
    mask_builder = PublicActionMaskBuilder(
        StructuredObservationBuilder(token_names=token_names)
    )
    expert_action_masked = np.zeros((samples,), dtype=np.bool_)
    for index in range(samples):
        actor = ActorObservation(
            entity_ids=arrays["entity_ids"][index],
            entity_features=arrays["entity_features"][index],
            entity_mask=arrays["entity_mask"][index],
            hand_ids=arrays["hand_ids"][index],
            global_features=arrays["global_features"][index],
            opponent_history_ids=history_ids[index],
            opponent_history_ages=history_ages[index],
            opponent_seen_card_ids=seen_ids[index],
        )
        public = degrade_simulator_public_observation(
            actor,
            profile=profile,
            rng=rng,
        )
        public_mask = mask_builder.build(
            PublicActionMaskInput.from_confidence_observation(public)
        )
        if "expert_actions" in arrays:
            expert_action = int(arrays["expert_actions"][index])
            if not public_mask[expert_action]:
                # This is label metadata, never a reason to mutate policy input.
                expert_action_masked[index] = True
        output_lists["action_masks"].append(public_mask)
        observation = public.observation
        for name in (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "hand_ids",
            "global_features",
            "opponent_history_ids",
            "opponent_history_ages",
            "opponent_seen_card_ids",
        ):
            output_lists[name].append(getattr(observation, name))
        for name in (
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_id_confidence",
            "global_feature_confidence",
            "opponent_history_confidence",
            "opponent_seen_card_confidence",
        ):
            output_lists[name].append(getattr(public, name))

    payload = {name: np.stack(values) for name, values in output_lists.items()}
    payload["expert_action_masked"] = expert_action_masked
    for name in (
        "entity_id_confidence",
        "entity_feature_confidence",
        "hand_id_confidence",
        "global_feature_confidence",
        "opponent_history_confidence",
        "opponent_seen_card_confidence",
    ):
        payload[name] = payload[name].astype(np.float16)
    for name in (
        "expert_actions",
        "episode_ids",
        "episode_starts",
        "source_frames",
    ):
        if name in arrays:
            payload[name] = arrays[name][:samples].copy()
    payload["schema_version"] = np.asarray(PUBLIC_OBSERVATION_SCHEMA_VERSION)
    payload["feature_contract_version"] = np.asarray(
        REAL_PLAY_FEATURE_CONTRACT_VERSION
    )
    payload["action_mask_contract_version"] = np.asarray(
        PUBLIC_ACTION_MASK_CONTRACT_VERSION
    )
    payload["profile_json"] = np.asarray(json.dumps(asdict(profile), sort_keys=True))

    visible = payload["entity_mask"].astype(np.bool_, copy=False)
    hp_observed = (payload["entity_feature_confidence"][..., 9] > 0) & visible
    motion_observed = (payload["entity_feature_confidence"][..., 27] > 0) & visible
    statistics = {
        "schema": "confidence-aware-public-observation-v2",
        "schema_version": PUBLIC_OBSERVATION_SCHEMA_VERSION,
        "feature_contract_version": REAL_PLAY_FEATURE_CONTRACT_VERSION,
        "action_mask_contract_version": PUBLIC_ACTION_MASK_CONTRACT_VERSION,
        "available_samples": available,
        "samples": samples,
        "visible_entities": int(visible.sum()),
        "entities_with_hp": int(hp_observed.sum()),
        "entity_hp_coverage": float(hp_observed.sum() / max(1, int(visible.sum()))),
        "entities_with_motion": int(motion_observed.sum()),
        "motion_coverage": float(
            motion_observed.sum() / max(1, int(visible.sum()))
        ),
        "profile": asdict(profile),
        "seed": seed,
        "expert_mask_recoveries": 0,
        "expert_actions_masked_by_public_state": int(expert_action_masked.sum()),
        "label_conditioned_mask_mutations": 0,
    }
    return payload, statistics


def main() -> None:
    args = parse_args()
    source = resolve_path(args.input, must_exist=True)
    output = resolve_path(args.output)
    manifest_path = resolve_path(args.manifest_out)
    profile = PublicObservationDegradationProfile(
        **{
            name: getattr(args, name)
            for name in asdict(PublicObservationDegradationProfile())
        }
    )
    profile.validate()
    with np.load(source, allow_pickle=False) as loaded:
        arrays = {name: loaded[name] for name in loaded.files}
    payload, statistics = build_public_sidecar(
        arrays=arrays,
        profile=profile,
        seed=args.seed,
        max_samples=args.max_samples,
    )
    atomic_save_npz(output, payload)
    manifest = {
        **statistics,
        "input": str(source),
        "input_sha256": file_sha256(source),
        "output": str(output),
        "output_sha256": file_sha256(output),
    }
    atomic_write_json(manifest_path, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
