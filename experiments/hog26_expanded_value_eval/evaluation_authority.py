"""Separate inference authority after the complete expanded fitting closeout."""

import json
from pathlib import Path

from continuation_contract import OUTPUT, validate
from continuation_contract import PLAN as EXECUTION_PLAN
from fitting_chain import audit_fold
from value_contract import PLAN, ROOT, load_plan, publish, sha

PIN = ROOT / 'reports/hog26_expanded_value_evaluation_pin_20260913.json'
REVIEW = ROOT / 'reports/hog26_threaded_value_scientific_review_20260913.json'


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def validate_pin(pin):
    if (pin.get('schema') != 'clasher.hog26.expanded-value-diagnostic.v1' or pin.get('fitting') is not False
            or pin.get('all_fits_reviewed') is not True or pin.get('fits') != 16 or pin.get('acceptance') is not False):
        raise ValueError('complete inference-only authority required')
    if not PIN.is_file() or json.loads(PIN.read_text()) != pin:
        raise ValueError('published evaluation authority required')
    load_plan()
    validate()
    if pin['sources'] != sources():
        raise ValueError('evaluation source changed')
    for path, expected in pin['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('evaluation resource changed: ' + path)
    return pin


def verify_fitting_chain():
    complete = json.loads((OUTPUT / 'complete.json').read_text())
    expected_reviews = {f'{kind}/seed{seed}-review.json' for kind in ('globals', 'trees') for seed in (1279501, 1279502)}
    if (complete['status'] != 'complete-threaded-value-fitting-and-exact-review'
            or complete['execution_plan_sha256'] != sha(EXECUTION_PLAN) or complete['plan_sha256'] != sha(PLAN)
            or complete['fold_bundles'] != 16 or complete['estimator_models'] != 24
            or set(complete['reviews']) != expected_reviews):
        raise ValueError('complete exact fitting chain required')
    for kind in ('globals', 'trees'):
        for seed in (1279501, 1279502):
            relative = f'{kind}/seed{seed}-review.json'
            path = OUTPUT / relative
            if sha(path) != complete['reviews'][relative]:
                raise ValueError('completed exact review changed')
            review = json.loads(path.read_text())
            if (review['status'] != 'complete-exact-expanded-fitting-review' or review['kind'] != kind or review['seed'] != seed
                    or review['execution_plan_sha256'] != sha(EXECUTION_PLAN) or review['plan_sha256'] != sha(PLAN)
                    or set(review['audited_folds']) != {'0', '1', '2', '3'}
                    or review['oof_sha256'] != sha(OUTPUT / kind / f'seed{seed}-oof.npz')):
                raise ValueError('exact review scope differs')
            for fold in range(4):
                audit_fold(OUTPUT / kind / f'seed{seed}-fold{fold}', completion_sha256=review['audited_folds'][str(fold)],
                           kind=kind, seed=seed, fold=fold, model_plan_sha256=sha(PLAN))
    if 'review_schedule_plan_sha256' in complete:
        path = OUTPUT / 'review_schedule_plan.json'
        schedule = json.loads(path.read_text())
        source = ROOT / 'experiments/hog26_parallel_value_review/supervise.py'
        if (sha(path) != complete['review_schedule_plan_sha256'] or schedule['source_sha256'] != sha(source)
                or schedule['worker_threads'] != 1 or schedule['aggregate_memory_limit_bytes'] != 18 * 1024**3
                or schedule['worker_source_sha256'] != validate()['sources']['experiments/hog26_threaded_value_fit/review_fits.py']):
            raise ValueError('parallel review scheduling authority differs')
        for resource, expected in schedule['resources'].items():
            if sha(ROOT / resource) != expected:
                raise ValueError('parallel review input changed')


def prepare_pin():
    load_plan()
    validate()
    if PIN.exists():
        raise ValueError('preserve published evaluation authority')
    review = json.loads(REVIEW.read_text())
    if (review['status'] != 'complete-threaded-value-scientific-review' or review['plan_sha256'] != sha(PLAN)
            or review['execution_plan_sha256'] != sha(EXECUTION_PLAN) or review['acceptance'] is not False or set(review['all_slices']) != {'globals', 'trees'}):
        raise ValueError('complete scientific fitting review required')
    scientific_pin = ROOT / 'reports/hog26_threaded_value_scientific_review_pin_20260913.json'
    if review['pin_sha256'] != sha(scientific_pin):
        raise ValueError('scientific review pin differs')
    verify_fitting_chain()
    resources = dict(review['resources'])
    for path, expected in resources.items():
        if sha(ROOT / path) != expected:
            raise ValueError('scientific fitting resource changed')
    paths = [PLAN, EXECUTION_PLAN, REVIEW, scientific_pin, ROOT / 'experiments/hog26_threaded_value_review/review_comparison.py', ROOT / 'reports/hog26_seed_transfer_frozen_plan_20260911.json',
             ROOT / 'reports/hog26_seed_transfer_preflight_pin_20260911.json',
             ROOT / 'reports/hog26_semantic_margin_frozen_plan_20260912.json']
    paths += [p for p in OUTPUT.rglob('*') if p.is_file()]
    if (OUTPUT / 'review_schedule_plan.json').exists():
        paths.append(ROOT / 'experiments/hog26_parallel_value_review/supervise.py')
    reference = ROOT / 'reports/hog26_scaling_seed_transfer_evaluation_20260912'
    if json.loads((reference / 'complete.json').read_text())['fits_evaluated'] != 20:
        raise ValueError('complete old diagnostic references required')
    paths += [p for p in reference.iterdir() if p.is_file()]
    for directory in ('hog26_seed_transfer', 'hog26_scaling_eval', 'hog26_scaling_review', 'hog26_public_semantics', 'hog26_residual_margin'):
        paths += list((ROOT / 'experiments' / directory).glob('*.py'))
    resources.update({str(path.relative_to(ROOT)): sha(path) for path in paths})
    resources.update(load_plan().resources)
    execution = validate()
    resources.update(execution['resources'])
    resources.update(execution['sources'])
    verify_fitting_chain()
    publish(PIN, {'schema': 'clasher.hog26.expanded-value-diagnostic.v1', 'sources': sources(), 'resources': resources,
                  'fits': 16, 'all_fits_reviewed': True, 'fitting': False, 'acceptance': False,
                  'groups': {'fresh_seen_families': 288, 'fresh_excluded_families': 96},
                  'paired_references': 'old scaled globals for expanded globals; expanded globals and old scaled tree for expanded trees',
                  'bootstrap_replicates': 2000, 'bootstrap_seed': 1279511})
