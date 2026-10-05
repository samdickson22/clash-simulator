"""Win counts with Wilson intervals and behaviour statistics for one evaluated checkpoint.

Reads evaluation/<name>/*.json (+ .decisions.json traces) and writes
results/evaluation-<name>.json. `--drop-traces` deletes the bulky decision traces
after they are summarized.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPO = HERE.parents[3]
COST = {"Archers": 3, "Cannon": 3, "DarkPrince": 4, "Fireball": 4, "Giant": 5, "Goblins": 2, "HogRider": 4,
        "IceGolem": 2, "IceSpirit": 1, "Knight": 3, "Log": 2, "Musketeer": 4, "Prince": 5, "Skeletons": 1,
        "Tesla": 4, "Zap": 2}
ROLES = ("holdout", "hog26")
STYLES = ("balanced", "pressure", "defense")


def wilson(wins: int, games: int, z: float = 1.959963984540054) -> list[float]:
    if games == 0:
        return [0.0, 1.0]
    p = wins / games
    centre = (p + z * z / (2 * games)) / (1 + z * z / games)
    half = z * math.sqrt(p * (1 - p) / games + z * z / (4 * games * games)) / (1 + z * z / games)
    return [max(0.0, centre - half), min(1.0, centre + half)]


def behaviour(records: list[dict]) -> dict:
    if not records:
        return {}
    games = collections.defaultdict(list)
    for record in records:
        games[(record["matchup_seed"], record["game"])].append(record)
    held, played = collections.Counter(), collections.Counter()
    elixir_at_play, per_minute, plays_per_match, wait_probability = [], [], [], []
    playable = waits_when_playable = waits = 0
    for decisions in games.values():
        plays = 0
        for record in decisions:
            is_play = record["slot"] is not None
            can_play = any(p > 0 for p in record["action_type_probabilities"][:4])
            waits += not is_play
            if can_play:
                playable += 1
                waits_when_playable += not is_play
                wait_probability.append(record["action_type_probabilities"][4])
            if is_play:
                plays += 1
                card = record["hand"][record["slot"]]
                played[card] += 1
                for name in record["hand"]:
                    if name:
                        held[name] += 1
                elixir_at_play.append(record["elixir"])
        plays_per_match.append(plays)
        per_minute.append(plays / max(1e-9, len(decisions) * 5 / 20 / 60))
    by_cost = collections.defaultdict(lambda: [0, 0])
    for name, count in held.items():
        by_cost[COST[name]][1] += count
        by_cost[COST[name]][0] += played[name]
    total = max(1, sum(played.values()))
    decisions = sum(len(v) for v in games.values())
    return {
        "traced_games": len(games), "decisions": decisions,
        "plays_per_match_mean": float(np.mean(plays_per_match)),
        "plays_per_minute_mean": float(np.mean(per_minute)),
        "wait_fraction": waits / max(1, decisions),
        "wait_when_playable": waits_when_playable / max(1, playable),
        "mean_wait_probability_when_playable": float(np.mean(wait_probability)) if wait_probability else None,
        "elixir_at_play": {f"p{q}": float(np.percentile(elixir_at_play, q)) for q in (25, 50, 75)} if elixir_at_play else {},
        "play_when_held_by_cost": {str(c): by_cost[c][0] / max(1, by_cost[c][1]) for c in sorted(by_cost)},
        "play_when_held_by_card": {name: played[name] / max(1, held[name]) for name in sorted(held)},
        "card_share": {name: count / total for name, count in played.most_common()},
        "mean_play_cost": sum(COST[name] * count for name, count in played.items()) / total,
        "share_cost_le_2": sum(count for name, count in played.items() if COST[name] <= 2) / total,
        "share_cost_ge_4": sum(count for name, count in played.items() if COST[name] >= 4) / total,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--drop-traces", action="store_true")
    args = parser.parse_args()
    directory = OUT / "evaluation" / args.name
    result = {"name": args.name, "cells": {}, "roles": {}}
    traces = {role: [] for role in ROLES}
    for role in ROLES:
        wins = games = draws = 0
        for style in STYLES:
            prefix = directory / f"{role}-nominal-{style}"
            summary = json.loads(Path(str(prefix) + ".json").read_text())
            metrics = summary["metrics"]
            cell = {"wins": int(metrics["wins"]), "losses": int(metrics["losses"]), "draws": int(metrics["draws"]),
                    "games": int(metrics["games"]), "seed": summary["seed"],
                    "noop_rate": metrics["candidate_noop_rate"], "noop_when_playable": metrics["candidate_noop_when_playable"],
                    "placement_rate": metrics["candidate_placement_rate"], "crown_diff_per_game": metrics["crown_diff_per_game"],
                    "average_ticks": metrics["average_ticks"], "checkpoint_sha256": summary["checkpoint_sha256"]}
            cell["wilson95"] = wilson(cell["wins"], cell["games"])
            result["cells"][f"{role}-{style}"] = cell
            wins, games, draws = wins + cell["wins"], games + cell["games"], draws + cell["draws"]
            trace = Path(str(prefix) + ".decisions.json")
            if trace.exists():
                traces[role].extend(json.loads(trace.read_text()))
        result["roles"][role] = {"wins": wins, "games": games, "draws": draws, "win_rate": wins / max(1, games),
                                 "wilson95": wilson(wins, games),
                                 "noop_when_playable": float(np.mean([result["cells"][f"{role}-{s}"]["noop_when_playable"] for s in STYLES])),
                                 "placement_rate": float(np.mean([result["cells"][f"{role}-{s}"]["placement_rate"] for s in STYLES])),
                                 "behaviour": behaviour(traces[role])}
    (OUT / "results").mkdir(exist_ok=True)
    (OUT / "results" / f"evaluation-{args.name}.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({role: {k: v for k, v in data.items() if k != "behaviour"} for role, data in result["roles"].items()}))
    if args.drop_traces:
        for trace in directory.glob("*.decisions.json"):
            trace.unlink()


if __name__ == "__main__":
    main()
