"""Evaluate a policy with a strategy override active only in a tick window."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from clasher.rl.eval import _policy_action, load_policy_checkpoint
from clasher.rl.reward_model import potential_breakdown_p0
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--matchup-seed", type=int, required=True)
    parser.add_argument("--candidate-player", type=int, choices=[0, 1], required=True)
    parser.add_argument("--strategy", choices=STRATEGY_NAMES, required=True)
    parser.add_argument("--danger-threshold", type=float, default=0.0)
    parser.add_argument("--outside-strategy", choices=STRATEGY_NAMES, default=None)
    parser.add_argument("--outside-danger-threshold", type=float, default=0.0)
    parser.add_argument("--start-tick", type=int, default=0)
    parser.add_argument("--end-tick", type=int, default=6000)
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    device = torch.device("cpu")
    policy = load_policy_checkpoint(
        Path(args.checkpoint),
        device=device,
        decks_path=Path("decks.json"),
    )
    env = SelfPlayBattleEnv(
        decision_interval_ticks=8,
        max_ticks=6000,
        decks_path="decks.json",
        seed=args.matchup_seed,
        mirror_match=False,
        canonical_perspective=True,
        engine_fast_path="off",
        reward_profile="defense-v2",
    )
    env.reset(seed=args.matchup_seed)
    opponent_rng = np.random.default_rng(args.matchup_seed + 91_117)
    torch.manual_seed(args.matchup_seed + 271_828)
    bot = StrategyBot(args.strategy)
    outside_bot = (
        StrategyBot(args.outside_strategy)
        if args.outside_strategy is not None
        else None
    )
    candidate_player = args.candidate_player
    other_player = 1 - candidate_player
    state = policy.model.initial_state(1, device=device)
    previous_action = env.action_space.no_op_action
    previous_reward = 0.0
    episode_start = True
    overrides = []
    done = False
    while not done:
        action, next_state, candidate_mask = _policy_action(
            policy,
            env,
            candidate_player,
            state=state,
            previous_action=previous_action,
            previous_reward=previous_reward,
            episode_start=episode_start,
            deterministic=True,
            device=device,
        )
        assert env.battle is not None
        breakdown = potential_breakdown_p0(env.battle)
        danger = max(
            0.0,
            -breakdown.tower_danger
            if candidate_player == 0
            else breakdown.tower_danger,
        )
        chosen = action
        active_bot = None
        if (
            args.start_tick <= env.battle.tick < args.end_tick
            and danger >= args.danger_threshold
        ):
            active_bot = bot
        elif (
            outside_bot is not None
            and danger >= args.outside_danger_threshold
        ):
            active_bot = outside_bot
        if active_bot is not None:
            chosen = active_bot.select_action(
                env,
                candidate_player,
                action_mask=candidate_mask,
            )
            if chosen != action:
                overrides.append(
                    {
                        "tick": env.battle.tick,
                        "danger": danger,
                        "baseline_action": action,
                        "alternative_action": chosen,
                        "strategy": active_bot.name,
                    }
                )
        other_mask = env.get_action_mask(other_player)
        legal = np.flatnonzero(other_mask)
        other_action = (
            int(opponent_rng.choice(legal))
            if legal.size
            else env.action_space.no_op_action
        )
        rewards, done, _ = env.step(
            {candidate_player: chosen, other_player: other_action},
            pre_action_masks={
                candidate_player: candidate_mask,
                other_player: other_mask,
            },
        )
        state = next_state
        previous_action = chosen
        previous_reward = float(rewards[candidate_player])
        episode_start = False

    assert env.battle is not None
    winner = env.battle.winner
    payload = {
        "schema_version": 1,
        "checkpoint": str(Path(args.checkpoint).resolve()),
        "matchup_seed": args.matchup_seed,
        "candidate_player": candidate_player,
        "strategy": args.strategy,
        "danger_threshold": args.danger_threshold,
        "outside_strategy": args.outside_strategy,
        "outside_danger_threshold": args.outside_danger_threshold,
        "start_tick": args.start_tick,
        "end_tick": args.end_tick,
        "outcome": (
            "draw"
            if winner is None
            else ("win" if winner == candidate_player else "loss")
        ),
        "candidate_crowns": env.battle.get_crown_count(candidate_player),
        "opponent_crowns": env.battle.get_crown_count(other_player),
        "end_game_tick": env.battle.tick,
        "overrides": overrides,
    }
    with open(args.json_out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({key: value for key, value in payload.items() if key != "overrides"}))


if __name__ == "__main__":
    main()
