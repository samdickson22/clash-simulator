"""Bind every phase checkpoint to the exact reviewed fold completion."""

import json
from pathlib import Path

from value_contract import sha


def audit_phase_fold(directory, *, completion_sha256, seed, fold, plan_sha256):
    directory = Path(directory)
    path = directory / 'complete.json'
    if sha(path) != completion_sha256:
        raise ValueError('reviewed phase completion changed')
    result = json.loads(path.read_text())
    names = {'manifest.json', 'phase0.pkl', 'phase1.pkl', 'phase2.pkl', 'predictions.npz', 'report.json'}
    if (result['status'] != 'complete-phase-margin-fold' or result['seed'] != seed or result['fold'] != fold
            or result['plan_sha256'] != plan_sha256 or set(result['artifacts']) != names
            or {p.name for p in directory.iterdir()} != names | {'complete.json'}):
        raise ValueError('reviewed phase fold identity or inventory differs')
    for name, expected in result['artifacts'].items():
        if sha(directory / name) != expected:
            raise ValueError('reviewed phase checkpoint or report changed')
    return {str(path): completion_sha256, **{str(directory / name): value for name, value in result['artifacts'].items()}}
