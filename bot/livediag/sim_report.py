"""Summaries of sim_diag runs: live-style metrics per arm and paired A/B deltas (bot lead live-diag, exploration).

    python3 -m bot.livediag.sim_report DIR [DIR ...] [--ref LD-K4L-R-gs-rw] [--json OUT]

Per candidate (all games of all DIRs): score by opponent; plays per game by card; share of frames with Giant /
Fireball in hand; Giant-push defence (bot.livediag.live_metrics.analyse); WAIT -> next decision gap; reaction time
= enemy play (accepted, tick) -> our next submitted play, and the number of search WAITs in between while our elixir
covered our cheapest hand card. Paired: per (opponent, index) score of each candidate minus --ref; 95% bootstrap CI
over cases within opponent, equal opponent weights (4000 draws, seed 0).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from bot.livediag.live_metrics import analyse

WAIT = 2304
COST = dict(Valkyrie=4, Archers=3, Minions=3, Cannon=3, Fireball=4, Giant=5, MiniPekka=4, Musketeer=4)


def load(dirs):
    rows = []
    for d in dirs:
        for p in Path(d).glob('games-*.jsonl'):
            for l in p.read_text().splitlines():
                if l.strip():
                    rows.append(json.loads(l))
    return rows


def reaction(r):
    """[(seconds enemy play -> our next play, search WAITs in between with elixir >= cheapest hand card)]."""
    plays = sorted(d['tick'] for d in r['dec'] if d['submitted'])
    pby = {p['n']: p for p in r['perc']}
    out = []
    for t, card in r['opp_plays']:
        nxt = next((p for p in plays if p >= t), None)
        if nxt is None:
            continue
        rich = 0
        for d in r['dec']:
            if t <= d['tick'] < nxt and d['stats'] and d['action'] >= WAIT:
                p = pby.get(d['n']) or {}
                hand = [c for c in (p.get('hand') or {}).get('cards') or [] if c in COST]
                if hand and p.get('elixir', 0) >= min(COST[c] for c in hand):
                    rich += 1
        out.append(((nxt - t) / 20, rich, card))
    return out


def boot(pairs_by_opp, draws=4000, seed=0):
    rng = random.Random(seed)
    opps = sorted(pairs_by_opp)
    point = sum(sum(v)/len(v) for v in pairs_by_opp.values()) / len(opps)
    samples = []
    for _ in range(draws):
        s = 0.
        for o in opps:
            v = pairs_by_opp[o]
            s += sum(v[rng.randrange(len(v))] for _ in v) / len(v)
        samples.append(s / len(opps))
    samples.sort()
    return point, samples[int(.025*draws)], samples[int(.975*draws)]


def q(xs, f):
    xs = sorted(xs)
    return xs[min(len(xs)-1, int(f*len(xs)))] if xs else None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--ref', default='LD-K4L-R-gs-rw')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    rows = load(a.dirs)
    errors = [r for r in rows if 'error' in r]
    rows = [r for r in rows if 'error' not in r]
    by = defaultdict(list)
    for r in rows:
        by[r['candidate']].append(r)
    report = dict(errors=len(errors), arms={})
    for cand, rs in sorted(by.items()):
        per_opp = defaultdict(list)
        cards, inhand, nh = Counter(), Counter(), 0
        pushes, gaps, react, src = [], Counter(), [], Counter()
        for r in rs:
            per_opp[r['opponent']].append(r['score'])
            m = analyse(r['perc'], r['dec'], dict(sid=f"{r['opponent']}:{r['index']}"))
            cards.update(m['plays'])
            for c, v in (m['in_hand_frac'] or {}).items():
                inhand[c] += v
            nh += 1
            pushes += m['giant_pushes']
            src.update(m['source'])
            nn = [d for d in r['dec'] if d['stats']]
            for x, y in zip(nn, nn[1:]):
                if x['action'] >= WAIT:
                    gaps[min(100, y['tick'] - x['tick'])] += 1
            react += reaction(r)
        n = len(rs)
        nd = sum(p['no_def_before_contact'] for p in pushes)
        dm = [p['def_minus_cross_s'] for p in pushes if p['def_minus_cross_s'] is not None]
        el = [p['elixir_cross'] for p in pushes if p['elixir_cross'] is not None]
        rg = [x[0] for x in react if x[2] == 'Giant']
        arm = dict(games=n, score={o: round(sum(v)/len(v), 3) for o, v in sorted(per_opp.items())},
                   pool=round(sum(sum(v)/len(v) for v in per_opp.values())/len(per_opp), 3),
                   plays_per_game={c: round(v/n, 2) for c, v in cards.most_common()},
                   in_hand={c: round(v/nh, 2) for c, v in inhand.items()},
                   source={k: v for k, v in src.items()},
                   wait_gap_ticks=dict(sorted(gaps.items())),
                   giant_pushes=len(pushes), no_def_before_contact=nd,
                   no_def_frac=round(nd/max(1, len(pushes)), 3),
                   def_minus_cross_s=[q(dm, .25), q(dm, .5), q(dm, .75)],
                   elixir_cross=[q(el, .25), q(el, .5), q(el, .75)],
                   reaction_s=[q([x[0] for x in react], .5), q([x[0] for x in react], .9)],
                   reaction_giant_s=[q(rg, .5), q(rg, .9)],
                   rich_waits_per_reaction=round(sum(x[1] for x in react)/max(1, len(react)), 2))
        report['arms'][cand] = arm
    ref = {(r['opponent'], r['index']): r['score'] for r in by.get(a.ref, [])}
    report['paired'] = {}
    for cand, rs in sorted(by.items()):
        if cand == a.ref:
            continue
        pairs = defaultdict(list)
        for r in rs:
            k = (r['opponent'], r['index'])
            if k in ref:
                pairs[r['opponent']].append(r['score'] - ref[k])
        if pairs:
            pt, lo, hi = boot(pairs)
            report['paired'][cand] = dict(n=sum(len(v) for v in pairs.values()), delta=round(pt, 4),
                                          ci=[round(lo, 4), round(hi, 4)],
                                          by_opp={o: round(sum(v)/len(v), 4) for o, v in sorted(pairs.items())})
    text = json.dumps(report, indent=1)
    if a.json:
        Path(a.json).write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main(sys.argv[1:])
