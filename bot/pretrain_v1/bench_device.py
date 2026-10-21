"""Batch-1 decision latency for any model size on any device: featurize + collate + device transfer + network +
masks + sampled gate / slot / tile (exactly Session.step's work), end to end.

    python -m bot.pretrain_v1.bench_device --records DIR [--ckpt CK | --size d,layers,heads,ffn] --device cpu|mps|cuda
        [--threads 1] [--polls 20000] [--out bench.json]

--records: a directory tree of logged live records (records.jsonl), replayed in order, one History per game (the
same real inputs as bench_cpu.py). Without --ckpt the weights are random: that measures NETWORK cost per size only,
because the weights change how often the tile branch runs. --session times the exact serving path,
policy.Session.step (value head, survival-scaled gate, decode) with accepted plays fed back to History, for
qualifying a trained checkpoint. Reports p50 / p95 / p99 / max, cold first decision, play fraction, entity counts and
the host's load at start and end (shared hosts: sequential runs under changing load are not strictly comparable).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import time
from pathlib import Path

import numpy as np
import torch

from . import featurize as F
from .model import PolicyV1, collate, tiles_ok_np


def games(root, limit):
    out, n = [], 0
    for p in sorted(Path(root).rglob('records.jsonl')):
        recs, last = [], None
        for line in open(p):
            try:
                r = json.loads(line)
                if last is None or r['tick'] > last:
                    recs.append(r)
                    last = r['tick']
            except json.JSONDecodeError:
                pass
        if recs:
            out.append(recs)
            n += len(recs)
        if n >= limit:
            break
    return out


def sync(dev):
    if dev.type == 'mps':
        torch.mps.synchronize()
    elif dev.type == 'cuda':
        torch.cuda.synchronize()


@torch.inference_mode()
def decide(model, dev, feat, rng):
    """One decision; returns per-component ms."""
    t0 = time.perf_counter()
    b = {k: v.to(dev) for k, v in collate([feat]).items()}
    cls, hand = model.trunk(b)
    gate = model.gate_logits(cls, hand, b['slot_ok'])[0]
    p = torch.softmax(gate.float(), -1).cpu().double().numpy()
    t1 = time.perf_counter()
    if feat['slot_ok'].any() and rng.random() >= p[0]:
        slot = int(rng.choice(4, p=p[1:]/p[1:].sum()))
        tok = torch.from_numpy(tiles_ok_np(feat['hand'][None], feat['slot_ok'][None], feat['alive'][None])).to(dev)
        z = model.tile_logits(cls, hand, torch.tensor([slot], device=dev), tok[:, slot])[0]
        pt = torch.softmax(z.float(), -1).cpu().double().numpy()
        rng.choice(F.NTILE, p=pt/pt.sum())
    sync(dev)
    return 1e3*(t1 - t0), 1e3*(time.perf_counter() - t1)


def stats(x):
    x = np.asarray(x)
    return dict(n=int(len(x)), p50=float(np.percentile(x, 50)), p95=float(np.percentile(x, 95)),
                p99=float(np.percentile(x, 99)), max=float(x.max()), mean=float(x.mean()))


def load_avg():
    try:
        return list(os.getloadavg())
    except OSError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--records', required=True)
    ap.add_argument('--ckpt', default=None)
    ap.add_argument('--size', default='192,4,6,576', help='d,layers,heads,ffn when no --ckpt')
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--threads', type=int, default=1)
    ap.add_argument('--polls', type=int, default=20000)
    ap.add_argument('--warmup', type=int, default=200)
    ap.add_argument('--out', default=None)
    ap.add_argument('--session', action='store_true', help='time policy.Session.step (the serving path), including device transfers')
    a = ap.parse_args(argv)
    if a.polls < 1 or a.warmup < 0:
        ap.error('--polls must be positive and --warmup nonnegative')
    torch.set_num_threads(a.threads)
    dev = torch.device(a.device)
    torch.manual_seed(0)
    if a.ckpt:
        checkpoint_bytes = Path(a.ckpt).read_bytes()
        checkpoint_sha256 = hashlib.sha256(checkpoint_bytes).hexdigest()
        ck = torch.load(io.BytesIO(checkpoint_bytes), map_location='cpu', weights_only=False)
        del checkpoint_bytes
        if ck.get('feature_hash') != F.feature_hash():
            raise SystemExit('checkpoint feature hash differs from this featurizer')
        c = ck['cfg']
        model = PolicyV1(d=c['d'], layers=c['layers'], heads=c['heads'], ffn=c['ffn'])
        model.load_state_dict(ck['model'])
    else:
        d, L, h, f = (int(x) for x in a.size.split(','))
        model = PolicyV1(d=d, layers=L, heads=h, ffn=f)
    model.eval().to(dev)
    gs = games(a.records, a.polls + a.warmup)
    rng = np.random.default_rng(0)
    load0 = load_avg()
    feats_ms, net_ms, dec_ms, total = [], [], [], []
    cold = None
    k = 0
    if a.session:
        from .policy import Session
        plays, ents = 0, []
        for gi, recs in enumerate(gs):
            sess = Session(model, gi)
            last = None
            for r in recs:
                if last is not None and r['tick'] <= last:
                    continue
                last = r['tick']
                sync(dev)
                t0 = time.perf_counter()
                d = sess.step(r)
                sync(dev)
                if d.status == 'play':
                    sess.accepted(d)
                tt = 1e3*(time.perf_counter() - t0)
                cold = tt if cold is None else cold
                k += 1
                if k > a.warmup:
                    total.append(tt)
                    feats_ms.append(d.ms.get('features', 0))
                    net_ms.append(d.ms.get('network', 0))
                    dec_ms.append(d.ms.get('decode', 0))
                    plays += d.status == 'play'
                    ents.append(len(sess.last_feat['ent']))
                if k >= a.polls + a.warmup:
                    break
            if k >= a.polls + a.warmup:
                break
        if len(total) != a.polls:
            raise SystemExit(f'only {len(total)} timed polls available; requested {a.polls}')
        dense_floor = float(np.percentile(ents, 90))
        dense = [ms for ms, n in zip(total, ents) if n >= dense_floor]
        res = dict(schema='clasher.pretrain_v1.bench-device.v1', mode='session', host=platform.node(),
                   machine=platform.machine(), platform=platform.platform(), torch=torch.__version__, device=a.device,
                   threads=a.threads, ckpt=a.ckpt,
                   checkpoint_sha256=checkpoint_sha256 if a.ckpt else None,
                   weights='checkpoint' if a.ckpt else 'random', params=model.n_params(), cfg=model.cfg, feature_hash=F.feature_hash(),
                   cold_ms=cold, total=stats(total), dense=stats(dense), dense_entity_floor=dense_floor,
                   features=stats(feats_ms), network=stats(net_ms),
                   decode=stats([x for x in dec_ms if x > 0] or [0.0]), play_fraction=plays/max(1, len(total)),
                   entities=dict(mean=float(np.mean(ents)), max=int(max(ents))), load_start=load0,
                   load_end=load_avg(), polls=len(total), warmup=a.warmup)
        print(json.dumps({k_: v for k_, v in res.items() if k_ != 'cfg'}), flush=True)
        if a.out:
            target = Path(a.out)
            temp = target.with_name(target.name + f'.{os.getpid()}.tmp')
            temp.write_text(json.dumps(res, indent=1) + '\n')
            os.replace(temp, target)
        return
    for recs in gs:
        h = F.History()
        last = None
        for r in recs:
            if last is not None and r['tick'] <= last:
                continue
            last = r['tick']
            t0 = time.perf_counter()
            feat = F.observe(r, None, h)
            tf = 1e3*(time.perf_counter() - t0)
            tn, td = decide(model, dev, feat, rng)
            tt = 1e3*(time.perf_counter() - t0)
            if cold is None:
                cold = tt
            k += 1
            if k > a.warmup:
                feats_ms.append(tf)
                net_ms.append(tn)
                dec_ms.append(td)
                total.append(tt)
            if k >= a.polls + a.warmup:
                break
        if k >= a.polls + a.warmup:
            break
    res = dict(schema='clasher.pretrain_v1.bench-device.v1', host=platform.node(), machine=platform.machine(),
               platform=platform.platform(), torch=torch.__version__, device=a.device, threads=a.threads,
               params=model.n_params(), cfg=model.cfg, feature_hash=F.feature_hash(), cold_ms=cold,
               total=stats(total), features=stats(feats_ms), network=stats(net_ms), decode=stats(dec_ms),
               load_start=load0, load_end=load_avg(), polls=len(total), warmup=a.warmup)
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: (round(vv, 2) if isinstance(vv, float) else vv)
                                                              for kk, vv in v.items()})
                      for k, v in res.items() if k not in ('cfg',)}), flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1) + '\n')


if __name__ == '__main__':
    main()
