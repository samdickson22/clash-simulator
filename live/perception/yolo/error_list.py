"""Per-frame error list of a detector on EVAL-SPLIT (weakness audit, held-out part), from an eval_yolo.py / eval_official.py output.

Location matching (greedy by score, one-to-one, <= 1 tile, any identity/team) of predictions (score >= thr) to truth, then per truth unit:
  ok | wrong-owner | wrong-class | miss (no prediction within 1 tile); unmatched predictions = phantom (incl. duplicates of one body, i.e.
  a split, and boxes > 1 tile off). A miss whose nearest same-team prediction already matched a truth unit within 1.5 tiles is counted
  as merge (two bodies, one detection).
Counts per card x owner x damaged (damage_recall.py's flags), and a JSON of every error with its frame id for the reviewer.

  python error_list.py --labels LABELS --damaged DAMAGED EVAL.json [--thr .5] [--out ERRORS.json]
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

from damage_recall import norm


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--labels', type=Path, required=True); p.add_argument('--damaged', type=Path, required=True)
    p.add_argument('--thr', type=float, default=.5); p.add_argument('--out', type=Path); p.add_argument('eval')
    a = p.parse_args()
    d = json.loads(Path(a.eval).read_text()); errs = []; cnt = Counter(); tot = Counter()
    for r in d['rows']:
        lab = json.loads((a.labels/f"{r['id']}.json").read_text()); units = lab['units']
        side = a.damaged/f"{r['id']}.json"; sd = json.loads(side.read_text())['damaged'] if side.exists() else [None]*len(units)
        dm = [u.get('damaged', sd[i] if i < len(sd) else None) for i, u in enumerate(units)]
        preds = sorted((q for q in r['pred'] if q['score'] >= a.thr), key=lambda q: -q['score'])
        used, pair = set(), {}
        for k, q in enumerate(preds):
            best, bd = None, 1.0+1e-9
            for j, t in enumerate(r['truth']):
                dd = math.hypot(t['x']-q['x'], t['y']-q['y'])
                if j not in used and dd <= bd:
                    best, bd = j, dd
            if best is not None:
                used.add(best); pair[best] = k
        for j, u in enumerate(units):
            tt, tn = norm(r['truth'][j]); own = 'ours' if u['owner'] == 'us' else 'opp'
            dk = {True: 'damaged', False: 'undamaged'}.get(dm[j], 'dmg?'); key = (u['card'], own, dk); tot[key] += 1
            if j in pair:
                pt, pn = norm(preds[pair[j]])
                kind = 'ok' if (pt, pn) == (tt, tn) else 'wrong-owner' if pt != tt else 'wrong-class'
            else:
                t = r['truth'][j]
                near = [k for jj, k in pair.items() if norm(preds[k])[0] == tt and math.hypot(preds[k]['x']-t['x'], preds[k]['y']-t['y']) <= 1.5]
                kind = 'merge' if near else 'miss'
            if kind != 'ok':
                cnt[(kind,)+key] += 1
                errs.append(dict(id=r['id'], kind=kind, card=u['card'], owner=own, damaged=dm[j], x=u['x'], y=u['y'],
                                 **({'pred': preds[pair[j]]} if j in pair else {})))
        for k, q in enumerate(preds):
            if k not in pair.values():
                pt, pn = norm(q); cnt[('phantom', pn, 'ours' if pt == 0 else 'opp', '')] += 1
                errs.append(dict(id=r['id'], kind='phantom', name=pn, owner='ours' if pt == 0 else 'opp', x=q['x'], y=q['y'], score=q['score']))
    print(f'thr {a.thr}: {sum(tot.values())} truth units, {len(d["rows"])} frames')
    for kind in ('miss', 'merge', 'wrong-owner', 'wrong-class', 'phantom'):
        rows = sorted(((k, v) for k, v in cnt.items() if k[0] == kind), key=lambda kv: -kv[1])
        print(f'{kind} {sum(v for _, v in rows)}: ' + '; '.join(f"{' '.join(x for x in k[1:] if x)} {v}" + (f"/{tot[k[1:]]}" if k[1:] in tot else '')
                                                         for k, v in rows[:12]))
    if a.out:
        a.out.write_text(json.dumps(errs, indent=1))


if __name__ == '__main__':
    main()
