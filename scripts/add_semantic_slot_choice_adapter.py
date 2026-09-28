"""Add a zero-output, card-semantic, timing-safe slot adapter to a policy."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
from pathlib import Path

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig


def add_semantic_slot_choice_adapter(
    payload: dict,
    *,
    replace_base: bool = False,
    query_weight: torch.Tensor | None = None,
) -> dict:
    config = PolicyConfig.from_dict(payload["model_config"])
    if config.semantic_slot_choice_adapter_enabled:
        raise ValueError("checkpoint already has a semantic slot-choice adapter")
    upgraded_config = PolicyConfig.from_dict(
        {
            **config.to_dict(),
            "semantic_slot_choice_adapter_enabled": True,
            "semantic_slot_choice_replace_base": replace_base,
        }
    )
    state = payload["model_state_dict"]
    card_stats = state["actor_encoder.card_stat_features"].detach().cpu().numpy()
    model = ClasherPolicy(upgraded_config, card_stats)
    incompatible = model.load_state_dict(state, strict=False)
    if incompatible.unexpected_keys or not incompatible.missing_keys:
        raise ValueError("unexpected checkpoint mismatch while adding semantic adapter")
    if not all(
        name.startswith("semantic_slot_choice_query.")
        for name in incompatible.missing_keys
    ):
        raise ValueError("only semantic slot-choice tensors may be absent")
    if query_weight is not None:
        expected = model.semantic_slot_choice_query
        assert expected is not None
        if query_weight.shape != expected.weight.shape:
            raise ValueError(
                "pretrained semantic query shape mismatch: "
                f"expected {tuple(expected.weight.shape)}, "
                f"got {tuple(query_weight.shape)}"
            )
        if not bool(torch.isfinite(query_weight).all()):
            raise ValueError("pretrained semantic query must be finite")
        with torch.no_grad():
            expected.weight.copy_(query_weight)

    upgraded = dict(payload)
    upgraded["model_config"] = upgraded_config.to_dict()
    upgraded["model_state_dict"] = model.state_dict()
    upgraded.pop("optimizer_state_dict", None)
    upgraded["semantic_slot_choice_adapter_upgrade"] = {
        "schema_version": 1,
        "source_update": int(payload.get("update", 0)),
        "preserves_base_policy_exactly_at_zero": not replace_base,
        "preserves_play_wait_ability_mass_after_training": True,
        "scores_frozen_identity_and_mechanics_embeddings": True,
        "replaces_base_conditional_slot_logits": replace_base,
        "initialized_from_pretrained_query": query_weight is not None,
    }
    return upgraded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--replace-base",
        action="store_true",
        help=(
            "replace legacy conditional hand-slot logits while preserving "
            "their total legal placement mass"
        ),
    )
    parser.add_argument(
        "--query-checkpoint",
        type=Path,
        help="checkpoint supplying a trained semantic_slot_choice_query.weight",
    )
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = torch.load(args.input, map_location="cpu", weights_only=False)
    query_weight = None
    if args.query_checkpoint is not None:
        query_payload = torch.load(
            args.query_checkpoint,
            map_location="cpu",
            weights_only=False,
        )
        if tuple(query_payload.get("token_names", ())) != tuple(
            payload.get("token_names", ())
        ):
            raise SystemExit("query checkpoint token vocabulary mismatch")
        query_weight = query_payload.get("model_state_dict", {}).get(
            "semantic_slot_choice_query.weight"
        )
        if query_weight is None:
            raise SystemExit("query checkpoint has no semantic slot-choice query")
    upgraded = add_semantic_slot_choice_adapter(
        payload,
        replace_base=args.replace_base,
        query_weight=query_weight,
    )
    if args.query_checkpoint is not None:
        upgraded["semantic_slot_choice_adapter_upgrade"] = {
            **upgraded["semantic_slot_choice_adapter_upgrade"],
            "query_checkpoint": str(args.query_checkpoint.resolve()),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(upgraded, args.output)
    print(f"wrote_semantic_slot_choice_adapter_checkpoint={args.output.resolve()}")


if __name__ == "__main__":
    main()
