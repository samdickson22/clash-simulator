"""Round 3: unit P/R on the hand-labelled official frames (+ false units on empty official frames).

Truth: labels/<id>.json (hand labels, native coordinates: x from the arena's left, y from its top). Units with a vocabulary
card are identity truth; OOV/UNKNOWN units count for owner-only truth and are ignore regions (radius 1 tile) for identity
scoring. Excluded frames are skipped. Matching as eval_val.match (greedy by score), radius 1 tile (and 1.5).

  python eval_official.py --ckpt CKPT.pt | --export EXPORT_DIR  --labels DIR --out OUT.json [--empty IMG...]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

R = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R/'src'), str(R/'live/perception'), str(R/'live/loop')]
import canvas as LC  # noqa: E402
import common as C  # noqa: E402
from clasher.vision.l1_v4 import prepare_pixels  # noqa: E402

THRS = (.3, .35, .4, .45, .5, .6, .7)
KEYS = ('body_heatmap', 'body_box', 'body_hp', 'body_hp_visible', 'hud_cards', 'elixir_digit', 'elixir_fraction',
        'clock_seconds', 'phase')


class Model:
    def __init__(self, ckpt=None, export=None):
        if export:
            from infer import FRAME_KEYS
            self.m = torch.jit.load(str(Path(export)/'frame.pt'), map_location='cpu').eval(); self.keys = FRAME_KEYS
            v = json.loads((Path(export)/'vocab.json').read_text()); self.cards, self.ids = v['cards'], v['identities']; self.ts = True
        else:
            from clasher.vision.l1_v4 import PerceptionV4
            st = torch.load(ckpt, map_location='cpu', weights_only=False)
            self.m = PerceptionV4(len(st['cards']), len(st['identities'])); self.m.load_state_dict(st['model']); self.m.eval()
            self.cards, self.ids = st['cards'], st['identities']; self.ts = False

    @torch.inference_mode()
    def __call__(self, canvas_bgr):
        arena, hud = prepare_pixels(canvas_bgr)
        t = lambda x: torch.from_numpy(np.ascontiguousarray(x)).permute(2, 0, 1)[None].float().div(255)
        if self.ts:
            out = dict(zip(self.keys, self.m(t(arena), t(hud))))
        else:
            out = self.m.encode(t(arena), t(hud))
        out = {k: out[k].float().numpy() for k in KEYS}
        return C.decode_frame(out, 0, self.cards, self.ids, threshold=min(THRS), offsets=True, counts=False)


def match(preds, truth, radius, key, ignore=()):
    used, tp, fp = set(), 0, 0
    for s, x, y, c in sorted(preds, key=lambda p: -p[0]):
        best, bd = None, radius+1e-9
        for j, (tx, ty, tc) in enumerate(truth):
            if j in used or (key and tc != c):
                continue
            d = math.hypot(tx-x, ty-y)
            if d <= bd:
                best, bd = j, d
        if best is not None:
            used.add(best); tp += 1
        elif not any(math.hypot(ix-x, iy-y) <= 1. and (not key or io == c[0]) for ix, iy, io in ignore):
            fp += 1
    match.used = used
    return tp, fp, len(truth)-len(used)


def unknown_at(r, thr, card_max=1.):
    """common.decode_frame's unknown rule re-applied at threshold thr (the eval decodes once at the lowest threshold)."""
    units = [u for u in r['pred'] if u['score'] >= thr]; out = []
    for o in sorted((u for u in r['obj'] if u['score'] >= thr), key=lambda d: -d['score']):
        near = lambda d: d['owner'] == o['owner'] and math.hypot(d['x']-o['x'], d['y']-o['y']) <= 1.
        if any(near(u) for u in units) or any(near(k) for k in out) or o.get('card_max', 0.) >= card_max:
            continue
        if any(abs(o['x']*1000-ax) <= 1000 and abs(o['y']*1000-ay) <= 1000 for _, _, _, ax, ay in C.TOWER_SLOTS):
            continue
        out.append(o)
    return out


def score(rows, thr, radius, card_max=1.):
    agg = {}
    for r in rows:
        pr = [(u['score'], u['x'], u['y'], (u['owner'], u['identity'])) for u in r['pred'] if u['score'] >= thr]
        tid = [(t['x'], t['y'], (t['owner'], t['card'])) for t in r['truth'] if t['vocab']]
        ign = [(t['x'], t['y'], t['owner']) for t in r['truth'] if not t['vocab']]
        tow = [(t['x'], t['y'], t['owner']) for t in r['truth']]
        for name, (p, t, ig, key) in dict(id=(pr, tid, ign, True),
                                          owner=([(s, x, y, k[0]) for s, x, y, k in pr], tow, (), False)).items():
            tp, fp, fn = match(p, t, radius, key, ig)
            if key:
                for j, (_, _, (o, card)) in enumerate(t):
                    pc = agg.setdefault(f"{r['arena']}:card", {}).setdefault(card, [0, 0])
                    pc[0] += j in match.used; pc[1] += 1
            groups = (r['arena'], 'all')+((r['arena']+'-emptytruth',) if not r['truth'] else ())
            for arena in groups:
                a = agg.setdefault(f'{arena}:{name}', dict(tp=0, fp=0, fn=0, frames=0))
                a['tp'] += tp; a['fp'] += fp; a['fn'] += fn; a['frames'] += 1
    if any('unk' in r for r in rows):
        for r in rows:
            # unknown class: an unknown_units detection is decoded at the unit threshold (decode floor); keep score >= thr
            un = [(u['score'], u['x'], u['y'], u['owner']) for u in unknown_at(r, thr, card_max)]
            oov = [(t['x'], t['y'], t['owner']) for t in r['truth'] if not t['vocab']]
            known = [(t['x'], t['y'], t['owner']) for t in r['truth'] if t['vocab']]
            tp, fp, fn = match(un, oov, radius, True)
            used = match.used
            fp_known = sum(1 for i, (s_, x, y, o) in enumerate(sorted(un, key=lambda p: -p[0]))
                           if any(math.hypot(tx-x, ty-y) <= radius and to == o for tx, ty, to in known)
                           and not any(math.hypot(tx-x, ty-y) <= radius and to == o for tx, ty, to in oov))
            ob = [(u['score'], u['x'], u['y'], u['owner']) for u in r['obj'] if u['score'] >= thr]
            otp, ofp, ofn = match(ob, [(t['x'], t['y'], t['owner']) for t in r['truth']], radius, True)
            for arena in (r['arena'], 'all'):
                a = agg.setdefault(f'{arena}:unknown', dict(tp=0, fp=0, fn=0, frames=0, fp_on_known=0))
                a['tp'] += tp; a['fp'] += fp; a['fn'] += fn; a['frames'] += 1; a['fp_on_known'] += fp_known
                a = agg.setdefault(f'{arena}:anyunit', dict(tp=0, fp=0, fn=0, frames=0))
                a['tp'] += otp; a['fp'] += ofp; a['fn'] += ofn; a['frames'] += 1
    for k, a in agg.items():
        if k.endswith(':card'):
            continue
        a['P'] = round(a['tp']/max(1, a['tp']+a['fp']), 3); a['R'] = round(a['tp']/max(1, a['tp']+a['fn']), 3)
        a['fp_per_frame'] = round(a['fp']/max(1, a['frames']), 3)
    return agg


def grp(path):
    return 'TC' if 'tc2-r1' in path else 'BP' if '/s1m01/' in path else 'GS-live5(unseen match)' if '/live5/' in path else 'GS-other'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ckpt'); p.add_argument('--export'); p.add_argument('--labels', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--empty', nargs='*', default=[])
    p.add_argument('--threads', type=int, default=8)
    a = p.parse_args(); torch.set_num_threads(a.threads)
    m = Model(a.ckpt, a.export)
    ix = {x['id']: x for x in json.loads((a.labels.parent/'label/index.json').read_text())}
    rows = []
    for f in sorted(a.labels.glob('*.json')):
        lab = json.loads(f.read_text())
        if lab.get('exclude'):
            continue
        src = ix[lab['id']]['source']
        dec = m(LC.canvas(cv2.imread(src)))
        truth = [dict(x=float(u['x']), y=float(u['y']), owner=1 if u['owner'] == 'us' else 0, card=u['card'],
                      vocab=u['card'] in m.ids[:56]) for u in lab['units']]
        pred = [dict(identity=u['identity'], owner=u['owner'], x=u['x'], y=u['y'], score=u['score']) for u in dec['units']
                if u['identity'] not in C.TOWER_BODIES]
        unk = [dict(owner=u['owner'], kind=u['kind'], x=u['x'], y=u['y'], score=u['score']) for u in dec.get('unknown_units', ())]
        obj = [dict(owner=u['owner'], kind=u['kind'], x=u['x'], y=u['y'], score=u['score'], card_max=u['card_max']) for u in dec.get('objects', ())]
        rows.append(dict(id=lab['id'], arena=lab['id'][:2], truth=truth, pred=pred, **(dict(unk=unk, obj=obj) if 'objects' in dec else {})))
    res = dict(frames={k: sum(1 for r in rows if r['arena'] == k) for k in ('GS', 'TC')},
               units={k: sum(len(r['truth']) for r in rows if r['arena'] == k) for k in ('GS', 'TC')},
               metrics={f'thr{t}_r{rad}': score(rows, t, rad) for t in THRS for rad in (1., 1.5)})
    if any('obj' in r for r in rows):
        res['unknown_sweep'] = {f'thr{t}_cardmax{cm}': {k: v for k, v in score(rows, t, 1., cm).items() if k.endswith(':unknown')}
                                for t in (.3, .4, .5) for cm in (.1, .2, .3, .4, 1.)}
    emp = {}
    for path in a.empty:
        dec = m(LC.canvas(cv2.imread(path)))
        us = [u for u in dec['units'] if u['identity'] not in C.TOWER_BODIES]
        us = us+[dict(identity='UNKNOWN:'+u['kind'], **{k: u[k] for k in ('owner', 'x', 'y', 'score')}) for u in dec.get('unknown_units', ())]
        emp[path] = {f'thr{t}': [(u['identity'], u['owner'], round(u['x'], 1), round(u['y'], 1), round(u['score'], 3))
                                 for u in us if u['score'] >= t] for t in THRS}
    if emp:
        res['empty'] = dict(frames=len(emp), fp_per_frame={f'thr{t}': round(sum(len(v[f'thr{t}']) for v in emp.values())/len(emp), 3)
                                                           for t in THRS},
                            by_arena={g: {f'thr{t}': round(float(np.mean([len(v[f'thr{t}']) for k, v in emp.items() if grp(k) == g])), 3)
                                          for t in THRS} for g in sorted({grp(k) for k in emp})},
                            detail=emp)
    res['rows'] = rows
    a.out.write_text(json.dumps(res, indent=1))
    for k in ('thr0.5_r1.0', 'thr0.4_r1.0', 'thr0.5_r1.5'):
        print(k, {n: (v['P'], v['R'], v['fp_per_frame']) for n, v in res['metrics'][k].items() if 'P' in v})
    if emp:
        print('empty fp/frame', res['empty']['fp_per_frame'], res['empty']['by_arena'])


if __name__ == '__main__':
    main()
