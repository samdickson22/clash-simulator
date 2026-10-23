"""Full DEV metrics only. Never select, admit, export, train, or launch anything."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import stat
import sys

SOURCE = '40ea0b503d94daba5486cb151f759b233664ba43'
FEATURE = 'ce6e509ee43a2a4a8c484261b5341b9a3f1b0c71a1a77a2024de89a80fa4773d'
MANIFEST = '1aa01c37fdd18ac7c23a5e9cf7b875b674d5021309ab4b4b79603fd29661b264'
MAPS = {'source': 'dd1f0b08b67f655ba1ab94340f7db5b5efc0e91bfe55f856e4a7b0d28dd4c89a',
        'store': '80e3a81aedc7d6dcfaafc4389ee593c43a7987673e5d4ec2adbbdfc395b8b456'}
ENV_MAP = '2971b4ca7f3d75c8ac334bb667892d23279b6c8311e1acb20d30d8a0d067db67'
JOB = Path('/mpac/sdicks02/jobs/clasher/dev-preview-primary-ep04-20261023')
STORE = Path('/mpac/sdicks02/jobs/clasher/supplemental-bc-20261022/staging/store/f-ce6e509ee43a-b-1005dbb4')
ORIGINAL = Path('/mpac/sdicks02/jobs/clasher/pretrain-v1/interim-20261022-b240')
CFG = dict(d=320, layers=6, heads=8, ffn=1280, drop=0.1)
ROWS, DEV_ROWS, NPARAMS = 23498034, 2332353, 8756421


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha256(path):
    with Path(path).open('rb') as f:
        return hash_stream(f)


def hash_stream(f):
    h = hashlib.sha256()
    for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
        h.update(b)
    return h.hexdigest()


def digest(value):
    require(isinstance(value, str) and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value), 'missing/invalid SHA256')
    return value


def plain_path(value):
    p = Path(value)
    require(p.is_absolute() and p == p.resolve(), 'path must be absolute, canonical, without symlinks')
    return p


def validate_inventory(d):
    require(d['purpose'] == 'unselected-DEV-PREVIEW', 'wrong purpose')
    require(d['source_commit'] == SOURCE and d['feature_hash'] == FEATURE, 'wrong source/feature pin')
    require(d['manifest_sha256'] == MANIFEST and d['map_sha256'] == MAPS, 'wrong store/source map pin')
    require(d['env_map_sha256'] == ENV_MAP, 'wrong environment pin')
    require(d['cfg'] == CFG and d['n_params'] == NPARAMS, 'wrong config/parameter count')
    require(d['rows'] == ROWS and d['dev_rows'] == DEV_ROWS, 'wrong row counts')
    require(plain_path(d['source_root']) == JOB/'inputs/source-40ea', 'wrong private source root')
    require(plain_path(d['store']) == STORE, 'wrong store path')
    digest(d['collection_receipt_sha256'])
    require(plain_path(d['collection_receipt_path']) == JOB/'metadata/parent-collection-receipt.json',
            'wrong collection receipt path')
    candidates = d['candidates']
    require(1 <= len(candidates) <= 4, 'need 1..4 explicit candidates')
    seen = set()
    for c in candidates:
        seed, ep = c['seed'], c['ep']
        require((seed, ep) not in seen, 'duplicate candidate')
        seen.add((seed, ep))
        require(type(seed) is int and seed in (2026102002, 2026102003) and
                type(ep) is int and ep == 4, 'only primary 2002/2003 finalized ep04 permitted')
        host = '127x01' if seed == 2026102002 else '127x02'
        name = f'ep{ep:02d}.pt'
        require(c['origin_host'] == host and c['origin_path'] == str(ORIGINAL/f'M-s{seed}'/name),
                'wrong finalized primary origin')
        h = digest(c['sha256'])
        require(type(c['bytes']) is int and 0 < c['bytes'] <= 512 * 1024**2, 'invalid checkpoint size')
        require(c['finalized'] is True, 'checkpoint not externally finalized')
        require(plain_path(c['path']) == JOB/'inputs'/host/f'M-s{seed}'/h/name,
                'checkpoint must use fresh raw-SHA destination')
    return d


def verify_collection_receipt(d):
    path = Path(d['collection_receipt_path'])
    require(sha256(path) == d['collection_receipt_sha256'], 'collection receipt SHA mismatch')
    r = json.loads(path.read_text())
    require(r['source_commit'] == SOURCE and r['snapshot_manifest_sha256'] == MANIFEST,
            'receipt source/snapshot mismatch')
    require(r['not_selection'] is True and r['not_anchor'] is True and r['final_unused'] is True and
            r['remote_write'] is False and r['gpu_or_training'] is False, 'wrong receipt authority')
    require(len({row['seed'] for row in r['rows']}) == len(r['rows']), 'duplicate receipt rows')
    rows = {row['seed']: row for row in r['rows']}
    for c in d['candidates']:
        row = rows[c['seed']]
        before = row['before']
        require(row['host'] == c['origin_host'] and before == row['after'] and
                before['path'] == c['origin_path'] and before['size'] == c['bytes'] and
                before['sha256'] == c['sha256'] == row['local_sha256'] and
                row['status'] == 'verified-immutable-unselected-preview-only', 'collection receipt mismatch')


def verify_map(root, path, expected, count):
    require(sha256(path) == expected, 'map SHA mismatch')
    entries = json.loads(Path(path).read_text())
    require(len(entries) == count, 'map count mismatch')
    root = plain_path(str(root))
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    require(actual == set(entries), 'input tree differs from pinned map')
    for rel, pin in entries.items():
        p = plain_path(str(root/rel))
        require(p.is_relative_to(root) and p.is_file(), 'unsafe mapped path')
        require(p.stat().st_size == pin['bytes'] and sha256(p) == pin['sha256'], 'mapped file mismatch: '+rel)


def import_reviewed(root):
    require('bot' not in sys.modules, 'refuse already imported bot package')
    sys.path.insert(0, str(root))
    modules = {k: importlib.import_module('bot.pretrain_v1.'+k) for k in ('featurize', 'model', 'train_bc')}
    for name, module in modules.items():
        require(Path(module.__file__).resolve() == root/'bot/pretrain_v1'/f'{name}.py', 'wrong imported source')
    require(modules['featurize'].feature_hash() == FEATURE, 'featurizer hash mismatch')
    return modules


def checkpoint_model(f, c, modules, torch):
    # Pinned bytes, safe tensor-only loading, full cfg including dropout, strict weights.
    ck = torch.load(f, map_location='cpu', weights_only=True)
    require(isinstance(ck, dict), 'incomplete checkpoint')
    require(ck.get('seed') == c['seed'] and ck.get('ep') == c['ep'], 'checkpoint seed/epoch mismatch')
    require(ck.get('feature_hash') == FEATURE, 'checkpoint feature mismatch')
    cat = modules['featurize'].catalog()
    cfg = dict(CFG, n_cards=cat.n_cards, n_bodies=cat.n_bodies)
    require(ck.get('cfg') == cfg, 'checkpoint cfg mismatch')
    require(ck.get('config', {}).get('dtype', 'float32') == 'float32', 'checkpoint dtype metadata mismatch')
    dev = ck.get('dev', {})
    require(dev.get('ep') == c['ep'] and type(dev.get('step')) is int and dev['step'] > 0 and
            math.isfinite(dev.get('dev/all/joint_nll', float('nan'))), 'missing complete epoch metrics')
    weights = ck.get('model')
    require(isinstance(weights, dict) and weights, 'missing policy weights')
    for t in weights.values():
        require(isinstance(t, torch.Tensor), 'non-tensor policy weight')
        require(not t.is_floating_point() or t.dtype == torch.float32, 'policy weights must be FP32')
        require(bool(torch.isfinite(t).all()), 'nonfinite policy weight')
    model = modules['model'].PolicyV1(**cfg)
    model.load_state_dict(weights, strict=True)
    require(model.n_params() == NPARAMS, 'wrong model parameter count')
    model.requires_grad_(False)
    model.eval()
    return model


def dev_indices(store, np, rows=ROWS, dev_rows=DEV_ROWS):
    require(store.n == rows and len(store.split) == rows, 'wrong total rows')
    idx = np.flatnonzero(store.split == 1)
    require(len(idx) == dev_rows, 'wrong full DEV row count')
    return idx


class DevOnly:
    """The reviewed functions can batch DEV only; they cannot request FINAL labels."""
    def __init__(self, store, np):
        self.store, self.np = store, np

    def batch(self, idx):
        idx = self.np.asarray(idx)
        require(idx.ndim == 1 and len(idx) > 0 and bool((idx >= 0).all()) and
                bool((idx < self.store.n).all()), 'invalid batch indices')
        require(bool((self.store.split[idx] == 1).all()), 'refuse non-DEV batch')
        b = self.store.batch(idx)
        for value in b.values():
            if self.np.issubdtype(value.dtype, self.np.number):
                require(bool(self.np.isfinite(value).all()), 'nonfinite DEV input')
        return b


def finite_report(value):
    if isinstance(value, dict):
        for v in value.values():
            finite_report(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            finite_report(v)
    elif isinstance(value, float):
        require(math.isfinite(value), 'nonfinite metrics/calibration')


def measure(model, store, idx, train, device):
    # Unchanged reviewed code. Fitted scalar is temporary and never exported.
    raw = train.evaluate(model, store, idx, device, bs=512)
    bias, before, after = train.fit_gate_bias(model, store, idx, device, bs=512)
    fitted = train.evaluate(model, store, idx, device, bs=512, gate_bias=bias)
    result = dict(raw=raw, in_memory_dev_calibrated=fitted,
                  unselected_gate_bias=bias, unselected_gate_bce=[before, after])
    finite_report(result)
    return result


def identity(s):
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink


def evaluate_candidate(c, store, idx, modules, torch, device):
    p = plain_path(c['path'])
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        s = os.fstat(f.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size == c['bytes'], 'unsafe/incomplete checkpoint')
        require(hash_stream(f) == c['sha256'], 'checkpoint SHA mismatch')
        f.seek(0)
        model = checkpoint_model(f, c, modules, torch).to(device)
        result = measure(model, store, idx, modules['train_bc'], device)
        del model
        f.seek(0)
        require(hash_stream(f) == c['sha256'] and identity(os.fstat(f.fileno())) == identity(s) and identity(p.stat()) == identity(s),
                'checkpoint changed during evaluation')
    return dict(candidate=c, metrics=result)


def write_report(out, inventory_sha, results, peak):
    report = dict(purpose='unselected-DEV-PREVIEW', complete=True, selected=False,
                  source_commit=SOURCE, feature_hash=FEATURE, manifest_sha256=MANIFEST,
                  inventory_sha256=inventory_sha, rows=ROWS, dev_rows=DEV_ROWS,
                  gpu_peak_reserved_gib=peak, candidates=results,
                  calibration='DEV-fitted scalar for diagnostic metrics only; no artifact exported')
    finite_report(report)
    with (out/'unselected-dev-preview.json').open('x') as f:
        f.write(json.dumps(report, indent=2, allow_nan=False)+'\n')
    os.chmod(out/'unselected-dev-preview.json', 0o600)


def load_inventory(path, expected):
    require(sha256(path) == digest(expected), 'inventory SHA mismatch')
    return validate_inventory(json.loads(Path(path).read_text()))


def reserve_output(path):
    out = plain_path(path)
    require(out.parent == JOB/'outputs', 'output must be a new private preview directory')
    out.mkdir(mode=0o700)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inventory', required=True)
    ap.add_argument('--inventory-sha256', required=True)
    ap.add_argument('--source-map', required=True)
    ap.add_argument('--store-map', required=True)
    ap.add_argument('--env-map', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    d = load_inventory(a.inventory, a.inventory_sha256)
    verify_collection_receipt(d)
    # Exclusive mkdir refuses retries, existing outputs, aliases and promotion paths.
    out = reserve_output(a.out)
    verify_map(Path(d['source_root']), a.source_map, MAPS['source'], 73)
    verify_map(Path(d['store']), a.store_map, MAPS['store'], 6241)
    require(sha256(Path(d['store'])/'MANIFEST.jsonl') == MANIFEST, 'store manifest mismatch')
    require(sys.version_info[:2] == (3, 12), 'requires READY Python 3.12')
    env_root = Path('/mpac/sdicks02/repos/clasher-bc-supplemental-40ea-20261022/env')
    require(Path(sys.executable) == env_root/'python/bin/python3.12' and
            os.environ.get('PYTHONHOME') == str(env_root/'python'), 'wrong READY Python path/home')
    verify_map(env_root, a.env_map, ENV_MAP, 20303)
    import numpy as np
    import torch
    require(torch.__version__ == '2.7.1+cu118' and np.__version__ == '2.3.5', 'wrong READY runtime')
    torch.set_num_threads(3)
    torch.set_num_interop_threads(1)
    modules = import_reviewed(Path(d['source_root']))
    # Refuse malformed CPU weights before allocating CUDA or loading the 17 GB store.
    for c in d['candidates']:
        p = plain_path(c['path'])
        require(p.is_file() and p.stat().st_nlink == 1 and p.stat().st_size == c['bytes'] and
                sha256(p) == c['sha256'], 'preflight checkpoint bytes/SHA mismatch')
        with p.open('rb') as f:
            checkpoint_model(f, c, modules, torch)
    # Preserve R5 fraction against its nominal GPU, allowing >8 GiB physical headroom on 14.
    torch.cuda.set_per_process_memory_fraction(37.5 / 47.98828125, device=0)
    store = modules['train_bc'].Store(d['store'])
    idx = dev_indices(store, np)
    only_dev = DevOnly(store, np)
    results = [evaluate_candidate(c, only_dev, idx, modules, torch, 'cuda:0') for c in d['candidates']]
    require(sha256(a.inventory) == a.inventory_sha256, 'inventory changed')
    write_report(out, a.inventory_sha256, results, torch.cuda.max_memory_reserved()/2**30)


if __name__ == '__main__':
    main()
