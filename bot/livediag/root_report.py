"""Summarise root_scores counterfactual rows: does the preferred action (wait-class vs play) flip with our command delay
or with true levels? (bot lead live-diag, exploration)

    python3 -m bot.livediag.root_report ROOTS/*.jsonl

Per cf row: keys[0] = the search's choice (a play, WAIT or a timed wait), keys[1] = WAIT, the rest the defence set.
'defend - wait' = best play key score - best wait-class key score. L11 reference for the level comparison: d27 on the
search's own sample (lv_resampled == 0) or lv11 on the re-drawn sample.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

WAIT = 2304


def margin(keys, s):
    plays = [v for k, v in zip(keys, s) if k < WAIT]
    waits = [v for k, v in zip(keys, s) if k >= WAIT]
    return (max(plays) - max(waits)) if plays and waits else None


def argmax(s):
    return max(range(len(s)), key=lambda i: s[i])


def main(paths):
    rows = [json.loads(l) for p in paths for l in open(p) if '"kind": "cf"' in l]
    out = dict(rows=len(rows))
    flips = Counter()
    lvm, l11m, giant_rows = [], [], 0
    for r in rows:
        keys = r['keys']
        has_play = any(k < WAIT for k in keys)
        if not has_play:
            flips['no_affordable_play'] += 1
            continue
        base = r['d27']
        for d in (5, 10, 20, 40):
            s = r.get(f'd{d}')
            if s and (margin(keys, s) > 0) != (margin(keys, base) > 0):
                flips[f'delay{d}_class_flip'] += 1
            if s and argmax(s) != argmax(base):
                flips[f'delay{d}_any_flip'] += 1
        if 'lv' in r:
            ref = r['lv11'] if r.get('lv_resampled') else base
            m11, mlv = margin(keys, ref), margin(keys, r['lv'])
            l11m.append(m11); lvm.append(mlv)
            flips['lv_rows'] += 1
            if (mlv > 0) != (m11 > 0):
                flips['lv_class_flip'] += 1
                flips['lv_flip_to_' + ('defend' if mlv > 0 else 'wait')] += 1
            if argmax(r['lv']) != argmax(ref):
                flips['lv_any_flip'] += 1
            if r.get('giant'):
                giant_rows += 1
                if (mlv > 0) != (m11 > 0):
                    flips['lv_class_flip_giant_visible'] += 1
    flips['with_play'] = len(rows) - flips['no_affordable_play']
    out['counts'] = dict(flips)
    out['giant_visible_lv_rows'] = giant_rows
    if lvm:
        d = sorted(b - a for a, b in zip(l11m, lvm))
        out['defend_minus_wait_shift_lv_minus_l11'] = dict(p10=round(d[len(d)//10], 4), p50=round(d[len(d)//2], 4),
                                                            p90=round(d[9*len(d)//10], 4),
                                                            mean=round(sum(d)/len(d), 4))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main(sys.argv[1:])
