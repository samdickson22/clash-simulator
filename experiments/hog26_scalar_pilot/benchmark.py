"""Synthetic full-game CPU backward feasibility; never opens corpus files."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

import torch
from scalar_models import EntityHistoryOutcome, GlobalWDL
from test_scalar_models import synthetic

torch.set_num_threads(1)
torch.manual_seed(1279501)
started = time.perf_counter()
model = EntityHistoryOutcome(498, princess_tower_token=10, king_tower_token=11)
x = synthetic(batch=2, time=750, entities=128)
generated = time.perf_counter()
optimizer = torch.optim.AdamW(model.parameters(), lr=.0003, weight_decay=.0001)
logits, margins, _ = model(x, torch.tensor([750, 750]))
forward = time.perf_counter()
targets = torch.ones(2, 750, dtype=torch.long) * 2
loss = torch.nn.functional.cross_entropy(logits.reshape(-1, 3), targets.reshape(-1)) + (margins - .3).abs().mean()
loss.backward()
gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
optimizer.step()
completed = time.perf_counter()
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
peak_bytes = peak if sys.platform == 'darwin' else peak * 1024
result = {
    'scope': 'synthetic feasibility only; no corpus or outcome training',
    'source_sha256': {name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('scalar_models.py','test_scalar_models.py','benchmark.py','scalar_training.py')},
    'shape': {'batch_games': 2, 'decisions': 750, 'entities': 128},
    'device': 'cpu', 'threads': 1, 'torch': torch.__version__,
    'dtype': 'float32', 'bptt': 'full-game; no detach or truncation',
    'global_parameters': sum(p.numel() for p in GlobalWDL().parameters()),
    'entity_parameters': sum(p.numel() for p in model.parameters()),
    'synthetic_generation_seconds': generated - started,
    'forward_including_optimizer_setup_seconds': forward - generated,
    'backward_optimizer_seconds': completed - forward,
    'total_seconds': completed - started, 'peak_process_rss_bytes': peak_bytes,
    'gradient_norm': float(gradient_norm), 'loss': float(loss.detach()),
    'finite_gradients': all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()),
}
print(json.dumps(result, indent=2))
