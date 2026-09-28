"""Add a zero-output domain-stable action adapter to a V2 checkpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig


def add_robust_action_type_adapter(payload: dict, *, hidden_size: int = 64) -> dict:
    if hidden_size <= 0:
        raise ValueError("robust action adapter hidden size must be positive")
    config = PolicyConfig.from_dict(payload["model_config"])
    if config.robust_action_type_adapter_size > 0:
        raise ValueError("checkpoint already has a robust action-type adapter")
    if config.card_semantics_version not in {1, 3}:
        raise ValueError("robust action adapter requires base public card features")
    upgraded_config = PolicyConfig.from_dict(
        {**config.to_dict(), "robust_action_type_adapter_size": hidden_size}
    )
    state = payload["model_state_dict"]
    card_stats = state["actor_encoder.card_stat_features"].detach().cpu().numpy()
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0)
        model = ClasherPolicy(upgraded_config, card_stats)
    incompatible = model.load_state_dict(state, strict=False)
    if incompatible.unexpected_keys or not incompatible.missing_keys:
        raise ValueError("unexpected checkpoint mismatch while adding robust adapter")
    if not all(
        name == "robust_action_card_stats"
        or name.startswith("robust_action_type_adapter.")
        for name in incompatible.missing_keys
    ):
        raise ValueError("only robust-action-adapter tensors may be absent")

    output = model.robust_action_type_adapter
    assert output is not None
    final = output[-1]
    assert isinstance(final, torch.nn.Linear)
    if torch.count_nonzero(final.weight) or torch.count_nonzero(final.bias):
        raise RuntimeError("new robust action adapter is not zero-output")

    upgraded = dict(payload)
    upgraded["model_config"] = upgraded_config.to_dict()
    upgraded["model_state_dict"] = model.state_dict()
    upgraded.pop("optimizer_state_dict", None)
    upgraded["robust_action_type_adapter_upgrade"] = {
        "schema_version": 1,
        "source_update": int(payload.get("update", 0)),
        "hidden_size": hidden_size,
        "feature_schema": "public-mechanics-coarse-board-v1",
        "preserves_base_policy_exactly": True,
    }
    return upgraded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hidden-size", type=int, default=64)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = torch.load(args.input, map_location="cpu", weights_only=False)
    upgraded = add_robust_action_type_adapter(
        payload,
        hidden_size=args.hidden_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(upgraded, args.output)
    print(f"wrote_robust_action_adapter_checkpoint={args.output.resolve()}")


if __name__ == "__main__":
    main()
