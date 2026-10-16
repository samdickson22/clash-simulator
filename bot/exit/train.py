"""ExIt student refit on GPU: warm start from a student checkpoint, R3 root-target loss, recalibrated gate.

    python -m bot.exit.train --init R3a.pt --assets assets.npz --new PACKED [--new PACKED2 ...] \
        [--old /mpac/.../exit-r2-20261010-r1/corpus --new-ratio 0.5] --steps 1000 --out DIR

Data: sealed teacher-v6 corpora (bot.exit.generate shards packed with imitation.exit_r1.pack, and
optionally R3a's own r1 corpus read-only). Only ROOT decisions train (exit_r3 RootTeacherStore:
teacher_root, wait kind 0, completed scores); ExIt rows with a budget cut (teacher_hit) are
dropped unless --keep-hits. Games are split train/heldout by a hash of (episode, seed) so the
held-out rows never train.

Loss: exit_r3.student.teacher_loss at T=0.003, play weight 1, per-batch gate/play denominators,
i.e. R3a's recipe (softmax over the teacher's complete 3-style root scores; timed waits fold
into WAIT). AdamW, linear warmup then cosine, grad clip 1, EMA of the weights (saved as 'ema',
which is what proposals.load_student serves).

Calibration: threshold on held-out ExIt rows so the student's play rate equals the teacher's
play rate on those (student-visited) states (proposals.calibrate). Written next to every
checkpoint as <ckpt>.calibration.json, so 'student:<ckpt>' works in bot.eval.headline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

RUNTIME = Path(os.environ.get('CLASHER_BOT_RUNTIME', '/mpac/sdicks02/repos/clasher-bot-runtime/r1'))


def bootstrap():
    for p in (RUNTIME / 'reports/explore/s1', RUNTIME / 'student-source', RUNTIME / 'src', RUNTIME):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    sys.dont_write_bytecode = True


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def split_rows(store, heldout_fraction, salt='bot-exit-heldout'):
    """(train, heldout) positions into store.root_indices, split by source game."""
    rows = store.root_indices
    ep = np.asarray(store.arrays['episode_ids'][rows]).astype(np.int64)
    seed = np.asarray(store.arrays['perspective_ids'][rows]).astype(np.int64)
    keys = np.unique(np.stack([ep, seed], 1), axis=0)
    held = set()
    for e, s in keys:
        h = int.from_bytes(hashlib.sha256(f'{salt}|{s}|{e}'.encode()).digest()[:8], 'big') / 2**64
        if h < heldout_fraction:
            held.add((int(e), int(s)))
    mask = np.array([(int(e), int(s)) in held for e, s in zip(ep, seed)], bool)
    return np.flatnonzero(~mask), np.flatnonzero(mask)


def make_stores(paths, assets, keep_hits):
    from exit_r3.student import RootTeacherStore
    stores = []
    for p in paths:
        s = RootTeacherStore(p, assets)
        if not keep_hits and 'teacher_hit' in s.arrays:
            s.root_indices = s.root_indices[~np.asarray(s.arrays['teacher_hit'][s.root_indices]).astype(bool)]
        stores.append(s)
    return stores


class Group:
    """Several stores, sampled uniformly over their (selected) root rows."""

    def __init__(self, stores, positions):
        self.stores, self.positions = stores, positions
        self.ends = np.cumsum([len(p) for p in positions])

    def __len__(self):
        return int(self.ends[-1]) if len(self.ends) else 0

    def batch(self, flat):
        from exit_r3.teacher_batch import combined_batch
        which = np.searchsorted(self.ends, flat, side='right')
        starts = np.r_[0, self.ends[:-1]]
        local = np.array([self.positions[w][f - starts[w]] for w, f in zip(which, flat)], np.int64)
        # combined_batch indexes shards by global position over len(store); map to store positions.
        sizes = np.cumsum([len(s) for s in self.stores])
        sstarts = np.r_[0, sizes[:-1]]
        return combined_batch(self.stores, sizes, local + sstarts[which])


def concat(parts):
    from exit_r3.teacher_batch import combined_batch  # noqa: F401  (same padding rules)
    import torch
    parts = [p for p in parts if p is not None]
    if len(parts) == 1:
        return parts[0]
    bw = max(b['ids'].shape[1] for b, _ in parts)
    rw = max(y['root_actions'].shape[1] for _, y in parts)

    def pad(v, width, fill=0):
        if v.shape[1] == width:
            return v
        dest = torch.full((v.shape[0], width, *v.shape[2:]), fill, dtype=v.dtype)
        dest[:, :v.shape[1]] = v
        return dest
    b = {k: torch.cat([pad(bb[k], bw) if k in ('ids', 'types', 'numeric', 'valid') else bb[k]
                       for bb, _ in parts]) for k in parts[0][0]}
    y = {k: torch.cat([pad(yy[k], rw, 2304 if k == 'root_actions' else 0) if k.startswith('root_') else yy[k]
                       for _, yy in parts]) for k in parts[0][1]}
    return b, y


class StepBatches:
    """Deterministic per-step mixed batches (torch Dataset over step numbers; fork workers share mmaps)."""

    def __init__(self, new, old, batch, ratio, seed, start, steps):
        self.new, self.old, self.batch, self.ratio = new, old, batch, ratio
        self.seed, self.start, self.steps = seed, start, steps

    def __len__(self):
        return self.steps - self.start

    def __getitem__(self, i):
        s = self.start + i
        rng = np.random.default_rng(np.random.SeedSequence([self.seed, s]))
        nn = self.batch if self.old is None else round(self.batch * self.ratio)
        parts = [self.new.batch(rng.integers(len(self.new), size=nn))]
        if self.old is not None and self.batch - nn:
            parts.append(self.old.batch(rng.integers(len(self.old), size=self.batch - nn)))
        return s, concat(parts)


def forward_loss(model, b, y, device, microbatch, temperature, dens=None):
    import torch
    from exit_r3.student import teacher_loss, teacher_targets
    w = y['weight'].float() * y['supervised'].float()
    q = teacher_targets(y, temperature)
    gate_den = float(w.sum()) if dens is None else dens[0]
    play_den = float((w * (q * (y['root_actions'] < 2304)).sum(-1)).sum()) if dens is None else dens[1]
    total = 0.
    for start in range(0, len(y['action']), microbatch):
        bb = {k: v[start:start + microbatch].to(device, non_blocking=True) for k, v in b.items()}
        yy = {k: v[start:start + microbatch].to(device, non_blocking=True) for k, v in y.items()}
        with torch.autocast('cuda', dtype=torch.bfloat16, enabled=device.type == 'cuda'):
            o = model(bb, torch.empty(0, dtype=torch.long, device=device))
            loss = teacher_loss(o, yy, temperature, 1., 0., denominators=(gate_den, play_den))
        if model.training:
            loss.backward()
        total += float(loss.detach())
    return total


def evaluate(model, group, device, microbatch=1024, chunk=4096, temperature=.003, threshold=None):
    """Held-out metrics + the arrays needed for calibration."""
    import torch
    from exit_r3.network import masked_log_softmax
    model.eval()
    probs, legal, tplay, tact, best, ces, ns = [], [], [], [], [], [], []
    with torch.no_grad():
        for start in range(0, len(group), chunk):
            flat = np.arange(start, min(len(group), start + chunk))
            b, y = group.batch(flat)
            ces.append(forward_loss(model, b, y, device, microbatch, temperature)); ns.append(len(flat))
            for s2 in range(0, len(flat), microbatch):
                bb = {k: v[s2:s2 + microbatch].to(device) for k, v in b.items()}
                # fp32 (no autocast, TF32 off): P(play) must match CPU serving for calibration.
                raw = model(bb, torch.empty(0, dtype=torch.long, device=device))
                gate = masked_log_softmax(raw['gate'].float(), raw['gate_mask']).exp()[:, 1]
                card = masked_log_softmax(raw['card'].float(), raw['card_mask'])
                tile = masked_log_softmax(raw['tile'].float(), raw['tile_mask'])
                joint = (card[:, :, None] + tile).flatten(1)
                joint = joint.masked_fill(~bb['action_mask'][:, :2304], -torch.inf)
                probs.append(gate.cpu().numpy()); best.append(joint.argmax(1).cpu().numpy())
                legal.append(bb['action_mask'][:, :2304].any(1).cpu().numpy())
            a = y['action'].numpy().astype(np.int64)
            tact.append(a); tplay.append(a < 2304)
    p, lg, tp, ta, bs = map(np.concatenate, (probs, legal, tplay, tact, best))
    model.train()
    from proposals import calibrate
    target = float(tp.mean())
    thr = calibrate(p, lg, target) if threshold is None else threshold
    sp = lg & (p >= thr)
    decision = np.where(sp, bs, 2304)
    plays = tp.sum()
    return dict(rows=int(len(p)), loss=float(np.dot(ces, ns) / np.sum(ns)), teacher_play_rate=target,
                threshold=float(thr), student_play_rate=float(sp.mean()),
                gate_acc=float((sp == tp).mean()), play_recall=float((sp & tp).sum() / max(1, plays)),
                play_precision=float((sp & tp).sum() / max(1, sp.sum())),
                top1_on_teacher_plays=float((bs[tp] == ta[tp]).mean()) if plays else None,
                decision_agree=float((decision == ta).mean()),
                gate_acc_at_half=float(((lg & (p >= .5)) == tp).mean()))


def grow(model, cfg, layers, ffn):
    """Function-preserving growth of an R3 SetPolicy: wider FFNs and extra blocks.

    New FFN hidden units get default-initialised input weights and ZERO output weights; new blocks get
    zero attention-output and FFN-output projections, i.e. identity residual branches. The grown model
    therefore computes exactly the initial student's function (checked by the caller).
    """
    import torch
    from dataclasses import replace
    from exit_r3.network import SetPolicy
    new_cfg = replace(cfg, layers=max(layers or cfg.layers, cfg.layers), ffn=max(ffn or cfg.ffn, cfg.ffn))
    big = SetPolicy(new_cfg, model.descriptors.cpu(), model.tile_features.cpu(), model.costs.cpu())
    old = model.state_dict()
    with torch.no_grad():
        for k, v in big.state_dict().items():
            if k in old:
                src = old[k]
                if src.shape == v.shape:
                    v.copy_(src)
                elif k.endswith('ffn.0.weight'):        # [ffn, width]: copy leading rows
                    v[:src.shape[0]] = src
                elif k.endswith('ffn.0.bias'):
                    v[:src.shape[0]] = src
                elif k.endswith('ffn.3.weight'):        # [width, ffn]: copy leading cols, zero the rest
                    v.zero_(); v[:, :src.shape[1]] = src
                else:
                    raise ValueError(f'cannot grow {k}: {tuple(src.shape)} -> {tuple(v.shape)}')
            elif k.startswith('blocks.'):
                if k.endswith(('attn.out.weight', 'attn.out.bias', 'ffn.3.weight', 'ffn.3.bias')):
                    v.zero_()
            else:
                raise ValueError(f'unexpected new parameter {k}')
    return big, new_cfg


def check_grown(small, big, a):
    """The grown model must reproduce the initial student on real rows (eval mode, fp32, CPU)."""
    import torch
    from exit_r3.student import RootTeacherStore
    store = RootTeacherStore(a.new[0], a.assets)
    b, _ = store.batch(np.arange(min(64, len(store))))
    small.eval(); big.eval()
    with torch.no_grad():
        x, y = small.log_policy(b), big.log_policy(b)
    err = max(float((x[k] - y[k]).abs().max()) for k in x)
    small.train(); big.train()
    print(json.dumps(dict(grown_max_abs_logprob_error=err, params_small=sum(p.numel() for p in small.parameters()),
                          params_big=sum(p.numel() for p in big.parameters()))), flush=True)
    if err > 1e-4:
        raise AssertionError(f'growth is not function-preserving: {err}')



def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--init', required=True)
    ap.add_argument('--assets', required=True)
    ap.add_argument('--new', action='append', required=True, help='packed ExIt corpus (repeatable)')
    ap.add_argument('--old', action='append', default=[], help='read-only older teacher corpus (repeatable)')
    ap.add_argument('--new-ratio', type=float, default=1.0,
                    help='fraction of each batch from --new, in (0, 1]; 1 requires omitting --old')
    ap.add_argument('--keep-hits', action='store_true')
    ap.add_argument('--heldout', type=float, default=0.05)
    ap.add_argument('--steps', type=int, default=1000)
    ap.add_argument('--batch', type=int, default=4096)
    ap.add_argument('--microbatch', type=int, default=1024)
    ap.add_argument('--lr', type=float, default=1e-4)
    ap.add_argument('--warmup', type=int, default=100)
    ap.add_argument('--weight-decay', type=float, default=.05)
    ap.add_argument('--ema', type=float, default=.01, help='EMA lerp rate per step')
    ap.add_argument('--temperature', type=float, default=.003)
    ap.add_argument('--eval-every', type=int, default=250)
    ap.add_argument('--seed', type=int, default=2026101401)
    ap.add_argument('--loader-workers', type=int, default=8)
    ap.add_argument('--grow-layers', type=int, default=0, help='grow to this many blocks (function-preserving)')
    ap.add_argument('--grow-ffn', type=int, default=0, help='grow FFN width to this (function-preserving)')
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args(argv)
    if not 0 < a.new_ratio <= 1:
        ap.error('--new-ratio is a batch fraction in (0, 1], not new:old odds')
    if a.old and a.new_ratio == 1:
        ap.error('--old would be unused at --new-ratio 1; use a fraction below 1 or omit --old')
    if not a.old and a.new_ratio != 1:
        ap.error('--new-ratio below 1 requires --old')
    if a.loader_workers < 0:
        ap.error('--loader-workers must be nonnegative')
    bootstrap()
    import torch
    from exit_r3.student import initialize_root
    a.out.mkdir(parents=True, exist_ok=True)
    if any(a.out.glob('step-*.pt')):
        raise ValueError('fresh output dir required')
    torch.manual_seed(a.seed); np.random.seed(a.seed)

    device = torch.device(a.device)
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    if device.type == 'cuda' and os.environ.get('BOT_GPU_MAX_GB'):  # leave room for other GPU users
        total = torch.cuda.get_device_properties(0).total_memory
        torch.cuda.set_per_process_memory_fraction(min(1., float(os.environ['BOT_GPU_MAX_GB']) * 2**30 / total), 0)
    model, cfg = initialize_root(a.init)
    base_cfg = cfg
    if a.grow_layers or a.grow_ffn:
        small = model
        model, cfg = grow(small, cfg, a.grow_layers, a.grow_ffn)
        check_grown(small, model, a)
    model = model.to(device)

    def fresh():
        m, _ = initialize_root(a.init)
        if cfg != base_cfg:
            m, _ = grow(m, base_cfg, a.grow_layers, a.grow_ffn)
        return m
    new_stores = make_stores(a.new, a.assets, a.keep_hits)
    splits = [split_rows(s, a.heldout) for s in new_stores]
    # Group positions index store.batch(), which itself maps through root_indices.
    new_train = Group(new_stores, [tr for tr, _ in splits])
    new_held = Group(new_stores, [ho for _, ho in splits])
    if not len(new_held):  # smoke runs on one game: evaluate on train rows (flagged in inputs.json)
        new_held = new_train
    old = None
    if a.old and a.new_ratio < 1:
        old_stores = make_stores(a.old, a.assets, True)
        old = Group(old_stores, [np.arange(len(s)) for s in old_stores])
        if not len(old):
            raise ValueError('required --old corpora contain no eligible root rows')
    if not len(new_train):
        raise ValueError('--new corpora contain no eligible training root rows')
    info = dict(args={k: str(v) for k, v in vars(a).items()}, config=asdict(cfg),
                init_sha256=sha(a.init), new_rows_train=len(new_train), new_rows_heldout=len(new_held),
                old_rows=len(old) if old else 0,
                new_manifests=[sha(Path(p) / 'manifest.json') for p in a.new],
                old_manifests=[sha(Path(p) / 'manifest.json') for p in a.old])
    (a.out / 'inputs.json').write_text(json.dumps(info, indent=2))
    print(json.dumps(info), flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=a.weight_decay)

    def lr_at(s):
        if s < a.warmup:
            return (s + 1) / a.warmup
        return .5 * (1 + math.cos(math.pi * min(1., (s - a.warmup) / max(1, a.steps - a.warmup))))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_at)
    ema = {k: v.detach().clone() for k, v in model.state_dict().items()}

    def ema_model():
        m = fresh()
        m.load_state_dict(ema)
        return m.to(device)

    def save(step, metrics):
        path = a.out / f'step-{step:06d}.pt'
        payload = dict(model=model.state_dict(), ema=ema, config=asdict(cfg), state=dict(step=step),
                       args=dict(vars(a), advantage_weight=0., out=str(a.out), new=a.new, old=a.old),
                       metrics=metrics)
        payload['args'] = {k: (str(v) if isinstance(v, Path) else v) for k, v in payload['args'].items()}
        tmp = path.with_suffix('.pt.partial')
        torch.save(payload, tmp); os.replace(tmp, path)
        Path(str(path) + '.calibration.json').write_text(json.dumps(dict(
            threshold=metrics['heldout']['threshold'], target_play_rate=metrics['heldout']['teacher_play_rate'],
            actual_play_rate=metrics['heldout']['student_play_rate'], rows=metrics['heldout']['rows'],
            checkpoint_sha256=sha(path), step=step, source='bot.exit.train heldout ExIt rows'), indent=2))
        return path

    log = open(a.out / 'train.jsonl', 'a', buffering=1)
    m0 = dict(step=0, heldout=evaluate(model, new_held, device))
    m0['heldout_init_threshold'] = evaluate(model, new_held, device, threshold=float(
        json.loads((RUNTIME / 'R3a-calibration.json').read_text())['threshold']))
    log.write(json.dumps(m0) + '\n'); print(json.dumps(m0), flush=True)
    data = StepBatches(new_train, old, a.batch, a.new_ratio, a.seed, 0, a.steps)
    loader = torch.utils.data.DataLoader(data, batch_size=None, shuffle=False, num_workers=a.loader_workers,
                                         prefetch_factor=4 if a.loader_workers else None, persistent_workers=False)
    model.train()
    t0 = time.time()
    for s, (b, y) in loader:
        opt.zero_grad(set_to_none=True)
        loss = forward_loss(model, b, y, device, a.microbatch, a.temperature)
        grad = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
        opt.step(); sched.step()
        with torch.no_grad():
            for k, v in model.state_dict().items():
                if v.is_floating_point() and k not in ('temperatures', 'costs', 'descriptors', 'tile_features', 'frequencies'):
                    ema[k].lerp_(v, a.ema)
                else:
                    ema[k].copy_(v)
        step = s + 1
        rec = dict(step=step, loss=loss, grad=float(grad), lr=sched.get_last_lr()[0], wall=time.time() - t0,
                   rows_new=round(len(y['action']) * (a.new_ratio if old else 1)))
        log.write(json.dumps(rec) + '\n')
        if step % 25 == 0:
            print(json.dumps(rec), flush=True)
        if step % a.eval_every == 0 or step == a.steps:
            em = ema_model()
            metrics = dict(step=step, heldout=evaluate(em, new_held, device),
                           heldout_raw=evaluate(model, new_held, device))
            path = save(step, metrics)
            log.write(json.dumps(dict(metrics, checkpoint=str(path))) + '\n')
            print(json.dumps(metrics), flush=True)
            del em
    (a.out / 'complete.json').write_text(json.dumps(dict(steps=a.steps, wall=time.time() - t0)))


if __name__ == '__main__':
    main()
