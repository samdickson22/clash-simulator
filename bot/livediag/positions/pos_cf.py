"""Live position replay + counterfactual lines (cycle-model owner; live-diag analysis, read-only on the run dir).

Replays a live run through fp_mac_bench.bench_run (live-diag's trace harness) with PLAYER and, at the first search
with tick >= --tick, records the root candidates and final scores (core.last) and the chosen action. With --lines it
then plays counterfactual lines from that decision's root (the planner's native BattleState, its belief sample):
each line forces our actions at tick offsets (others: our side WAITS until --free-from, then the native 'balanced'
script, as in the search's rollouts); the opponent is the search's learned rollout opponent (make_opp(j), CRN
sample j = the seed index). Each line runs to a terminal state or --horizon ticks; it records native.evaluate at
+600 ticks and at the end, and per-side tower HP (BattleState.snapshot) at +600 ticks and at the end.
Then the replay stops (no further decisions).

    python pos_cf.py --bench FP_MAC_BENCH --code TREE --player NAME --run RUN --tick 270 --out OUT.json \
        [--levels own=11,opp=11,own_tower=10,opp_tower=12,own_bodies=Skeleton:10;Cannon:12] \
        [--lines 'a=0:1983;b=101:1857' --free 'a=0,b=101' --seeds 30 --horizon 6000]
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path

WAIT = 2304


class Stop(SystemExit):        # control exception: the live player re-raises it (player._reraise_control)
    pass


def towers(sim):
    """{owner: {tower name: hp}} for the live tower entities in BattleState.snapshot() (dead towers are absent)."""
    snap = sim.snapshot()
    snap = json.loads(snap) if isinstance(snap, str) else snap
    out = {}
    for e in snap.get('entities', []):
        st = e.get('stats') or {}
        name = ' '.join(str(x) for x in (st.get('name'), st.get('payload_key'), e.get('class')) if x)
        if 'Tower' in name and e.get('alive', True):
            side = 'L' if e.get('x', 9) < 9 else 'R' if e.get('x', 9) > 9 else 'K'
            out.setdefault(str(e.get('owner')), {})[f'{name}:{side}'] = float(e.get('hp', 0))
    return out


def run_line(native, root, seat, forced, free_from, make_opp, j, horizon, cd, od, t0):
    sim = root.clone()
    opp = 1 - seat
    learned = make_opp(j)
    own = None
    oq = None
    plan = sorted(forced)
    rec = {}
    k = 0
    step = 5
    while k < horizon:
        while plan and plan[0][0] <= k and own is None:
            own = (k + cd, plan.pop(0)[1])
        if own is None and k >= free_from and not plan and k % 10 == 0:
            a = native.select_action(sim, seat, 'balanced')
            if a != WAIT:
                own = (k + cd, a)
        if oq is None and k % learned.interval == 0:
            a = learned.decide(native, [sim], [0], opp, t0 + k)[0]
            if a != WAIT:
                oq = (k + od, a)
        end = k + step
        cur = k
        while True:
            if own is not None and own[0] <= cur:
                native.apply_discrete(sim, seat, own[1])
                own = None
            if oq is not None and oq[0] <= cur:
                native.apply_discrete(sim, opp, oq[1])
                oq = None
            nxt = min([q[0] for q in (own, oq) if q is not None and cur < q[0] < end] + [end])
            sim.step(nxt - cur)
            cur = nxt
            if cur >= end:
                break
        k = end
        if k == 600:
            rec['v600'] = float(native.evaluate(sim, seat, 1.0))
            rec['towers600'] = towers(sim)
        if k % 100 == 0:
            v = float(native.evaluate(sim, seat, 1.0))
            if abs(v) >= 2.:
                rec.update(v_end=v, end_k=k, terminal=True, towers_end=towers(sim))
                return rec
    rec.update(v_end=float(native.evaluate(sim, seat, 1.0)), end_k=k, terminal=False, towers_end=towers(sim))
    return rec


def main():
    ap = argparse.ArgumentParser()
    for k in ('--bench', '--code', '--player'):
        ap.add_argument(k, required=True)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--tick', type=float, required=True)
    ap.add_argument('--levels', default='')
    ap.add_argument('--lines', default='')
    ap.add_argument('--free', default='')
    ap.add_argument('--seeds', type=int, default=30)
    ap.add_argument('--horizon', type=int, default=6000)
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location('fpb', a.bench)
    fpb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fpb)
    os.environ.setdefault('LL_HANDSYNC', '1')
    code = fpb.use_code(a.code)
    drive = fpb.load_drive(code, ['cv2'])
    from bot.players.runtime import Runtime
    import bot.search.lopp_fast as lf
    rt = Runtime()
    names = rt.R.builder.token_names
    if a.levels:
        from bot.live.levels import Levels, LevelRoot
        kw = {}
        for part in a.levels.split(','):
            k, _, v = part.partition('=')
            if k in ('own_bodies', 'opp_bodies'):
                kw[k] = {b: int(l) for b, _, l in (x.partition(':') for x in v.split(';') if x)}
            else:
                kw[k] = int(v)
        lv = Levels(**kw)
        rt.R.root = LevelRoot(rt.R, lv).root
        print('levels', lv)
    out = dict(player=a.player, tick=a.tick, levels=a.levels)
    orig = lf.reduce_fast

    def wrapped(core, root, seat, candidates, **kw):
        best, info = orig(core, root, seat, candidates, **kw)
        t = float(core.info.tick)
        if t < a.tick or 'decision' in out:
            return best, info
        obs = core.info.packet.observation
        hand = [names[int(x)] if int(x) > 0 else None for x in list(obs.hand_ids)[:4]]
        last = getattr(core, 'last', None) or {}
        cands = sorted(([int(c), (hand[int(c) // 576] if int(c) < WAIT else None), s]
                        for c, s in zip(last.get('candidates', []), last.get('scores', []))), key=lambda x: -x[2])
        out['decision'] = dict(tick=t, seat=seat, elixir=float(obs.global_features[5]) * 10, hand=hand,
                               best=int(best), best_card=hand[int(best) // 576] if int(best) < WAIT else None,
                               candidates=cands, prior=getattr(core, 'prior_counts', None))
        out['towers0'] = towers(root)
        if a.lines:
            free = {k: int(v) for k, _, v in (x.partition('=') for x in a.free.split(','))}
            res = {}
            for part in a.lines.split(';'):
                name, _, acts = part.partition('=')
                forced = [(int(o), int(x)) for o, _, x in (y.partition(':') for y in acts.split('+'))]
                res[name] = [run_line(core.native, root, seat, forced, free[name], kw['make_opp'], j, a.horizon,
                                      core.command_delay, core.opponent_delay, int(t)) for j in range(a.seeds)]
            out['lines'] = res
        raise Stop()

    lf.reduce_fast = wrapped
    try:
        fpb.bench_run(drive, rt, a.player, a.run, None)
    except Stop:
        pass
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print('wrote', a.out, 'decision' in out, list(out.get('lines', {})))


if __name__ == '__main__':
    main()
