"""A separate encoding-only audit on fixed training games, without model fitting."""

import json
from pathlib import Path

import numpy as np
from body_features import feature_names as physical_names
from body_stats import compile_body_table
from cache_reader import read_complete_cache
from health_features import make_layout as health_layout
from residual_features import make_layout
from semantic_contract import FrozenPlan
from value_contract import CACHE, ROOT, publish, sha

PIN = ROOT / 'reports/hog26_online_value_features_pin_20260913.json'
RESULT = ROOT / 'reports/hog26_online_value_features_audit_20260913.json'
FEATURE_PLAN = ROOT / 'reports/hog26_semantic_margin_frozen_plan_20260912.json'


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def configuration():
    plan = FrozenPlan.model_validate_json(FEATURE_PLAN.read_text())
    layout = make_layout(len(plan.data.vocabulary), plan.data.hand_tokens)
    table = compile_body_table(plan.data.vocabulary)
    names = (*layout.names, *physical_names())
    if names != tuple(json.loads((CACHE / 'complete.json').read_text())['feature_names']):
        raise ValueError('online configuration differs from complete809-column cache')
    return layout, table, health_layout(names)


def prepare():
    mapped, evaluation, complete, _ = read_complete_cache(CACHE)
    mapped._mmap.close()
    del evaluation
    configuration()
    selected = np.linspace(0, 6143, 16, dtype=np.int64).tolist()
    paths = [FEATURE_PLAN, CACHE / 'complete.json', CACHE / 'rows.npz']
    for directory in ('hog26_public_semantics', 'hog26_residual_margin', 'hog26_scalar_pilot', 'hog26_expanded_tree_value'):
        paths += list((ROOT / 'experiments' / directory).glob('*.py'))
    resources = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    games = []
    for index in selected:
        record = complete['game_records'][index]
        if sha(record['path']) != record['sha256']:
            raise ValueError('selected raw training game changed')
        games.append({'index': index, 'path': record['path'], 'sha256': record['sha256'], 'rows': record['rows']})
    publish(PIN, {'schema': 'clasher.hog26.online-value-features.v1', 'sources': sources(), 'resources': resources,
                  'base_cache_sha256': complete['cache']['sha256'], 'games': games, 'history_frames': 20, 'features': 814,
                  'scope': 'Encoding-only parity on16 preselected complete training games. No labels or metadata enter the encoder. This verifies the existing audited public payload, not a new visibility mask or live policy.',
                  'fitting': False, 'acceptance': False})
    print(json.dumps({'status': 'online-feature-audit-pinned', 'sha256': sha(PIN)}), flush=True)


def validate():
    pin = json.loads(PIN.read_text())
    if (pin['schema'] != 'clasher.hog26.online-value-features.v1' or pin['sources'] != sources()
            or pin['history_frames'] != 20 or pin['features'] != 814 or pin['fitting'] or pin['acceptance']
            or [game['index'] for game in pin['games']] != np.linspace(0, 6143, 16, dtype=np.int64).tolist()):
        raise ValueError('online encoding audit authority differs')
    for path, expected in pin['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('online encoding resource changed: ' + path)
    for game in pin['games']:
        if sha(game['path']) != game['sha256']:
            raise ValueError('online encoding raw game changed')
    return pin
