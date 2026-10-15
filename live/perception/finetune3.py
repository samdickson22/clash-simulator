"""Perception round 2 (exploration): joint body/HUD + TemporalHead run from ft-r2, with

  * effect identities 'fx:<spell>' (dense_labels.py --r2): frame-level supervision of spell areas/projectiles so the
    backbone features carry spell visuals (round-1 diagnosis: 32% of missed opponent spells had head evidence below
    threshold, 9% none). Effects are never units (common.decode_frame puts them in dec['effects']).
  * Royal Ghost positives while stationary on target (labels --r2).
  * per-cell COUNT head in body_box[2:4] (native owner 0 / 1; round 1 left these channels unused): number of body
    centres in the half-tile cell. Round-1 diagnosis: 51% of unit misses were merged same-card peaks (+21% displaced
    1-2 tiles), SkeletonArmy alone 21% of all misses. common.decode_frame emits one detection per counted body.
  * event windows: spell endpoints oversampled harder (--spell-share), and the event loss reaches the backbone through
    the latest --egrad frames of every window (round 1: backbone frozen for events).

Train split only (HeldoutGuard).

  python live/perception/finetune3.py --init JOB/ft-r2/final.pt --labels JOB2/labels-r2 --out JOB2/ft-r3 --hours 4
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
import finetune as F1
import finetune2 as F2
from finetune import Blocks, flat, focal, augment
from finetune2 import Windows, event_targets, visual_births, event_loss, load_events

FORMAT = 'live-dense-v2'
args_zero_w = 1.   # count-loss weight of empty cells (main() --count-zero-w)
N_UNIT = 56          # card identities; 56, 57 = towers; >= 58 = effects


def build_model(init, K, cards):
    from clasher.vision.l1_v4 import PerceptionV4
    state = torch.load(init, map_location='cpu', weights_only=False)
    model = PerceptionV4(len(state['cards']), K)
    sd = dict(state['model'])
    if state.get('format') == FORMAT:
        model.load_state_dict(sd)
        return model, state
    assert state.get('format') == F1.FORMAT, state.get('format')
    k0 = len(state['identities'])
    cur = model.state_dict()
    for k, v in sd.items():
        if not k.startswith('body.heatmap'):
            cur[k] = v
    w, b = cur['body.heatmap.weight'], cur['body.heatmap.bias']
    w.zero_(); b.fill_(-4.)
    for o in (0, 1):
        w[o*K:o*K+k0] = sd['body.heatmap.weight'][o*k0:(o+1)*k0]; b[o*K:o*K+k0] = sd['body.heatmap.bias'][o*k0:(o+1)*k0]
    # count channels start at ~1 body per positive cell: zero weights, bias 0 (sigmoid-free regression)
    cur['body.box.weight'][2:4].zero_(); cur['body.box.bias'][2:4].zero_()
    model.load_state_dict(cur)
    print(json.dumps(dict(init=str(init), expanded=f'{k0}->{K} identities')), flush=True)
    return model, state


def targets(b, K, flip):
    heat, valid, peak, off, hp = F1.targets(b, K, flip)
    pos = b['pos']; B = pos.shape[0]; dev = pos.device
    x = pos[..., 2]
    if flip is not None:
        x = torch.where(flip[:, None], 18.0-x, x)
    gx = (x*2).floor().clamp(0, 35).long(); gy = (pos[..., 3]*2).floor().clamp(0, 63).long()
    cls = pos[..., 0].long(); own = pos[..., 1].long().clamp(0, 1)
    body = (pos[..., 5] > 0) & (cls < N_UNIT)
    cnt = torch.zeros(B, 2*64*36, device=dev)
    cnt.scatter_add_(1, own*64*36+gy*36+gx, body.float())
    # hp targets only for bodies with hit points (effects carry none)
    has_hp = (pos[..., 5] > 0) & (cls < N_UNIT+2)
    hpm = torch.zeros(B, 64*36, device=dev)
    hpm.scatter_(1, torch.where(has_hp, gy*36+gx, torch.zeros_like(gx)), has_hp.float())
    hpm[:, 0] = 0
    return heat, valid, peak, off, hp, cnt.view(B, 2, 64, 36), hpm.view(B, 1, 64, 36)


def loss_fn(out, b, heat, valid, peak, off, hp, cnt, hpm):
    _, parts = F1.loss_fn(out, b, heat, valid, peak, off, hp*hpm)
    parts['hp'] = 2*((out['body_hp'].float()-hp).abs()*hpm).sum()/hpm.sum().clamp_min(1)
    pred = out['body_box'][:, 2:4].float()
    w = (cnt > 0).float()+args_zero_w  # zero cells weighted args_zero_w (r3 start 0.05 over-predicted counts next to bodies)
    parts['count'] = (F.smooth_l1_loss(pred, cnt, reduction='none', beta=.25)*w*valid).sum()/(cnt > 0).float().sum().clamp_min(1)
    return sum(parts.values()), parts


def window_forward(model, w, device, egrad=0, gen=None):
    arena = w['arena'].to(device, non_blocking=True); B, T = arena.shape[:2]
    x = arena.permute(0, 1, 4, 2, 3).float()/255
    if gen is not None:
        gain = torch.empty(B, 1, 1, 1, 1, device=device).uniform_(.85, 1.15, generator=gen)
        x = (x*gain).clamp(0, 1)
    ages = w['ages'].to(device); valid = w['valid'].to(device)
    x = torch.where(valid[:, :, None, None, None], x, torch.zeros_like(x))
    g = min(egrad, T)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        with torch.no_grad():
            old = model.backbone(x[:, :T-g].reshape(-1, *x.shape[2:])) if T-g else None
        parts = [] if old is None else [old.view(B, T-g, *old.shape[1:])]
        if g:
            new = model.backbone(x[:, T-g:].reshape(-1, *x.shape[2:]))
            parts.append(new.view(B, g, *new.shape[1:]))
        cache = torch.cat(parts, 1)
        with torch.no_grad():
            births = visual_births(model, cache.detach(), ages, valid)
        out = model.temporal(cache.float(), ages, valid, births.float())
    return out


@torch.no_grad()
def quick_val(model, loader, K, device, ident):
    """finetune.quick_val with v2 targets (effects excluded from units by decode_frame) + count-decode unit F1."""
    from eval_val import match
    model.eval(); tot = dict(n=0, hand=0, hand_n=0, tp=0, fp=0, fn=0, ctp=0, cfp=0, cfn=0, cnt_mae=0., cnt_n=0)
    for b in loader:
        b = flat(b, device)
        arena = b['arena'].permute(0, 3, 1, 2).float()/255; hud = b['hud'].permute(0, 3, 1, 2).float()/255
        with torch.autocast('cuda', dtype=torch.bfloat16):
            out = model.encode(arena, hud)
        _, _, _, _, _, cnt, _ = targets(b, K, None)
        m = cnt > 0
        tot['cnt_mae'] += float((out['body_box'][:, 2:4].float()-cnt).abs()[m].sum()); tot['cnt_n'] += int(m.sum())
        pc = out['hud_cards'].float().argmax(-1); mm = b['cards'] < 56
        tot['hand'] += int(((pc == b['cards']) & mm).sum()); tot['hand_n'] += int(mm.sum()); tot['n'] += len(pc)
        o = {k: out[k].float().cpu().numpy() for k in ('body_heatmap', 'body_hp', 'body_hp_visible', 'body_box', 'hud_cards',
                                                     'elixir_digit', 'elixir_fraction', 'clock_seconds', 'phase')}
        P = b['pos'].cpu().numpy()
        for f in range(len(P)):
            if bool(b['stale'][f]):
                continue
            pv = P[f][P[f][:, 5] > 0]
            tr = [(x, y, (int(ow), ident[int(c)])) for c, ow, x, y, fr, v in pv if int(c) < N_UNIT]
            for counts, key in ((False, ''), (True, 'c')):
                dec = C.decode_frame(o, f, ident[:56], ident, threshold=.4, offsets=True, counts=counts)
                pr = [(u['score'], u['x'], u['y'], (u['owner'], u['identity'])) for u in dec['units'] if u['identity'] not in C.TOWER_BODIES]
                tp, fp, used = match(pr, tr, 1., True)
                tot[key+'tp'] += len(tp); tot[key+'fp'] += len(fp); tot[key+'fn'] += len(tr)-len(used)
    model.train()
    pr = lambda tp, fp, fn: (round(tp/max(1, tp+fp), 4), round(tp/max(1, tp+fn), 4), round(2*tp/max(1, 2*tp+fp+fn), 4))
    return dict(hand_acc=tot['hand']/max(1, tot['hand_n']), unit_id_prf=pr(tot['tp'], tot['fp'], tot['fn']),
                unit_id_prf_counts=pr(tot['ctp'], tot['cfp'], tot['cfn']), count_mae_pos_cells=tot['cnt_mae']/max(1, tot['cnt_n']),
                frames=tot['n'])


class Windows3(Windows):
    """finetune2.Windows with a configurable spell share of event endpoints."""
    spell_share = .5

    def __getitem__(self, index):
        if self.fixed is not None:
            return super().__getitem__(index)
        rng = random.Random(self.seed*7_000_003+index)
        u = rng.random()
        if u < .7:
            for _ in range(10):
                ep = rng.choice(self.eps)
                if (C.CACHE/ep/'index.json').exists() or (C.LOCAL_CACHE/ep/'index.json').exists():
                    break
            ev = self.events(ep); lab = self.blocks.lab(ep); tick = lab['tick']
            if len(ev):
                spells = ev[ev[:, 5] > 0]
                e = spells[rng.randrange(len(spells))] if (len(spells) and rng.random() < self.spell_share) else ev[rng.randrange(len(ev))]
                end = int(np.clip(np.searchsorted(tick, e[4]+rng.uniform(0, 30)), 1, len(tick)-1))
                saved, self.fixed = self.fixed, [(ep, end, rng.uniform(8, 25))]
                try:
                    return super().__getitem__(0)
                finally:
                    self.fixed = saved
        return super().__getitem__(index)

    def __len__(self):
        return self.length


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--init', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--labels', type=Path, required=True)
    p.add_argument('--hours', type=float, default=4.); p.add_argument('--epoch-steps', type=int, default=1000)
    p.add_argument('--blocks', type=int, default=8); p.add_argument('--windows', type=int, default=8)
    p.add_argument('--workers', type=int, default=7); p.add_argument('--wworkers', type=int, default=8)
    p.add_argument('--lr', type=float, default=1.2e-4); p.add_argument('--tlr', type=float, default=2.5e-4)
    p.add_argument('--egrad', type=int, default=4); p.add_argument('--spell-share', type=float, default=.6)
    p.add_argument('--max-steps', type=int, default=0); p.add_argument('--val-matches', type=int, default=16)
    p.add_argument('--seed', type=int, default=20261016); p.add_argument('--copy-to', default='')
    p.add_argument('--count-zero-w', type=float, default=1.)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    global args_zero_w
    args_zero_w = a.count_zero_w
    torch.set_num_threads(2); torch.manual_seed(a.seed); device = 'cuda'
    guard = C.HeldoutGuard()
    train_eps = guard.episodes('train'); val_eps = guard.episodes('validation')[:a.val_matches]
    guard.check(train_eps+val_eps); assert not (set(train_eps) & set(val_eps))
    ident = D.vocab(guard.cards, effects=True); K = len(ident); nc = len(guard.cards)
    voc = json.loads((a.labels/'vocab.json').read_text())
    assert voc['identities'] == ident, 'labels are not --r2'
    model, _ = build_model(a.init, K, guard.cards); model.to(device).train()
    groups = dict(head=[], rest=[], temporal=[])
    for n, p_ in model.named_parameters():
        groups['temporal' if n.startswith('temporal.') else 'head' if n.startswith(('body.', 'hud.')) else 'rest'].append(p_)
    bases = (a.lr, a.lr/2, a.tlr)
    opt = torch.optim.AdamW([dict(params=groups[k], lr=v) for k, v in zip(('head', 'rest', 'temporal'), bases)], weight_decay=1e-4)
    fixed = []
    for ep in val_eps:
        lab = D.load(a.labels/f'{ep}.npz'); n = len(lab['row'])
        for k in range(0, n//16, 8):
            ok = [i for i in range(k*16, min(n, k*16+16)) if lab['row'][i] >= 0]
            if len(ok) >= 4:
                fixed.append((ep, k, ok[::max(1, len(ok)//4)][:4]))
    val_loader = torch.utils.data.DataLoader(Blocks(val_eps, a.labels, 'validation', 0, 0, fixed=fixed[::2]), batch_size=a.blocks, num_workers=3)
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
    Windows3.spell_share = a.spell_share
    wtrain = Windows3(train_eps, a.labels, 'train', 10**8, a.seed+1, guard.cards)
    wloader = torch.utils.data.DataLoader(wtrain, batch_size=a.windows, num_workers=a.wworkers, pin_memory=True,
                                          persistent_workers=True, prefetch_factor=3, sampler=range(10**8))
    meta = dict(format=FORMAT, cards=guard.cards, bodies=ident, identities=ident, init=str(a.init), init_sha256=C.sha(a.init),
                split_sha256=C.SPLIT_SHA, train_matches=len(train_eps), labels=str(a.labels),
                temporal=f'trained on dense events (finetune3, egrad {a.egrad}, spell share {a.spell_share})',
                offsets='body_box[0:2] = sub-cell x,y offset', counts='body_box[2:4] = bodies per cell, native owner 0/1',
                effects='identities fx:<spell> = spell areas/projectiles (not units)', heldout_opened=False)
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
                out = window_forward(model, w, device, egrad=0)
                ev = w['events'].to(device); heat, age, mask = event_targets(ev, nc)
                l1, l2 = event_loss(out, heat, age, mask); tot['loss'] += float(l1+l2); tot['n'] += 1
                sc = out['event_heatmap'].float().sigmoid(); pk = (sc == F.max_pool2d(sc, 3, 1, 1)) & (sc >= .5)
                for bi in range(len(ev)):
                    tr = [(int(e[1])*nc+int(e[0]), float(e[2]), float(e[3]), bool(guard.cards[int(e[0])] in F2.SPELLS)) for e in ev[bi].cpu().numpy() if e[5] > 0]
                    cs, ys, xs = torch.nonzero(pk[bi], as_tuple=True)
                    pr = [(int(c), (int(x)+.5)/2, (int(y)+.5)/2) for c, y, x in zip(cs.tolist(), ys.tolist(), xs.tolist())]
                    used = set()
                    for c, x, y in pr:
                        hit = [j for j, t in enumerate(tr) if j not in used and t[0] == c and math.hypot(t[1]-x, t[2]-y) <= 2]
                        if hit:
                            used.add(hit[0]); tot['tp'] += 1; tot['stp'] += tr[hit[0]][3]
                        else:
                            tot['fp'] += 1; tot['sfp'] += guard.cards[c % nc] in F2.SPELLS
                    tot['fn'] += len(tr)-len(used); tot['sfn'] += sum(t[3] for j, t in enumerate(tr) if j not in used)
        model.train()
        f = lambda tp, fp, fn: (round(tp/max(1, tp+fp), 4), round(tp/max(1, tp+fn), 4))
        return dict(event_loss=tot['loss']/max(1, tot['n']), event_pr_window=f(tot['tp'], tot['fp'], tot['fn']),
                    spell_pr_window=f(tot['stp'], tot['sfp'], tot['sfn']))

    def save(name):
        torch.save(dict(model=model.state_dict(), step=step, **meta), a.out/f'{name}.tmp'); (a.out/f'{name}.tmp').replace(a.out/f'{name}.pt')

    if a.epoch_steps and not a.max_steps:      # baseline row (init weights, expanded heads)
        qv = quick_val(model, val_loader, K, device, ident); qv.update(wval_metrics()); qv.update(step=0)
        history.append(qv); print(json.dumps(dict(val=qv)), flush=True)
    for b, w in zip(loader, wloader):
        if stopping or time.time() > deadline or (a.max_steps and step >= a.max_steps):
            break
        if step == 150 and not a.max_steps:
            rate = 150/(time.time()-t0); est = int(rate*a.hours*3600*.95)
            print(json.dumps(dict(steps_per_s=round(rate, 3), est_steps=est, max_mem_gb=round(torch.cuda.max_memory_allocated()/2**30, 1))), flush=True)
        scale = min(1., (step+1)/200)*(.5*(1+math.cos(math.pi*min(1., step/est))))*.97+.03
        for g, base in zip(opt.param_groups, bases):
            g['lr'] = base*scale
        b = flat(b, device)
        arena = b['arena'].permute(0, 3, 1, 2).float()/255; hud = b['hud'].permute(0, 3, 1, 2).float()/255
        arena, hud, flip = augment(arena, hud, gen)
        with torch.autocast('cuda', dtype=torch.bfloat16):
            out = model.encode(arena, hud)
        floss, parts = loss_fn(out, b, *targets(b, K, flip))
        wout = window_forward(model, w, device, egrad=a.egrad, gen=gen)
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
        if a.epoch_steps and step % a.epoch_steps == 0:
            qv = quick_val(model, val_loader, K, device, ident); qv.update(wval_metrics()); qv.update(step=step, time=time.time()-t0)
            history.append(qv); print(json.dumps(dict(val=qv)), flush=True)
            save(f'epoch-{step//a.epoch_steps}'); save('last')
            (a.out/'history.json').write_text(json.dumps(history, indent=1)+'\n')
    qv = quick_val(model, val_loader, K, device, ident); qv.update(wval_metrics()); qv.update(step=step, final=True)
    history.append(qv); print(json.dumps(dict(done=True, val=qv)), flush=True)
    save('final'); save('last')
    (a.out/'history.json').write_text(json.dumps(history, indent=1)+'\n')


if __name__ == '__main__':
    main()
