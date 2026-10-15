"""Round-2 diagnosis: unit misses (validation dump, record frame). For each missed true unit (owner-only greedy match
<= 1 tile at the deployed 0.4 threshold, as bot/live/empirical.fit): merged (a same-owner detection within 1 tile is
matched to another true unit), below threshold (a 0.25-0.4 detection within 1 tile), or nothing.

  python live/perception/r2/diag_units.py DUMP_DIR OUT.json
"""
import json, math, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from bot.live.real_replay import load_dump  # noqa: E402
from bot.live.empirical import _greedy  # noqa: E402

SWARM = {'SkeletonArmy', 'MinionHorde', 'GoblinGang', 'AngryBarbarians', 'Barbarians', 'Minions', 'Skeletons', 'Goblins',
         'SpearGoblins', 'Rascals', 'Bats', 'RoyalRecruits', 'ThreeMusketeers', 'Guards', 'EliteBarbarians', 'FireSpirit',
         'IceSpirit', 'GoblinHut', 'Graveyard', 'Witch', 'Tombstone', 'BarbLog', 'RoyalDelivery'}


def main(dump, out):
    tot, cat = Counter(), defaultdict(Counter)
    crowd = Counter()
    age_miss = Counter(); age_tot = Counter()
    for f in sorted(Path(dump).glob('*.jsonl.gz')):
        head, rows = load_dump(f)
        first_seen = {}
        for r in rows:
            tr, pr = r['truth'], r['pred']
            if tr.get('objects_stale'):
                continue
            lo = [u for u in r['units_lo'] if u['score'] < .4]
            for owner in (0, 1):
                T = [u for u in tr['units'] if u['owner'] == owner]
                P = [u for u in pr['units'] if u['owner'] == owner]
                L = [u for u in lo if u['owner'] == owner]
                pairs = _greedy(P, T, 1.0)
                hit = {j for _, j, _ in pairs}
                for j, t in enumerate(T):
                    c = t['card']; tot[c] += 1
                    # same-card neighbours within 1 tile (crowd size)
                    nb = sum(1 for k, s in enumerate(T) if k != j and s['card'] == c and math.hypot(s['x']-t['x'], s['y']-t['y']) <= 1.)
                    crowd[(min(nb, 3), j in hit)] += 1
                    if j in hit:
                        cat[c]['hit'] += 1
                        continue
                    if any(math.hypot(p['x']-t['x'], p['y']-t['y']) <= 1. for p in P):
                        k = 'merged'
                    elif any(math.hypot(p['x']-t['x'], p['y']-t['y']) <= 1. for p in L):
                        k = 'below_thr'
                    elif any(math.hypot(p['x']-t['x'], p['y']-t['y']) <= 2. for p in P):
                        k = 'pos_off_1to2'
                    else:
                        k = 'none'
                    cat[c][k] += 1; cat['*'][k] += 1
        cat['*']['hit'] = sum(v['hit'] for k, v in cat.items() if k != '*')
    allm = sum(v for k, v in cat['*'].items() if k != 'hit')
    rows = sorted(((c, tot[c], tot[c]-cat[c]['hit'], dict(cat[c])) for c in tot), key=lambda r: -r[2])
    res = dict(total=sum(tot.values()), missed=allm, recall=1-allm/sum(tot.values()), categories=dict(cat['*']),
               by_crowd={f'{n}nb_{"hit" if h else "miss"}': v for (n, h), v in sorted(crowd.items())},
               per_card=[dict(card=c, n=n, missed=m, share_of_all_misses=round(m/allm, 4), recall=round(1-m/n, 3), **d) for c, n, m, d in rows])
    Path(out).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ('total', 'missed', 'recall', 'categories', 'by_crowd')}))
    for r in res['per_card'][:25]:
        print(r)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
