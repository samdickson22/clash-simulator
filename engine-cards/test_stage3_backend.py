"""Default-path preservation and timed complete calls through the opt-in flag."""

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import hashlib
import json
from pathlib import Path
import sys
import time
import cloudpickle
import numpy as np
from differential import ES, battle_digest
from test_stage3 import fingerprint
from clasher.rl.script_rollout_planner import ScriptRolloutPlanner

sys.path.insert(0, str(ES / "srp_reference"))
from oq_lib import Context

spec = spec_from_file_location(
    "clasher.rl._stage3_default_reference",
    Path("engine-rs/evidence-stage3/script_rollout_planner.before-native.py").resolve(),
)
reference = module_from_spec(spec)
spec.loader.exec_module(reference)


def run(cls, env, bot, sb, b, seat, legal, seed, backend=None, trace=True):
    kwargs = dict(
        samples=16,
        script_top=4,
        horizon=160,
        rollout_interval=10,
        seed=seed,
        opponent_model=sb,
    )
    if backend is not None:
        kwargs["backend"] = backend
    planner = cls(env, bot, **kwargs)
    events = []
    leaves = []
    rows = []
    if trace:
        original_model = planner._model_action
        original_phi = planner._phi
        original_rollout = planner._rollout

        def model(sim, actor, planning):
            move = original_model(sim, actor, planning)
            events.append([sim.tick, actor, move, battle_digest(sim)])
            return move

        def phi(sim, actor):
            score = original_phi(sim, actor)
            leaves.append(battle_digest(sim))
            return score

        planner._model_action = model
        planner._phi = phi
        if backend == "native":
            native = planner._native_scripts

            class Capture:
                def rollout(self, *args):
                    result = native.rollout(*args, True)
                    events.extend([list(v) for v in result[4]])
                    leaves.append(result[5])
                    return result

            planner._native_scripts = Capture()

        def rollout(root, actor, action, other):
            events.clear()
            before = planner.rollout_ticks
            score = original_rollout(root, actor, action, other)
            rows.append(
                dict(
                    action=action,
                    other=other,
                    value=score.hex(),
                    ticks=planner.rollout_ticks - before,
                    trace=list(events),
                    leaf=leaves[-1],
                )
            )
            return score

        planner._rollout = rollout
    start = time.process_time()
    action = planner.select_action(b, seat, legal)
    cpu = time.process_time() - start
    counters = {
        k: getattr(planner, k)
        for k in (
            "rollouts",
            "rollout_ticks",
            "script_calls",
            "observation_skips",
            "overrides",
        )
    }
    return dict(
        action=action,
        counters=counters,
        trace_sha256=hashlib.sha256(
            json.dumps(rows, sort_keys=True).encode()
        ).hexdigest(),
    ), cpu


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls", type=int, default=12)
    ap.add_argument("--output", type=Path, default=ES / "results/stage3_backend.json")
    args = ap.parse_args()
    ctx = Context()
    env = ctx.envs("holdout", 0)[0]
    bot = ctx.bot("balanced")
    sb = ctx.strategy_bot("balanced")
    roots = cloudpickle.loads(
        (
            Path.home() / ".cache/clasher-engine-speed/stage3-srp-search-snapshots.pkl"
        ).read_bytes()
    )
    qualified = json.loads((ES / "results/stage3_search_rollouts_a.json").read_text())[
        "results"
    ]
    results = []
    for i in range(args.calls):
        q = qualified[str(i)]
        b = roots[q["root_index"]]
        seat = q["seat"]
        env.battle = b
        legal = np.flatnonzero(
            env.action_space.legal_action_mask(b, seat) & env.get_action_mask(seat)
        )
        expected, _ = run(
            reference.ScriptRolloutPlanner, env, bot, sb, b, seat, legal, 51000 + i
        )
        # No backend argument: test the actual default constructor path.
        default, _ = run(ScriptRolloutPlanner, env, bot, sb, b, seat, legal, 51000 + i)
        native, _ = run(
            ScriptRolloutPlanner,
            env,
            bot,
            sb,
            b,
            seat,
            legal,
            51000 + i,
            backend="native",
        )
        assert expected == default == native, (i, expected, default, native)
        assert expected["trace_sha256"] == q["trace_sha256"], (
            i,
            "saved qualification trace",
        )
        # Measure uninstrumented complete select_action, including native root import.
        py, pcpu = run(
            ScriptRolloutPlanner, env, bot, sb, b, seat, legal, 51000 + i, trace=False
        )
        rust, rcpu = run(
            ScriptRolloutPlanner,
            env,
            bot,
            sb,
            b,
            seat,
            legal,
            51000 + i,
            backend="native",
            trace=False,
        )
        assert py == rust, (i, py, rust)
        row = dict(
            call=i,
            root_index=q["root_index"],
            seat=seat,
            python_cpu=pcpu,
            native_cpu=rcpu,
            trace=expected,
        )
        results.append(row)
        out = dict(
            fingerprint=fingerprint(),
            driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            results=results,
            python_cpu_per_call=sum(x["python_cpu"] for x in results) / len(results),
            native_cpu_per_call=sum(x["native_cpu"] for x in results) / len(results),
            speedup=sum(x["python_cpu"] for x in results)
            / sum(x["native_cpu"] for x in results),
        )
        tmp = args.output.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=2) + "\n")
        tmp.replace(args.output)
        print(
            "backend",
            i,
            "PASS",
            round(pcpu, 4),
            round(rcpu, 4),
            round(pcpu / rcpu, 2),
            flush=True,
        )
    assert out["speedup"] >= 20, out["speedup"]
    print(
        "PASS",
        args.calls,
        "default/reference/native traces; speedup",
        out["speedup"],
        flush=True,
    )


if __name__ == "__main__":
    main()
