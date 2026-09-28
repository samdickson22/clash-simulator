"""Search two-decision policy repairs using only full episode replays."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.eval import LoadedPolicy, _policy_action, load_policy_checkpoint
from clasher.rl.reward_model import DEFENSE_V2, REWARD_PROFILES
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.train_recurrent import maybe_silence_stdio


def _ranked_proposals(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    unique: dict[tuple[int, int], dict[str, Any]] = {}
    for branch in payload["branches"]:
        key = (int(branch["tick"]), int(branch["alternative_action"]))
        unique.setdefault(key, branch)
    return sorted(
        unique.values(),
        key=lambda branch: (
            int(branch["candidate_crowns"]) - int(branch["opponent_crowns"]),
            branch["outcome"] == "win",
            -int(branch["end_tick"]),
        ),
        reverse=True,
    )[:limit]


@torch.no_grad()
def _replay_pair(
    policy: LoadedPolicy,
    *,
    decks_path: Path,
    matchup_seed: int,
    candidate_player: int,
    proposals: tuple[dict[str, Any], dict[str, Any]],
    decision_interval: int,
    max_ticks: int,
    engine_fast_path: str,
    reward_profile: str,
    device: torch.device,
    quiet_engine: bool,
) -> dict[str, Any]:
    plan = {
        int(proposal["tick"]): int(proposal["alternative_action"])
        for proposal in proposals
    }
    if len(plan) != 2:
        return {"valid": False, "reason": "duplicate override tick"}
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        seed=matchup_seed,
        mirror_match=False,
        canonical_perspective=True,
        engine_fast_path=engine_fast_path,
        reward_profile=reward_profile,
    )
    with maybe_silence_stdio(quiet_engine):
        env.reset(seed=matchup_seed)
    opponent_rng = np.random.default_rng(matchup_seed + 91_117)
    torch.manual_seed(matchup_seed + 271_828)
    other_player = 1 - candidate_player
    state = policy.model.initial_state(1, device=device)
    previous_action = env.action_space.no_op_action
    previous_reward = 0.0
    episode_start = True
    applied: list[dict[str, int]] = []
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
        override = plan.get(env.battle.tick)
        if override is not None:
            if not candidate_mask[override]:
                return {
                    "valid": False,
                    "reason": "illegal override",
                    "tick": env.battle.tick,
                    "alternative_action": override,
                }
            applied.append(
                {
                    "tick": env.battle.tick,
                    "baseline_action": action,
                    "alternative_action": override,
                }
            )
            action = override
        other_mask = env.get_action_mask(other_player)
        legal = np.flatnonzero(other_mask)
        other_action = (
            int(opponent_rng.choice(legal))
            if legal.size
            else env.action_space.no_op_action
        )
        with maybe_silence_stdio(quiet_engine):
            rewards, done, _ = env.step(
                {candidate_player: action, other_player: other_action},
                pre_action_masks={
                    candidate_player: candidate_mask,
                    other_player: other_mask,
                },
            )
        state = next_state
        previous_action = action
        previous_reward = float(rewards[candidate_player])
        episode_start = False

    if len(applied) != 2:
        return {
            "valid": False,
            "reason": "episode ended before both overrides",
            "applied": applied,
        }
    assert env.battle is not None
    winner = env.battle.winner
    return {
        "valid": True,
        "overrides": applied,
        "outcome": (
            "draw"
            if winner is None
            else ("win" if winner == candidate_player else "loss")
        ),
        "candidate_crowns": env.battle.get_crown_count(candidate_player),
        "opponent_crowns": env.battle.get_crown_count(other_player),
        "end_tick": env.battle.tick,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--proposals", required=True)
    parser.add_argument("--top", type=int, default=18)
    parser.add_argument("--partition-index", type=int, required=True)
    parser.add_argument("--partition-count", type=int, required=True)
    parser.add_argument("--stop-after-win", action="store_true")
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=6000)
    parser.add_argument(
        "--engine-fast-path", choices=["off", "shadow", "on"], default="off"
    )
    parser.add_argument(
        "--reward-profile", choices=REWARD_PROFILES, default=DEFENSE_V2
    )
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    parser.add_argument("--torch-threads", type=int, default=1)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--quiet-engine", action="store_true", default=True)
    parser.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")
    args = parser.parse_args()
    if not 0 <= args.partition_index < args.partition_count:
        raise ValueError("partition index must be within partition count")

    torch.set_num_threads(args.torch_threads)
    device = torch.device(args.device)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    checkpoint = resolve_path(args.checkpoint, must_exist=True)
    proposals_path = resolve_path(args.proposals, must_exist=True)
    payload = json.loads(proposals_path.read_text(encoding="utf-8"))
    policy = load_policy_checkpoint(
        checkpoint,
        device=device,
        decks_path=decks_path,
    )
    ranked = _ranked_proposals(payload, args.top)
    pairs = [
        pair
        for pair in itertools.combinations(ranked, 2)
        if int(pair[0]["tick"]) != int(pair[1]["tick"])
    ]
    assigned = pairs[args.partition_index :: args.partition_count]
    results: list[dict[str, Any]] = []
    for first, second in assigned:
        ordered = cast(
            tuple[dict[str, Any], dict[str, Any]],
            tuple(sorted((first, second), key=lambda item: int(item["tick"]))),
        )
        exact = _replay_pair(
            policy,
            decks_path=decks_path,
            matchup_seed=int(payload["matchup_seed"]),
            candidate_player=int(payload["candidate_player"]),
            proposals=ordered,
            decision_interval=args.decision_interval,
            max_ticks=args.max_ticks,
            engine_fast_path=args.engine_fast_path,
            reward_profile=args.reward_profile,
            device=device,
            quiet_engine=args.quiet_engine,
        )
        results.append({"proposals": ordered, "exact": exact})
        print(json.dumps(exact, sort_keys=True), flush=True)
        if args.stop_after_win and exact.get("outcome") == "win":
            break

    output_payload = {
        "schema_version": 1,
        "checkpoint": str(checkpoint),
        "proposals": str(proposals_path),
        "matchup_seed": int(payload["matchup_seed"]),
        "candidate_player": int(payload["candidate_player"]),
        "partition_index": args.partition_index,
        "partition_count": args.partition_count,
        "pairs_total": len(pairs),
        "pairs_assigned": len(assigned),
        "results": results,
        "winning_repairs": [
            item["exact"] for item in results if item["exact"].get("outcome") == "win"
        ],
    }
    output = resolve_path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(output_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
