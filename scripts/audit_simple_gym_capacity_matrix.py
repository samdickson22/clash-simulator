#!/usr/bin/env python3
"""Audit peak resident capacity across every ordered supported-deck matchup."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clasher.data import CardDataLoader
from clasher.rl.simple_pytorch_backend import (
    _typed_lookups,
    load_current_client_typed_vocabulary,
    load_simple_supported_decks,
)
from clasher.torch_sim.simple_cuda_graph import SimpleCudaGraphRunner
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.validate_simple_full_matches import select_actions


@dataclass(frozen=True)
class Pair:
    index: int
    player0_deck: int
    player1_deck: int


def ordered_pairs(deck_count: int) -> tuple[Pair, ...]:
    if deck_count < 1:
        raise ValueError("deck_count must be positive")
    return tuple(
        Pair(index=index, player0_deck=left, player1_deck=right)
        for index, (left, right) in enumerate(
            (left, right)
            for left in range(deck_count)
            for right in range(deck_count)
        )
    )


def _pair_rows(
    decks: tuple[tuple[str, ...], ...], pairs: tuple[Pair, ...]
) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    return tuple((decks[pair.player0_deck], decks[pair.player1_deck]) for pair in pairs)


def _chunk_digest(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _run_chunk(
    args: argparse.Namespace,
    *,
    setup: Any,
    entity_lookup: torch.Tensor,
    hand_lookup: torch.Tensor,
    decks: tuple[tuple[str, ...], ...],
    pairs: tuple[Pair, ...],
) -> list[dict[str, Any]]:
    runtime = setup.create_runtime(
        _pair_rows(decks, pairs),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        canonical_lane_globals=True,
        max_entities=args.runtime_max_entities,
        max_effects=args.runtime_max_effects,
    )
    observation = runtime.observe()
    example_actions = select_actions(observation.legal_mask, "first-legal")
    stepper = SimpleCudaGraphRunner(runtime, example_actions)
    peak_entities = runtime.state.active.sum(dim=1, dtype=torch.int64)
    peak_effects = runtime.effects.active.sum(dim=1, dtype=torch.int64)
    invalid_active_rows = torch.zeros(runtime.batch_size, dtype=torch.bool, device=runtime.device)
    previous_done = torch.zeros_like(invalid_active_rows)
    last = None
    for tick in range(args.maximum_ticks):
        actions = select_actions(observation.legal_mask, "first-legal")
        last = stepper.step_tick(actions)
        active_before = ~previous_done
        invalid_active_rows |= active_before & ~(
            last.committed & (last.native_ticks == 1)
        )
        peak_entities = torch.maximum(
            peak_entities,
            runtime.state.active.sum(dim=1, dtype=torch.int64),
        )
        peak_effects = torch.maximum(
            peak_effects,
            runtime.effects.active.sum(dim=1, dtype=torch.int64),
        )
        # CUDA Graph outputs reuse fixed storage on every replay. Preserve the
        # prior done mask so the next iteration can distinguish terminal rows
        # from active rows without observing an overwritten view.
        previous_done = last.done.clone()
        observation = last.observation
        if (tick + 1) % args.done_poll_interval == 0 and bool(last.done.all().item()):
            break
    if last is None:
        raise RuntimeError("capacity audit executed no ticks")
    if not bool(last.done.all().item()):
        raise RuntimeError("capacity audit chunk did not reach terminal states")
    invalid = invalid_active_rows.cpu().tolist()
    peaks_entities = peak_entities.cpu().tolist()
    peaks_effects = peak_effects.cpu().tolist()
    final_ticks = runtime.state.tick.cpu().tolist()
    winners = last.winner.cpu().tolist()
    rows: list[dict[str, Any]] = []
    for local_index, pair in enumerate(pairs):
        rows.append(
            {
                "pair_index": pair.index,
                "player0_deck": pair.player0_deck,
                "player1_deck": pair.player1_deck,
                "peak_entities": int(peaks_entities[local_index]),
                "peak_effects": int(peaks_effects[local_index]),
                "final_tick": int(final_ticks[local_index]),
                "winner": int(winners[local_index]),
                "invalid_active_row": bool(invalid[local_index]),
            }
        )
    return rows


def audit(args: argparse.Namespace) -> dict[str, Any]:
    if args.device != "cuda" or not torch.cuda.is_available():
        raise ValueError("capacity matrix requires CUDA Graph execution")
    if min(
        args.chunk_size,
        args.runtime_max_entities,
        args.runtime_max_effects,
        args.candidate_max_entities,
        args.candidate_max_effects,
        args.maximum_ticks,
        args.done_poll_interval,
        args.repetitions,
    ) < 1:
        raise ValueError("capacity audit sizes must be positive")
    if args.candidate_max_entities > args.runtime_max_entities:
        raise ValueError("candidate entity capacity exceeds diagnostic runtime")
    if args.candidate_max_effects > args.runtime_max_effects:
        raise ValueError("candidate effect capacity exceeds diagnostic runtime")

    artifact = load_simple_supported_decks(args.supported_decks_path)
    vocabulary = load_current_client_typed_vocabulary(args.typed_vocabulary_path)
    loader = CardDataLoader()
    setup = compile_standard_simple_setup(
        loader,
        artifact.public_cards,
        device=torch.device("cuda"),
        canonical_lane_globals=True,
    )
    entity_lookup, hand_lookup = _typed_lookups(setup, loader, vocabulary)
    pairs = ordered_pairs(len(artifact.decks))
    repetition_rows: list[list[dict[str, Any]]] = []
    repetition_digests: list[str] = []
    for _repetition in range(args.repetitions):
        rows: list[dict[str, Any]] = []
        for start in range(0, len(pairs), args.chunk_size):
            chunk = pairs[start : start + args.chunk_size]
            rows.extend(
                _run_chunk(
                    args,
                    setup=setup,
                    entity_lookup=entity_lookup,
                    hand_lookup=hand_lookup,
                    decks=artifact.decks,
                    pairs=chunk,
                )
            )
        rows.sort(key=lambda row: int(row["pair_index"]))
        repetition_rows.append(rows)
        repetition_digests.append(_chunk_digest(rows))
    deterministic = len(set(repetition_digests)) == 1
    rows = repetition_rows[0]
    maximum_entities = max(int(row["peak_entities"]) for row in rows)
    maximum_effects = max(int(row["peak_effects"]) for row in rows)
    invalid_rows = [row for row in rows if bool(row["invalid_active_row"])]
    candidate_admitted = (
        deterministic
        and not invalid_rows
        and maximum_entities <= args.candidate_max_entities
        and maximum_effects <= args.candidate_max_effects
    )
    return {
        "schema_version": 1,
        "scope": "all ordered supported-deck pairs under deterministic first-legal play",
        "execution_mode": "cuda-graph",
        "deck_count": len(artifact.decks),
        "ordered_pairs": len(pairs),
        "chunk_size": args.chunk_size,
        "repetitions": args.repetitions,
        "runtime_capacity": {
            "max_entities": args.runtime_max_entities,
            "max_effects": args.runtime_max_effects,
        },
        "candidate_capacity": {
            "max_entities": args.candidate_max_entities,
            "max_effects": args.candidate_max_effects,
        },
        "observed": {
            "maximum_entities": maximum_entities,
            "maximum_effects": maximum_effects,
            "invalid_active_rows": len(invalid_rows),
        },
        "acceptance": {
            "deterministic": deterministic,
            "all_active_rows_native_and_committed": not invalid_rows,
            "candidate_capacity_admitted": candidate_admitted,
        },
        "repetition_digests": repetition_digests,
        "deck_names": [list(deck) for deck in artifact.decks],
        "rows": rows,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cuda",), default="cuda")
    parser.add_argument("--chunk-size", type=int, default=128)
    parser.add_argument("--runtime-max-entities", type=int, default=64)
    parser.add_argument("--runtime-max-effects", type=int, default=64)
    parser.add_argument("--candidate-max-entities", type=int, default=48)
    parser.add_argument("--candidate-max-effects", type=int, default=64)
    parser.add_argument("--maximum-ticks", type=int, default=6_000)
    parser.add_argument("--done-poll-interval", type=int, default=16)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument(
        "--supported-decks-path",
        default="training_decks/simple_gym_supported_v1.json",
    )
    parser.add_argument(
        "--typed-vocabulary-path",
        default="reports/current_client_youtube_stable_vocabulary_v1.json",
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = audit(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not result["acceptance"]["candidate_capacity_admitted"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
