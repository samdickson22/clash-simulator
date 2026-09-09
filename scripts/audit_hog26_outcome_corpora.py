#!/usr/bin/env python3
"""Audit complete-game Hog outcome corpora before value-model training."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter, defaultdict
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.direct_simple_behavior import load_direct_simple_behavior_corpus
from scripts.collect_hog26_direct_simple_behavior import _atomic_json, file_sha256
from scripts.hog26_scenario_clusters import episode_matchup_cluster
from scripts.train_hog26_actor_outcome import validate_outcome_corpus


def _counts(values: np.ndarray) -> dict[str, int]:
    names = {-1: "loss", 0: "draw", 1: "win"}
    counted = Counter(int(value) for value in values.tolist())
    return {names[value]: counted[value] for value in (-1, 0, 1)}


def _reached_phases(progress: np.ndarray) -> tuple[str, ...]:
    values = np.asarray(progress, dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("episode progress must be a finite vector")
    return tuple(
        phase
        for phase, lower, upper in (
            ("early", 0.0, 1.0 / 3.0),
            ("middle", 1.0 / 3.0, 2.0 / 3.0),
            ("late", 2.0 / 3.0, np.inf),
        )
        if bool(((values >= lower) & (values < upper)).any())
    )


def _validate_actor_contract(metadata: dict[str, Any]) -> None:
    backend = metadata.get("simulation_backend_metadata")
    if not isinstance(backend, dict):
        raise TypeError("outcome corpus lacks simulator contract metadata")
    mask = backend.get("public_action_mask_semantics")
    if not isinstance(mask, dict):
        raise TypeError("outcome corpus lacks public mask semantics")
    expected = {
        "canonical_lane_globals": True,
        "fresh_only": True,
        "public_action_mask_contract_version": 2,
    }
    if any(backend.get(key) != value for key, value in expected.items()):
        raise ValueError("outcome corpus actor contract is not current and causal")
    if mask.get("uses_critic") is not False:
        raise ValueError("outcome corpus public mask consumes critic state")
    if mask.get("uses_labels") is not False:
        raise ValueError("outcome corpus public mask consumes target labels")
    if mask.get("uses_simulator_legal_mask") is not False:
        raise ValueError("outcome corpus public mask consumes simulator truth")


def audit(
    paths: list[Path],
    *,
    expected_decks: set[str] | None = None,
    expected_opponents: set[str] | None = None,
    expected_supported_decks_sha256: str | None = None,
    expected_split: str | None = None,
    mmap_directory: Path | None = None,
) -> dict[str, Any]:
    if mmap_directory is None:
        with tempfile.TemporaryDirectory(prefix="hog26-full-audit-") as directory:
            return audit(
                paths, expected_decks=expected_decks, expected_opponents=expected_opponents,
                expected_supported_decks_sha256=expected_supported_decks_sha256,
                expected_split=expected_split, mmap_directory=Path(directory),
            )
    if not paths:
        raise ValueError("at least one outcome corpus is required")
    hashes = [file_sha256(path) for path in paths]
    if len(set(hashes)) != len(hashes):
        raise ValueError("outcome corpus inputs contain duplicate bytes")

    rows = 0
    episodes = 0
    seeds: set[int] = set()
    episode_outcomes: list[np.ndarray] = []
    phase_counts: Counter[str] = Counter()
    cells: defaultdict[tuple[str, str, int], Counter[int]] = defaultdict(Counter)
    corpus_reports: list[dict[str, Any]] = []
    natural_styles: set[str] = set()
    natural_decks: set[str] = set()
    phase_clusters: dict[str, defaultdict[str, set[int]]] = {
        phase: defaultdict(set) for phase in ("early", "middle", "late")
    }

    for index, (path, digest) in enumerate(zip(paths, hashes, strict=True)):
        metadata, corpus = load_direct_simple_behavior_corpus(
            path, mmap_directory=mmap_directory / f"corpus-{index}",
        )
        validate_outcome_corpus(metadata, corpus)
        _validate_actor_contract(metadata)
        if (
            expected_supported_decks_sha256 is not None
            and metadata.get("supported_decks_sha256")
            != expected_supported_decks_sha256
        ):
            raise ValueError("outcome corpus supported-deck authority mismatch")
        if expected_split is not None and metadata.get("opponent_deck_split") != (
            expected_split
        ):
            raise ValueError("outcome corpus deck split mismatch")
        seed = int(metadata["seed"])
        if seed in seeds:
            raise ValueError("outcome corpora reuse a collection seed")
        seeds.add(seed)

        offsets = corpus.episode_offsets
        stream_rows = corpus.episode_stream_rows
        ordinals = corpus.episode_ordinals
        outcomes = np.asarray(corpus.episode_arrays["episode_final_outcomes"])
        margins = np.asarray(
            corpus.episode_arrays["episode_terminal_tower_margins"]
        )
        seats = np.asarray(corpus.episode_arrays["episode_learner_players"])
        expected_per_stream = int(metadata.get("episodes_per_seat", 1))
        stream_count = len(metadata["row_opponents"])
        if corpus.episode_count != stream_count * expected_per_stream:
            raise ValueError("corpus episode count does not cover every stream")
        if not np.array_equal(
            np.bincount(stream_rows, minlength=stream_count),
            np.full(stream_count, expected_per_stream),
        ):
            raise ValueError("corpus stream episode counts are incomplete")
        for stream in range(stream_count):
            if not np.array_equal(
                np.sort(ordinals[stream_rows == stream]),
                np.arange(expected_per_stream),
            ):
                raise ValueError("corpus stream ordinals are not contiguous")

        starts = np.asarray(corpus.arrays["episode_starts"], dtype=np.bool_)
        dones = np.asarray(corpus.arrays["dones"], dtype=np.bool_)
        winners = np.asarray(corpus.arrays["terminal_winners"], dtype=np.int64)
        for episode, (begin, end) in enumerate(pairwise(offsets)):
            if (
                not starts[begin]
                or starts[begin + 1 : end].any()
                or not dones[end - 1]
                or dones[begin : end - 1].any()
            ):
                raise ValueError("episode boundaries are not exact")
            winner = int(winners[end - 1])
            actor = int(seats[episode])
            expected = 0 if winner < 0 else (1 if winner == actor else -1)
            if int(outcomes[episode]) != expected:
                raise ValueError("episode outcome disagrees with terminal winner")

        progress = np.asarray(corpus.arrays["global_features"][:, 0])
        phase_counts["early"] += int((progress < 1.0 / 3.0).sum())
        phase_counts["middle"] += int(
            ((progress >= 1.0 / 3.0) & (progress < 2.0 / 3.0)).sum()
        )
        phase_counts["late"] += int((progress >= 2.0 / 3.0).sum())

        opponents = tuple(str(value) for value in metadata["opponents"])
        episode_opponents = np.asarray(
            corpus.episode_arrays["episode_opponent_indices"], dtype=np.int64
        )
        if "episode_opponent_deck_indices" in corpus.episode_arrays:
            decks = tuple(str(value) for value in metadata["opponent_decks"])
            episode_decks = np.asarray(
                corpus.episode_arrays["episode_opponent_deck_indices"],
                dtype=np.int64,
            )
            for opponent_index, deck_index, seat, outcome in zip(
                episode_opponents, episode_decks, seats, outcomes, strict=True
            ):
                style = opponents[int(opponent_index)]
                deck = decks[int(deck_index)]
                natural_styles.add(style)
                natural_decks.add(deck)
                cells[(style, deck, int(seat))][int(outcome)] += 1
            for episode, (begin, end) in enumerate(pairwise(offsets)):
                style = opponents[int(episode_opponents[episode])]
                deck = decks[int(episode_decks[episode])]
                cluster = episode_matchup_cluster(metadata, corpus, episode)
                for phase in _reached_phases(progress[begin:end]):
                    phase_clusters[phase][cluster].add(int(outcomes[episode]))

        rows += corpus.row_count
        episodes += corpus.episode_count
        episode_outcomes.append(outcomes)
        corpus_reports.append(
            {
                "path": str(path.resolve()),
                "sha256": digest,
                "seed": seed,
                "rows": corpus.row_count,
                "episodes": corpus.episode_count,
                "outcomes": _counts(outcomes),
                "margin_minimum": float(margins.min()),
                "margin_maximum": float(margins.max()),
                "supported_decks_sha256": metadata.get("supported_decks_sha256"),
                "opponent_deck_split": metadata.get("opponent_deck_split"),
            }
        )

    combined_outcomes = np.concatenate(episode_outcomes)
    if expected_decks is not None and natural_decks != expected_decks:
        raise ValueError("outcome corpus does not exactly cover expected decks")
    if expected_opponents is not None and natural_styles != expected_opponents:
        raise ValueError("outcome corpus does not exactly cover expected opponents")
    return {
        "schema": "clasher.hog26.outcome-corpus-audit.v1",
        "status": "passed",
        "corpora": corpus_reports,
        "corpus_count": len(paths),
        "rows": rows,
        "episodes": episodes,
        "outcomes": _counts(combined_outcomes),
        "phase_rows": dict(sorted(phase_counts.items())),
        "natural_diversity": {
            "opponent_styles": sorted(natural_styles),
            "opponent_decks": sorted(natural_decks),
            "style_deck_seat_cells": len(cells),
            "cells_with_both_decisive_outcomes": sum(
                counter[-1] > 0 and counter[1] > 0 for counter in cells.values()
            ),
            "phase_matchup_clusters": {
                phase: {
                    "clusters": len(cluster_outcomes),
                    "with_loss": sum(
                        -1 in values for values in cluster_outcomes.values()
                    ),
                    "with_win": sum(
                        1 in values for values in cluster_outcomes.values()
                    ),
                    "with_both": sum(
                        {-1, 1}.issubset(values)
                        for values in cluster_outcomes.values()
                    ),
                }
                for phase, cluster_outcomes in phase_clusters.items()
            },
        },
        "cell_outcomes": {
            f"{style}|{deck}|seat{seat}": _counts(
                np.asarray(
                    [value for value, count in counter.items() for _ in range(count)],
                    dtype=np.int8,
                )
            )
            for (style, deck, seat), counter in sorted(cells.items())
        },
        "checks": {
            "unique_hashes": True,
            "unique_seeds": True,
            "complete_stream_coverage": True,
            "contiguous_stream_ordinals": True,
            "exact_episode_boundaries": True,
            "exact_actor_relative_terminal_labels": True,
            "finite_outcomes_and_margins": True,
            "critic_inputs_absent": True,
            "current_causal_actor_contract": True,
            "label_independent_public_mask_v2": True,
            "expected_decks_exact": expected_decks is None
            or natural_decks == expected_decks,
            "expected_opponents_exact": expected_opponents is None
            or natural_styles == expected_opponents,
            "supported_deck_authority_exact": (
                expected_supported_decks_sha256 is None
                or all(
                    report.get("supported_decks_sha256")
                    == expected_supported_decks_sha256
                    for report in corpus_reports
                )
            ),
            "expected_split_exact": expected_split is None
            or all(
                report.get("opponent_deck_split") == expected_split
                for report in corpus_reports
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--supported-decks-path", type=Path)
    parser.add_argument("--expected-deck-split")
    parser.add_argument("--expected-opponent", action="append", default=[])
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite outcome corpus audit")
    expected_decks: set[str] | None = None
    expected_supported_decks_sha256: str | None = None
    if args.supported_decks_path is not None:
        if args.expected_deck_split is None:
            raise SystemExit("--supported-decks-path requires --expected-deck-split")
        payload = json.loads(args.supported_decks_path.read_text())
        rows = payload.get("decks")
        if not isinstance(rows, list):
            raise SystemExit("supported-deck artifact has no deck rows")
        expected_decks = {
            str(row["name"])
            for row in rows
            if isinstance(row, dict)
            and row.get("split") == args.expected_deck_split
            and isinstance(row.get("name"), str)
        }
        if not expected_decks:
            raise SystemExit("supported-deck artifact has no expected split rows")
        expected_supported_decks_sha256 = file_sha256(args.supported_decks_path)
    report = audit(
        args.corpus,
        expected_decks=expected_decks,
        expected_opponents=set(args.expected_opponent) or None,
        expected_supported_decks_sha256=expected_supported_decks_sha256,
        expected_split=args.expected_deck_split,
    )
    _atomic_json(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
