"""New-card labelling (SpearGoblins / Tombstone / Bomber / GoblinCage): pick frames from the loop owner's manifest and render
labelling sheets (same layout as label_prep.py). Images stay in 05 scratch, never committed.

Frames: inside each candidate window every `--win-step` ticks, plus uniform battle coverage every `--uni-step` ticks, at most
`--cap` per battle, spaced >= `--min-gap` ticks. Held-out battles (`--heldout`) are skipped (they are the per-card eval set).

  python newcard_prep.py MANIFEST OUT_DIR --heldout s1-m01,s2-m01,s5-m01,s7-m04
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from label_prep import arena_img, grid  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument('manifest', type=Path); p.add_argument('out', type=Path)
    p.add_argument('--heldout', default=''); p.add_argument('--win-step', type=float, default=30.)
    p.add_argument('--uni-step', type=float, default=150.); p.add_argument('--min-gap', type=float, default=20.)
    p.add_argument('--cap', type=int, default=18)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    held = set(filter(None, a.heldout.split(',')))
    index = []
    for line in a.manifest.read_text().splitlines():
        m = json.loads(line)
        if m['run'] in held:
            continue
        rows = [json.loads(x) for x in Path(m['frames']).read_text().splitlines() if x.strip()]
        bt = [(r['n'], r['tick']) for r in rows if r.get('state') == 'battle' and r.get('tick') is not None]
        if not bt:
            continue
        ns, ticks = np.array([n for n, _ in bt]), np.array([t for _, t in bt])
        want = []
        for lo, hi in m.get('candidate_windows', []):
            want += list(np.arange(lo, hi+1, a.win_step))
        want += list(np.arange(ticks[0]+40, ticks[-1]-40, a.uni_step))
        chosen = []
        for t in sorted(want):
            j = int(np.argmin(np.abs(ticks-t)))
            if all(abs(ticks[j]-ticks[k]) >= a.min_gap for k in chosen):
                chosen.append(j)
        if len(chosen) > a.cap:
            chosen = [chosen[int(i)] for i in np.linspace(0, len(chosen)-1, a.cap).round()]
        vd = Path(m['video_dir'])
        for j in chosen:
            n = int(ns[j]); src = vd/f'{n:06d}.jpg'
            if not src.exists():
                continue
            fid = f"NC-{m['run']}-{n:06d}"
            cur = arena_img(src); prev = arena_img(vd/f'{max(0, n-10):06d}.jpg') if (vd/f'{max(0, n-10):06d}.jpg').exists() else cur
            sheet = np.hstack([prev, np.full((cur.shape[0], 8, 3), 255, np.uint8), cur, np.full((cur.shape[0], 8, 3), 255, np.uint8), grid(cur)])
            cv2.imwrite(str(a.out/f'{fid}.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
            index.append(dict(id=fid, run=m['run'], arena=m['arena'], tick=float(ticks[j]), n=n, source=str(src),
                              target_cards=m['target_cards'], opp_deck=m['opp_deck'], sheet=str(a.out/f'{fid}.jpg')))
    (a.out/'index.json').write_text(json.dumps(index, indent=1))
    print(len(index), {r: sum(1 for x in index if x['run'] == r) for r in sorted({x['run'] for x in index})})


if __name__ == '__main__':
    main()
