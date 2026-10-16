"""Background bank for the YOLO compositor (568x896 KataCR arena crop space).

  python prep_bgs.py BANK [--sheet SHEET.jpg]

- official floors: training-eligible recordings only (reports/live/perception/EVAL-SPLIT.md held-out battles are skipped),
  frames ~0.5 and ~1 s after match_start, warped with the r3 crop box and normalised to white 255 (BlueStacks recordings
  are dimmed to ~178; the compositor re-applies the dim as an augmentation). Their 6 towers are located by masked template
  matching against the KataCR tower cut-outs, so each baked-in tower becomes a labelled, depth-sorted layer (floor pixels
  under the matched alpha).
- katacr floors: KataCR's 27 empty arenas (no towers; the compositor pastes tower cut-outs).
Writes BANK/bgs/*.png and BANK/bgs.json. Images stay out of git.
"""
import argparse
import glob
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry import CROP_720, W, H, cell2px, TOWER_SLOTS  # noqa: E402

LOOP = Path('/mpac/sdicks02/scratch/live-loop')
SEG = Path('/mpac/sdicks02/jobs/clasher/yolo-synth-20261016/src-data/crdd/images/segment')
# EVAL-SPLIT.md (2026-10-16): never used as floors
HELDOUT = {'ladder1-r1', 'live1', 'live2', 'live3', 'live4', 'live5', 'tc2-r1', 's1-m01', 's2-m01', 's5-m01', 's5-m02', 's7-m04'}


def video_dir(run):
    s, _, m = run.partition('-')
    for d in (LOOP/'runs'/run/'video', LOOP/'runs'/s/m/'video', LOOP/'runs'/(s+m)/'video'):
        if d.is_dir():
            return d
    return None


def warp(im):
    h, w = im.shape[:2]
    sx, sy = w/720, h/1280
    x0, y0, x1, y1 = CROP_720
    m = np.array([[W/((x1-x0)*sx), 0, -x0*W/(x1-x0)], [0, H/((y1-y0)*sy), -y0*H/(y1-y0)]], np.float64)
    return cv2.warpAffine(im, m, (W, H), flags=cv2.INTER_AREA)


def normalise_white(im, white):
    if white and white < 250:
        im = np.clip(im.astype(np.float32)*(255.0/white), 0, 255).astype(np.uint8)
    return im


def official_candidates():
    runs_map = json.loads((LOOP/'runs-map.json').read_text())
    arena = {v['run']: v['arena'] for v in runs_map.values()}
    out = []
    for run in sorted(arena):
        if run in HELDOUT:
            continue
        rd = LOOP/'runs-all'/run
        vd = video_dir(run)
        if vd is None or not (rd/'events.jsonl').exists():
            continue
        n0 = None
        for line in (rd/'events.jsonl').read_text().splitlines():
            ev = json.loads(line)
            if ev.get('ev') == 'match_start':
                n0 = ev['n']; break
        if n0 is None:
            continue
        whites = {}
        for line in (rd/'frames.jsonl').read_text().splitlines():
            r = json.loads(line)
            if n0 <= r['n'] <= n0+12:
                whites[r['n']] = r.get('white')
        for k in (5, 10):
            f = vd/f'{n0+k:06d}.jpg'
            if f.exists():
                out.append(dict(run=run, arena=arena[run], frame=n0+k, path=str(f), white=whites.get(n0+k)))
    return out


def tower_templates():
    t = {}
    for name in ('king-tower', 'queen-tower'):
        for b in (0, 1):
            ims = []
            for f in sorted(glob.glob(str(SEG/name/f'{name}_{b}_*.png'))):
                if '_attack' in f or '_freeze' in f:
                    continue
                im = cv2.imread(f, cv2.IMREAD_UNCHANGED)
                ims.append(im); ims.append(im[:, ::-1].copy())
            t[(name, b)] = ims
    return t


def match_tower(floor, tpls, bc, search=22):
    """Best masked SQDIFF match of any template whose bottom centre lies within `search` px of bc."""
    best = None
    fx, fy = bc
    for tp in tpls:
        h, w = tp.shape[:2]
        x0 = int(round(fx - w/2 - search)); y0 = int(round(fy - h - search))
        x1 = x0 + w + 2*search; y1 = y0 + h + 2*search
        if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
            continue
        reg = floor[y0:y1, x0:x1]
        mask = (tp[..., 3] > 127).astype(np.uint8)
        area = mask.sum()
        if area < 200:
            continue
        r = cv2.matchTemplate(reg.astype(np.float32), tp[..., :3].astype(np.float32), cv2.TM_SQDIFF,
                              mask=cv2.merge([mask]*3).astype(np.float32))
        _, _, mnl, _ = cv2.minMaxLoc(np.where(np.isfinite(r), r, np.inf))
        s = r[mnl[1], mnl[0]] / (area*3)
        if best is None or s < best[0]:
            best = (s, x0+mnl[0], y0+mnl[1], mask)
    return best


def main():
    p = argparse.ArgumentParser()
    p.add_argument('bank', type=Path)
    p.add_argument('--sheet', type=Path)
    p.add_argument('--exclude', default='', help='comma list of bg ids rejected by eye (not empty etc.)')
    a = p.parse_args()
    bd = a.bank/'bgs'; bd.mkdir(parents=True, exist_ok=True)
    excl = set(filter(None, a.exclude.split(',')))
    tpls = tower_templates()
    entries, thumbs = [], []
    for c in official_candidates():
        bid = f"off-{c['run']}-{c['frame']:06d}"
        if bid in excl:
            continue
        im = normalise_white(warp(cv2.imread(c['path'])), c['white'])
        cv2.imwrite(str(bd/f'{bid}.png'), im)
        towers = []
        vis = im.copy()
        for k, (name, b, cx, cy) in enumerate(TOWER_SLOTS):
            m = match_tower(im, tpls[(name, b)], cell2px(cx, cy))
            if m is None:
                continue
            s, x0, y0, mask = m
            h, w = mask.shape
            alpha = (mask*255).astype(np.uint8)
            cut = np.dstack([im[y0:y0+h, x0:x0+w], alpha])
            tf = f'{bid}-t{k}.png'
            cv2.imwrite(str(bd/tf), cut)
            towers.append(dict(name=name, belong=b, x0=int(x0), y0=int(y0), w=int(w), h=int(h), file=tf, sqdiff=round(float(s), 1)))
            cv2.rectangle(vis, (x0, y0), (x0+w, y0+h), (0, 0, 255) if b else (255, 0, 0), 2)
            cv2.putText(vis, f'{s:.0f}', (x0, y0+12), 0, .4, (255, 255, 255), 1)
        entries.append(dict(id=bid, file=f'{bid}.png', kind='official', arena=c['arena'], run=c['run'], frame=c['frame'],
                            white=c['white'], towers=towers))
        cv2.putText(vis, bid, (4, 880), 0, .5, (255, 255, 255), 2)
        thumbs.append(cv2.resize(vis, (284, 448)))
    for f in sorted(glob.glob(str(SEG/'backgrounds/background*.jpg'))):
        bid = 'kcr-'+Path(f).stem
        im = cv2.imread(f)
        assert im.shape[:2] == (H, W), (f, im.shape)
        cv2.imwrite(str(bd/f'{bid}.png'), im)
        entries.append(dict(id=bid, file=f'{bid}.png', kind='katacr', arena='katacr', towers=[]))
    (a.bank/'bgs.json').write_text(json.dumps(entries, indent=1))
    print(f"{sum(e['kind'] == 'official' for e in entries)} official + {sum(e['kind'] == 'katacr' for e in entries)} katacr floors")
    if a.sheet and thumbs:
        rows = [np.concatenate((thumbs[i:i+8] + [np.zeros_like(thumbs[0])]*8)[:8], 1) for i in range(0, len(thumbs), 8)]
        cv2.imwrite(str(a.sheet), np.concatenate(rows, 0), [cv2.IMWRITE_JPEG_QUALITY, 85])


if __name__ == '__main__':
    main()
