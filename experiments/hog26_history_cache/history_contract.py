"""Frozen authority for a public-history feature cache, with no model fitting."""

import json
from pathlib import Path

from history_features import LAGS, history_names, observable_names
from value_contract import CACHE, ROOT, publish, sha

PLAN = ROOT / 'reports/hog26_public_history_cache_plan_20260913.json'
OUTPUT = ROOT / 'reports/hog26_public_history_cache_20260913'
AUDIT_GAMES = (0, 127, 255, 383, 384, 767, 1023, 1535, 1536, 3071, 4095, 6143)


def sources():
    directories = (Path(__file__).parent, ROOT / 'experiments/hog26_public_history')
    return {str(path.relative_to(ROOT)): sha(path) for directory in directories for path in sorted(directory.glob('*.py'))}


def prepare():
    complete_path = CACHE / 'complete.json'
    complete = json.loads(complete_path.read_text())
    if complete['status'] != 'complete-audited-expanded-feature-cache' or complete['games'] != 6144 or complete['rows'] != 2465152:
        raise ValueError('complete public base cache required')
    paths = [complete_path, CACHE / 'rows.npz', ROOT / 'reports/hog26_expanded_feature_plan_20260913.json',
             ROOT / 'reports/hog26_expanded_cache_review_20260913.json',
             ROOT / 'reports/hog26_expanded_error_localization_20260913.json',
             ROOT / 'experiments/hog26_streamed_features/feature_store.py']
    paths += list((ROOT / 'experiments/hog26_expanded_corpus').glob('*.py'))
    publish(PLAN, {'schema': 'clasher.hog26.public-history-cache.v1', 'sources': sources(),
                   'resources': {str(path.relative_to(ROOT)): sha(path) for path in paths},
                   'base_feature_sha256': complete['cache']['sha256'], 'base_shape': [2465152, 809],
                   'history_columns': 97, 'observables': list(observable_names()), 'lags': list(LAGS),
                   'names': list(history_names()), 'streaming_audit_games': list(AUDIT_GAMES),
                   'random_read_seed': 1280301, 'random_read_rows': 512,
                   'fitting': False, 'acceptance': False,
                   'scope': 'Full public-input feature extraction. Existing global resource history stays unchanged; new features extend history to observed entity summaries. Game boundaries are used only to reset state.'})
    print(json.dumps({'status': 'public-history-cache-pinned', 'sha256': sha(PLAN)}), flush=True)


def validate():
    plan = json.loads(PLAN.read_text())
    if (plan['schema'] != 'clasher.hog26.public-history-cache.v1' or plan['sources'] != sources()
            or plan['base_shape'] != [2465152, 809] or plan['history_columns'] != 97
            or plan['observables'] != list(observable_names()) or plan['lags'] != list(LAGS)
            or plan['names'] != list(history_names()) or plan['streaming_audit_games'] != list(AUDIT_GAMES)
            or plan['random_read_seed'] != 1280301 or plan['random_read_rows'] != 512
            or plan['fitting'] is not False or plan['acceptance'] is not False):
        raise ValueError('public history cache authority differs')
    for path, expected in plan['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('history cache prerequisite changed: ' + path)
    return plan
