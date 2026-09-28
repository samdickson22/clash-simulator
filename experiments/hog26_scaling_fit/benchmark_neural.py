"""Synthetic full-game step through the exact scaling trainer; no corpus reads."""
import hashlib
import json
import resource
import time
from dataclasses import fields
from pathlib import Path

import numpy as np
import torch
from scalar_dataset import Game
from scaling_training import fit_entity
from test_scalar_models import synthetic


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    tokens = [f'synthetic:{i}' for i in range(498)]
    tokens[10], tokens[11] = 'tower:Tower', 'tower:KingTower'
    batch = synthetic(batch=2, time=750, entities=128)
    games = [Game({f.name:getattr(batch, f.name)[i].numpy() for f in fields(batch)},
                  2, .3, 'synthetic', 'synthetic', i, 'synthetic', '', '') for i in range(2)]
    weights = [np.full(750, 1/1500) for _ in games]
    started = time.monotonic()
    model = fit_entity(games, [0,1], weights, weights, vocabulary=tokens, seed=1279501,
                       epochs=1, batch_games=2)
    finite = all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters())
    if not finite:
        raise ValueError('nonfinite or missing synthetic gradients')
    sources = ['experiments/hog26_scaling_fit/benchmark_neural.py',
               'experiments/hog26_scaling_fit/scaling_training.py',
               'experiments/hog26_data_scaling/compact_public.py',
               'experiments/hog26_data_scaling/scaling_dataset.py',
               'experiments/hog26_scalar_pilot/scalar_models.py',
               'experiments/hog26_scalar_pilot/test_scalar_models.py']
    result = {'scope':'synthetic exact scaling-training step; no actual-corpus fitting',
              'shape':[2,750,128], 'full_bptt':True, 'epochs':1, 'steps':1,
              'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'seconds':time.monotonic()-started, 'finite_gradients':finite,
              'parameters':sum(p.numel() for p in model.parameters()),
              'runtime':{'torch':torch.__version__, 'device':'cpu', 'threads':1},
              'sources':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources},
              'full_combined_memory_verified':False}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
