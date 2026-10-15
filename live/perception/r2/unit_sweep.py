"""Round 2: unit recall and phantom (false-positive) units per frame per side vs unit threshold, from a validation dump's
units_lo (>= 0.25), matched exactly as bot/live/empirical.fit (owner-only greedy <= 1 tile). Optional count extras.

  python live/perception/r2/unit_sweep.py DUMP_DIR OUT.json [--thresholds .4,.5,.6]
Proxy (linear in the 2026-10-15 ablation endpoints, ABLATION.md; pooled R3a/v1): removing all misses (recall .811 -> 1)
= +0.0435, removing all phantoms (0.38/frame -> 0) = +0.0485 => value ~ 0.230*recall - 0.128*phantoms_per_frame (both sides).
"""
import argparse, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from bot.live.real_replay import load_dump  # noqa: E402
from bot.live.empirical import _greedy  # noqa: E402

A_RECALL, B_FP = .0435/(1-.811), .0485/.38


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dump'); ap.add_argument('out')
    ap.add_argument('--thresholds', default='.35,.4,.45,.5,.55,.6,.65,.7')
    ap.add_argument('--group', action='store_true', help='also separate thresholds for single-body / MULTI_BODY cards')
    ap.add_argument('--half', choices=('all', 'even', 'odd'), default='all')
    a = ap.parse_args(); ths = [float(t) for t in a.thresholds.split(',')]
    sys.path.insert(0, str(REPO/'live/perception'))
    from common import MULTI_BODY
    variants = [(t, t, c) for t in ths for c in (True, False)]
    if a.group:
        variants += [(ts, tm, c) for ts in ths for tm in ths if ts != tm for c in (True, False)]
    acc = {v: dict(tot=0, hit=0, fp0=0, fp1=0) for v in variants}; frames = 0; has_counted = False
    files = sorted(Path(a.dump).glob('*.jsonl.gz'))
    files = files if a.half == 'all' else files[0 if a.half == 'even' else 1::2]
    for f in files:
        _, rows = load_dump(f)
        for r in rows:
            tr = r['truth']
            if tr.get('objects_stale'):
                continue
            frames += 1
            lo = [u for u in r['units_lo'] if not u.get('effect')]
            has_counted |= any(u.get('counted') for u in lo)
            for (ts, tm, c) in variants:
                P_all = [u for u in lo if u['score'] >= (tm if u['card'] in MULTI_BODY else ts) and (c or not u.get('counted'))]
                d = acc[(ts, tm, c)]
                for owner in (0, 1):
                    T = [u for u in tr['units'] if u['owner'] == owner]; P = [u for u in P_all if u['owner'] == owner]
                    pairs = _greedy(P, T, 1.)
                    d['tot'] += len(T); d['hit'] += len(pairs); d[f'fp{owner}'] += len(P)-len(pairs)
    rows = []
    for (ts, tm, c), d in acc.items():
        if not has_counted and not c:
            continue
        R = d['hit']/max(1, d['tot']); fp0, fp1 = d['fp0']/frames, d['fp1']/frames
        rows.append(dict(threshold=ts, threshold_multi=tm, count_extras=c, recall=round(R, 4), fp_per_frame_own=round(fp0, 4), fp_per_frame_opp=round(fp1, 4),
                         proxy=round(A_RECALL*R-B_FP*(fp0+fp1), 4)))
    rows.sort(key=lambda r: -r['proxy'])
    Path(a.out).write_text(json.dumps(dict(dump=a.dump, half=a.half, frames=frames, a_recall=A_RECALL, b_fp=B_FP, rows=rows), indent=1))
    for r in rows[:15]:
        print(r)


if __name__ == '__main__':
    main()
