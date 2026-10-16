"""Round 3 data prep: one empty-arena background per renderer match (train + validation only; HeldoutGuard).

Background = the earliest frame in the first 8 cache blocks whose label row has all 6 towers, no unit positives and no
ignore objects (match start, before the first deployment). Saved losslessly as JOB/bg/<episode>.png (832x448 arena-cache BGR).

  python r3/prep_bg.py --labels LABELS --out JOB/bg --workers 14
"""
import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C  # noqa: E402
import dense_labels as D  # noqa: E402


def build(job):
    ep, split, labels, out = job
    guard = C.HeldoutGuard(); guard.check([ep])
    dst = Path(out)/f'{ep}.png'
    if dst.exists():
        return ep, split, 'cached', None
    lab = D.load(Path(labels)/f'{ep}.npz')
    if str(lab['split']) != split:
        raise AssertionError('label split mismatch')
    px = C.Pixels(guard, ep, C.load_receipt(guard, ep, split))
    for k in range(min(8, len(px.idx['blocks']))):
        ar = None
        for i in range(k*px.bs, min(px.n, (k+1)*px.bs)):
            got = D.frame_objects(lab, i)
            if got is None:
                continue
            cls, own, x, y, frac, ig = got
            if (cls >= 56).sum() == 6 and (cls < 56).sum() == 0 and len(ig) == 0:
                if ar is None:
                    ar, _ = px.block(k)
                cv2.imwrite(str(dst), ar[i-k*px.bs])
                return ep, split, 'built', i
    return ep, split, 'none', None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--labels', type=Path, default=Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels'))
    p.add_argument('--out', type=Path, required=True); p.add_argument('--workers', type=int, default=14)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    guard = C.HeldoutGuard()
    jobs = [(ep, s, str(a.labels), str(a.out)) for s in ('train', 'validation') for ep in guard.episodes(s)]
    guard.check([j[0] for j in jobs])
    res = {}
    with Pool(a.workers) as pool:
        for k, (ep, s, status, i) in enumerate(pool.imap_unordered(build, jobs)):
            res[ep] = dict(split=s, status=status, frame=i)
            if k % 50 == 0:
                print(k, len(jobs), ep, status, i, flush=True)
    old = json.loads((a.out/'index.json').read_text()) if (a.out/'index.json').exists() else {}
    old.update({e: r for e, r in res.items() if r['status'] != 'cached'})
    (a.out/'index.json').write_text(json.dumps(old, indent=1))
    print(json.dumps({s: sum(1 for r in res.values() if r['status'] == s) for s in ('built', 'cached', 'none')}))


if __name__ == '__main__':
    main()
