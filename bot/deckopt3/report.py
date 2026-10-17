"""DECK SEARCH v3 readout: paired deck arms per row (screen, A, B, C, D) from driver rows (OUT/rows/*.json).

    python3 -m bot.deckopt3.report DIR [DIR ...] [--json FILE]

Rows are keyed by entry id `<tag>-<case>:<deck>`; a case counts in a row's paired analysis only if every arm of
that row has a clean row for it. Score = win + 0.5 draw. CIs: bootstrap over cases, 10,000 resamples, seed 0
(paired for deltas vs `sam`; row B resamples within its two strata). Row B = W_PH x mean(P.E.K.K.A/Hog cases of A
and Bsup) + (1 - W_PH) x mean(other A cases), W_PH = 28/52 (s73-s78 share).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

W_PH = 28 / 52
REF = 'sam'
SPELLS = {'Zap', 'Arrows', 'Fireball', 'Rocket'}
N_BOOT = 10000


def score(r):
    return .5 if r.get('draw') else float(r.get('win') or 0)


def clean(r):
    return 'result' in r and not r.get('error') and not r.get('issues')


def load(dirs):
    rows, bad = {}, []
    for d in dirs:
        for p in sorted(Path(d, 'rows').glob('*.json')):
            r = json.loads(p.read_text())
            if r['id'] in rows:
                raise SystemExit(f'duplicate entry {r["id"]} in {p}')
            rows[r['id']] = r
            if not clean(r):
                bad.append(dict(id=r['id'], path=str(p), error=r.get('error'), issues=r.get('issues')))
    return rows, bad


def q(xs, f):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(f * len(xs)))], 2) if xs else None


def ci(draws):
    draws = sorted(draws)
    return [round(draws[int(.025 * len(draws))], 3), round(draws[int(.975 * len(draws)) - 1], 3)]


def boot_mean(vals, rng):
    n = len(vals)
    return [sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(N_BOOT)]


def play_stats(r):
    seat = str(r['seat'])
    log = r['result'].get('play_log') or {}
    mine = [(t, c) for t, c, a, ok in log.get(seat, []) if ok]
    theirs = [(t, c) for t, c, a, ok in log.get(str(1 - int(seat)), []) if ok]
    ticks = sorted(t for t, _ in mine)
    react = []
    for t, c in theirs:
        nxt = next((x for x in ticks if x >= t), None)
        if nxt is not None:
            react.append((nxt - t) / 20)
    return Counter(c for _, c in mine), react


def arm_diag(rs):
    cards, react = Counter(), []
    for r in rs:
        c, x = play_stats(r)
        cards.update(c)
        react += x
    n = max(1, len(rs))
    return dict(plays_per_battle=round(sum(cards.values()) / n, 1),
                spells_per_battle=round(sum(v for k, v in cards.items() if k in SPELLS) / n, 2),
                card_plays_per_battle={k: round(v / n, 2) for k, v in cards.most_common()},
                reaction_p50_p90=[q(react, .5), q(react, .9)])


def paired_table(rows, tag, arms):
    cases = defaultdict(dict)
    for r in rows.values():
        if r['case'].startswith(tag + '-') and r['deck'] in arms:
            cases[r['case']][r['deck']] = r
    full = {c: v for c, v in cases.items() if all(a in v and clean(v[a]) for a in arms)}
    return cases, full


def summarise(rows, tag, arms):
    cases, full = paired_table(rows, tag, arms)
    keys = sorted(full)
    out = dict(tag=tag, cases_seen=len(cases), cases_paired=len(keys), arms={})
    if not keys:
        return out
    for a in arms:
        vals = [score(full[k][a]) for k in keys]
        rng = random.Random(0)
        d = dict(n=len(vals), win=round(sum(vals) / len(vals), 3), ci=ci(boot_mean(vals, rng)),
                 **arm_diag([full[k][a] for k in keys]))
        if a != REF and REF in arms:
            diff = [score(full[k][a]) - score(full[k][REF]) for k in keys]
            d['delta'] = round(sum(diff) / len(diff), 3)
            d['delta_ci'] = ci(boot_mean(diff, random.Random(0)))
        for name, sel in (('pekka_hog', lambda r: r['pekka_hog']), ('other', lambda r: not r['pekka_hog']),
                          ('pekka', lambda r: r['pekka'])):
            ks = [k for k in keys if sel(full[k][a])]
            if ks:
                v = [score(full[k][a]) for k in ks]
                d[name] = dict(n=len(v), win=round(sum(v) / len(v), 3))
                if a != REF and REF in arms:
                    dv = [score(full[k][a]) - score(full[k][REF]) for k in ks]
                    d[name].update(delta=round(sum(dv) / len(dv), 3), delta_ci=ci(boot_mean(dv, random.Random(0))))
        out['arms'][a] = d
    return out


def row_b(rows, arms):
    _, fa = paired_table(rows, 'A', arms)
    _, fb = paired_table(rows, 'Bsup', arms)
    ph = [v for v in list(fa.values()) + list(fb.values()) if v[arms[0]]['pekka_hog']]
    other = [v for v in fa.values() if not v[arms[0]]['pekka_hog']]
    out = dict(w_pekka_hog=round(W_PH, 4), n_pekka_hog=len(ph), n_other=len(other), arms={})
    if not ph or not other:
        return out
    for a in arms:
        def est(f):
            p = [f(v) for v in ph]
            o = [f(v) for v in other]
            point = W_PH * sum(p) / len(p) + (1 - W_PH) * sum(o) / len(o)
            rng = random.Random(0)
            draws = [W_PH * bp + (1 - W_PH) * bo for bp, bo in zip(boot_mean(p, rng), boot_mean(o, rng))]
            return round(point, 3), ci(draws)
        w, wci = est(lambda v: score(v[a]))
        d = dict(win=w, ci=wci)
        pv = [score(v[a]) for v in ph]
        d['pekka_hog_only'] = dict(n=len(pv), win=round(sum(pv) / len(pv), 3), ci=ci(boot_mean(pv, random.Random(0))))
        pk = [score(v[a]) for v in ph if v[a]['pekka']]
        d['pekka_only'] = dict(n=len(pk), win=round(sum(pk) / max(1, len(pk)), 3))
        if a != REF:
            d['delta'], d['delta_ci'] = est(lambda v: score(v[a]) - score(v[REF]))
            dv = [score(v[a]) - score(v[REF]) for v in ph]
            d['pekka_hog_only'].update(delta=round(sum(dv) / len(dv), 3), delta_ci=ci(boot_mean(dv, random.Random(0))))
        out['arms'][a] = d
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--json', default=None)
    ap.add_argument('--screen', action='store_true', help='rank screen arms (tag scr) by paired delta vs sam')
    a = ap.parse_args(argv)
    rows, bad = load(a.dirs)
    arms = sorted({r['deck'] for r in rows.values()}, key=lambda x: (x != REF, x))
    tags = sorted({r['case'].rsplit('-', 1)[0] for r in rows.values()})
    out = dict(rows=len(rows), unclean=bad, tags=tags, arms=arms)
    for t in tags:
        out[t] = summarise(rows, t, arms)
    if 'A' in tags and 'Bsup' in tags:
        out['B'] = row_b(rows, arms)
    if a.screen:
        s = out.get('scr', {}).get('arms', {})
        out['ranking'] = sorted(((k, v.get('delta')) for k, v in s.items() if k not in (REF, 'dk2')),
                                key=lambda kv: -(kv[1] if kv[1] is not None else -9))
    text = json.dumps(out, indent=1)
    if a.json:
        Path(a.json).write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main(sys.argv[1:])
