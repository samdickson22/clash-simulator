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
    a = ap.parse_args(argv)
    torch.set_num_threads(4)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    store = Store(a.store)
    dev = np.nonzero(store.split == 1)[0]
    cache, table = {}, []
    for run in a.runs:
        for ck_path in sorted(Path(run).glob('ep[0-9][0-9].pt')):
            model, ck = load(ck_path, map_location=a.device)
            model.to(a.device)
            bias, nll0, nll1 = fit_gate_bias(model, store, dev, a.device)
            model.gate_bias.fill_(bias)
            res = admission(model, store, a.device, 'dev', cache)
            row = dict(ckpt=str(ck_path), seed=int(ck['seed']), ep=int(ck['ep']), gate_bias=bias,
                       gate_bce=[nll0, nll1], **res)
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
    name = 'anchor.pt' if admitted else 'PROVISIONAL-not-admitted.pt'
    torch.save(dict(model=model.state_dict(), cfg=model.cfg, feature_hash=F.feature_hash(), seed=win['seed'],
                    ep=win['ep'], gate_bias=win['gate_bias'], admission=win, source=win['ckpt']), out/name)
    summary = dict(admitted=admitted, selected=win['ckpt'], seed=win['seed'], ep=win['ep'], file=name,
                   sha256=hashlib.sha256((out/name).read_bytes()).hexdigest(), candidates=len(table),
                   eligible=sum(r['eligible'] for r in table), selection=win)
    (out/'selection.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'selection'}, indent=1))


if __name__ == '__main__':
    main()
