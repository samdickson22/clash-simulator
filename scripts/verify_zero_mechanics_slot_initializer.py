"""Prove that a zero mechanics adapter preserves a recurrent policy exactly."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.imitation import (
    _sequence_batch_inputs,
    load_corpus,
    load_public_observation_sidecar,
)
from clasher.rl.model import PolicyConfig, PolicyOutput
from clasher.rl.oracle_corpus import file_sha256

_NEW_STATE_KEYS = {
    "mechanics_slot_card_stats",
    "mechanics_slot_choice_query.weight",
}


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assert_tensor_equal(
    name: str, source: torch.Tensor, candidate: torch.Tensor
) -> None:
    if source.dtype != candidate.dtype or source.shape != candidate.shape:
        raise ValueError(
            f"{name} tensor metadata changed: "
            f"{source.dtype}/{tuple(source.shape)} != "
            f"{candidate.dtype}/{tuple(candidate.shape)}"
        )
    source_bytes = source.detach().cpu().contiguous().view(torch.uint8)
    candidate_bytes = candidate.detach().cpu().contiguous().view(torch.uint8)
    if not torch.equal(source_bytes, candidate_bytes):
        raise ValueError(f"{name} tensor values changed")


def verify_checkpoint_structure(source: dict, candidate: dict) -> dict[str, Any]:
    for name in ("format_version", "update", "token_names"):
        if source.get(name) != candidate.get(name):
            raise ValueError(f"checkpoint {name} changed")

    source_state = source.get("model_state_dict")
    candidate_state = candidate.get("model_state_dict")
    if not isinstance(source_state, dict) or not isinstance(candidate_state, dict):
        raise TypeError("checkpoint model state must be a dictionary")
    source_keys = set(source_state)
    candidate_keys = set(candidate_state)
    if candidate_keys - source_keys != _NEW_STATE_KEYS:
        raise ValueError(
            "zero adapter has unexpected new tensors: "
            f"{sorted(candidate_keys - source_keys)!r}"
        )
    if source_keys - candidate_keys:
        raise ValueError(
            f"zero adapter dropped tensors: {sorted(source_keys - candidate_keys)!r}"
        )
    for name in sorted(source_keys):
        _assert_tensor_equal(name, source_state[name], candidate_state[name])

    query = candidate_state["mechanics_slot_choice_query.weight"]
    if int(torch.count_nonzero(query).item()) != 0:
        raise ValueError("mechanics adapter query is not exactly zero")

    source_config = PolicyConfig.from_dict(source["model_config"]).to_dict()
    expected_config = {
        **source_config,
        "mechanics_slot_choice_adapter_enabled": True,
        "mechanics_slot_choice_replace_base": False,
        "mechanics_slot_choice_base_scale": 1.0,
    }
    candidate_config = PolicyConfig.from_dict(candidate["model_config"]).to_dict()
    if candidate_config != expected_config:
        changed = {
            name: (source_config.get(name), candidate_config.get(name))
            for name in sorted(set(source_config) | set(candidate_config))
            if source_config.get(name) != candidate_config.get(name)
        }
        raise ValueError(f"unexpected policy config changes: {changed!r}")

    metadata = candidate.get("mechanics_slot_choice_adapter_upgrade")
    required_metadata = {
        "schema_version": 1,
        "source_update": int(source.get("update", 0)),
        "preserves_base_policy_exactly_at_zero": True,
        "preserves_play_wait_ability_mass_after_training": True,
        "preserves_conditional_placement_geometry": True,
        "scores_only_frozen_public_mechanics": True,
        "mechanics_feature_count": 16,
        "replaces_base_conditional_slot_logits": False,
        "base_logit_scale": 1.0,
        "initialized_from_pretrained_query": False,
        "query_scale": 1.0,
    }
    if metadata != required_metadata:
        raise ValueError("zero adapter upgrade metadata does not match its contract")

    return {
        "inherited_tensor_count": len(source_keys),
        "new_tensor_names": sorted(_NEW_STATE_KEYS),
        "query_nonzero_count": 0,
        "config_changes": {
            "mechanics_slot_choice_adapter_enabled": [False, True],
        },
        "upgrade_metadata": metadata,
    }


def _output_tensors(output: PolicyOutput) -> dict[str, torch.Tensor]:
    tensors: dict[str, torch.Tensor] = {}
    for field in fields(output):
        value = getattr(output, field.name)
        if value is None:
            continue
        if isinstance(value, torch.Tensor):
            tensors[field.name] = value
        elif isinstance(value, tuple):
            for index, item in enumerate(value):
                if not isinstance(item, torch.Tensor):
                    raise TypeError(
                        f"unsupported PolicyOutput tuple field {field.name}"
                    )
                tensors[f"{field.name}[{index}]"] = item
        else:
            raise TypeError(f"unsupported PolicyOutput field {field.name}")
    return tensors


def verify_runtime_equivalence(
    *,
    source_checkpoint: Path,
    candidate_checkpoint: Path,
    corpus_path: Path,
    public_sidecar_path: Path | None,
    decks_path: Path,
) -> dict[str, Any]:
    device = torch.device("cpu")
    source = load_policy_checkpoint(
        source_checkpoint,
        device=device,
        decks_path=decks_path,
    )
    candidate = load_policy_checkpoint(
        candidate_checkpoint,
        device=device,
        decks_path=decks_path,
    )
    metadata, arrays = load_corpus(corpus_path)
    if public_sidecar_path is not None:
        arrays = load_public_observation_sidecar(
            public_sidecar_path,
            base_arrays=arrays,
        )

    episode_ids = arrays["episode_ids"]
    compared_fields: set[str] = set()
    equivalent_auxiliary_fields: set[str] = set()
    action_count = 0
    with torch.no_grad():
        for episode_id in np.unique(episode_ids):
            indices = np.flatnonzero(episode_ids == episode_id)
            if indices.size == 0 or np.any(np.diff(indices) != 1):
                raise ValueError("corpus episode samples must be contiguous")
            inputs = _sequence_batch_inputs(arrays, indices[None, :], device)
            source_output = source.model(inputs)
            candidate_output = candidate.model(inputs)
            source_tensors = _output_tensors(source_output)
            candidate_tensors = _output_tensors(candidate_output)
            candidate_only = candidate_tensors.keys() - source_tensors.keys()
            if candidate_only == {"deterministic_timing_logits"}:
                _assert_tensor_equal(
                    f"episode={int(episode_id)} deterministic_timing_logits",
                    source_tensors["action_type_logits"],
                    candidate_tensors.pop("deterministic_timing_logits"),
                )
                equivalent_auxiliary_fields.add("deterministic_timing_logits")
            if source_tensors.keys() != candidate_tensors.keys():
                raise ValueError(
                    "PolicyOutput fields changed: "
                    f"source_only={sorted(source_tensors.keys() - candidate_tensors.keys())!r}, "
                    f"candidate_only={sorted(candidate_tensors.keys() - source_tensors.keys())!r}"
                )
            for name in sorted(source_tensors):
                _assert_tensor_equal(
                    f"episode={int(episode_id)} output={name}",
                    source_tensors[name],
                    candidate_tensors[name],
                )
                compared_fields.add(name)
            source_actions = source.model._deterministic_actions(
                source_output,
                inputs.action_mask,
            )
            candidate_actions = candidate.model._deterministic_actions(
                candidate_output,
                inputs.action_mask,
            )
            _assert_tensor_equal(
                f"episode={int(episode_id)} deterministic_actions",
                source_actions,
                candidate_actions,
            )
            action_count += int(source_actions.numel())

    return {
        "corpus_schema_version": int(metadata.schema_version),
        "episodes": int(np.unique(episode_ids).size),
        "samples": int(metadata.samples),
        "deterministic_actions_compared": action_count,
        "policy_output_fields_compared": sorted(compared_fields),
        "equivalent_candidate_auxiliary_fields": sorted(equivalent_auxiliary_fields),
        "all_policy_outputs_bitwise_equal": True,
        "all_deterministic_actions_equal": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a zero mechanics adapter is an exact RL initializer"
    )
    parser.add_argument("--source-checkpoint", required=True, type=Path)
    parser.add_argument("--candidate-checkpoint", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--public-observation-sidecar", type=Path)
    parser.add_argument("--decks-path", default=Path("decks.json"), type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    args = parser.parse_args()

    source_payload = torch.load(
        args.source_checkpoint,
        map_location="cpu",
        weights_only=False,
    )
    candidate_payload = torch.load(
        args.candidate_checkpoint,
        map_location="cpu",
        weights_only=False,
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "source_checkpoint": str(args.source_checkpoint.resolve()),
        "source_checkpoint_sha256": file_sha256(args.source_checkpoint),
        "candidate_checkpoint": str(args.candidate_checkpoint.resolve()),
        "candidate_checkpoint_sha256": file_sha256(args.candidate_checkpoint),
        "corpus": str(args.corpus.resolve()),
        "corpus_sha256": file_sha256(args.corpus),
        "public_observation_sidecar": (
            str(args.public_observation_sidecar.resolve())
            if args.public_observation_sidecar is not None
            else None
        ),
        "public_observation_sidecar_sha256": (
            file_sha256(args.public_observation_sidecar)
            if args.public_observation_sidecar is not None
            else None
        ),
        "structure": verify_checkpoint_structure(source_payload, candidate_payload),
        "runtime": verify_runtime_equivalence(
            source_checkpoint=args.source_checkpoint,
            candidate_checkpoint=args.candidate_checkpoint,
            corpus_path=args.corpus,
            public_sidecar_path=args.public_observation_sidecar,
            decks_path=args.decks_path,
        ),
        "exact_behavior_preservation_verified": True,
    }
    report["evidence_sha256"] = _canonical_sha256(report)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
