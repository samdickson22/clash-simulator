"""Exact recorded SRP candidate, leaf, continuation and counter differential."""

import argparse
from dataclasses import astuple
import hashlib
import json
from pathlib import Path
import sys
import time
import cloudpickle
import numpy as np
import clasher_core
from differential import ES, config, snapshot, battle_digest
from stage2_matches import PILOT
from test_stage3 import metadata, fingerprint
from clasher.rl.script_rollout_planner import ScriptRolloutPlanner
from clasher.rl.reward_model import potential_breakdown_p0

sys.path.insert(0, str(ES / "srp_reference"))
from oq_lib import Context


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls", type=int, default=200)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--searchable", action="store_true")
    ap.add_argument("--corpus", type=Path)
    ap.add_argument("--output", type=Path, default=ES / "results/stage3_rollouts.json")
    args = ap.parse_args()
    ctx = Context()
    env = ctx.envs("holdout", 0)[0]
    bot = ctx.bot("balanced")
    sb = ctx.strategy_bot("balanced")
    cfg = config(PILOT)
    native = clasher_core.NativeScripts(json.dumps(metadata(bot.builder)))
    corpus = args.corpus or (
        Path.home()
        / ".cache/clasher-engine-speed"
        / (
            "stage3-srp-search-snapshots.pkl"
            if args.searchable
            else "stage3-srp-snapshots.pkl"
        )
    )
    roots = cloudpickle.loads(corpus.read_bytes())
    out = dict(
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        fingerprint=fingerprint(),
        corpus_sha256=hashlib.sha256(corpus.read_bytes()).hexdigest(),
        results={},
    )
    if args.output.exists():
        prev = json.loads(args.output.read_text())
        if prev["fingerprint"] == out["fingerprint"]:
            out = prev
    work = []
    for root_index, b in enumerate(roots):
        seats = (
            (root_index % 2, 1 - root_index % 2)
            if args.searchable
            else (root_index % 2,)
        )
        for seat in seats:
            env.battle = b
            legal = np.flatnonzero(
                env.action_space.legal_action_mask(b, seat) & env.get_action_mask(seat)
            )
            if args.searchable and not np.any(legal != 2304):
                continue
            work.append((root_index, b, seat, legal))
            break
        if len(work) >= args.calls:
            break
    assert len(work) >= args.calls, (
        "not enough qualifying roots",
        len(work),
        args.calls,
    )
    print(
        "Selected", len(work), "distinct roots, searchable", args.searchable, flush=True
    )
    for i, (root_index, b, seat, legal) in enumerate(work):
        if i < args.start or str(i) in out["results"]:
            continue
        env.battle = b
        rb = clasher_core.BattleState(snapshot(b, cfg))
        rb.set_public_movement_speeds(
            [
                (
                    e.id,
                    float(
                        e.original_speed if e.original_speed is not None else e.speed
                    ),
                )
                for e in b.entities.values()
                if type(e).__name__ == "Troop"
            ]
        )
        pp = list(astuple(potential_breakdown_p0(b)))
        rp = native.evaluation_parts(rb)
        assert pp == rp, (
            "root potential",
            i,
            [(k, x.hex(), y.hex()) for k, (x, y) in enumerate(zip(pp, rp)) if x != y],
        )
        kwargs = dict(
            samples=16,
            script_top=4,
            horizon=160,
            rollout_interval=10,
            seed=51000 + i,
            opponent_model=sb,
        )
        planner = ScriptRolloutPlanner(env, bot, **kwargs)
        events = []
        leaves = []
        expected = []
        model = planner._model_action
        phi = planner._phi
        rollout = planner._rollout

        def model_action(sim, actor, planning):
            move = model(sim, actor, planning)
            events.append([sim.tick, actor, move, battle_digest(sim)])
            return move

        def evaluate(sim, actor):
            value = phi(sim, actor)
            leaves.append([value.hex(), battle_digest(sim)])
            return value

        def python_rollout(root, actor, action, other):
            events.clear()
            before = planner.rollout_ticks
            value = rollout(root, actor, action, other)
            expected.append(
                dict(
                    action=action,
                    other=other,
                    value=value.hex(),
                    ticks=planner.rollout_ticks - before,
                    trace=list(events),
                    leaf=leaves[-1][1],
                )
            )
            return value

        planner._model_action = model_action
        planner._phi = evaluate
        planner._rollout = python_rollout
        start = time.process_time()
        chosen = planner.select_action(b, seat, legal)
        pcpu = time.process_time() - start
        candidate = ScriptRolloutPlanner(env, bot, **kwargs)
        actual = []

        def native_rollout(root, actor, action, other):
            value, ticks, calls, skips, trace, digest = native.rollout(
                rb, actor, action, other, "balanced", "sb-balanced", 160, 10, 1.0, True
            )
            candidate.rollouts += 1
            candidate.rollout_ticks += ticks
            candidate.script_calls += calls
            candidate.observation_skips += skips
            actual.append(
                dict(
                    action=action,
                    other=other,
                    value=value.hex(),
                    ticks=ticks,
                    trace=[list(v) for v in trace],
                    leaf=digest,
                )
            )
            return value

        candidate._rollout = native_rollout
        start = time.process_time()
        got = candidate.select_action(b, seat, legal)
        rcpu = time.process_time() - start
        if actual != expected or chosen != got:
            failure = dict(
                root=i,
                seat=seat,
                tick=b.tick,
                chosen=chosen,
                got=got,
                expected=expected,
                actual=actual,
            )
            (ES / "results/stage3_rollout_failure.json").write_text(
                json.dumps(failure, indent=2) + "\n"
            )
            Path("engine-rs/evidence-stage3/rollout_failure.pkl").write_bytes(
                cloudpickle.dumps(b)
            )
            first = next(
                (j for j, (p, r) in enumerate(zip(expected, actual)) if p != r), None
            )
            raise AssertionError(
                ("rollout", i, seat, first, "details in stage3_rollout_failure.json")
            )
        for key in (
            "rollouts",
            "rollout_ticks",
            "script_calls",
            "observation_skips",
            "overrides",
        ):
            assert getattr(planner, key) == getattr(candidate, key), (
                i,
                key,
                getattr(planner, key),
                getattr(candidate, key),
            )
        out["results"][str(i)] = dict(
            root_index=root_index,
            root_digest=battle_digest(b),
            seat=seat,
            tick=b.tick,
            chosen=chosen,
            candidates=len(expected),
            python_cpu=pcpu,
            native_cpu=rcpu,
            trace_sha256=hashlib.sha256(
                json.dumps(expected, sort_keys=True).encode()
            ).hexdigest(),
            rollout_ticks=planner.rollout_ticks,
            continuation_actions=sum(len(x["trace"]) for x in expected),
        )
        tmp = args.output.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=2) + "\n")
        tmp.replace(args.output)
        print(
            "call",
            i,
            "PASS",
            len(expected),
            "candidates",
            round(pcpu, 3),
            round(rcpu, 3),
            flush=True,
        )
    print("PASS", len(out["results"]), "calls", flush=True)


if __name__ == "__main__":
    main()
