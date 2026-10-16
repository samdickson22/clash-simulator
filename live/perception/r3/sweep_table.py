"""Threshold sweep + per-card recall tables from eval_official.py outputs.

  python sweep_table.py NAME=EVAL.json ...
"""
import json
import sys

EG = ('GS-live5(unseen match)', 'GS-other', 'TC', 'BP')
runs = [(a.split('=', 1)[0], json.loads(open(a.split('=', 1)[1]).read())) for a in sys.argv[1:]]
AR = [a for a in ('GS', 'TC', 'BP', 'BB') if any(f'{a}:id' in d['metrics']['thr0.5_r1.0'] for _, d in runs)]
print('| model | thr | '+' | '.join(f'{a} id P/R (FP/frame) | {a} owner P/R' for a in AR)+' | empty false units/frame '+' / '.join(EG)+' |')
print('|---|---|'+'---|---|'*len(AR)+'---|')
for name, d in runs:
    for t in ('0.3', '0.35', '0.4', '0.45', '0.5', '0.6'):
        m = d['metrics'].get(f'thr{t}_r1.0')
        if not m:
            continue
        f = lambda k, fp=False: (f"{m[k]['P']:.3f} / {m[k]['R']:.3f}"+(f" ({m[k]['fp_per_frame']:.2f})" if fp else '')) if k in m else '-'
        e = d.get('empty', {}).get('by_arena', {})
        emp = ' / '.join(f"{e[g][f'thr{t}']:.2f}" if g in e and f'thr{t}' in e[g] else '-' for g in EG)
        print(f"| {name} | {t} | "+' | '.join(f"{f(a+':id', True)} | {f(a+':owner')}" for a in AR)+f" | {emp} |")
print()
for t in ('0.4', '0.5'):
    print(f'Per-card recall (identity x owner, <=1 tile, thr {t}); hits/n')
    cards = sorted({c for _, d in runs for ar in AR for c in d['metrics'][f'thr{t}_r1.0'].get(f'{ar}:card', {})})
    print('| card | '+' | '.join(f'{n} {a}' for n, _ in runs for a in AR)+' |')
    print('|---|'+'---|'*(len(AR)*len(runs)))
    for c in cards:
        row = []
        for _, d in runs:
            for ar in AR:
                h, n = d['metrics'][f'thr{t}_r1.0'].get(f'{ar}:card', {}).get(c, [0, 0])
                row.append(f'{h}/{n}' if n else '-')
        print(f'| {c} | '+' | '.join(row)+' |')
    print()
