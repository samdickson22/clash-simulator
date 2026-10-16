"""Recall of truth units by owner x damaged state and per swarm body, for eval_yolo.py AND eval_official.py outputs (no model run).

Damaged = the unit's level badge or HP bar is visible in that frame: `damaged` in the truth label (labels/<ID>.json units) or, for
frames labelled before that field existed, `damaged/<ID>.json` = {"damaged": [true|false|null, ...]} in units order (Sol pass).
Matching per frame, predictions with score >= thr, greedy by score, one-to-one, <= 1 tile:
  det = same owner, any identity (is the unit seen as a unit of the right team?)
  id  = same owner AND identity (model namespace: eval_yolo `name`, eval_official `card`)
Rows' truth lists are in label-file units order (both eval scripts), which is how damaged flags and cards are joined.

  python damage_recall.py --labels LABELS_DIR --damaged DAMAGED_DIR NAME=EVAL.json ... [--thr .5] [--json OUT.json]
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

SWARMS = ('Minions', 'Skeletons', 'Archers', 'SkeletonArmy', 'GoblinGang', 'MinionHorde', 'SpearGoblins', 'Goblins')


def norm(d):
    """(team 0 ours / 1 opp, name) for truth or prediction of either eval format."""
    if 'team' in d:
        return int(d['team']), d.get('name')
    return (0 if d['owner'] == 1 else 1), d.get('card') or d.get('identity')


def matched(truth, pred, thr, ident):
    used = set()
    for p in sorted((p for p in pred if p['score'] >= thr), key=lambda p: -p['score']):
        pt, pn = norm(p); best, bd = None, 1.0+1e-9
        for j, t in enumerate(truth):
            tt, tn = norm(t)
            if j in used or tt != pt or (ident and tn != pn):
                continue
            dd = math.hypot(t['x']-p['x'], t['y']-p['y'])
            if dd <= bd:
                best, bd = j, dd
        if best is not None:
            used.add(best)
    return used


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--labels', type=Path, required=True); p.add_argument('--damaged', type=Path, required=True)
    p.add_argument('--thr', type=float, default=.5); p.add_argument('--json', type=Path); p.add_argument('evals', nargs='+')
    a = p.parse_args()
    labs = {}
    for f in a.labels.glob('*.json'):
        lab = json.loads(f.read_text()); dm = [u.get('damaged') for u in lab['units']]
        side = a.damaged/f'{lab["id"]}.json'
        if any(v is None for v in dm) and side.exists():
            s = json.loads(side.read_text())['damaged']
            if len(s) == len(dm):
                dm = [v if v is not None else s[i] for i, v in enumerate(dm)]
        labs[lab['id']] = (lab['units'], dm)
    out = {}
    for spec in a.evals:
        name, path = spec.split('=', 1); d = json.loads(Path(path).read_text())
        st = defaultdict(lambda: [0, 0, 0])  # key -> [det hits, id hits, n]
        for r in d['rows']:
            if r['id'] not in labs:
                continue
            units, dm = labs[r['id']]
            assert len(units) == len(r['truth']), r['id']
            det, idm = matched(r['truth'], r['pred'], a.thr, False), matched(r['truth'], r['pred'], a.thr, True)
            for j, u in enumerate(units):
                own = 'ours' if u['owner'] == 'us' else 'opp'
                dk = {True: 'damaged', False: 'undamaged'}.get(dm[j], 'dmg?')
                keys = [f'{own}:all', f'{own}:{dk}', f"{r['arena']}:{own}:{dk}"]
                if u['card'] in SWARMS:
                    keys += [f"swarm:{u['card']}:{own}", f"swarm:{u['card']}:{own}:{dk}", f'swarm:ALL:{own}:{dk}']
                for k in keys:
                    s = st[k]; s[0] += j in det; s[1] += j in idm; s[2] += 1
        out[name] = {k: dict(det=round(v[0]/v[2], 3), id=round(v[1]/v[2], 3), n=v[2]) for k, v in sorted(st.items())}
    keys = sorted({k for v in out.values() for k in v}, key=lambda k: (k.startswith('swarm'), k.count(':'), k))
    print(f'thr {a.thr}, <=1 tile; cell = det recall (right team, any identity) / id recall (team + identity) (n)')
    print('| slice | ' + ' | '.join(out) + ' |'); print('|---|' + '---|'*len(out))
    for k in keys:
        print(f'| {k} | ' + ' | '.join(f"{v[k]['det']:.2f} / {v[k]['id']:.2f} ({v[k]['n']})" if k in v else '-' for v in out.values()) + ' |')
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
