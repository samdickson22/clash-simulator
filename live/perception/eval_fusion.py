"""Offline EventTracker variants on the per-frame VALIDATION dump (dump_records.py), CPU only (LIVE integration (a)).

Replays the tracker from each frame's stored event peaks + low-score unit detections, so a configuration costs
seconds instead of a perception pass. Scoring = eval_events (same side+card, detection time in [exec, exec+W],
Hungarian). Also reports the latency the hold adds (matched truth events: detection - execution, and the per-event
difference vs the baseline tracker on the events both match).

  python eval_fusion.py DUMP_DIR OUT.json [--grid default|small|hold-only|JSON cfg or list] [--half all|even|odd] [--workers 4]
Selection rule (exploration tier, validation only): best all-events F1 at W=1000 on the EVEN half; configs within 0.01
of it -> lowest median latency; then reported on the ODD half and on all 64 (select_fusion()).
"""
import argparse
import gzip
import itertools
import json
import math
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import torch

from events import EventTracker
from eval_events import score, summarize, per_card
from infer import SPELLS

BASE = dict(threshold=.6)
CARDS = None


def load(path):
    with gzip.open(path, 'rt') as f:
        head = json.loads(f.readline())
        frames = [json.loads(x) for x in f]
    if head.get('split') != 'validation':
        raise ValueError(f'{path}: not a validation dump')
    return head, frames


def truth_of(head, cards):
    return [dict(card=e['card'], side=e['side'], x=e['tile'][0], y=e['tile'][1], exec_ms=e['exec_tick']*50.)
            for e in head['truth_events'] if e['card'] in cards]


def prepare(frames):
    return [(fr['ts'], [(s, x, y, e, torch.tensor(p), age) for s, x, y, e, age, p in fr['peaks']], fr['units_lo']) for fr in frames]


def run_tracker(pre, cards, cfg):
    tr = EventTracker(cards, **cfg); preds = []
    for ts, pk, units in pre:
        for c in tr.update(None, ts, peaks=pk, units=units):
            preds.append(dict(card=c['card'], side=c['side'], x=c['x_tiles'], y=c['y_tiles'], exec_ms=c['execution_timestamp_ms'],
                              det_ms=c['det_ms'], score=1.0, head_card=c['head_card']))
    return preds, tr.revised


def _match_job(args):
    path, cfgs = args
    head, frames = load(path)
    cards = CARDS
    truth = truth_of(head, cards)
    out = []; pre = prepare(frames)
    for cfg in cfgs:
        preds, rev = run_tracker(pre, cards, cfg)
        out.append((preds, rev))
    return head['episode'], truth, out


def latency(allp, allt, W):
    """-> {event key: det-exec} over matched truth events (key = match idx, truth idx)."""
    lat = {}
    for m, (preds, truth) in enumerate(zip(allp, allt)):
        P, pairs = score(preds, truth, W, 0.)
        for i, j in pairs:
            lat[(m, j)] = P[i]['det_ms']-truth[j]['exec_ms']
    return lat


def grid(name):
    if name == 'small':
        return [dict(BASE), dict(BASE, hold_ms=500.), dict(BASE, hold_ms=700., vote_min=.5)]
    cfgs = [dict(BASE), dict(BASE, threshold=.5)]
    for th, hold, vmin, prior, ur, agree, early in itertools.product((.5, .6), (300., 500., 700., 900.), (.2, .35, .5),
                                                                      (0., .02), (1.5, 2.5), (0, 2), (None, .6)):
        cfgs.append(dict(threshold=th, hold_ms=hold, max_hold_ms=hold, vote_min=vmin, prior_min=prior, unit_radius=ur,
                         agree_frames=agree, early_share=early))
    if name == 'hold-only':        # ablation: the hold without body votes (vote_min unreachable)
        return [dict(BASE), dict(BASE, threshold=.5)] + [dict(threshold=th, hold_ms=h, max_hold_ms=h, vote_min=1e9, agree_frames=0)
                                                         for th in (.5, .6) for h in (300., 500., 700., 900.)]
    return cfgs


def select(rows, tol=.01):
    f1 = lambda m: 2*m['precision']*m['recall']/max(1e-9, m['precision']+m['recall'])
    best = max(f1(r['W1000']['all']) for r in rows)
    ok = [r for r in rows if f1(r['W1000']['all']) >= best-tol]
    return min(ok, key=lambda r: (r['latency']['median'], r['latency']['p90'], -f1(r['W1000']['all'])))['cfg']


def main():
    global CARDS
    ap = argparse.ArgumentParser(); ap.add_argument('dump', type=Path); ap.add_argument('out', type=Path)
    ap.add_argument('--grid', default='default'); ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--max-matches', type=int, default=0)
    ap.add_argument('--half', choices=['all', 'even', 'odd'], default='all', help='matches by sorted index (split-half selection)')
    ap.add_argument('--vocab', default='/mpac/sdicks02/jobs/clasher/live-perception-20261014/export-final/vocab.json')
    a = ap.parse_args(); torch.set_num_threads(1)
    CARDS = json.loads(Path(a.vocab).read_text())['cards']
    files = sorted(a.dump.glob('*.jsonl.gz'))
    files = files[:a.max_matches] if a.max_matches else files
    files = files if a.half == 'all' else files[0 if a.half == 'even' else 1::2]
    cfgs = grid(a.grid) if not a.grid.startswith('{') and not a.grid.startswith('[') else \
        [dict(BASE)] + [c for c in (json.loads(a.grid) if a.grid.startswith('[') else [json.loads(a.grid)])]
    with Pool(a.workers) as pool:
        res = pool.map(_match_job, [(f, cfgs) for f in files])
    allt = [t for _, t, _ in res]
    base_lat = None; rows = []
    for k, cfg in enumerate(cfgs):
        allp = [o[k][0] for _, _, o in res]; rev = sum(o[k][1] for _, _, o in res)
        row = dict(cfg=cfg, revised=rev, emitted=sum(len(p) for p in allp))
        for W in (1000, 1500):
            row[f'W{W}'] = summarize(allp, allt, W, 0.)
        lat = latency(allp, allt, 1500)
        if k == 0:
            base_lat = lat
        both = [lat[e]-base_lat[e] for e in lat if e in base_lat]
        v = np.asarray(list(lat.values()) or [0.])
        row['latency'] = dict(median=float(np.median(v)), p90=float(np.quantile(v, .9)),
                              added_vs_base_median=float(np.median(both)) if both else None,
                              added_vs_base_p90=float(np.quantile(both, .9)) if both else None, n_common=len(both))
        if k == 0 or cfg.get('hold_ms'):
            row['per_card_W1000'] = per_card(allp, allt, 1000, 0.) if k in (0,) else None
        rows.append(row)
        w = row['W1000']
        print(json.dumps(dict(k=k, cfg=cfg, all=(w['all']['precision'], w['all']['recall']),
                              opp_troop=(w['opp_troop_building']['precision'], w['opp_troop_building']['recall']),
                              opp_spell=(w['opp_spell']['precision'], w['opp_spell']['recall']), lat=row['latency'])), flush=True)
    a.out.write_text(json.dumps(dict(schema='clasher.live.event-fusion-eval.v1', split='validation', heldout_opened=False,
                                     matches=[e for e, _, _ in res], truth_events=sum(len(t) for t in allt), rows=rows), indent=1)+'\n')
    with (a.out.with_suffix('.preds.jsonl')).open('w') as f:
        for (ep, truth, o) in res:
            f.write(json.dumps(dict(episode=ep, base=o[0][0]))+'\n')


if __name__ == '__main__':
    main()
