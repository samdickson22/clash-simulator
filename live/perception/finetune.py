"""Exploration fine-tune of PerceptionV4 encode() on dense card-level labels (train split only).

Body head -> 58 identities (C56 cards + KingTower + PrincessTower) x 2 native owners.
body_box channels 0/1 are repurposed as the sub-cell (x, y) offset of the object inside
its half-tile cell (sigmoid in [0,1]); channels 2/3 are unused. The temporal head is
carried along untrained. Checkpoints every epoch + quick val subset metrics.

  python live/perception/finetune.py --init T7.pt --out JOBDIR/ft-r1 --hours 4.5
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

P_MAX, Q_MAX, FPB = 192, 96, 4
FORMAT = 'live-dense-v1'


class Blocks(torch.utils.data.Dataset):
    """Random (episode, 16-frame block) -> FPB frames with non-stale object rows."""
    def __init__(self, eps, labels, split, length, seed, fixed=None):
        self.eps, self.labels, self.split, self.length, self.seed, self.fixed = eps, Path(labels), split, length, seed, fixed
        self._lab, self._pix, self._guard = {}, {}, None

    def __len__(self):
        return len(self.fixed) if self.fixed is not None else self.length

    def lab(self, ep):
        if ep not in self._lab:
            if len(self._lab) > 96:
                self._lab.pop(next(iter(self._lab)))
            self._lab[ep] = D.load(self.labels/f'{ep}.npz')
            if str(self._lab[ep]['split']) != self.split:
                raise AssertionError('label split mismatch')
        return self._lab[ep]

    def pix(self, ep):
        if self._guard is None:
            self._guard = C.HeldoutGuard()
        if ep not in self._pix:
            self._pix[ep] = C.Pixels(self._guard, ep, C.load_receipt(self._guard, ep, self.split))
        return self._pix[ep]

    def __getitem__(self, index):
        if self.fixed is not None:
            ep, k, sel = self.fixed[index]
        else:
            rng = random.Random(self.seed*1_000_003+index)
            for _ in range(20):
                ep = rng.choice(self.eps)
                if not ((C.CACHE/ep/'index.json').exists() or (C.LOCAL_CACHE/ep/'index.json').exists()):
                    continue  # cache still being built
                lab = self.lab(ep); px = self.pix(ep)
                k = rng.randrange(len(px.idx['blocks']))
                ok = [i for i in range(k*px.bs, min(px.n, (k+1)*px.bs)) if lab['row'][i] >= 0]
                if len(ok) >= FPB:
                    break
            sel = sorted(rng.sample(ok, FPB))
        lab = self.lab(ep); px = self.pix(ep)
        ar, hu = px.block(k); loc = [i-k*px.bs for i in sel]
        pos = np.zeros((len(sel), P_MAX, 6), np.float32); ign = np.zeros((len(sel), Q_MAX, 3), np.float32)
        for f, i in enumerate(sel):
            got = D.frame_objects(lab, i)
            if got is None:
                continue
            cls, own, x, y, frac, ig = got
            m = min(len(cls), P_MAX)
            pos[f, :m] = np.stack([cls[:m], own[:m], x[:m], y[:m], frac[:m], np.ones(m)], 1)
            q = min(len(ig), Q_MAX)
            if q:
                ign[f, :q, :2] = ig[:q]; ign[f, :q, 2] = 1
        el = lab['elixir'][sel]
        return dict(arena=torch.from_numpy(np.ascontiguousarray(ar[loc])), hud=torch.from_numpy(np.ascontiguousarray(hu[loc])),
                    pos=torch.from_numpy(pos), ign=torch.from_numpy(ign),
                    cards=torch.from_numpy(lab['hand'][sel].astype(np.int64)),
                    edigit=torch.from_numpy(lab['elixir_int'][sel].astype(np.int64)),
                    efrac=torch.from_numpy((el-np.floor(el)).astype(np.float32)),
                    clock=torch.from_numpy(lab['clock'][sel]), phase=torch.from_numpy(lab['phase'][sel].astype(np.int64)-1),
                    stale=torch.from_numpy((lab['row'][sel] < 0)))


def flat(b, device):
    out = {}
    for k, v in b.items():
        v = v.to(device, non_blocking=True)
        out[k] = v.reshape(-1, *v.shape[2:])
    return out


def targets(b, K, flip):
    """GPU targets. pos: [B,P,6] cls, owner, x, y, frac, valid (tiles, native)."""
    pos, ign = b['pos'], b['ign']; B = pos.shape[0]; dev = pos.device
    x, y = pos[..., 2], pos[..., 3]
    if flip is not None:
        x = torch.where(flip[:, None], 18.0-x, x)
        ig_x = torch.where(flip[:, None], 18.0-ign[..., 0], ign[..., 0])
    else:
        ig_x = ign[..., 0]
    cx, cy = x*2, y*2
    gx = cx.floor().clamp(0, 35); gy = cy.floor().clamp(0, 63)
    offx = (cx-gx).clamp(0, 1); offy = (cy-gy).clamp(0, 1)
    valid = pos[..., 5] > 0
    yy = torch.arange(64, device=dev).view(1, 1, 64, 1).float(); xx = torch.arange(36, device=dev).view(1, 1, 1, 36).float()
    g = torch.exp(-((xx-gx[..., None, None])**2+(yy-gy[..., None, None])**2)/2)*valid[..., None, None]
    ch = (pos[..., 1]*K+pos[..., 0]).long().clamp(0, 2*K-1)
    heat = torch.zeros(B, 2*K, 64, 36, device=dev)
    heat.scatter_reduce_(1, ch[..., None, None].expand(-1, -1, 64, 36), g, 'amax')
    # ignore windows (+-3 cells), positives re-enabled at their peak cells
    igx = (ig_x*2).floor().clamp(0, 35); igy = (ign[..., 1]*2).floor().clamp(0, 63)
    box = ((xx-igx[..., None, None]).abs() <= 3) & ((yy-igy[..., None, None]).abs() <= 3) & (ign[..., 2:3, None] > 0)
    body_valid = (~box.any(1, keepdim=True)).float()
    peak = torch.zeros(B, 1, 64, 36, device=dev)
    flat_idx = (gy*36+gx).long()
    peak.view(B, -1).scatter_(1, torch.where(valid, flat_idx, torch.zeros_like(flat_idx)), valid.float())
    peak[:, :, 0, 0] = 0  # padded writes land on cell 0; a genuine object there is extremely rare
    body_valid = torch.maximum(body_valid, peak)
    off = torch.zeros(B, 2, 64*36, device=dev); hp = torch.zeros(B, 1, 64*36, device=dev)
    idx = torch.where(valid, flat_idx, torch.zeros_like(flat_idx))
    off[:, 0].scatter_(1, idx, torch.where(valid, offx, off[:, 0].gather(1, idx)))
    off[:, 1].scatter_(1, idx, torch.where(valid, offy, off[:, 1].gather(1, idx)))
    hp[:, 0].scatter_(1, idx, torch.where(valid, pos[..., 4], hp[:, 0].gather(1, idx)))
    return heat, body_valid, peak, off.view(B, 2, 64, 36), hp.view(B, 1, 64, 36)


def focal(logits, target, mask):
    p = logits.float().sigmoid().clamp(1e-5, 1-1e-5); positive = target.eq(1)
    loss = -(p.log()*(1-p)**2*positive+(1-p).log()*p**2*(1-target)**4*~positive)
    loss = loss*mask; positive = positive*mask
    return loss.sum()/positive.sum().clamp_min(1)


def augment(arena, hud, gen):
    B = arena.shape[0]; dev = arena.device
    gain = torch.empty(B, 1, 1, 1, device=dev).uniform_(.8, 1.2, generator=gen)
    gamma = torch.empty(B, 1, 1, 1, device=dev).uniform_(.85, 1.15, generator=gen)
    tint = torch.empty(B, 3, 1, 1, device=dev).uniform_(.93, 1.07, generator=gen)
    arena = (arena*gain*tint).clamp(0, 1)**gamma; hud = (hud*gain*tint).clamp(0, 1)**gamma
    # resolution jitter: down/up-sample half the batch (capture resolution / scaler gap)
    s = random.uniform(.45, .9)
    half = torch.rand(B, device=dev, generator=gen) < .5
    if half.any():
        sub = arena[half]
        small = F.interpolate(sub, scale_factor=s, mode='area')
        arena[half] = F.interpolate(small, size=sub.shape[-2:], mode='bilinear', align_corners=False)
        subh = hud[half]
        hud[half] = F.interpolate(F.interpolate(subh, scale_factor=s, mode='area'), size=subh.shape[-2:], mode='bilinear', align_corners=False)
    noise = torch.rand(B, 1, 1, 1, device=dev, generator=gen)*.03
    arena = (arena+torch.randn(arena.shape, device=dev, generator=gen)*noise).clamp(0, 1)
    flip = torch.rand(B, device=dev, generator=gen) < .3
    arena = torch.where(flip[:, None, None, None], arena.flip(-1), arena)
    return arena, hud, flip


def build_model(init, K, device):
    from clasher.vision.l1_v4 import PerceptionV4
    state = torch.load(init, map_location='cpu', weights_only=False)  # own checkpoints (history holds numpy scalars)
    model = PerceptionV4(len(state['cards']), K)
    sd = state['model']
    if state.get('format') == FORMAT:
        model.load_state_dict(sd)
        return model, state
    old_bodies = state['bodies']; ob = len(old_bodies)
    cur = model.state_dict()
    for k, v in sd.items():
        if k.startswith('body.heatmap'):
            continue
        cur[k] = v
    w, bias = cur['body.heatmap.weight'], cur['body.heatmap.bias']
    w.zero_(); bias.fill_(-4)
    ident = D.vocab(state['cards'])
    copied = []
    for j, name in enumerate(old_bodies):
        card = name if name in ident else C.body_card(name)
        if card in ident and card not in copied:
            t = ident.index(card); copied.append(card)
            for o in (0, 1):
                w[o*K+t] = sd['body.heatmap.weight'][o*ob+j]; bias[o*K+t] = sd['body.heatmap.bias'][o*ob+j]
    model.load_state_dict(cur)
    print(json.dumps(dict(init=str(init), copied_heads=copied)), flush=True)
    return model, state


def loss_fn(out, b, heat, valid, peak, off, hp):
    body = focal(out['body_heatmap'], heat, valid)
    pm = peak.expand(-1, 2, -1, -1)
    offl = (F.smooth_l1_loss(out['body_box'][:, :2].float(), off, reduction='none', beta=.1)*pm).sum()/pm.sum().clamp_min(1)
    hpl = ((out['body_hp'].float()-hp).abs()*peak).sum()/peak.sum().clamp_min(1)
    hud = F.cross_entropy(out['hud_cards'].flatten(0, 1).float(), b['cards'].flatten())
    hud = hud+F.cross_entropy(out['elixir_digit'].float(), b['edigit'])
    hud = hud+F.smooth_l1_loss(out['elixir_fraction'].float(), b['efrac'], beta=.1)*4
    hud = hud+F.smooth_l1_loss(out['clock_seconds'].float()/180, b['clock']/180)+F.cross_entropy(out['phase'].float(), b['phase'])
    parts = dict(body=body, offset=offl, hp=hpl*2, hud=hud)
    return sum(parts.values()), parts


@torch.no_grad()
def quick_val(model, loader, K, device, ident):
    """Subset val: losses, hand slot acc, elixir int acc / MAE, unit F1 (id x owner and owner, r=1, t=.5)."""
    from eval_val import match
    model.eval(); tot = dict(n=0, hand=0, hand_n=0, eint=0, emae=0., tp=0, fp=0, fn=0, otp=0, ofp=0, ofn=0, tow=0., tow_n=0)
    lsum = 0.; ln = 0
    for b in loader:
        b = flat(b, device)
        arena = b['arena'].permute(0, 3, 1, 2).float()/255; hud = b['hud'].permute(0, 3, 1, 2).float()/255
        with torch.autocast('cuda', dtype=torch.bfloat16):
            out = model.encode(arena, hud)
        heat, valid, peak, off, hp = targets(b, K, None)
        loss, _ = loss_fn(out, b, heat, valid, peak, off, hp); lsum += float(loss); ln += 1
        pc = out['hud_cards'].float().argmax(-1); m = b['cards'] < 56
        tot['hand'] += int(((pc == b['cards']) & m).sum()); tot['hand_n'] += int(m.sum())
        ed = out['elixir_digit'].float().argmax(-1); tot['eint'] += int((ed == b['edigit']).sum())
        ev = (ed.float()+out['elixir_fraction'].float()).clamp(max=10)
        tot['emae'] += float((ev-(b['edigit'].float()+b['efrac'])).abs().sum()); tot['n'] += len(ed)
        o = {k: out[k].float().cpu().numpy() for k in ('body_heatmap', 'body_hp', 'body_hp_visible', 'body_box', 'hud_cards',
                                                     'elixir_digit', 'elixir_fraction', 'clock_seconds', 'phase')}
        P = b['pos'].cpu().numpy()
        for f in range(len(P)):
            if bool(b['stale'][f]):
                continue
            dec = C.decode_frame(o, f, ident[:56], ident, threshold=.5, offsets=True)
            pv = P[f][P[f][:, 5] > 0]
            tr = [(x, y, (int(ow), ident[int(c)])) for c, ow, x, y, fr, v in pv if int(c) < 56]
            pr = [(u['score'], u['x'], u['y'], (u['owner'], u['identity'])) for u in dec['units'] if u['identity'] not in C.TOWER_BODIES]
            tp, fp, used = match(pr, tr, 1., True); tot['tp'] += len(tp); tot['fp'] += len(fp); tot['fn'] += len(tr)-len(used)
            tro = [(x, y, k[0]) for x, y, k in tr]; pro = [(s, x, y, k[0]) for s, x, y, k in pr]
            tp, fp, used = match(pro, tro, 1., True); tot['otp'] += len(tp); tot['ofp'] += len(fp); tot['ofn'] += len(tro)-len(used)
            for t in dec['towers']:
                anc = [(fr) for c, ow, x, y, fr, v in pv if int(c) >= 56 and int(ow) == t['owner']
                       and abs(x*1000-[a for a in C.TOWER_SLOTS if a[0] == t['owner'] and a[1] == t['kind'] and a[2] == t['side']][0][3]) < 1]
                truth = anc[0] if anc else 0.
                pred = t['hp_frac'] if t['score'] >= .5 else 0.
                tot['tow'] += abs(pred-truth); tot['tow_n'] += 1
    model.train()
    f1 = lambda tp, fp, fn: 2*tp/max(1, 2*tp+fp+fn)
    return dict(val_loss=lsum/max(1, ln), hand_acc=tot['hand']/max(1, tot['hand_n']), elixir_int_acc=tot['eint']/max(1, tot['n']),
                elixir_mae=tot['emae']/max(1, tot['n']), unit_id_f1=f1(tot['tp'], tot['fp'], tot['fn']),
                unit_id_p=tot['tp']/max(1, tot['tp']+tot['fp']), unit_id_r=tot['tp']/max(1, tot['tp']+tot['fn']),
                unit_owner_f1=f1(tot['otp'], tot['ofp'], tot['ofn']), tower_hp_mae=tot['tow']/max(1, tot['tow_n']), frames=tot['n'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--init', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--labels', type=Path, default=Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels'))
    p.add_argument('--hours', type=float, default=4.); p.add_argument('--epoch-steps', type=int, default=1500)
    p.add_argument('--blocks', type=int, default=8); p.add_argument('--workers', type=int, default=11)
    p.add_argument('--lr', type=float, default=3e-4); p.add_argument('--max-steps', type=int, default=0)
    p.add_argument('--val-matches', type=int, default=16); p.add_argument('--seed', type=int, default=20261014)
    p.add_argument('--resume', action='store_true')
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4); torch.manual_seed(a.seed); device = 'cuda'
    guard = C.HeldoutGuard()
    train_eps = guard.episodes('train'); val_eps = guard.episodes('validation')[:a.val_matches]
    guard.check(train_eps+val_eps); assert not (set(train_eps) & set(val_eps))
    K = len(D.vocab(guard.cards))
    model, init_state = build_model(a.init, K, 'cpu'); model.to(device).train()
    head = [p_ for n, p_ in model.named_parameters() if n.startswith(('body.', 'hud.'))]
    rest = [p_ for n, p_ in model.named_parameters() if not n.startswith(('body.', 'hud.', 'temporal.'))]
    for n, p_ in model.named_parameters():
        if n.startswith('temporal.'):
            p_.requires_grad_(False)
    opt = torch.optim.AdamW([dict(params=head, lr=a.lr), dict(params=rest, lr=a.lr/2)], weight_decay=1e-4)
    est_steps = a.max_steps or int(a.hours*3600*4)  # schedule horizon; refined after warmup timing
    step = 0; history = []
    if a.resume and (a.out/'last.pt').exists():
        st = torch.load(a.out/'last.pt', map_location='cpu', weights_only=False)
        model.load_state_dict(st['model']); opt.load_state_dict(st['optimizer']); step = st['step']; est_steps = st['est_steps']
        history = st['history']
    # fixed val subset: every 8th block, 4 evenly spaced frames
    fixed = []
    for ep in val_eps:
        lab = D.load(a.labels/f'{ep}.npz'); n = len(lab['row'])
        for k in range(0, n//16, 8):
            ok = [i for i in range(k*16, min(n, k*16+16)) if lab['row'][i] >= 0]
            if len(ok) >= FPB:
                fixed.append((ep, k, ok[::max(1, len(ok)//FPB)][:FPB]))
    val_loader = torch.utils.data.DataLoader(Blocks(val_eps, a.labels, 'validation', 0, 0, fixed=fixed), batch_size=a.blocks,
                                             num_workers=4, shuffle=False)
    train = Blocks(train_eps, a.labels, 'train', 10**8, a.seed+step)
    sampler = range(step*a.blocks, 10**8)
    loader = torch.utils.data.DataLoader(train, batch_size=a.blocks, num_workers=a.workers, sampler=sampler,
                                         pin_memory=True, persistent_workers=True, prefetch_factor=4)
    meta = dict(format=FORMAT, cards=guard.cards, bodies=D.vocab(guard.cards), identities=D.vocab(guard.cards),
                init=str(a.init), init_sha256=C.sha(a.init), split_sha256=C.SPLIT_SHA, train_matches=len(train_eps),
                val_subset_matches=len(val_eps), offsets='body_box[0:2] = sub-cell x,y offset', heldout_opened=False)
    (a.out/'meta.json').write_text(json.dumps(meta, indent=1)+'\n')
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGUSR1, stop)
    gen = torch.Generator(device=device); gen.manual_seed(a.seed+step)
    deadline = time.time()+a.hours*3600; t0 = time.time(); tl = time.time(); run = {}
    warm = 300
    for b in loader:
        if stopping or time.time() > deadline or (a.max_steps and step >= a.max_steps):
            break
        b = flat(b, device)
        arena = b['arena'].permute(0, 3, 1, 2).float()/255; hud = b['hud'].permute(0, 3, 1, 2).float()/255
        arena, hud, flip = augment(arena, hud, gen)
        lr_scale = min(1., (step+1)/warm)*(.5*(1+math.cos(math.pi*min(1., step/est_steps))))*.97+.03
        for g, base in zip(opt.param_groups, (a.lr, a.lr/2)):
            g['lr'] = base*lr_scale
        with torch.autocast('cuda', dtype=torch.bfloat16):
            out = model.encode(arena, hud)
        heat, valid, peak, off, hp = targets(b, K, flip)
        loss, parts = loss_fn(out, b, heat, valid, peak, off, hp)
        if not torch.isfinite(loss):
            raise ValueError('nonfinite loss')
        opt.zero_grad(set_to_none=True); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 10); opt.step(); step += 1
        for k, v in parts.items():
            run[k] = run.get(k, 0.)+float(v)
        if step == 200 and not a.max_steps:
            rate = 200/(time.time()-t0); est_steps = int(rate*a.hours*3600*.93)
            print(json.dumps(dict(steps_per_s=round(rate, 3), est_steps=est_steps)), flush=True)
        if step % 100 == 0:
            print(json.dumps(dict(step=step, lr=round(a.lr*lr_scale, 7), sec=round(time.time()-tl, 1),
                                  **{k: round(v/100, 4) for k, v in run.items()})), flush=True)
            run = {}; tl = time.time()
        if step % a.epoch_steps == 0:
            qv = quick_val(model, val_loader, K, device, meta['identities']); qv.update(step=step, time=time.time()-t0); history.append(qv)
            print(json.dumps(dict(val=qv)), flush=True)
            ep_n = step//a.epoch_steps
            torch.save(dict(model=model.state_dict(), step=step, **meta), a.out/f'epoch-{ep_n}.pt')
            torch.save(dict(model=model.state_dict(), optimizer=opt.state_dict(), step=step, est_steps=est_steps,
                            history=history, **meta), a.out/'last.tmp'); (a.out/'last.tmp').replace(a.out/'last.pt')
            (a.out/'history.json').write_text(json.dumps(history, indent=1)+'\n')
    qv = quick_val(model, val_loader, K, device, meta['identities']); qv.update(step=step, time=time.time()-t0, final=True); history.append(qv)
    torch.save(dict(model=model.state_dict(), step=step, **meta), a.out/'final.pt')
    torch.save(dict(model=model.state_dict(), optimizer=opt.state_dict(), step=step, est_steps=est_steps, history=history, **meta),
               a.out/'last.tmp'); (a.out/'last.tmp').replace(a.out/'last.pt')
    (a.out/'history.json').write_text(json.dumps(history, indent=1)+'\n')
    print(json.dumps(dict(done=True, val=qv)), flush=True)


if __name__ == '__main__':
    main()
