"""New-card sprite bank: cut verified official units (labels-nc) out of their frames, in arena-cache space (832x448, the model
input), against the battle's median background (camera is fixed; units move, so the per-pixel median over the battle is the
empty arena plus long-lived buildings only where they stood > half the battle).

Per unit: RGBA PNG (alpha = unit mask) + an index row {identity, card, body, owner, anchor (px in the patch), source}.

  python sprite_bank.py LABELS_NC_DIR LABEL_NC_INDEX MANIFEST OUT_DIR
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

R = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R/'src'), str(R/'live/loop')]
import canvas as LC  # noqa: E402
from clasher.vision.l1_v4 import prepare_pixels  # noqa: E402

TW, TH = 28.545*448/540, 22.895*832/800
CX0, CY0 = 12.09*448/540, (237.18-200)*832/800
IDENTITY = {('SpearGoblins', 'SpearGoblin'): 'SpearGoblins', ('Tombstone', 'Tombstone'): 'Tombstone',
            ('Tombstone', 'Skeleton'): 'Skeletons', ('Bomber', 'Bomber'): 'Bomber', ('GoblinCage', 'GoblinCage'): 'GoblinCage',
            ('GoblinCage', 'GoblinBrawler'): 'GoblinBrawler'}
BUILDING = {'Tombstone', 'GoblinCage'}
# box around the ground point, tiles: half-width, up, down
BOX = {'SpearGoblins': (1.0, 1.9, .6), 'Skeletons': (.9, 1.6, .5), 'Bomber': (1.1, 2.1, .6), 'GoblinBrawler': (1.3, 2.4, .6),
       'Tombstone': (1.4, 2.4, 1.0), 'GoblinCage': (1.6, 2.8, 1.1)}


def arena(path):
    return prepare_pixels(LC.canvas(cv2.imread(str(path))))[0]


def ellipse_alpha(h, w, ax, ay, hw, up, dn):
    """Soft elliptical alpha (uint8 0..255) covering the sprite above its ground point (ax, ay) inside an h x w patch. Precise
    masks fail on green-on-green sprites; the floor that travels with the sprite matches the official floors it is pasted on."""
    m = np.zeros((h, w), np.float32)
    cy = ay-(up-dn)*TH/2
    cv2.ellipse(m, (int(ax), int(cy)), (int(hw*TW*.85), int((up+dn)*TH/2*.92)), 0, 0, 360, 1., -1)
    return (cv2.GaussianBlur(m, (0, 0), 2.5)*255).astype(np.uint8)


def grabcut(patch, bgp, cx, cy):
    """Unit mask in a patch: GrabCut seeded with the sprite core (fg), strong differences vs the battle's median background
    (probable fg) and the patch border (bg); the component containing the core is kept."""
    d = np.abs(patch.astype(np.int16)-bgp).max(2)
    gc = np.full(patch.shape[:2], cv2.GC_PR_BGD, np.uint8)
    gc[d > 40] = cv2.GC_PR_FGD
    gc[max(0, cy-5):cy+5, max(0, cx-4):cx+4] = cv2.GC_FGD
    gc[:2] = gc[-2:] = cv2.GC_BGD; gc[:, :2] = gc[:, -2:] = cv2.GC_BGD
    try:
        bm, fm = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(patch, gc, None, bm, fm, 5, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return None
    m = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    n_c, cc = cv2.connectedComponents(m)
    lab = cc[min(cc.shape[0]-1, max(0, cy)), min(cc.shape[1]-1, max(0, cx))]
    return (cc == lab).astype(np.uint8) if lab > 0 else None


def median_bg(video_dir, ns):
    picks = ns[::max(1, len(ns)//60)]
    stack = np.stack([arena(video_dir/f'{n:06d}.jpg') for n in picks if (video_dir/f'{n:06d}.jpg').exists()])
    return np.median(stack, 0).astype(np.uint8)


def main():
    lab_dir, ix_path, manifest, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)
    ix = {x['id']: x for x in json.loads(ix_path.read_text())}
    man = {json.loads(l)['run']: json.loads(l) for l in manifest.read_text().splitlines() if l.strip()}
    labs = [json.loads(f.read_text()) for f in sorted(lab_dir.glob('*.json'))]
    bgs, rows = {}, []
    for lab in labs:
        if lab.get('exclude') or not lab['units']:
            continue
        meta = ix[lab['id']]; run = meta['run']
        if run not in bgs:
            fr = [json.loads(x) for x in Path(man[run]['frames']).read_text().splitlines() if x.strip()]
            ns = [r['n'] for r in fr if r.get('state') == 'battle']
            bgs[run] = median_bg(Path(man[run]['video_dir']), ns)
            cv2.imwrite(str(out/f'bg-{run}.png'), bgs[run])
        img = arena(meta['source']).astype(np.int16); bg = bgs[run].astype(np.int16)
        for k, u in enumerate(lab['units']):
            ident = IDENTITY.get((u['card'], u.get('body')))
            if ident is None or u.get('conf') == 'low':
                continue
            X, Y = CX0+TW*float(u['x']), CY0+TH*float(u['y'])
            hw, up, dn = BOX[ident]
            x0, x1 = max(0, int(X-hw*TW)), min(448, int(X+hw*TW)); y0, y1 = max(0, int(Y-up*TH)), min(832, int(Y+dn*TH))
            m = ellipse_alpha(y1-y0, x1-x0, X-x0, Y-y0, hw, up, dn)
            patch = img[y0:y1, x0:x1].astype(np.uint8)
            rgba = np.dstack([patch, m])
            name = f"{lab['id']}-{k}-{ident}.png"
            cv2.imwrite(str(out/name), rgba)
            rows.append(dict(file=name, identity=ident, card=u['card'], body=u.get('body'), owner=u['owner'],
                             anchor=[float(X-x0), float(Y-y0)], size=[int(x1-x0), int(y1-y0)], arena=meta['arena'],
                             run=run, frame=lab['id'], building=ident in BUILDING, conf=u.get('conf')))
    (out/'bank.json').write_text(json.dumps(rows, indent=1))
    from collections import Counter
    print(len(rows), dict(Counter(r['identity'] for r in rows)), 'runs', dict(Counter(r['run'] for r in rows)))


if __name__ == '__main__':
    main()
