"""Frozen source and evidence authority for expanded public outcome fits."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'reports/hog26_expanded_value_frozen_plan_20260913.json'
CACHE = ROOT / 'reports/hog26_expanded_feature_cache_20260913'
OUTPUT = ROOT / 'reports/hog26_expanded_value_comparison_20260913'


class ValuePlan(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schema_id: Literal['clasher.hog26.expanded-value.v1']
    games: Literal[6144]
    rows: Literal[2465152]
    features: Literal[814]
    seeds: tuple[Literal[1279501], Literal[1279502]]
    folds: Literal[4]
    globals_epochs: Literal[30]
    batch_rows: Literal[512]
    tree_iterations: Literal[100]
    implementation: dict[str, str]
    resources: dict[str, str]
    runtime: dict[str, str | int]
    fitting_allowed: Literal[True]
    opened_diagnostic_allowed: Literal[False]
    reserved_collection_allowed: Literal[False]
    policy_updates_allowed: Literal[False]
    acceptance: Literal[False]
    interpretation: list[str]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def runtime():
    import platform
    import sys

    import numpy as np
    import torch

    sys.path.insert(0, '/Users/sam/.cache/clasher-margin-tree-diagnostic')
    import sklearn

    return {'python': platform.python_version(), 'numpy': np.__version__, 'torch': torch.__version__,
            'sklearn': sklearn.__version__, 'device': 'cpu', 'threads': torch.get_num_threads()}


def load_plan():
    plan = ValuePlan.model_validate_json(PLAN.read_text())
    if plan.implementation != sources() or plan.runtime != runtime():
        raise ValueError('frozen model source or runtime differs')
    for path, expected in plan.resources.items():
        if sha(ROOT / path) != expected:
            raise ValueError('frozen resource changed: ' + path)
    return plan


def publish(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
