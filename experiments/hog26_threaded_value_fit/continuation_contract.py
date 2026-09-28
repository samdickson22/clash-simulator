"""Continue the fixed model comparison only after exact full-size thread replay."""

import json
from pathlib import Path

from value_contract import OUTPUT as SERIAL
from value_contract import PLAN as ORIGINAL_PLAN
from value_contract import ROOT, load_plan, publish, sha

PLAN = ROOT / 'reports/hog26_threaded_value_continuation_plan_20260913.json'
OUTPUT = ROOT / 'reports/hog26_expanded_value_threaded_comparison_20260913'
REPLAY = ROOT / 'reports/hog26_tree_state_replay_20260913'


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    original = load_plan()
    replay_path = REPLAY / 'complete.json'
    replay = json.loads(replay_path.read_text())
    guard_path = ROOT / 'reports/hog26_tree_state_replay_guard_20260913.json'
    guard = json.loads(guard_path.read_text())
    if (replay['status'] != 'complete-exact-full-tree-thread-replay' or replay['full_prediction_rows'] != 2465152
            or guard['exit_code'] != 0 or guard['memory_limit_terminated']
            or max(replay['peak_rss_bytes'], guard['peak_rss_bytes']) + 2 * 1024**3 > 18 * 1024**3
            or set(replay['components']) != {'classifier', 'regressor'}
            or set(replay['prediction_arrays']) != {'probabilities', 'margin'}
            or replay['prediction_arrays']['probabilities']['shape'] != [2465152, 3]
            or replay['prediction_arrays']['margin']['shape'] != [2465152]
            or not all(row['exact_normalized_state'] for row in replay['components'].values())):
        raise ValueError('full-size exact state, prediction, and memory replay required')
    for name, expected in replay['artifacts'].items():
        if sha(REPLAY / name) != expected:
            raise ValueError('thread replay artifact changed')
    replay_plan_path = ROOT / 'reports/hog26_tree_state_replay_plan_20260913.json'
    if replay['plan_sha256'] != sha(replay_plan_path) or guard['plan_sha256'] != sha(replay_plan_path):
        raise ValueError('thread replay authority differs')
    replay_plan = json.loads(replay_plan_path.read_text())
    resources = {**replay_plan['resources'], **replay_plan['sources']}
    paths = [ORIGINAL_PLAN, replay_path, guard_path, replay_plan_path, *REPLAY.iterdir()]
    paths += list((SERIAL / 'globals').rglob('*'))
    paths += list((SERIAL / 'trees/seed1279501-fold0').iterdir())
    resources.update({str(path.relative_to(ROOT)): sha(path) for path in paths if path.is_file()})
    for path, expected in resources.items():
        if sha(ROOT / path) != expected:
            raise ValueError('continuation prerequisite changed')
    publish(PLAN, {'schema': 'clasher.hog26.threaded-value-continuation.v1', 'sources': sources(), 'resources': resources,
                   'original_model_plan_sha256': sha(ORIGINAL_PLAN), 'original_runtime': original.runtime,
                   'tree_fit_openmp_threads': 8, 'seeds': [1279501, 1279502], 'folds': 4,
                   'reuse': 'Eight completed serial globals; exact eight-thread replay tree at seed1279501/fold0, with identical reference statistics.',
                   'remaining_tree_pairs': 7, 'reserved_memory_headroom_bytes': 2 * 1024**3, 'model_hyperparameters_changed': False, 'data_roles_changed': False,
                   'opened_diagnostic_allowed': False, 'acceptance': False,
                   'scope': 'Thread execution and artifact location change only. Full numerical equality is measured on the complete reference fold, with source-level stable ordering and additional synthetic cases; no model-quality selection.'})
    print(json.dumps({'status': 'threaded-continuation-pinned', 'sha256': sha(PLAN)}), flush=True)


def validate():
    original = load_plan()
    plan = json.loads(PLAN.read_text())
    if (plan['schema'] != 'clasher.hog26.threaded-value-continuation.v1' or plan['sources'] != sources()
            or plan['original_model_plan_sha256'] != sha(ORIGINAL_PLAN) or plan['original_runtime'] != original.runtime
            or plan['tree_fit_openmp_threads'] != 8 or plan['seeds'] != [1279501, 1279502] or plan['folds'] != 4
            or plan['remaining_tree_pairs'] != 7 or plan['model_hyperparameters_changed'] is not False
            or plan['reserved_memory_headroom_bytes'] != 2 * 1024**3 or plan['opened_diagnostic_allowed'] is not False
            or plan['data_roles_changed'] is not False or plan['acceptance'] is not False):
        raise ValueError('thread continuation contract differs')
    for path, expected in plan['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('continuation resource changed: ' + path)
    return plan
