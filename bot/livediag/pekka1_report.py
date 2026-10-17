"""PEKKA-1 readout (reports/bot/live-diag/PEKKA1-PREREG.md): the pre-registered statistics, read once all rows are in.

    python3 -m bot.livediag.pekka1_report --l16 DIR --account DIR [--exclude-run s74-m16] [--json OUT]

Per row x stratum x arm: score with a bootstrap 95 % CI, reaction p50 / p90, and undefended Hog / Battle Ram pushes
(an accepted opponent HogRider or BattleRam play with no accepted play of ours in the next 100 ticks): the mean per battle
and the share of such plays. Predictions:
  1. account row, res-wintp: score(pekka) - score(control); CI from independent bootstraps of the two strata;
  2. per row: paired delta(res-wintp - res) on pekka, by case index; CI over cases;
  3. per row x arm: undefended pushes per battle, pekka vs control.
Bootstrap: 10,000 resamples, seed 0. --exclude-run gives the pre-announced sensitivity cut (s74-m16, unmapped hut goblins).
"""
from __future__ import annotations

import argparse
import glob
import json
import random

PUSH = ('HogRider', 'BattleRam')
WINDOW = 100     # ticks (5.0 s)
B = 10000


def load(d, exclude):
    rows, bad = [], 0
    for p in glob.glob(d + '/rows/*.json'):
        r = json.load(open(p))
        if r.get('error') or 'result' not in r:
            bad += 1
            continue
        if r.get('source_run') in exclude:
            continue
        rows.append(r)
    return rows, bad


def score(r):
    return .5 if r.get('draw') else float(r.get('win') or 0)


def pushes(r):
    seat = r['seat']
    log = r['result']['play_log']
    ours = sorted(t for t, _, _, ok in log[str(seat)] if ok)
    theirs = [t for t, c, _, ok in log[str(1 - seat)] if ok and c in PUSH]
    und = sum(1 for t in theirs if not any(t < u <= t + WINDOW for u in ours))
    return und, len(theirs)


def boot_mean(xs, seed=0):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(B))
    return round(sum(xs) / len(xs), 4), [round(m[int(.025 * B)], 4), round(m[int(.975 * B) - 1], 4)]


def boot_diff(a, b, seed=0):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(a) for _ in a) / len(a) - sum(rng.choice(b) for _ in b) / len(b) for _ in range(B))
    return round(sum(a) / len(a) - sum(b) / len(b), 4), [round(m[int(.025 * B)], 4), round(m[int(.975 * B) - 1], 4)]


def q(xs, f):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(f * len(xs)))], 2) if xs else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--l16', required=True)
    ap.add_argument('--account', required=True)
    ap.add_argument('--exclude-run', default='')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    exclude = set(filter(None, a.exclude_run.split(',')))
    out = dict(exclude=sorted(exclude), rows={}, predictions={})
    for row, d in (('l16', a.l16), ('account', a.account)):
        rows, bad = load(d, exclude)
        cells = {}
        for r in rows:
            cells.setdefault((r['stratum'], r['player']), []).append(r)
        res = dict(unusable_rows=bad, issues=sum(bool(r.get('issues')) for r in rows), cells={})
        for (st, pl), rs in sorted(cells.items()):
            und = [pushes(r) for r in rs]
            react = [x for r in rs for x in r['result']['public_diagnostics'][str(r['seat'])]['reaction_s']]
            res['cells'][f'{st}/{pl}'] = dict(
                n=len(rs), score=boot_mean([score(r) for r in rs]), reaction_p50_p90=[q(react, .5), q(react, .9)],
                undefended_per_battle=round(sum(u for u, _ in und) / len(rs), 3),
                undefended_share=round(sum(u for u, _ in und) / max(1, sum(n for _, n in und)), 3),
                hog_ram_plays_per_battle=round(sum(n for _, n in und) / len(rs), 2),
                decks=sorted({r['source_run'] for r in rs}))
        pk = {r['index']: r for r in rows if r['stratum'] == 'pekka' and r['player'] == 'res-wintp'}
        pr = {r['index']: r for r in rows if r['stratum'] == 'pekka' and r['player'] == 'res'}
        k = sorted(set(pk) & set(pr))
        res['p2_delta_wint_minus_res_pekka'] = dict(n=len(k), **dict(zip(('mean', 'ci'),
                                                      boot_mean([score(pk[i]) - score(pr[i]) for i in k]))))
        out['rows'][row] = res
        if row == 'account':
            w = [r for r in rows if r['player'] == 'res-wintp']
            out['predictions']['p1_account_wint_pekka_minus_control'] = dict(zip(('mean', 'ci'), boot_diff(
                [score(r) for r in w if r['stratum'] == 'pekka'], [score(r) for r in w if r['stratum'] == 'control'])))
    p1 = out['predictions']['p1_account_wint_pekka_minus_control']
    out['predictions']['p1_holds'] = p1['mean'] <= -0.10
    for row in ('l16', 'account'):
        d = out['rows'][row]['p2_delta_wint_minus_res_pekka']
        out['predictions'][f'p2_{row}'] = dict(d, holds=d['mean'] >= -0.03, wint_implicated=d['ci'][1] < 0)
        c = out['rows'][row]['cells']
        out['predictions'][f'p3_{row}'] = {pl: dict(pekka=c.get(f'pekka/{pl}', {}).get('undefended_per_battle'),
                                                    control=c.get(f'control/{pl}', {}).get('undefended_per_battle'))
                                           for pl in ('res-wintp', 'res')}
        for pl, v in out['predictions'][f'p3_{row}'].items():
            v['holds'] = None if None in v.values() else v['pekka'] > v['control']
    print(json.dumps(out, indent=1))
    if a.json:
        open(a.json, 'w').write(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
