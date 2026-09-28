from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from typing import Any

import numpy as np
from evaluate_recurrent_corpus import (
    _action_types,
    _checkpoint_metrics,
    _placement_tolerance,
)

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.imitation import load_corpus
from clasher.rl.train_recurrent import resolve_torch_device

FREQUENCY_BINS: tuple[tuple[str, int, int | None], ...] = (
    ("unseen", 0, 0),
    ("one_to_9", 1, 9),
    ("ten_to_99", 10, 99),
    ("hundred_to_999", 100, 999),
    ("thousand_plus", 1000, None),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate action accuracy by expert-card frequency in a reference corpus"
        )
    )
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--frequency-reference-corpus", required=True)
    parser.add_argument("--checkpoint", action="append", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument(
        "--device", choices=("auto", "cpu", "mps", "cuda"), default="auto"
    )
    parser.add_argument("--json-out", default=None)
    return parser.parse_args()


def _expert_card_ids(arrays: dict[str, np.ndarray]) -> np.ndarray:
    actions = arrays["expert_actions"]
    hand_ids = arrays["hand_ids"]
    card_ids = np.full(actions.shape, -1, dtype=np.int64)
    placements = actions < NUM_HAND_SLOTS * NUM_TILES
    rows = np.flatnonzero(placements)
    slots = actions[placements] // NUM_TILES
    card_ids[placements] = hand_ids[rows, slots]
    return card_ids


def _expert_card_counts(
    arrays: dict[str, np.ndarray], *, num_tokens: int
) -> np.ndarray:
    card_ids = _expert_card_ids(arrays)
    return np.bincount(card_ids[card_ids >= 0], minlength=num_tokens)


def _frequency_metrics(
    *,
    arrays: dict[str, np.ndarray],
    chosen_actions: np.ndarray,
    reference_counts: np.ndarray,
    token_names: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    expert_actions = arrays["expert_actions"]
    card_ids = _expert_card_ids(arrays)
    expert_types = _action_types(expert_actions)
    chosen_types = _action_types(chosen_actions)
    correct_type = expert_types == chosen_types
    correct_slot = (
        (card_ids >= 0)
        & (chosen_actions < NUM_HAND_SLOTS * NUM_TILES)
        & correct_type
    )
    within_two = _placement_tolerance(
        chosen_actions, expert_actions, radius=2.0
    )
    frequencies = np.zeros(card_ids.shape, dtype=np.int64)
    valid = card_ids >= 0
    frequencies[valid] = reference_counts[card_ids[valid]]
    result: dict[str, dict[str, Any]] = {}
    for name, lower, upper in FREQUENCY_BINS:
        selected = valid & (frequencies >= lower)
        if upper is not None:
            selected &= frequencies <= upper
        selected_ids = np.unique(card_ids[selected])
        sample_count = int(np.sum(selected))
        correct_slot_count = int(np.sum(correct_slot & selected))
        result[name] = {
            "samples": sample_count,
            "cards": [token_names[int(card_id)] for card_id in selected_ids],
            "exact_accuracy": (
                float(np.mean(chosen_actions[selected] == expert_actions[selected]))
                if sample_count
                else 0.0
            ),
            "action_type_accuracy": (
                float(np.mean(correct_type[selected])) if sample_count else 0.0
            ),
            "correct_slot_placements": correct_slot_count,
            "within_two_tile_accuracy": (
                float(np.sum(within_two & selected) / correct_slot_count)
                if correct_slot_count
                else 0.0
            ),
        }
    return result


def main() -> None:
    args = parse_args()
    device = resolve_torch_device(args.device)
    corpus_path = resolve_path(args.corpus, must_exist=True)
    reference_path = resolve_path(args.frequency_reference_corpus, must_exist=True)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    metadata, arrays = load_corpus(corpus_path)
    reference_metadata, reference_arrays = load_corpus(reference_path)
    if metadata.token_names != reference_metadata.token_names:
        raise ValueError("evaluation and frequency-reference token names must match")
    reference_counts = _expert_card_counts(
        reference_arrays, num_tokens=len(metadata.token_names)
    )

    results: list[dict[str, Any]] = []
    for value in args.checkpoint:
        metrics, chosen = _checkpoint_metrics(
            resolve_path(value, must_exist=True),
            arrays=arrays,
            device=device,
            decks_path=decks_path,
        )
        metrics["card_frequency_bins"] = _frequency_metrics(
            arrays=arrays,
            chosen_actions=chosen,
            reference_counts=reference_counts,
            token_names=metadata.token_names,
        )
        results.append(metrics)
    payload = {
        "schema_version": 1,
        "corpus": str(corpus_path),
        "frequency_reference_corpus": str(reference_path),
        "device": str(device),
        "results": results,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        output_path = resolve_path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
