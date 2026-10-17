"""s69 loss-streak check: per battle opponent tower HP vs ours (king level proxy), opponent unit classes, v3b remaps fired."""
import json, re, statistics as st, sys
from collections import Counter
from pathlib import Path

RUNS = Path('/mpac/sdicks02/jobs/clasher/bot-livediag/runs')
RES_MD = Path('/mpac/sdicks02/repos/clasher-live/reports/live/loop/RESULTS.md')
A = json.load(open('/mpac/sdicks02/scratch/live-loop/packages/bundle-stage/true-ids-v3a.json'))['cards']
B = json.load(open('/mpac/sdicks02/scratch/live-loop/packages/restart3b-stage/true-ids-v3b.json'))['cards']
NEW = set(B) - set(A)

res = {}
for line in RES_MD.read_text().splitlines():
    c = [x.strip() for x in line.strip().strip('|').split('|')]
    if len(c) > 3 and re.fullmatch(r's\d+[a-z]?-m\d+', c[0]):
        res[c[0]] = (c[1].replace('*', ''), c[2])

rows = []
for d in sorted(RUNS.iterdir()):
    if not re.fullmatch(r's6[789]-m\d+', d.name) or not (d / 'perception.jsonl').exists():
        continue
    cfg = json.load(open(d / 'session-config.json'))
    sess = json.load(open(d / 'session.json'))
    full = {(o, k): [] for o in (0, 1) for k in ('king', 'princess')}
    opp = Counter()
    for l in open(d / 'perception.jsonl'):
        r = json.loads(l)
        for t in r.get('towers') or []:
            if t.get('alive') and t.get('hp_read') and (t.get('hp_frac') or 0) >= .995:
                full[(t['owner'], t['kind'])].append(t['hp_read'])
        for u in r.get('units') or []:
            if u.get('owner') == 1:
                opp[u.get('card') or u.get('cls')] += 1
    med = {k: (st.median(v) if v else None) for k, v in full.items()}
    ratio = lambda k: round(med[(1, k)] / med[(0, k)], 3) if med[(1, k)] and med[(0, k)] else None
    tid = {k[len('true_id:'):]: v for k, v in (sess.get('tr_stats') or {}).items() if k.startswith('true_id:')}
    v3b_fired = {k: v for k, v in tid.items() if k.split('->')[1] in NEW}
    rows.append(dict(battle=d.name, result=res.get(d.name, ('?', ''))[0], trophies=res.get(d.name, ('', '?'))[1],
                     arm=cfg.get('arm'), ids=(cfg.get('true_ids') or {}).get('path', '').split('/')[-1],
                     king=[med[(0, 'king')], med[(1, 'king')], ratio('king')],
                     princess=[med[(0, 'princess')], med[(1, 'princess')], ratio('princess')],
                     opp_units=[k for k, v in opp.most_common(10) if v >= 20], true_id=tid, v3b_fired=v3b_fired))
json.dump(rows, open(sys.argv[1], 'w'), indent=1)
for r in rows:
    print(r['battle'], r['result'][:8], r['trophies'], r['arm'], r['ids'][9:13], 'king', r['king'], 'pr', r['princess'],
          'opp', ','.join(r['opp_units'][:8]), 'v3b', r['v3b_fired'])
