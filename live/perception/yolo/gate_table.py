"""YOLO live-candidate gates (PROGRESS-R3 standing duty 1) for eval_yolo.py outputs, one row per checkpoint, thr .5, <= 1 tile:
  owner  enemy->ours <= 3% overall and per building class (location matching as owner_eval.py)
  recall friendly UNDAMAGED (right team) >= .75; swarm bodies (right team) >= .80 for ours and for opp (damage_recall.py)
  P/R    identity P/R per arena not worse than the reference (first argument) beyond --tol, 0 empty-frame units
Prints PASS only when every gate holds.

  python gate_table.py --labels LABELS --damaged DAMAGED REF=EVAL.json NAME=EVAL.json ...
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from damage_recall import SWARMS, matched, norm

BUILD = {'cannon', 'goblin-hut', 'tombstone', 'goblin-cage', 'bomb-tower', 'inferno-tower', 'tesla', 'mortar', 'x-bow', 'barbarian-hut',
         'furnace', 'elixir-collector'}


def owner_errors(d, thr=.5):
    eo, per = [0, 0], defaultdict(lambda: [0, 0])
    for r in d['rows']:
        used = set()
        for p in sorted((p for p in r['pred'] if p['score'] >= thr), key=lambda p: -p['score']):
            best, bd = None, 1.0+1e-9
            for j, t in enumerate(r['truth']):
                dd = math.hypot(t['x']-p['x'], t['y']-p['y'])
                if j not in used and dd <= bd:
                    best, bd = j, dd
            if best is None:
                continue
            used.add(best); tt, tn = norm(r['truth'][best]); pt, _ = norm(p)
            if tt == 1:
                eo[0] += pt == 0; eo[1] += 1
                if tn in BUILD:
                    per[tn][0] += pt == 0; per[tn][1] += 1
    return eo, per


def recalls(d, labs, thr=.5):
    st = defaultdict(lambda: [0, 0])
    for r in d['rows']:
        units, dm = labs[r['id']]; det = matched(r['truth'], r['pred'], thr, False)
        for j, u in enumerate(units):
            own = 'ours' if u['owner'] == 'us' else 'opp'
            keys = ([f'{own}:undamaged'] if dm[j] is False else []) + ([f'swarm:{own}'] if u['card'] in SWARMS else [])
            for k in keys:
                st[k][0] += j in det; st[k][1] += 1
    return {k: (v[0]/max(1, v[1]), v[1]) for k, v in st.items()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--labels', type=Path, required=True); p.add_argument('--damaged', type=Path, required=True); p.add_argument('evals', nargs='+')
    p.add_argument('--tol', type=float, default=.02, help='P/R tolerance vs the reference (sample noise: TC has ~100 units)')
    a = p.parse_args()
    labs = {}
    for f in a.labels.glob('*.json'):
        lab = json.loads(f.read_text()); side = a.damaged/f"{lab['id']}.json"
        sd = json.loads(side.read_text())['damaged'] if side.exists() else []
        labs[lab['id']] = (lab['units'], [u.get('damaged', sd[i] if i < len(sd) else None) for i, u in enumerate(lab['units'])])
    ref = None
    print('| model | enemy->ours | worst building | ours undamaged | swarm ours | swarm opp | id P/R GS TC BP BB | empty | gate |')
    print('|---|---|---|---|---|---|---|---|---|')
    for spec in a.evals:
        name, path = spec.split('=', 1); d = json.loads(Path(path).read_text()); m = d['metrics']['thr0.5_r1.0']
        eo, per = owner_errors(d); rc = recalls(d, labs)
        pr = {g: (m[f'{g}:id']['P'], m[f'{g}:id']['R']) for g in ('GS', 'TC', 'BP', 'BB') if f'{g}:id' in m}
        if ref is None:
            ref = pr
        wb = max(per.items(), key=lambda kv: kv[1][0]/max(1, kv[1][1]), default=('-', [0, 0]))
        g_owner = eo[0] <= .03*eo[1] and all(v[0] <= .03*v[1] for v in per.values())
        g = lambda k, bar: rc.get(k, (0, 0))[0] >= bar
        g_pr = all(pr[k][0] >= ref[k][0]-a.tol-1e-9 and pr[k][1] >= ref[k][1]-a.tol-1e-9 for k in ref if k in pr)
        ok = g_owner and g('ours:undamaged', .75) and g('swarm:ours', .80) and g('swarm:opp', .80) and g_pr and d['empty']['thr0.5'] == 0
        f = lambda k: f"{rc[k][0]:.2f} ({rc[k][1]})" if k in rc else '-'
        print(f"| {name} | {eo[0]}/{eo[1]} ({eo[0]/max(1, eo[1]):.1%}) | {wb[0]} {wb[1][0]}/{wb[1][1]} | {f('ours:undamaged')} | "
              f"{f('swarm:ours')} | {f('swarm:opp')} | {' '.join(f'{v[0]:.2f}/{v[1]:.2f}' for v in pr.values())} | {d['empty']['thr0.5']} | "
              f"{'PASS' if ok else 'fail: ' + ','.join(n for n, c in (('owner', g_owner), ('undmg', g('ours:undamaged', .75)), ('swarm', g('swarm:ours', .8) and g('swarm:opp', .8)), ('P/R', g_pr)) if not c)} |")


if __name__ == '__main__':
    main()
