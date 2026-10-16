"""Per-stretch summary of bot.pocket.live_replay outputs (exploration).

    python -m bot.pocket.live_analyze OUT_DIR [--variants K4P-pw2,K4P-kc100-pw2]

OUT_DIR/<run>-<search>.jsonl. Stretch = an enemy princess tower's death (replay 'tower' rows, own frame) to the next
enemy princess tower death or the last decision; plays are classed with live/loop/pocket.py's definition (rows >= 17
within 5 tiles of the dead tower's lane x = pocket). For K4L-R-gs rows with a counterfactual the best pocket push is
compared with the chosen action at 160/320/480 ticks (full score and learned-opponent term).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def rows(p):
    return [json.loads(x) for x in open(p)] if Path(p).exists() else []


def stretches(R):
    deaths = {}
    for r in R:
        if r['kind'] == 'tower':
            for j, side in ((0, 'l'), (1, 'r')):
                if r['dead'][j] and side not in deaths:
                    deaths[side] = r['tick']
    end = max([r['tick'] for r in R if 'tick' in r and r['tick'] is not None] + [0])
    order = sorted(deaths.items(), key=lambda kv: kv[1])
    out = []
    for n, (side, t0) in enumerate(order):
        t1 = order[n + 1][1] if n + 1 < len(order) else end + 1
        if t1 - t0 >= 40:
            out.append((side, t0, t1))
    return out


def live_class(a, side):
    row, col = (a % 576) // 18, a % 18
    zone = 'enemy' if row >= 17 else ('bridge' if row >= 15 else 'own')
    return zone, zone == 'enemy' and abs(col + .5 - (3.5 if side == 'l' else 14.5)) <= 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--variants', default='K4P-pw2,K4P-kc100-pw2')
    a = ap.parse_args()
    variants = a.variants.split(',')
    runs = sorted({p.name.rsplit('-K4', 1)[0] for p in a.out.glob('*-K4L-R-gs.jsonl')})
    tot = defaultdict(Counter)
    per = []
    for run in runs:
        base = rows(a.out / f'{run}-K4L-R-gs.jsonl')
        if not base or base[-1].get('kind') != 'end':
            continue
        for side, t0, t1 in stretches(base):
            rec = dict(run=run, tower=f'opp-{side}', ticks=[t0, t1])
            for v in ['K4L-R-gs'] + variants:
                R = base if v == 'K4L-R-gs' else rows(a.out / f'{run}-{v}.jsonl')
                S = [r for r in R if r['kind'] == 'search' and t0 <= r['tick'] < t1]
                plays = [r for r in S if r['action'] < 2304]
                cls = [live_class(r['action'], side) for r in plays]
                c = tot[v]
                c['decisions'] += len(S); c['plays'] += len(plays)
                c['pocket'] += sum(p for _, p in cls); c['own'] += sum(z == 'own' for z, _ in cls)
                c['enemy'] += sum(z == 'enemy' for z, _ in cls)
                c['pocket_cls'] += sum(r['cls'] == 'pocket' for r in plays)
                rec[v] = dict(decisions=len(S), plays=len(plays), pocket=sum(p for _, p in cls),
                              own=sum(z == 'own' for z, _ in cls),
                              actions=[(r['tick'], r['cls'], r.get('card')) for r in plays])
                if v == 'K4L-R-gs':
                    for r in S:
                        cf = r.get('cf')
                        if not cf:
                            continue
                        pk = [j for j, k in enumerate(cf['cls']) if k == 'pocket']
                        if not pk:
                            continue
                        c['cf'] += 1
                        for h in ('160', '320', '480'):
                            b = max(pk, key=lambda j: cf[h][j])
                            d = cf[h][b] - cf[h][0]
                            c[f'better{h}'] += d > 1e-9; c[f'worse{h}'] += d < -1e-9
                            bl = max(pk, key=lambda j: cf['L' + h][j])
                            c[f'Lbetter{h}'] += cf['L' + h][bl] - cf['L' + h][0] > 1e-9
                        # the search's own horizon: a pocket push whose learned rollout wins while the choice does not
                        c['L160_pocket_wins'] += any(cf['L160'][j] >= 2 for j in pk) and cf['L160'][0] < 2
            per.append(rec)
    for rec in per:
        print(json.dumps(rec))
    print(json.dumps({v: dict(c) for v, c in tot.items()}, indent=1))


if __name__ == '__main__':
    main()
