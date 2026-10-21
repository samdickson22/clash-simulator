"""CPU latency benchmark of one pretrain-v1 decision (featurize + network + mask/decode), batch 1.

    python -m bot.pretrain_v1.bench_cpu [--ckpt best.pt] [--polls 20000] [--threads 1 4] --out bench.json

Inputs are real logged live records (records.jsonl of the live mirror, replayed in order through one Session per
game, so History grows as in a battle) plus a dense set: the polls with the most bodies across all recordings,
replayed after a warm history. Reports p50/p95/p99/max per thread count and scenario, and cold start (first step
after model load). PREREG G1 item 4 bar (to be re-measured on the Mac serving runtime): p95 <= 30 ms, p99 <= 50 ms.
"""
from __future__ import annotations

import argparse
import glob
import json
import platform
import time
from pathlib import Path

import numpy as np
import torch

from . import featurize as F
from .model import PolicyV1
from .policy import Session, load

LIVE_GLOB = '/mpac/sdicks02/scratch/live-mem/mirror/mem-c2*/m*/records.jsonl'


def games(limit_polls):
    out, n = [], 0
    for p in sorted(glob.glob(LIVE_GLOB)):
        recs = []
        for line in open(p):
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        if recs:
            out.append(recs)
            n += len(recs)
        if n >= limit_polls:
            break
    return out


def run(model, gs, polls, seed=0):
    ts, parts = [], []
    k = 0
    for recs in gs:
        s = Session(model, seed + k)
        last = None
        for r in recs:
            if last is not None and r['tick'] <= last:
                continue
            last = r['tick']
            t0 = time.perf_counter()
            d = s.step(r)
            ts.append(1e3*(time.perf_counter() - t0))
            parts.append(d.ms)
            k += 1
            if k >= polls:
                return np.array(ts), parts
    return np.array(ts), parts


def stats(ts):
    return dict(n=int(len(ts)), p50=float(np.percentile(ts, 50)), p95=float(np.percentile(ts, 95)),
                p99=float(np.percentile(ts, 99)), max=float(ts.max()), mean=float(ts.mean()))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt', default=None)
    ap.add_argument('--polls', type=int, default=20000)
    ap.add_argument('--threads', type=int, nargs='+', default=[1, 4])
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    if a.ckpt:
        model, _ = load(a.ckpt)
    else:
        torch.manual_seed(0)
        model = PolicyV1()
        model.eval()
    load_ms = 1e3*(time.perf_counter() - t0)
    gs = games(a.polls)
    # dense scenario: the 500 polls with the most units, each after a 40-poll warm history from its own game
    dense = []
    for recs in gs:
        for i, r in enumerate(recs):
            dense.append((len(r['units']), i, recs))
    dense.sort(key=lambda x: -x[0])
    dense_sets = [recs[max(0, i - 40):i + 1] for _, i, recs in dense[:500]]
    res = dict(schema='clasher.pretrain_v1.bench.v1', host=platform.node(), cpu=platform.processor(),
               torch=torch.__version__, params=model.n_params(), feature_hash=F.feature_hash(), load_ms=load_ms,
               max_units_dense=dense[0][0] if dense else None, runs={})
    for th in a.threads:
        torch.set_num_threads(th)
        s = Session(model, 123)
        r0 = gs[0][0]
        t1 = time.perf_counter()
        s.step(r0)
        cold = 1e3*(time.perf_counter() - t1)
        ts, parts = run(model, gs, a.polls)
        feat = np.array([p.get('features', 0) for p in parts])
        net = np.array([p.get('network', 0) for p in parts])
        dec = np.array([p.get('decode', 0) for p in parts])
        dts = []
        for seq in dense_sets:
            s = Session(model, 7)
            last = None
            for r in seq[:-1]:
                if last is None or r['tick'] > last:
                    s.step(r)
                    last = r['tick']
            if seq[-1]['tick'] > (last or -1):
                t1 = time.perf_counter()
                s.step(seq[-1])
                dts.append(1e3*(time.perf_counter() - t1))
        res['runs'][str(th)] = dict(cold_ms=cold, normal=stats(ts), features=stats(feat), network=stats(net),
                                    decode=stats(dec[dec > 0]) if (dec > 0).any() else None,
                                    dense=stats(np.array(dts)) if dts else None)
        print(json.dumps({th: {k: (v if not isinstance(v, dict) else {kk: round(vv, 2) for kk, vv in v.items()})
                               for k, v in res['runs'][str(th)].items()}}), flush=True)
    Path(a.out).write_text(json.dumps(res, indent=1) + '\n')


if __name__ == '__main__':
    main()
