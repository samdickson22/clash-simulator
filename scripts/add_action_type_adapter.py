"""Add the zero-output contextual action-type adapter to a V2 checkpoint."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig


def add_action_type_adapter(payload: dict) -> dict:
    config = PolicyConfig.from_dict(payload["model_config"])
    if config.action_type_adapter_enabled:
        raise ValueError("checkpoint already has an action-type adapter")
    upgraded_config = PolicyConfig.from_dict(
        {**config.to_dict(), "action_type_adapter_enabled": True}
    )
    state = payload["model_state_dict"]
    card_stats = state["actor_encoder.card_stat_features"].detach().cpu().numpy()
    model = ClasherPolicy(upgraded_config, card_stats)
    incompatible = model.load_state_dict(state, strict=False)
    if incompatible.unexpected_keys or not incompatible.missing_keys:
        raise ValueError("unexpected checkpoint mismatch while adding adapter")
    if not all(
        name.startswith("action_type_adapter.")
        for name in incompatible.missing_keys
    ):
        raise ValueError("only action-type-adapter tensors may be absent")

    upgraded = dict(payload)
    upgraded["model_config"] = upgraded_config.to_dict()
    upgraded["model_state_dict"] = model.state_dict()
    upgraded.pop("optimizer_state_dict", None)
    upgraded["action_type_adapter_upgrade"] = {
        "schema_version": 1,
        "source_update": int(payload.get("update", 0)),
        "preserves_base_policy_exactly": True,
    }
    return upgraded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = torch.load(args.input, map_location="cpu", weights_only=False)
    upgraded = add_action_type_adapter(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(upgraded, args.output)
    print(f"wrote_action_type_adapter_checkpoint={args.output.resolve()}")


if __name__ == "__main__":
    main()
