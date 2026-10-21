"""Paired comparison of two eval_rsim candidate arms (e.g. model sizes) on the same r2 bank assignment.

    (under r2's run.sh)  python compare_arms.py --a DIR_A --b DIR_B [--out compare.json]

Provenance (Sol R10): both run manifests must agree on bank, assignment, runtime pins and external identity; every
row is validated as eval_rsim.summarise does (checkpoint / bank hash, assigned-case identity, runtime pins, and module
origins for rows claiming validity). Strata are the assigned cases' opponent controllers with equal fixed weights.

Reported: each arm's failures / not-run counts; the complete-pair mean of A - B over cases where both produced a
valid terminal game; all-assigned bounds (lower: A failures 0 and B failures 1; upper: the reverse); 20,000-draw PCG64
case bootstrap stratified by controller, 95% intervals. DEV evidence; exploratory across several comparisons.

PRE-DECLARED selection rule (coordinator 2026-10-21, "prefer the bigger model only if it wins on games"): a bigger
size A WINS over the smaller B iff the complete-pair 95% lower bound of A - B is > 0 AND the all-assigned lower-bound
point estimate is > 0. Otherwise the smaller size is kept.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_rsim as E  # noqa: E402  (validators only; importing it does not import the bot package)


def arm(d, bank_cases):
    man = json.loads((Path(d)/'manifest.json').read_text())
    scores, failed = {}, 0
    for i in man['assigned']:
        p = Path(d)/'rows'/f"{i:04}-{man['arm']}.json"
        if not p.exists():
            scores[i] = None
            continue
        r = json.loads(p.read_text())
        c = bank_cases[i]
        if (r.get('ckpt_sha256') != man['ckpt_sha256'] or r.get('bank_sha256') != man['bank_sha256']
                or not E.same_case(r, c) or r.get('runtime_pins') != man['runtime_pins']):
            raise SystemExit(f'{p}: row does not match its run manifest / assigned case / runtime pins')
        ok = ('score' in r and not r.get('error') and not r.get('invalid') and (r.get('result') or {}).get('terminal'))
        if ok:
            good, why = E.origins_valid(r.get('module_origins_after'))
            if not good:
                raise SystemExit(f'{p}: row claims validity but its provenance fails ({why})')
        scores[i] = r['score'] if ok else None
        failed += not ok
    return man, scores, failed


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', required=True)
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)
    import hashlib
    raw = (E.R2/'evaluation/bank.json').read_bytes()
    bank = {c['index']: c for c in json.loads(raw)['cases']}
    ma, sa, fa = arm(a.a, bank)
    mb, sb, fb = arm(a.b, bank)
    for k in ('bank_sha256', 'assigned', 'runtime_pins', 'external_sha256'):
        if ma.get(k) != mb.get(k):
            raise SystemExit(f'the two arms differ in {k}')
    if hashlib.sha256(raw).hexdigest() != ma['bank_sha256']:
        raise SystemExit('the loaded bank differs from the runs\' bank')
    if E.external_identity() != ma['external_sha256']:
        raise SystemExit('the r2 harness / opponent models / RoyaleSim changed since the runs')
    assigned = ma['assigned']
    opps = sorted({bank[i]['opponent'] for i in assigned})
    rng = np.random.Generator(np.random.PCG64(2026102023))

    def estimate(diffs):
        if any(not diffs[o] for o in opps):
            return None, None
        point = sum(np.mean(diffs[o]) for o in opps)/len(opps)
        stats = np.zeros(20000)
        for o in opps:
            d = np.array(diffs[o])
            stats += rng.choice(d, size=(20000, len(d))).mean(1)/len(opps)
        return float(point), [float(np.quantile(stats, .025)), float(np.quantile(stats, .975))]
    res = dict(a=a.a, b=a.b, a_ckpt=ma['ckpt_sha256'], b_ckpt=mb['ckpt_sha256'], assigned=len(assigned),
               a_failed_or_not_run=sum(sa[i] is None for i in assigned), a_failed=fa,
               b_failed_or_not_run=sum(sb[i] is None for i in assigned), b_failed=fb,
               controller_weights={o: 1/len(opps) for o in opps})
    for label, fa_, fb_ in (('complete_pairs', None, None), ('all_assigned_lower', 0.0, 1.0),
                            ('all_assigned_upper', 1.0, 0.0)):
        diffs = {o: [] for o in opps}
        for i in assigned:
            x = sa[i] if sa[i] is not None else fa_
            y = sb[i] if sb[i] is not None else fb_
            if x is None or y is None:
                continue
            diffs[bank[i]['opponent']].append(x - y)
        point, ci = estimate(diffs)
        res[label] = dict(n=sum(len(v) for v in diffs.values()), delta=point, ci95=ci,
                          by_opponent={o: dict(n=len(diffs[o]), delta=float(np.mean(diffs[o])) if diffs[o] else None)
                                       for o in opps})
    cp, lo = res['complete_pairs'], res['all_assigned_lower']
    res['a_wins_by_registered_rule'] = bool(cp['ci95'] is not None and cp['ci95'][0] > 0
                                            and lo['delta'] is not None and lo['delta'] > 0)
    print(json.dumps(res, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1) + '\n')


if __name__ == '__main__':
    main()
