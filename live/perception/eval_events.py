"""Streaming VALIDATION play-event metrics (TemporalHead + EventFusion), exploration tier.

Replays each validation match at --stride (2 = ~10 FPS): backbone per frame, 16-frame ring of the
latest processed frames, visual births, TemporalHead, then l1_v4.EventFusion (300 ms / 1.5 tile dedupe).
Match rule (as scoring_v4 point mode, plus a 1000 ms variant): same native side and card, detection
frame time in [exec, exec + W]; maximum cardinality (Hungarian). Placement error is reported on matches.

  python live/perception/eval_events.py --checkpoint CKPT --out DIR --stride 2
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import linear_sum_assignment

import common as C
from finetune2 import SPELLS, visual_births

WINDOWS = (500, 1000)
THRESHOLDS = (.3, .4, .5, .6, .7)


def run_match(model, guard, ep, stride, device, cards, fusion_threshold):
    from clasher.vision.l1_v4 import EventFusion
    rec = C.load_receipt(guard, ep, 'validation'); px = C.Pixels(guard, ep, rec)
    import dense_labels as D
    lab = D.load(Path(ARGS.labels)/f'{ep}.npz'); tick = lab['tick']
    idx = list(range(0, px.n, stride)); feats = []; times = []
    with torch.inference_mode():
        for k in sorted({i//px.bs for i in idx}):
            ar, _ = px.block(k); sel = [i for i in range(k*px.bs, min(px.n, (k+1)*px.bs)) if i % stride == 0]
            x = torch.from_numpy(np.ascontiguousarray(ar[[i-k*px.bs for i in sel]])).to(device).permute(0, 3, 1, 2).float()/255
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=device == 'cuda'):
                feats.append(model.backbone(x).float())
            times += [float(tick[i])*50. for i in sel]
        feats = torch.cat(feats); times = np.asarray(times); N = len(times)
        fusion = EventFusion(cards, SPELLS, {'default': fusion_threshold}, {})
        from events import EventTracker
        trackers = {th: EventTracker(cards, threshold=th) for th in THRESHOLDS}; tpreds = {th: [] for th in THRESHOLDS}
        preds = []
        B = 48
        for s in range(0, N, B):
            ends = list(range(s, min(N, s+B)))
            cache = torch.zeros(len(ends), 16, *feats.shape[1:], device=device); ages = torch.zeros(len(ends), 16, device=device)
            valid = torch.zeros(len(ends), 16, dtype=torch.bool, device=device)
            for r, e in enumerate(ends):
                lo = max(0, e-15); m = e-lo+1
                cache[r, 16-m:] = feats[lo:e+1]
                ages[r, 16-m:] = torch.from_numpy(times[e]-times[lo:e+1]).float().to(device); valid[r, 16-m:] = True
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=device == 'cuda'):
                births = visual_births(model, cache, ages, valid)
                out = model.temporal(cache, ages, valid, births.float())
            out = {k: v.float() for k, v in out.items()}
            for r, e in enumerate(ends):
                o = {k: v[r:r+1] for k, v in out.items()}
                pk = trackers[THRESHOLDS[0]].peaks(o)
                for th, tr in trackers.items():
                    for c in tr.update(o, times[e], peaks=pk):
                        tpreds[th].append(dict(card=c['card'], side=c['side'], x=c['x_tiles'], y=c['y_tiles'], exec_ms=c['execution_timestamp_ms'],
                                               det_ms=c['det_ms'], score=1.0))
                for c in fusion.update(o, times[e], times[e], list(cards)):
                    preds.append(dict(card=c.card, side=c.side, x=c.x_tiles-.25, y=c.y_tiles-.25,  # placements are tile centres: gx/2 exec_ms=c.execution_timestamp_ms,
                                      det_ms=float(times[e]), score=c.existence_q))
    truth = [dict(card=e['card'], side=e['side'], x=e['tile'][0], y=e['tile'][1], exec_ms=e['exec_tick']*50.)
             for e in C.read_jsonl(C.MATCHES/ep/'events.jsonl') if e['accepted'] and e['kind'] != 'champion ability' and e['card'] in cards]
    return preds, truth, N, tpreds


def score(preds, truth, W, th):
    P = [p for p in preds if p['score'] >= th]; pairs = []
    keys = defaultdict(lambda: ([], []))
    for i, p in enumerate(P):
        keys[(p['card'], p['side'])][0].append(i)
    for j, t in enumerate(truth):
        keys[(t['card'], t['side'])][1].append(j)
    for (pi, ti) in keys.values():
        if not pi or not ti:
            continue
        cost = np.full((len(pi), len(ti)), 1e6)
        for a, i in enumerate(pi):
            for b, j in enumerate(ti):
                d = P[i]['det_ms']-truth[j]['exec_ms']
                if 0 <= d <= W:
                    cost[a, b] = d
        r, c = linear_sum_assignment(cost)
        pairs += [(pi[a], ti[b]) for a, b in zip(r, c) if cost[a, b] < 1e6]
    return P, pairs


def summarize(allp, allt, W, th):
    res = {}
    groups = {'all': lambda e: True, 'opp': lambda e: e['side'] != C.OWN_NATIVE, 'own': lambda e: e['side'] == C.OWN_NATIVE,
              'opp_spell': lambda e: e['side'] != C.OWN_NATIVE and e['card'] in SPELLS,
              'opp_troop_building': lambda e: e['side'] != C.OWN_NATIVE and e['card'] not in SPELLS}
    for name, f in groups.items():
        tp = fp = fn = 0; dists = []; lat = []
        for preds, truth in zip(allp, allt):
            P, pairs = score(preds, truth, W, th)
            mp = {i for i, _ in pairs}; mt = {j for _, j in pairs}
            tp += sum(1 for i, j in pairs if f(truth[j]))
            fp += sum(1 for i, p in enumerate(P) if i not in mp and f(p))
            fn += sum(1 for j, t in enumerate(truth) if j not in mt and f(t))
            for i, j in pairs:
                if f(truth[j]):
                    dists.append(math.hypot(P[i]['x']-truth[j]['x'], P[i]['y']-truth[j]['y'])); lat.append(P[i]['det_ms']-truth[j]['exec_ms'])
        d = np.asarray(dists) if dists else np.zeros(1); l = np.asarray(lat) if lat else np.zeros(1)
        res[name] = dict(precision=round(tp/max(1, tp+fp), 4), recall=round(tp/max(1, tp+fn), 4), tp=tp, fp=fp, fn=fn,
                         placement_median_tiles=round(float(np.median(d)), 3), placement_p90_tiles=round(float(np.quantile(d, .9)), 3),
                         within_1_tile=round(float((d <= 1).mean()), 4), latency_median_ms=round(float(np.median(l)), 1))
    return res


def per_card(allp, allt, W, th):
    c = defaultdict(lambda: [0, 0, 0])
    for preds, truth in zip(allp, allt):
        P, pairs = score(preds, truth, W, th); mt = {j for _, j in pairs}; mp = {i for i, _ in pairs}
        for j, t in enumerate(truth):
            c[(t['side'], t['card'])][0 if j in mt else 2] += 1
        for i, p in enumerate(P):
            if i not in mp:
                c[(p['side'], p['card'])][1] += 1
    rows = [dict(owner='own' if s == C.OWN_NATIVE else 'opp', card=k, tp=v[0], fp=v[1], fn=v[2],
                 recall=round(v[0]/max(1, v[0]+v[2]), 3), precision=round(v[0]/max(1, v[0]+v[1]), 3)) for (s, k), v in c.items()]
    return sorted(rows, key=lambda r: -(r['tp']+r['fn']))


def main():
    global ARGS
    p = argparse.ArgumentParser(); p.add_argument('--checkpoint', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--stride', type=int, default=2); p.add_argument('--device', default='cuda'); p.add_argument('--max-matches', type=int, default=0)
    p.add_argument('--labels', default='/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels')
    a = p.parse_args(); ARGS = a; a.out.mkdir(parents=True, exist_ok=True); torch.set_num_threads(3)
    from clasher.vision.l1_v4 import PerceptionV4
    guard = C.HeldoutGuard(); eps = guard.episodes('validation'); eps = eps[:a.max_matches] if a.max_matches else eps; guard.check(eps)
    st = torch.load(a.checkpoint, map_location='cpu', weights_only=False)
    model = PerceptionV4(len(st['cards']), len(st['bodies'])); model.load_state_dict(st['model']); model.to(a.device).eval()
    allp, allt = [], []; frames = 0; alltr = {th: [] for th in THRESHOLDS}
    for k, ep in enumerate(eps):
        preds, truth, n, tpreds = run_match(model, guard, ep, a.stride, a.device, st['cards'], min(THRESHOLDS))
        allp.append(preds); allt.append(truth); frames += n
        for th in THRESHOLDS:
            alltr[th].append(tpreds[th])
        print(json.dumps(dict(match=k+1, of=len(eps), preds=len(preds), truth=len(truth))), flush=True)
    res = dict(schema='clasher.live.event-eval.v1', split='validation', heldout_opened=False, checkpoint=str(a.checkpoint),
               checkpoint_sha256=C.sha(a.checkpoint), stride=a.stride, approx_fps=round(20/a.stride, 1), matches=len(eps), frames=frames,
               truth_events=sum(len(t) for t in allt),
               metrics={f'W={W}ms': {str(th): summarize(allp, allt, W, th) for th in THRESHOLDS} for W in WINDOWS},
               per_card_W1000_t05=per_card(allp, allt, 1000, .5),
               tracker_metrics={f'W={W}ms': {str(th): summarize(alltr[th], allt, W, 0.) for th in THRESHOLDS} for W in WINDOWS},
               tracker_per_card_W1000_t04=per_card(alltr[.4], allt, 1000, 0.),
               rule='same native side+card; detection frame time in [exec, exec+W]; Hungarian; EventFusion dedupe 300 ms/1.5 tiles')
    (a.out/'events.json').write_text(json.dumps(res, indent=1)+'\n')
    with (a.out/'predictions.jsonl').open('w') as f:
        for k, (ep, preds) in enumerate(zip(eps, allp)):
            f.write(json.dumps(dict(episode=ep, preds=preds, tracker={str(th): alltr[th][k] for th in THRESHOLDS}))+'\n')
    for th in ('0.3', '0.4', '0.5'):
        m = res['tracker_metrics']['W=1000ms'][th]
        print('tracker', th, json.dumps({k: (v['precision'], v['recall'], v['placement_median_tiles']) for k, v in m.items()}), flush=True)


if __name__ == '__main__':
    main()
