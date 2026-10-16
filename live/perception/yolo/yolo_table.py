"""Compact table of eval_yolo.py outputs: NAME=EVAL.json ... -> per threshold GS/TC/BP id P/R, owner P/R (all), empty false units."""
import json
import sys

print('| model | thr | GS id P/R | TC id P/R | BP id P/R | BB id P/R | all id P/R | all owner P/R | empty FP/frame |')
print('|---|---|---|---|---|---|---|---|---|')
for arg in sys.argv[1:]:
    name, path = arg.split('=', 1); d = json.loads(open(path).read())
    for t in ('0.3', '0.4', '0.5', '0.6'):
        m = d['metrics'].get(f'thr{t}_r1.0')
        if not m:
            continue
        f = lambda k: f"{m[k]['P']:.3f}/{m[k]['R']:.3f}" if k in m else '-'
        print(f"| {name} | {t} | {f('GS:id')} | {f('TC:id')} | {f('BP:id')} | {f('BB:id')} | {f('all:id')} | {f('all:owner')} | {d['empty'].get(f'thr{t}', '-')} |")
