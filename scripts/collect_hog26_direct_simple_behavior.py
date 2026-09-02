#!/usr/bin/env python3
"""Collect complete frozen-teacher Hog trajectories from the Simple Gym."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from collections import Counter
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.direct_simple_behavior import CompleteEpisodeBuilder
from clasher.rl.simple_pytorch_backend import (
    DEFAULT_SIMPLE_SUPPORTED_DECKS,
    DEFAULT_SIMPLE_TOKEN_VOCABULARY,
    SimpleLeagueSpec,
    SimplePytorchTrainingCollector,
)
from clasher.rl.strategy_bots import STRATEGY_NAMES
from scripts.evaluate_hog26_simple_policy import load_model

SCHEMA = "clasher.hog26.direct-simple-behavior.v2"
PLACEMENT_ACTIONS = NUM_HAND_SLOTS * NUM_TILES


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def paired_row_opponents(opponents: tuple[str, ...]) -> tuple[str, ...]:
    if len(opponents) < 2:
        raise ValueError("direct behavior collection requires at least two opponents")
    if len(set(opponents)) != len(opponents):
        raise ValueError("behavior opponents must be unique")
    if any(value != "random" and value not in STRATEGY_NAMES for value in opponents):
        raise ValueError("behavior collection contains an unknown opponent")
    return tuple(opponent for opponent in opponents for _seat in range(2))


def _league_schedule(opponents: tuple[str, ...]) -> tuple[SimpleLeagueSpec, ...]:
    schedule: list[SimpleLeagueSpec] = []
    for opponent in opponents:
        schedule.append(
            ("random", None) if opponent == "random" else ("strategy", opponent)
        )
    return tuple(schedule)


def _atomic_npz(path: Path, arrays: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".npz",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
    try:
        np.savez_compressed(temporary, **arrays)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".json",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _card_counts(
    actions: np.ndarray,
    hand_ids: np.ndarray,
    token_names: tuple[str, ...],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    placement_rows = np.flatnonzero(actions < PLACEMENT_ACTIONS)
    for row in placement_rows.tolist():
        slot = int(actions[row]) // NUM_TILES
        token = int(hand_ids[row, slot])
        if not 0 <= token < len(token_names):
            raise ValueError("behavior hand token is outside the checkpoint vocabulary")
        counts[token_names[token]] += 1
    return dict(sorted(counts.items()))


def _validate_play_probabilities(
    actions: np.ndarray, probabilities: np.ndarray
) -> None:
    if probabilities.shape != actions.shape:
        raise ValueError("teacher hazard factors do not align with behavior actions")
    if not np.isfinite(probabilities).all() or bool(
        ((probabilities < 0.0) | (probabilities >= 1.0)).any()
    ):
        raise ValueError("teacher hazard factors must be finite probabilities")


def _audit_hazard_reproduction(
    *,
    actions: np.ndarray,
    probabilities: np.ndarray,
    action_masks: np.ndarray,
    episode_offsets: np.ndarray,
    initial_hidden: np.ndarray,
    threshold: float,
) -> dict[str, int]:
    """Reproduce every frozen-teacher play from its exported accumulator input."""

    if not 0.0 < threshold < 1.0:
        raise ValueError("teacher hazard threshold must be in (0, 1)")
    _validate_play_probabilities(actions, probabilities)
    if initial_hidden.ndim != 2 or initial_hidden.shape[0] + 1 != len(episode_offsets):
        raise ValueError("initial hidden states do not align with episodes")
    mismatches = 0
    rows = 0
    for episode, (begin, end) in enumerate(pairwise(episode_offsets)):
        accumulator = float(initial_hidden[episode, -1])
        for row in range(int(begin), int(end)):
            accumulator = 1.0 - (1.0 - accumulator) * (1.0 - float(probabilities[row]))
            can_play = bool(action_masks[row, :PLACEMENT_ACTIONS].any())
            predicted = accumulator >= threshold and can_play
            actual = bool(actions[row] < PLACEMENT_ACTIONS)
            mismatches += int(predicted != actual)
            rows += 1
            if predicted:
                accumulator = 0.0
    if mismatches:
        raise ValueError(
            f"teacher hazard factors fail exact action reproduction: {mismatches}/{rows}"
        )
    return {"rows": rows, "mismatches": mismatches}


def collect(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite direct behavior artifacts")
    if args.episodes_per_seat < 1 or args.chunk_steps < 1:
        raise ValueError("episode and chunk counts must be positive")
    if args.chunk_steps > 128:
        raise ValueError("chunk steps must not exceed 128")
    opponents = tuple(value.strip() for value in args.opponents.split(",") if value)
    row_opponents = paired_row_opponents(opponents)
    device = torch.device(args.device)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    model, builder = load_model(args.checkpoint, device)
    if not model.config.play_hazard_enabled:
        raise ValueError(
            "the frozen behavior teacher must expose calibrated hazard timing"
        )
    collector = SimplePytorchTrainingCollector(
        model=model,
        builder=builder,
        batch_size=len(row_opponents),
        device=device,
        decision_interval=8,
        gamma=0.995,
        supported_decks_path=DEFAULT_SIMPLE_SUPPORTED_DECKS,
        typed_vocabulary_path=DEFAULT_SIMPLE_TOKEN_VOCABULARY,
        mirror_match=False,
        opponent_mode="league",
        opponent_league_schedule=_league_schedule(opponents),
        learner_deck_name="Hog 2.6 Cycle",
    )
    collector.policy.deterministic = True
    state = model.initial_state(len(row_opponents), device=device)
    reset_hidden = state[0].detach().cpu().numpy()
    reset_cell = state[1].detach().cpu().numpy()
    episode_builder = CompleteEpisodeBuilder(
        stream_count=len(row_opponents),
        episodes_per_stream=args.episodes_per_seat,
        reset_hidden=reset_hidden,
        reset_cell=reset_cell,
        extra_transition_keys=("play_hazard_probabilities",),
    )
    max_chunks = args.episodes_per_seat * 16 + 16
    chunks = 0
    started = time.monotonic()
    while not episode_builder.complete:
        if chunks >= max_chunks:
            raise RuntimeError("direct behavior collection exceeded its terminal guard")
        arrays, state, *_continuation = collector.collect(
            args.chunk_steps,
            state,
            include_terminal_winners=True,
            include_policy_factors=True,
        )
        episode_builder.add_rollout(arrays)
        chunks += 1
        print(
            json.dumps(
                {
                    "chunks": chunks,
                    "completed_by_stream": episode_builder.completed_by_stream.tolist(),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                },
                sort_keys=True,
            ),
            flush=True,
        )
    corpus = episode_builder.finalize()
    checkpoint_payload = torch.load(
        args.checkpoint, map_location="cpu", weights_only=False
    )
    token_names = tuple(checkpoint_payload["token_names"])
    learner_players = collector.learner_players.detach().cpu().numpy()
    opponent_index_by_stream = np.asarray(
        [opponents.index(value) for value in row_opponents], dtype=np.int64
    )
    episode_opponent_indices = opponent_index_by_stream[corpus.episode_stream_rows]
    episode_learner_players = learner_players[corpus.episode_stream_rows]
    metadata = {
        "schema": SCHEMA,
        "seed": args.seed,
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": file_sha256(args.checkpoint),
        "token_names": list(token_names),
        "opponents": list(opponents),
        "row_opponents": list(row_opponents),
        "episodes_per_seat": args.episodes_per_seat,
        "chunk_steps": args.chunk_steps,
        "episode_count": corpus.episode_count,
        "row_count": corpus.row_count,
        "complete_episodes_only": True,
        "initial_recurrent_state": "exact-model-reset-state-per-episode",
        "teacher_factor_authority": "original-one-step-policy-boundary",
        "simulation_backend_metadata": collector.checkpoint_metadata(),
    }
    archive = {
        **corpus.arrays,
        "episode_offsets": corpus.episode_offsets,
        "episode_stream_rows": corpus.episode_stream_rows,
        "episode_ordinals": corpus.episode_ordinals,
        "episode_opponent_indices": episode_opponent_indices,
        "episode_learner_players": episode_learner_players,
        "initial_hidden": corpus.initial_hidden,
        "initial_cell": corpus.initial_cell,
        "metadata_json": np.asarray(json.dumps(metadata, sort_keys=True)),
    }
    _atomic_npz(args.output, archive)
    actions = corpus.arrays["actions"]
    play_probabilities = corpus.arrays["play_hazard_probabilities"]
    _validate_play_probabilities(actions, play_probabilities)
    hazard_audit = _audit_hazard_reproduction(
        actions=actions,
        probabilities=play_probabilities,
        action_masks=corpus.arrays["action_masks"],
        episode_offsets=corpus.episode_offsets,
        initial_hidden=corpus.initial_hidden,
        threshold=model.config.play_hazard_threshold,
    )
    report = {
        **metadata,
        "output": str(args.output.resolve()),
        "output_sha256": file_sha256(args.output),
        "elapsed_seconds": time.monotonic() - started,
        "chunks": chunks,
        "placements": int(np.count_nonzero(actions < PLACEMENT_ACTIONS)),
        "placement_rate": float(np.mean(actions < PLACEMENT_ACTIONS)),
        "play_hazard_probability": {
            "minimum": float(np.min(play_probabilities)),
            "mean": float(np.mean(play_probabilities)),
            "maximum": float(np.max(play_probabilities)),
        },
        "teacher_hazard_reproduction": hazard_audit,
        "card_counts": _card_counts(actions, corpus.arrays["hand_ids"], token_names),
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
        "--opponents",
        default="balanced,bridge-pressure,reactive-defense,slow-push,spell-control,split-lane,random",
    )
    result = collect(parser.parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
