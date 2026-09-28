"""Authority for one full-size exact replay, without selecting new model settings."""

import json
from pathlib import Path

from value_contract import OUTPUT as SERIAL
from value_contract import PLAN as ORIGINAL_PLAN
from value_contract import ROOT, load_plan, publish, sha

PLAN = ROOT / 'reports/hog26_tree_state_replay_plan_20260913.json'
OUTPUT = ROOT / 'reports/hog26_tree_state_replay_20260913'
REFERENCE = SERIAL / 'trees/seed1279501-fold0'


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    original = load_plan()
    control_path = ROOT / 'reports/hog26_tree_state_serialization_control_20260913.json'
    control = json.loads(control_path.read_text())
    if (control['status'] != 'complete-unchanged-estimator-serialization-control'
            or not all(row['all_fields_exact'] for row in control['controls'].values())
            or control['learned_fields_ignored'] != []
            or control['checker_sha256'] != sha(Path(__file__).parent / 'state_fields.py')):
        raise ValueError('unchanged-model field serialization control required')
    handoff_path = ROOT / 'reports/hog26_tree_thread_serial_reference_20260913.json'
    handoff = json.loads(handoff_path.read_text())
    if (handoff['status'] != 'serial-reference-complete-supervisor-intentionally-retired'
            or handoff['original_plan_sha256'] != sha(ORIGINAL_PLAN)
            or handoff['complete_tree_sha256'] != sha(REFERENCE / 'complete.json')):
        raise ValueError('complete preserved serial reference required')
    reference = json.loads((REFERENCE / 'complete.json').read_text())
    if reference['status'] != 'complete-expanded-value-fold' or reference['seed'] != 1279501 or reference['fold'] != 0:
        raise ValueError('reference model identity differs')
    paths = [ORIGINAL_PLAN, handoff_path, control_path,
             ROOT / 'reports/hog26_tree_full_thread_replay_plan_20260913.json',
             ROOT / 'reports/hog26_tree_full_thread_replay_guard_20260913.json',
             ROOT / 'reports/hog26_tree_full_thread_replay_20260913/classifier-state.json', ROOT / 'reports/hog26_tree_thread_handoff_pin_20260913.json',
             ROOT / 'reports/hog26_tree_thread_synthetic_probe_20260913.json',
             ROOT / 'reports/hog26_tree_thread_synthetic_probe_20260913.receipt.json',
             ROOT / 'reports/hog26_tree_thread_synthetic_probe_20260913.pin.json',
             ROOT / 'experiments/hog26_tree_thread_probe/probe.py']
    paths += list(REFERENCE.iterdir())
    resources = {str(path.relative_to(ROOT)): sha(path) for path in paths if path.is_file()}
    for name, expected in reference['artifacts'].items():
        if sha(REFERENCE / name) != expected:
            raise ValueError('reference artifact changed')
    native_pin = json.loads((ROOT / 'reports/hog26_tree_thread_synthetic_probe_20260913.pin.json').read_text())
    resources.update(native_pin['sources'])
    for path, expected in resources.items():
        if sha(ROOT / path) != expected:
            raise ValueError('replay prerequisite changed')
    publish(PLAN, {'schema': 'clasher.hog26.full-tree-state-replay.v1', 'sources': sources(), 'resources': resources,
                   'original_runtime': original.runtime, 'seed': 1279501, 'fold': 0, 'tree_fit_openmp_threads': 8,
                   'iterations': 100, 'same_model_data_objectives': True, 'full_prediction_rows': 2465152,
                   'only_normalized_state_field': 'copied_estimator._bin_mapper.n_threads',
                   'state_comparison': 'all individually serialized estimator fields; no learned fields ignored',
                   'prior_failure': 'Whole-object pickle memoization rejected an unchanged model after serialization; that failed replay remains preserved.',
                   'remaining_fits_allowed': False, 'acceptance': False})
    print(json.dumps({'status': 'full-thread-replay-pinned', 'sha256': sha(PLAN)}), flush=True)


def validate():
    load_plan()
    plan = json.loads(PLAN.read_text())
    if (plan['schema'] != 'clasher.hog26.full-tree-state-replay.v1' or plan['sources'] != sources()
            or plan['seed'] != 1279501 or plan['fold'] != 0 or plan['tree_fit_openmp_threads'] != 8
            or plan['iterations'] != 100 or plan['remaining_fits_allowed'] is not False or plan['acceptance'] is not False):
        raise ValueError('frozen replay contract differs')
    for path, expected in plan['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('replay resource changed: ' + path)
    return plan
