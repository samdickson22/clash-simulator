"""Audit realized opponent sampling for exact counterfactual game IDs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _load_pool(path: Path) -> tuple[dict[tuple[str, ...], str], dict[str, float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    deck_to_archetype: dict[tuple[str, ...], str] = {}
    archetype_weights: defaultdict[str, float] = defaultdict(float)
    for index, row in enumerate(payload.get("decks", [])):
        cards = tuple(sorted(str(card) for card in row.get("cards", [])))
        if len(cards) != 8:
            raise ValueError(f"deck {index} must contain exactly eight cards")
        archetype = str(row.get("archetype", "")).strip()
        if not archetype:
            raise ValueError(f"deck {index} has no archetype")
        weight = float(row.get("sampling_weight", 1.0))
        if weight <= 0.0:
            raise ValueError(f"deck {index} has a non-positive sampling weight")
        previous = deck_to_archetype.setdefault(cards, archetype)
        if previous != archetype:
            raise ValueError(
                f"deck {index} belongs to both {previous!r} and {archetype!r}"
            )
        archetype_weights[archetype] += weight
    if not deck_to_archetype:
        raise ValueError("opponent pool contains no decks")
    return deck_to_archetype, dict(archetype_weights)


def audit_sampling(
    *,
    shards: Path,
    opponent_pool: Path,
    games: int,
    maximum_total_variation: float,
    schema: str,
) -> dict[str, Any]:
    if games <= 0:
        raise ValueError("games must be positive")
    if maximum_total_variation < 0.0:
        raise ValueError("maximum total variation must be non-negative")

    deck_to_archetype, archetype_weights = _load_pool(opponent_pool)
    total_weight = sum(archetype_weights.values())
    expected = {
        archetype: weight / total_weight
        for archetype, weight in sorted(archetype_weights.items())
    }
    observed: Counter[str] = Counter()
    seats: Counter[int] = Counter()
    seen: set[int] = set()
    for report_path in sorted(shards.glob("game_*.json")):
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        rows = payload.get("games", [])
        if len(rows) != 1:
            raise ValueError(f"{report_path} must contain exactly one game")
        row = rows[0]
        game_id = int(row["game"])
        if game_id < 0 or game_id >= games:
            continue
        if game_id in seen:
            raise ValueError(f"duplicate game id {game_id}")
        seen.add(game_id)
        controlled_player = int(row["controlled_player"])
        if controlled_player not in (0, 1):
            raise ValueError(f"game {game_id} has invalid controlled player")
        decks = row.get("decks", [])
        if len(decks) != 2:
            raise ValueError(f"game {game_id} must contain exactly two decks")
        opponent_signature = tuple(
            sorted(str(card) for card in decks[1 - controlled_player])
        )
        try:
            archetype = deck_to_archetype[opponent_signature]
        except KeyError as exc:
            raise ValueError(f"game {game_id} opponent deck is outside the pool") from exc
        observed[archetype] += 1
        seats[controlled_player] += 1

    required_ids = set(range(games))
    if seen != required_ids:
        missing = sorted(required_ids - seen)
        extra = sorted(seen - required_ids)
        raise ValueError(
            f"game ids are incomplete: missing={missing[:8]} extra={extra[:8]}"
        )
    observed_probability = {
        archetype: observed[archetype] / games for archetype in expected
    }
    total_variation = 0.5 * sum(
        abs(observed_probability[archetype] - expected[archetype])
        for archetype in expected
    )
    pearson = sum(
        (observed[archetype] - games * probability) ** 2
        / (games * probability)
        for archetype, probability in expected.items()
    )
    return {
        "schema": schema,
        "passed": total_variation <= maximum_total_variation,
        "games": games,
        "game_ids": [0, games - 1],
        "candidate_seats": {str(seat): seats[seat] for seat in (0, 1)},
        "expected_archetype_probability": expected,
        "observed_archetype_games": {
            archetype: observed[archetype] for archetype in expected
        },
        "observed_archetype_probability": observed_probability,
        "total_variation": total_variation,
        "maximum_total_variation": maximum_total_variation,
        "pearson_chi_square": pearson,
        "pearson_degrees_of_freedom": len(expected) - 1,
        "promotion_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=Path, required=True)
    parser.add_argument("--opponent-pool", type=Path, required=True)
    parser.add_argument("--games", type=int, required=True)
    parser.add_argument("--maximum-total-variation", type=float, required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_sampling(
        shards=args.shards,
        opponent_pool=args.opponent_pool,
        games=args.games,
        maximum_total_variation=args.maximum_total_variation,
        schema=args.schema,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not result["passed"]:
        raise SystemExit("realized weighted sampling exceeded the declared bound")


if __name__ == "__main__":
    main()
