"""A fixed early-point margin assay, not a full-phase candidate."""

import json
from pathlib import Path

from margin_data import load_data
from value_contract import ROOT, publish, runtime, sha
from value_models import TREE_SETTINGS

PLAN = ROOT / 'reports/hog26_early_margin_probe_plan_20260913.json'
MEMORY = ROOT / 'reports/hog26_early_margin_probe_memory_20260913.json'
OUTPUT = ROOT / 'reports/hog26_early_margin_probe_20260913'
SEED = 1280501


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    data = load_data()
    paths = [ROOT / 'reports/hog26_early_behavior_probe_review_20260913.json',
             ROOT / 'reports/hog26_expanded_error_localization_20260913.json',
             ROOT / 'reports/hog26_public_history_cache_plan_20260913.json',
             ROOT / 'reports/hog26_public_history_cache_20260913/complete.json',
             ROOT / 'reports/hog26_threaded_value_scientific_review_20260913.json',
             ROOT / 'reports/hog26_expanded_value_threaded_comparison_20260913/complete.json',
             ROOT / 'experiments/hog26_expanded_value_fit/value_models.py',
             ROOT / 'experiments/hog26_expanded_tree_value/health_features.py']
    for directory in ('hog26_early_behavior_probe', 'hog26_public_history', 'hog26_history_cache'):
        paths += list((ROOT / 'experiments' / directory).glob('*.py'))
    resources = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    resources.update(data.audit['reference_resources'])
    publish(PLAN, {'schema': 'clasher.hog26.focused-early-margin.v1', 'sources': sources(), 'resources': resources,
                   'data_audit': data.audit, 'representations': {'base_public': 814, 'entity_history': 911},
                   'seed': SEED, 'folds': 4, 'fits': 8, 'tree_settings': TREE_SETTINGS, 'loss': 'absolute_error',
                   'runtime': runtime(), 'objective': 'equal-game early-representative absolute terminal-minus-current margin',
                   'seed_scope': 'One fixed seed: this small full-binned, all-feature learner is deterministic; duplicate seeds do not provide independent replication.',
                   'scope': 'Training-only early-point assay. Both representations use identical points and learner settings. Comparisons with full-training references also change sample/phase allocation and binning; they do not isolate a cause.',
                   'full_phase_candidate': False, 'policy_updates_allowed': False, 'acceptance': False})
    print(json.dumps({'status': 'early-margin-assay-pinned', 'sha256': sha(PLAN)}), flush=True)


def validate(*, memory=False):
    plan = json.loads(PLAN.read_text())
    if (plan['schema'] != 'clasher.hog26.focused-early-margin.v1' or plan['sources'] != sources()
            or plan['seed'] != SEED or plan['folds'] != 4 or plan['fits'] != 8 or plan['tree_settings'] != TREE_SETTINGS
            or plan['loss'] != 'absolute_error' or plan['runtime'] != runtime()
            or plan['representations'] != {'base_public': 814, 'entity_history': 911}
            or plan['full_phase_candidate'] is not False or plan['policy_updates_allowed'] is not False or plan['acceptance'] is not False):
        raise ValueError('focused margin assay authority differs')
    for path, expected in plan['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('focused assay resource changed: ' + path)
    if memory:
        check = json.loads(MEMORY.read_text())
        guard = json.loads((ROOT / 'reports/hog26_early_margin_probe_memory_guard_20260913.json').read_text())
        if (check['status'] != 'complete-focused-margin-synthetic-memory' or check['plan_sha256'] != sha(PLAN)
                or check['shape'] != [6144, 911] or check['real_targets_used'] or check['checkpoint_saved']
                or guard['exit_code'] != 0 or guard['memory_limit_terminated'] or guard['plan_sha256'] != sha(PLAN)
                or max(check['peak_rss_bytes'], guard['peak_rss_bytes']) > 18 * 1024**3):
            raise ValueError('full-shape synthetic memory prerequisite required')
    return plan
