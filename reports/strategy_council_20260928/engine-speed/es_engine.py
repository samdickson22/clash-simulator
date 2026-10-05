"""Engine-only random-legal play over full matches (training-role pilot decks).

Both seats pick a uniformly random ENGINE-legal action (no-op included) every
5-tick decision, exactly like oracle-qualification's "with deploys" workload but
for whole matches. Modes:
  time     : wall + process_time, split into legal-mask / env.step
  cprofile : deterministic profile (pstats dump + phase table)
  sample   : low-overhead stack sampler (py-spy needs root here), subsystem table
Writes results/engine_<label>.json
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
import time

import numpy as np

from es_common import RESULTS, TRAIN_DECKS, Timer, battle_digest, host_info, peak_rss_mb, write_json

from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.train_recurrent import maybe_silence_stdio

from es_classify import classify_engine_stacks
from es_common import CollapsedSampler


def make_env(seed: int, fast_path: str) -> SelfPlayBattleEnv:
    env = SelfPlayBattleEnv(
        decision_interval_ticks=5,
        max_ticks=6001,
        decks_path=TRAIN_DECKS,
        sampling_decks_path=TRAIN_DECKS,
        seed=seed,
        public_contract_version=4,
        canonical_lane_globals=True,
        engine_fast_path=fast_path,
        reward_potential_scale=0.05,
    )
    return env


def play_match(env, seed: int, mask_timer: Timer, step_timer: Timer, rng, *,
               mask_fast: bool | None, deploy_prob: float, record_digest_every: int = 0,
               snapshots: list | None = None, snapshot_every: int = 0):
    with maybe_silence_stdio(True):
        env.reset(seed=seed)
    space = env.action_space
    battle = env.battle
    done = False
    decisions = 0
    deploys = 0
    entity_sum = 0
    digests = []
    max_entities = 0
    next_snap = snapshot_every
    while not done:
        actions = {}
        with mask_timer:
            for pid in (0, 1):
                if deploy_prob < 1.0 and rng.random() >= deploy_prob:
                    actions[pid] = space.no_op_action
                else:
                    actions[pid] = space.random_legal_action(battle, pid, rng, fast_path=mask_fast)
        deploys += sum(1 for a in actions.values() if a != space.no_op_action)
        with step_timer:
            with maybe_silence_stdio(True):
                _, done, _ = env.step(actions)
        decisions += 1
        n = len(battle.entities)
        entity_sum += n
        max_entities = max(max_entities, n)
        if record_digest_every and decisions % record_digest_every == 0:
            digests.append(battle_digest(battle))
        if snapshots is not None and snapshot_every and battle.tick >= next_snap:
            snapshots.append(battle.clone())
            next_snap += snapshot_every
    return {
        "seed": seed,
        "ticks": int(battle.tick),
        "decisions": decisions,
        "deploy_attempts": deploys,
        "mean_entities": entity_sum / max(1, decisions),
        "max_entities": max_entities,
        "winner": battle.winner,
        "final_digest": battle_digest(battle),
        "digests": digests,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("time", "cprofile", "sample"), default="time")
    ap.add_argument("--matches", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7100)
    ap.add_argument("--fast-path", choices=("off", "on"), default="off")
    ap.add_argument("--mask-fast", choices=("default", "on", "off"), default="default")
    ap.add_argument("--deploy-prob", type=float, default=1.0)
    ap.add_argument("--digest-every", type=int, default=0)
    ap.add_argument("--clone-snapshots", action="store_true")
    ap.add_argument("--label", required=True)
    args = ap.parse_args()
    mask_fast = {"default": None, "on": True, "off": False}[args.mask_fast]

    out = {"args": vars(args), "host_before": host_info()}
    env = make_env(args.seed, args.fast_path)
    rng = np.random.default_rng(args.seed)
    # warm-up match (imports, caches) is not timed
    play_match(env, args.seed - 1, Timer(), Timer(), np.random.default_rng(0), mask_fast=mask_fast,
               deploy_prob=args.deploy_prob)

    mask_t, step_t = Timer(), Timer()
    matches = []
    snapshots: list = [] if args.clone_snapshots else None
    profiler = sampler = None
    if args.mode == "cprofile":
        profiler = cProfile.Profile()
        profiler.enable()
    elif args.mode == "sample":
        sampler = CollapsedSampler().start()
    total = Timer()
    with total:
        for m in range(args.matches):
            matches.append(play_match(env, args.seed + 1009 * m, mask_t, step_t, rng, mask_fast=mask_fast,
                                      deploy_prob=args.deploy_prob, record_digest_every=args.digest_every,
                                      snapshots=snapshots, snapshot_every=600))
            print(f"match {m}: {matches[-1]['ticks']} ticks, mean ent {matches[-1]['mean_entities']:.1f}",
                  flush=True)
    if profiler is not None:
        profiler.disable()
    if sampler is not None:
        sampler.stop()

    ticks = sum(m["ticks"] for m in matches)
    out.update(
        matches=matches,
        ticks=ticks,
        wall_seconds=total.wall,
        cpu_seconds=total.cpu,
        ticks_per_second_wall=ticks / total.wall,
        ticks_per_second_cpu=ticks / total.cpu,
        mask_wall=mask_t.wall, mask_cpu=mask_t.cpu,
        step_wall=step_t.wall, step_cpu=step_t.cpu,
        step_ticks_per_second_cpu=ticks / step_t.cpu,
        host_after=host_info(),
        peak_rss_mb=peak_rss_mb(),
    )
    if snapshots:
        times = []
        for b in snapshots:
            for _ in range(3):
                t0 = time.process_time()
                b.clone()
                times.append(time.process_time() - t0)
        out["clone_cpu_ms"] = {
            "mean": 1e3 * float(np.mean(times)), "median": 1e3 * float(np.median(times)),
            "n": len(times),
            "entities": [len(b.entities) for b in snapshots],
        }
    if profiler is not None:
        path = RESULTS / f"engine_{args.label}.pstats"
        profiler.dump_stats(str(path))
        s = io.StringIO()
        pstats.Stats(profiler, stream=s).sort_stats("tottime").print_stats(45)
        (RESULTS / f"engine_{args.label}_tottime.txt").write_text(s.getvalue())
        s = io.StringIO()
        pstats.Stats(profiler, stream=s).sort_stats("cumulative").print_stats(70)
        (RESULTS / f"engine_{args.label}_cumtime.txt").write_text(s.getvalue())
    if sampler is not None:
        sampler.dump(RESULTS / f"engine_{args.label}.collapsed")
        out["sample_categories"] = classify_engine_stacks(dict(sampler.stacks))
        out["samples"] = sampler.samples
    write_json(RESULTS / f"engine_{args.label}.json", out)
    print(f"ticks/s wall {out['ticks_per_second_wall']:.0f} cpu {out['ticks_per_second_cpu']:.0f}; "
          f"mask cpu share {mask_t.cpu / total.cpu:.2%}")


if __name__ == "__main__":
    main()
