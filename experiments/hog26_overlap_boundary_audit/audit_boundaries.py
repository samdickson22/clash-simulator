"""Decompose observed forecast changes into public gate and expert contributions."""

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import torch
from overlap_contract import OUTPUT, PLAN, SEEDS, training_data, validate
from overlap_storage import blended_predict, overlap_weights
from phase_contract import OUTPUT as HARD
from phase_contract import REFERENCES
from value_contract import CACHE, ROOT, publish, sha
from value_storage import materialize_fitting

PIN = ROOT / 'reports/hog26_overlap_boundary_audit_pin_20260913.json'
RESULT = ROOT / 'reports/hog26_overlap_boundary_audit_20260913.json'
BOUNDARIES = (('early_center', 1 / 6), ('old_early_middle_boundary', 1 / 3), ('middle_center', .5),
              ('old_middle_late_boundary', 2 / 3), ('late_center', 5 / 6))


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def describe(values):
    values = np.asarray(values, dtype=np.float64)
    if not len(values):
        return {'status': 'empty'}
    if not np.isfinite(values).all():
        raise ValueError('finite component values required')
    return {'mean_signed': float(values.mean()), 'mean_absolute': float(np.abs(values).mean()),
            'median_absolute': float(np.median(np.abs(values))), 'p95_absolute': float(np.quantile(np.abs(values), .95)),
            'maximum_absolute': float(np.abs(values).max())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pin', action='store_true')
    args = parser.parse_args()
    torch.set_num_threads(1)
    validate(memory=True)
    if args.pin:
        publish(PIN, {'sources': sources(), 'model_plan_sha256': sha(PLAN), 'boundaries': BOUNDARIES,
                      'selection': 'Every adjacent observed within-game crossing of the three fixed centers and two old phase boundaries. No outcome-dependent selection.',
                      'decomposition': 'delta forecast = sum[(w_after-w_before)*head_before] + sum[w_after*(head_after-head_before)], using clipped head predictions. Routing contribution is bounded by6*delta_clock for fixed head values.',
                      'scope': 'Training-only predictor diagnostic, not an environment-action counterfactual, calibration or ranking gate. Expert predictions may still jump; continuous weights do not establish continuous forecasts.',
                      'outcome_targets_used': False, 'acceptance': False})
        return
    pin = json.loads(PIN.read_text())
    if pin['sources'] != sources() or pin['model_plan_sha256'] != sha(PLAN) or pin['boundaries'] != [list(x) for x in BOUNDARIES]:
        raise ValueError('overlap boundary authority changed')
    if RESULT.exists():
        raise ValueError('preserve completed overlap boundary audit')
    completion_path = OUTPUT / 'complete.json'
    completion = json.loads(completion_path.read_text())
    science_path = OUTPUT / 'scientific-review.json'
    if (completion['status'] != 'complete-overlap-margin-comparison' or completion['plan_sha256'] != sha(PLAN)
            or completion['scientific_review_sha256'] != sha(science_path)):
        raise ValueError('complete overlap exact/scientific review required')
    science = json.loads(science_path.read_text())
    evaluation, _, _, shape, layout = training_data()
    ids, clock, folds, clusters = evaluation[0], evaluation[1].astype(np.float64), evaluation[7], evaluation[8]
    same_game = ids[1:] == ids[:-1]
    if (np.diff(clock)[same_game] < 0).any():
        raise ValueError('public clock reversed inside a game')
    crossings = [np.flatnonzero(same_game & (clock[:-1] < threshold) & (clock[1:] >= threshold)) + 1
                 for _, threshold in BOUNDARIES]
    after = np.concatenate(crossings)
    before = after - 1
    group_ids = np.repeat(np.arange(len(BOUNDARIES)), [len(x) for x in crossings])
    selected = np.unique(np.r_[before, after])
    features = materialize_fitting(CACHE / 'features.f32', shape, selected, layout)
    before_locations, after_locations = np.searchsorted(selected, before), np.searchsorted(selected, after)
    wb, wa = overlap_weights(clock[before]), overlap_weights(clock[after])
    elapsed = clock[after] - clock[before]
    if not (elapsed > 0).all():
        raise ValueError('positive boundary clock advance required')
    resources = {'complete.json': sha(completion_path), 'scientific-review.json': sha(science_path)}
    results, arrays = {}, {'before_rows': before, 'after_rows': after, 'boundary_index': group_ids}
    for seed in SEEDS:
        review_path = OUTPUT / f'seed{seed}-review.json'
        oof_path = OUTPUT / f'seed{seed}-oof.npz'
        if sha(review_path) != science['resources'][review_path.name] or sha(oof_path) != science['resources'][oof_path.name]:
            raise ValueError('reviewed overlap OOF authority changed')
        review = json.loads(review_path.read_text())
        with np.load(oof_path, allow_pickle=False) as saved:
            margin = saved['margin']
        with np.load(HARD / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            hard_margin = saved['margin']
        with np.load(REFERENCES / 'trees' / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            full_margin = saved['margin']
        resources[review_path.name], resources[oof_path.name] = sha(review_path), sha(oof_path)
        pb, pa = np.full((len(after), 3), np.nan), np.full((len(after), 3), np.nan)
        for fold in range(4):
            directory = OUTPUT / f'seed{seed}-fold{fold}'
            path = directory / 'complete.json'
            if sha(path) != review['audited_folds'][str(fold)]:
                raise ValueError('reviewed overlap fold changed')
            complete = json.loads(path.read_text())
            models = []
            for expert in range(3):
                path = directory / f'expert{expert}.pkl'
                if sha(path) != complete['artifacts'][path.name]:
                    raise ValueError('reviewed overlap checkpoint changed')
                with path.open('rb') as stream:
                    models.append(pickle.load(stream))
            mask = folds[after] == fold
            for locations, destination, rows in ((before_locations, pb, before), (after_locations, pa, after)):
                block = features[locations[mask]]
                actual = blended_predict(models, block, layout.globals[0])
                expected = margin[rows[mask]]
                if actual.dtype != expected.dtype or actual.tobytes() != expected.tobytes():
                    raise ValueError('boundary blended predictions differ from exact OOF bytes')
                for expert, model in enumerate(models):
                    destination[mask, expert] = np.clip(block[:, -1] + model.predict(block), -1, 1)
        routing = ((wa - wb) * pb).sum(1)
        experts = (wa * (pa - pb)).sum(1)
        actual = margin[after] - margin[before]
        if (not np.allclose(routing + experts, actual, rtol=0, atol=1e-12)
                or (np.abs(routing) > 6 * elapsed + 1e-12).any()):
            raise ValueError('routing decomposition or fixed-head bound failed')
        arrays[f'seed{seed}_routing'] = routing
        arrays[f'seed{seed}_expert_change'] = experts
        arrays[f'seed{seed}_actual_change'] = actual
        results[str(seed)] = {}
        for index, (name, threshold) in enumerate(BOUNDARIES):
            mask = group_ids == index
            results[str(seed)][name] = {'threshold': threshold, 'transitions': int(mask.sum()),
                    'games': len(np.unique(ids[after][mask])), 'clusters': len(np.unique(clusters[after][mask])),
                    'routing_component': describe(routing[mask]), 'expert_component': describe(experts[mask]),
                    'overlap_actual_change': describe(actual[mask]),
                    'hard_phase_actual_change': describe((hard_margin[after] - hard_margin[before])[mask]),
                    'full_tree_actual_change': describe((full_margin[after] - full_margin[before])[mask]),
                    'current_margin_change': describe((evaluation[4][after] - evaluation[4][before])[mask])}
    array_path = ROOT / 'reports/hog26_overlap_boundary_audit_arrays_20260913.npz'
    with array_path.open('xb') as stream:
        np.savez_compressed(stream, **arrays)
    validate(memory=True)
    publish(RESULT, {'status': 'complete-overlap-boundary-component-audit', 'pin_sha256': sha(PIN),
                     'resources': resources, 'array_sha256': sha(array_path), 'results': results,
                     'decomposition_absolute_tolerance': 1e-12, 'fixed_head_routing_bound_passed': True,
                     'scope': pin['scope'], 'outcome_targets_used': False, 'acceptance': False})


if __name__ == '__main__':
    main()
