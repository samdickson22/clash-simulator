#!/usr/bin/env python3
"""Collect complete Hog games with undiscounted actor-relative outcome labels."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.complete_outcomes import attach_complete_outcomes
from clasher.rl.direct_simple_behavior import CompleteEpisodeBuilder
from clasher.rl.simple_pytorch_backend import (
    DEFAULT_SIMPLE_SUPPORTED_DECKS,
    DEFAULT_SIMPLE_TOKEN_VOCABULARY,
    SimplePytorchTrainingCollector,
    load_simple_supported_decks,
)
from scripts.collect_hog26_direct_simple_behavior import (
    _atomic_json,
    _atomic_npz,
    _card_counts,
    _league_schedule,
    file_sha256,
    paired_row_opponents,
)
from scripts.evaluate_hog26_simple_policy import load_model

SCHEMA = "clasher.hog26.complete-outcome-corpus.v1"


def _outcome_counts(values: np.ndarray) -> dict[str, int]:
    labels = {-1: "loss", 0: "draw", 1: "win"}
    counts = Counter(int(value) for value in values.tolist())
    return {labels[key]: int(counts[key]) for key in (-1, 0, 1)}


def crossed_opponent_rows(
    opponents: tuple[str, ...], opponent_decks: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if len(opponents) < 2 or not opponent_decks:
        raise ValueError("crossed outcome collection needs opponents and decks")
    rows = tuple(
        (opponent, deck)
        for deck in opponent_decks
        for opponent in opponents
        for _seat in range(2)
    )
    return tuple(row[0] for row in rows), tuple(row[1] for row in rows)


def collect(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite complete-outcome artifacts")
    if args.episodes_per_seat < 1 or not 1 <= args.chunk_steps <= 128:
        raise ValueError("invalid complete-outcome collection size")
    opponents = tuple(value.strip() for value in args.opponents.split(",") if value)
    requested_decks = tuple(
        value.strip() for value in args.opponent_decks.split(",") if value.strip()
    )
    supported_decks_path = Path(args.supported_decks_path)
    artifact = load_simple_supported_decks(supported_decks_path)
    if requested_decks:
        if any(deck not in artifact.deck_names for deck in requested_decks):
            raise ValueError("crossed outcome collection contains an unknown deck")
        if "Hog 2.6 Cycle" in requested_decks:
            raise ValueError("opponent deck schedule must exclude the learner deck")
        row_opponents, row_decks = crossed_opponent_rows(opponents, requested_decks)
    else:
        row_opponents = paired_row_opponents(opponents)
        row_decks = ()
    device = torch.device(args.device)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    model, observation_builder = load_model(args.checkpoint, device)
    collector = SimplePytorchTrainingCollector(
        model=model,
        builder=observation_builder,
        batch_size=len(row_opponents),
        device=device,
        decision_interval=8,
        gamma=0.995,
        supported_decks_path=supported_decks_path,
        typed_vocabulary_path=DEFAULT_SIMPLE_TOKEN_VOCABULARY,
        mirror_match=False,
        opponent_mode="league",
        opponent_league_schedule=_league_schedule(opponents),
        learner_deck_name="Hog 2.6 Cycle",
        opponent_deck_name_schedule=row_decks,
    )
    collector.policy.deterministic = True
    state = model.initial_state(len(row_opponents), device=device)
    builder = CompleteEpisodeBuilder(
        stream_count=len(row_opponents),
        episodes_per_stream=args.episodes_per_seat,
        reset_hidden=state[0].detach().cpu().numpy(),
        reset_cell=state[1].detach().cpu().numpy(),
        extra_transition_keys=("terminal_winners", "next_global_features"),
    )
    chunks = 0
    started = time.monotonic()
    while not builder.complete:
        if chunks >= args.episodes_per_seat * 16 + 16:
            raise RuntimeError("complete-outcome collection exceeded terminal guard")
        arrays, state, *_ = collector.collect(
            args.chunk_steps,
            state,
            include_outcome_labels=True,
        )
        builder.add_rollout(arrays)
        chunks += 1
        print(
            json.dumps(
                {
                    "chunks": chunks,
                    "completed_by_stream": builder.completed_by_stream.tolist(),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                },
                sort_keys=True,
            ),
            flush=True,
        )
    corpus = builder.finalize()
    learner_players = collector.learner_players.detach().cpu().numpy()
    opponent_index_by_stream = np.asarray(
        [opponents.index(value) for value in row_opponents], dtype=np.int64
    )
    episode_arrays = {
        "episode_opponent_indices": opponent_index_by_stream[
            corpus.episode_stream_rows
        ],
        "episode_learner_players": learner_players[corpus.episode_stream_rows],
    }
    actual_decks = tuple(collector.metadata.opponent_deck_names)
    opponent_decks = tuple(dict.fromkeys(actual_decks))
    deck_index_by_stream = np.asarray(
        [opponent_decks.index(value) for value in actual_decks], dtype=np.int64
    )
    episode_arrays["episode_opponent_deck_indices"] = deck_index_by_stream[
        corpus.episode_stream_rows
    ]
    corpus = attach_complete_outcomes(replace(corpus, episode_arrays=episode_arrays))
    checkpoint_payload = torch.load(
        args.checkpoint, map_location="cpu", weights_only=False
    )
    token_names = tuple(checkpoint_payload["token_names"])
    metadata = {
        "schema": SCHEMA,
        "outcome_source": "natural-strategy-games",
        "seed": args.seed,
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": file_sha256(args.checkpoint),
        "supported_decks_path": str(supported_decks_path.resolve()),
        "supported_decks_sha256": artifact.sha256,
        "supported_deck_profile_sha256": artifact.support_profile_sha256,
        "token_names": list(token_names),
        "opponents": list(opponents),
        "row_opponents": list(row_opponents),
        "opponent_decks": list(opponent_decks),
        "row_opponent_decks": list(actual_decks),
        "strategy_deck_cross_product": bool(requested_decks),
        "episodes_per_seat": args.episodes_per_seat,
        "chunk_steps": args.chunk_steps,
        "episode_count": corpus.episode_count,
        "row_count": corpus.row_count,
        "complete_episodes_only": True,
        "initial_recurrent_state": "exact-model-reset-state-per-episode",
        "label_authority": (
            "undiscounted-terminal-winner-and-post-action-public-tower-fractions-v1"
        ),
        "actor_input_excludes_outcome_labels": True,
        "simulation_backend_metadata": collector.checkpoint_metadata(),
    }
    archive = {
        **corpus.arrays,
        "episode_offsets": corpus.episode_offsets,
        "episode_stream_rows": corpus.episode_stream_rows,
        "episode_ordinals": corpus.episode_ordinals,
        "initial_hidden": corpus.initial_hidden,
        "initial_cell": corpus.initial_cell,
        **corpus.episode_arrays,
        "metadata_json": np.asarray(json.dumps(metadata, sort_keys=True)),
    }
    _atomic_npz(args.output, archive)
    outcomes = corpus.episode_arrays["episode_final_outcomes"]
    margins = corpus.episode_arrays["episode_terminal_tower_margins"]
    report = {
        **metadata,
        "output": str(args.output.resolve()),
        "output_sha256": file_sha256(args.output),
        "elapsed_seconds": time.monotonic() - started,
        "chunks": chunks,
        "episode_outcomes": _outcome_counts(outcomes),
        "terminal_tower_margin": {
            "minimum": float(margins.min()),
            "mean": float(margins.mean()),
            "maximum": float(margins.max()),
        },
        "card_counts": _card_counts(
            corpus.arrays["actions"], corpus.arrays["hand_ids"], token_names
        ),
        "episode_lengths": {
            "minimum": int(np.diff(corpus.episode_offsets).min()),
            "median": float(np.median(np.diff(corpus.episode_offsets))),
            "maximum": int(np.diff(corpus.episode_offsets).max()),
        },
    }
    _atomic_json(args.report, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--episodes-per-seat", type=int, default=1)
    parser.add_argument("--chunk-steps", type=int, default=64)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument(
        "--supported-decks-path",
        type=Path,
        default=DEFAULT_SIMPLE_SUPPORTED_DECKS,
    )
    parser.add_argument(
        "--opponents",
        default=(
            "balanced,bridge-pressure,reactive-defense,slow-push,spell-control,"
            "split-lane,random"
        ),
    )
    parser.add_argument(
        "--opponent-decks",
        default="",
        help="comma-separated explicit decks crossed with every opponent style",
    )
    result = collect(parser.parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
