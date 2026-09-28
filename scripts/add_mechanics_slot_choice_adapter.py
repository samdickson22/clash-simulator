"""Add a timing-invariant mechanics-only hand-card adapter to a policy."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import math
from pathlib import Path

import numpy as np
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder


def add_mechanics_slot_choice_adapter(
    payload: dict,
    *,
    card_stat_features: np.ndarray | torch.Tensor | None = None,
    replace_base: bool = False,
    base_scale: float = 1.0,
    query_weight: torch.Tensor | None = None,
    query_scale: float = 1.0,
) -> dict:
    config = PolicyConfig.from_dict(payload["model_config"])
    if config.mechanics_slot_choice_adapter_enabled:
        raise ValueError("checkpoint already has a mechanics slot-choice adapter")
    if config.card_semantics_version not in {1, 3}:
        raise ValueError("mechanics slot adapter requires card semantics v1 or v3")
    if not math.isfinite(query_scale) or query_scale < 0.0:
        raise ValueError("query scale must be finite and nonnegative")
    if not math.isfinite(base_scale) or base_scale < 0.0:
        raise ValueError("base scale must be finite and nonnegative")
    if replace_base and base_scale != 1.0:
        raise ValueError("replace-base cannot be combined with a base scale")
    upgraded_config = PolicyConfig.from_dict(
        {
            **config.to_dict(),
            "mechanics_slot_choice_adapter_enabled": True,
            "mechanics_slot_choice_replace_base": replace_base,
            "mechanics_slot_choice_base_scale": base_scale,
        }
    )
    state = payload["model_state_dict"]
    if card_stat_features is None:
        card_stat_features = state.get("actor_encoder.card_stat_features")
        if card_stat_features is None:
            raise ValueError(
                "card stat features are required for an identity-only source policy"
            )
    card_stats = torch.as_tensor(card_stat_features, dtype=torch.float32)
    model = ClasherPolicy(upgraded_config, card_stats)
    incompatible = model.load_state_dict(state, strict=False)
    expected_missing = {
        "mechanics_slot_card_stats",
        "mechanics_slot_choice_query.weight",
    }
    if incompatible.unexpected_keys or set(incompatible.missing_keys) != expected_missing:
        raise ValueError(
            "unexpected checkpoint mismatch while adding mechanics adapter: "
            f"missing={sorted(incompatible.missing_keys)!r}, "
            f"unexpected={sorted(incompatible.unexpected_keys)!r}"
        )
    if query_weight is not None:
        expected = model.mechanics_slot_choice_query
        assert expected is not None
        if query_weight.shape != expected.weight.shape:
            raise ValueError(
                "pretrained mechanics query shape mismatch: "
                f"expected {tuple(expected.weight.shape)}, "
                f"got {tuple(query_weight.shape)}"
            )
        if not bool(torch.isfinite(query_weight).all()):
            raise ValueError("pretrained mechanics query must be finite")
        with torch.no_grad():
            expected.weight.copy_(query_weight * query_scale)

    upgraded = dict(payload)
    upgraded["model_config"] = upgraded_config.to_dict()
    upgraded["model_state_dict"] = model.state_dict()
    upgraded.pop("optimizer_state_dict", None)
    upgraded["mechanics_slot_choice_adapter_upgrade"] = {
        "schema_version": 1,
        "source_update": int(payload.get("update", 0)),
        "preserves_base_policy_exactly_at_zero": (
            not replace_base and base_scale == 1.0
        ),
        "preserves_play_wait_ability_mass_after_training": True,
        "preserves_conditional_placement_geometry": True,
        "scores_only_frozen_public_mechanics": True,
        "mechanics_feature_count": 16,
        "replaces_base_conditional_slot_logits": replace_base,
        "base_logit_scale": float(base_scale),
        "initialized_from_pretrained_query": query_weight is not None,
        "query_scale": float(query_scale),
    }
    return upgraded


def _probe_query_weight(probe: dict, *, token_names: tuple[str, ...]) -> torch.Tensor:
    if int(probe.get("schema_version", 0)) != 1:
        raise ValueError("mechanics probe has an unsupported schema")
    if int(probe.get("semantics_version", 0)) != 1:
        raise ValueError("mechanics probe must use the 16-feature v1 schema")
    if int(probe.get("hidden_size", -1)) != 0:
        raise ValueError("mechanics probe must be the linear scorer")
    if tuple(probe.get("token_names", ())) != token_names:
        raise ValueError("mechanics probe token vocabulary mismatch")
    state = probe.get("state_dict") or {}
    if set(state) != {"state_query.weight"}:
        raise ValueError("mechanics probe must contain only the linear state query")
    weight = state["state_query.weight"]
    if not isinstance(weight, torch.Tensor):
        raise TypeError("mechanics probe query is not a tensor")
    return weight


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--decks-path", default=Path("decks.json"), type=Path)
    parser.add_argument(
        "--replace-base",
        action="store_true",
        help=(
            "replace legacy conditional slot logits while retaining their total "
            "legal placement mass"
        ),
    )
    parser.add_argument(
        "--query-checkpoint",
        type=Path,
        help="linear v1 MechanicsSlotScorer checkpoint used to initialize the query",
    )
    parser.add_argument(
        "--base-scale",
        type=float,
        default=1.0,
        help=(
            "nonnegative multiplier for legacy slot logits; combine "
            "1-alpha here with alpha as query-scale to reproduce a logit blend"
        ),
    )
    parser.add_argument(
        "--query-scale",
        type=float,
        default=1.0,
        help="nonnegative multiplier applied to a pretrained query",
    )
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = torch.load(args.input, map_location="cpu", weights_only=False)
    config = PolicyConfig.from_dict(payload["model_config"])
    token_names = tuple(payload.get("token_names", ()))
    builder = StructuredObservationBuilder(
        decks_path=args.decks_path,
        max_entities=config.max_entities,
        token_names=token_names,
        card_semantics_version=config.card_semantics_version,
        canonical_lane_globals=config.canonical_lane_globals,
        public_history_slots=config.public_history_slots,
        public_seen_card_slots=config.public_seen_card_slots,
    )
    query_weight = None
    if args.query_checkpoint is not None:
        probe = torch.load(
            args.query_checkpoint,
            map_location="cpu",
            weights_only=False,
        )
        query_weight = _probe_query_weight(probe, token_names=token_names)
    upgraded = add_mechanics_slot_choice_adapter(
        payload,
        card_stat_features=builder.card_stat_features,
        replace_base=args.replace_base,
        base_scale=args.base_scale,
        query_weight=query_weight,
        query_scale=args.query_scale,
    )
    if args.query_checkpoint is not None:
        upgraded["mechanics_slot_choice_adapter_upgrade"] = {
            **upgraded["mechanics_slot_choice_adapter_upgrade"],
            "query_checkpoint": str(args.query_checkpoint.resolve()),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(upgraded, args.output)
    print(f"wrote_mechanics_slot_choice_adapter_checkpoint={args.output.resolve()}")


if __name__ == "__main__":
    main()
