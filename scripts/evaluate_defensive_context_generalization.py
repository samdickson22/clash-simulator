"""Measure human action-type agreement under visible defensive pressure."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from typing import Any

import numpy as np

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.human_context import visible_enemy_pressure_mask
from clasher.rl.imitation import load_corpus
from clasher.rl.train_recurrent import resolve_torch_device
from scripts.evaluate_recurrent_corpus import _action_types, _checkpoint_metrics


def _pressure_context_masks(
    entity_features: np.ndarray,
    entity_mask: np.ndarray,
) -> dict[str, np.ndarray]:
    """Create conservative contexts from public video detections.

    Canonical y=0 is the observed player's defended side. Only detected enemy
    troops/buildings count; spells, projectiles, and Crown Towers are excluded.
    This is a visible-pressure proxy, not a claim about simulator aggro or DPS.
    """
    if entity_features.ndim != 3 or entity_features.shape[2] < 32:
        raise ValueError("entity_features must have shape [samples, entities, >=32]")
    if entity_mask.shape != entity_features.shape[:2]:
        raise ValueError("entity_mask shape must match entity features")
    tower_zone = visible_enemy_pressure_mask(
        entity_features, entity_mask, maximum_canonical_y=0.25
    )
    own_half = visible_enemy_pressure_mask(
        entity_features, entity_mask, maximum_canonical_y=0.50
    )
    return {
        "tower_zone": tower_zone,
        "own_half_pressure": own_half,
        "remote_or_clear": ~own_half,
    }


def _context_metrics(
    *,
    selected: np.ndarray,
    episode_ids: np.ndarray,
    expert_actions: np.ndarray,
    chosen_actions: np.ndarray,
    action_type_nll: np.ndarray,
) -> dict[str, Any]:
    count = int(np.sum(selected))
    if count == 0:
        return {
            "samples": 0,
            "episodes": 0,
            "action_type_nll": None,
            "action_type_accuracy": None,
            "expert_play_rate": None,
            "predicted_play_rate": None,
            "play_recall": None,
            "noop_recall": None,
            "played_card_slot_accuracy": None,
        }
    placement_actions = NUM_HAND_SLOTS * NUM_TILES
    expert_types = _action_types(expert_actions)
    chosen_types = _action_types(chosen_actions)
    expert_play = expert_actions < placement_actions
    chosen_play = chosen_actions < placement_actions
    expert_noop = expert_actions == placement_actions
    chosen_noop = chosen_actions == placement_actions
    selected_play = selected & expert_play
    selected_noop = selected & expert_noop
    return {
        "samples": count,
        "episodes": int(np.unique(episode_ids[selected]).size),
        "action_type_nll": float(np.mean(action_type_nll[selected])),
        "action_type_accuracy": float(
            np.mean(expert_types[selected] == chosen_types[selected])
        ),
        "expert_play_rate": float(np.mean(expert_play[selected])),
        "predicted_play_rate": float(np.mean(chosen_play[selected])),
        "play_recall": (
            float(np.mean(chosen_play[selected_play]))
            if np.any(selected_play)
            else None
        ),
        "noop_recall": (
            float(np.mean(chosen_noop[selected_noop]))
            if np.any(selected_noop)
            else None
        ),
        "played_card_slot_accuracy": (
            float(np.mean(chosen_types[selected_play] == expert_types[selected_play]))
            if np.any(selected_play)
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--checkpoint", action="append", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument(
        "--device", choices=("auto", "cpu", "mps", "cuda"), default="auto"
    )
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    corpus_path = resolve_path(args.corpus, must_exist=True)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    device = resolve_torch_device(args.device)
    _, arrays = load_corpus(corpus_path)
    contexts = _pressure_context_masks(
        arrays["entity_features"], arrays["entity_mask"]
    )
    results: list[dict[str, Any]] = []
    for checkpoint_value in args.checkpoint:
        checkpoint = resolve_path(checkpoint_value, must_exist=True)
        diagnostics: dict[str, np.ndarray] = {}
        overall, chosen = _checkpoint_metrics(
            checkpoint,
            arrays=arrays,
            device=device,
            decks_path=decks_path,
            diagnostics=diagnostics,
        )
        results.append(
            {
                "checkpoint": str(checkpoint),
                "checkpoint_update": overall["checkpoint_update"],
                "contexts": {
                    name: _context_metrics(
                        selected=selected,
                        episode_ids=arrays["episode_ids"],
                        expert_actions=arrays["expert_actions"],
                        chosen_actions=chosen,
                        action_type_nll=diagnostics["action_type_nll"],
                    )
                    for name, selected in contexts.items()
                },
            }
        )
    payload = {
        "schema_version": 1,
        "corpus": str(corpus_path),
        "device": str(device),
        "context_definition": {
            "tower_zone": "nearest detected enemy troop/building canonical_y <= 0.25",
            "own_half_pressure": (
                "nearest detected enemy troop/building canonical_y <= 0.50"
            ),
            "remote_or_clear": (
                "no detected enemy troop/building with canonical_y <= 0.50"
            ),
            "caveat": "visible-pressure proxy; not simulator aggro or exact DPS",
        },
        "results": results,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        output = resolve_path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
