#!/usr/bin/env python3
"""Create a complete-episode strategy/deck subset without row leakage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.direct_simple_behavior import load_direct_simple_behavior_corpus
from scripts.collect_hog26_direct_simple_behavior import (
    _atomic_json,
    _atomic_npz,
    file_sha256,
)
from scripts.train_hog26_actor_outcome import validate_outcome_corpus


def _requested(raw: str, *, label: str) -> tuple[str, ...]:
    values = tuple(value.strip() for value in raw.split(",") if value.strip())
    if not values or len(values) != len(set(values)):
        raise ValueError(f"{label} selection must be nonempty and unique")
    return values


def subset(
    input_path: Path,
    output_path: Path,
    report_path: Path,
    *,
    opponents: tuple[str, ...],
    decks: tuple[str, ...],
) -> dict[str, Any]:
    if output_path.exists() or report_path.exists():
        raise SystemExit("refusing to overwrite outcome subset artifacts")
    metadata, corpus = load_direct_simple_behavior_corpus(input_path)
    validate_outcome_corpus(metadata, corpus)
    available_opponents = tuple(str(value) for value in metadata["opponents"])
    available_decks = tuple(str(value) for value in metadata["opponent_decks"])
    if not set(opponents).issubset(available_opponents):
        raise ValueError("requested outcome subset contains an unknown opponent")
    if not set(decks).issubset(available_decks):
        raise ValueError("requested outcome subset contains an unknown deck")

    episode_opponents = np.asarray(
        corpus.episode_arrays["episode_opponent_indices"], dtype=np.int64
    )
    episode_decks = np.asarray(
        corpus.episode_arrays["episode_opponent_deck_indices"], dtype=np.int64
    )
    opponent_names = np.asarray(available_opponents, dtype=np.str_)[episode_opponents]
    deck_names = np.asarray(available_decks, dtype=np.str_)[episode_decks]
    selected_episodes = np.flatnonzero(
        np.isin(opponent_names, opponents) & np.isin(deck_names, decks)
    )
    expected = len(opponents) * len(decks) * 2 * int(metadata["episodes_per_seat"])
    if selected_episodes.size != expected:
        raise ValueError("outcome subset does not contain the complete cross product")

    lengths = np.diff(corpus.episode_offsets)[selected_episodes]
    row_parts = [
        np.arange(
            corpus.episode_offsets[episode],
            corpus.episode_offsets[episode + 1],
            dtype=np.int64,
        )
        for episode in selected_episodes
    ]
    selected_rows = np.concatenate(row_parts)
    arrays = {name: values[selected_rows].copy() for name, values in corpus.arrays.items()}
    offsets = np.concatenate(
        (np.zeros(1, dtype=np.int64), np.cumsum(lengths, dtype=np.int64))
    )

    old_streams = corpus.episode_stream_rows[selected_episodes]
    selected_streams = np.unique(old_streams)
    stream_remap = {int(old): new for new, old in enumerate(selected_streams.tolist())}
    stream_rows = np.asarray(
        [stream_remap[int(old)] for old in old_streams], dtype=np.int64
    )
    old_row_opponents = tuple(str(value) for value in metadata["row_opponents"])
    old_row_decks = tuple(str(value) for value in metadata["row_opponent_decks"])
    row_opponents = [old_row_opponents[int(stream)] for stream in selected_streams]
    row_decks = [old_row_decks[int(stream)] for stream in selected_streams]

    opponent_remap = {name: index for index, name in enumerate(opponents)}
    deck_remap = {name: index for index, name in enumerate(decks)}
    episode_arrays = {
        name: values[selected_episodes].copy()
        for name, values in corpus.episode_arrays.items()
    }
    episode_arrays["episode_opponent_indices"] = np.asarray(
        [opponent_remap[str(name)] for name in opponent_names[selected_episodes]],
        dtype=np.int64,
    )
    episode_arrays["episode_opponent_deck_indices"] = np.asarray(
        [deck_remap[str(name)] for name in deck_names[selected_episodes]],
        dtype=np.int64,
    )

    new_metadata = dict(metadata)
    new_metadata.update(
        {
            "source_corpus": str(input_path.resolve()),
            "source_corpus_sha256": file_sha256(input_path),
            "subset_contract": "complete-episode-strategy-deck-cross-product-v1",
            "opponents": list(opponents),
            "opponent_decks": list(decks),
            "row_opponents": row_opponents,
            "row_opponent_decks": row_decks,
            "episode_count": int(selected_episodes.size),
            "row_count": int(selected_rows.size),
        }
    )
    archive = {
        **arrays,
        "episode_offsets": offsets,
        "episode_stream_rows": stream_rows,
        "episode_ordinals": corpus.episode_ordinals[selected_episodes].copy(),
        "initial_hidden": corpus.initial_hidden[selected_episodes].copy(),
        "initial_cell": corpus.initial_cell[selected_episodes].copy(),
        **episode_arrays,
        "metadata_json": np.asarray(json.dumps(new_metadata, sort_keys=True)),
    }
    _atomic_npz(output_path, archive)
    report = {
        "schema": "clasher.hog26.outcome-corpus-subset.v1",
        "input": str(input_path.resolve()),
        "input_sha256": file_sha256(input_path),
        "output": str(output_path.resolve()),
        "output_sha256": file_sha256(output_path),
        "opponents": list(opponents),
        "opponent_decks": list(decks),
        "episodes": int(selected_episodes.size),
        "rows": int(selected_rows.size),
        "selected_source_episode_indices": selected_episodes.tolist(),
    }
    _atomic_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--opponents", required=True)
    parser.add_argument("--decks", required=True)
    args = parser.parse_args()
    report = subset(
        args.input,
        args.output,
        args.report,
        opponents=_requested(args.opponents, label="opponent"),
        decks=_requested(args.decks, label="deck"),
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
