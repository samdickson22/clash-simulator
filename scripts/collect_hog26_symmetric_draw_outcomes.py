#!/usr/bin/env python3
"""Collect exact mirrored self-play trajectories for the rare draw class."""

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
)
from scripts.collect_hog26_direct_simple_behavior import (
    _atomic_json,
    _atomic_npz,
    _card_counts,
    file_sha256,
)
from scripts.evaluate_hog26_simple_policy import load_model

SCHEMA = "clasher.hog26.complete-outcome-corpus.v1"


def collect(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() or args.report.exists():
        raise SystemExit("refusing to overwrite symmetric-draw artifacts")
    if args.battles < 1 or args.episodes_per_battle < 1:
        raise ValueError("symmetric draw counts must be positive")
    device = torch.device(args.device)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    model, observation_builder = load_model(args.checkpoint, device)
    collector = SimplePytorchTrainingCollector(
        model=model,
        builder=observation_builder,
        batch_size=args.battles,
        device=device,
        decision_interval=8,
        gamma=0.995,
        supported_decks_path=DEFAULT_SIMPLE_SUPPORTED_DECKS,
        typed_vocabulary_path=DEFAULT_SIMPLE_TOKEN_VOCABULARY,
        mirror_match=True,
        opponent_mode="selfplay",
        selfplay_deck_name="Hog 2.6 Cycle",
    )
    collector.policy.deterministic = True
    stream_count = 2 * args.battles
    state = model.initial_state(stream_count, device=device)
    builder = CompleteEpisodeBuilder(
        stream_count=stream_count,
        episodes_per_stream=args.episodes_per_battle,
        reset_hidden=state[0].detach().cpu().numpy(),
        reset_cell=state[1].detach().cpu().numpy(),
        extra_transition_keys=("terminal_winners", "next_global_features"),
    )
    chunks = 0
    started = time.monotonic()
    while not builder.complete:
        if chunks >= args.episodes_per_battle * 16 + 16:
            raise RuntimeError("symmetric draw collection exceeded terminal guard")
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
    episode_arrays = {
        "episode_opponent_indices": np.zeros(corpus.episode_count, dtype=np.int64),
        "episode_learner_players": corpus.episode_stream_rows % 2,
        "episode_battle_indices": corpus.episode_stream_rows // 2,
    }
    corpus = attach_complete_outcomes(replace(corpus, episode_arrays=episode_arrays))
    checkpoint_payload = torch.load(
        args.checkpoint, map_location="cpu", weights_only=False
    )
    token_names = tuple(checkpoint_payload["token_names"])
    metadata = {
        "schema": SCHEMA,
        "outcome_source": "controlled-symmetric-draws",
        "seed": args.seed,
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": file_sha256(args.checkpoint),
        "token_names": list(token_names),
        "opponents": ["symmetric-selfplay"],
        "row_opponents": ["symmetric-selfplay"] * stream_count,
        "episodes_per_seat": args.episodes_per_battle,
        "chunk_steps": args.chunk_steps,
        "episode_count": corpus.episode_count,
        "physical_battle_count": args.battles * args.episodes_per_battle,
        "row_count": corpus.row_count,
        "complete_episodes_only": True,
        "initial_recurrent_state": "exact-model-reset-state-per-episode",
        "label_authority": (
            "undiscounted-terminal-winner-and-post-action-public-tower-fractions-v1"
        ),
        "actor_input_excludes_outcome_labels": True,
        "symmetric_draw_source": True,
        "paired_actor_views_share_physical_battle": True,
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
    outcome_counts = Counter(
        int(value) for value in corpus.episode_arrays["episode_final_outcomes"].tolist()
    )
    report = {
        **metadata,
        "output": str(args.output.resolve()),
        "output_sha256": file_sha256(args.output),
        "elapsed_seconds": time.monotonic() - started,
        "chunks": chunks,
        "episode_outcomes": {
            "loss": outcome_counts[-1],
            "draw": outcome_counts[0],
            "win": outcome_counts[1],
        },
        "all_physical_battles_drew": outcome_counts[0] == corpus.episode_count,
        "card_counts": _card_counts(
            corpus.arrays["actions"], corpus.arrays["hand_ids"], token_names
        ),
    }
    _atomic_json(args.report, report)
    if not report["all_physical_battles_drew"]:
        raise RuntimeError("symmetric self-play did not produce only exact draws")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--battles", type=int, default=4)
    parser.add_argument("--episodes-per-battle", type=int, default=1)
    parser.add_argument("--chunk-steps", type=int, default=64)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    result = collect(parser.parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
