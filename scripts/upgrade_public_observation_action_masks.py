from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from clasher.paths import resolve_path
from clasher.rl.oracle_corpus import atomic_save_npz, atomic_write_json, file_sha256
from clasher.rl.public_action_mask import (
    PUBLIC_ACTION_MASK_CONTRACT_VERSION,
    PublicActionMaskBuilder,
    PublicActionMaskInput,
)
from clasher.rl.public_observation import REAL_PLAY_FEATURE_CONTRACT_VERSION
from clasher.rl.structured_obs import StructuredObservationBuilder


def _token_names(base: dict[str, np.ndarray]) -> tuple[str, ...]:
    metadata_json = base.get("metadata_json")
    if metadata_json is None:
        raise ValueError("base corpus has no metadata_json token vocabulary")
    metadata = json.loads(str(metadata_json.item()))
    names = tuple(str(name) for name in metadata.get("token_names", ()))
    if not names:
        raise ValueError("base corpus metadata has no token_names")
    return names


def upgrade_action_masks(
    *,
    base: dict[str, np.ndarray],
    sidecar: dict[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    required = (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "entity_id_confidence",
        "hand_ids",
        "hand_id_confidence",
        "global_features",
        "global_feature_confidence",
    )
    missing = [name for name in required if name not in sidecar]
    if missing:
        raise ValueError(f"public sidecar is missing arrays: {missing}")
    if "expert_actions" not in base:
        raise ValueError("base corpus has no expert_actions")
    samples = int(base["expert_actions"].shape[0])
    if any(sidecar[name].shape[0] != samples for name in required):
        raise ValueError("public sidecar row count does not match base corpus")

    builder = PublicActionMaskBuilder(
        StructuredObservationBuilder(token_names=_token_names(base))
    )
    action_masks = np.zeros((samples, builder.num_actions), dtype=np.bool_)
    expert_action_masked = np.zeros((samples,), dtype=np.bool_)
    for index in range(samples):
        observation = PublicActionMaskInput(
            entity_ids=sidecar["entity_ids"][index],
            entity_features=sidecar["entity_features"][index],
            entity_mask=sidecar["entity_mask"][index],
            hand_ids=sidecar["hand_ids"][index],
            global_features=sidecar["global_features"][index],
            entity_id_confidence=sidecar["entity_id_confidence"][index],
            hand_id_confidence=sidecar["hand_id_confidence"][index],
            global_feature_confidence=sidecar["global_feature_confidence"][index],
        )
        action_mask = builder.build(observation)
        expert_action = int(base["expert_actions"][index])
        if not action_mask[expert_action]:
            expert_action_masked[index] = True
        action_masks[index] = action_mask

    payload = {name: value.copy() for name, value in sidecar.items()}
    payload["action_masks"] = action_masks
    payload["expert_actions"] = base["expert_actions"].copy()
    payload["expert_action_masked"] = expert_action_masked
    payload["feature_contract_version"] = np.asarray(
        REAL_PLAY_FEATURE_CONTRACT_VERSION
    )
    payload["action_mask_contract_version"] = np.asarray(
        PUBLIC_ACTION_MASK_CONTRACT_VERSION
    )
    legal_counts = action_masks.sum(axis=1)
    statistics = {
        "schema": "confidence-aware-public-observation-v2",
        "feature_contract_version": REAL_PLAY_FEATURE_CONTRACT_VERSION,
        "action_mask_contract_version": PUBLIC_ACTION_MASK_CONTRACT_VERSION,
        "samples": samples,
        "expert_mask_recoveries": 0,
        "expert_actions_masked_by_public_state": int(expert_action_masked.sum()),
        "label_conditioned_mask_mutations": 0,
        "mean_legal_actions": float(legal_counts.mean()),
        "minimum_legal_actions": int(legal_counts.min()),
        "maximum_legal_actions": int(legal_counts.max()),
    }
    return payload, statistics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add public-only action masks to an aligned vision sidecar"
    )
    parser.add_argument("--base-corpus", required=True)
    parser.add_argument("--sidecar", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-out", required=True)
    return parser.parse_args()


def _load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as loaded:
        return {name: loaded[name] for name in loaded.files}


def main() -> None:
    args = parse_args()
    base_path = resolve_path(args.base_corpus, must_exist=True)
    sidecar_path = resolve_path(args.sidecar, must_exist=True)
    output_path = resolve_path(args.output)
    manifest_path = resolve_path(args.manifest_out)
    payload, statistics = upgrade_action_masks(
        base=_load(base_path),
        sidecar=_load(sidecar_path),
    )
    atomic_save_npz(output_path, payload)
    manifest = {
        **statistics,
        "base_corpus": str(base_path),
        "base_corpus_sha256": file_sha256(base_path),
        "input_sidecar": str(sidecar_path),
        "input_sidecar_sha256": file_sha256(sidecar_path),
        "output": str(output_path),
        "output_sha256": file_sha256(output_path),
    }
    atomic_write_json(manifest_path, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
