"""Owner (team) accuracy of a detector on EVAL-SPLIT, from eval_yolo.py / eval_official.py outputs (no model run).

Truth units and predictions (score >= thr) are matched by LOCATION only (greedy by score, one-to-one, <= 1 tile, any identity, any
team). Among matched truth units: owner accuracy and the confusion matrix truth ours/theirs x predicted ours/theirs, per arena and on the
CROWDED MIXED-TEAM subset (truth units with >= 2 units of each team within 3 tiles, counting the unit itself).

  python owner_eval.py NAME=EVAL.json ... [--thr .5]
"""
import json
import math
import sys
from collections import defaultdict


def team_of(d):
    if 'team' in d:
        return int(d['team'])
    return 0 if d['owner'] in ('us', 1) and d['owner'] != 0 else 1  # eval_official rows: owner 1 = ours (native)


def rows_of(d):
    for r in d['rows']:
        truth = [dict(x=float(t['x']), y=float(t['y']), team=int(t['team']) if 'team' in t else (0 if t['owner'] == 1 else 1),
                      name=t.get('name') or t.get('card')) for t in r['truth']]
        pred = [dict(x=float(p['x']), y=float(p['y']), score=float(p['score']),
                     team=int(p['team']) if 'team' in p else (0 if p['owner'] == 1 else 1)) for p in r['pred']]
        yield r['arena'], truth, pred


def crowded(truth, i):
    c = [0, 0]
    for t in truth:
        if math.hypot(t['x']-truth[i]['x'], t['y']-truth[i]['y']) <= 3:
            c[t['team']] += 1
    return c[0] >= 2 and c[1] >= 2


def main():
    args = sys.argv[1:]; thr = .5
    if '--thr' in args:
        k = args.index('--thr'); thr = float(args[k+1]); args = args[:k]+args[k+2:]
    global PER
    PER = []
    print(f'thr {thr}: owner accuracy among location-matched units (n); confusion [truth->pred] ours->theirs / theirs->ours')
    print('| model | GS | TC | BP | BB | all | crowded mixed-team | ours->theirs | theirs->ours |')
    print('|---|---|---|---|---|---|---|---|---|')
    for arg in args:
        name, path = arg.split('=', 1); d = json.loads(open(path).read())
        acc = defaultdict(lambda: [0, 0]); conf = defaultdict(int); per = defaultdict(lambda: [0, 0, 0, 0])
        for arena, truth, pred in rows_of(d):
            used = set(); pairs = []
            for p in sorted((p for p in pred if p['score'] >= thr), key=lambda p: -p['score']):
                best, bd = None, 1.0+1e-9
                for j, t in enumerate(truth):
                    if j in used:
                        continue
                    dd = math.hypot(t['x']-p['x'], t['y']-p['y'])
                    if dd <= bd:
                        best, bd = j, dd
                if best is not None:
                    used.add(best); pairs.append((best, p))
            for j, p in pairs:
                ok = int(p['team'] == truth[j]['team'])
                keys = [arena, 'all'] + (['crowd'] if crowded(truth, j) else [])
                for k in keys:
                    acc[k][0] += ok; acc[k][1] += 1
                conf[(truth[j]['team'], p['team'])] += 1
                pc = per[truth[j]['name']]; pc[2*truth[j]['team']+p['team']] += 1  # [ours->ours, ours->theirs, theirs->ours, theirs->theirs]
        f = lambda k: f"{acc[k][0]/max(1, acc[k][1]):.3f} ({acc[k][1]})" if acc[k][1] else '-'
        print(f"| {name} | {f('GS')} | {f('TC')} | {f('BP')} | {f('BB')} | {f('all')} | {f('crowd')} | "
              f"{conf[(0, 1)]}/{conf[(0, 0)]+conf[(0, 1)]} | {conf[(1, 0)]}/{conf[(1, 0)]+conf[(1, 1)]} |")
        PER.append((name, per))
    print()
    print('Per class (truth name): enemy->ours / enemy n, ours->enemy / ours n; BUILDINGS first')
    B = ('cannon', 'goblin-hut', 'tombstone', 'goblin-cage', 'bomb-tower', 'inferno-tower', 'tesla', 'barbarian-hut', 'mortar', 'x-bow',
         'Cannon', 'GoblinHut', 'Tombstone', 'GoblinCage', 'BombTower', 'InfernoTower', 'Tesla')
    for name, per in PER:
        keys = sorted(per, key=lambda k: (k not in B, -(per[k][2]+per[k][3])))
        print(name+': '+'; '.join(f"{k} {per[k][2]}/{per[k][2]+per[k][3]}, {per[k][1]}/{per[k][0]+per[k][1]}" for k in keys[:14]))


if __name__ == '__main__':
    main()
