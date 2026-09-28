"""Separate all-eight inference authority for the permanently opened diagnostic."""

import json
from pathlib import Path

from evaluation_authority import PIN as OLD_PIN
from evaluation_authority import validate_pin as validate_old_pin
from phase_contract import OUTPUT as MODELS
from phase_contract import PLAN as MODEL_PLAN
from phase_contract import SEEDS, validate
from phase_eval_chain import audit_phase_fold
from value_contract import ROOT, publish, sha

PIN = ROOT / 'reports/hog26_phase_margin_evaluation_pin_20260913.json'
DESTINATION = ROOT / 'reports/hog26_phase_margin_seed_transfer_20260913'
REVIEW = ROOT / 'reports/hog26_phase_margin_diagnostic_review_20260913.json'
OLD_DIAGNOSTIC = ROOT / 'reports/hog26_expanded_value_seed_transfer_20260913'


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def prepare_pin():
    model_plan = validate(memory=True)
    validate_old_pin(json.loads(OLD_PIN.read_text()))
    complete_path = MODELS / 'complete.json'
    complete = json.loads(complete_path.read_text())
    science_path = MODELS / 'scientific-review.json'
    science = json.loads(science_path.read_text())
    if (complete['status'] != 'complete-phase-margin-comparison' or complete['plan_sha256'] != sha(MODEL_PLAN)
            or complete['regressor_fits'] != 24 or complete['unchanged_global_references'] != 8
            or complete['scientific_review_sha256'] != sha(science_path)
            or science['status'] != 'complete-phase-margin-scientific-review' or science['plan_sha256'] != sha(MODEL_PLAN)):
        raise ValueError('complete phase exact and scientific review required')
    schedule_path = ROOT / 'reports/hog26_phase_parallel_review_plan_20260913.json'
    schedule = json.loads(schedule_path.read_text())
    scheduler = ROOT / 'experiments/hog26_phase_parallel_review/supervise.py'
    if (complete['review_schedule_plan_sha256'] != sha(schedule_path) or schedule['source_sha256'] != sha(scheduler)
            or schedule['worker_threads'] != 1 or schedule['aggregate_memory_limit_bytes'] != 18 * 1024**3
            or schedule['worker_source_sha256'] != model_plan['sources']['experiments/hog26_phase_margin/review_phase.py']):
        raise ValueError('phase review scheduling authority differs')
    resources = dict(schedule['resources'])
    for seed in SEEDS:
        path = MODELS / f'seed{seed}-review.json'
        oof = MODELS / f'seed{seed}-oof.npz'
        review = json.loads(path.read_text())
        if (sha(path) != science['resources'][path.name] or review['status'] != 'complete-exact-phase-margin-review'
                or review['seed'] != seed or review['plan_sha256'] != sha(MODEL_PLAN)
                or set(review['audited_folds']) != {'0', '1', '2', '3'}
                or review['oof_sha256'] != sha(oof) or sha(oof) != science['resources'][oof.name]):
            raise ValueError('phase reviewed OOF authority differs')
        resources[str(path.relative_to(ROOT))], resources[str(oof.relative_to(ROOT))] = sha(path), sha(oof)
        for fold in range(4):
            chain = audit_phase_fold(MODELS / f'seed{seed}-fold{fold}', completion_sha256=review['audited_folds'][str(fold)],
                                     seed=seed, fold=fold, plan_sha256=sha(MODEL_PLAN))
            resources.update({str(Path(path).relative_to(ROOT)): expected for path, expected in chain.items()})
    old_review_path = ROOT / 'reports/hog26_expanded_value_diagnostic_review_20260913.json'
    old_review = json.loads(old_review_path.read_text())
    old_complete_path = OLD_DIAGNOSTIC / 'complete.json'
    old_complete = json.loads(old_complete_path.read_text())
    if (old_review['status'] != 'complete-expanded-value-diagnostic-review' or old_review['fits'] != 16
            or old_review['completion_sha256'] != sha(old_complete_path)
            or not all(old_review[k] for k in ('checkpoint_predictions_exact', 'point_metrics_exact', 'paired_intervals_exact'))
            or old_complete['status'] != 'complete-expanded-value-diagnostic' or old_complete['pin_sha256'] != sha(OLD_PIN)):
        raise ValueError('exact old diagnostic reference review required')
    for name, expected in old_complete['artifacts'].items():
        resources[str((OLD_DIAGNOSTIC / name).relative_to(ROOT))] = expected
    paths = [MODEL_PLAN, complete_path, science_path, schedule_path, scheduler, OLD_PIN, old_review_path, old_complete_path,
             ROOT / 'reports/hog26_phase_margin_conclusion_20260913.json',
             ROOT / 'reports/hog26_phase_boundary_audit_20260913.json',
             ROOT / 'reports/hog26_expanded_value_diagnostic_guard_20260913.json']
    for directory in ('hog26_phase_margin', 'hog26_expanded_value_eval', 'hog26_scaling_review'):
        paths += list((ROOT / 'experiments' / directory).glob('*.py'))
    resources.update({str(path.relative_to(ROOT)): sha(path) for path in paths})
    for path, expected in resources.items():
        if sha(ROOT / path) != expected:
            raise ValueError('phase diagnostic resource changed: ' + path)
    publish(PIN, {'schema': 'clasher.hog26.phase-value-diagnostic.v1', 'sources': sources(), 'resources': resources,
                  'fits': 8, 'seeds': list(SEEDS), 'folds': 4, 'all_fits_reviewed': True,
                  'fitting': False, 'selection': False, 'calibration': False, 'acceptance': False,
                  'groups': {'fresh_seen_families': 288, 'fresh_excluded_families': 96},
                  'paired_references': 'Current margin and reviewed full-training tree margin; WDL is identical expanded globals in both contrasts.',
                  'bootstrap_replicates': 2000, 'bootstrap_seed': 1279511,
                  'memory_basis': 'Unchanged audited814-column diagnostic decoder already completed under18GiB. Only three small phase regressors replace the old bundle; inference remains guarded.',
                  'scope': 'All eight fixed models on the permanently opened diagnostic only. No fitting, selection, calibration, reserved role or acceptance authority.'})
    print(json.dumps({'status': 'phase-diagnostic-pinned', 'sha256': sha(PIN)}), flush=True)


def validate_pin():
    if not PIN.is_file():
        raise ValueError('published phase diagnostic authority required')
    pin = json.loads(PIN.read_text())
    if (pin['schema'] != 'clasher.hog26.phase-value-diagnostic.v1' or pin['sources'] != sources()
            or pin['fits'] != 8 or pin['seeds'] != list(SEEDS) or pin['folds'] != 4 or not pin['all_fits_reviewed']
            or any(pin[key] is not False for key in ('fitting', 'selection', 'calibration', 'acceptance'))):
        raise ValueError('phase diagnostic authority differs')
    validate(memory=True)
    validate_old_pin(json.loads(OLD_PIN.read_text()))
    for path, expected in pin['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('phase diagnostic resource changed: ' + path)
    return pin
