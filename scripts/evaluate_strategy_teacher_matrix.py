#!/usr/bin/env python3
# mypy: disable-error-code="import-untyped"
"""Evaluate public-information strategy teachers on a fixed learner deck."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import (
    STRATEGY_NAMES,
    BalancedStrategyConfig,
    StrategyBot,
)

RANDOM = "random"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(
    *,
    decks_path: Path,
    learner_decks_path: Path,
    opponent_decks_path: Path,
    candidate_strategies: list[str],
    opponent_controllers: list[str],
    games_per_matchup: int,
    seed: int,
    balanced_config: BalancedStrategyConfig | None = None,
) -> dict[str, Any]:
    if games_per_matchup <= 0 or games_per_matchup % 2:
        raise ValueError("games per matchup must be a positive even number")
    if not candidate_strategies or not opponent_controllers:
        raise ValueError("candidate and opponent lists must be non-empty")
    if any(name not in STRATEGY_NAMES for name in candidate_strategies):
        raise ValueError("unknown candidate strategy")
    if any(
        name != RANDOM and name not in STRATEGY_NAMES
        for name in opponent_controllers
    ):
        raise ValueError("unknown opponent controller")

    results: dict[str, dict[str, dict[str, float]]] = {}
    for candidate_name in candidate_strategies:
        candidate_bot = StrategyBot(
            candidate_name,
            balanced_config=balanced_config or BalancedStrategyConfig(),
        )
        candidate_results: dict[str, dict[str, float]] = {}
        for opponent_index, opponent_name in enumerate(opponent_controllers):
            opponent_bot = (
                None if opponent_name == RANDOM else StrategyBot(opponent_name)
            )
            wins = losses = draws = candidate_crowns = opponent_crowns = 0
            placements = decisions = 0
            for game in range(games_per_matchup):
                candidate = game % 2
                opponent = 1 - candidate
                player_paths = (
                    (learner_decks_path, opponent_decks_path)
                    if candidate == 0
                    else (opponent_decks_path, learner_decks_path)
                )
                matchup_seed = seed + opponent_index * 100_003 + (game // 2) * 1009
                env = SelfPlayBattleEnv(
                    decision_interval_ticks=8,
                    max_ticks=6000,
                    decks_path=decks_path,
                    sampling_decks_path=opponent_decks_path,
                    player0_sampling_decks_path=player_paths[0],
                    player1_sampling_decks_path=player_paths[1],
                    learner_player_id=candidate,
                    seed=matchup_seed,
                    canonical_perspective=True,
                    canonical_lane_globals=True,
                    engine_fast_path="on",
                    reward_profile="objective-v1",
                )
                env.reset(seed=matchup_seed)
                rng = np.random.default_rng(matchup_seed + 91_117)
                done = False
                while not done:
                    candidate_mask = env.get_action_mask(candidate)
                    candidate_action = candidate_bot.select_action(
                        env, candidate, action_mask=candidate_mask
                    )
                    opponent_mask = env.get_action_mask(opponent)
                    if opponent_bot is None:
                        legal = np.flatnonzero(opponent_mask)
                        opponent_action = (
                            int(rng.choice(legal))
                            if legal.size
                            else env.action_space.no_op_action
                        )
                    else:
                        opponent_action = opponent_bot.select_action(
                            env, opponent, action_mask=opponent_mask
                        )
                    _, done, _ = env.step(
                        {candidate: candidate_action, opponent: opponent_action},
                        pre_action_masks={
                            candidate: candidate_mask,
                            opponent: opponent_mask,
                        },
                    )
                    decisions += 1
                    placements += int(candidate_action < env.action_space.no_op_action)
                assert env.battle is not None
                candidate_crowns += env.battle.get_crown_count(candidate)
                opponent_crowns += env.battle.get_crown_count(opponent)
                if env.battle.winner is None:
                    draws += 1
                elif env.battle.winner == candidate:
                    wins += 1
                else:
                    losses += 1
            candidate_results[opponent_name] = {
                "games": float(games_per_matchup),
                "wins": float(wins),
                "losses": float(losses),
                "draws": float(draws),
                "score_rate": (wins + 0.5 * draws) / games_per_matchup,
                "crown_diff_per_game": (
                    candidate_crowns - opponent_crowns
                ) / games_per_matchup,
                "placement_rate": placements / max(1, decisions),
            }
        results[candidate_name] = candidate_results

    rankings: list[dict[str, Any]] = []
    for candidate_name, rows in results.items():
        rankings.append(
            {
                "candidate": candidate_name,
                "mean_score_rate": float(
                    np.mean([row["score_rate"] for row in rows.values()])
                ),
                "worst_score_rate": min(
                    row["score_rate"] for row in rows.values()
                ),
                "total_wins": int(sum(row["wins"] for row in rows.values())),
                "total_losses": int(sum(row["losses"] for row in rows.values())),
            }
        )
    rankings.sort(
        key=lambda row: (
            row["mean_score_rate"],
            row["worst_score_rate"],
            row["total_wins"],
        ),
        reverse=True,
    )
    return {
        "schema": "clasher.strategy_teacher_matrix.v1",
        "seed": seed,
        "games_per_matchup": games_per_matchup,
        "decks_path": str(decks_path.resolve()),
        "learner_decks_path": str(learner_decks_path.resolve()),
        "learner_decks_sha256": _sha256(learner_decks_path),
        "opponent_decks_path": str(opponent_decks_path.resolve()),
        "opponent_decks_sha256": _sha256(opponent_decks_path),
        "balanced_config": asdict(balanced_config or BalancedStrategyConfig()),
        "results": results,
        "rankings": rankings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--learner-decks-path", type=Path, required=True)
    parser.add_argument("--opponent-decks-path", type=Path, required=True)
    parser.add_argument(
        "--candidate-strategy",
        action="append",
        choices=STRATEGY_NAMES,
        dest="candidate_strategies",
    )
    parser.add_argument(
        "--opponent-controller",
        action="append",
        choices=(*STRATEGY_NAMES, RANDOM),
        dest="opponent_controllers",
    )
    parser.add_argument("--games-per-matchup", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1073901)
    parser.add_argument("--balanced-config", type=Path)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    balanced_config = None
    if args.balanced_config is not None:
        config_payload = json.loads(args.balanced_config.read_text(encoding="utf-8"))
        if not isinstance(config_payload, dict):
            raise TypeError("balanced config must be a JSON object")
        balanced_config = BalancedStrategyConfig(**config_payload)
    payload = evaluate(
        decks_path=args.decks_path.resolve(),
        learner_decks_path=args.learner_decks_path.resolve(),
        opponent_decks_path=args.opponent_decks_path.resolve(),
        candidate_strategies=args.candidate_strategies or list(STRATEGY_NAMES),
        opponent_controllers=args.opponent_controllers
        or [*STRATEGY_NAMES, RANDOM],
        games_per_matchup=args.games_per_matchup,
        seed=args.seed,
        balanced_config=balanced_config,
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"rankings": payload["rankings"]}, sort_keys=True))


if __name__ == "__main__":
    main()
