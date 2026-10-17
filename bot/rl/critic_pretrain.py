"""Pretrain the RL critic on game outcomes of packed ExIt corpora (exploration; reports/bot/rl/, ExIt it9 arm C).

    BOT_GPU_MAX_GB=12 $GPU_PY -B -m bot.rl.critic_pretrain --init IT5S2 --assets A --new PACK [--new PACK ...] \
        --steps 3000 --out DIR [--rollouts RUN/rollouts --ref-state RUN/learner-state.pt]

The RL r3 critic (bot.rl.learner.make_critic: it5s2 trunk + opponent embedding + value head) explained only 0-36%
of the outcome variance after 3 warm-up updates on ~45 k transitions. The packed ExIt corpora hold millions of
states of the same behaviour (it5s2 seats vs v1 / R3a / itself, our engine) with the game outcome of the labelled
seat (recorded_outcome), so the critic can be trained on ~100x more games before PPO starts.

- Rows: every root row of each pack (teacher hits kept; the value target does not use the teacher). Games are split
  train/held-out by bot.exit.train.split_rows (5 %), so held-out rows come from games never trained on.
- Opponent id (training-only critic input, as in RL): bot.exit.generate plays opponent pool[g % len(pool)] in game
  g = seed - base; the packs used here were all generated with --pool v1,R3a,self, so the opponent is
  ('v1', 'R3a', 'self')[g % 3]. 'self' maps to the RL league id of frozen it5s2 only when the behaviour student is
  it5s2 (--self-is-it5s2 PACK...); otherwise the row gets no opponent embedding. The rule is verified against every
  local shard receipt (sources.json) before training; a mismatch aborts.
- Loss: MSE(tanh value, outcome in {-1, 0, 1}); AdamW, warmup then cosine, grad clip 1. The checkpoint with the best
  held-out explained variance is kept as critic-best.pt (state_dict loadable into make_critic).
- --rollouts: also report explained variance on RL actor rollouts (RL-format transitions, MC return = outcome), for
  this critic and for --ref-state's critic (the r3 learner's), on the same games.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

import numpy as np

POOL = ('v1', 'R3a', 'self')


def pack_opponents(path, base, self_is_it5s2):
    """Per-row RL opponent id (-1 = none) of a pack, from g % 3; checked against readable shard receipts."""
    from bot.rl.actor import OPP_IDS
    path = Path(path)
    seeds = np.load(path / 'train' / 'perspective_ids.npy', mmap_mode='r')
    g = np.asarray(seeds, np.int64) - base
    if (g < 0).any():
        raise ValueError(f'{path}: seed below base')
    ids = {name: OPP_IDS.get('it5s2' if name == 'self' else name, -1) for name in POOL}
    if not self_is_it5s2:
        ids['self'] = -1
    opp = np.array([ids[POOL[i]] for i in range(3)], np.int64)[g % 3]
    checked = 0
    for k, src in enumerate(json.loads((path / 'sources.json').read_text())['games']):
        rec = Path(src['path']) / 'receipt.json'
        if not rec.exists():
            continue
        r = json.loads(rec.read_text())
        if r['opponent'] != POOL[(r['seed'] - base) % 3] or r['base'] != base:
            raise ValueError(f'{rec}: opponent {r["opponent"]} breaks the pool rule')
        if self_is_it5s2 and 'it5s2' not in r['student']:
            raise ValueError(f'{rec}: behaviour {r["student"]} is not it5s2')
        checked += 1
    return opp, checked


class ValueGroup:
    """bot.exit.train.Group plus the per-row opponent id and outcome."""

    def __init__(self, stores, positions, opps):
        self.stores, self.positions, self.opps = stores, positions, opps
        self.ends = np.cumsum([len(p) for p in positions])
        self.sizes = np.cumsum([len(s) for s in stores])

    def __len__(self):
        return int(self.ends[-1]) if len(self.ends) else 0

    def batch(self, flat):
        """Rows come back in ascending flat order: combined_batch groups rows by store (its outputs are in store
        order), and the store index is monotone in the flat index, so sorting first keeps the per-row opponent ids
        aligned with the batch (before 2026-10-17 they were in sampling order: misaligned across packs)."""
        import torch
        from exit_r3.teacher_batch import combined_batch
        flat = np.sort(np.asarray(flat, np.int64))
        which = np.searchsorted(self.ends, flat, side='right')
        starts = np.r_[0, self.ends[:-1]]
        local = np.array([self.positions[w][f - starts[w]] for w, f in zip(which, flat)], np.int64)
        sstarts = np.r_[0, self.sizes[:-1]]
        b, y = combined_batch(self.stores, self.sizes, local + sstarts[which])
        rows = np.array([self.stores[w].root_indices[p] for w, p in zip(which, local)], np.int64)
        opp = np.array([self.opps[w][r] for w, r in zip(which, rows)], np.int64)
        return b, dict(outcome=y['outcome'].float(), opp=torch.from_numpy(opp))


class Steps:
    def __init__(self, group, batch, seed, steps):
        self.group, self.batch, self.seed, self.steps = group, batch, seed, steps

    def __len__(self):
        return self.steps

    def __getitem__(self, s):
        rng = np.random.default_rng(np.random.SeedSequence([self.seed, s]))
        return s, self.group.batch(rng.integers(len(self.group), size=self.batch))


def value(critic, b, opp):
    """make_critic's forward, with no opponent embedding for opp < 0."""
    import torch
    x = critic.trunk.encode(b)[:, 0]
    has = (opp >= 0)
    x = x + critic.opp(opp.clamp_min(0)) * has[:, None].to(x.dtype)
    return torch.tanh(critic.head(x)).squeeze(-1)


def explained(pred, target):
    pred, target = np.asarray(pred, float), np.asarray(target, float)
    return float(1 - np.var(target - pred) / max(1e-12, np.var(target)))


def evaluate(critic, group, device, microbatch, chunk=4096, rows=60000):
    import torch
    n = len(group)
    idx = np.arange(n) if n <= rows else np.random.default_rng(0).choice(n, rows, replace=False)
    preds, ys = [], []
    critic.eval()
    with torch.no_grad():
        for start in range(0, len(idx), chunk):
            b, y = group.batch(idx[start:start + chunk])
            for m in range(0, len(y['outcome']), microbatch):
                bb = {k: v[m:m + microbatch].to(device) for k, v in b.items()}
                with torch.autocast('cuda', dtype=torch.bfloat16, enabled=device.type == 'cuda'):
                    preds.append(value(critic, bb, y['opp'][m:m + microbatch].to(device)).float().cpu().numpy())
            ys.append(y['outcome'].numpy())
    p, t = np.concatenate(preds), np.concatenate(ys)
    return dict(rows=int(len(t)), mse=float(np.mean((p - t) ** 2)), explained_var=explained(p, t),
                mean_outcome=float(t.mean()))


def rollout_ev(critics, files, device, microbatch=512):
    """Explained variance of each critic on RL rollouts (MC return = outcome), with the RL opponent ids."""
    import torch
    from bot.rl.learner import load_games, collate, to_dev
    games = load_games(files)
    if not games:
        return {}
    t = collate(games)
    out = {}
    for name, c in critics.items():
        c.eval()
        vals = np.zeros(len(t['x_ntok']), np.float32)
        with torch.no_grad():
            for s in range(0, len(vals), microbatch):
                idx = np.arange(s, min(len(vals), s + microbatch))
                b, x = to_dev(t, idx, device)
                vals[idx] = value(c, b, x['opp']).float().cpu().numpy()
        ret = t['x_outcome']
        by_opp = {}
        from bot.rl.actor import LEAGUE
        for i, (opp, _) in enumerate(LEAGUE):
            m = t['x_opp'] == i
            if m.sum() > 100:
                by_opp[opp] = round(explained(vals[m], ret[m]), 4)
        out[name] = dict(games=len(games), transitions=int(len(vals)), explained_var=explained(vals, ret),
                         mse=float(np.mean((vals - ret) ** 2)), by_opponent=by_opp)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--init', required=True)
    ap.add_argument('--assets', required=True)
    ap.add_argument('--new', action='append', required=True)
    ap.add_argument('--self-is-it5s2', nargs='*', default=None,
                    help="packs whose behaviour is it5s2 ('self' opponent = frozen it5s2); default: all --new")
    ap.add_argument('--base', type=int, default=874184153281168)
    ap.add_argument('--heldout', type=float, default=.05)
    ap.add_argument('--steps', type=int, default=3000)
    ap.add_argument('--batch', type=int, default=4096)
    ap.add_argument('--microbatch', type=int, default=1024)
    ap.add_argument('--lr', type=float, default=1e-4)
    ap.add_argument('--warmup', type=int, default=100)
    ap.add_argument('--weight-decay', type=float, default=.01)
    ap.add_argument('--eval-every', type=int, default=250)
    ap.add_argument('--seed', type=int, default=2026101590)
    ap.add_argument('--loader-workers', type=int, default=6)
    ap.add_argument('--eval-rows', type=int, default=60000, help='held-out rows per evaluation (fixed sample)')
    ap.add_argument('--rollouts', type=Path, help='RL rollout dir (v*.npz) for the RL-format explained variance')
    ap.add_argument('--ref-state', type=Path, help='learner-state.pt whose critic is the reference')
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args(argv)
    from bot.exit.train import bootstrap, make_stores, split_rows, sha
    bootstrap()
    import torch
    from bot.rl.learner import make_critic
    from exit_r3.student import initialize_root
    a.out.mkdir(parents=True, exist_ok=True)
    if (a.out / 'critic-best.pt').exists():
        raise ValueError('fresh output dir required')
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    device = torch.device(a.device)
    if device.type == 'cuda' and os.environ.get('BOT_GPU_MAX_GB'):
        total = torch.cuda.get_device_properties(0).total_memory
        torch.cuda.set_per_process_memory_fraction(min(1., float(os.environ['BOT_GPU_MAX_GB']) * 2**30 / total), 0)
    selfs = set(a.new if a.self_is_it5s2 is None else a.self_is_it5s2)
    stores = make_stores(a.new, a.assets, keep_hits=True)
    opps, receipts = [], 0
    for p in a.new:
        o, c = pack_opponents(p, a.base, p in selfs)
        opps.append(o); receipts += c
    splits = [split_rows(s, a.heldout) for s in stores]
    train = ValueGroup(stores, [tr for tr, _ in splits], opps)
    held = ValueGroup(stores, [ho for _, ho in splits], opps)
    _, cfg = initialize_root(a.init)
    critic = make_critic(a.init, cfg.width).to(device)
    files = sorted(a.rollouts.glob('v*.npz')) if a.rollouts else []
    ref = None
    if a.ref_state:
        ref = make_critic(a.init, cfg.width).to(device)
        ref.load_state_dict(torch.load(a.ref_state, map_location=device, weights_only=False)['critic'])
    info = dict(args={k: str(v) for k, v in vars(a).items()}, init_sha256=sha(a.init), rows_train=len(train),
                rows_heldout=len(held), receipts_checked=receipts, rollout_files=len(files),
                manifests=[sha(Path(p) / 'manifest.json') for p in a.new])
    (a.out / 'inputs.json').write_text(json.dumps(info, indent=2))
    print(json.dumps(info), flush=True)
    log = open(a.out / 'train.jsonl', 'a', buffering=1)
    m0 = dict(step=0, heldout=evaluate(critic, held, device, a.microbatch, rows=a.eval_rows))
    if files:
        m0['rollouts'] = rollout_ev(dict(pretrain=critic, **({'r3': ref} if ref is not None else {})), files, device)
    log.write(json.dumps(m0) + '\n'); print(json.dumps(m0), flush=True)
    opt = torch.optim.AdamW(critic.parameters(), lr=a.lr, weight_decay=a.weight_decay)

    def lr_at(s):
        if s < a.warmup:
            return (s + 1) / a.warmup
        return .5 * (1 + math.cos(math.pi * min(1., (s - a.warmup) / max(1, a.steps - a.warmup))))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_at)
    loader = torch.utils.data.DataLoader(Steps(train, a.batch, a.seed, a.steps), batch_size=None, shuffle=False,
                                         num_workers=a.loader_workers,
                                         prefetch_factor=4 if a.loader_workers else None)
    best, t0 = -1e9, time.time()
    critic.train()
    for s, (b, y) in loader:
        opt.zero_grad(set_to_none=True)
        n, total = len(y['outcome']), 0.
        for m in range(0, n, a.microbatch):
            bb = {k: v[m:m + a.microbatch].to(device, non_blocking=True) for k, v in b.items()}
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=device.type == 'cuda'):
                v = value(critic, bb, y['opp'][m:m + a.microbatch].to(device))
            loss = ((v.float() - y['outcome'][m:m + a.microbatch].to(device)) ** 2).sum() / n
            loss.backward()
            total += float(loss.detach())
        grad = torch.nn.utils.clip_grad_norm_(critic.parameters(), 1., error_if_nonfinite=True)
        opt.step(); sched.step()
        step = s + 1
        rec = dict(step=step, loss=total, grad=float(grad), lr=sched.get_last_lr()[0], wall=time.time() - t0)
        log.write(json.dumps(rec) + '\n')
        if step % 25 == 0:
            print(json.dumps(rec), flush=True)
        if step % a.eval_every == 0 or step == a.steps:
            m = dict(step=step, heldout=evaluate(critic, held, device, a.microbatch, rows=a.eval_rows))
            if files:
                m['rollouts'] = rollout_ev(dict(pretrain=critic), files, device)
            critic.train()
            if m['heldout']['explained_var'] > best:
                best = m['heldout']['explained_var']
                torch.save(critic.state_dict(), a.out / 'critic-best.pt.partial')
                os.replace(a.out / 'critic-best.pt.partial', a.out / 'critic-best.pt')
                m['saved'] = 'critic-best.pt'
            log.write(json.dumps(m) + '\n'); print(json.dumps(m), flush=True)
    torch.save(critic.state_dict(), a.out / 'critic-last.pt')
    (a.out / 'complete.json').write_text(json.dumps(dict(steps=a.steps, best_heldout_ev=best, wall=time.time() - t0)))


if __name__ == '__main__':
    main()
