#!/usr/bin/env python3
"""Evaluate one policy deterministically in the resident Simple PyTorch Gym."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
import torch
from numpy.typing import NDArray

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.simple_pytorch_backend import (
    DEFAULT_SIMPLE_SUPPORTED_DECKS,
    DEFAULT_SIMPLE_TOKEN_VOCABULARY,
    SimplePytorchTrainingCollector,
    load_current_client_typed_vocabulary,
)
from clasher.rl.strategy_bots import STRATEGY_NAMES
from clasher.rl.structured_obs import StructuredObservationBuilder

SCHEMA = "clasher.hog26.simple-policy-evaluation.v1"
OPPONENTS = (*STRATEGY_NAMES, "random")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluation_seed(base_seed: int, opponent: str) -> int:
    return base_seed + 1009 * OPPONENTS.index(opponent)


def load_model(
    checkpoint: Path, device: torch.device
) -> tuple[ClasherPolicy, StructuredObservationBuilder]:
    payload = torch.load(checkpoint, map_location=device, weights_only=False)
    config = PolicyConfig.from_dict(payload["model_config"])
    vocabulary = load_current_client_typed_vocabulary()
    if tuple(payload["token_names"]) != vocabulary.token_names:
        raise ValueError("evaluation checkpoint vocabulary is not current-client exact")
    builder = StructuredObservationBuilder(
        decks_path="decks.json",
        token_names=vocabulary.token_names,
        max_entities=config.max_entities,
        card_semantics_version=config.card_semantics_version,
        canonical_lane_globals=True,
    )
    model = ClasherPolicy(config, builder.card_stat_features).to(device)
    model.load_state_dict(payload["model_state_dict"], strict=True)
    model.eval()
    return model, builder


def evaluate_opponent(
    model: ClasherPolicy,
    builder: StructuredObservationBuilder,
    *,
    opponent: str,
    games: int,
    device: torch.device,
    chunk_steps: int,
    seed: int,
) -> dict[str, Any]:
    np.random.seed(seed)
    torch.manual_seed(seed)
    mode: Literal["random", "strategy"] = (
        "random" if opponent == "random" else "strategy"
    )
    collector = SimplePytorchTrainingCollector(
        model=model,
        builder=builder,
        batch_size=games,
        device=device,
        decision_interval=8,
        gamma=0.995,
        supported_decks_path=DEFAULT_SIMPLE_SUPPORTED_DECKS,
        typed_vocabulary_path=DEFAULT_SIMPLE_TOKEN_VOCABULARY,
        mirror_match=False,
        opponent_mode=mode,
        opponent_strategy=None if mode == "random" else opponent,
        learner_deck_name="Hog 2.6 Cycle",
    )
    collector.policy.deterministic = True
    learner_players = collector.learner_players.detach().cpu().numpy()
    records: list[dict[str, Any] | None] = [None] * games
    row_placements: NDArray[np.int64] = np.zeros(games, dtype=np.int64)
    row_decisions: NDArray[np.int64] = np.zeros(games, dtype=np.int64)
    state = model.initial_state(games, device=device)
    decision_offset = 0
    while decision_offset < 760 and any(record is None for record in records):
        steps = min(chunk_steps, 760 - decision_offset)
        arrays, state, *_rest = collector.collect(
            steps,
            state,
            include_terminal_winners=True,
        )
        dones = np.asarray(arrays["dones"], dtype=np.bool_)
        winners = np.asarray(arrays["terminal_winners"], dtype=np.int64)
        actions = np.asarray(arrays["actions"], dtype=np.int64)
        if dones.shape != winners.shape or dones.shape != actions.shape:
            raise ValueError("simple evaluation rollout projections changed")
        for row in range(games):
            if records[row] is not None:
                continue
            terminal = np.flatnonzero(dones[row])
            used = steps if terminal.size == 0 else int(terminal[0]) + 1
            row_actions = actions[row, :used]
            row_placements[row] += int(np.count_nonzero(row_actions < 2304))
            row_decisions[row] += used
            if terminal.size:
                end = int(terminal[0])
                winner = int(winners[row, end])
                learner = int(learner_players[row])
                outcome = (
                    "win" if winner == learner else "draw" if winner < 0 else "loss"
                )
                records[row] = {
                    "row": row,
                    "learner_player": learner,
                    "terminal_decision": decision_offset + end,
                    "winner": winner,
                    "outcome": outcome,
                    "placements": int(row_placements[row]),
                    "decisions": int(row_decisions[row]),
                }
        decision_offset += steps
    if any(record is None for record in records):
        missing = [index for index, record in enumerate(records) if record is None]
        raise ValueError(f"evaluation rows did not terminate: {missing}")
    completed = [record for record in records if record is not None]
    wins = sum(record["outcome"] == "win" for record in completed)
    losses = sum(record["outcome"] == "loss" for record in completed)
    draws = sum(record["outcome"] == "draw" for record in completed)
    placements = int(row_placements.sum())
    decisions = int(row_decisions.sum())
    result = {
        "opponent": opponent,
        "seed": seed,
        "games": games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": wins / games,
        "placement_rate": placements / max(1, decisions),
        "records": completed,
    }
    del collector
    gc.collect()
    if device.type == "mps":
        torch.mps.empty_cache()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--seed", type=int, default=1247001)
    parser.add_argument("--chunk-steps", type=int, default=32)
    parser.add_argument("--opponent", action="append", dest="opponents")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite simple policy evaluation")
    if args.games < 2 or args.games % 2:
        raise ValueError("evaluation games must be a positive even count")
    if args.chunk_steps < 1 or args.chunk_steps > 128:
        raise ValueError("chunk steps must be in [1, 128]")
    opponents = args.opponents or list(OPPONENTS)
    if any(value != "random" and value not in STRATEGY_NAMES for value in opponents):
        raise ValueError("evaluation contains an unknown opponent")
    if len(set(opponents)) != len(opponents):
        raise ValueError("evaluation opponents must be unique")
    device = torch.device(args.device)
    model, builder = load_model(args.checkpoint, device)
    rows = [
        evaluate_opponent(
            model,
            builder,
            opponent=opponent,
            games=args.games,
            device=device,
            chunk_steps=args.chunk_steps,
            seed=evaluation_seed(args.seed, opponent),
        )
        for opponent in opponents
    ]
    payload = {
        "schema": SCHEMA,
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": file_sha256(args.checkpoint),
        "device": str(device),
        "deterministic_policy": True,
        "seeded_environment": True,
        "base_seed": args.seed,
        "games_per_opponent": args.games,
        "chunk_steps": args.chunk_steps,
        "rows": rows,
        "total": {
            "games": sum(row["games"] for row in rows),
            "wins": sum(row["wins"] for row in rows),
            "losses": sum(row["losses"] for row in rows),
            "draws": sum(row["draws"] for row in rows),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["total"], sort_keys=True))


if __name__ == "__main__":
    main()
