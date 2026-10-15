"""Joint exploration run: body/HUD frame batches (as finetune.py) + TemporalHead play-event windows.

Window step: 16 frames at a random 8-25 FPS ending at a sampled endpoint; backbone features
are computed without grad (detached), visual births from body peaks as in PerceptionV4.forward,
TemporalHead trained with focal heatmap + age NLL on accepted play events (champion abilities
excluded). Spell-event endpoints oversampled. Train split only.

  python live/perception/finetune2.py --init JOB/ft-r1/last.pt --out JOB/ft-r2 --hours 3.5
"""
import argparse
import json
import math
import random
import signal
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

import common as C
import dense_labels as D
from finetune import Blocks, build_model, flat, targets, focal, augment, loss_fn as frame_loss, quick_val, FORMAT

E_MAX = 24
SPELLS = {'Arrows', 'BarbLog', 'Earthquake', 'Fireball', 'GoblinBarrel', 'Lightning', 'Log', 'Poison', 'Rocket',
          'RoyalDelivery', 'Tornado', 'Zap'}


def load_events(ep, cards):
    rows = C.read_jsonl(C.MATCHES/ep/'events.jsonl')
    ev = [(cards.index(e['card']), e['side'], e['tile'][0], e['tile'][1], e['exec_tick'], e['card'] in SPELLS)
          for e in rows if e['accepted'] and e['kind'] != 'champion ability' and e['card'] in cards]
    return np.asarray(ev, np.float64).reshape(-1, 6)


class Windows(torch.utils.data.Dataset):
    def __init__(self, eps, labels, split, length, seed, cards, fixed=None):
        self.eps, self.labels, self.split, self.length, self.seed, self.cards, self.fixed = eps, Path(labels), split, length, seed, cards, fixed
        self.blocks = Blocks(eps, labels, split, 0, 0); self._ev = {}

    def __len__(self):
        return len(self.fixed) if self.fixed is not None else self.length

    def events(self, ep):
        if ep not in self._ev:
            self._ev[ep] = load_events(ep, self.cards)
        return self._ev[ep]

    def __getitem__(self, index):
        rng = random.Random(self.seed*7_000_003+index)
        if self.fixed is not None:
            ep, end, rate = self.fixed[index]
        else:
            while True:
                ep = rng.choice(self.eps)
                if (C.CACHE/ep/'index.json').exists() or (C.LOCAL_CACHE/ep/'index.json').exists():
                    break
            lab = self.blocks.lab(ep); ev = self.events(ep); tick = lab['tick']; n = len(tick)
            u = rng.random()
            if len(ev) and u < .65:
                spells = ev[ev[:, 5] > 0]
                e = spells[rng.randrange(len(spells))] if (len(spells) and rng.random() < .5) else ev[rng.randrange(len(ev))]
                target_tick = e[4]+rng.uniform(0, 30)  # 0..1.5 s after execution
                end = int(np.clip(np.searchsorted(tick, target_tick), 1, n-1))
            else:
                end = rng.randrange(1, n)
            rate = rng.uniform(8, 25)
        lab = self.blocks.lab(ep); px = self.blocks.pix(ep); tick = lab['tick']
        # pick up to 16 frames going back at `rate` FPS (ticks are 50 ms)
        chosen = [end]; due = tick[end]-20/rate
        for i in range(end-1, -1, -1):
            if tick[i] <= due+1e-6:
                chosen.append(i); due = tick[i]-20/rate
                if len(chosen) == 16:
                    break
        chosen = chosen[::-1]
        blocks = {}
        ar = [];
        for i in chosen:
            k = i//px.bs
            if k not in blocks:
                blocks[k] = px.block(k)
            ar.append(blocks[k][0][i-k*px.bs])
        hud = blocks[end//px.bs][1][end-(end//px.bs)*px.bs]
        pad = 16-len(ar)
        arena = np.zeros((16, *ar[0].shape), np.uint8); arena[pad:] = np.stack(ar)
        ages = np.zeros(16, np.float32); ages[pad:] = (tick[end]-tick[chosen])*50.
        valid = np.zeros(16, bool); valid[pad:] = True
        ev = self.events(ep); out = np.zeros((E_MAX, 6), np.float32); m = 0
        for c, s, x, y, et, sp in ev:
            dt = (tick[end]-et)*50.
            if 0 <= dt <= 1500 and m < E_MAX:
                out[m] = (c, s, x, y, dt, 1); m += 1
        return dict(arena=torch.from_numpy(arena), hud=torch.from_numpy(np.ascontiguousarray(hud)), ages=torch.from_numpy(ages),
                    valid=torch.from_numpy(valid), events=torch.from_numpy(out))


def event_targets(ev, n_cards):
    """ev [B,E,6] cls, side, x, y, dt_ms, valid -> heat [B,2n,64,36], age, mask."""
    B = ev.shape[0]; dev = ev.device; valid = ev[..., 5] > 0
    gx = (ev[..., 2]*2).floor().clamp(0, 35); gy = (ev[..., 3]*2).floor().clamp(0, 63)
    yy = torch.arange(64, device=dev).view(1, 1, 64, 1).float(); xx = torch.arange(36, device=dev).view(1, 1, 1, 36).float()
    g = torch.exp(-((xx-gx[..., None, None])**2+(yy-gy[..., None, None])**2)/2)*valid[..., None, None]
    ch = (ev[..., 1]*n_cards+ev[..., 0]).long().clamp(0, 2*n_cards-1)
    heat = torch.zeros(B, 2*n_cards, 64, 36, device=dev)
    heat.scatter_reduce_(1, ch[..., None, None].expand(-1, -1, 64, 36), g, 'amax')
    flat_idx = (ch*64*36+gy.long()*36+gx.long())
    age = torch.zeros(B, 2*n_cards*64*36, device=dev); mask = torch.zeros_like(age)
    idx = torch.where(valid, flat_idx, torch.zeros_like(flat_idx))
    age.scatter_(1, idx, torch.where(valid, ev[..., 4], age.gather(1, idx)))
    mask.scatter_(1, idx, valid.float()); mask[:, 0] = 0
    return heat, age.view_as(heat), mask.view_as(heat)


def visual_births(model, cache, ages, valid):
    """As PerceptionV4.forward (training branch): fresh body peaks in the latest vs previous valid frame."""
    b = cache.shape[0]; ar = torch.arange(b, device=cache.device)
    latest = ages.masked_fill(~valid, float('inf')).argmin(1)
    previous = ages.masked_fill(~valid | (ages <= 0), float('inf')).argmin(1)
    new = model.body(cache[ar, latest])['body_heatmap'].sigmoid()
    old = model.body(cache[ar, previous])['body_heatmap'].sigmoid()
    peaks = (new == F.max_pool2d(new, 3, 1, 1)) & (new >= .5)
    fresh = peaks & (F.max_pool2d(old, 7, 1, 3) < .3)
    vb = fresh.reshape(b, 2, -1, 64, 36).sum(2).float()
    has_prev = torch.isfinite(ages.masked_fill(~valid | (ages <= 0), float('inf')).min(1).values)
    vb = vb*has_prev[:, None, None, None]
    return F.max_pool2d(vb, 7, 1, 3).clamp(max=8)


def window_forward(model, w, device, train=True, gen=None):
    arena = w['arena'].to(device, non_blocking=True); B, T = arena.shape[:2]
    x = arena.reshape(B*T, *arena.shape[2:]).permute(0, 3, 1, 2).float()/255
    if train and gen is not None:
        gain = torch.empty(B, 1, 1, 1, 1, device=device).uniform_(.85, 1.15, generator=gen)
        x = (x.view(B, T, *x.shape[1:])*gain).clamp(0, 1).view_as(x)
    ages = w['ages'].to(device); valid = w['valid'].to(device)
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
        x = torch.where(valid.reshape(-1)[:, None, None, None], x, torch.zeros_like(x))
        feats = model.backbone(x)
        cache = feats.view(B, T, *feats.shape[1:])
        births = visual_births(model, cache, ages, valid)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        out = model.temporal(cache.float(), ages, valid, births.float())
    return out


def event_loss(out, heat, age, mask):
    ev = focal(out['event_heatmap'], heat, torch.ones_like(heat[:, :1]))
    sigma = out['event_sigma_ms'].float()/1000; residual = (out['event_age_ms'].float()-age)/1000
    nll = ((.5*(residual/sigma)**2+sigma.log())*mask).sum()/mask.sum().clamp_min(1)
    return ev, nll


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--init', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--labels', type=Path, default=Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels'))
    p.add_argument('--hours', type=float, default=3.5); p.add_argument('--epoch-steps', type=int, default=1000)
    p.add_argument('--blocks', type=int, default=8); p.add_argument('--windows', type=int, default=8)
    p.add_argument('--workers', type=int, default=6); p.add_argument('--wworkers', type=int, default=8)
    p.add_argument('--lr', type=float, default=1.5e-4); p.add_argument('--tlr', type=float, default=3e-4)
    p.add_argument('--max-steps', type=int, default=0); p.add_argument('--val-matches', type=int, default=16)
    p.add_argument('--seed', type=int, default=20261015)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2); torch.manual_seed(a.seed); device = 'cuda'
    guard = C.HeldoutGuard()
    train_eps = guard.episodes('train'); val_eps = guard.episodes('validation')[:a.val_matches]
    guard.check(train_eps+val_eps); assert not (set(train_eps) & set(val_eps))
    K = len(D.vocab(guard.cards)); nc = len(guard.cards)
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
    # fixed val windows: every accepted event endpoint +10 ticks, plus uniform
    wfixed = []
    for ep in val_eps:
        lab = D.load(a.labels/f'{ep}.npz'); tick = lab['tick']; ev = load_events(ep, guard.cards)
        for e in ev[::2]:
            wfixed.append((ep, int(np.clip(np.searchsorted(tick, e[4]+10), 1, len(tick)-1)), 15.))
        for end in range(40, len(tick), 400):
            wfixed.append((ep, end, 15.))
    wval = torch.utils.data.DataLoader(Windows(val_eps, a.labels, 'validation', 0, 0, guard.cards, fixed=wfixed), batch_size=a.windows, num_workers=3)
    train = Blocks(train_eps, a.labels, 'train', 10**8, a.seed)
    loader = torch.utils.data.DataLoader(train, batch_size=a.blocks, num_workers=a.workers, pin_memory=True,
                                         persistent_workers=True, prefetch_factor=4, sampler=range(10**8))
    wtrain = Windows(train_eps, a.labels, 'train', 10**8, a.seed+1, guard.cards)
    wloader = torch.utils.data.DataLoader(wtrain, batch_size=a.windows, num_workers=a.wworkers, pin_memory=True,
                                          persistent_workers=True, prefetch_factor=3, sampler=range(10**8))
    meta = dict(format=FORMAT, cards=guard.cards, bodies=D.vocab(guard.cards), identities=D.vocab(guard.cards),
                init=str(a.init), init_sha256=C.sha(a.init), split_sha256=C.SPLIT_SHA, train_matches=len(train_eps),
                temporal='trained on dense events (finetune2)', offsets='body_box[0:2] = sub-cell x,y offset', heldout_opened=False)
    (a.out/'meta.json').write_text(json.dumps(meta, indent=1)+'\n')
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGUSR1, stop)
    gen = torch.Generator(device=device); gen.manual_seed(a.seed)
    deadline = time.time()+a.hours*3600; t0 = time.time(); tl = time.time(); run = {}; step = 0; est = a.max_steps or 10**9
    history = []

    def wval_metrics():
        model.eval(); tot = dict(loss=0., n=0, tp=0, fp=0, fn=0, stp=0, sfn=0, sfp=0)
        with torch.no_grad():
            for w in wval:
                out = window_forward(model, w, device, train=False)
                ev = w['events'].to(device); heat, age, mask = event_targets(ev, nc)
                l1, l2 = event_loss(out, heat, age, mask); tot['loss'] += float(l1+l2); tot['n'] += 1
                sc = out['event_heatmap'].float().sigmoid(); pk = (sc == F.max_pool2d(sc, 3, 1, 1)) & (sc >= .5)
                for bi in range(len(ev)):
                    tr = [(int(e[1])*nc+int(e[0]), float(e[2]), float(e[3]), bool(guard.cards[int(e[0])] in SPELLS)) for e in ev[bi].cpu().numpy() if e[5] > 0]
                    cs, ys, xs = torch.nonzero(pk[bi], as_tuple=True)
                    pr = [(int(c), (int(x)+.5)/2, (int(y)+.5)/2) for c, y, x in zip(cs.tolist(), ys.tolist(), xs.tolist())]
                    used = set()
                    for c, x, y in pr:
                        hit = [j for j, t in enumerate(tr) if j not in used and t[0] == c and math.hypot(t[1]-x, t[2]-y) <= 2]
                        if hit:
                            used.add(hit[0]); tot['tp'] += 1; tot['stp'] += tr[hit[0]][3]
                        else:
                            tot['fp'] += 1; tot['sfp'] += guard.cards[c % nc] in SPELLS
                    tot['fn'] += len(tr)-len(used); tot['sfn'] += sum(t[3] for j, t in enumerate(tr) if j not in used)
        model.train()
        f = lambda tp, fp, fn: (round(tp/max(1, tp+fp), 4), round(tp/max(1, tp+fn), 4))
        return dict(event_loss=tot['loss']/max(1, tot['n']), event_pr_window=f(tot['tp'], tot['fp'], tot['fn']),
                    spell_pr_window=f(tot['stp'], tot['sfp'], tot['sfn']))

    for b, w in zip(loader, wloader):
        if stopping or time.time() > deadline or (a.max_steps and step >= a.max_steps):
            break
        if step == 150 and not a.max_steps:
            rate = 150/(time.time()-t0); est = int(rate*a.hours*3600*.95)
            print(json.dumps(dict(steps_per_s=round(rate, 3), est_steps=est)), flush=True)
        scale = min(1., (step+1)/200)*(.5*(1+math.cos(math.pi*min(1., step/est))))*.97+.03
        for g, base in zip(opt.param_groups, bases):
            g['lr'] = base*scale
        b = flat(b, device)
        arena = b['arena'].permute(0, 3, 1, 2).float()/255; hud = b['hud'].permute(0, 3, 1, 2).float()/255
        arena, hud, flip = augment(arena, hud, gen)
        with torch.autocast('cuda', dtype=torch.bfloat16):
            out = model.encode(arena, hud)
        heat, valid, peak, off, hp = targets(b, K, flip)
        floss, parts = frame_loss(out, b, heat, valid, peak, off, hp)
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
            qv = quick_val(model, val_loader, K, device, meta['identities']); qv.update(wval_metrics()); qv.update(step=step, time=time.time()-t0)
            history.append(qv); print(json.dumps(dict(val=qv)), flush=True)
            torch.save(dict(model=model.state_dict(), step=step, **meta), a.out/f'epoch-{step//a.epoch_steps}.pt')
            (a.out/'history.json').write_text(json.dumps(history, indent=1)+'\n')
    qv = quick_val(model, val_loader, K, device, meta['identities']); qv.update(wval_metrics()); qv.update(step=step, final=True)
    history.append(qv); print(json.dumps(dict(done=True, val=qv)), flush=True)
    torch.save(dict(model=model.state_dict(), step=step, **meta), a.out/'final.pt')
    (a.out/'history.json').write_text(json.dumps(history, indent=1)+'\n')


if __name__ == '__main__':
    main()
