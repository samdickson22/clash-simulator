"""Run an exact oracle-controlled matchup against the stationary random policy."""

from __future__ import annotations

import argparse
import json

import numpy as np

from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matchup-seed", type=int, required=True)
    parser.add_argument("--candidate-player", type=int, choices=[0, 1], required=True)
    parser.add_argument("--planner-seed", type=int, required=True)
    parser.add_argument("--plan-depth", type=int, default=6)
    parser.add_argument("--simulations", type=int, default=32)
    parser.add_argument("--action-samples", type=int, default=64)
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

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
    planner = FixedDepthThompsonOracle(
        env.action_space,
        decision_interval_ticks=8,
        plan_depth=args.plan_depth,
        num_simulations=args.simulations,
        rollout_action_samples=args.action_samples,
        seed=args.planner_seed,
        reward_profile="defense-v2",
        stable_root_candidates=True,
    )
    opponent_rng = np.random.default_rng(args.matchup_seed + 91_117)
    candidate_player = args.candidate_player
    other_player = 1 - candidate_player
    trace = []
    done = False
    while not done:
        assert env.battle is not None
        candidate_mask = env.get_action_mask(candidate_player)
        candidate_action = planner.select_actions(env.battle)[candidate_player]
        if not candidate_mask[candidate_action]:
            raise RuntimeError(f"planner selected illegal action {candidate_action}")
        other_mask = env.get_action_mask(other_player)
        legal = np.flatnonzero(other_mask)
        other_action = (
            int(opponent_rng.choice(legal))
            if legal.size
            else env.action_space.no_op_action
        )
        trace.append({"tick": env.battle.tick, "action": candidate_action})
        _, done, _ = env.step(
            {candidate_player: candidate_action, other_player: other_action},
            pre_action_masks={
                candidate_player: candidate_mask,
                other_player: other_mask,
            },
        )

    assert env.battle is not None
    winner = env.battle.winner
    result = {
        "schema_version": 1,
        "matchup_seed": args.matchup_seed,
        "candidate_player": candidate_player,
        "planner_seed": args.planner_seed,
        "plan_depth": args.plan_depth,
        "simulations": args.simulations,
        "action_samples": args.action_samples,
        "outcome": (
            "draw"
            if winner is None
            else ("win" if winner == candidate_player else "loss")
        ),
        "candidate_crowns": env.battle.get_crown_count(candidate_player),
        "opponent_crowns": env.battle.get_crown_count(other_player),
        "end_tick": env.battle.tick,
        "trace": trace,
    }
    with open(args.json_out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({key: value for key, value in result.items() if key != "trace"}))


if __name__ == "__main__":
    main()
