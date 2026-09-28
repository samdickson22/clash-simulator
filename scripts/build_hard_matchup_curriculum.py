from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from clasher.paths import resolve_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_curriculum(paths: list[Path]) -> dict[str, Any]:
    grouped: dict[tuple[tuple[str, ...], tuple[str, ...]], dict[str, Any]] = {}
    strategy_losses: defaultdict[str, int] = defaultdict(int)
    total_games = 0
    for path in paths:
        strategy = path.stem
        games = json.loads(path.read_text(encoding="utf-8"))
        total_games += len(games)
        for game in games:
            if game["outcome"] != "loss":
                continue
            learner = tuple(game["candidate_deck"])
            opponent = tuple(game["opponent_deck"])
            key = (learner, opponent)
            crown_deficit = max(
                1, int(game["opponent_crowns"]) - int(game["candidate_crowns"])
            )
            entry = grouped.setdefault(
                key,
                {
                    "learner_cards": list(learner),
                    "opponent_cards": list(opponent),
                    "weight": 0.0,
                    "source_losses": [],
                },
            )
            # Every observed loss receives one unit; larger crown deficits receive
            # proportionally more sampling mass without making a single game
            # dominate the curriculum.
            entry["weight"] += float(1 + crown_deficit)
            entry["source_losses"].append(
                {
                    "strategy": strategy,
                    "matchup_seed": int(game["matchup_seed"]),
                    "candidate_player": int(game["candidate_player"]),
                    "crown_deficit": crown_deficit,
                }
            )
            strategy_losses[strategy] += 1

    matchups = sorted(
        grouped.values(),
        key=lambda row: (
            -float(row["weight"]),
            tuple(row["learner_cards"]),
            tuple(row["opponent_cards"]),
        ),
    )
    if not matchups:
        raise ValueError("no candidate losses found in supplied game records")
    return {
        "schema_version": 1,
        "metadata": {
            "selection": "candidate losses only",
            "weighting": "1 + crown deficit",
            "source_games": total_games,
            "source_losses": sum(strategy_losses.values()),
            "unique_matchups": len(matchups),
            "losses_by_strategy": dict(sorted(strategy_losses.items())),
            "sources": [
                {"path": str(path), "sha256": _sha256(path)} for path in paths
            ],
        },
        "matchups": matchups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a weighted exact-matchup curriculum from eval losses"
    )
    parser.add_argument("--games-json", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    paths = [resolve_path(path, must_exist=True) for path in args.games_json]
    output = resolve_path(args.output)
    payload = build_curriculum(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["metadata"], sort_keys=True))


if __name__ == "__main__":
    main()
