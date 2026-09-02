#!/usr/bin/env python3
"""Evaluate one policy deterministically in the resident Simple PyTorch Gym."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import gc
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import numpy as np
import torch
from numpy.typing import NDArray

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.simple_pytorch_backend import (
    DEFAULT_SIMPLE_SUPPORTED_DECKS,
    DEFAULT_SIMPLE_TOKEN_VOCABULARY,
    SimpleLeagueSpec,
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


def batched_row_opponents(
    opponents: tuple[str, ...], games: int
) -> tuple[str, ...]:
    if len(opponents) < 2:
        raise ValueError("batched evaluation requires at least two opponents")
    if games < 2 or games % 2:
        raise ValueError("batched evaluation games must be a positive even count")
    return tuple(
        opponents[(row // 2) % len(opponents)]
        for row in range(games * len(opponents))
    )


def _collect_terminal_rows(
    model: ClasherPolicy,
    collector: SimplePytorchTrainingCollector,
    *,
    row_opponents: tuple[str, ...],
    device: torch.device,
    chunk_steps: int,
    token_names: tuple[str, ...],
) -> tuple[list[dict[str, Any]], NDArray[np.int64], NDArray[np.int64]]:
    row_count = len(row_opponents)
    learner_players = collector.learner_players.detach().cpu().numpy()
    if learner_players.shape != (row_count,):
        raise ValueError("collector learner-seat projection changed")
    records: list[dict[str, Any] | None] = [None] * row_count
    row_placements: NDArray[np.int64] = np.zeros(row_count, dtype=np.int64)
    row_decisions: NDArray[np.int64] = np.zeros(row_count, dtype=np.int64)
    row_card_counts: list[Counter[str]] = [Counter() for _row in range(row_count)]
    row_action_digests = [hashlib.sha256() for _row in range(row_count)]
    state = model.initial_state(row_count, device=device)
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
        hand_ids = np.asarray(arrays["hand_ids"], dtype=np.int64)
        if dones.shape != winners.shape or dones.shape != actions.shape:
            raise ValueError("simple evaluation rollout projections changed")
        for row in range(row_count):
            if records[row] is not None:
                continue
            terminal = np.flatnonzero(dones[row])
            used = steps if terminal.size == 0 else int(terminal[0]) + 1
            row_actions = actions[row, :used]
            row_placements[row] += int(np.count_nonzero(row_actions < 2304))
            row_decisions[row] += used
            row_action_digests[row].update(
                row_actions.astype("<i8", copy=False).tobytes()
            )
            for step in np.flatnonzero(row_actions < 2304).tolist():
                slot = int(row_actions[step]) // 576
                token = int(hand_ids[row, step, slot])
                if not 0 <= token < len(token_names):
                    raise ValueError("evaluation action references an unknown hand token")
                row_card_counts[row][token_names[token]] += 1
            if terminal.size:
                end = int(terminal[0])
                winner = int(winners[row, end])
                learner = int(learner_players[row])
                outcome = (
                    "win" if winner == learner else "draw" if winner < 0 else "loss"
                )
                records[row] = {
                    "row": row,
                    "opponent": row_opponents[row],
                    "learner_player": learner,
                    "terminal_decision": decision_offset + end,
                    "winner": winner,
                    "outcome": outcome,
                    "placements": int(row_placements[row]),
                    "decisions": int(row_decisions[row]),
                    "card_counts": dict(sorted(row_card_counts[row].items())),
                    "action_sha256": row_action_digests[row].hexdigest(),
                }
        decision_offset += steps
        print(
            json.dumps(
                {
                    "decision_offset": decision_offset,
                    "completed_rows": sum(record is not None for record in records),
                    "total_rows": row_count,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    if any(record is None for record in records):
        missing = [index for index, record in enumerate(records) if record is None]
        raise ValueError(f"evaluation rows did not terminate: {missing}")
    return (
        [record for record in records if record is not None],
        row_placements,
        row_decisions,
    )


def _summarize_opponent(
    *,
    opponent: str,
    seed: int,
    row_opponents: tuple[str, ...],
    records: list[dict[str, Any]],
    row_placements: NDArray[np.int64],
    row_decisions: NDArray[np.int64],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    indices = [
        index for index, row_opponent in enumerate(row_opponents)
        if row_opponent == opponent
    ]
    completed = [records[index] for index in indices]
    games = len(completed)
    wins = sum(record["outcome"] == "win" for record in completed)
    losses = sum(record["outcome"] == "loss" for record in completed)
    draws = sum(record["outcome"] == "draw" for record in completed)
    placements = int(row_placements[indices].sum())
    decisions = int(row_decisions[indices].sum())
    card_counts: Counter[str] = Counter()
    for record in completed:
        card_counts.update(record["card_counts"])
    return {
        "opponent": opponent,
        "seed": seed,
        "games": games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": wins / games,
        "placement_rate": placements / max(1, decisions),
        "card_counts": dict(sorted(card_counts.items())),
        "simulation_backend_metadata": metadata,
        "records": completed,
    }


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
    row_opponents = (opponent,) * games
    records, row_placements, row_decisions = _collect_terminal_rows(
        model,
        collector,
        row_opponents=row_opponents,
        device=device,
        chunk_steps=chunk_steps,
        token_names=tuple(builder.token_names),
    )
    result = _summarize_opponent(
        opponent=opponent,
        seed=seed,
        row_opponents=row_opponents,
        records=records,
        row_placements=row_placements,
        row_decisions=row_decisions,
        metadata=collector.checkpoint_metadata(),
    )
    del collector
    gc.collect()
    if device.type == "mps":
        torch.mps.empty_cache()
    return result


def evaluate_opponents_batched(
    model: ClasherPolicy,
    builder: StructuredObservationBuilder,
    *,
    opponents: tuple[str, ...],
    games: int,
    device: torch.device,
    chunk_steps: int,
    seed: int,
) -> list[dict[str, Any]]:
    np.random.seed(seed)
    torch.manual_seed(seed)
    row_opponents = batched_row_opponents(opponents, games)
    schedule: tuple[SimpleLeagueSpec, ...] = tuple(
        ("random", None) if opponent == "random" else ("strategy", opponent)
        for opponent in opponents
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
        opponent_league_schedule=schedule,
        learner_deck_name="Hog 2.6 Cycle",
    )
    collector.policy.deterministic = True
    records, row_placements, row_decisions = _collect_terminal_rows(
        model,
        collector,
        row_opponents=row_opponents,
        device=device,
        chunk_steps=chunk_steps,
        token_names=tuple(builder.token_names),
    )
    metadata = collector.checkpoint_metadata()
    rows = [
        _summarize_opponent(
            opponent=opponent,
            seed=seed,
            row_opponents=row_opponents,
            records=records,
            row_placements=row_placements,
            row_decisions=row_decisions,
            metadata=metadata,
        )
        for opponent in opponents
    ]
    del collector
    gc.collect()
    if device.type == "mps":
        torch.mps.empty_cache()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--seed", type=int, default=1247001)
    parser.add_argument("--chunk-steps", type=int, default=32)
    parser.add_argument("--opponent", action="append", dest="opponents")
    parser.add_argument(
        "--sequential-opponents",
        action="store_true",
        help="diagnostic fallback; default batches all requested opponents",
    )
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
    rows = (
        [
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
        if args.sequential_opponents or len(opponents) == 1
        else evaluate_opponents_batched(
            model,
            builder,
            opponents=tuple(opponents),
            games=args.games,
            device=device,
            chunk_steps=args.chunk_steps,
            seed=args.seed,
        )
    )
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
        "opponent_execution": (
            "sequential" if args.sequential_opponents or len(opponents) == 1 else "batched-league"
        ),
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
