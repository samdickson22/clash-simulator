"""Training/evaluation rows for the learned temporal owner (bot/live/owner_track.py) from recorded live runs and the
r3 owner's Sol labels (live-perc-r3 labels-yolo-raw/<SET>-<run>-<n>.json; x tiles from the left, y from the TOP: the
record frame is (x, 32 - y)).

Each run is replayed through the deployed LiveSession/LiveTranslator (bot/live/audit_plays), so the owner tracks see
exactly the translator's inputs at its own poll cadence: units with the detector's team, their raw classes
(units_yolo) and our own plays so far. A labelled unit is joined to the unit of the nearest poll (by capture time,
<= 150 ms) within 1 tile; its track takes the label (conflicting tracks are dropped). Rows: every poll-frame of a
labelled track within +-`window` ticks of a label, with `exact` = 1 at the labelled frame itself.

    python -m bot.live.owner_dataset --sets HARD3,HARD4 --exclude-runs s48,s50,s53,s56-m02 --out train.npz
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from bot.live.owner_track import NAMES, OwnerTracks

LABELS = Path('/mpac/sdicks02/scratch/live-perc-r3/labels-yolo-raw')
CLASSES = Path(__file__).resolve().parents[2] / 'live/yolo_synth/classes.json'


def labels(sets, include=None, exclude=()):
    """-> {run: {n: [(owner 1 opp / 0 ours, x, y record frame, card)]}} for complete frames, sure owners ('opp' /
    'us'; 'unsure' is skipped)."""
    out = defaultdict(dict)
    for s in sets:
        for f in sorted(glob.glob(str(LABELS / f'{s}-*.json'))):
            d = json.loads(Path(f).read_text())
            m = re.search(r'(s\d+[a-z]?-m\d+)-(\d+)$', d['id'])
            if not m or not d.get('complete') or d.get('exclude'):
                continue
            run, n = m.group(1), int(m.group(2))
            keys = {run, run.split('-')[0]}           # a whole session ('s53') or one run ('s56-m02')
            if keys & set(exclude) or (include and not keys & set(include)):
                continue
            us = [(1 if u['owner'] == 'opp' else 0, float(u['x']), 32. - float(u['y']), u.get('card'))
                  for u in d.get('units', ()) if u.get('owner') in ('opp', 'us', 'ours')]
            out[run][n] = us
    return out


def capture(run, rt):
    """Replay a run's battles through the deployed session; per translator call: (timestamp_ms, units, raw, own)."""
    from bot.live import audit_plays as A
    from bot.live import translate as T
    import inspect
    d = A.RUNS_ROOT / run
    cfg = json.loads((d / 'session-config.json').read_text())
    known = set(inspect.signature(T.LiveSession.__init__).parameters)
    cfg = dict(cfg, session={k: v for k, v in cfg.get('session', {}).items() if k in known | {'cls'}})
    if cfg['session'].get('cls') not in (None, 'bot.live.translate.LiveSession'):
        cfg['session'] = dict(cfg['session'], cls='bot.live.translate.LiveSession')
    recs, ev, dec = A.jsonl(d / 'perception.jsonl'), A.jsonl(d / 'events.jsonl', optional=True), \
        A.jsonl(d / 'decisions.jsonl', optional=True)
    ts_of_n = {r.get('n'): r.get('timestamp_ms', r.get('ts_ms')) for r in recs}
    cap, orig = [], T.LiveTranslator.information

    def information(self, record):
        own = [(e['tick'], e['name'], e['x'], e['y']) for e in self.public_events if e['seat'] == 0]
        if not record.get('_synthetic'):
            cap.append((record.get('timestamp_ms'), record.get('tick'), [dict(u) for u in record.get('units') or ()],
                        record.get('units_yolo'), own))
        return orig(self, record)
    T.LiveTranslator.information = information
    battles = []
    try:
        for anchor, rows in A.battles(recs, ev):
            cap.clear()
            A.replay_battle(rt, cfg, rows, ev, dec, anchor, None, None)
            battles.append(list(cap))
    finally:
        T.LiveTranslator.information = orig
    return battles, ts_of_n, cfg.get('deck', ())


def build(runs_labels, rt, classes, window=60):
    X, y, exact, det, meta = [], [], [], [], []
    stats = Counter()
    for run, frames in sorted(runs_labels.items()):
        battles, ts_of_n, deck = capture(run, rt)
        for b, cap in enumerate(battles):
            tr = OwnerTracks(classes, deck)
            seq = []
            for ts, tick, units, raw, own in cap:
                rows, ids = tr.update(tick, units, raw, own)
                seq.append((ts, tick, units, rows, ids))
            # join labels: label frame -> nearest poll by capture time
            lab_track, lab_points = defaultdict(Counter), []
            for n, us in frames.items():
                ts = ts_of_n.get(n)
                if ts is None:
                    continue
                k = min(range(len(seq)), key=lambda i: abs((seq[i][0] or 0) - ts), default=None)
                if k is None or abs((seq[k][0] or 0) - ts) > 150:
                    stats['label_frame_unpolled'] += 1
                    continue
                _, tick, units, rows, ids = seq[k]
                used = set()
                for o, lx, ly, card in us:
                    j = min((j for j in range(len(units)) if j not in used),
                            key=lambda j: math.hypot(float(units[j]['x']) - lx, float(units[j]['y']) - ly), default=None)
                    if j is None or math.hypot(float(units[j]['x']) - lx, float(units[j]['y']) - ly) > 1.:
                        stats['label_unit_unmatched'] += 1
                        continue
                    used.add(j)
                    lab_track[ids[j]][o] += 1
                    lab_points.append((k, j, o))
                    stats['label_unit_matched'] += 1
            owner_of = {tid: c.most_common(1)[0][0] for tid, c in lab_track.items() if len(c) == 1}
            stats['tracks_labelled'] += len(owner_of)
            stats['tracks_conflicting'] += sum(len(c) > 1 for c in lab_track.values())
            exact_at = {(k, j) for k, j, o in lab_points}
            label_ticks = defaultdict(list)
            for k, j, o in lab_points:
                label_ticks[seq[k][4][j]].append(seq[k][1])
            for k, (ts, tick, units, rows, ids) in enumerate(seq):
                for j, (row, tid) in enumerate(zip(rows, ids)):
                    if tid not in owner_of or not any(abs(tick - lt) <= window for lt in label_ticks[tid]):
                        continue
                    X.append(row); y.append(owner_of[tid]); exact.append((k, j) in exact_at)
                    det.append(int(units[j]['owner']) == 1 and 1 or 0)
                    meta.append((run, b, tid, tick))
        print(run, dict(stats), file=sys.stderr, flush=True)
    return (np.array(X, np.float32).reshape(-1, len(NAMES)), np.array(y, np.int8), np.array(exact, bool),
            np.array(det, np.int8), meta, stats)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sets', required=True)
    ap.add_argument('--include-runs', default='')
    ap.add_argument('--exclude-runs', default='')
    ap.add_argument('--window', type=int, default=60)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    from bot.players.runtime import Runtime
    rt = Runtime()
    classes = {e['name']: e for e in json.loads(CLASSES.read_text())['names']}
    inc = set(filter(None, a.include_runs.split(',')))
    exc = set(filter(None, a.exclude_runs.split(',')))
    L = labels(a.sets.split(','), inc or None, exc)
    X, y, exact, det, meta, stats = build(L, rt, classes, a.window)
    np.savez_compressed(a.out, X=X, y=y, exact=exact, det=det, names=np.array(NAMES),
                        run=np.array([m[0] for m in meta]), battle=np.array([m[1] for m in meta], np.int16),
                        track=np.array([m[2] for m in meta], np.int32), tick=np.array([m[3] for m in meta], np.int32))
    Path(a.out + '.stats.json').write_text(json.dumps(dict(stats=stats, runs=sorted(L), rows=int(len(y)),
                                                           exact=int(exact.sum())), indent=1))
    print(json.dumps(dict(rows=int(len(y)), exact=int(exact.sum()), opp=int(y.sum()), **stats)))


if __name__ == '__main__':
    sys.exit(main())
