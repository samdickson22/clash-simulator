"""Summarize per-archetype outcomes from an eval --games-json-out artifact."""

from __future__ import annotations

import argparse
import json

from clasher.paths import resolve_path
from clasher.rl.deck_benchmark import deck_archetype_index, summarize_deck_records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games-json", required=True)
    parser.add_argument("--deck-pool", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    games_path = resolve_path(args.games_json, must_exist=True)
    pool_path = resolve_path(args.deck_pool, must_exist=True)
    records = json.loads(games_path.read_text(encoding="utf-8"))
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    summary = {
        "schema_version": 1,
        "games_json": str(games_path),
        "deck_pool": str(pool_path),
        **summarize_deck_records(
            records,
            archetypes_by_deck=deck_archetype_index(pool.get("decks", ())),
        ),
    }
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
