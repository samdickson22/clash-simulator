#!/usr/bin/env python3
"""Measure stochastic policy temperatures against deterministic gameplay."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import torch
from torch.distributions import Categorical

from clasher.rl.eval import evaluate, load_policy_checkpoint
from clasher.rl.model import PolicyOutput
from clasher.rl.strategy_bots import StrategyBot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, required=True)
    parser.add_argument("--candidate-decks", type=Path, required=True)
    parser.add_argument("--opponent-decks", type=Path, required=True)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1192401)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--temperature",
        action="append",
        type=float,
        dest="temperatures",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    temperatures = args.temperatures or [1.0, 0.75, 0.5, 0.35, 0.25, 0.15, 0.1]
    if args.games <= 0:
        raise ValueError("games must be positive")
    if any(not 0.0 < value <= 1.0 for value in temperatures):
        raise ValueError("temperatures must be in (0, 1]")

    device = torch.device("cpu")
    candidate = load_policy_checkpoint(
        args.checkpoint.resolve(),
        device=device,
        decks_path=args.decks_path.resolve(),
    )
    original: Callable[[PolicyOutput], Categorical] = PolicyOutput.distribution
    rows: list[dict[str, object]] = []
    try:
        arms: list[tuple[str, float | None]] = [("deterministic", None)]
        arms.extend((f"temperature-{value:g}", value) for value in temperatures)
        for arm_index, (label, temperature) in enumerate(arms):
            if temperature is None:
                PolicyOutput.distribution = original
            else:
                def tempered_distribution(
                    output: PolicyOutput,
                    *,
                    _temperature: float = temperature,
                ) -> Categorical:
                    return Categorical(logits=output.joint_logits / _temperature)

                PolicyOutput.distribution = tempered_distribution
            for opponent_index, opponent_name in enumerate(("balanced", "random")):
                game_records: list[dict[str, object]] = []
                metrics = evaluate(
                    candidate=candidate,
                    decks_path=args.decks_path.resolve(),
                    games=args.games,
                    seed=args.seed + opponent_index,
                    decision_interval=8,
                    max_ticks=6000,
                    opponent_mode=("strategy" if opponent_name == "balanced" else "random"),
                    opponent=None,
                    deterministic=temperature is None,
                    quiet_engine=True,
                    device=device,
                    sampling_decks_path=args.opponent_decks.resolve(),
                    candidate_sampling_decks_path=args.candidate_decks.resolve(),
                    opponent_sampling_decks_path=args.opponent_decks.resolve(),
                    reward_profile="objective-v1",
                    opponent_bot=(
                        StrategyBot("balanced") if opponent_name == "balanced" else None
                    ),
                    game_records=game_records,
                )
                rows.append(
                    {
                        "arm": label,
                        "temperature": temperature,
                        "opponent": opponent_name,
                        "seed": args.seed + opponent_index,
                        "metrics": metrics,
                        "games": game_records,
                    }
                )
    finally:
        PolicyOutput.distribution = original

    summary: list[dict[str, object]] = []
    for label in dict.fromkeys(str(row["arm"]) for row in rows):
        selected = [row for row in rows if row["arm"] == label]
        metrics = [row["metrics"] for row in selected]
        summary.append(
            {
                "arm": label,
                "temperature": selected[0]["temperature"],
                "games": sum(int(item["games"]) for item in metrics),
                "wins": sum(int(item["wins"]) for item in metrics),
                "losses": sum(int(item["losses"]) for item in metrics),
                "draws": sum(int(item["draws"]) for item in metrics),
                "crown_diff_per_game": sum(
                    float(item["crown_diff_per_game"]) * int(item["games"])
                    for item in metrics
                )
                / sum(int(item["games"]) for item in metrics),
                "placement_rate": sum(
                    float(item["candidate_placement_rate"]) for item in metrics
                )
                / len(metrics),
            }
        )

    payload = {
        "schema": "clasher.hog26.sampling-temperature-screen.v1",
        "checkpoint": str(args.checkpoint.resolve()),
        "games_per_opponent": args.games,
        "opponents": ["balanced", "random"],
        "rows": rows,
        "summary": summary,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
