"""Cost measurements (single process): engine ticks/s, BattleState fork cost,
planner primitive costs and planner wall time per decision for several budgets.

Snapshots are forks of real evaluation-game states (seed-2903 1M checkpoint vs the
balanced public script, holdout and hog26 pilot matchups) taken every 400 ticks.
Writes cost/cost.json (resumable per section).
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

import oq_lib
from clasher.rl import eval as cl_eval
from clasher.rl.reward_model import reward_win_prob_p0
from clasher.rl.train_recurrent import maybe_silence_stdio

OUT = oq_lib.OQ_DIR / "cost" / "cost.json"
result = json.loads(OUT.read_text()) if OUT.exists() else {}


def save():
    oq_lib.write_json_atomic(OUT, result)


def collect_snapshots(ctx, role, style, game, every_ticks=400):
    """Replay one pilot game (policy vs script) and fork states along the way."""
    import torch
    from clasher.rl.public_observation import project_council_public_observation

    seed = oq_lib.PILOT_CELL_SEEDS[(role, style)]
    matchup_seed = seed + (game // 2) * 1009
    cp = game % 2
    op = 1 - cp
    env = ctx.envs(role, seed)[cp]
    cd, od = cl_eval._sample_paired_ordered_decks(*ctx.pools(role), matchup_seed=matchup_seed)
    with maybe_silence_stdio(True):
        env.reset(seed=matchup_seed, ordered_decks=(cd, od) if cp == 0 else (od, cd))
    torch.manual_seed(matchup_seed + 271_828)
    state = ctx.loaded.model.initial_state(1, device=ctx.device)
    prev_a, prev_r, start, done = env.action_space.no_op_action, 0.0, True, False
    snaps = []
    step_seconds = 0.0
    next_snap = every_ticks
    while not done:
        if env.battle.tick >= next_snap:
            snaps.append(env.battle.clone())
            next_snap += every_ticks
        a, state, mask, _ = cl_eval._policy_step(
            ctx.loaded, env, cp, state=state, previous_action=prev_a,
            previous_reward=prev_r, episode_start=start, deterministic=False, device=ctx.device,
        )
        obs = env.get_structured_observation(op)
        omask = env.get_action_mask(op, structured_observation=obs)
        oa = ctx.bot(style).select_action(project_council_public_observation(obs))
        t0 = time.perf_counter()
        with maybe_silence_stdio(True):
            rewards, done, _ = env.step({cp: a, op: oa}, pre_action_masks={cp: mask, op: omask})
        step_seconds += time.perf_counter() - t0
        prev_a, prev_r, start = a, float(rewards[cp]), False
    return snaps, env.battle.tick, step_seconds


def alive(b):
    return sum(1 for e in b.entities.values() if e.is_alive)


def main():
    ctx = oq_lib.Context()
    snaps = []
    env_step = []
    for role, style, game in (("holdout", "balanced", 0), ("hog26", "balanced", 1), ("holdout", "pressure", 2)):
        s, ticks, secs = collect_snapshots(ctx, role, style, game)
        snaps += s
        env_step.append({"role": role, "style": style, "game": game, "ticks": ticks, "env_step_seconds": secs, "ticks_per_second": ticks / secs})
        print("game", role, style, game, ticks, f"{ticks/secs:.0f} ticks/s in env.step", flush=True)
    space = oq_lib.DiscreteTileActionSpaceSingleton = ctx.envs("holdout", 0)[0].action_space
    result["snapshots"] = [{"tick": int(b.tick), "alive_entities": alive(b)} for b in snaps]
    result["env_step_full_games"] = env_step
    print("snapshots", len(snaps), [x["alive_entities"] for x in result["snapshots"]], flush=True)

    # 1. fork cost
    t = []
    for b in snaps:
        for _ in range(5):
            t0 = time.perf_counter(); c = b.clone(); t.append(time.perf_counter() - t0)
    result["clone_ms"] = {"mean": 1e3 * statistics.mean(t), "median": 1e3 * statistics.median(t), "min": 1e3 * min(t), "max": 1e3 * max(t), "n": len(t)}
    print("clone ms", result["clone_ms"], flush=True)

    # 2. raw engine ticks/s (fork, then step with no further deploys)
    ticks = 0; secs = 0.0
    for b in snaps:
        c = b.clone()
        t0 = time.perf_counter()
        with maybe_silence_stdio(True):
            for _ in range(200):
                if c.game_over: break
                c.step(); ticks += 1
        secs += time.perf_counter() - t0
    result["engine_no_deploy"] = {"ticks": ticks, "seconds": secs, "ticks_per_second": ticks / secs}
    print("engine no-deploy ticks/s", ticks / secs, flush=True)

    # 2b. raw engine ticks/s with random legal deploys by both seats every 5 ticks
    rng = np.random.default_rng(1)
    ticks = 0; secs = 0.0
    for b in snaps:
        c = b.clone()
        for _ in range(40):
            if c.game_over: break
            for pid in (0, 1):
                space.apply_action(c, pid, space.random_legal_action(c, pid, rng))
            t0 = time.perf_counter()
            with maybe_silence_stdio(True):
                for _ in range(5):
                    if c.game_over: break
                    c.step(); ticks += 1
            secs += time.perf_counter() - t0
    result["engine_random_deploys"] = {"ticks": ticks, "seconds": secs, "ticks_per_second": ticks / secs}
    print("engine random-deploy ticks/s", ticks / secs, flush=True)

    # 3. primitives
    pl = oq_lib.make_planner(ctx.envs("holdout", 0)[0], {}, seed=1)
    def timeit(fn, reps=3):
        t = []
        for b in snaps:
            for _ in range(reps):
                t0 = time.perf_counter(); fn(b); t.append(time.perf_counter() - t0)
        return 1e3 * statistics.mean(t)
    result["primitives_ms"] = {
        "legal_action_mask_one_player": timeit(lambda b: space.legal_action_mask(b, 0)),
        "state_key": timeit(lambda b: pl._state_key(b)),
        "reward_win_prob_objective_v1": timeit(lambda b: reward_win_prob_p0(b, "objective-v1")),
        "reward_win_prob_defense_v2": timeit(lambda b: reward_win_prob_p0(b, "defense-v2")),
    }
    result["legal_action_counts"] = [int(np.count_nonzero(space.legal_action_mask(b, p))) for b in snaps for p in (0, 1)]
    print("primitives", result["primitives_ms"], flush=True)
    save()

    # 4. planner wall time per decision
    budgets = {
        "default_d10_s48_a96": {},
        "legacy_d6_s32_a64_stable_defv2": {"depth": 6, "sims": 32, "samples": 64, "stable_root": True, "profile": "defense-v2"},
        "greedy1_d1_s48_a96": {"depth": 1},
        "cheap_d4_s16_a32": {"depth": 4, "sims": 16, "samples": 32},
        "roll_d1_s32_a32_leaf200": {"depth": 1, "sims": 32, "samples": 32, "stable_root": True, "profile": "defense-v2", "leaf_rollout_ticks": 200},
        "roll_d1_s64_a32_leaf200": {"depth": 1, "sims": 64, "samples": 32, "stable_root": True, "profile": "defense-v2", "leaf_rollout_ticks": 200},
        "roll_d4i10_s64_a32_leaf160": {"depth": 4, "interval": 10, "sims": 64, "samples": 32, "stable_root": True, "profile": "defense-v2", "leaf_rollout_ticks": 160},
        "supercell_like_d50_i10_s16_a257": {"depth": 50, "interval": 10, "sims": 16, "samples": 257, "stable_root": True},
        "supercell_like_d50_i10_s16_a257_leaf_to_end": {"depth": 50, "interval": 10, "sims": 16, "samples": 257, "stable_root": True, "leaf_rollout_ticks": 6001},
    }
    result.setdefault("planner_seconds_per_decision", {})
    only = sys.argv[1:] or list(budgets)
    for name in only:
        if name in result["planner_seconds_per_decision"]:
            continue
        cfg = budgets[name]
        use = snaps if "supercell" not in name else snaps[::4]
        t = []
        for b in use:
            p = oq_lib.make_planner(ctx.envs("holdout", 0)[0], cfg, seed=3)
            t0 = time.perf_counter()
            with maybe_silence_stdio(True):
                p.select_actions(b)
            t.append(time.perf_counter() - t0)
        result["planner_seconds_per_decision"][name] = {"config": cfg, "mean": statistics.mean(t), "median": statistics.median(t), "min": min(t), "max": max(t), "n": len(t)}
        print(name, result["planner_seconds_per_decision"][name], flush=True)
        save()


if __name__ == "__main__":
    main()
