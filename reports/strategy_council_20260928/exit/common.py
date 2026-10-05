"""Local experiment setup, pins and bounded artifact storage."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tomllib
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COUNCIL = HERE.parent
os.environ.update(CLASHER_ROOT=str(ROOT), PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
for path in (ROOT/'src', ROOT/'engine-rs'):
    sys.path.insert(0, str(path))
import numpy as np
import torch
from pydantic import BaseModel, ConfigDict, Field
from support import Context, TRAIN_DECKS, DEV_DECKS, HOG_DECKS, CHECKPOINT, ROLE_DECKS, cl_eval, maybe_silence_stdio
from public_planner import Resources, PublicPlanner, observe
ROLE_DECKS['training'] = TRAIN_DECKS
DEVICE = torch.device('cpu')
STYLES = ('balanced', 'pressure', 'defense')

class Config(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    games: int = Field(ge=2, le=150)
    iterations: int = Field(ge=1, le=3)
    workers: int = Field(ge=1, le=3)
    epochs: int = Field(ge=1, le=2)
    learning_rate: float
    anchor_kl: float
    chunk: int = Field(ge=2)
    collection_seed: int
    evaluation_seed: int
    split_seed: int
    fit_seed: int

def config():
    cfg = Config.model_validate(tomllib.loads((HERE/'config.toml').read_text()))
    assert cfg.games % 2 == 0 and cfg.learning_rate == 5e-6 and cfg.anchor_kl == 1.
    return cfg

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(1024*1024), b''): h.update(data)
    return h.hexdigest()

def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n'); tmp.replace(path)

def log(value):
    print(json.dumps(value, sort_keys=True), flush=True)

def folder(iteration):
    out = HERE/f'it{iteration}'; out.mkdir(exist_ok=True); return out

def previous(iteration):
    return CHECKPOINT if iteration == 1 else folder(iteration-1)/'student.pt'

def budget():
    total = sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())
    if total >= 2*1024**3: raise RuntimeError('exit artifact budget exceeded')
    return total

def verify():
    pins = json.loads((HERE/'manifest.json').read_text())
    for name, expected in pins['sha256'].items():
        if sha(ROOT/name) != expected: raise RuntimeError('dependency drift: '+name)
    budget()
    return sha(HERE/'manifest.json')

def preflight():
    config()
    assert sha(ROOT/'gamedata.json') == '892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65'
    native = json.loads((COUNCIL/'srp-dagger/native-runtime.json').read_text())
    for name, expected in native['verified_hashes'].items():
        assert sha(ROOT/name) == expected, name
    files = list((ROOT/'src/clasher').rglob('*.py')) + list(HERE.glob('*.py'))
    files += [HERE/'config.toml', HERE/'DESIGN.md', ROOT/'gamedata.json', CHECKPOINT, TRAIN_DECKS, DEV_DECKS, HOG_DECKS]
    files += [ROOT/p for p in native['verified_hashes']]
    files += [COUNCIL/'human-prior-p16/scripts/run_eval.py']
    write_json(HERE/'manifest.json', dict(created=datetime.now(timezone.utc).isoformat(),
        sha256={str(p.relative_to(ROOT)):sha(p) for p in files}))
    log(dict(preflight='passed', bytes=budget()))

def reset(ctx, role, seed, seat, *, symmetric=False):
    env = ctx.envs(role, seed)[seat]
    pools = ctx.pools(role)
    decks = cl_eval._sample_paired_ordered_decks(pools[0], pools[0] if symmetric else pools[1], matchup_seed=seed)
    # For symmetric H2H, keep world decks fixed while swapping the controller seat.
    ordered = decks if symmetric or seat == 0 else decks[::-1]
    with maybe_silence_stdio(True): env.reset(seed=seed, ordered_decks=ordered)
    return env, ordered
