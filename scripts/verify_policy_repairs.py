"""Verify proposed policy repairs by replaying each branch from episode reset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.eval import _policy_action, load_policy_checkpoint
from clasher.rl.reward_model import DEFENSE_V2, REWARD_PROFILES
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.train_recurrent import maybe_silence_stdio


def _ranked_proposals(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    unique: dict[tuple[int, int], dict[str, Any]] = {}
    for branch in payload["branches"]:
        key = (int(branch["tick"]), int(branch["alternative_action"]))
        unique.setdefault(key, branch)
    ranked = sorted(
        unique.values(),
        key=lambda branch: (
            int(branch["candidate_crowns"]) - int(branch["opponent_crowns"]),
            branch["outcome"] == "win",
            -int(branch["end_tick"]),
        ),
        reverse=True,
    )
    return ranked[:limit]


@torch.no_grad()
def _exact_replay(
    *,
    checkpoint: Path,
    decks_path: Path,
    matchup_seed: int,
    candidate_player: int,
    override_tick: int,
    override_action: int,
    decision_interval: int,
    max_ticks: int,
    engine_fast_path: str,
    reward_profile: str,
    device: torch.device,
    quiet_engine: bool,
) -> dict[str, Any]:
    policy = load_policy_checkpoint(
        checkpoint,
        device=device,
        decks_path=decks_path,
    )
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
    applied = False
    baseline_action: int | None = None
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
        if env.battle.tick == override_tick:
            if not candidate_mask[override_action]:
                raise RuntimeError(
                    f"override action {override_action} is illegal at tick {override_tick}"
                )
            baseline_action = action
            action = override_action
            applied = True
        elif env.battle.tick > override_tick and not applied:
            raise RuntimeError(f"override tick {override_tick} was skipped")
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

    assert env.battle is not None
    winner = env.battle.winner
    return {
        "tick": override_tick,
        "baseline_action": baseline_action,
        "alternative_action": override_action,
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
    parser.add_argument("--top", type=int, default=24)
    parser.add_argument("--partition-index", type=int, default=0)
    parser.add_argument("--partition-count", type=int, default=1)
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
    checkpoint = resolve_path(args.checkpoint, must_exist=True)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    proposals_path = resolve_path(args.proposals, must_exist=True)
    proposals = json.loads(proposals_path.read_text(encoding="utf-8"))
    matchup_seed = int(proposals["matchup_seed"])
    candidate_player = int(proposals["candidate_player"])
    verified = []
    ranked = _ranked_proposals(proposals, args.top)
    assigned = ranked[args.partition_index :: args.partition_count]
    for proposal in assigned:
        result = _exact_replay(
            checkpoint=checkpoint,
            decks_path=decks_path,
            matchup_seed=matchup_seed,
            candidate_player=candidate_player,
            override_tick=int(proposal["tick"]),
            override_action=int(proposal["alternative_action"]),
            decision_interval=args.decision_interval,
            max_ticks=args.max_ticks,
            engine_fast_path=args.engine_fast_path,
            reward_profile=args.reward_profile,
            device=torch.device(args.device),
            quiet_engine=args.quiet_engine,
        )
        verified.append({"proposal": proposal, "exact": result})
        print(json.dumps(result, sort_keys=True), flush=True)

    payload = {
        "schema_version": 1,
        "checkpoint": str(checkpoint),
        "proposals": str(proposals_path),
        "matchup_seed": matchup_seed,
        "candidate_player": candidate_player,
        "partition_index": args.partition_index,
        "partition_count": args.partition_count,
        "proposals_total": len(ranked),
        "verified": verified,
        "winning_repairs": [
            item["exact"] for item in verified if item["exact"]["outcome"] == "win"
        ],
    }
    output = resolve_path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
