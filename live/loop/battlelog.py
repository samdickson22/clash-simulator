"""In-game Battle Log -> opponent deck inventory (runs on 05; reads the Android guest through our adb on the Mac).

  python battlelog.py capture OUT_DIR [--pages 16]   # Battle Log must be open at the top; scrolls, saves settled pages
  python battlelog.py extract OUT_DIR                # pages -> entries (cells + header) -> OUT_DIR/entries.pkl
  python battlelog.py label OUT_DIR                  # unknown card crops -> OUT_DIR/unknown/<cluster>/ for naming
  python battlelog.py decks OUT_DIR --templates DIR --runs RUNS.json --out opponent-decks.jsonl

Geometry (1080x1920 guest, Battle Log v10-2026): each entry ends in Practice/Watch buttons; their top edge `a` anchors
the 2x4 card grids (ours x0=68, opponent x0=554, pitch 114 x 133, cell 104x128, rows from a-281) and the header strip
(a-475..a-290: result, crowns, names, trophies). Cards are identified by normalized correlation against labelled
templates (TEMPLATES/<CardName>/*.png). Pages are screenshots taken after the list has settled (two equal captures),
so no entry is blended by the scroll animation. Opponent names never leave the local scratch dir.
"""
import argparse
import glob
import json
import os
import pickle
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ADB = '$HOME/clasher-live/tools/platform-tools/adb -P 5047 -s 127.0.0.1:5555'
US_X0, OPP_X0, PITCH_X, PITCH_Y, CW, CH, ROW0 = 68, 554, 114, 133, 104, 128, 281


def guest(cmd, binary=False):
    out = subprocess.run(['ssh', '-o', 'BatchMode=yes', 'macmini-fleet', f'{ADB} {cmd}'], capture_output=True, timeout=60)
    return out.stdout if binary else out.stdout.decode(errors='replace')


def screenshot():
    png = guest('exec-out screencap -p', binary=True)
    im = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if im is None or im.shape[:2] != (1920, 1080):
        raise RuntimeError('bad guest screenshot')
    return im


def settled():
    """Screenshot once two consecutive captures agree (the list stopped moving)."""
    prev = screenshot()
    for _ in range(8):
        time.sleep(.6)
        cur = screenshot()
        if np.abs(cur.astype(np.int16) - prev).mean() < 1.0:
            return cur
        prev = cur
    return cur


def capture(out, pages):
    out.mkdir(parents=True, exist_ok=True)
    for i in range(pages):
        cv2.imwrite(str(out/f'p{i:02d}.png'), settled())
        guest('shell input swipe 540 1500 540 950 1200')
    print('pages', pages, '->', out)


def anchors(im):
    col = im[:, 600:740].astype(int)
    blue = ((col[..., 0] > 150) & (col[..., 2] < 90) & (col[..., 1] > 80) & (col[..., 1] < 170)).mean(1) > .6
    ys = np.nonzero(blue)[0]; runs = []
    for y in ys:
        if runs and y - runs[-1][1] <= 2: runs[-1][1] = y
        else: runs.append([y, y])
    tops = [r[0] for r in runs if r[1] - r[0] >= 8]
    tops = [t for i, t in enumerate(tops) if i == 0 or t - tops[i-1] > 25]
    def green(y):                          # the Watch button right of Practice on the same row
        p = im[y+6:y+30, 820:960].astype(int)
        return ((p[..., 1] > 110) & (p[..., 1] > p[..., 2] + 50) & (p[..., 1] > p[..., 0] + 50)).mean() > .25
    def blue_above(y):                     # Practice's top edge: no button colour just above it
        p = im[y-8:y-2, 600:740].astype(int)
        return ((p[..., 0] > 150) & (p[..., 2] < 90)).mean() < .2
    return [t for t in tops if green(t) and blue_above(t)]


def grid_top(im, a):
    """Top border row of the first card row. Nominally a-281; older entries ('1h 30min ago' on two lines) sit the
    buttons lower, so search the dark card border (also 128 px lower: the cards' bottom border) within -90..+10."""
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    xs = np.concatenate([np.arange(US_X0 + 10 + PITCH_X*c, US_X0 + CW - 10 + PITCH_X*c) for c in range(4)])
    best, by = -1, a - ROW0
    for dy in range(-90, 11):
        y = a - ROW0 + dy
        sc = (g[y, xs] < 45).mean() + (g[y + CH - 3:y + CH + 3, xs].min(0) < 45).mean()
        if sc > best:
            best, by = sc, y
    return by


def entry_crops(im, a):
    top = grid_top(im, a)
    cells = {}
    for side, x0 in (('us', US_X0), ('opp', OPP_X0)):
        for r in range(2):
            for c in range(4):
                y, x = top + PITCH_Y*r, x0 + PITCH_X*c
                cells[(side, 4*r + c)] = im[y:y+CH, x:x+CW].copy()
    return cells, im[top-194:top-9, 40:1040].copy()


def extract(out):
    ents = []
    for pi, pg in enumerate(sorted(glob.glob(str(out/'p*.png')))):
        im = cv2.imread(pg)
        for a in anchors(im):
            if grid_top(im, a) - 194 < 300 or a > 1790:      # header must be below the dialog title, buttons above the bottom
                continue
            cells, hdr = entry_crops(im, a)
            ents.append(dict(page=pi, a=int(a), cells=cells, hdr=hdr))
    pickle.dump(ents, open(out/'entries.pkl', 'wb'))
    print(len(ents), 'entries')
    return ents


def feat(c):
    """Grey card art without the level text, for header/whole-entry comparisons."""
    g = cv2.cvtColor(cv2.resize(c[6:96, 6:98], (46, 45), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
    g -= g.mean()
    return g/(np.linalg.norm(g) + 1e-6)


def art(c):
    return cv2.cvtColor(c[0:100], cv2.COLOR_BGR2GRAY)


def load_templates(d):
    """TEMPLATES/<CardName>/*.png -> [(name, inner art patch)]; matching tolerates a few px of misalignment."""
    T = []
    for f in sorted(glob.glob(str(Path(d)/'*'/'*.png'))):
        T.append((Path(f).parent.name, art(cv2.imread(f))[14:86, 14:90]))
    return T


def identify(cell, T, thr=.80):
    a = art(cell)
    best = max(((float(cv2.matchTemplate(a, t, cv2.TM_CCOEFF_NORMED).max()), n) for n, t in T), default=(0, None))
    return (best[1], best[0]) if best[0] >= thr else (None, best[0])


def level(cell):
    """Card level N from 'lvl.N' (best effort with the tower-number glyphs; None = unread, never a guess)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import towers
    v = towers.read_number(_norm_hdr(cell), (55, 92, 104, 128))
    return v if v is not None and 1 <= v <= 15 else None


def label(out, templates):
    ents = pickle.load(open(out/'entries.pkl', 'rb'))
    T = load_templates(templates) if templates and Path(templates).exists() else []
    unk = [(e, k, c) for e in ents for k, c in e['cells'].items() if identify(c, T)[0] is None]
    if not unk:
        print('no unknown cards'); return
    X = np.array([feat(c).ravel() for _, _, c in unk], np.float32)  # clusters for naming only
    K = min(40, len(unk))
    _, lab, _ = cv2.kmeans(X, K, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-3), 4, cv2.KMEANS_PP_CENTERS)
    for (e, k, c), l in zip(unk, lab.ravel()):
        d = out/'unknown'/f'c{l:02d}'; d.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(d/f"p{e['page']:02d}_a{e['a']}_{k[0]}{k[1]}.png"), c)
    print(len(unk), 'unknown cells in', K, 'clusters under', out/'unknown')


C56 = {'AngryBarbarians', 'ArcherQueen', 'Archers', 'Arrows', 'BabyDragon', 'Balloon', 'BarbLog', 'Bats', 'Berserker',
       'BlowdartGoblin', 'BombTower', 'Cannon', 'DarkPrince', 'Earthquake', 'ElectroSpirit', 'FireSpirits', 'Fireball',
       'Firecracker', 'FirespiritHut', 'Ghost', 'Giant', 'GoblinBarrel', 'GoblinGang', 'GoblinHut', 'Goblins',
       'Goblinstein', 'Golem', 'HogRider', 'IceGolem', 'IceSpirit', 'InfernoTower', 'Knight', 'Lightning', 'Log',
       'MightyMiner', 'Miner', 'MiniPekka', 'MinionHorde', 'Minions', 'Musketeer', 'Poison', 'Prince', 'Princess',
       'Rascals', 'Rocket', 'RoyalDelivery', 'RoyalHogs', 'SkeletonArmy', 'Skeletons', 'Tesla', 'Tornado', 'Valkyrie',
       'Wallbreakers', 'Wizard', 'Xbow', 'Zap'}          # = the perception vocab 'cards' (56), our engines' card set


def decks(out, templates, runs_json, out_jsonl):
    """One row per distinct battle (newest first). Same battle on two pages = identical 16 card labels and our/opp
    trophy counts. RUNS.json maps '<our trophies before>:<W|L>' -> {run, arena}. No opponent names are written."""
    ents = pickle.load(open(out/'entries.pkl', 'rb'))
    T = load_templates(templates)
    runs = json.loads(Path(runs_json).read_text()) if runs_json else {}
    rows, seen = [], set()
    for e in ents:
        ids = {k: identify(c, T) for k, c in e['cells'].items()}
        if any(n is None for n, _ in ids.values()):
            continue                            # an unreadable (cut / unknown) card: the entry is skipped
        us = [ids[('us', i)][0] for i in range(8)]; opp = [ids[('opp', i)][0] for i in range(8)]
        nums = header_numbers(e['hdr'])
        hdr = e['hdr'].astype(int)[5:45, 10:230]
        res = 'W' if (hdr[..., 0] - hdr[..., 2]).clip(0).mean() > (hdr[..., 2] - hdr[..., 0]).clip(0).mean() else 'L'
        key = (tuple(us), tuple(opp), nums.get('us'), nums.get('opp'), res)
        if key in seen:
            continue
        seen.add(key)
        meta = runs.get(f"{nums.get('us')}:{res}", {})
        rows.append(dict(log_index=len(rows), run=meta.get('run'), arena=meta.get('arena'), result=res,
                         crowns=[nums.get('crowns_us'), nums.get('crowns_opp')],
                         our_trophies_before=nums.get('us'), opp_trophies=nums.get('opp'),
                         opp_deck=opp, opp_levels=[level(e['cells'][('opp', i)]) for i in range(8)],
                         opp_non_c56=[c for c in opp if c not in C56], our_deck=us, source='battle-log'))
    with open(out_jsonl, 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    counts = {}
    for r in rows:
        a = counts.setdefault(r['arena'] or 'unknown', {'battles': 0, 'non_c56': {}})
        a['battles'] += 1
        for c in set(r['opp_non_c56']):
            a['non_c56'][c] = a['non_c56'].get(c, 0) + 1
    Path(out_jsonl).with_name('opponent-cards-non-c56.json').write_text(json.dumps(counts, indent=1) + '\n')
    print(len(rows), 'battles ->', out_jsonl)
    return rows


def _norm_hdr(hdr):
    w = float(np.percentile(hdr.max(2), 99.5))
    return cv2.convertScaleAbs(hdr, alpha=255./max(w, 80))


def header_glyphs(h, box):
    """White digit components inside a trophy box of the (normalized) header, left to right, as 12x18 vectors."""
    x1, y1, x2, y2 = box
    c = h[y1:y2, x1:x2].astype(np.int16)
    m = (((.299*c[..., 2] + .587*c[..., 1] + .114*c[..., 0]) > 175) & ((c.max(2) - c.min(2)) < 90)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    out = []
    for i in range(1, n):
        x, y, w, hh, a = st[i]
        if 10 <= hh <= 30 and a >= 20 and w <= 22:
            out.append((x, cv2.resize((lab[y:y+hh, x:x+w] == i).astype(np.float32), (12, 18),
                                      interpolation=cv2.INTER_AREA).ravel()))
    return [v for _, v in sorted(out, key=lambda t: t[0])]


BOX_US, BOX_OPP = (128, 146, 228, 182), (758, 146, 858, 182)
DIGITS = Path(__file__).resolve().parent/'cards'/'_header_digits.npz'


def build_header_digits(ents, known_us):
    """Header-digit templates from entries whose OUR trophy count is known (run table): known_us[i] for ents[i]."""
    X, Y = [], []
    for e, v in zip(ents, known_us):
        if v is None:
            continue
        g = header_glyphs(_norm_hdr(e['hdr']), BOX_US)
        if len(g) == len(str(v)):
            X += g; Y += list(str(v))
    np.savez_compressed(DIGITS, x=np.array(X, np.float32), y=np.array(Y))
    return len(X)


def read_header_number(h, box):
    if not DIGITS.exists():
        return None
    d = np.load(DIGITS); X, Y = d['x'], d['y']
    g = header_glyphs(h, box)
    if not g:
        return None
    return int(''.join(Y[int(np.argmin(((X - v)**2).sum(1)))] for v in g))


def header_numbers(hdr):
    """Trophy counts and crowns in the header strip, brightness-normalized (the client was dimmed in the log)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import towers
    h = _norm_hdr(hdr)
    crowns = cv2.resize(h[5:50, 400:600], (100, 22))       # '3 - 0': digits too tall for the HP glyphs -> half size
    return dict(us=read_header_number(h, BOX_US), opp=read_header_number(h, BOX_OPP),
                crowns_us=towers.read_number(crowns, (0, 0, 35, 22)), crowns_opp=towers.read_number(crowns, (65, 0, 100, 22)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('capture', 'extract', 'label', 'decks'))
    ap.add_argument('dir')
    ap.add_argument('--pages', type=int, default=16)
    ap.add_argument('--templates')
    ap.add_argument('--runs')
    ap.add_argument('--out')
    a = ap.parse_args()
    d = Path(a.dir)
    if a.cmd == 'capture': capture(d, a.pages)
    elif a.cmd == 'extract': extract(d)
    elif a.cmd == 'label': label(d, a.templates)
    else: decks(d, a.templates, a.runs, a.out)


if __name__ == '__main__':
    main()
