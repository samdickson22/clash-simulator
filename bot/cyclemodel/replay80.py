"""Offline belief replay of the live battles' opponent-play streams with the cycle model (exploration).

    python -m bot.cyclemodel.replay80 OUT.json --dep G/replay/dep-0.json G/replay/dep-1.json \
        --drops G/cycle-labels/all-435-drops-features.json [--labels G/cycle-labels/sample1-labels-with-features.json ...]

Per battle: the deployed translator's accepted opponent plays (dep-*.json) as 'card' events plus its cycle-conflict
drops (all-435 features) as 'card?' with p = bot.cyclemodel.preal.p_real(features), in tick order, through the planner's
belief class with BOT_CYCLE_MODEL=soft (full-pool prior as live: BOT_BELIEF_PRIOR / rt.belief_prior; default
fullpool:11433651:freq=b53b02a1fde4), polled every 10 ticks as the search does. Per drop: p, outcome (real branch feasible
with k* hidden plays / phantom only), resolver ms; per battle: cycle_stats, rebuilds, errors. With labels: outcome by
verdict. This is the belief side of gate (b); the translator owner's replay + video check is the real gate.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter, defaultdict


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--dep', nargs='+', required=True)
    ap.add_argument('--drops', required=True)
    ap.add_argument('--labels', nargs='*', default=())
    ap.add_argument('--prior', default='fullpool:11433651:freq=b53b02a1fde4')
    ap.add_argument('--cycle', default='soft')
    a = ap.parse_args(argv)
    os.environ['BOT_CYCLE_MODEL'] = a.cycle
    from bot.players.runtime import Runtime
    rt = Runtime()
    rt.belief_prior = a.prior
    from derived_public_state import PublicEvent, DerivedPublicState
    from belief import Belief
    from bot.fullpool.belief import planner_belief
    from bot.cyclemodel.preal import p_real
    prior, cls = planner_belief(rt, Belief)

    drops = defaultdict(list)
    for d in json.load(open(a.drops)):
        drops[d['run']].append(d)
    labels = {}
    for path in a.labels:
        for r in json.load(open(path)):
            if r.get('verdict') in ('real', 'phantom'):
                labels[(r['run'], int(r['tick']), r['card'])] = r['verdict']
    battles = [b for path in a.dep for b in json.load(open(path))['battles']]
    out_b, out_d = [], []
    for b in battles:
        run = b['run']
        items = [(int(p['tick']), 0, 'card', p['card'], None) for p in b['plays']]
        items += [(int(d['tick']), 1, 'card?', d['card'], d) for d in drops.get(run, ())]
        items.sort(key=lambda x: (x[0], x[1]))
        bel = cls.__new__(cls)
        DerivedPublicState.__init__(bel, prior, rt.R.costs)
        bel.__class__ = cls
        events, err, seen = [], None, set()
        pending = list(items)
        last = (items[-1][0] if items else 0) + 10
        try:
            for tick in range(10, last + 10, 10):
                new = []
                while pending and pending[0][0] <= tick:
                    t, _, kind, name, d = pending.pop(0)
                    if d is None:
                        seen.add(name)
                    elif name not in seen and len(seen) >= 8:      # 9th distinct card: the diff never emits it
                        out_d.append(dict(run=run, tick=d['tick'], card=name, kind=d.get('kind'), outcome='ninth',
                                          p=None, k=None, rows=None, update_ms=0., resolver_ms=0.,
                                          verdict=labels.get((run, int(d['tick']), name))))
                        continue
                    amount = 0. if d is None else p_real(d)
                    events.append(PublicEvent(t, kind, name, amount))
                    new.append((len(events) - 1, d, amount))
                if not new:
                    continue
                t0 = time.perf_counter()
                bel.update(tick, list(events))
                ms = 1000 * (time.perf_counter() - t0)
                log = getattr(bel, '_cycle_log', {}) or {}
                for i, d, p in new:
                    if d is None:
                        continue
                    lg = log.get(i, {})
                    outcome = 'phantom_only' if lg.get('phantom_only') else 'real_feasible'
                    out_d.append(dict(run=run, tick=d['tick'], card=d['card'], kind=d.get('kind'),
                                      plays_between=d.get('plays_between'), p=round(p, 4), outcome=outcome,
                                      k=(lg.get('hidden_plays', 0) / p) if p and outcome == 'real_feasible' else None,
                                      rows=lg.get('max_rows'), update_ms=round(ms, 2),
                                      resolver_ms=round(lg.get('max_ms', 0.), 2),
                                      verdict=labels.get((run, int(d['tick']), d['card']))))
        except Exception as ex:
            err = repr(ex)[:300]
        out_b.append(dict(run=run, plays=len(b['plays']), drops=len(drops.get(run, ())), error=err,
                          rebuilds=getattr(bel, 'rebuilds', 0), cycle_stats=bel.cycle_stats, rows=len(bel.states)))
    oc = Counter(d['outcome'] for d in out_d)
    by_v = defaultdict(Counter)
    for d in out_d:
        if d['verdict']:
            by_v[d['verdict']][d['outcome']] += 1
    ms = sorted(d['update_ms'] for d in out_d)
    rms = sorted(d['resolver_ms'] for d in out_d)
    summary = dict(battles=len(out_b), errors=sum(1 for b in out_b if b['error']), drops=len(out_d),
                   outcomes=dict(oc), real_mass=round(sum(d['p'] for d in out_d if d['outcome'] == 'real_feasible'), 1),
                   k=dict(Counter(round(d['k']) for d in out_d if d['k'] is not None)),
                   by_verdict={k: dict(v) for k, v in by_v.items()},
                   update_ms_p50=ms[len(ms) // 2] if ms else None, update_ms_p95=ms[int(.95 * len(ms))] if ms else None,
                   update_ms_max=ms[-1] if ms else None,
                   resolver_ms_p50=rms[len(rms) // 2] if rms else None,
                   resolver_ms_p95=rms[int(.95 * len(rms))] if rms else None, resolver_ms_max=rms[-1] if rms else None, max_rows=max((d['rows'] or 0) for d in out_d) if out_d else 0)
    json.dump(dict(summary=summary, battles=out_b, drops=out_d), open(a.out, 'w'), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
