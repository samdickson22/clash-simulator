"""Perception round 3: background-invariant fine-tune (official client domain gap).

Joint run as finetune2.py (body/HUD frame batches + TemporalHead play-event windows on renderer data, train split
only), but most frame-batch frames are COMPOSITED: the renderer frame's unit pixels are pasted onto another floor.

Unit pixels = (|frame - match-start empty frame| > tau) & (|frame - clean renderer template| > tau) & (box around a
labelled object or ignore object), closed, dilated and feathered. The template term drops replay-control overlays
present in some match-start frames. Floors (per frame, `KINDS`):
  plain     the renderer frame as is
  official  an empty official arena (Goblin Stadium starts, canvas.py mapping), optionally recoloured
  hardneg   an empty official arena with no units at all (decor false-positive negatives)
  recolour  the match's own empty renderer arena, hue/saturation/value/contrast shifted (units untouched)
  texture   procedural floor (low-frequency colour noise + random checker tiles) with the template's towers
Non-plain frames get tower targets from the floor (all 6 alive, full HP: every floor is a match start).
Training Camp is never used as a floor (held-out arena).

  python r3/finetune_r3.py --init FT_R2_FINAL --bgs JOB/bg --official JOB/official-bg.npz --out JOB/ft-r4 --hours 5.5
"""
import argparse
import json
import math
import random
import signal
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C  # noqa: E402
import dense_labels as D  # noqa: E402
from finetune import Blocks, build_model, flat, targets, loss_fn as frame_loss, quick_val, FORMAT, P_MAX, FPB  # noqa: E402
from finetune2 import Windows, window_forward, event_targets, event_loss  # noqa: E402

KINDS = ('plain', 'official', 'hardneg', 'recolour', 'texture')
TW, TH = 28.545*448/540, 22.895*832/800        # one tile in arena-cache px (x, y)
CX0, CY0 = 12.09*448/540, (237.18-200)*832/800  # native tile (0, 0) in arena-cache px
BIG = {'Giant', 'Golem', 'Balloon', 'BabyDragon', 'IceGolem', 'Prince', 'DarkPrince', 'Goblinstein', 'MightyMiner',
       'Xbow', 'InfernoTower', 'BombTower', 'Tesla', 'Cannon', 'FirespiritHut', 'GoblinHut', 'ArcherQueen', 'HogRider',
       'RoyalHogs', 'Wizard', 'Berserker', 'Valkyrie', 'Musketeer', 'MiniPekka'}
FLY = {'Balloon', 'BabyDragon', 'Bats', 'Minions', 'MinionHorde'}


def px(x, y):
    return CX0+TW*x, CY0+TH*y


def tower_rows():
    """6 alive full-HP tower positives (cls, owner, x, y, frac, valid) at the label anchors."""
    return np.array([[56 if kind == 'king' else 57, o, ax/1000., ay/1000., 1., 1.] for o, kind, _, ax, ay in C.TOWER_SLOTS], np.float32)


def tower_mask(template):
    """Tower pixels of the renderer template: inside generous tower boxes, colour far from the median floor (sand)."""
    box = np.zeros((832, 448), np.uint8)
    for o, kind, _, ax, ay in C.TOWER_SLOTS:
        x, y = px(ax/1000., ay/1000.)
        hw, up, dn = (2.6, 4.2, 2.4) if kind == 'king' else (2.0, 3.6, 2.0)
        cv2.rectangle(box, (int(x-hw*TW), int(y-up*TH)), (int(x+hw*TW), int(y+dn*TH)), 1, -1)
    t = cv2.blur(template.astype(np.float32), (5, 5))
    sand = np.median(t[box == 0].reshape(-1, 3), 0)
    m = ((np.abs(t-sand).max(2) > 40) & (box > 0)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.5)


class CompBlocks(Blocks):
    """Blocks + per-frame floor kind, floor index, the match-start background and the unit box mask."""
    def __init__(self, *args, bgs=None, n_official=1, probs=(.3, .3, .06, .14, .2), badge_p=.6, **kw):
        super().__init__(*args, **kw)
        self.bgs, self.n_official, self.probs, self.badge_p = Path(bgs), n_official, probs, badge_p
        self._bg = {}; self.names = None; self._tpl = None

    def template(self):
        if self._tpl is None:
            self._tpl = cv2.imread(str(self.bgs/'template.png')).astype(np.int16)
        return self._tpl

    def bg(self, ep):
        if ep not in self._bg:
            if len(self._bg) > 64:
                self._bg.pop(next(iter(self._bg)))
            im = cv2.imread(str(self.bgs/f'{ep}.png'))
            if im is None or im.shape != (832, 448, 3):
                raise FileNotFoundError(f'background missing: {ep}')
            self._bg[ep] = im
        return self._bg[ep]

    def __getitem__(self, index):
        d = super().__getitem__(index)
        if self.names is None:
            self.names = D.vocab(self._guard.cards)
        rng = random.Random(self.seed*9_000_011+index+17)
        ep = self._last_ep
        kinds = np.array([rng.choices(range(len(KINDS)), weights=self.probs)[0] for _ in range(FPB)], np.int64)
        fl = np.array([rng.randrange(self.n_official) for _ in range(FPB)], np.int64)
        box = np.zeros((FPB, 832, 448), np.uint8)
        pos, ign = d['pos'].numpy(), d['ign'].numpy()
        arena = d['arena'].numpy(); bgi = self.bg(ep).astype(np.int16)
        for f in range(FPB):
            units = []
            for c, o, x, y, fr, v in pos[f]:
                if v <= 0 or c >= 56:
                    continue
                name = self.names[int(c)]
                hw, up, dn = (2.3, 4.3, 1.0) if name in BIG else (1.7, 3.2, .9)
                if name in FLY:
                    up += 1.2
                X, Y = px(x, y)
                cv2.rectangle(box[f], (int(X-hw*TW), int(Y-up*TH)), (int(X+hw*TW), int(Y+dn*TH)), 1, -1)
                units.append((X, Y, name in BIG, up))
            for x, y, v in ign[f]:
                if v > 0:
                    X, Y = px(x, y)
                    cv2.rectangle(box[f], (int(X-2*TW), int(Y-4*TH)), (int(X+2*TW), int(Y+TH)), 1, -1)
            if KINDS[kinds[f]] != 'plain':
                keep = pos[f][(pos[f][:, 5] > 0) & (pos[f][:, 0] < 56)]
                if KINDS[kinds[f]] == 'hardneg':
                    keep = keep[:0]; ign[f] = 0; box[f] = 0
                rows = np.concatenate([keep, tower_rows()])[:P_MAX]
                pos[f] = 0; pos[f, :len(rows)] = rows
            box[f] = self.unit_mask(arena, f, bgi, box[f], units, rng, KINDS[kinds[f]])
        d.update(pos=torch.from_numpy(pos), ign=torch.from_numpy(ign), kind=torch.from_numpy(kinds), floor=torch.from_numpy(fl),
                 box=torch.from_numpy(box), bg=torch.from_numpy(np.ascontiguousarray(self.bg(ep))))
        return d

    def unit_mask(self, arena, f, bgi, box, units, rng, kind):
        """Pixel mask of the frame's units (CPU). Badge strip: the official client draws no level badge / HP bar on full-HP
        units (the renderer always does), so with p=badge_p a unit's top 16 px band (badge + bar) is dropped from the mask;
        on plain frames that band is repainted with the match-start floor."""
        if kind == 'hardneg' or not units:
            return np.zeros_like(box)
        fr = arena[f].astype(np.int16)
        m = ((np.abs(fr-bgi).max(2) > 20) & (np.abs(fr-self.template()).max(2) > 20) & (box > 0)).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)) & box
        keep = m.copy()
        for X, Y, big, up in units:
            if rng.random() >= self.badge_p:
                continue
            hw = 1.8 if big else 1.4
            x0, x1 = max(0, int(X-hw*TW)), min(448, int(X+hw*TW)); y0, y1 = max(0, int(Y-up*TH)), max(0, int(Y))
            rows = np.nonzero(m[y0:y1, x0:x1].sum(1) >= 3)[0]
            if len(rows):
                top = y0+int(rows[0]); keep[top:top+16, x0:x1] = 0
        if kind == 'plain':
            strip = (m > 0) & (keep == 0)
            arena[f][strip] = bgi[strip].astype(np.uint8)
            return np.zeros_like(box)
        return keep


def _patch_getitem():
    """Blocks.__getitem__ picks the episode internally; record it for CompBlocks (wrap pix(), called once per item last)."""
    orig = Blocks.pix

    def pix(self, ep):
        self._last_ep = ep
        return orig(self, ep)
    Blocks.pix = pix


_patch_getitem()


def any_unit_rows(pos, names):
    """pos [B,P,6] (cls, owner, x, y, frac, valid) -> pos with one extra AnyTroop/AnyBuilding row per valid card body."""
    building = torch.tensor([n in C.BUILDING_CARDS for n in names[:56]], device=pos.device)
    cls = pos[..., 0].long(); ok = (pos[..., 5] > 0) & (cls < 56)
    dup = pos.clone()
    dup[..., 0] = torch.where(building[cls.clamp(0, 55)], 59., 58.)
    dup[..., 5] = ok.float()
    return torch.cat([pos, dup], 1)


def load_any_unit(init, names, device):
    """live-dense-v1 checkpoint with 58 identities -> PerceptionV4 with 60 (AnyTroop, AnyBuilding appended); copies by name."""
    from clasher.vision.l1_v4 import PerceptionV4
    st = torch.load(init, map_location='cpu', weights_only=False)
    old = st['identities']; K = len(names)
    model = PerceptionV4(len(st['cards']), K)
    if list(old) == list(names):
        model.load_state_dict(st['model']); return model.to(device), st
    cur = model.state_dict(); ob = len(old)
    for k, v in st['model'].items():
        if not k.startswith('body.heatmap'):
            cur[k] = v
    w, bias = cur['body.heatmap.weight'], cur['body.heatmap.bias']
    w.zero_(); bias.fill_(-4)
    for j, n in enumerate(old):
        t = names.index(n)
        for o in (0, 1):
            w[o*K+t] = st['model']['body.heatmap.weight'][o*ob+j]; bias[o*K+t] = st['model']['body.heatmap.bias'][o*ob+j]
    model.load_state_dict(cur)
    print(json.dumps(dict(any_unit_init=str(init), copied=len(old), new=[n for n in names if n not in old])), flush=True)
    return model.to(device), st


def rgb_jitter(x, gen, strength=1.):
    """x [B,3,H,W] BGR in [0,1] -> hue rotation (YIQ), saturation, value, contrast; per sample."""
    B = x.shape[0]; dev = x.device
    th = torch.empty(B, device=dev).uniform_(-math.pi, math.pi, generator=gen)*strength
    sat = torch.empty(B, device=dev).uniform_(1-.6*strength, 1+.5*strength, generator=gen)
    val = torch.empty(B, 1, 1, 1, device=dev).uniform_(1-.35*strength, 1+.25*strength, generator=gen)
    con = torch.empty(B, 1, 1, 1, device=dev).uniform_(1-.4*strength, 1+.3*strength, generator=gen)
    rgb = x.flip(1)
    T = torch.tensor([[.299, .587, .114], [.596, -.274, -.322], [.211, -.523, .312]], device=dev); Ti = torch.linalg.inv(T)
    yiq = torch.einsum('ij,bjhw->bihw', T, rgb)
    c, s = th.cos()*sat, th.sin()*sat
    i2 = c[:, None, None]*yiq[:, 1]-s[:, None, None]*yiq[:, 2]; q2 = s[:, None, None]*yiq[:, 1]+c[:, None, None]*yiq[:, 2]
    rgb = torch.einsum('ij,bjhw->bihw', Ti, torch.stack([yiq[:, 0], i2, q2], 1))
    m = rgb.mean((1, 2, 3), keepdim=True)
    rgb = ((rgb-m)*con+m)*val
    return rgb.clamp(0, 1).flip(1)


def textures(n, template, tmask, gen, dev):
    """Procedural floors with the renderer template's towers."""
    H, W = 832, 448
    lo = torch.rand(n, 3, 6, 4, device=dev, generator=gen)
    mid = torch.rand(n, 3, 26, 14, device=dev, generator=gen)
    base = F.interpolate(lo, (H, W), mode='bicubic', align_corners=False)
    mw = torch.rand(n, 1, 1, 1, device=dev, generator=gen)*.5
    tex = base*(1-mw)+F.interpolate(mid, (H, W), mode='bilinear', align_corners=False)*mw
    # checker tiles (arena floors are tiled), random size and contrast
    yy = torch.arange(H, device=dev).view(1, 1, H, 1).float(); xx = torch.arange(W, device=dev).view(1, 1, 1, W).float()
    size = torch.empty(n, 1, 1, 1, device=dev).uniform_(.5, 2.5, generator=gen)
    chk = (((xx/(TW*size)).floor()+(yy/(TH*size)).floor()) % 2)
    amp = torch.rand(n, 1, 1, 1, device=dev, generator=gen)*.15*(torch.rand(n, 1, 1, 1, device=dev, generator=gen) < .7)
    tex = tex*(1-amp)+chk*amp*tex*2
    tex = tex+torch.randn(n, 3, H, W, device=dev, generator=gen)*torch.rand(n, 1, 1, 1, device=dev, generator=gen)*.04
    tex = tex.clamp(0, 1)
    return tex*(1-tmask)+template*tmask


def composite(arena, bg, box, kind, floor, official, template, tmask, gen, tau=.08):
    """arena/bg [B,3,H,W] float; box [B,H,W] uint8 unit pixel mask; official [N,3,H,W]; template [1,3,H,W]."""
    B = arena.shape[0]; dev = arena.device
    out = arena.clone()
    k = kind
    if not bool((k != 0).any()):
        return out
    m = F.avg_pool2d(box[:, None].float(), 3, 1, 1)  # unit pixel mask from the loader (CompBlocks.unit_mask), feathered
    dest = torch.zeros_like(arena)
    sel = (k == 1) | (k == 2)
    if sel.any():
        dest[sel] = official[floor[sel]]
        rec = sel & (torch.rand(B, device=dev, generator=gen) < .5)
        if rec.any():
            dest[rec] = rgb_jitter(dest[rec], gen, .5)
    sel = k == 3
    if sel.any():
        dest[sel] = rgb_jitter(bg[sel], gen, 1.)
    sel = k == 4
    if sel.any():
        dest[sel] = textures(int(sel.sum()), template, tmask, gen, dev)
    composite.last_mask = m
    comp = m*arena+(1-m)*dest
    comp[k == 2] = dest[k == 2]
    return torch.where((k != 0)[:, None, None, None], comp, out)


def augment(arena, hud, kind, gen):
    """finetune.augment + stronger resolution loss (720x1280 capture ~ 0.6 of the renderer's source px per canvas px)."""
    B = arena.shape[0]; dev = arena.device
    gain = torch.empty(B, 1, 1, 1, device=dev).uniform_(.75, 1.25, generator=gen)
    gamma = torch.empty(B, 1, 1, 1, device=dev).uniform_(.8, 1.2, generator=gen)
    tint = torch.empty(B, 3, 1, 1, device=dev).uniform_(.9, 1.1, generator=gen)
    arena = (arena*gain*tint).clamp(0, 1)**gamma; hud = (hud*gain*tint).clamp(0, 1)**gamma
    for s, frac in ((random.uniform(.45, .7), .45), (random.uniform(.7, .9), .3)):
        sel = torch.rand(B, device=dev, generator=gen) < frac
        if sel.any():
            sub = arena[sel]
            arena[sel] = F.interpolate(F.interpolate(sub, scale_factor=s, mode='area'), size=sub.shape[-2:], mode='bilinear',
                                       align_corners=False)
    sel = torch.rand(B, device=dev, generator=gen) < .3
    if sel.any():
        s = random.uniform(.5, .9); subh = hud[sel]
        hud[sel] = F.interpolate(F.interpolate(subh, scale_factor=s, mode='area'), size=subh.shape[-2:], mode='bilinear', align_corners=False)
    noise = torch.rand(B, 1, 1, 1, device=dev, generator=gen)*.03
    arena = (arena+torch.randn(arena.shape, device=dev, generator=gen)*noise).clamp(0, 1)
    flip = torch.rand(B, device=dev, generator=gen) < .3
    arena = torch.where(flip[:, None, None, None], arena.flip(-1), arena)
    return arena, hud, flip


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--init', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--bgs', type=Path, required=True); p.add_argument('--official', type=Path, required=True)
    p.add_argument('--labels', type=Path, default=Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels'))
    p.add_argument('--hours', type=float, default=5.5); p.add_argument('--epoch-steps', type=int, default=1000)
    p.add_argument('--blocks', type=int, default=8); p.add_argument('--windows', type=int, default=8)
    p.add_argument('--workers', type=int, default=8); p.add_argument('--wworkers', type=int, default=6)
    p.add_argument('--lr', type=float, default=1.5e-4); p.add_argument('--tlr', type=float, default=1.5e-4)
    p.add_argument('--max-steps', type=int, default=0); p.add_argument('--val-matches', type=int, default=16)
    p.add_argument('--probs', default='.3,.3,.06,.14,.2'); p.add_argument('--badge-p', type=float, default=.6); p.add_argument('--any-unit', action='store_true'); p.add_argument('--seed', type=int, default=20261016)
    p.add_argument('--dump', type=Path, default=None, help='write a few composited inputs as JPEG (debug) and exit')
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2); torch.manual_seed(a.seed); random.seed(a.seed); device = 'cuda'
    guard = C.HeldoutGuard()
    train_eps = guard.episodes('train'); val_eps = guard.episodes('validation')[:a.val_matches]
    guard.check(train_eps+val_eps); assert not (set(train_eps) & set(val_eps))
    names = D.vocab(guard.cards)+(list(C.ANY_UNIT) if a.any_unit else [])
    K = len(names); nc = len(guard.cards)
    off = np.load(a.official)
    if any('training' in str(n).lower() or 'tc' == str(n)[:2] for n in off['names']):
        raise AssertionError('Training Camp is the held-out arena')
    official = torch.from_numpy(off['arena']).to(device).permute(0, 3, 1, 2).float()/255
    template = torch.from_numpy(cv2.imread(str(a.bgs/'template.png'))).to(device).permute(2, 0, 1)[None].float()/255
    tmask = torch.from_numpy(tower_mask(cv2.imread(str(a.bgs/'template.png')))).to(device)[None, None]
    if a.any_unit:
        model, _ = load_any_unit(a.init, names, device); model.train()
    else:
        model, _ = build_model(a.init, K, 'cpu'); model.to(device).train()
    groups = dict(head=[], rest=[], temporal=[])
    for n, p_ in model.named_parameters():
        groups['temporal' if n.startswith('temporal.') else 'head' if n.startswith(('body.', 'hud.')) else 'rest'].append(p_)
    bases = (a.lr, a.lr/2, a.tlr)
    opt = torch.optim.AdamW([dict(params=groups['head'], lr=a.lr), dict(params=groups['rest'], lr=a.lr/2),
                             dict(params=groups['temporal'], lr=a.tlr)], weight_decay=1e-4)
    fixed = []
    for ep in val_eps:
        lab = D.load(a.labels/f'{ep}.npz'); n = len(lab['row'])
        for k in range(0, n//16, 8):
            ok = [i for i in range(k*16, min(n, k*16+16)) if lab['row'][i] >= 0]
            if len(ok) >= 4:
                fixed.append((ep, k, ok[::max(1, len(ok)//4)][:4]))
    val_loader = torch.utils.data.DataLoader(Blocks(val_eps, a.labels, 'validation', 0, 0, fixed=fixed), batch_size=a.blocks, num_workers=3)
    probs = tuple(float(x) for x in a.probs.split(','))
    train = CompBlocks(train_eps, a.labels, 'train', 10**8, a.seed, bgs=a.bgs, n_official=len(official), probs=probs, badge_p=a.badge_p)
    loader = torch.utils.data.DataLoader(train, batch_size=a.blocks, num_workers=a.workers, pin_memory=True,
                                         persistent_workers=True, prefetch_factor=3, sampler=range(10**8))
    wtrain = Windows(train_eps, a.labels, 'train', 10**8, a.seed+1, guard.cards)
    wloader = torch.utils.data.DataLoader(wtrain, batch_size=a.windows, num_workers=a.wworkers, pin_memory=True,
                                          persistent_workers=True, prefetch_factor=3, sampler=range(10**8))
    meta = dict(format=FORMAT, cards=guard.cards, bodies=names, identities=names, any_unit=bool(a.any_unit),
                init=str(a.init), init_sha256=C.sha(a.init), split_sha256=C.SPLIT_SHA, train_matches=len(train_eps),
                round3=dict(kinds=KINDS, probs=probs, badge_p=a.badge_p, official_floors=[str(n) for n in off['names']], heldout_arena='Training Camp'),
                temporal='trained on dense events (finetune2 windows, renderer only)', offsets='body_box[0:2] = sub-cell x,y offset',
                heldout_opened=False)
    (a.out/'meta.json').write_text(json.dumps(meta, indent=1)+'\n')
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGUSR1, stop)
    gen = torch.Generator(device=device); gen.manual_seed(a.seed)
    deadline = time.time()+a.hours*3600; t0 = time.time(); tl = time.time(); run = {}; step = 0; est = a.max_steps or 10**9
    history = []
    import finetune2 as F2

    def wval_metrics():
        # finetune2.main's closure is not importable; minimal copy of its window metric
        model.eval(); tot = dict(loss=0., n=0, tp=0, fp=0, fn=0)
        with torch.no_grad():
            for w in wval:
                out = window_forward(model, w, device, train=False)
                ev = w['events'].to(device); heat, age, mask = event_targets(ev, nc)
                l1, l2 = event_loss(out, heat, age, mask); tot['loss'] += float(l1+l2); tot['n'] += 1
                sc = out['event_heatmap'].float().sigmoid(); pk = (sc == F.max_pool2d(sc, 3, 1, 1)) & (sc >= .5)
                for bi in range(len(ev)):
                    tr = [(int(e[1])*nc+int(e[0]), float(e[2]), float(e[3])) for e in ev[bi].cpu().numpy() if e[5] > 0]
                    cs, ys, xs = torch.nonzero(pk[bi], as_tuple=True); used = set()
                    for c, y, x in zip(cs.tolist(), ys.tolist(), xs.tolist()):
                        hit = [j for j, t in enumerate(tr) if j not in used and t[0] == c and math.hypot(t[1]-(x+.5)/2, t[2]-(y+.5)/2) <= 2]
                        if hit:
                            used.add(hit[0]); tot['tp'] += 1
                        else:
                            tot['fp'] += 1
                    tot['fn'] += len(tr)-len(used)
        model.train()
        return dict(event_loss=tot['loss']/max(1, tot['n']), event_pr_window=(round(tot['tp']/max(1, tot['tp']+tot['fp']), 4),
                                                                              round(tot['tp']/max(1, tot['tp']+tot['fn']), 4)))
    wfixed = []
    for ep in val_eps:
        lab = D.load(a.labels/f'{ep}.npz'); tick = lab['tick']; ev = F2.load_events(ep, guard.cards)
        for e in ev[::2]:
            wfixed.append((ep, int(np.clip(np.searchsorted(tick, e[4]+10), 1, len(tick)-1)), 15.))
        for end in range(40, len(tick), 400):
            wfixed.append((ep, end, 15.))
    wval = torch.utils.data.DataLoader(Windows(val_eps, a.labels, 'validation', 0, 0, guard.cards, fixed=wfixed), batch_size=a.windows, num_workers=3)

    def save_epoch(tag):
        torch.save(dict(model=model.state_dict(), step=step, **meta), a.out/f'{tag}.tmp'); (a.out/f'{tag}.tmp').replace(a.out/f'{tag}.pt')

    if not a.dump:
        qv = quick_val(model, val_loader, K, device, meta['identities']); qv.update(wval_metrics()); qv.update(step=0, init=True)
        history.append(qv); print(json.dumps(dict(val=qv)), flush=True)
    t0 = time.time()  # rate estimate excludes the initial validation
    for b, w in zip(loader, wloader):
        if stopping or time.time() > deadline or (a.max_steps and step >= a.max_steps):
            break
        if step == 150:
            rate = 150/(time.time()-t0); est = a.max_steps or int(rate*(deadline-time.time())*.95)
            print(json.dumps(dict(steps_per_s=round(rate, 3), est_steps=est)), flush=True)
        scale = min(1., (step+1)/200)*(.5*(1+math.cos(math.pi*min(1., step/est))))*.97+.03
        for g, base in zip(opt.param_groups, bases):
            g['lr'] = base*scale
        bg = b.pop('bg').to(device, non_blocking=True)
        b = flat(b, device)
        arena = b['arena'].permute(0, 3, 1, 2).float()/255; hud = b['hud'].permute(0, 3, 1, 2).float()/255
        bgf = bg.permute(0, 3, 1, 2).float().div(255).repeat_interleave(FPB, 0)
        arena = composite(arena, bgf, b['box'], b['kind'], b['floor'], official, template, tmask, gen)
        arena, hud, flip = augment(arena, hud, b['kind'], gen)
        if a.dump:
            a.dump.mkdir(parents=True, exist_ok=True)
            for i in range(len(arena)):
                im = (arena[i].permute(1, 2, 0).cpu().numpy()*255).astype(np.uint8).copy()
                for c, o, x, y, fr, v in b['pos'][i].cpu().numpy():
                    if v > 0:
                        X, Y = px(18-x if bool(flip[i]) else x, y)
                        cv2.circle(im, (int(X), int(Y)), 4, (255, 0, 0) if o == 1 else (0, 0, 255), -1)
                cv2.imwrite(str(a.dump/f'{step}-{i}-{KINDS[int(b["kind"][i])]}.jpg'), im)
                mm = getattr(composite, 'last_mask', None)
                if mm is not None:
                    cv2.imwrite(str(a.dump/f'{step}-{i}-mask.png'), (mm[i, 0].cpu().numpy()*255).astype(np.uint8))
            step += 1
            if step >= 2:
                return
            continue
        with torch.autocast('cuda', dtype=torch.bfloat16):
            out = model.encode(arena, hud)
        if a.any_unit:
            b['pos'] = any_unit_rows(b['pos'], names)
        heat, valid, peak, off_, hp = targets(b, K, flip)
        floss, parts = frame_loss(out, b, heat, valid, peak, off_, hp)
        wout = window_forward(model, w, device, train=True, gen=gen)
        eh, ea, em = event_targets(w['events'].to(device), nc)
        e1, e2 = event_loss(wout, eh, ea, em)
        loss = floss+e1+.2*e2
        if not torch.isfinite(loss):
            raise ValueError('nonfinite loss')
        opt.zero_grad(set_to_none=True); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 10); opt.step(); step += 1
        parts.update(event=e1, age=e2)
        for k, v in parts.items():
            run[k] = run.get(k, 0.)+float(v)
        if step % 100 == 0:
            print(json.dumps(dict(step=step, lr_scale=round(scale, 4), sec=round(time.time()-tl, 1),
                                  **{k: round(v/100, 4) for k, v in run.items()})), flush=True)
            run = {}; tl = time.time()
        if step % a.epoch_steps == 0:
            save_epoch(f'epoch-{step//a.epoch_steps}')
            qv = quick_val(model, val_loader, K, device, meta['identities']); qv.update(wval_metrics()); qv.update(step=step, time=time.time()-t0)
            history.append(qv); print(json.dumps(dict(val=qv)), flush=True)
            (a.out/'history.json').write_text(json.dumps(history, indent=1)+'\n')
    save_epoch('final')
    qv = quick_val(model, val_loader, K, device, meta['identities']); qv.update(wval_metrics()); qv.update(step=step, final=True)
    history.append(qv); print(json.dumps(dict(done=True, val=qv)), flush=True)
    (a.out/'history.json').write_text(json.dumps(history, indent=1)+'\n')


if __name__ == '__main__':
    main()
