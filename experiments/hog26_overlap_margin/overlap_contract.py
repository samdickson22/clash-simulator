"""Separate authority for the predeclared smooth overlapping experts."""

import json
from pathlib import Path

import numpy as np
from overlap_storage import overlap_weights
from phase_contract import PLAN as HARD_PLAN
from phase_contract import SEEDS, training_data
from phase_contract import validate as validate_hard
from phase_eval_contract import DESTINATION as DIAGNOSTIC
from phase_eval_contract import PIN as DIAGNOSTIC_PIN
from phase_eval_contract import REVIEW as DIAGNOSTIC_REVIEW
from phase_eval_contract import validate_pin as validate_diagnostic_pin
from value_contract import ROOT, publish, runtime, sha
from value_models import TREE_SETTINGS

PLAN = ROOT / 'reports/hog26_overlap_margin_plan_20260913.json'
OUTPUT = ROOT / 'reports/hog26_overlap_margin_20260913'
MEMORY = ROOT / 'reports/hog26_overlap_margin_memory_20260913.json'
HYPOTHESIS = ROOT / 'reports/hog26_overlap_margin_training_hypothesis_20260913.json'


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def diagnostic_ready():
    pin = validate_diagnostic_pin()
    review = json.loads(DIAGNOSTIC_REVIEW.read_text())
    completion_path = DIAGNOSTIC / 'complete.json'
    if (review['status'] != 'complete-exact-phase-margin-diagnostic-review' or review['fits'] != 8
            or review['pin_sha256'] != sha(DIAGNOSTIC_PIN) or review['completion_sha256'] != sha(completion_path)
            or not all(review[key] for key in ('checkpoint_predictions_exact', 'point_metrics_exact', 'paired_intervals_exact'))):
        raise ValueError('completed prior diagnostic execution required; its results do not select this design')
    completion = json.loads(completion_path.read_text())
    if completion['status'] != 'complete-phase-margin-diagnostic' or completion['fits'] != 8:
        raise ValueError('all fixed diagnostic evaluations must finish')
    for name, expected in completion['artifacts'].items():
        if sha(DIAGNOSTIC / name) != expected:
            raise ValueError('completed diagnostic artifact changed')
    for mode in ('evaluate', 'review'):
        guard = json.loads((ROOT / f'reports/hog26_phase_margin_diagnostic_{mode}_guard_20260913.json').read_text())
        if guard['exit_code'] != 0 or guard['memory_limit_terminated'] or guard['pin_sha256'] != sha(DIAGNOSTIC_PIN):
            raise ValueError('completed diagnostic guards required')
    return pin


def prepare():
    validate_hard(memory=True)
    diagnostic = diagnostic_ready()
    hypothesis = json.loads(HYPOTHESIS.read_text())
    design = hypothesis['design']
    if (hypothesis['status'] != 'fixed-training-hypothesis-not-execution-authority'
            or design['features'] != 814 or design['experts'] != 3 or design['seeds'] != list(SEEDS)
            or design['folds'] != 4 or design['fits'] != 24 or design['public_centers'] != [1 / 6, .5, 5 / 6]
            or design['gate'] != 'early=clip(3*(0.5-t),0,1); late=clip(3*(t-0.5),0,1); middle=1-early-late'
            or hypothesis['fitting_allowed'] or hypothesis['opened_diagnostic_fitting_allowed'] or hypothesis['acceptance']):
        raise ValueError('pre-transfer training-only design differs')
    for path, expected in hypothesis['basis'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('training-only hypothesis basis changed')
    resources = dict(diagnostic['resources'])
    resources.update(hypothesis['basis'])
    for name, status, script in (
        ('hog26_overlap_statistics_equivalence_20260913.json', 'complete-exact-WDL-statistic-reuse-proof', 'verify_statistics.py'),
        ('hog26_overlap_all_statistics_identity_20260913.json', 'complete-all-slice-statistic-identity-proof', 'verify_all_reuse.py'),
    ):
        path = ROOT / 'reports' / name
        proof = json.loads(path.read_text())
        if proof['status'] != status or proof['source_sha256'] != sha(Path(__file__).parent / script):
            raise ValueError('exact statistic-reuse proof required')
        resources.update(proof['resources'])
        resources[str(path.relative_to(ROOT))] = sha(path)
    evaluation, complete, _, shape, _ = training_data()
    gates = overlap_weights(evaluation[1])
    counts = {str(fold): [int(((evaluation[7] != fold) & (gates[:, expert] > 0)).sum()) for expert in range(3)] for fold in range(4)}
    paths = [HYPOTHESIS, HARD_PLAN, DIAGNOSTIC_PIN, DIAGNOSTIC_REVIEW, DIAGNOSTIC / 'complete.json',
             ROOT / 'reports/hog26_phase_margin_diagnostic_evaluate_guard_20260913.json',
             ROOT / 'reports/hog26_phase_margin_diagnostic_review_guard_20260913.json']
    paths += [path for path in DIAGNOSTIC.iterdir() if path.is_file()]
    resources.update({str(path.relative_to(ROOT)): sha(path) for path in paths})
    for path, expected in resources.items():
        if sha(ROOT / path) != expected:
            raise ValueError('overlap prerequisite changed: ' + path)
    publish(PLAN, {'schema': 'clasher.hog26.overlap-margin.v1', 'sources': sources(), 'resources': resources,
                   'hypothesis_sha256': sha(HYPOTHESIS), 'runtime': runtime(), 'seeds': list(SEEDS), 'folds': 4,
                   'experts': 3, 'regressor_fits': 24, 'features': 814, 'tree_settings': TREE_SETTINGS,
                   'loss': 'absolute_error', 'public_centers': [1 / 6, .5, 5 / 6], 'fit_threads': 8,
                   'expert_rows_by_fold': counts, 'full_rows': shape[0], 'base_cache_sha256': complete['cache']['sha256'],
                   'objective': design['fitting'], 'prediction': design['inference'], 'binning': design['binning'],
                   'wdl_statistics': 'Exact reviewed hard-phase WDL/baseline bootstrap reuse after full probability/prior identity; margin MAE and gain intervals recomputed with the original cluster draws.',
                   'references': ['current_margin', 'full_training_tree_margin', 'hard_phase_margin'],
                   'scope': hypothesis['purpose'], 'diagnostic_role': 'Completed diagnostic is an execution prerequisite only; neither its input rows nor results choose training data/settings.',
                   'opened_diagnostic_allowed': False, 'policy_updates_allowed': False, 'acceptance': False})
    print(json.dumps({'status': 'overlap-margin-pinned', 'sha256': sha(PLAN), 'expert_rows_by_fold': counts}), flush=True)


def validate(*, memory=False):
    validate_hard(memory=True)
    plan = json.loads(PLAN.read_text())
    if (plan['schema'] != 'clasher.hog26.overlap-margin.v1' or plan['sources'] != sources()
            or plan['runtime'] != runtime() or plan['hypothesis_sha256'] != sha(HYPOTHESIS)
            or plan['seeds'] != list(SEEDS) or plan['folds'] != 4 or plan['experts'] != 3 or plan['regressor_fits'] != 24
            or plan['features'] != 814 or plan['tree_settings'] != TREE_SETTINGS or plan['loss'] != 'absolute_error'
            or plan['public_centers'] != [1 / 6, .5, 5 / 6] or plan['fit_threads'] != 8
            or plan['opened_diagnostic_allowed'] or plan['policy_updates_allowed'] or plan['acceptance']):
        raise ValueError('fixed overlapping expert authority differs')
    for path, expected in plan['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('overlap source or resource changed: ' + path)
    if memory:
        result = json.loads(MEMORY.read_text())
        guard = json.loads((ROOT / 'reports/hog26_overlap_margin_memory_guard_20260913.json').read_text())
        expected = np.asarray(list(plan['expert_rows_by_fold'].values())).max(axis=0).tolist()
        if (result['status'] != 'complete-overlap-margin-synthetic-memory' or result['plan_sha256'] != sha(PLAN)
                or result['largest_expert_rows'] != expected or result['full_inference_rows'] != plan['full_rows']
                or result['real_targets_used'] or result['checkpoint_saved'] or guard['exit_code'] != 0
                or guard['memory_limit_terminated'] or guard['plan_sha256'] != sha(PLAN)
                or max(result['peak_rss_bytes'], guard['peak_rss_bytes']) + 2 * 1024**3 > 18 * 1024**3):
            raise ValueError('complete synthetic overlap memory proof and2GiB headroom required')
    return plan
