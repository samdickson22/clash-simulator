#!/usr/bin/env python3
"""Create a fresh current-client F3 policy with a direct recurrent play gate."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import save_checkpoint


def create_control(
    *,
    architecture_source: Path,
    decks_path: Path,
    output: Path,
    seed: int,
) -> dict[str, object]:
    source = torch.load(architecture_source, map_location="cpu", weights_only=False)
    if int(source.get("format_version", 0)) != 2:
        raise ValueError("architecture source is not a V2 policy")
    base = PolicyConfig.from_dict(source["model_config"])
    token_names = tuple(str(name) for name in source["token_names"])
    builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=base.max_entities,
        token_names=token_names,
        card_semantics_version=base.card_semantics_version,
        canonical_lane_globals=base.canonical_lane_globals,
        public_history_slots=base.public_history_slots,
        public_seen_card_slots=base.public_seen_card_slots,
    )
    if tuple(builder.token_names) != token_names:
        raise ValueError("builder changed the frozen current-client vocabulary")
    config = replace(
        base,
        deterministic_hierarchy="play-gate",
        play_hazard_enabled=False,
        play_hazard_positive_weight=1.0,
        play_hazard_base_rate=0.5,
        play_hazard_threshold=0.5,
        play_hazard_adapter_size=0,
        play_hazard_adapter_enemy_y_gate=1.0,
        play_hazard_adapter_gain=1.0,
    )
    torch.manual_seed(seed)
    model = ClasherPolicy(config, builder.card_stat_features)
    if any(
        name.startswith("play_hazard_head.") for name, _ in model.named_parameters()
    ):
        raise RuntimeError("direct play-gate control unexpectedly has a hazard head")
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing existing play-gate control: {output}")
    provenance = argparse.Namespace(
        source="fresh_f3_play_gate_control",
        architecture_source=str(architecture_source.resolve()),
        seed=seed,
        deterministic_hierarchy="play-gate",
        play_hazard_enabled=False,
    )
    save_checkpoint(
        output,
        model=model,
        optimizer=optimizer,
        builder=builder,
        args=provenance,
        update=0,
        total_transitions=0,
        metrics={},
    )
    return {
        "output": str(output.resolve()),
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "seed": seed,
        "tokens": len(token_names),
        "deterministic_hierarchy": config.deterministic_hierarchy,
        "play_hazard_enabled": config.play_hazard_enabled,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--architecture-source", required=True, type=Path)
    parser.add_argument("--decks-path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    args = parser.parse_args()
    print(
        json.dumps(
            create_control(
                architecture_source=args.architecture_source,
                decks_path=args.decks_path,
                output=args.output,
                seed=args.seed,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
