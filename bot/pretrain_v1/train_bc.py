"""pretrain-v1 behaviour cloning (PREREG section 5) on a dataset.py store.

    python -m bot.pretrain_v1.train_bc --store DIR --out RUN --seed 2026102001 [--device cuda] [--epochs 8]

Objective per retained row (weights w = w_ipw * w_dom; w_ipw = 10 for retained WAIT / forced rows):
  natural-frequency gate/slot CE (5-way, masked) + 1[play] * conditional tile CE (576-way, masked)  on actor rows
  + .25 * W/D/L CE on rows of qualified complete matches (exact / outcome tiers), weighted by w_ipw.
Sampling: Hog-cycle (base-composition Hog 2.6, Log or Zap) and general perspectives drawn 50/50 (DESIGN item 6).
AdamW lr 3e-4, wd 1e-4, batch 512, grad clip 1, one-epoch linear warm-up then cosine; at most 8 passes, stop after
2 passes without DEV joint-NLL improvement (on a fixed CAPPED DEV sample: per-epoch metrics are sampled estimates).
best.pt / best-calibrated.pt are per-seed conveniences only. The REGISTERED anchor selection (gate calibration + full
DEV G1 admission + eligibility + tie rules across all seeds and epochs) is select_bc.py.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

from . import featurize as F
from .model import PolicyV1

SEEDS = (2026102001, 2026102002, 2026102003)
FIXED = ('tow', 'hand', 'glob', 'lag', 'slot_ok', 'alive', 'gate', 'slot', 'tile', 'actor', 'w_ipw', 'w_dom', 'value',
         'match', 'seat', 'tick', 'why', 'unc')
RAGGED = (('ent', F.E_COLS, F.MAX_ENT), ('ev', F.V_COLS, F.MAX_EV), ('rev', F.R_COLS, F.MAX_REV))


def host_resource_check(extra_bytes=0):
    """Opt-in cooperative host guard. Raise in our own job; never signal another process."""
    import os
    floor = float(os.environ.get('PV1_HOST_MIN_AVAILABLE_GIB', '0'))
    ceiling = float(os.environ.get('PV1_HOST_MAX_LOAD', '0'))
    if floor:
        avail = next(int(line.split()[1])/2**20 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
        if avail - extra_bytes/2**30 < floor:
            raise RuntimeError(f'host MemAvailable {avail:.2f} GiB below {floor} after projected {extra_bytes/2**30:.2f} GiB allocation')
    if ceiling and os.getloadavg()[0] > ceiling:
        raise RuntimeError(f'host load {os.getloadavg()[0]:.2f} above {ceiling}')


def guarded_concatenate(parts):
    host_resource_check(2*sum(p.nbytes for p in parts))  # include possible dtype conversion after concatenation
    result = np.concatenate(parts)
    host_resource_check()
    return result


class Store:
    """All shards of one dataset store: fixed per-row arrays in RAM, ragged arrays memory-mapped."""

    def __init__(self, root, lease_poll=None):
        host_resource_check()
        root = Path(root)
        self.shards = sorted(p for p in (root/'shards').iterdir() if p.is_dir() and not p.name.startswith('.'))
        fixed = {k: [] for k in FIXED}
        self.rag = {k: [] for k, _, _ in RAGGED}
        self.meta = []
        self.row_shard, self.row_local = [], []
        hashes = set()
        split_of, hog, hogzap, vanilla, persp, phys, donor = [], [], [], [], [], [], []
        fp_index, donor_index = {}, {}
        moff = 0
        for si, sd in enumerate(self.shards):
            if lease_poll is not None:
                lease_poll()
            host_resource_check()
            m = json.loads((sd/'meta.json').read_text())
            hashes.add(m['feature_hash'])
            self.meta.append(m)
            n = m['rows']
            for k in FIXED:
                host_resource_check((sd/f'{k}.npy').stat().st_size)
                fixed[k].append(np.load(sd/f'{k}.npy'))
            for k, _, _ in RAGGED:
                host_resource_check((sd/f'{k}_off.npy').stat().st_size)
                self.rag[k].append((np.load(sd/f'{k}.npy', mmap_mode='r'), np.load(sd/f'{k}_off.npy')))
            host_resource_check(n*80)  # row maps and derived split/donor arrays for this shard
            self.row_shard.append(np.full(n, si, np.int32))
            self.row_local.append(np.arange(n, dtype=np.int64))
            mt = m['matches']
            mi, seat = fixed['match'][-1], fixed['seat'][-1]
            persp.append((moff + mi.astype(np.int64))*2 + seat)            # one id per (match, seat)
            fps = np.array([fp_index.setdefault(x['fp'], len(fp_index)) for x in self.meta[-1]['matches']] + [-1])
            phys.append(fps[mi])                                            # one id per physical game (fingerprint)
            # one id per human DONOR perspective across duplicate copies: (game fingerprint, own deck, other deck)
            dk = np.array([[donor_index.setdefault((x['fp'], tuple(sorted(x['seats'][s_]['deck'])),
                                                    tuple(sorted(x['seats'][1 - s_]['deck']))), len(donor_index))
                            for s_ in (0, 1)] for x in self.meta[-1]['matches']] + [[-1, -1]])
            donor.append(dk[mi, seat])
            moff += len(self.meta[-1]['matches'])
            sp = np.array([{'train': 0, 'dev': 1, 'final': 2}[x['split']] for x in mt] + [0], np.int8)
            split_of.append(sp[mi])
            hg = np.array([[s['hog26'] for s in x['seats']] for x in mt] + [[0, 0]], np.int8)
            hz = np.array([[s['hog26_zap'] for s in x['seats']] for x in mt] + [[0, 0]], np.int8)
            va = np.array([[s['vanilla'] for s in x['seats']] for x in mt] + [[0, 0]], np.int8)
            hog.append(hg[mi, seat])
            hogzap.append(hz[mi, seat])
            vanilla.append(va[mi, seat])
        if len(hashes) > 1:
            raise SystemExit(f'store mixes feature hashes {hashes}')
        if hashes and hashes != {F.feature_hash()}:
            raise SystemExit(f'store feature hash {hashes} != featurizer {F.feature_hash()}')
        self.x = {k: guarded_concatenate(v) for k, v in fixed.items()}
        fixed.clear()
        self.row_shard = guarded_concatenate(self.row_shard)
        self.row_local = guarded_concatenate(self.row_local)
        self.split = guarded_concatenate(split_of)
        self.hog = guarded_concatenate(hog).astype(bool)
        self.hogzap = guarded_concatenate(hogzap).astype(bool)
        self.vanilla = guarded_concatenate(vanilla).astype(bool)
        self.persp = guarded_concatenate(persp)
        self.phys = guarded_concatenate(phys)
        self.donor = guarded_concatenate(donor)
        self.n = len(self.split)

    def batch(self, idx):
        host_resource_check()
        b = {k: self.x[k][idx] for k in FIXED}
        sh, lo = self.row_shard[idx], self.row_local[idx]
        for k, cols, cap in RAGGED:
            parts = []
            for s, l in zip(sh, lo):
                data, off = self.rag[k][s]
                parts.append(data[off[l]:off[l + 1]])
            n = min(cap, max([len(p) for p in parts] + [1]))
            arr = np.zeros((len(idx), n, cols), np.int16)
            mask = np.zeros((len(idx), n), bool)
            for i, p in enumerate(parts):
                k_ = min(len(p), n)
                arr[i, :k_] = p[:k_]
                mask[i, :k_] = True
            b[k], b[k + '_mask'] = arr, mask
        # tile legality of the labelled slot (play rows) from the public placement geometry
        tok = np.zeros((len(idx), F.NTILE), bool)
        for i in np.nonzero(b['gate'] == 1)[0]:
            s = int(b['slot'][i])
            tok[i] = F.tile_mask(int(b['hand'][i, s, F.H_PLACE]), tuple(bool(a) for a in b['alive'][i]))
        b['tile_ok'] = tok
        b['hog'], b['hogzap'], b['vanilla'] = self.hog[idx], self.hogzap[idx], self.vanilla[idx]
        return b


def _waterfill(total, caps):
    """Split `total` mass equally over items, none above its cap (water-filling); -> (masses, unplaced mass)."""
    m = np.zeros(len(caps))
    order = np.argsort(caps)
    left, n = float(total), len(caps)
    for k, i in enumerate(order):
        share = left/(n - k)
        m[i] = min(share, caps[i])
        left -= m[i]
    return m, left


def game_sampler(store, tr, hog_share, max_exposure):
    """Row-draw probabilities over train rows that balance PHYSICAL DONORS (DESIGN item 5 / Sol R3 #3, R4 #5): each
    human donor perspective (game fingerprint + own deck + other deck, i.e. all duplicate copies of it together) gets
    equal mass within its group (Hog-cycle / general), split hog_share : 1 - hog_share; a donor's mass is split
    equally over its copies, and a copy's over its rows (long games and duplicated games do not dominate). Exposure
    cap: no row is drawn more than `max_exposure` times per pass in expectation; capped mass goes to the group's other
    donors, then to the other group. The realised Hog share is reported."""
    N = len(tr)
    pid, did = store.persp[tr], store.donor[tr]
    pu, pinv, pcnt = np.unique(pid, return_inverse=True, return_counts=True)       # perspective copies
    p_donor = np.zeros(len(pu), np.int64)
    p_donor[pinv] = did
    du, dinv = np.unique(p_donor, return_inverse=True)                              # copies -> donors
    copies = np.bincount(dinv, minlength=len(du))
    min_rows = np.full(len(du), np.inf)
    np.minimum.at(min_rows, dinv, pcnt)
    hog_d = np.zeros(len(du), bool)
    hog_rows = store.hog[tr]
    hog_d[dinv[pinv[hog_rows]]] = True
    caps = max_exposure*min_rows*copies/N                     # a donor's mass m -> m / copies / rows per row
    share = {True: hog_share if hog_d.any() and (~hog_d).any() else float(hog_d.any())}
    share[False] = 1.0 - share[True]
    mass = np.zeros(len(du))
    left = {}
    for g in (True, False):
        mass[hog_d == g], left[g] = _waterfill(share[g], caps[hog_d == g])
    for g in (True, False):
        if left[g] > 1e-12:
            sel = hog_d == (not g)
            extra, _ = _waterfill(left[g], caps[sel] - mass[sel])
            mass[sel] += extra
    copy_mass = mass[dinv]/copies[dinv]
    p = copy_mass[pinv]/pcnt[pinv]
    p /= p.sum()
    info = dict(donors=int(len(du)), perspectives=int(len(pu)), duplicate_copies=int((copies - 1).sum()),
                hog_donors=int(hog_d.sum()), hog_share_requested=hog_share, hog_share_realised=float(p[hog_rows].sum()),
                max_row_exposure=float((p*N).max()),
                rows_per_perspective=[int(pcnt.min()), int(np.median(pcnt)), int(pcnt.max())])
    return p, info


def to_torch(b, device, drop_ages=0.0, rng=None):
    out = {k: torch.from_numpy(np.ascontiguousarray(v)).to(device, non_blocking=True) for k, v in b.items()}
    if drop_ages and rng is not None:
        # missing-extras augmentation: live recordings (and a live translator error) carry no unit RF ages
        drop = torch.from_numpy(rng.random(len(b['gate'])) < drop_ages).to(device)
        ent = out['ent'].clone()
        unit = (ent[..., F.E_KIND] == 1) & drop[:, None]
        ent[..., F.E_AGE] = torch.where(unit, torch.full_like(ent[..., F.E_AGE], -1), ent[..., F.E_AGE])
        out['ent'] = ent
        g = out['glob'].clone()
        g[:, F.G_X_UNITS] = torch.where(drop, torch.zeros_like(g[:, F.G_X_UNITS]), g[:, F.G_X_UNITS])
        out['glob'] = g
    return out


def losses(model, b):
    out = model(b)
    gate = out['gate']
    actor = b['actor'].bool()
    play = (b['gate'] == 1) & actor
    target = torch.where(play, b['slot'].long() + 1, torch.zeros_like(b['slot'].long()))
    logp = torch.log_softmax(gate, -1)
    gate_nll = -logp.gather(1, target[:, None]).squeeze(1)
    tile_nll = torch.zeros_like(gate_nll)
    if play.any():
        pi = play.nonzero().squeeze(1)
        z = model.tile_logits(out['cls'][pi], out['hand'][pi], b['slot'][pi].long(), b['tile_ok'][pi])
        tile_nll[pi] = Fn.cross_entropy(z, b['tile'][pi].long(), reduction='none')
    w = b['w_ipw']*b['w_dom']*actor.float()
    joint = gate_nll + tile_nll
    vmask = b['value'] >= 0
    # the value loss sees the natural row distribution: undo the Hog 50/50 draw (otherwise ~600 Hog games' outcomes
    # are memorised; v0 shakedown DEV Hog value NLL 3.05 after one pass)
    wv = b['w_ipw']*vmask.float()*b.get('iw', torch.ones_like(b['w_ipw']))
    v_nll = Fn.cross_entropy(out['value'], b['value'].long().clamp(min=0), reduction='none')
    return dict(out=out, gate_nll=gate_nll, tile_nll=tile_nll, joint=joint, w=w, v_nll=v_nll, wv=wv, play=play,
                logp=logp)


def objective(L):
    a = (L['w']*L['joint']).sum()/L['w'].sum().clamp(min=1e-6)
    v = (L['wv']*L['v_nll']).sum()/L['wv'].sum().clamp(min=1e-6)
    return a + .25*v, a, v


class Acc:
    """Weighted DEV metrics (natural frequency via w_ipw; domain weights not applied in evaluation)."""

    def __init__(self):
        self.s = {}

    def add(self, name, v, w=1.0):
        a = self.s.setdefault(name, [0.0, 0.0])
        a[0] += float(v)
        a[1] += float(w)

    def get(self):
        return {k: (v[0]/v[1] if v[1] else None) for k, v in self.s.items()}


def evaluate(model, store, idx, device, bs=1024, gate_bias=None, prefix='', lease_poll=None):
    model.eval()
    acc = Acc()
    bins = np.zeros((10, 3))                      # sum w, sum w*p, sum w*y  (gate calibration)
    groups = {'all': None, 'hog': 'hog', 'hogzap': 'hogzap', 'vanilla': 'vanilla'}
    with torch.inference_mode():
        for i in range(0, len(idx), bs):
            if lease_poll is not None:
                lease_poll()
            nb = store.batch(idx[i:i + bs])
            b = to_torch(nb, device)
            if gate_bias is not None:
                model.gate_bias.fill_(gate_bias)
            L = losses(model, b)
            actor = b['actor'].bool()
            wn = b['w_ipw']*actor.float()                     # natural frequency, no domain weight
            p = L['logp'].exp()
            p_play = 1 - p[:, 0]
            y = L['play'].float()
            pred_slot = L['logp'][:, 1:].argmax(1)
            for gname, key in groups.items():
                m = torch.ones_like(actor) if key is None else b[key]
                vm = (b['value'] >= 0) & m
                if vm.any():                                  # value rows count whether or not the actor is eligible
                    wv = b['w_ipw'][vm]
                    acc.add(f'{gname}/value_nll', (wv*L['v_nll'][vm]).sum(), wv.sum())
                    vp = torch.softmax(L['out']['value'][vm].float(), -1)
                    acc.add(f'{gname}/value_acc', (wv*(vp.argmax(1) == b['value'][vm].long()).float()).sum(), wv.sum())
                    oh = Fn.one_hot(b['value'][vm].long(), 3).float()
                    acc.add(f'{gname}/value_brier', (wv*((vp - oh)**2).sum(1)).sum(), wv.sum())
                ww = wn*m.float()
                if ww.sum() == 0:
                    continue
                acc.add(f'{gname}/joint_nll', (ww*L['joint']).sum(), ww.sum())
                acc.add(f'{gname}/gate_nll', (ww*L['gate_nll']).sum(), ww.sum())
                acc.add(f'{gname}/brier', (ww*(p_play - y)**2).sum(), ww.sum())
                acc.add(f'{gname}/plays_pred', (ww*p_play).sum(), 1)
                acc.add(f'{gname}/plays_true', (ww*y).sum(), 1)
                pm = L['play'] & m
                if pm.any():
                    acc.add(f'{gname}/tile_nll', L['tile_nll'][pm].sum(), pm.sum())
                    acc.add(f'{gname}/card_top1', (pred_slot[pm] == b['slot'][pm].long()).sum(), pm.sum())
                    out = L['out']
                    pi = pm.nonzero().squeeze(1)
                    z = model.tile_logits(out['cls'][pi], out['hand'][pi], b['slot'][pi].long(), b['tile_ok'][pi])
                    t_pred, t_true = z.argmax(1), b['tile'][pi].long()
                    dc = (t_pred % F.W - t_true % F.W).abs()
                    dr = (torch.div(t_pred, F.W, rounding_mode='floor') - torch.div(t_true, F.W, rounding_mode='floor')).abs()
                    acc.add(f'{gname}/tile_top1', (t_pred == t_true).sum(), len(pi))
                    acc.add(f'{gname}/tile_within1', ((dc <= 1) & (dr <= 1)).sum(), len(pi))
                    acc.add(f'{gname}/play_slot_nll', (-L['logp'][pi, 1 + b['slot'][pi].long()]
                                                       + torch.log(p_play[pi])).sum(), len(pi))
            pp, yy, w_ = p_play.cpu().numpy(), y.cpu().numpy(), wn.cpu().numpy()
            bi = np.minimum((pp*10).astype(int), 9)
            np.add.at(bins, (bi, 0), w_)
            np.add.at(bins, (bi, 1), w_*pp)
            np.add.at(bins, (bi, 2), w_*yy)
    r = acc.get()
    for g in groups:
        if r.get(f'{g}/plays_true'):
            r[f'{g}/plays_ratio'] = r[f'{g}/plays_pred']/r[f'{g}/plays_true']
    tot = bins[:, 0].sum()
    r['all/ece'] = float(sum(abs(b_[1] - b_[2]) for b_ in bins)/max(tot, 1e-9))
    r['all/reliability'] = [[float(b_[0]), float(b_[1]/b_[0]) if b_[0] else None, float(b_[2]/b_[0]) if b_[0] else None]
                            for b_ in bins]
    model.train()
    return {prefix + k: v for k, v in r.items()}


def fit_gate_bias(model, store, idx, device, bs=2048, lease_poll=None):
    """One scalar added to the no-op logit, minimising weighted Bernoulli NLL of play vs wait on natural DEV."""
    model.eval()
    zs, ws, ys = [], [], []
    with torch.inference_mode():
        model.gate_bias.zero_()
        for i in range(0, len(idx), bs):
            if lease_poll is not None:
                lease_poll()
            b = to_torch(store.batch(idx[i:i + bs]), device)
            L = losses(model, b)
            actor = b['actor'].bool()
            g = L['out']['gate']
            lse_play = torch.logsumexp(g[:, 1:], 1)
            zs.append((g[:, 0] - lse_play)[actor].cpu())         # logit of wait vs play
            ws.append(b['w_ipw'][actor].cpu())
            ys.append(L['play'][actor].float().cpu())
    z, w, y = torch.cat(zs).double(), torch.cat(ws).double(), torch.cat(ys).double()
    fin = torch.isfinite(z)
    z, w, y = z[fin], w[fin], y[fin]

    def nll(bias):
        pw = torch.sigmoid(z + bias)                           # P(wait)
        return float(-(w*(y*torch.log1p(-pw + 1e-12) + (1 - y)*torch.log(pw + 1e-12))).sum()/w.sum())
    lo, hi = -3.0, 3.0
    for _ in range(60):
        if lease_poll is not None:
            lease_poll()
        m1, m2 = lo + (hi - lo)/3, hi - (hi - lo)/3
        if nll(m1) < nll(m2):
            hi = m2
        else:
            lo = m1
    if lease_poll is not None:
        lease_poll()
    bias = (lo + hi)/2
    model.train()
    return bias, nll(0.0), nll(bias)


def baseline_nll(store, tr_idx, dev_idx, lease_poll=None):
    """Fixed training-frequency baseline: constant hazard, card frequency over legal slots, per-card tile frequency
    over legal tiles (add-one smoothing). Natural-frequency joint NLL on DEV (PREREG G1 criterion 1)."""
    x = store.x
    w = x['w_ipw'][tr_idx]*x['actor'][tr_idx]
    play = (x['gate'][tr_idx] == 1) & (x['actor'][tr_idx] == 1)
    hazard = float((w*play).sum()/w.sum())
    pi = tr_idx[play]
    cards = x['hand'][pi, x['slot'][pi].astype(int), F.H_CARD]
    cat = F.catalog()
    cf = np.bincount(cards, minlength=cat.n_cards).astype(float) + 1
    tf = np.ones((cat.n_cards, F.NTILE))
    np.add.at(tf, (cards, x['tile'][pi].astype(int)), 1)
    by = {'all': [0.0, 0.0], 'hog': [0.0, 0.0]}
    for j, i in enumerate(dev_idx):
        if lease_poll is not None and j % 1000 == 0:
            lease_poll()
        if not x['actor'][i]:
            continue
        wi = float(x['w_ipw'][i])
        ok = x['slot_ok'][i]
        if x['gate'][i] == 1:
            s = int(x['slot'][i])
            c = x['hand'][i, :4, F.H_CARD]
            pc = cf[c]*ok
            nll = -math.log(hazard) - math.log(pc[s]/pc.sum())
            m = F.tile_mask(int(x['hand'][i, s, F.H_PLACE]), tuple(bool(a) for a in x['alive'][i]))
            pt = tf[c[s]]*m
            nll -= math.log(pt[int(x['tile'][i])]/pt.sum())
        else:
            nll = -math.log(1 - hazard) if ok.any() else 0.0
        for g in ('all', 'hog'):
            if g == 'all' or store.hog[i]:
                by[g][0] += wi*nll
                by[g][1] += wi
    return {f'baseline/{g}/joint_nll': v[0]/v[1] for g, v in by.items() if v[1]}, hazard


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--store', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=SEEDS[0])
    ap.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
    ap.add_argument('--epochs', type=int, default=8)
    ap.add_argument('--patience', type=int, default=2)
    ap.add_argument('--bs', type=int, default=512)
    ap.add_argument('--lr', type=float, default=3e-4)
    ap.add_argument('--wd', type=float, default=1e-4)
    ap.add_argument('--drop-ages', type=float, default=.05)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--max-gpu-hours', type=float, default=64)
    ap.add_argument('--dev-cap', type=int, default=400000, help='DEV rows evaluated per pass (fixed subset)')
    ap.add_argument('--steps-per-epoch', type=int, default=0, help='0: one pass over the train rows')
    ap.add_argument('--hog-share', type=float, default=.5, help='DESIGN: Hog-cycle / general games drawn 50/50')
    ap.add_argument('--d', type=int, default=192, help='model width (size sweep; registered BC: 192)')
    ap.add_argument('--layers', type=int, default=4)
    ap.add_argument('--heads', type=int, default=6)
    ap.add_argument('--ffn', type=int, default=576)
    ap.add_argument('--drop', type=float, default=0.0)
    ap.add_argument('--amp', choices=('none', 'bf16'), default='none', help='CUDA autocast for training / DEV passes')
    ap.add_argument('--train-frac', type=float, default=1.0,
                    help='data-scaling read: keep this fraction of TRAIN donors (nested subsets, fixed RNG); DEV fixed')
    ap.add_argument('--eval-every', type=int, default=1, help='DEV evaluation every N passes (patience counts evals)')
    ap.add_argument('--warmup-steps', type=int, default=0, help='linear warm-up steps (0: one pass)')
    ap.add_argument('--max-row-exposure', type=float, default=5.0,
                    help='cap on expected draws per retained row per pass (duplicate-donor exposure cap)')
    a = ap.parse_args(argv)
    torch.set_num_threads(a.threads)
    import os
    frac = float(os.environ.get('PV1_GPU_FRACTION', '0') or 0)
    if frac and str(a.device).startswith('cuda'):
        # shared A6000: cap this process's caching allocator (an overrun fails THIS job; the cap does not reserve memory
    # for anyone else, so callers must also account for co-tenants: see reports/bot/pretrain-v1/sweep/sweep_08.py)
        torch.cuda.set_per_process_memory_fraction(frac)
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    from .lease_stop import LeaseStop
    lease = LeaseStop.from_env(out, a.seed)
    model = opt = sched = pool = None
    completed_training_state = None
    step, ep, consumed_batches = 0, -1, 0
    phase = 'initialization'

    def lease_poll():
        if lease is not None:
            lease.poll(model, opt, sched, step=step, epoch=ep, consumed_batches=consumed_batches,
                       phase=phase, args=a, pool=pool, model_state=completed_training_state)

    lease_poll()
    t_start = time.time()
    store = Store(a.store, lease_poll=lease_poll if lease is not None else None)
    lease_poll()
    tr = np.nonzero(store.split == 0)[0]
    if a.train_frac < 1.0:                       # nested donor subsets: the first k of one fixed permutation
        donors = np.unique(store.donor[tr])
        keep = np.random.default_rng(2026102030).permutation(donors)[:max(1, int(round(a.train_frac*len(donors))))]
        tr = tr[np.isin(store.donor[tr], keep)]
    dv = np.nonzero(store.split == 1)[0]
    dv_eval = np.sort(np.random.default_rng(0).choice(dv, min(len(dv), a.dev_cap), replace=False))
    lease_poll()
    p, sampler = game_sampler(store, tr, a.hog_share, a.max_row_exposure)
    lease_poll()
    iw_all = ((1/len(tr))/p).astype(np.float32)          # natural / sampled probability, mean 1 under sampling
    model = PolicyV1(d=a.d, layers=a.layers, heads=a.heads, ffn=a.ffn, drop=a.drop).to(a.device)
    lease_poll()
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=a.wd)
    amp = (torch.autocast('cuda', dtype=torch.bfloat16) if a.amp == 'bf16' and str(a.device).startswith('cuda')
           else contextlib.nullcontext())
    spe = a.steps_per_epoch or max(1, len(tr)//a.bs)
    total = spe*a.epochs
    wu = a.warmup_steps or spe
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1)/wu) if s < wu else .5*(1 + math.cos(math.pi*(s - wu)/max(1, total - wu))))
    hog_tr = store.hog[tr]
    info = dict(schema='clasher.pretrain_v1.bc-run.v1', seed=a.seed, store=str(a.store), feature_hash=F.feature_hash(),
                params=model.n_params(), cfg=model.cfg, rows=int(store.n), train_rows=int(len(tr)),
                dev_rows=int(len(dv)), dev_eval_rows=int(len(dv_eval)), hog_train_rows=int(hog_tr.sum()),
                sampler=sampler, train_donors=int(len(np.unique(store.donor[tr]))),
                code_sha256={n: hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest()
                             for n in ('train_bc.py', 'model.py', 'featurize.py')},
                steps_per_epoch=spe, args=vars(a))
    phase = 'baseline'
    base, hazard = baseline_nll(store, tr, dv_eval, lease_poll=lease_poll if lease is not None else None)
    info['baseline'] = base
    info['baseline_hazard'] = hazard
    (out/'run.json').write_text(json.dumps(info, indent=1) + '\n')
    print(json.dumps(info), flush=True)
    log = open(out/'log.jsonl', 'a')
    best, bad, step = float('inf'), 0, 0
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(3)
    for ep in range(a.epochs):
        phase = 'training'
        consumed_batches = 0
        lease_poll()
        draws = rng.choice(len(tr), spe*a.bs, p=p)          # row draws whose marginal is the game-balanced p
        batches = [tr[draws[i*a.bs:(i + 1)*a.bs]] for i in range(spe)]
        iws = [iw_all[draws[i*a.bs:(i + 1)*a.bs]] for i in range(spe)]
        futs = [pool.submit(store.batch, batches[i]) for i in range(min(6, spe))]
        t0 = time.time()
        run = np.zeros(4)
        for i in range(spe):
            lease_poll()
            nb = futs[i].result()
            futs[i] = None                                 # release the consumed batch (no per-pass accumulation)
            if i + 6 < spe:
                futs.append(pool.submit(store.batch, batches[i + 6]))
            nb['iw'] = iws[i]
            b = to_torch(nb, a.device, a.drop_ages, rng)
            with amp:
                L = losses(model, b)
                loss, la, lv = objective(L)
            if not torch.isfinite(loss):
                raise SystemExit(f'nonfinite loss at step {step}')
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            step += 1
            consumed_batches = i + 1
            lease_poll()
            run += (loss.item(), la.item(), lv.item(), 1)
            if step % 500 == 0:
                mem = (round(torch.cuda.max_memory_reserved()/2**30, 2) if str(a.device).startswith('cuda') else None)
                print(json.dumps(dict(ep=ep, step=step, loss=run[0]/run[3], actor=run[1]/run[3], value=run[2]/run[3],
                                      lr=sched.get_last_lr()[0], rows_s=round(500*a.bs/(time.time() - t0), 1),
                                      gpu_reserved_gib=mem)),
                      flush=True)
                run[:] = 0
                t0 = time.time()
            if (time.time() - t_start)/3600 > a.max_gpu_hours:
                break
        futs.clear()
        if (ep + 1) % a.eval_every and ep + 1 < a.epochs:
            continue
        phase = 'dev'
        lease_poll()
        with amp:
            ev = evaluate(model, store, dv_eval, a.device, prefix='dev/',
                          lease_poll=lease_poll if lease is not None else None)
        lease_poll()
        ev.update(ep=ep, step=step, wall_h=(time.time() - t_start)/3600)
        log.write(json.dumps(ev) + '\n')
        log.flush()
        print(json.dumps({k: v for k, v in ev.items() if not k.endswith('reliability')}), flush=True)
        torch.save(dict(model=model.state_dict(), cfg=model.cfg, feature_hash=F.feature_hash(), seed=a.seed, ep=ep,
                        dev=ev), out/f'ep{ep:02d}.pt')
        if ev['dev/all/joint_nll'] < best - 1e-4:
            best, bad = ev['dev/all/joint_nll'], 0
            torch.save(dict(model=model.state_dict(), cfg=model.cfg, feature_hash=F.feature_hash(), seed=a.seed,
                            ep=ep, dev=ev), out/'best.pt')
        else:
            bad += 1
            if bad >= a.patience:
                break
        if (time.time() - t_start)/3600 > a.max_gpu_hours:
            break
    phase = 'calibration'
    # Calibration reloads an earlier epoch. Preserve the final training model for lease cancellation.
    if lease is not None:
        completed_training_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    lease_poll()
    # frozen gate intercept on natural-frequency DEV
    ck = torch.load(out/'best.pt', map_location=a.device, weights_only=False)
    model.load_state_dict(ck['model'])
    bias, nll0, nll1 = fit_gate_bias(model, store, dv_eval, a.device, lease_poll=lease_poll if lease is not None else None)
    model.gate_bias.fill_(bias)
    ev = evaluate(model, store, dv_eval, a.device, prefix='dev_cal/',
                  lease_poll=lease_poll if lease is not None else None)
    ck.update(model=model.state_dict(), gate_bias=bias, gate_nll_before=nll0, gate_nll_after=nll1, dev_cal=ev)
    torch.save(ck, out/'best-calibrated.pt')
    summary = dict(best_ep=ck['ep'], best_dev=ck['dev'], gate_bias=bias, gate_bce=[nll0, nll1], dev_cal=ev,
                   baseline=base, wall_h=(time.time() - t_start)/3600,
                   gpu_peak_reserved_gib=(torch.cuda.max_memory_reserved()/2**30
                                          if str(a.device).startswith('cuda') else None))
    lease_poll()
    if pool is not None:
        pool.shutdown(wait=True)
    (out/'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(dict(best_ep=ck['ep'], gate_bias=bias, gate_bce=[nll0, nll1])), flush=True)


if __name__ == '__main__':
    main()
