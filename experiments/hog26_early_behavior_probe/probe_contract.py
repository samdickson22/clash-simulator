"""Freeze a training-only information probe; no outcome model is updated."""

import json
from pathlib import Path

from probe_data import load_data
from value_contract import ROOT, publish, runtime, sha
from value_models import TREE_SETTINGS

PLAN = ROOT / 'reports/hog26_early_behavior_probe_plan_20260913.json'
MEMORY = ROOT / 'reports/hog26_early_behavior_probe_memory_20260913.json'
MEMORY_GUARD = ROOT / 'reports/hog26_early_behavior_probe_memory_guard_20260913.json'
OUTPUT = ROOT / 'reports/hog26_early_behavior_probe_20260913'
SEEDS = (1280401, 1280402)


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    data = load_data()
    paths = [ROOT / 'reports/hog26_public_history_cache_plan_20260913.json',
             ROOT / 'reports/hog26_public_history_cache_20260913/complete.json',
             ROOT / 'reports/hog26_public_history_cache_guard_20260913.json',
             ROOT / 'reports/hog26_expanded_error_localization_20260913.json',
             ROOT / 'experiments/hog26_expanded_value_fit/value_models.py',
             ROOT / 'experiments/hog26_expanded_tree_value/health_features.py',
             ROOT / 'experiments/hog26_scalar_pilot/scalar_evaluation.py']
    for directory in ('hog26_public_history', 'hog26_history_cache'):
        paths += list((ROOT / 'experiments' / directory).glob('*.py'))
    publish(PLAN, {'schema': 'clasher.hog26.early-public-behavior-probe.v1', 'sources': sources(),
                   'resources': {str(path.relative_to(ROOT)): sha(path) for path in paths}, 'data_audit': data.audit,
                   'representations': {'base_public': 814, 'entity_history': 911}, 'seeds': list(SEEDS), 'folds': 4,
                   'target': 'bridge-pressure versus the other five simulated styles; metadata is a target only',
                   'tree_settings': TREE_SETTINGS, 'runtime': runtime(), 'training_weight': 'one equal-weight early representative per complete game',
                   'models': 16, 'fixed_iterations': 100, 'memory_required_before_fitting': True,
                   'outcome_fitting': False, 'auxiliary_prediction_as_outcome_input': False, 'acceptance': False,
                   'scope': 'Training-only evidence about usable public temporal information, not full-phase or outcome calibration. No private style label enters an input and no opened diagnostic data is accessed.'})
    print(json.dumps({'status': 'early-behavior-probe-pinned', 'sha256': sha(PLAN)}), flush=True)


def validate(*, require_memory=False):
    plan = json.loads(PLAN.read_text())
    if (plan['schema'] != 'clasher.hog26.early-public-behavior-probe.v1' or plan['sources'] != sources()
            or plan['seeds'] != list(SEEDS) or plan['folds'] != 4 or plan['models'] != 16
            or plan['representations'] != {'base_public': 814, 'entity_history': 911}
            or plan['tree_settings'] != TREE_SETTINGS or plan['runtime'] != runtime()
            or plan['outcome_fitting'] is not False or plan['auxiliary_prediction_as_outcome_input'] is not False
            or plan['acceptance'] is not False):
        raise ValueError('fixed auxiliary information-probe contract differs')
    for path, expected in plan['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('auxiliary prerequisite changed: ' + path)
    if require_memory:
        result = json.loads(MEMORY.read_text())
        guard = json.loads(MEMORY_GUARD.read_text())
        if (result['status'] != 'complete-early-behavior-synthetic-memory' or result['plan_sha256'] != sha(PLAN)
                or result['shape'] != [6144, 911] or result['real_labels_used'] or result['checkpoint_saved']
                or guard['exit_code'] != 0 or guard['memory_limit_terminated'] or guard['plan_sha256'] != sha(PLAN)
                or max(result['peak_rss_bytes'], guard['peak_rss_bytes']) > 18 * 1024**3):
            raise ValueError('full-shape synthetic auxiliary memory proof required')
    return plan
