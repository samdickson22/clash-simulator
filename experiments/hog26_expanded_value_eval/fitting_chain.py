"""Bind evaluation authority to the exact checkpoints covered by completed reviews."""

import json
from pathlib import Path

from value_contract import sha


def audit_fold(directory, *, completion_sha256, kind, seed, fold, model_plan_sha256):
    directory = Path(directory)
    complete_path = directory / 'complete.json'
    if sha(complete_path) != completion_sha256:
        raise ValueError('reviewed fold completion changed')
    complete = json.loads(complete_path.read_text())
    if (complete['status'] != 'complete-expanded-value-fold' or complete['kind'] != kind
            or complete['seed'] != seed or complete['fold'] != fold or complete['plan_sha256'] != model_plan_sha256):
        raise ValueError('reviewed fold identity differs')
    if {p.name for p in directory.iterdir()} != set(complete['artifacts']) | {'complete.json'}:
        raise ValueError('reviewed fold inventory differs')
    for name, expected in complete['artifacts'].items():
        if sha(directory / name) != expected:
            raise ValueError('reviewed checkpoint or report changed')
