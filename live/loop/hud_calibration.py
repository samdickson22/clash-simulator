"""Per-card precision of the HUD's coloured own-hand reads, by confidence bin, against the video truth (slot_audit.py).

  python hud_calibration.py RUN_DIR [RUN_DIR ...] [--out CAL.json] [--jobs 12]

For each (read card, p bin) over COLOURED non-empty slot frames: n and precision = P(video truth == read). The bins are
BINS. Printed as the CAL literal drive.py embeds (cells with n < MIN_N are left out = untrusted).
"""
import argparse
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CACHE = '/mpac/sdicks02/scratch/live-loop/slot-cache'
BINS = (0., .3, .5, .7, .9)
MIN_N = 30


def frames(d):
    import slot_audit
    fr = []
    slot_audit.audit(d, cache=CACHE, frames=fr)
    return [f for f in fr if f['coloured'] and f['card'] and f['p'] is not None]


def bin_of(p):
    return max(i for i, b in enumerate(BINS) if p >= b)


def table(F):
    c = defaultdict(lambda: [0, 0])
    for f in F:
        k = (f['card'], bin_of(f['p']))
        c[k][0] += 1; c[k][1] += f['truth'] == f['card']
    return {card: {b: (n, ok / n) for (cc, b), (n, ok) in c.items() if cc == card} for card in sorted({k[0] for k in c})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--out')
    ap.add_argument('--jobs', type=int, default=12)
    a = ap.parse_args()
    with Pool(a.jobs) as p:
        F = [f for fr in p.map(frames, a.runs) for f in fr]
    T = table(F)
    for card, row in T.items():
        print(card, {f'{BINS[b]:.1f}': f'{pr:.3f} (n={n})' for b, (n, pr) in sorted(row.items())})
    cal = {card: [round(row[b][1], 3) if b in row and row[b][0] >= MIN_N else None for b in range(len(BINS))]
           for card, row in T.items()}
    print('CAL =', json.dumps(cal))
    if a.out:
        Path(a.out).write_text(json.dumps(dict(bins=BINS, min_n=MIN_N, runs=a.runs, frames=len(F), cal=cal,
                                               table={c: {str(b): v for b, v in r.items()} for c, r in T.items()}), indent=1))


if __name__ == '__main__':
    main()
