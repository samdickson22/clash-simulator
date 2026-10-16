"""Compact table of eval_official.py outputs: per checkpoint, GS/TC id x owner and owner-only P/R (<=1 tile), empty-frame FPs.

  python summarize_evals.py NAME=EVAL.json ...
"""
import json
import sys

print('| model | thr | GS id P/R | GS owner P/R | TC id P/R | TC owner P/R | empty FP/frame GS-live5 / GS-other / TC |')
print('|---|---|---|---|---|---|---|')
for arg in sys.argv[1:]:
    name, path = arg.split('=', 1); d = json.loads(open(path).read())
    for t in ('0.4', '0.5', '0.6'):
        m = d['metrics'][f'thr{t}_r1.0']
        f = lambda k: f"{m[k]['P']:.3f} / {m[k]['R']:.3f}" if k in m else '-'
        e = d.get('empty', {}).get('by_arena', {})
        emp = ' / '.join(f"{e[g][f'thr{t}']:.2f}" for g in ('GS-live5(unseen match)', 'GS-other', 'TC') if g in e)
        print(f"| {name} | {t} | {f('GS:id')} | {f('GS:owner')} | {f('TC:id')} | {f('TC:owner')} | {emp} |")
