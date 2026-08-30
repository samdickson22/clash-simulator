#!/usr/bin/env python3
"""Convert a hazard-gated checkpoint into a trainable factorized play gate."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
from typing import Any

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig

CONVERSION_SCHEMA = "clasher.hazard-to-playgate-conversion.v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def convert_payload(
    payload: dict[str, Any],
    *,
    source: Path,
    source_sha256: str,
) -> dict[str, Any]:
    config = dict(payload["model_config"])
    if config.get("deterministic_hierarchy") != "hazard" or not bool(
        config.get("play_hazard_enabled")
    ):
        raise ValueError("source checkpoint is not hazard-gated")
    if not bool(config.get("hierarchical_mode_gate_enabled")):
        raise ValueError("source checkpoint has no factorized mode gate")
    config.update(
        deterministic_hierarchy="play-gate",
        play_hazard_enabled=False,
        play_hazard_adapter_size=0,
        play_hazard_adapter_enemy_y_gate=1.0,
        play_hazard_adapter_gain=1.0,
    )
    state = {
        name: value
        for name, value in payload["model_state_dict"].items()
        if not name.startswith(("play_hazard_head.", "play_hazard_adapter."))
    }
    converted = copy.deepcopy(payload)
    converted["model_config"] = config
    converted["model_state_dict"] = state
    converted.pop("optimizer_state_dict", None)
    converted["architecture_conversion"] = {
        "schema": CONVERSION_SCHEMA,
        "source": str(source.resolve()),
        "source_sha256": source_sha256,
        "removed_parameter_prefixes": [
            "play_hazard_head.",
            "play_hazard_adapter.",
        ],
        "deterministic_hierarchy": "play-gate",
        "requires_behavior_distillation_before_gameplay": True,
    }
    return converted


def validate_payload(payload: dict[str, Any]) -> None:
    state = payload["model_state_dict"]
    card_stats = torch.as_tensor(state["actor_encoder.card_stat_features"])
    semantic = state.get("actor_encoder.semantic_card_features")
    if semantic is not None:
        card_stats = torch.cat([card_stats, torch.as_tensor(semantic)], dim=-1)
    model = ClasherPolicy(
        PolicyConfig.from_dict(payload["model_config"]),
        card_stats,
    )
    model.load_state_dict(state, strict=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite checkpoint: {args.output}")
    source_sha256 = file_sha256(args.input)
    payload = torch.load(args.input, map_location="cpu", weights_only=False)
    converted = convert_payload(
        payload,
        source=args.input,
        source_sha256=source_sha256,
    )
    validate_payload(converted)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(converted, args.output)
    print(f"checkpoint={args.output.resolve()}")
    print(f"sha256={file_sha256(args.output)}")


if __name__ == "__main__":
    main()
