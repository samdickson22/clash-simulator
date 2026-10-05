"""Profile one srp planner call (oracle-qualification ScriptRolloutPlanner) into parts.

Runs inside the frozen pilot runtime like oq_run.py (read-only use of oq_lib/oq_cost).
Splits planner CPU into: clone, engine step, script decisions (observation build,
public projection, script decide), apply_action, phi, root overhead. Also runs the
stack sampler for an engine-subsystem breakdown of the step share.

usage: es_srp.py --calls N --label L
"""

from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

ES = Path(__file__).resolve().parent
sys.path.insert(0, str(ES))
sys.path.insert(0, str(ES.parent / "oracle-qualification"))

import numpy as np  # noqa: E402

import es_classify  # noqa: E402
from es_common import RESULTS, CollapsedSampler, host_info, peak_rss_mb, write_json  # noqa: E402

import oq_cost  # noqa: E402
import oq_lib  # noqa: E402
from clasher.rl.train_recurrent import maybe_silence_stdio  # noqa: E402


class Acc:
    def __init__(self):
        self.cpu = collections.Counter()
        self.n = collections.Counter()

    def wrap(self, name, fn):
        def inner(*a, **k):
            c = time.process_time()
            try:
                return fn(*a, **k)
            finally:
                self.cpu[name] += time.process_time() - c
                self.n[name] += 1
        return inner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls", type=int, default=12)
    ap.add_argument("--label", default="srp")
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    ctx = oq_lib.Context()
    snaps = []
    for role, style, game in (("holdout", "balanced", 0), ("hog26", "balanced", 1)):
        s, _, _ = oq_cost.collect_snapshots(ctx, role, style, game, every_ticks=300)
        snaps += s
    env = ctx.envs("holdout", 0)[0]
    space = env.action_space
    no_op = space.no_op_action
    bot = ctx.bot("balanced")
    planner = oq_lib.ScriptRolloutPlanner(env, bot, samples=16, script_top=4, horizon=160,
                                          rollout_interval=10, seed=1)

    acc = Acc()
    orig_obs = env.get_structured_observation
    from clasher.battle import BattleState
    import clasher.rl.public_observation as pubobs

    # instance/class-level wrappers (process-local; source untouched)
    orig_clone = BattleState.clone
    orig_step = BattleState.step
    BattleState.clone = lambda self, *a, **k: acc.wrap("clone", orig_clone)(self, *a, **k)
    BattleState.step = lambda self, *a, **k: acc.wrap("engine_step", orig_step)(self, *a, **k)
    env.get_structured_observation = acc.wrap("script:observation", env.get_structured_observation)
    pubobs.project_council_public_observation = acc.wrap(
        "script:public_projection", pubobs.project_council_public_observation)
    bot.select_action = acc.wrap("script:decide", bot.select_action)
    space.apply_action = acc.wrap("apply_action", space.apply_action)
    planner._phi = acc.wrap("phi", planner._phi)

    sampler = CollapsedSampler().start() if args.sample else None
    calls = []
    total_cpu = 0.0
    for b in snaps:
        if len(calls) >= args.calls:
            break
        if b.game_over:
            continue
        for pid in (0, 1):
            if len(calls) >= args.calls:
                break
            real = env.battle
            env.battle = b
            try:
                obs = orig_obs(pid)
                mask = env.get_action_mask(pid, structured_observation=obs)
            finally:
                env.battle = real
            exact = space.legal_action_mask(b, pid) & mask
            exact[no_op] = True
            legal = np.flatnonzero(exact).astype(np.int64)
            if not np.any(legal != no_op):
                continue
            r0, t0, s0 = planner.rollouts, planner.rollout_ticks, planner.script_calls
            c0, w0 = time.process_time(), time.perf_counter()
            with maybe_silence_stdio(True):
                chosen = planner.select_action(b, pid, legal)
            dc, dw = time.process_time() - c0, time.perf_counter() - w0
            total_cpu += dc
            calls.append({"tick": int(b.tick), "pid": pid, "action": int(chosen), "cpu": dc, "wall": dw,
                          "alive": sum(1 for e in b.entities.values() if e.is_alive),
                          "rollouts": planner.rollouts - r0, "ticks": planner.rollout_ticks - t0,
                          "script_calls": planner.script_calls - s0})
            print(calls[-1], flush=True)
    if sampler:
        sampler.stop()
        sampler.dump(RESULTS / f"srp_{args.label}.collapsed")
    # the script's observation build is nested inside _packet; projection/decide too
    parts = {k: v for k, v in acc.cpu.items()}
    parts["other"] = total_cpu - sum(parts.values())
    out = {
        "label": args.label, "calls": calls, "n_calls": len(calls),
        "cpu_per_call_s": total_cpu / max(1, len(calls)),
        "parts_cpu_share": {k: v / total_cpu for k, v in sorted(parts.items(), key=lambda kv: -kv[1])},
        "parts_counts_per_call": {k: v / max(1, len(calls)) for k, v in acc.n.items()},
        "per_unit_ms": {k: 1e3 * acc.cpu[k] / max(1, acc.n[k]) for k in acc.cpu},
        "engine_ticks_per_s_inside": acc.n["engine_step"] / max(1e-9, acc.cpu["engine_step"]),
        "host": host_info(), "peak_rss_mb": peak_rss_mb(),
    }
    if sampler:
        stacks = {s: n for s, n in sampler.stacks.items()}
        step_only = {s: n for s, n in stacks.items() if "battle.py:step" in s}
        out["engine_subsystems_within_step"] = es_classify.classify_engine_stacks(step_only)
    write_json(RESULTS / f"srp_{args.label}.json", out)
    print({k: out[k] for k in ("cpu_per_call_s", "parts_cpu_share", "per_unit_ms", "engine_ticks_per_s_inside")})


if __name__ == "__main__":
    main()
