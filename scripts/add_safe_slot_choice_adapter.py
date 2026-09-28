"""Add a zero-output, deterministic-timing-safe slot adapter to a V2 policy."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig


def add_safe_slot_choice_adapter(payload: dict) -> dict:
    config = PolicyConfig.from_dict(payload["model_config"])
    if config.safe_slot_choice_adapter_enabled:
        raise ValueError("checkpoint already has a safe slot-choice adapter")
    upgraded_config = PolicyConfig.from_dict(
        {**config.to_dict(), "safe_slot_choice_adapter_enabled": True}
    )
    state = payload["model_state_dict"]
    card_stats = state["actor_encoder.card_stat_features"].detach().cpu().numpy()
    model = ClasherPolicy(upgraded_config, card_stats)
    incompatible = model.load_state_dict(state, strict=False)
    if incompatible.unexpected_keys or not incompatible.missing_keys:
        raise ValueError("unexpected checkpoint mismatch while adding safe adapter")
    if not all(
        name.startswith("safe_slot_choice_adapter.")
        for name in incompatible.missing_keys
    ):
        raise ValueError("only safe slot-choice-adapter tensors may be absent")

    upgraded = dict(payload)
    upgraded["model_config"] = upgraded_config.to_dict()
    upgraded["model_state_dict"] = model.state_dict()
    upgraded.pop("optimizer_state_dict", None)
    upgraded["safe_slot_choice_adapter_upgrade"] = {
        "schema_version": 1,
        "source_update": int(payload.get("update", 0)),
        "preserves_base_policy_exactly_at_zero": True,
        "preserves_deterministic_play_wait_ability_after_training": True,
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
    upgraded = add_safe_slot_choice_adapter(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(upgraded, args.output)
    print(f"wrote_safe_slot_choice_adapter_checkpoint={args.output.resolve()}")


if __name__ == "__main__":
    main()
