"""Paired comparison of two eval_rsim candidate arms on the same r2 bank cases (e.g. model sizes): mean score
difference A - B over cases where BOTH arms produced a valid terminal game, each arm also against r2's sealed live
search (f1a2). 20,000-draw PCG64 case bootstrap stratified by opponent controller, equal fixed controller weights,
95% intervals; DEV / selection evidence only.

    python compare_arms.py --a DIR_A --b DIR_B [--out compare.json]       (run under r2's run.sh, like eval_rsim)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def arm_rows(d):
    man = json.loads((Path(d)/'manifest.json').read_text())
    rows = {}
    for p in sorted((Path(d)/'rows').glob(f"*-{man['arm']}.json")):
        r = json.loads(p.read_text())
        ok = ('score' in r and not r.get('error') and not r.get('invalid') and (r.get('result') or {}).get('terminal'))
        rows[r['index']] = (r['opponent'], r['score'] if ok else None)
    return man, rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', required=True)
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)
    ma, ra = arm_rows(a.a)
    mb, rb = arm_rows(a.b)
    if ma['bank_sha256'] != mb['bank_sha256'] or ma['assigned'] != mb['assigned']:
        raise SystemExit('the two arms were not run on the same bank / assignment')
    opps = sorted({o for o, _ in ra.values()} | {o for o, _ in rb.values()})
    diffs = {o: [] for o in opps}
    for i in ma['assigned']:
        if i in ra and i in rb and ra[i][1] is not None and rb[i][1] is not None:
            diffs[ra[i][0]].append(ra[i][1] - rb[i][1])
    rng = np.random.Generator(np.random.PCG64(2026102023))
    out = dict(a=a.a, b=a.b, a_ckpt=ma['ckpt_sha256'], b_ckpt=mb['ckpt_sha256'], assigned=len(ma['assigned']),
               pairs=sum(len(v) for v in diffs.values()),
               by_opponent={o: dict(n=len(v), delta=float(np.mean(v)) if v else None) for o, v in diffs.items()})
    if all(diffs[o] for o in opps):
        point = sum(np.mean(diffs[o]) for o in opps)/len(opps)
        stats = np.zeros(20000)
        for o in opps:
            d = np.array(diffs[o])
            stats += rng.choice(d, size=(20000, len(d))).mean(1)/len(opps)
        out.update(delta=float(point), ci95=[float(np.quantile(stats, .025)), float(np.quantile(stats, .975))])
    else:
        out.update(delta=None, note='a controller stratum has no valid pair')
    print(json.dumps(out, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
