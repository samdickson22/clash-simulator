"""Describe fixed expert-switch jumps on observed held-family boundary states."""

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import torch
from phase_contract import OUTPUT, PLAN, training_data, validate
from scalar_evaluation import phase_ids
from value_contract import CACHE, ROOT, publish, sha
from value_storage import materialize_fitting

PIN = ROOT / 'reports/hog26_phase_boundary_audit_pin_20260913.json'
RESULT = ROOT / 'reports/hog26_phase_boundary_audit_20260913.json'


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def describe(values):
    values = np.asarray(values, dtype=np.float64)
    if not len(values):
        return {'status': 'empty'}
    if not np.isfinite(values).all():
        raise ValueError('finite boundary differences required')
    return {'mean_signed': float(values.mean()), 'mean_absolute': float(np.abs(values).mean()),
            'median_absolute': float(np.median(np.abs(values))), 'p95_absolute': float(np.quantile(np.abs(values), .95)),
            'maximum_absolute': float(np.abs(values).max())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pin', action='store_true')
    args = parser.parse_args()
    torch.set_num_threads(1)
    plan = validate(memory=True)
    if args.pin:
        publish(PIN, {'sources': sources(), 'phase_plan_sha256': sha(PLAN), 'thresholds': [1 / 3, 2 / 3],
                      'selection': 'For every training game that crosses an existing phase boundary in adjacent recorded rows, retain the last row before and first row after. No outcome-dependent selection.',
                      'scope': 'Compare adjacent experts on each identical observed public state to describe routing discontinuity. This is extrapolation of a predictor outside its fitted phase, not an environment-action counterfactual or ranking test.',
                      'acceptance': False})
        return
    pin = json.loads(PIN.read_text())
    if pin['sources'] != sources() or pin['phase_plan_sha256'] != sha(PLAN):
        raise ValueError('boundary audit source or phase authority changed')
    if RESULT.exists():
        raise ValueError('preserve existing boundary audit')
    completion_path = OUTPUT / 'complete.json'
    completion = json.loads(completion_path.read_text())
    science_path = OUTPUT / 'scientific-review.json'
    if (completion['status'] != 'complete-phase-margin-comparison' or completion['plan_sha256'] != sha(PLAN)
            or completion['scientific_review_sha256'] != sha(science_path)):
        raise ValueError('all phase fits and exact/scientific reviews must complete first')
    science = json.loads(science_path.read_text())
    evaluation, _, _, shape, layout = training_data()
    ids, progress, folds, clusters = evaluation[0], evaluation[1], evaluation[7], evaluation[8]
    phases = phase_ids(progress)
    changes = np.diff(phases)[ids[1:] == ids[:-1]]
    if (changes < 0).any() or (changes > 1).any():
        raise ValueError('unexpected reversed or skipped public phase')
    after = np.flatnonzero((ids[1:] == ids[:-1]) & (phases[1:] == phases[:-1] + 1)) + 1
    before = after - 1
    selected = np.unique(np.r_[before, after])
    features = materialize_fitting(CACHE / 'features.f32', shape, selected, layout)
    locations_before, locations_after = np.searchsorted(selected, before), np.searchsorted(selected, after)
    results, resources = {}, {'complete.json': sha(completion_path), 'scientific-review.json': sha(science_path)}
    arrays = {'before_rows': before, 'after_rows': after}
    for seed in plan['seeds']:
        review_path = OUTPUT / f'seed{seed}-review.json'
        oof_path = OUTPUT / f'seed{seed}-oof.npz'
        if sha(review_path) != science['resources'][review_path.name] or sha(oof_path) != science['resources'][oof_path.name]:
            raise ValueError('boundary reviewed phase authority changed')
        review = json.loads(review_path.read_text())
        resources[review_path.name], resources[oof_path.name] = sha(review_path), sha(oof_path)
        with np.load(oof_path, allow_pickle=False) as saved:
            observed = saved['margin']
        jump_before, jump_after = np.full(len(after), np.nan), np.full(len(after), np.nan)
        for fold in range(4):
            directory = OUTPUT / f'seed{seed}-fold{fold}'
            fold_path = directory / 'complete.json'
            if sha(fold_path) != review['audited_folds'][str(fold)]:
                raise ValueError('boundary fold completion changed')
            fold_complete = json.loads(fold_path.read_text())
            models = []
            for phase in range(3):
                path = directory / f'phase{phase}.pkl'
                if sha(path) != fold_complete['artifacts'][path.name]:
                    raise ValueError('boundary checkpoint changed')
                with path.open('rb') as stream:
                    models.append(pickle.load(stream))
            for phase in (1, 2):
                mask = (folds[after] == fold) & (phases[after] == phase)
                if not mask.any():
                    continue
                for positions, storage, expected_phase in ((locations_before, jump_before, phase - 1), (locations_after, jump_after, phase)):
                    block = features[positions[mask]]
                    old = np.clip(block[:, -1] + models[phase - 1].predict(block), -1, 1)
                    new = np.clip(block[:, -1] + models[phase].predict(block), -1, 1)
                    routed = old if expected_phase == phase - 1 else new
                    expected = observed[selected[positions[mask]]]
                    if not np.array_equal(routed, expected):
                        raise ValueError('boundary routed inference differs from exact reviewed OOF')
                    storage[mask] = new - old
        arrays[f'seed{seed}_switch_before'], arrays[f'seed{seed}_switch_after'] = jump_before, jump_after
        results[str(seed)] = {}
        for phase in (1, 2):
            mask = phases[after] == phase
            results[str(seed)][str(phase)] = {'transitions': int(mask.sum()), 'games': len(np.unique(ids[after][mask])),
                    'clusters': len(np.unique(clusters[after][mask])), 'expert_switch_at_before_state': describe(jump_before[mask]),
                    'expert_switch_at_after_state': describe(jump_after[mask]),
                    'actual_adjacent_prediction_change': describe((observed[after] - observed[before])[mask]),
                    'actual_adjacent_current_margin_change': describe((evaluation[4][after] - evaluation[4][before])[mask])}
    array_path = ROOT / 'reports/hog26_phase_boundary_audit_arrays_20260913.npz'
    with array_path.open('xb') as stream:
        np.savez_compressed(stream, **arrays)
    validate(memory=True)
    publish(RESULT, {'status': 'complete-phase-boundary-discontinuity-audit', 'pin_sha256': sha(PIN),
                     'resources': resources, 'array_sha256': sha(array_path), 'results': results,
                     'scope': pin['scope'], 'outcome_targets_used': False, 'acceptance': False})


if __name__ == '__main__':
    main()
