"""Aggregate LIVE fidelity runs (bot.simfid.live_run outputs) into tables; optional paired comparison."""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

HOG = ('Skeletons', 'Musketeer', 'IceGolem', 'Cannon', 'Fireball', 'Zap', 'IceSpirit', 'HogRider')
OWN_TOWER = dict(king=4008, princess=2534)


def load(out):
    out = Path(out)
    probes = json.loads((out / 'probes.json').read_text())
    tmax = {int(k): v for k, v in probes['towers'].items()}
    games = {}
    for f in sorted(out.glob('mem-*.json')):
        games[f.stem] = json.loads(f.read_text())
    return games, tmax


def seg_rows(games, tmax, certain_only=False):
    """-> list of dict(game, t0, h -> acc, cards, tower_abs_err, dmg_err, plays...)."""
    rows = []
    for g, d in games.items():
        ot = d.get('opp_tower_level') or 11
        for s in d['segments']:
            if 'error' in s:
                continue
            if certain_only and s.get('flags'):
                continue
            r = dict(game=g, t0=s['t0'], plays=s['plays'], acc=s['acc'], cards=s['cards'], counters=s['counters'],
                     towers={})
            for h, t in s['towers'].items():
                errs, dmg = [], {'0': [0., 0.], '1': [0., 0.]}
                dead = []
                for row in t['rows']:
                    o, kind, side = row['key']
                    m = OWN_TOWER[kind] if o == 0 else tmax[ot][kind]
                    if row['truth'] is None or row['sim'] is None:
                        continue
                    errs.append(abs(row['truth'] - row['sim']) * m)
                    dmg[str(o)][0] += (row['t0'] - row['truth']) * m
                    dmg[str(o)][1] += (row['t0'] - row['sim']) * m
                    if row['t0'] > 0:
                        dead.append((row['truth'] <= 0) == (row['sim'] <= 0))
                r['towers'][h] = dict(abs=errs, dmg=dmg, dead=dead)
            rows.append(r)
    return rows


def pct(a, k):
    return 100. * a[k] / a['ut'] if a['ut'] else float('nan')


def boot(rows, fn, n=1000, seed=0):
    """Percentile bootstrap over GAMES of a ratio statistic fn(list of rows)."""
    by = defaultdict(list)
    for r in rows:
        by[r['game']].append(r)
    keys = sorted(by)
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        sample = [r for k in (rng.choice(keys) for _ in keys) for r in by[k]]
        vals.append(fn(sample))
    vals.sort()
    return vals[int(.025 * n)], vals[int(.975 * n) - 1]


def overall(rows, h):
    a = Counter()
    for r in rows:
        a.update(r['acc'].get(str(h), {}))
    return a


def summary(out, certain_only=False):
    games, tmax = load(out)
    rows = seg_rows(games, tmax, certain_only)
    res = dict(games=len(games), segments=len(rows),
               segment_errors=sum(1 for d in games.values() for s in d['segments'] if 'error' in s),
               counters=sum((Counter(r['counters']) for r in rows), Counter()))
    for h in (100, 200, 400):
        a = overall(rows, h)
        lo, hi = boot(rows, lambda rs: pct(overall(rs, h), 'q'), n=400)
        tw = [e for r in rows if str(h) in r['towers'] for e in r['towers'][str(h)]['abs']]
        dm = [abs(r['towers'][str(h)]['dmg'][o][0] - r['towers'][str(h)]['dmg'][o][1])
              for r in rows if str(h) in r['towers'] for o in ('0', '1')]
        dd = [x for r in rows if str(h) in r['towers'] for x in r['towers'][str(h)]['dead']]
        res[h] = dict(ut=a['ut'], q=pct(a, 'q'), q_ci=(lo, hi), c1=pct(a, 'c1'), hp=pct(a, 'hp'), miss=pct(a, 'miss'),
                      tower_abs_mae=sum(tw) / max(1, len(tw)), tower_dmg_mae=sum(dm) / max(1, len(dm)),
                      tower_dead_agree=sum(dd) / max(1, len(dd)))
    return res, rows


def per_card(rows, h=400, min_ut=500):
    acc = defaultdict(Counter)
    for r in rows:
        for k, v in r['cards'].get(str(h), {}).items():
            acc[k].update(v)
    return {k: v for k, v in acc.items() if v['ut'] >= min_ut}


def per_interaction(rows, h=400, min_seg=15):
    """(own card, opponent card) both played in the segment -> pooled segment accuracy."""
    acc = defaultdict(Counter)
    nseg = Counter()
    for r in rows:
        own = {p[1] for p in r['plays'] if p[0] == 0}
        opp = {p[1] for p in r['plays'] if p[0] == 1}
        a = r['acc'].get(str(h), {})
        dmg = r['towers'].get(str(h), {}).get('dmg', {})
        for o in own:
            for e in opp:
                acc[o, e].update(a)
                nseg[o, e] += 1
                if dmg:
                    acc[o, e]['tdmg_err'] += abs(dmg['1'][0] - dmg['1'][1]) + abs(dmg['0'][0] - dmg['0'][1])
    return {k: (nseg[k], v) for k, v in acc.items() if nseg[k] >= min_seg}


def report(out, compare=None):
    for certain in (False, True):
        res, rows = summary(out, certain)
        print(f"== {out} {'CLEAN (no opponent form, dropout or uncertain play)' if certain else 'all segments'}: games {res['games']} "
              f"segments {res['segments']} errors {res['segment_errors']}")
        print('   counters', dict(res['counters']))
        for h in (100, 200, 400):
            x = res[h]
            print(f"   {h // 20:>2d}s ut={x['ut']:>7d} <=1/4 {x['q']:.1f} [{x['q_ci'][0]:.1f},{x['q_ci'][1]:.1f}] "
                  f"<=1 {x['c1']:.1f} hp<=2% {x['hp']:.1f} unmatched {x['miss']:.1f} | tower |err| {x['tower_abs_mae']:.0f} "
                  f"dmg err {x['tower_dmg_mae']:.0f} death agree {100 * x['tower_dead_agree']:.1f}")
    res, rows = summary(out, True)
    pc = per_card(rows)
    print('\n   per card (CLEAN segments, 20 s, owner|card, ut>=500):')
    for k, v in sorted(pc.items(), key=lambda kv: -kv[1]['ut'])[:45]:
        print(f"     {k:<28s} ut={v['ut']:>6d} <=1/4 {pct(v, 'q'):5.1f} <=1 {pct(v, 'c1'):5.1f} "
              f"hp {pct(v, 'hp'):5.1f} unmatched {pct(v, 'miss'):5.1f}")
    pi = per_interaction(rows)
    print('\n   per interaction (20 s, own card x opponent card, >=15 segments; worst 30 by <=1/4):')
    for k, (n, v) in sorted(pi.items(), key=lambda kv: pct(kv[1][1], 'q'))[:30]:
        print(f"     {k[0]:>10s} x {k[1]:<16s} seg={n:>3d} <=1/4 {pct(v, 'q'):5.1f} hp {pct(v, 'hp'):5.1f} "
              f"unmatched {pct(v, 'miss'):5.1f} tower-dmg err/seg {v['tdmg_err'] / n:6.0f}")
    if compare:
        res2, rows2 = summary(compare, True)
        key = {(r['game'], r['t0']): r for r in rows2}
        common = [(r, key[r['game'], r['t0']]) for r in rows if (r['game'], r['t0']) in key]
        print(f'\n   paired vs {compare}: {len(common)} common segments')
        for h in (100, 200, 400):
            a = overall([r for r, _ in common], h); b = overall([s for _, s in common], h)
            print(f"     {h // 20}s <=1/4 {pct(a, 'q'):.1f} vs {pct(b, 'q'):.1f}; hp {pct(a, 'hp'):.1f} vs {pct(b, 'hp'):.1f}")
