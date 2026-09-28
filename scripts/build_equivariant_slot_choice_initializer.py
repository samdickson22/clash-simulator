from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_equivariant_initializer(
    payload: dict[str, Any],
    *,
    include_semantic_query: bool = False,
) -> dict[str, Any]:
    config = PolicyConfig.from_dict(payload["model_config"])
    if not config.mechanics_slot_choice_adapter_enabled:
        raise ValueError("equivariant initializer requires a mechanics card query")
    if config.semantic_slot_choice_adapter_enabled:
        raise ValueError("first equivariant initializer isolates the mechanics query")
    upgraded = PolicyConfig.from_dict(
        {
            **config.to_dict(),
            "actor_current_hand_slot_invariant": True,
            "semantic_slot_choice_adapter_enabled": include_semantic_query,
            "semantic_slot_choice_replace_base": include_semantic_query,
            "mechanics_slot_choice_replace_base": True,
            "mechanics_slot_choice_base_scale": 1.0,
            "equivariant_slot_choice": True,
        }
    )
    state = payload["model_state_dict"]
    card_stats = state.get("actor_encoder.card_stat_features")
    if not isinstance(card_stats, (np.ndarray, torch.Tensor)):
        raise TypeError("source checkpoint has no mechanics card-stat buffer")
    if config.card_semantics_version == 3:
        semantic_stats = state.get("actor_encoder.semantic_card_features")
        if not isinstance(semantic_stats, (np.ndarray, torch.Tensor)):
            raise TypeError("semantic-v3 source has no semantic card-stat buffer")
        card_stats = torch.cat(
            (
                torch.as_tensor(card_stats),
                torch.as_tensor(semantic_stats),
            ),
            dim=-1,
        )
    model = ClasherPolicy(upgraded, card_stats)
    incompatible = model.load_state_dict(state, strict=False)
    expected_missing = (
        {"semantic_slot_choice_query.weight"} if include_semantic_query else set()
    )
    if (
        incompatible.unexpected_keys
        or set(incompatible.missing_keys) != expected_missing
    ):
        raise ValueError(
            "unexpected state mismatch while adding equivariant slot choice: "
            f"missing={sorted(incompatible.missing_keys)!r}, "
            f"unexpected={sorted(incompatible.unexpected_keys)!r}"
        )
    query = model.mechanics_slot_choice_query
    if query is None:
        raise RuntimeError("equivariant initializer did not construct its query")
    if bool(torch.count_nonzero(query.weight)):
        raise ValueError(
            "source mechanics query must be zero before structural pretraining"
        )

    result = dict(payload)
    result["model_config"] = upgraded.to_dict()
    result["model_state_dict"] = model.state_dict()
    result.pop("optimizer_state_dict", None)
    result["equivariant_slot_choice_upgrade"] = {
        "schema_version": 1,
        "actor_current_hand_slots_share_their_mean_embedding": True,
        "aggregate_play_timing_is_slot_permutation_invariant": True,
        "conditional_card_choice_replaces_fixed_slot_logits": True,
        "conditional_card_choice_query": "mechanics_slot_choice_query",
        "semantic_card_query_enabled": include_semantic_query,
        "query_is_zero_and_requires_supervised_pretraining": True,
        "legacy_checkpoint_outputs_preserved": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--include-semantic-query", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = torch.load(args.input, map_location="cpu", weights_only=False)
    upgraded = build_equivariant_initializer(
        payload,
        include_semantic_query=args.include_semantic_query,
    )
    upgraded["equivariant_slot_choice_upgrade"] = {
        **upgraded["equivariant_slot_choice_upgrade"],
        "source_checkpoint": str(args.input.resolve()),
        "source_checkpoint_sha256": _sha256(args.input),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(upgraded, args.output)
    print(f"output={args.output.resolve()}")
    print(f"sha256={_sha256(args.output)}")


if __name__ == "__main__":
    main()
