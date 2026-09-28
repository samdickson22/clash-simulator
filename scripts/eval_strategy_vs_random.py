from __future__ import annotations

import argparse
import json

import numpy as np

from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=STRATEGY_NAMES, required=True)
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--seed", type=int, default=9601)
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    env = SelfPlayBattleEnv(
        decision_interval_ticks=8,
        max_ticks=6000,
        decks_path="decks.json",
        seed=args.seed,
        canonical_perspective=True,
        reward_profile="defense-v2",
    )
    bot = StrategyBot(args.strategy)
    wins = losses = draws = 0
    candidate_crowns = opponent_crowns = 0
    for game in range(args.games):
        matchup_seed = args.seed + (game // 2) * 1009
        env.reset(seed=matchup_seed)
        rng = np.random.default_rng(matchup_seed + 91_117)
        candidate = game % 2
        other = 1 - candidate
        done = False
        while not done:
            candidate_mask = env.get_action_mask(candidate)
            candidate_action = bot.select_action(
                env,
                candidate,
                action_mask=candidate_mask,
            )
            other_mask = env.get_action_mask(other)
            legal = np.flatnonzero(other_mask)
            other_action = (
                int(rng.choice(legal))
                if legal.size
                else env.action_space.no_op_action
            )
            _, done, _ = env.step(
                {candidate: candidate_action, other: other_action},
                pre_action_masks={candidate: candidate_mask, other: other_mask},
            )

        assert env.battle is not None
        candidate_crowns += env.battle.get_crown_count(candidate)
        opponent_crowns += env.battle.get_crown_count(other)
        if env.battle.winner is None:
            draws += 1
        elif env.battle.winner == candidate:
            wins += 1
        else:
            losses += 1

    result = {
        "strategy": args.strategy,
        "games": args.games,
        "seed": args.seed,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "crown_diff_per_game": (candidate_crowns - opponent_crowns) / args.games,
    }
    with open(args.json_out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
