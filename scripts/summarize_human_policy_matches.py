"""Summarize recorded human-versus-policy matches with a fail-closed protocol."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


def _deck_signature(cards: object) -> tuple[str, ...]:
    if not isinstance(cards, list):
        raise TypeError("recorded deck must be a list")
    signature = tuple(sorted(str(card) for card in cards))
    if len(signature) != 8 or len(set(signature)) != 8:
        raise ValueError("recorded deck must contain eight unique cards")
    return signature


def _score_interval(score: float, games: int) -> tuple[float, float]:
    """Wilson-style interval for win=1, draw=.5, loss=0 match scores."""
    if games <= 0:
        return 0.0, 1.0
    z = 1.959963984540054
    rate = score / games
    denominator = 1.0 + z * z / games
    center = (rate + z * z / (2.0 * games)) / denominator
    radius = (
        z
        * math.sqrt(
            max(0.0, rate * (1.0 - rate) / games + z * z / (4.0 * games * games))
        )
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def summarize_human_matches(
    records: list[dict[str, Any]],
    *,
    required_games: int,
    required_distinct_decks: int,
    required_score_rate: float,
    required_human_ladder_label: str = "mid-ladder",
) -> dict[str, Any]:
    if required_games <= 0 or required_distinct_decks <= 0:
        raise ValueError("required games and decks must be positive")
    if not 0.0 <= required_score_rate <= 1.0:
        raise ValueError("required score rate must be between zero and one")
    if not required_human_ladder_label:
        raise ValueError("required human ladder label must be non-empty")
    seen: set[tuple[object, ...]] = set()
    outcomes: Counter[str] = Counter()
    seats: dict[int, Counter[str]] = {0: Counter(), 1: Counter()}
    checkpoint_hashes: set[str] = set()
    human_labels: set[str] = set()
    ladder_labels: set[str] = set()
    metadata_complete = True
    pacing_valid = True
    human_decks: set[tuple[str, ...]] = set()
    candidate_decks: set[tuple[str, ...]] = set()
    matchup_signatures: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    matchup_candidate_seats: dict[
        tuple[tuple[str, ...], tuple[str, ...]], Counter[int]
    ] = {}
    for row in records:
        outcome = str(row.get("candidate_outcome", ""))
        if outcome not in {"win", "loss", "draw"}:
            raise ValueError(f"invalid candidate outcome {outcome!r}")
        human_player = int(row.get("human_player", -1))
        candidate_player = int(row.get("candidate_player", -1))
        if human_player not in (0, 1) or candidate_player != 1 - human_player:
            raise ValueError("human and candidate seats must be opposite")
        key = (
            row.get("checkpoint_sha256"),
            row.get("session_seed"),
            row.get("match_number"),
            human_player,
        )
        if key in seen:
            raise ValueError(f"duplicate human match key {key!r}")
        seen.add(key)
        human_deck = _deck_signature(row.get("human_deck"))
        candidate_deck = _deck_signature(row.get("candidate_deck"))
        human_decks.add(human_deck)
        candidate_decks.add(candidate_deck)
        matchup = (human_deck, candidate_deck)
        matchup_signatures.add(matchup)
        matchup_candidate_seats.setdefault(matchup, Counter())[candidate_player] += 1
        outcomes[outcome] += 1
        seats[candidate_player][outcome] += 1
        checkpoint_hashes.add(str(row.get("checkpoint_sha256", "")))
        human_label = str(row.get("human_label") or "")
        ladder_label = str(row.get("human_ladder_label") or "")
        if human_label:
            human_labels.add(human_label)
        else:
            metadata_complete = False
        if ladder_label:
            ladder_labels.add(ladder_label)
        else:
            metadata_complete = False
        if (
            row.get("pacing_mode") != "wall_clock_logic_ticks"
            or row.get("speed_locked") is not True
            or not math.isclose(
                float(row.get("logic_tick_seconds", -1.0)),
                0.05,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            pacing_valid = False

    games = len(records)
    wins = outcomes["win"]
    losses = outcomes["loss"]
    draws = outcomes["draw"]
    score = wins + 0.5 * draws
    score_rate = score / max(1, games)
    ci_low, ci_high = _score_interval(score, games)
    seat_games = {
        player_id: sum(seats[player_id].values()) for player_id in (0, 1)
    }
    gates = {
        "single_checkpoint": len(checkpoint_hashes) == 1
        and all(
            len(value) == 64
            and all(character in "0123456789abcdef" for character in value.lower())
            for value in checkpoint_hashes
        ),
        "human_metadata_present": metadata_complete,
        "required_human_ladder_cohort": ladder_labels
        == {required_human_ladder_label},
        "realtime_pacing": pacing_valid,
        "minimum_games": games >= required_games,
        "balanced_candidate_seats": abs(seat_games[0] - seat_games[1]) <= 1,
        "balanced_matchup_seats": bool(matchup_candidate_seats)
        and all(
            counts[0] > 0 and counts[0] == counts[1]
            for counts in matchup_candidate_seats.values()
        ),
        "minimum_human_decks": len(human_decks) >= required_distinct_decks,
        "minimum_candidate_decks": len(candidate_decks) >= required_distinct_decks,
        "minimum_matchups": len(matchup_signatures) >= required_distinct_decks,
        "score_rate": score_rate >= required_score_rate,
        "score_ci95_low": ci_low >= required_score_rate,
    }
    return {
        "schema_version": 2,
        "games": games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "score_rate": score_rate,
        "score_ci95_low": ci_low,
        "score_ci95_high": ci_high,
        "candidate_seats": {
            str(player_id): {
                "games": seat_games[player_id],
                "wins": seats[player_id]["win"],
                "losses": seats[player_id]["loss"],
                "draws": seats[player_id]["draw"],
            }
            for player_id in (0, 1)
        },
        "checkpoint_sha256": (
            next(iter(checkpoint_hashes)) if len(checkpoint_hashes) == 1 else None
        ),
        "human_labels": sorted(human_labels),
        "human_ladder_labels": sorted(ladder_labels),
        "distinct_human_decks": len(human_decks),
        "distinct_candidate_decks": len(candidate_decks),
        "distinct_matchups": len(matchup_signatures),
        "matchup_seat_counts": [
            {
                "human_deck": list(human_deck),
                "candidate_deck": list(candidate_deck),
                "candidate_seat_0": matchup_candidate_seats[
                    (human_deck, candidate_deck)
                ][0],
                "candidate_seat_1": matchup_candidate_seats[
                    (human_deck, candidate_deck)
                ][1],
            }
            for human_deck, candidate_deck in sorted(matchup_candidate_seats)
        ],
        "required_games": required_games,
        "required_distinct_decks": required_distinct_decks,
        "required_score_rate": required_score_rate,
        "required_human_ladder_label": required_human_ladder_label,
        "gates": gates,
        "passes_competitive_gate": all(gates.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--required-games", type=int, default=40)
    parser.add_argument("--required-distinct-decks", type=int, default=8)
    parser.add_argument("--required-score-rate", type=float, default=0.5)
    parser.add_argument(
        "--required-human-ladder-label",
        default="mid-ladder",
    )
    parser.add_argument("--fail-on-gate", action="store_true")
    args = parser.parse_args()
    records = [
        json.loads(line)
        for line in args.records.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    payload = summarize_human_matches(
        records,
        required_games=args.required_games,
        required_distinct_decks=args.required_distinct_decks,
        required_score_rate=args.required_score_rate,
        required_human_ladder_label=args.required_human_ladder_label,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, sort_keys=True))
    if args.fail_on_gate and not payload["passes_competitive_gate"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
