"""Separate frozen authority for public-phase margin experts."""

import json
from pathlib import Path

import numpy as np
from cache_reader import read_complete_cache
from continuation_contract import OUTPUT as REFERENCES
from continuation_contract import validate as validate_reference
from health_features import make_layout
from scalar_evaluation import phase_ids
from value_contract import CACHE, ROOT, publish, runtime, sha
from value_models import TREE_SETTINGS

PLAN = ROOT / 'reports/hog26_phase_margin_plan_20260913.json'
OUTPUT = ROOT / 'reports/hog26_phase_margin_20260913'
MEMORY = ROOT / 'reports/hog26_phase_margin_memory_20260913.json'
SEEDS = (1279501, 1279502)


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def training_data():
    mapped, evaluation, complete, clusters = read_complete_cache(CACHE)
    shape = mapped.shape
    mapped._mmap.close()
    layout = make_layout(complete['feature_names'])
    return evaluation, complete, clusters, shape, layout


def prepare():
    validate_reference()
    evaluation, complete, _, shape, layout = training_data()
    for start in range(0, shape[0], 8192):
        end = min(start + 8192, shape[0])
        mapped = np.memmap(CACHE / 'features.f32', mode='r', dtype='<f4', shape=shape)
        exact = np.array_equal(mapped[start:end, layout.globals[0]], evaluation[1][start:end])
        mapped._mmap.close()
        if not exact:
            raise ValueError('phase routing must equal the actor-visible clock at every row')
    phases = phase_ids(evaluation[1])
    counts = {str(fold): np.bincount(phases[evaluation[7] != fold], minlength=3).tolist() for fold in range(4)}
    science_path = ROOT / 'reports/hog26_threaded_value_scientific_review_20260913.json'
    science = json.loads(science_path.read_text())
    completion = json.loads((REFERENCES / 'complete.json').read_text())
    resources = dict(science['resources'])
    for kind in ('globals', 'trees'):
        for seed in SEEDS:
            review_path = REFERENCES / kind / f'seed{seed}-review.json'
            if sha(review_path) != completion['reviews'][str(review_path.relative_to(REFERENCES))]:
                raise ValueError('reference review differs')
            review = json.loads(review_path.read_text())
            if sha(REFERENCES / kind / f'seed{seed}-oof.npz') != review['oof_sha256']:
                raise ValueError('reference OOF differs')
            for fold, expected in review['audited_folds'].items():
                fold_path = REFERENCES / kind / f'seed{seed}-fold{fold}' / 'complete.json'
                if sha(fold_path) != expected:
                    raise ValueError('reference fold completion differs')
                resources[str(fold_path.relative_to(ROOT))] = expected
                for name, digest in json.loads(fold_path.read_text())['artifacts'].items():
                    resources[str((fold_path.parent / name).relative_to(ROOT))] = digest
    paths = [science_path, ROOT / 'reports/hog26_early_margin_probe_review_20260913.json',
             ROOT / 'reports/hog26_early_margin_probe_conclusion_20260913.json',
             ROOT / 'reports/hog26_expanded_error_localization_20260913.json',
             CACHE / 'complete.json', CACHE / 'rows.npz']
    for directory in ('hog26_expanded_value_fit', 'hog26_expanded_tree_value', 'hog26_expanded_corpus',
                      'hog26_threaded_value_fit', 'hog26_scaling_review'):
        paths += list((ROOT / 'experiments' / directory).glob('*.py'))
    paths += [ROOT / 'experiments/hog26_scalar_pilot/scalar_evaluation.py']
    resources.update({str(path.relative_to(ROOT)): sha(path) for path in paths})
    for path, expected in resources.items():
        if sha(ROOT / path) != expected:
            raise ValueError('reference chain changed: ' + path)
    publish(PLAN, {'schema': 'clasher.hog26.phase-margin.v1', 'sources': sources(), 'resources': resources,
                   'runtime': runtime(), 'seeds': list(SEEDS), 'folds': 4, 'phases': 3, 'regressor_fits': 24,
                   'tree_settings': TREE_SETTINGS, 'loss': 'absolute_error', 'features': 814,
                   'phase_thresholds': [1 / 3, 2 / 3], 'phase_rows_by_fold': counts,
                   'full_rows': shape[0], 'public_clock_exact_rows': shape[0],
                   'base_cache_sha256': complete['cache']['sha256'], 'fit_threads': 8,
                   'objective': 'Original 50/50 uniform/representative margin weights, restricted to each public phase and normalized to mean one. Residual terminal-minus-current target; add current and clip[-1,1].',
                   'wdl': 'Unchanged reviewed globals checkpoint for the matching seed/fold; no WDL refit.',
                   'seed_scope': 'Two matched seeds can vary early/middle bin subsampling; late fitting has fewer than200000 rows and is expected to be deterministic. Do not count identical phase fits as independent replications.',
                   'scope': 'Training-only held-family comparison. Three fixed experts change capacity, phase allocation and per-phase binning; this does not isolate one cause. No tuned phase thresholds or private-style routing.',
                   'opened_diagnostic_allowed': False, 'policy_updates_allowed': False, 'acceptance': False})
    print(json.dumps({'status': 'phase-margin-pinned', 'sha256': sha(PLAN)}), flush=True)


def validate(*, memory=False):
    validate_reference()
    plan = json.loads(PLAN.read_text())
    if (plan['schema'] != 'clasher.hog26.phase-margin.v1' or plan['sources'] != sources() or plan['runtime'] != runtime()
            or plan['seeds'] != list(SEEDS) or plan['folds'] != 4 or plan['phases'] != 3 or plan['regressor_fits'] != 24
            or plan['tree_settings'] != TREE_SETTINGS or plan['loss'] != 'absolute_error' or plan['features'] != 814
            or plan['phase_thresholds'] != [1 / 3, 2 / 3] or plan['fit_threads'] != 8
            or plan['opened_diagnostic_allowed'] or plan['policy_updates_allowed'] or plan['acceptance']):
        raise ValueError('phase expert authority differs')
    for path, expected in plan['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('phase expert resource changed: ' + path)
    if memory:
        result = json.loads(MEMORY.read_text())
        guard = json.loads((ROOT / 'reports/hog26_phase_margin_memory_guard_20260913.json').read_text())
        largest = np.asarray(list(plan['phase_rows_by_fold'].values())).max(axis=0).tolist()
        if (result['status'] != 'complete-phase-margin-synthetic-memory' or result['plan_sha256'] != sha(PLAN)
                or result['largest_phase_rows'] != largest or result['full_inference_rows'] != plan['full_rows']
                or result['real_targets_used'] or result['checkpoint_saved'] or guard['exit_code'] != 0
                or guard['memory_limit_terminated'] or guard['plan_sha256'] != sha(PLAN)
                or max(result['peak_rss_bytes'], guard['peak_rss_bytes']) + 2 * 1024**3 > 18 * 1024**3):
            raise ValueError('full-phase memory proof and2GiB headroom required')
    return plan
