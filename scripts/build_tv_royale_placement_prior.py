from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.paths import resolve_path
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH, NUM_TILES
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.structured_obs import StructuredObservationBuilder

IMAGE_WIDTH = 428
IMAGE_HEIGHT = 683
Y_OFFSET_TOP = 62
Y_OFFSET_BOTTOM = 7
MIDDLE_Y = Y_OFFSET_TOP + (IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM) / 2

SOURCE_ALIASES = {
    "barbbarrel": "BarbarianBarrel",
    "ewiz": "ElectroWizard",
    "ghost": "RoyalGhost",
    "skelebarrel": "SkeletonBarrel",
    "snowball": "GiantSnowball",
    "teslacoil": "Tesla",
    "valk": "Valkyrie",
}
AMBIGUOUS_SOURCE_CARDS = {"musketeers", "skarmy"}
GLOBAL_DEPLOY_CARDS = {"Miner"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_name(name: str) -> str:
    return "".join(character for character in name.lower() if character.isalnum())


def source_card_lookup(enabled_cards: Iterable[str]) -> dict[str, str]:
    cards = tuple(enabled_cards)
    lookup = {_normalized_name(card): card for card in cards}
    enabled = set(cards)
    lookup.update(
        {
            source: target
            for source, target in SOURCE_ALIASES.items()
            if target in enabled
        }
    )
    return lookup


def source_pixel_to_canonical_tile(x: int, y: int) -> int:
    grid_height = IMAGE_HEIGHT - Y_OFFSET_TOP - Y_OFFSET_BOTTOM
    tile_x = int(x / (IMAGE_WIDTH / BOARD_WIDTH))
    tile_y = int((y - Y_OFFSET_TOP) / (grid_height / BOARD_HEIGHT))
    tile_x = max(0, min(tile_x, BOARD_WIDTH - 1))
    tile_y = max(0, min(tile_y, BOARD_HEIGHT - 1))
    canonical_x = BOARD_WIDTH - 1 - tile_x
    canonical_y = BOARD_HEIGHT - 1 - tile_y
    return canonical_y * BOARD_WIDTH + canonical_x


def build_prior_logits(
    rows: Iterable[dict[str, str]],
    *,
    builder: StructuredObservationBuilder,
    enabled_cards: Iterable[str],
    alpha: float = 1.0,
) -> tuple[torch.Tensor, dict[str, Any]]:
    if alpha <= 0.0:
        raise ValueError("alpha must be positive")
    enabled = tuple(enabled_cards)
    lookup = source_card_lookup(enabled)
    counts = np.zeros((builder.spec.num_tokens, NUM_TILES), dtype=np.float64)
    examples: dict[str, int] = {}
    skipped: dict[str, int] = {}

    for row in rows:
        source_name = row["card"]
        reason: str | None = None
        if row.get("source_shard", "1") != "1":
            reason = "coordinate_schema"
        elif source_name.startswith("evo_"):
            reason = "evolution"
        elif source_name in AMBIGUOUS_SOURCE_CARDS:
            reason = "ambiguous_alias"
        else:
            card_name = lookup.get(_normalized_name(source_name))
            if card_name is None:
                reason = "outside_enabled_decks"
            else:
                stats = builder.loader.get_card(card_name)
                if stats is None:
                    reason = "missing_card_data"
                elif str(getattr(stats, "card_type", "")).lower() == "spell":
                    reason = "spell"
                elif card_name in GLOBAL_DEPLOY_CARDS:
                    reason = "global_deploy_ambiguous_seat"
                elif int(row["y"]) <= MIDDLE_Y:
                    reason = "opponent_side"
                else:
                    tile = source_pixel_to_canonical_tile(
                        int(row["x"]), int(row["y"])
                    )
                    token_id = builder.token_id(card_name)
                    counts[token_id, tile] += 1.0
                    mirror_x = BOARD_WIDTH - 1 - (tile % BOARD_WIDTH)
                    mirror_tile = (tile // BOARD_WIDTH) * BOARD_WIDTH + mirror_x
                    counts[token_id, mirror_tile] += 1.0
                    examples[card_name] = examples.get(card_name, 0) + 1
        if reason is not None:
            skipped[reason] = skipped.get(reason, 0) + 1

    logits = np.zeros_like(counts, dtype=np.float32)
    own_tiles = (BOARD_HEIGHT // 2) * BOARD_WIDTH
    for card_name, sample_count in examples.items():
        if sample_count <= 0:
            continue
        token_id = builder.token_id(card_name)
        own_counts = counts[token_id, :own_tiles]
        log_probabilities = np.log(
            (own_counts + alpha) / (own_counts.sum() + alpha * own_tiles)
        )
        logits[token_id, :own_tiles] = (
            log_probabilities - log_probabilities.mean()
        ).astype(np.float32)

    metadata = {
        "schema_version": 1,
        "alpha": alpha,
        "accepted_samples": int(sum(examples.values())),
        "cards_with_prior": len(examples),
        "examples_per_card": dict(sorted(examples.items())),
        "skipped": dict(sorted(skipped.items())),
        "horizontal_mirror_augmentation": True,
        "coordinate_transform": {
            "image_width": IMAGE_WIDTH,
            "image_height": IMAGE_HEIGHT,
            "y_offset_top": Y_OFFSET_TOP,
            "y_offset_bottom": Y_OFFSET_BOTTOM,
            "rotation_degrees": 180,
        },
    }
    return torch.from_numpy(logits), metadata


def augment_checkpoint(
    payload: dict[str, Any],
    *,
    builder: StructuredObservationBuilder,
    prior_logits: torch.Tensor,
    scale: float,
) -> dict[str, Any]:
    if not math.isfinite(scale) or scale < 0.0:
        raise ValueError("scale must be finite and non-negative")
    config = PolicyConfig.from_dict(payload["model_config"])
    if config.placement_prior_enabled:
        raise ValueError("checkpoint already has a placement prior")
    augmented_config = replace(config, placement_prior_enabled=True)
    model = ClasherPolicy(augmented_config, builder.card_stat_features)
    incompatible = model.load_state_dict(payload["model_state_dict"], strict=False)
    if incompatible.unexpected_keys or incompatible.missing_keys != [
        "placement_prior.weight"
    ]:
        raise ValueError("unexpected checkpoint mismatch while adding placement prior")
    if prior_logits.shape != (augmented_config.num_tokens, NUM_TILES):
        raise ValueError("placement-prior tensor shape differs from policy vocabulary")
    assert model.placement_prior is not None
    with torch.no_grad():
        model.placement_prior.weight.copy_(prior_logits * scale)

    result = dict(payload)
    result["model_config"] = augmented_config.to_dict()
    result["model_state_dict"] = model.state_dict()
    result.pop("optimizer_state_dict", None)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add a real-game card-conditioned placement prior to a V2 policy"
    )
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--placements-csv", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--scale", type=float, required=True)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--source-url", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checkpoint_path = resolve_path(args.checkpoint, must_exist=True)
    placements_path = resolve_path(args.placements_csv, must_exist=True)
    decks_path = resolve_path(args.decks_path, must_exist=True)
    output_path = resolve_path(args.output)
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("input is not a V2 policy checkpoint")
    config = PolicyConfig.from_dict(payload["model_config"])
    builder = StructuredObservationBuilder(
        decks_path=decks_path,
        max_entities=config.max_entities,
        token_names=payload["token_names"],
    )
    with placements_path.open(newline="") as source:
        prior_logits, metadata = build_prior_logits(
            csv.DictReader(source),
            builder=builder,
            enabled_cards={
                card
                for deck in json.loads(decks_path.read_text())["decks"]
                for card in deck["cards"]
            },
            alpha=args.alpha,
        )
    result = augment_checkpoint(
        payload,
        builder=builder,
        prior_logits=prior_logits,
        scale=args.scale,
    )
    result["placement_prior"] = {
        **metadata,
        "scale": args.scale,
        "source": str(placements_path),
        "source_sha256": file_sha256(placements_path),
        "source_url": args.source_url,
        "base_checkpoint": str(checkpoint_path),
        "base_checkpoint_sha256": file_sha256(checkpoint_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, output_path)
    print(
        json.dumps(
            {
                "output": str(output_path),
                "output_sha256": file_sha256(output_path),
                **result["placement_prior"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
