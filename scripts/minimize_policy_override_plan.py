"""Delta-minimize a winning action-override trace with full episode replays."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.eval import LoadedPolicy, _policy_action, load_policy_checkpoint
from clasher.rl.selfplay_env import SelfPlayBattleEnv


@torch.no_grad()
def _replay(
    policy: LoadedPolicy,
    *,
    matchup_seed: int,
    candidate_player: int,
    plan: list[dict[str, Any]],
) -> dict[str, Any]:
    by_tick = {int(item["tick"]): int(item["alternative_action"]) for item in plan}
    if len(by_tick) != len(plan):
        return {"valid": False, "reason": "duplicate tick"}
    env = SelfPlayBattleEnv(
        decision_interval_ticks=8,
        max_ticks=6000,
        decks_path="decks.json",
        seed=matchup_seed,
        mirror_match=False,
        canonical_perspective=True,
        engine_fast_path="off",
        reward_profile="defense-v2",
    )
    env.reset(seed=matchup_seed)
    opponent_rng = np.random.default_rng(matchup_seed + 91_117)
    torch.manual_seed(matchup_seed + 271_828)
    other_player = 1 - candidate_player
    state = policy.model.initial_state(1, device=torch.device("cpu"))
    previous_action = env.action_space.no_op_action
    previous_reward = 0.0
    episode_start = True
    applied = []
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
            device=torch.device("cpu"),
        )
        assert env.battle is not None
        alternative = by_tick.get(env.battle.tick)
        if alternative is not None:
            if not candidate_mask[alternative]:
                return {
                    "valid": False,
                    "reason": "illegal override",
                    "tick": env.battle.tick,
                }
            applied.append(
                {
                    "tick": env.battle.tick,
                    "baseline_action": action,
                    "alternative_action": alternative,
                }
            )
            action = alternative
        other_mask = env.get_action_mask(other_player)
        legal = np.flatnonzero(other_mask)
        other_action = (
            int(opponent_rng.choice(legal))
            if legal.size
            else env.action_space.no_op_action
        )
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
        "valid": len(applied) == len(plan),
        "applied": applied,
        "outcome": (
            "draw"
            if winner is None
            else ("win" if winner == candidate_player else "loss")
        ),
        "candidate_crowns": env.battle.get_crown_count(candidate_player),
        "opponent_crowns": env.battle.get_crown_count(other_player),
        "end_tick": env.battle.tick,
    }


def _wins(result: dict[str, Any]) -> bool:
    return bool(result.get("valid") and result.get("outcome") == "win")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    checkpoint = Path(args.checkpoint).resolve()
    trace_path = Path(args.trace).resolve()
    source = json.loads(trace_path.read_text(encoding="utf-8"))
    matchup_seed = int(source["matchup_seed"])
    candidate_player = int(source["candidate_player"])
    policy = load_policy_checkpoint(
        checkpoint,
        device=torch.device("cpu"),
        decks_path=Path("decks.json"),
    )
    current = list(source["overrides"])
    initial = _replay(
        policy,
        matchup_seed=matchup_seed,
        candidate_player=candidate_player,
        plan=current,
    )
    if not _wins(initial):
        raise RuntimeError(f"source override trace is not an exact win: {initial}")

    granularity = 2
    trials = 0
    while len(current) >= 2:
        chunk_size = math.ceil(len(current) / granularity)
        reduced = False
        for start in range(0, len(current), chunk_size):
            candidate = current[:start] + current[start + chunk_size :]
            result = _replay(
                policy,
                matchup_seed=matchup_seed,
                candidate_player=candidate_player,
                plan=candidate,
            )
            trials += 1
            print(
                json.dumps(
                    {
                        "trial": trials,
                        "from": len(current),
                        "candidate": len(candidate),
                        "removed_start": start,
                        "removed_count": min(chunk_size, len(current) - start),
                        "valid": result.get("valid"),
                        "outcome": result.get("outcome"),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if _wins(result):
                current = candidate
                granularity = max(2, granularity - 1)
                reduced = True
                break
        if reduced:
            continue
        if granularity >= len(current):
            break
        granularity = min(len(current), granularity * 2)

    final = _replay(
        policy,
        matchup_seed=matchup_seed,
        candidate_player=candidate_player,
        plan=current,
    )
    if not _wins(final):
        raise RuntimeError(f"minimized plan no longer wins: {final}")
    verified_result = {
        key: final[key]
        for key in ("outcome", "candidate_crowns", "opponent_crowns", "end_tick")
    }
    payload = {
        "schema_version": 1,
        "checkpoint": str(checkpoint),
        "source_trace": str(trace_path),
        "matchup_seed": matchup_seed,
        "candidate_player": candidate_player,
        "verification": "full-replay-plan",
        "initial_steps": len(source["overrides"]),
        "minimized_steps": len(final["applied"]),
        "trials": trials,
        "repair_plan": final["applied"],
        "verified_result": verified_result,
    }
    output = Path(args.json_out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
