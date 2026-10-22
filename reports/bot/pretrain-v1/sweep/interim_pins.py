"""Enforce independently reviewed launch bytes and recorded runtime before each spawn."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def runtime():
    files = {'python': sha(Path(sys.executable).resolve())}
    versions = {}
    for name in ('numpy', 'torch'):
        module = importlib.import_module(name)
        versions[name] = module.__version__
        files[name] = sha(module.__file__)
    import numpy._core._multiarray_umath as multi
    import torch._C as tc
    files['numpy-core'] = sha(multi.__file__)
    files['torch-C'] = sha(tc.__file__)
    return dict(python=sys.version, versions=versions, files=files)


def verify(code):
    path = Path(os.environ['PV1_LAUNCH_PIN'])
    assert sha(path) == os.environ['PV1_LAUNCH_PIN_SHA256'], 'launch pin changed'
    d = json.loads(path.read_text())
    assert d['base_commit'] == '7f3b1cbaa9d1ee33d59faed4e5f9e9bfd9f4f305'
    for name, digest in d['files'].items():
        assert sha(code/name) == digest, 'reviewed source changed: '+name
    host = os.uname().nodename.split('.')[0]
    assert runtime() == d['runtimes'][host], 'runtime changed'
    return dict(sha256=sha(path), base_commit=d['base_commit'], reviewed_diff_sha256=d['reviewed_diff_sha256'])


def host_ok(min_gib, max_load):
    avail = next(int(l.split()[1])/2**20 for l in Path('/proc/meminfo').read_text().splitlines()
                 if l.startswith('MemAvailable:'))
    return avail >= min_gib and os.getloadavg()[0] < max_load
