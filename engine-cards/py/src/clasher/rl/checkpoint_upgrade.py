from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import torch

from .model import ClasherPolicy, PolicyConfig
from .structured_obs import StructuredObservationBuilder


def _semantic_v3_missing_keys() -> set[str]:
    suffixes = {
        "semantic_card_features",
        "semantic_card_projection.0.weight",
        "semantic_card_projection.0.bias",
        "semantic_card_projection.2.weight",
        "semantic_card_projection.2.bias",
    }
    return {
        f"{encoder}.{suffix}"
        for encoder in ("actor_encoder", "critic_encoder")
        for suffix in suffixes
    }


def upgrade_v1_checkpoint_to_semantic_v3(
    *,
    source_path: Path,
    output_path: Path,
    decks_path: Path,
    seed: int,
) -> dict[str, Any]:
    """Add the zero-output semantic-v3 residual path to a v1 policy.

    All v1 parameters and legacy card descriptors are retained exactly. The
    new semantic path's final linear layer is zero initialized, so it cannot
    change policy outputs until it is trained.
    """

    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise ValueError("semantic upgrade output must differ from its source")
    payload = torch.load(source_path, map_location="cpu", weights_only=False)
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("source checkpoint is not a V2 recurrent policy")
    source_config = PolicyConfig.from_dict(payload["model_config"])
    if source_config.card_semantics_version != 1:
        raise ValueError("semantic-v3 upgrade requires a semantic-v1 checkpoint")
    token_names = tuple(payload["token_names"])
    source_builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=source_config.max_entities,
        token_names=token_names,
        card_semantics_version=1,
        public_history_slots=source_config.public_history_slots,
        public_seen_card_slots=source_config.public_seen_card_slots,
    )
    source_model = ClasherPolicy(
        source_config,
        source_builder.card_stat_features,
    )
    source_model.load_state_dict(payload["model_state_dict"])

    target_config = replace(source_config, card_semantics_version=3)
    target_builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=target_config.max_entities,
        token_names=token_names,
        card_semantics_version=3,
        public_history_slots=target_config.public_history_slots,
        public_seen_card_slots=target_config.public_seen_card_slots,
    )
    torch.manual_seed(seed)
    target_model = ClasherPolicy(
        target_config,
        target_builder.card_stat_features,
    )
    incompatible = target_model.load_state_dict(source_model.state_dict(), strict=False)
    expected_missing = _semantic_v3_missing_keys()
    if incompatible.unexpected_keys or set(incompatible.missing_keys) != expected_missing:
        raise ValueError(
            "unexpected state mismatch during semantic-v3 upgrade: "
            f"missing={sorted(incompatible.missing_keys)!r}, "
            f"unexpected={sorted(incompatible.unexpected_keys)!r}"
        )

    upgraded = dict(payload)
    upgraded.pop("optimizer_state_dict", None)
    upgraded["model_config"] = target_config.to_dict()
    upgraded["model_state_dict"] = target_model.state_dict()
    args = dict(payload.get("args") or {})
    args["card_semantics_upgrade"] = {
        "source_checkpoint": str(source_path),
        "source_version": 1,
        "target_version": 3,
        "seed": int(seed),
        "zero_output_residual": True,
    }
    upgraded["args"] = args
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(upgraded, output_path)
    return {
        "schema_version": 1,
        "source_checkpoint": str(source_path),
        "output_checkpoint": str(output_path),
        "source_card_semantics_version": 1,
        "target_card_semantics_version": 3,
        "seed": int(seed),
        "missing_keys_initialized": sorted(expected_missing),
        "optimizer_state_preserved": False,
        "source_parameters": sum(parameter.numel() for parameter in source_model.parameters()),
        "target_parameters": sum(parameter.numel() for parameter in target_model.parameters()),
    }


def scale_semantic_v3_adapter(
    *,
    source_path: Path,
    output_path: Path,
    alpha: float,
) -> dict[str, Any]:
    """Scale the semantic residual contribution without changing its features."""

    if not 0.0 <= alpha <= 1.0:
        raise ValueError("semantic adapter alpha must be between zero and one")
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise ValueError("scaled checkpoint output must differ from its source")
    payload = torch.load(source_path, map_location="cpu", weights_only=False)
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("source checkpoint is not a V2 recurrent policy")
    config = PolicyConfig.from_dict(payload["model_config"])
    if config.card_semantics_version != 3:
        raise ValueError("semantic adapter scaling requires a semantic-v3 checkpoint")
    state = dict(payload["model_state_dict"])
    scaled_keys = []
    for encoder in ("actor_encoder", "critic_encoder"):
        for suffix in ("weight", "bias"):
            key = f"{encoder}.semantic_card_projection.2.{suffix}"
            value = state.get(key)
            if value is None:
                raise ValueError(f"semantic-v3 checkpoint is missing {key}")
            if not isinstance(value, torch.Tensor):
                raise TypeError(f"semantic-v3 checkpoint has non-tensor {key}")
            state[key] = value * alpha
            scaled_keys.append(key)
    scaled = dict(payload)
    scaled.pop("optimizer_state_dict", None)
    scaled["model_state_dict"] = state
    args = dict(payload.get("args") or {})
    args["semantic_card_adapter_scale"] = {
        "source_checkpoint": str(source_path),
        "alpha": float(alpha),
    }
    scaled["args"] = args
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(scaled, output_path)
    return {
        "schema_version": 1,
        "source_checkpoint": str(source_path),
        "output_checkpoint": str(output_path),
        "alpha": float(alpha),
        "scaled_keys": scaled_keys,
        "optimizer_state_preserved": False,
    }
