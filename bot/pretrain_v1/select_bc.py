"""Registered BC anchor selection (PREREG section 5): over every per-epoch checkpoint of every seed run, fit the one
scalar gate intercept on natural-frequency DEV, run the full-DEV G1 admission (admit_bc.admission), keep the
ELIGIBLE candidates (G1 item 1 broad + Hog, item 2's checkable parts, target-card coverage), and select the lowest
broad DEV joint NLL; ties (< 1e-4) -> lower Hog NLL -> earlier epoch -> lower seed. The winner, with its frozen gate
intercept, is written as the human KL anchor. If nothing is eligible, the best candidate is written as a
PROVISIONAL checkpoint and the report says no admissible anchor exists.

    python -m bot.pretrain_v1.select_bc --store STORE --runs RUN_s1 RUN_s2 RUN_s3 --out DIR [--device cuda]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from . import featurize as F
from .admit_bc import admission
from .policy import load
from .train_bc import Store, fit_gate_bias


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--store', required=True)
    ap.add_argument('--runs', nargs='+', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
    ap.add_argument('--smoke-games', type=int, default=0, help='SMOKE ONLY: restrict DEV to this many physical games')
    a = ap.parse_args(argv)
    torch.set_num_threads(4)
    import os
    frac = float(os.environ.get('PV1_GPU_FRACTION', '0') or 0)
    if frac and str(a.device).startswith('cuda'):
        torch.cuda.set_per_process_memory_fraction(frac)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    store = Store(a.store)
    if a.smoke_games:                                  # smoke test only: a DEV subset (never a registered selection)
        keep = np.unique(store.phys[store.split == 1])[:a.smoke_games]
        store.split = np.where((store.split == 1) & ~np.isin(store.phys, keep), 3, store.split)
    dev = np.nonzero(store.split == 1)[0]
    cache, table = {}, []
    for run in a.runs:
        for ck_path in sorted(Path(run).glob('ep[0-9][0-9].pt')):
            model, ck = load(ck_path, map_location=a.device)
            model.to(a.device)
            bias, nll0, nll1 = fit_gate_bias(model, store, dev, a.device)
            model.gate_bias.fill_(bias)
            res = admission(model, store, a.device, 'dev', cache)
            row = dict(res, ckpt=str(ck_path), seed=int(ck['seed']), ep=int(ck['ep']), gate_bce=[nll0, nll1])
            assert abs(row['gate_bias'] - bias) < 1e-6
            table.append(row)
            print(json.dumps({k: row[k] for k in ('ckpt', 'seed', 'ep', 'eligible', 'broad/joint_nll_model',
                                                  'hog/joint_nll_model', 'gate_ece', 'plays_ratio')}), flush=True)
            (out/'candidates.jsonl').open('a').write(json.dumps(row) + '\n')
    pool = [r for r in table if r['eligible']] or table
    admitted = any(r['eligible'] for r in table)
    best = min(r['broad/joint_nll_model'] for r in pool)
    tied = [r for r in pool if r['broad/joint_nll_model'] - best < 1e-4]
    win = sorted(tied, key=lambda r: (r.get('hog/joint_nll_model', 9e9), r['ep'], r['seed']))[0]
    model, ck = load(win['ckpt'], map_location='cpu')
    model.gate_bias.fill_(win['gate_bias'])
    name = 'anchor.pt' if admitted and not a.smoke_games else 'PROVISIONAL-not-admitted.pt'
    torch.save(dict(model=model.state_dict(), cfg=model.cfg, feature_hash=F.feature_hash(), seed=win['seed'],
                    ep=win['ep'], gate_bias=win['gate_bias'], admission=win, source=win['ckpt']), out/name)
    summary = dict(admitted=admitted and not a.smoke_games, smoke=bool(a.smoke_games), selected=win['ckpt'],
                   gpu_peak_reserved_gib=(torch.cuda.max_memory_reserved()/2**30
                                          if str(a.device).startswith('cuda') else None), seed=win['seed'], ep=win['ep'], file=name,
                   sha256=hashlib.sha256((out/name).read_bytes()).hexdigest(), candidates=len(table),
                   eligible=sum(r['eligible'] for r in table), selection=win)
    (out/'selection.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'selection'}, indent=1))


if __name__ == '__main__':
    main()
