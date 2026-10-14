"""Uniform weight average ("model soup") of student checkpoints that share one architecture and init.

    python -m bot.exit.soup --out SOUP.pt CKPT [CKPT ...]

Averages the floating-point tensors of each checkpoint's 'ema' (the served weights); non-float buffers are
taken from the first. Writes a checkpoint loadable by proposals.load_student / 'student:<path>'. The play
threshold must then be calibrated on-policy (bot.exit.calibrate --mode rate).
"""
from __future__ import annotations

import argparse
import hashlib

import torch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('ckpts', nargs='+')
    a = ap.parse_args()
    cks = [torch.load(p, map_location='cpu', weights_only=True) for p in a.ckpts]
    cfg = cks[0]['config']
    if any(c['config'] != cfg for c in cks):
        raise ValueError('architectures differ')
    ema = {}
    for k, v in cks[0]['ema'].items():
        ema[k] = (torch.stack([c['ema'][k].float() for c in cks]).mean(0).to(v.dtype)
                  if v.is_floating_point() and k not in ('temperatures', 'costs', 'descriptors', 'tile_features', 'frequencies')
                  else v.clone())
    sources = []
    for p in a.ckpts:
        h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
        sources.append(dict(path=p, sha256=h))
    torch.save(dict(ema=ema, model=ema, config=cfg, state=dict(step=0),
                    args=dict(advantage_weight=0., soup=sources)), a.out)
    print(a.out, len(cks))


if __name__ == '__main__':
    main()
