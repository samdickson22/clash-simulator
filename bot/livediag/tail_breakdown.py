"""Where live decision-step time goes (s74): per battle, step p95 and the slow-step breakdown."""
import json, sys, statistics as st
from pathlib import Path
def pct(xs, q):
    xs = sorted(xs); return xs[min(len(xs)-1, int(q*len(xs)))] if xs else None
for run in sys.argv[1:]:
    run = Path(run)
    units = {}
    for l in open(run/'perception.jsonl'):
        f = json.loads(l); units[f['n']] = len(f.get('units') or [])
    D = [json.loads(l) for l in open(run/'decisions.jsonl')]
    steps = [d['step_ms'] for d in D]
    srch = [d for d in D if d.get('stats') and d['stats'].get('source') == 'search']
    p95 = pct(steps, .95)
    slow = [d for d in D if d['step_ms'] >= p95]
    def agg(rows, key): 
        v = [r['stats'].get(key) for r in rows if r.get('stats') and r['stats'].get(key) is not None]
        return round(st.median(v), 1) if v else None
    print(f"{run.parent.name}/{run.name}: n={len(D)} step p50={pct(steps,.5):.1f} p95={p95:.1f} max={max(steps):.1f} "
          f"search n={len(srch)} hits={sum(bool(d['stats'].get('hit')) for d in srch)}")
    for lab, rows in (('slow(>=p95)', slow), ('search(all)', srch)):
        ss = [r for r in rows if r.get('stats')]
        ov = [r['step_ms'] - r['stats']['wall_ms'] for r in ss if r['stats'].get('wall_ms') is not None]
        print(f"  {lab:12s} n={len(rows)} searched={len(ss)} cand={agg(rows,'candidates')} roll={agg(rows,'rollouts')} "
              f"native={agg(rows,'native_rollouts')} learned={agg(rows,'learned_rollouts')} wall={agg(rows,'wall_ms')} "
              f"cpu={agg(rows,'cpu_ms')} overhead(step-wall) med={st.median(ov) if ov else None and 0:.1f} units={st.median([units.get(r['n'],0) for r in rows])}")
    # by unit-count bucket: search wall p95
    for lo, hi in ((0,6),(6,11),(11,16),(16,99)):
        b = [d for d in srch if lo <= units.get(d['n'],0) < hi]
        if b: print(f"  units {lo:2d}-{hi-1:2d}: n={len(b):3d} wall p50={pct([d['stats']['wall_ms'] for d in b],.5):5.1f} p95={pct([d['stats']['wall_ms'] for d in b],.95):5.1f} "
                    f"step p95={pct([d['step_ms'] for d in b],.95):5.1f} cand p50={pct([d['stats']['candidates'] for d in b],.5)} learned p95={pct([d['stats'].get('learned_rollouts',0) for d in b],.95)}")
