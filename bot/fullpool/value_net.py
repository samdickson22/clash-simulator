"""Value-net v0: a learned state value on the student encoder, short-horizon margin targets (exploration; plan step 2).

    BOT_GPU_MAX_GB=20 $GPU_PY -B -m bot.fullpool.value_net --init EXT/rl5-v10-fp.pt --assets A \
        --pack G1PACK [--pack ...] --pack C56PACK [...] --steps 6000 --out DIR

Rows: every root row of each teacher-v6 pack (G1 full-pool games and the C56 kc7a corpus). The labelled seat's
fair state is the v5 packet the student reads (hand, elixir, cycle, board, revealed opponent cards, exact
opponent elixir); outcomes and future margins appear only as targets.

Margin m(row) = (own - enemy crowns)/3 + (own - enemy tower HP)/15000, from the packet's tower fractions
(princess 3052, king 4824 HP at level 11; crowns = destroyed towers, king = 3), the live-diag units
(bot/livediag/dumpbank_fit.py). Targets per row, within the row's own game (perspective_ids, episode_ids):
- d15 / d30 / d60: m(first row at tick >= t + 300 / 600 / 1200) - m(row). If the game ends first, the end margin is
  m(last row), plus outcome/3 when the last row's crown difference does not already agree with the outcome (the
  deciding tower fell after the last labelled row); a draw adds nothing.
- outcome in {-1, 0, 1} (recorded_outcome).
Model: the init trunk (initialize_root) + a GELU head with 4 outputs [d15, d30, d60, outcome]; loss = MSE on
the margin heads in target-std units (weights .5 / 1 / .5) + .5 * MSE(tanh outcome). AdamW, warmup + cosine.
Split by game (bot.exit.train.split_rows, 5 %): held-out rows come from games never trained on.
Each evaluation reports, per head and per pack kind (g1 / c56), the held-out Pearson correlation and explained
variance, and the elixir sanity checks: the mean change of the d30 / outcome predictions for +1 own elixir and
+1 opponent elixir on the same held-out rows (expected > 0 and < 0).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

import numpy as np

HEADS = ('d15', 'd30', 'd60', 'outcome')
HORIZONS = dict(d15=300, d30=600, d60=1200)
LOSS_W = dict(d15=.5, d30=1., d60=.5, outcome=.5)
PRINCESS, KING, HP_UNIT = 3052., 4824., 15000.


def margin(gf):
    """(own - enemy crowns)/3 + (own - enemy tower HP)/15000 from global_features columns 8..13."""
    gf = np.asarray(gf, np.float64)
    own, opp = gf[:, 8:11], gf[:, 11:14]

    def crowns(t):
        c = (t[:, 0] <= 0).astype(float) + (t[:, 1] <= 0)
        return np.where(t[:, 2] <= 0, 3., c)
    hp = lambda t: PRINCESS * (t[:, 0] + t[:, 1]) + KING * t[:, 2]
    return (crowns(opp) - crowns(own)) / 3 + (hp(own) - hp(opp)) / HP_UNIT, crowns(opp) - crowns(own)


def targets(arrays):
    """Per pack row: dict(d15, d30, d60, outcome) float32 arrays (all rows of the pack)."""
    seed = np.asarray(arrays['perspective_ids'], np.int64)
    ep = np.asarray(arrays['episode_ids'], np.int64)
    tick = np.asarray(arrays['submitted_ticks'], np.int64)
    out = np.asarray(arrays['recorded_outcome'], np.float64)
    m, cd = margin(arrays['global_features'])
    _, gid = np.unique(np.stack([seed, ep], 1), axis=0, return_inverse=True)
    gid = gid.reshape(-1).astype(np.int64)
    order = np.lexsort((tick, gid))
    key = gid[order] * 10_000_000 + tick[order]
    g_sorted = gid[order]
    last = np.r_[np.flatnonzero(np.diff(g_sorted)), len(order) - 1]       # last sorted position per game
    last_of = np.empty(int(gid.max()) + 1, np.int64)
    last_of[g_sorted[last]] = order[last]
    lr = last_of[gid]                                                      # each row's game's last row
    agree = np.sign(cd[lr]) == np.sign(out[lr])
    m_end = m[lr] + np.where(agree | (out[lr] == 0), 0., out[lr] / 3)
    res = dict(outcome=out.astype(np.float32))
    for name, h in HORIZONS.items():
        j = np.searchsorted(key, gid * 10_000_000 + tick + h, side='left')
        inside = j < len(order)
        jj = np.where(inside, j, 0)
        inside &= g_sorted[jj] == gid
        fut = np.where(inside, m[order[jj]], m_end)
        res[name] = (fut - m).astype(np.float32)
    res['horizon_inside_d30'] = None   # filled below (share of rows whose +30 s point is inside the game)
    j = np.searchsorted(key, gid * 10_000_000 + tick + 600, side='left')
    res['horizon_inside_d30'] = float(np.mean((j < len(order)) & (g_sorted[np.minimum(j, len(order) - 1)] == gid)))
    return res


class Shift:
    """arrays[...] view adding `delta` to one column (or the whole 1-d array) on read, clipped to [lo, hi]."""

    def __init__(self, base, delta, col=None, lo=0., hi=1.):
        self.base, self.delta, self.col, self.lo, self.hi = base, delta, col, lo, hi
        self.shape, self.dtype = base.shape, base.dtype

    def __len__(self):
        return len(self.base)

    def __getitem__(self, key):
        first, rest = (key[0], key[1:]) if isinstance(key, tuple) else (key, ())
        a = np.array(self.base[first], copy=True)
        if self.col is None:
            a = np.clip(a + self.delta, self.lo, self.hi).astype(self.dtype)
        else:
            a[..., self.col] = np.clip(a[..., self.col] + self.delta, self.lo, self.hi)
        return a[(slice(None),) + rest] if rest else a


class VGroup:
    """Stores sampled uniformly over their selected root rows, with per-row targets."""

    def __init__(self, stores, positions, tg):
        self.stores, self.positions, self.tg = stores, positions, tg
        self.ends = np.cumsum([len(p) for p in positions])
        self.sizes = np.cumsum([len(s) for s in stores])

    def __len__(self):
        return int(self.ends[-1]) if len(self.ends) else 0

    def batch(self, flat):
        """Rows come back in ascending flat order: combined_batch groups rows by store, and the store index is
        monotone in the flat index, so sorting first keeps inputs and targets aligned."""
        import torch
        from exit_r3.teacher_batch import combined_batch
        flat = np.sort(np.asarray(flat, np.int64))
        which = np.searchsorted(self.ends, flat, side='right')
        starts = np.r_[0, self.ends[:-1]]
        local = np.array([self.positions[w][f - starts[w]] for w, f in zip(which, flat)], np.int64)
        sstarts = np.r_[0, self.sizes[:-1]]
        b, _ = combined_batch(self.stores, self.sizes, local + sstarts[which])
        rows = np.array([self.stores[w].root_indices[p] for w, p in zip(which, local)], np.int64)
        y = np.stack([np.array([self.tg[w][h][r] for w, r in zip(which, rows)], np.float32) for h in HEADS], 1)
        return b, torch.from_numpy(y)


class Steps:
    def __init__(self, group, batch, seed, steps):
        self.group, self.batch, self.seed, self.steps = group, batch, seed, steps

    def __len__(self):
        return self.steps

    def __getitem__(self, s):
        rng = np.random.default_rng(np.random.SeedSequence([self.seed, s]))
        return s, self.group.batch(rng.integers(len(self.group), size=self.batch))


def make_net(init, width):
    import torch
    from torch import nn
    from exit_r3.student import initialize_root

    class ValueNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.trunk, _ = initialize_root(init)
            self.head = nn.Sequential(nn.Linear(width, width), nn.GELU(), nn.Linear(width, len(HEADS)))

        def forward(self, b):
            out = self.head(self.trunk.encode(b)[:, 0])
            return torch.cat([out[:, :3], torch.tanh(out[:, 3:])], 1)
    return ValueNet()


def predict(net, group, idx, device, microbatch, chunk=4096):
    import torch
    preds, ys = [], []
    net.eval()
    with torch.no_grad():
        for start in range(0, len(idx), chunk):
            b, y = group.batch(idx[start:start + chunk])
            for m in range(0, len(y), microbatch):
                bb = {k: v[m:m + microbatch].to(device) for k, v in b.items()}
                with torch.autocast('cuda', dtype=torch.bfloat16, enabled=device.type == 'cuda'):
                    preds.append(net(bb).float().cpu().numpy())
            ys.append(y.numpy())
    return np.concatenate(preds), np.concatenate(ys)


def stats(p, t):
    out = {}
    for k, h in enumerate(HEADS):
        a, b = p[:, k].astype(float), t[:, k].astype(float)
        c = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else None
        out[h] = dict(corr=None if c is None else round(c, 4),
                      ev=round(float(1 - np.var(b - a) / max(1e-12, np.var(b))), 4), mean_target=round(float(b.mean()), 4))
    return out


def evaluate(net, held, kinds, device, microbatch, rows, elixir_rows):
    """Held-out metrics overall / per pack kind / by time bucket + the elixir sensitivity checks."""
    n = len(held)
    idx = np.arange(n) if n <= rows else np.sort(np.random.default_rng(0).choice(n, rows, replace=False))
    p, t = predict(net, held, idx, device, microbatch)
    which = np.searchsorted(held.ends, idx, side='right')
    res = dict(rows=int(len(idx)), all=stats(p, t))
    for kind in sorted(set(kinds)):
        m = np.isin(which, [w for w, k in enumerate(kinds) if k == kind])
        if m.sum() > 100:
            res[kind] = stats(p[m], t[m])
    # time buckets from the packet's battle_progress (global_features[:, 0])
    prog = np.array([held.stores[w].arrays['global_features'][held.stores[w].root_indices[
        held.positions[w][f - (held.ends[w - 1] if w else 0)]], 0] for w, f in zip(which, idx)])
    for lo, hi, name in ((0, .33, 'early'), (.33, .67, 'mid'), (.67, 9, 'late_ot')):
        m = (prog >= lo) & (prog < hi)
        if m.sum() > 100:
            res[f'time_{name}'] = {h: v['corr'] for h, v in stats(p[m], t[m]).items()}
    sub = np.sort(np.random.default_rng(1).choice(idx, min(elixir_rows, len(idx)), replace=False))
    base = p[np.searchsorted(idx, sub)]
    sens = {}
    for name, key, delta, col, hi in (('own_elixir_plus1', 'global_features', .1, 5, 1.),
                                      ('opp_elixir_plus1', 'opp_elixir', 1., None, 10.)):
        saved = [s.arrays[key] for s in held.stores]
        try:
            for s in held.stores:
                s.arrays[key] = Shift(s.arrays[key], delta, col, 0., hi)
            q, _ = predict(net, held, sub, device, microbatch)
        finally:
            for s, a in zip(held.stores, saved):
                s.arrays[key] = a
        d = q - base
        sens[name] = {h: dict(mean=round(float(d[:, k].mean()), 5), share_pos=round(float((d[:, k] > 0).mean()), 3))
                      for k, h in enumerate(HEADS)}
    res['elixir_sensitivity'] = dict(rows=int(len(sub)), **sens)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--init', required=True)
    ap.add_argument('--assets', required=True)
    ap.add_argument('--pack', action='append', required=True)
    ap.add_argument('--heldout', type=float, default=.05)
    ap.add_argument('--steps', type=int, default=6000)
    ap.add_argument('--batch', type=int, default=4096)
    ap.add_argument('--microbatch', type=int, default=1024)
    ap.add_argument('--lr', type=float, default=1e-4)
    ap.add_argument('--warmup', type=int, default=200)
    ap.add_argument('--weight-decay', type=float, default=.01)
    ap.add_argument('--eval-every', type=int, default=500)
    ap.add_argument('--eval-rows', type=int, default=60000)
    ap.add_argument('--elixir-rows', type=int, default=8192)
    ap.add_argument('--main-head', default='d30', choices=HEADS, help='checkpoint selection: best held-out corr')
    ap.add_argument('--seed', type=int, default=2026101701)
    ap.add_argument('--loader-workers', type=int, default=6)
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args(argv)
    from bot.exit.train import bootstrap, make_stores, split_rows, sha
    bootstrap()
    import torch
    from exit_r3.student import initialize_root
    a.out.mkdir(parents=True, exist_ok=True)
    if (a.out / 'value-best.pt').exists():
        raise ValueError('fresh output dir required')
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    device = torch.device(a.device)
    if device.type == 'cuda' and os.environ.get('BOT_GPU_MAX_GB'):
        total = torch.cuda.get_device_properties(0).total_memory
        torch.cuda.set_per_process_memory_fraction(min(1., float(os.environ['BOT_GPU_MAX_GB']) * 2**30 / total), 0)
    stores = make_stores(a.pack, a.assets, keep_hits=True)
    kinds = ['c56' if 'kc7a' in Path(p).name else 'g1' for p in a.pack]
    tg, tinfo = [], []
    for p, s in zip(a.pack, stores):
        t0 = time.time()
        t = targets(s.arrays)
        inside = t.pop('horizon_inside_d30')
        tg.append(t)
        r = s.root_indices
        tinfo.append(dict(pack=p, rows=int(len(r)), d30_inside_share=round(inside, 4), seconds=round(time.time() - t0, 1),
                          **{f'{h}_mean': round(float(t[h][r].mean()), 4) for h in HEADS},
                          **{f'{h}_std': round(float(t[h][r].std()), 4) for h in HEADS}))
        print(json.dumps(tinfo[-1]), flush=True)
    splits = [split_rows(s, a.heldout) for s in stores]
    train = VGroup(stores, [tr for tr, _ in splits], tg)
    held = VGroup(stores, [ho for _, ho in splits], tg)
    scale = np.array([max(1e-6, float(np.std(np.concatenate([t[h][s.root_indices[tr]] for t, s, (tr, _) in
                                                              zip(tg, stores, splits)])))) for h in HEADS], np.float32)
    scale[HEADS.index('outcome')] = 1.
    _, cfg = initialize_root(a.init)
    net = make_net(a.init, cfg.width).to(device)
    info = dict(args={k: str(v) for k, v in vars(a).items()}, init_sha256=sha(a.init), rows_train=len(train),
                rows_heldout=len(held), target_scale=dict(zip(HEADS, scale.tolist())), targets=tinfo,
                manifests=[sha(Path(p) / 'manifest.json') for p in a.pack], kinds=kinds)
    (a.out / 'inputs.json').write_text(json.dumps(info, indent=2))
    print(json.dumps(info), flush=True)
    log = open(a.out / 'train.jsonl', 'a', buffering=1)
    w = torch.tensor([LOSS_W[h] for h in HEADS], device=device)
    sc = torch.from_numpy(scale).to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=a.weight_decay)

    def lr_at(s):
        if s < a.warmup:
            return (s + 1) / a.warmup
        return .5 * (1 + math.cos(math.pi * min(1., (s - a.warmup) / max(1, a.steps - a.warmup))))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_at)
    loader = torch.utils.data.DataLoader(Steps(train, a.batch, a.seed, a.steps), batch_size=None, shuffle=False,
                                         num_workers=a.loader_workers, prefetch_factor=4 if a.loader_workers else None)
    best, t0 = -1e9, time.time()
    k_main = HEADS.index(a.main_head)

    def checkpoint(step, tag):
        m = dict(step=step, heldout=evaluate(net, held, kinds, device, a.microbatch, a.eval_rows, a.elixir_rows),
                 wall=time.time() - t0)
        net.train()
        nonlocal best
        c = m['heldout']['all'][a.main_head]['corr'] or -1
        if tag != 'init' and c > best:
            best = c
            torch.save(dict(state=net.state_dict(), heads=HEADS, scale=scale.tolist(), init=a.init, step=step),
                       a.out / 'value-best.pt.partial')
            os.replace(a.out / 'value-best.pt.partial', a.out / 'value-best.pt')
            m['saved'] = 'value-best.pt'
        log.write(json.dumps(m) + '\n'); print(json.dumps(m), flush=True)
    checkpoint(0, 'init')
    net.train()
    for s, (b, y) in loader:
        opt.zero_grad(set_to_none=True)
        n, total = len(y), 0.
        for m in range(0, n, a.microbatch):
            bb = {k: v[m:m + a.microbatch].to(device, non_blocking=True) for k, v in b.items()}
            yy = y[m:m + a.microbatch].to(device)
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=device.type == 'cuda'):
                v = net(bb)
            loss = ((((v.float() - yy) / sc) ** 2) * w).sum() / n
            loss.backward()
            total += float(loss.detach())
        grad = torch.nn.utils.clip_grad_norm_(net.parameters(), 1., error_if_nonfinite=True)
        opt.step(); sched.step()
        step = s + 1
        rec = dict(step=step, loss=total, grad=float(grad), lr=sched.get_last_lr()[0], wall=time.time() - t0)
        log.write(json.dumps(rec) + '\n')
        if step % 25 == 0:
            print(json.dumps(rec), flush=True)
        if step % a.eval_every == 0 or step == a.steps:
            checkpoint(step, 'step')
    torch.save(dict(state=net.state_dict(), heads=HEADS, scale=scale.tolist(), init=a.init, step=a.steps),
               a.out / 'value-last.pt')
    (a.out / 'complete.json').write_text(json.dumps(dict(steps=a.steps, best_heldout_corr=best, main_head=a.main_head,
                                                         wall=time.time() - t0)))


if __name__ == '__main__':
    main()
