"""Synthetic official-looking battle frames with exact labels (568x896 KataCR arena crop, the r3 YOLO input space).

One frame = background floor (official recording floor with its 6 towers as depth-sorted layers, or a KataCR empty arena
with pasted tower cut-outs) + unit cut-outs (KataCR segments now, Null's Royale cut-outs as they arrive) placed on
KataCR's ground / air placement maps, drawn in depth order (layer, then feet y). Labels come from a per-pixel id map of
the top-most drawn layer, so every box is the VISIBLE sprite body (as the r3 hand labels: badge / HP bar / shadow excluded)
and units hidden below `min_visible` are removed before drawing (no unlabelled ghosts).

Realism (Sam / coordinator):
- HP bar + level badge only on 'damaged' units (p_damaged), team-coloured KataCR bar cut-outs, never labelled;
- crowding: swarms (same card, same team, k bodies around a centre) and dense frames; correct y-ordering by depth;
- spells / projectiles are labelled KataCR classes (kind spell/object in classes.json; drop them if unwanted);
- distractors: deploy clocks, elixir pop-ups, emotes, text, blood/flowers/ribbons (KataCR background items), unlabelled;
- colour: per-unit KataCR hit/freeze/rage/heal filters, invisibility transparency, global gain/bias/saturation/hue,
  BlueStacks dim (white level ~178) with p_dim, noise, blur, down-up resampling, JPEG.
Missing team: most KataCR classes have cut-outs for one team only; the other team is synthesised by swapping the
saturated red/blue team accents (meta 'swap': true), until Null's per-team cut-outs cover it.
"""
import json
import math
from pathlib import Path

import cv2
import numpy as np

from geometry import W, H, CELL_W, CELL_H, cell2px, TOWER_SLOTS

# KataCR generation_config.map_ground / map_fly (rows = y cells 0..31 from the top, cols = x 0..17)
MAP_GROUND = np.array([
    [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0],
    [.5, .5, .5, .5, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, .5, .5, .5, .5],
    [.5, .5, .5, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, .5, .5, .5],
    [.5, .5, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, .5, .5],
    [.5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, .5],
    [1, 1, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 1, 1],
    [1, 1, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 1, 1],
    [1, 1, 0, 0, 0, 2, 2, 1, 1, 1, 1, 2, 2, 0, 0, 0, 1, 1],
    [1, 1, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 1, 1],
    [0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0],
    [0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0],
    [1, 1, 3, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 1, 1],
    [1, 1, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 1, 3, 3, 3, 1, 1],
    [1, 1, 0, 0, 0, 2, 2, 1, 1, 1, 1, 2, 2, 0, 0, 0, 1, 1],
    [1, 1, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 1, 1],
    [1, 1, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 1, 1],
    [.5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, .5],
    [.5, .5, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, .5, .5],
    [.5, .5, .5, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, .5, .5, .5],
    [.5, .5, .5, .5, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, .5, .5, .5, .5],
    [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0]], np.float64)
MAP_FLY = np.ones((32, 18)); MAP_FLY[0, :6] = MAP_FLY[0, 12:] = MAP_FLY[31, :6] = MAP_FLY[31, 12:] = 0

DEFAULT_CFG = dict(
    p_official=.6,                 # official floor vs KataCR floor
    arena_weight={'bone-pit': 3.0, 'goblin-stadium': 1.0, 'barbarian-bowl': 1.0},   # within official floors
    n_units=((.04, 0, 0), (.36, 1, 8), (.40, 8, 22), (.20, 22, 45)),               # (p, lo, hi) bodies per frame
    p_swarm=.35, swarm_k=(2, 9), swarm_sigma=.8,                                    # tiles
    p_damaged=.35, p_clock=.06, p_elixir=.05,
    min_visible=.3, min_box=5,
    scale=(.92, 1.08), p_flip=.5,
    p_filter=.10, p_trans=.5,      # per-unit colour filter; invisibility transparency for royal-ghost / archer-queen
    p_dim=.5, dim_white=(168, 190),
    gain=(.85, 1.15), bias=(-12, 12), sat=(.8, 1.2), hue=(-4, 4),
    p_noise=.3, noise_sigma=(1.5, 5.0), p_blur=.15, p_resample=.3, resample=(.55, .9),
    p_tower_bar=.5, p_items=1.0,
    katacr_queen=(('queen-tower', .6), ('cannoneer-tower', .1), ('dagger-duchess-tower', .1), ('ruin', .2)),
    p_king_ruin=.04,
    p_swap=.5,                     # missing team: swap red/blue accents, else use the real team's cut-out
)

FILTERS = {'red': ((0, 0, 255), 80, (30, 50)), 'blue': ((255, 0, 0), 100, (30, 80)), 'golden': ((0, 215, 255), 150, (70, 80)),
           'white': ((255, 255, 255), 150, (110, 120)), 'violet': ((255, 0, 127), 100, (10, 30))}   # BGR, alpha/255, bright
DECOR_TOP = ('bar', 'bar-level')


class Bank:
    """Backgrounds + cut-outs, loaded once per process (fork shares it)."""

    def __init__(self, root, classes_json, sprite_index='sprites.jsonl'):
        root = Path(root)
        self.root = root
        doc = json.loads(Path(classes_json).read_text())
        self.names = {x['name']: x for x in doc['names']}
        self.bgs = []
        for e in json.loads((root/'bgs.json').read_text()):
            if e.get('reject'):
                continue
            e = dict(e)
            e['img'] = cv2.imread(str(root/'bgs'/e['file']))
            for t in e['towers']:
                t['img'] = cv2.imread(str(root/'bgs'/t['file']), cv2.IMREAD_UNCHANGED)
            self.bgs.append(e)
        self.sprites = {}            # name -> belong -> [entry]
        for line in (root/sprite_index).read_text().splitlines():
            s = json.loads(line)
            im = cv2.imread(str(root/s['file']), cv2.IMREAD_UNCHANGED)
            if im is None or im.ndim != 3 or im.shape[2] != 4:
                continue
            if s.get('scale', 1.0) != 1.0:
                f = s['scale']
                im = cv2.resize(im, (max(1, round(im.shape[1]*f)), max(1, round(im.shape[0]*f))), interpolation=cv2.INTER_AREA)
            s['img'] = im
            self.sprites.setdefault(s['name'], {}).setdefault(int(s['belong']), []).append(s)
        self.unit_names = sorted(n for n in self.sprites if n in self.names and self.names[n]['labelled']
                                 and self.names[n]['kind'] != 'tower')
        self.off_bgs = [b for b in self.bgs if b['kind'] == 'official']
        self.kcr_bgs = [b for b in self.bgs if b['kind'] == 'katacr']

    def pick(self, rng, name, belong=None, p_swap=1.0):
        by = self.sprites.get(name, {})
        if not by:
            return None, False
        if belong is None or belong not in by:
            if belong is not None and belong in (0, 1) and set(by) - {belong} and name in self.names \
                    and self.names[name]['labelled'] and rng.random() < p_swap:
                other = [b for b in by if b in (0, 1)]
                if other:
                    s = by[other[0]][rng.integers(len(by[other[0]]))]
                    return s, True       # caller swaps team colours
            belong = list(by)[rng.integers(len(by))]
        lst = by[belong]
        return lst[rng.integers(len(lst))], False


def team_swap(bgra):
    """Swap saturated red <-> blue accents (KataCR team colours) in a BGRA cut-out."""
    hsv = cv2.cvtColor(bgra[..., :3], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(np.int16), hsv[..., 1], hsv[..., 2]
    sat = (s > 110) & (v > 60)
    red = sat & ((h <= 7) | (h >= 172))
    blue = sat & (h >= 100) & (h <= 125)
    h2 = h.copy()
    h2[red] = 112 + ((h[red] + 8) % 180 - 8)        # red (~0) -> blue (~112)
    h2[blue] = (h[blue] - 112) % 180                # blue (~112) -> red (~0)
    hsv[..., 0] = np.clip(h2 % 180, 0, 179).astype(np.uint8)
    out = bgra.copy()
    out[..., :3] = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return out


def color_filter(bgr, rng, kind):
    col, alpha, bright = FILTERS[kind]
    a = alpha/255.0
    out = bgr.astype(np.float32)*(1-a) + np.array(col, np.float32)*a
    out += (bgr.mean() - out.mean()) + rng.uniform(*bright)
    return np.clip(out, 0, 255).astype(np.uint8)


class Layer:
    __slots__ = ('img', 'x0', 'y0', 'z', 'label', 'group', 'meta', 'alpha')

    def __init__(self, img, x0, y0, z, label=None, group=None, meta=None, alpha=1.0):
        self.img, self.x0, self.y0, self.z, self.label, self.group, self.meta, self.alpha = img, int(x0), int(y0), z, label, group, meta, alpha


def sample_cell(rng, m):
    p = m.ravel()/m.sum()
    k = rng.choice(p.size, p=p)
    cy, cx = divmod(k, m.shape[1])
    return cx + rng.random(), cy + rng.random()


PRIORITY = ('spear-goblin', 'tombstone', 'bomber', 'goblin-cage', 'goblin-brawler', 'skeleton', 'goblin-hut', 'goblin',
            'barbarian', 'barbarian-hut', 'archer', 'minion', 'knight', 'giant', 'musketeer', 'mini-pekka', 'valkyrie')


def default_weights(names):
    """Unit class sampling: spells/projectiles are brief on screen (.4/.6); r3 priority + Bone Pit bodies x2."""
    w = {}
    for n, m in names.items():
        w[n] = {'spell': .4, 'object': .6}.get(m['kind'], 1.0) * (2.0 if n in PRIORITY else 1.0)
    return w


class Composer:
    def __init__(self, bank, cfg=None, class_weights=None):
        self.b = bank
        self.cfg = dict(DEFAULT_CFG, **(cfg or {}))
        names = bank.unit_names
        cw = class_weights if class_weights is not None else default_weights(bank.names)
        w = np.array([cw.get(n, 1.0) for n in names], np.float64)
        self.unit_names, self.unit_p = names, w/w.sum()
        arena_w = self.cfg['arena_weight']
        ow = np.array([arena_w.get(b['arena'], 1.0) for b in bank.off_bgs], np.float64)
        self.off_p = ow/ow.sum() if len(ow) else None

    # ---- layers ---------------------------------------------------------------------------------------------------
    def _sprite_layer(self, rng, name, belong, foot, layer_level, label=True, group=None, aug=True, fmt='bottom'):
        s, swap = self.b.pick(rng, name, belong, self.cfg['p_swap'])
        if s is None:
            return None
        im = s['img']
        if swap:
            im = team_swap(im)
        b = belong if swap else int(s['belong'])
        c = self.cfg
        if aug:
            f = rng.uniform(*c['scale'])
            if abs(f-1) > .01:
                im = cv2.resize(im, (max(2, round(im.shape[1]*f)), max(2, round(im.shape[0]*f))), interpolation=cv2.INTER_LINEAR)
            if rng.random() < c['p_flip']:
                im = im[:, ::-1]
        im = np.ascontiguousarray(im)
        alpha = 1.0
        kind = self.b.names.get(name, {}).get('kind')
        if aug and kind in ('troop', 'building'):
            if name in ('royal-ghost', 'archer-queen') and rng.random() < c['p_trans']:
                alpha = 150/255
            elif rng.random() < c['p_filter']:
                im = im.copy(); im[..., :3] = color_filter(im[..., :3], rng, list(FILTERS)[rng.integers(len(FILTERS))])
        h, w = im.shape[:2]
        fx, fy = foot
        if fmt == 'bottom':
            x0, y0 = fx - w/2, fy - h
        elif fmt == 'center':
            x0, y0 = fx - w/2, fy - h/2
        elif fmt == 'left':       # foot = left-centre
            x0, y0 = fx, fy - h/2
        else:                      # 'right' = right-centre
            x0, y0 = fx - w, fy - h/2
        z = (layer_level, fy)
        lab = (self.b.names[name]['idx'], b) if label and name in self.b.names and self.b.names[name]['labelled'] else None
        return Layer(im, x0, y0, z, lab, group, dict(name=name, belong=b, src=s.get('src', 'katacr'), swap=bool(swap),
                                                   sprite=s.get('file')), alpha)

    def _towers(self, rng, bg, layers):
        if bg['kind'] == 'official':
            for t in bg['towers']:
                lab = (self.b.names[t['name']]['idx'], t['belong'])
                layers.append(Layer(t['img'], t['x0'], t['y0'], (1, t['y0']+t['h']), lab, None,
                                    dict(name=t['name'], belong=t['belong'], src='floor')))
            return
        for name, b, cx, cy in TOWER_SLOTS:
            foot = cell2px(cx, cy)
            if name == 'king-tower':
                choice = 'king-tower-ruin' if rng.random() < self.cfg['p_king_ruin'] else 'king-tower'
            else:
                opts = self.cfg['katacr_queen']
                choice = opts[rng.choice(len(opts), p=np.array([p for _, p in opts])/sum(p for _, p in opts))][0]
            if choice in ('ruin', 'king-tower-ruin'):
                L = self._sprite_layer(rng, choice, None, foot, 0, label=False, aug=False)
            else:
                L = self._sprite_layer(rng, choice, b, foot, 1, aug=False)
                if L is not None and L.meta['swap']:
                    L = None
                if L is None:
                    L = self._sprite_layer(rng, 'queen-tower' if name == 'queen-tower' else 'king-tower', b, foot, 1, aug=False)
            if L is None:
                continue
            layers.append(L)
            if L.label and rng.random() < self.cfg['p_tower_bar']:
                # KataCR component_cfg: tower-bar0 above the foot, tower-bar1 above the top, king bars below / on top
                top = L.y0
                if choice == 'king-tower':
                    pos = (foot[0], foot[1] + rng.uniform(1, 1.5)*CELL_H) if b == 0 else (foot[0], top + 2)
                    bar = 'king-tower-bar'
                else:
                    pos = (foot[0], foot[1] - rng.uniform(.5, 1.5)*CELL_H) if b == 0 else (foot[0], top + rng.uniform(-.3, .2)*CELL_H)
                    bar = 'tower-bar'
                D = self._sprite_layer(rng, bar, b, pos, 3, label=False, aug=False)
                if D is not None:
                    layers.append(D)

    def _items(self, rng, layers):
        """KataCR background items + UI distractors (unlabelled)."""
        g0, g1 = cell2px(0, 0), cell2px(18, 32)
        for name, p, nmax, lvl in (('blood', .3, 12, 0), ('flower', .3, 5, 0), ('ribbon', .3, 12, 0), ('butterfly', .1, 3, 0),
                                   ('skull', .05, 3, 0), ('grave', .05, 8, 0), ('snow', .05, 4, 0), ('cup', .03, 2, 0),
                                   ('circle', .05, 3, 0), ('emote', .1, 2, 3), ('text', .015, 1, 3)):
            if rng.random() > p*self.cfg['p_items']:
                continue
            for _ in range(rng.integers(1, nmax+1)):
                pos = (rng.uniform(g0[0], g1[0]), rng.uniform(g0[1], g1[1]))
                L = self._sprite_layer(rng, name, None, pos, lvl, label=False, aug=False, fmt='center')
                if L is not None:
                    layers.append(L)

    def _decorate(self, rng, L, layers, gid):
        """HP bar + level badge only on damaged units; deploy clock / elixir pop-up sometimes. All unlabelled."""
        c = self.cfg
        kind = self.b.names[L.meta['name']]['kind']
        if kind not in ('troop', 'building'):
            return
        b = L.meta['belong']
        cx = L.x0 + L.img.shape[1]/2
        top = L.y0
        if rng.random() < c['p_damaged']:
            bx = cx + rng.uniform(-.3, -.1)*CELL_W - 18
            by = top - rng.uniform(0, .3)*CELL_H
            bar = self._sprite_layer(rng, 'bar', b, (bx, by), 3, label=False, group=gid, aug=False, fmt='left')
            if bar is not None:
                layers.append(bar)
                lvl = self._sprite_layer(rng, 'bar-level', b, (bar.x0 + 3, by), 3, label=False, group=gid, aug=False,
                                         fmt='right')
                if lvl is not None:
                    layers.append(lvl)
        if rng.random() < c['p_clock']:
            D = self._sprite_layer(rng, 'clock', b, (cx, L.z[1] + rng.uniform(.5, 1.2)*CELL_H), 3, label=False, group=gid, aug=False)
            if D is not None:
                layers.append(D)
        if rng.random() < c['p_elixir']:
            D = self._sprite_layer(rng, 'elixir', 0, (cx, top - rng.uniform(.5, 1.5)*CELL_H), 3, label=False, group=gid, aug=False)
            if D is not None:
                layers.append(D)

    def _units(self, rng, layers):
        c = self.cfg
        bands = c['n_units']
        k = rng.choice(len(bands), p=[x[0] for x in bands])
        n = int(rng.integers(bands[k][1], bands[k][2]+1)) if bands[k][2] > 0 else 0
        gid = 0
        placed = 0
        while placed < n:
            name = self.unit_names[rng.choice(len(self.unit_names), p=self.unit_p)]
            belong = int(rng.integers(2))
            meta = self.b.names[name]
            level = meta['layer']
            m = MAP_FLY if level != 1 else MAP_GROUND
            cxy = sample_cell(rng, m)
            k = 1
            if meta['kind'] == 'troop' and rng.random() < c['p_swarm']:
                k = int(rng.integers(c['swarm_k'][0], c['swarm_k'][1]+1))
            for j in range(min(k, n - placed if n > placed else 1)):
                x, y = cxy
                for _ in range(8 if j else 1):      # swarm bodies stay on cells the placement map allows
                    if j:
                        x, y = cxy[0] + rng.normal(0, c['swarm_sigma']), cxy[1] + rng.normal(0, c['swarm_sigma'])
                    x, y = float(np.clip(x, .2, 17.8)), float(np.clip(y, .3, 31.9))
                    if m[int(y), int(x)] > 0:
                        break
                else:
                    continue
                L = self._sprite_layer(rng, name, belong, cell2px(x, y), level, group=gid)
                if L is None:
                    break
                L.meta['tile'] = (round(x, 2), round(y, 2))
                layers.append(L)
                self._decorate(rng, L, layers, gid)
                gid += 1
                placed += 1

    # ---- render ---------------------------------------------------------------------------------------------------
    @staticmethod
    def _render(base, layers, want_ids=True):
        img = base.astype(np.float32)
        ids = np.full((H, W), -1, np.int32)
        for i, L in enumerate(layers):
            h, w = L.img.shape[:2]
            x0, y0 = L.x0, L.y0
            ax0, ay0, ax1, ay1 = max(0, x0), max(0, y0), min(W, x0+w), min(H, y0+h)
            if ax0 >= ax1 or ay0 >= ay1:
                continue
            sub = L.img[ay0-y0:ay1-y0, ax0-x0:ax1-x0]
            a = sub[..., 3:4].astype(np.float32)/255.0*L.alpha
            reg = img[ay0:ay1, ax0:ax1]
            reg *= (1-a); reg += a*sub[..., :3]
            if want_ids:
                ids[ay0:ay1, ax0:ax1][sub[..., 3] > 127] = i
        return img, ids

    def frame(self, rng):
        c = self.cfg
        if self.b.off_bgs and rng.random() < c['p_official']:
            bg = self.b.off_bgs[rng.choice(len(self.b.off_bgs), p=self.off_p)]
        else:
            bg = self.b.kcr_bgs[rng.integers(len(self.b.kcr_bgs))]
        layers = []
        self._towers(rng, bg, layers)
        self._items(rng, layers)
        self._units(rng, layers)
        layers.sort(key=lambda L: L.z)
        dropped = 0
        for _ in range(4):
            img, ids = self._render(bg['img'], layers)
            counts = np.bincount(ids.ravel()+1, minlength=len(layers)+1)[1:]
            bad_groups, bad = set(), set()
            for i, L in enumerate(layers):
                if L.label is None or L.meta.get('src') == 'floor':
                    continue
                full = int((L.img[..., 3] > 127).sum())
                if full == 0 or counts[i]/full < c['min_visible']:
                    bad.add(i)
                    if L.group is not None:
                        bad_groups.add(L.group)
            if not bad:
                break
            dropped += len(bad)
            layers = [L for i, L in enumerate(layers) if i not in bad and not (L.label is None and L.group in bad_groups)]
        labels, units = [], []
        for i, L in enumerate(layers):
            if L.label is None:
                continue
            ys, xs = np.nonzero(ids[max(0, L.y0):L.y0+L.img.shape[0], max(0, L.x0):L.x0+L.img.shape[1]] == i)
            if len(xs) == 0:
                continue
            x1, y1 = xs.min()+max(0, L.x0), ys.min()+max(0, L.y0)
            x2, y2 = xs.max()+max(0, L.x0)+1, ys.max()+max(0, L.y0)+1
            if x2-x1 < c['min_box'] or y2-y1 < c['min_box']:
                continue
            labels.append((L.label[0], L.label[1], x1, y1, x2, y2))
            units.append(dict(L.meta, box=[int(x1), int(y1), int(x2), int(y2)]))
        img = self._global_aug(rng, img)
        meta = dict(bg=bg['id'], arena=bg['arena'], n=len(labels), dropped=dropped,
                    damaged=sum(1 for L in layers if L.meta and L.meta.get('name') == 'bar'), units=units)
        return img, labels, meta

    def _global_aug(self, rng, img):
        c = self.cfg
        img = img*rng.uniform(*c['gain']) + rng.uniform(*c['bias'])
        img = np.clip(img, 0, 255).astype(np.uint8)
        s, hshift = rng.uniform(*c['sat']), rng.uniform(*c['hue'])
        if abs(s-1) > .02 or abs(hshift) > .5:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[..., 0] = (hsv[..., 0] + hshift) % 180
            hsv[..., 1] = np.clip(hsv[..., 1]*s, 0, 255)
            img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        if rng.random() < c['p_resample']:
            f = rng.uniform(*c['resample'])
            img = cv2.resize(cv2.resize(img, (round(W*f), round(H*f)), interpolation=cv2.INTER_AREA), (W, H),
                             interpolation=cv2.INTER_LINEAR)
        if rng.random() < c['p_blur']:
            img = cv2.GaussianBlur(img, (3, 3), rng.uniform(.4, 1.0))
        if rng.random() < c['p_noise']:
            img = np.clip(img.astype(np.float32) + rng.normal(0, rng.uniform(*c['noise_sigma']), img.shape), 0, 255).astype(np.uint8)
        if rng.random() < c['p_dim']:
            img = (img.astype(np.float32)*(rng.uniform(*c['dim_white'])/255.0)).astype(np.uint8)
        return img


def yolo_lines(labels):
    """KataCR format: name_idx cx cy w h belong (normalised to 568x896)."""
    out = []
    for idx, b, x1, y1, x2, y2 in labels:
        out.append(f'{idx} {(x1+x2)/2/W:.6f} {(y1+y2)/2/H:.6f} {(x2-x1)/W:.6f} {(y2-y1)/H:.6f} {b}')
    return '\n'.join(out) + ('\n' if out else '')


def frame_seed(base, shard, i):
    return (base * 1_000_003 + shard) * 10_007 + i
