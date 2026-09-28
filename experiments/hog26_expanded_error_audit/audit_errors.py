"""Retrospective error localization on reviewed held-family training predictions."""

import json

import numpy as np
import torch
from cache_reader import read_complete_cache
from continuation_contract import OUTPUT, PLAN, validate
from paired_errors import paired_error_intervals
from scalar_evaluation import EvaluationIndex, evaluation_weights
from value_contract import CACHE, ROOT, publish, sha


def describe(mask_weights, probability, margin, evaluation, final):
    ids, _, labels, target, current, _, _, _, clusters, _ = evaluation
    active = mask_weights > 0
    mass = float(mask_weights.sum())
    if not active.any():
        return {'status': 'empty', 'weight_mass': 0}
    w = mask_weights / mass
    pair = paired_error_intervals(probability, probability, current, margin, labels, target, mask_weights, clusters)
    return {'games': len(np.unique(ids[active])), 'rows': int(active.sum()), 'clusters': len(np.unique(clusters[active])),
            'weight_mass': mass, 'final_decision_weight_fraction': float(w[final].sum()),
            'baseline_mae': float(np.sum(w * np.abs(current - target))),
            'model_mae': float(np.sum(w * np.abs(margin - target))),
            'margin_gain': pair['metrics']['margin_mae_reduction']}


def main():
    torch.set_num_threads(1)
    validate()
    result_path = ROOT / 'reports/hog26_expanded_error_localization_20260913.json'
    if result_path.exists():
        raise ValueError('preserve completed retrospective error analysis')
    complete = json.loads((OUTPUT / 'complete.json').read_text())
    if complete['status'] != 'complete-threaded-value-fitting-and-exact-review':
        raise ValueError('all exact model reviews required')
    mapped, evaluation, cache, _ = read_complete_cache(CACHE)
    mapped._mmap.close()
    ids, progress, _, _, _, seats, styles, _, _, families = evaluation
    index = EvaluationIndex(ids, progress)
    offsets = np.r_[0, np.cumsum([g['rows'] for g in cache['game_records']])]
    final = np.zeros(len(ids), dtype=bool)
    final[offsets[1:] - 1] = True
    resources = {str(PLAN.relative_to(ROOT)): sha(PLAN), str((OUTPUT / 'complete.json').relative_to(ROOT)): sha(OUTPUT / 'complete.json')}
    results, fitting_points = {}, {}
    for seed in (1279501, 1279502):
        review_path = OUTPUT / 'trees' / f'seed{seed}-review.json'
        reviewed = json.loads(review_path.read_text())
        if sha(review_path) != complete['reviews'][f'trees/seed{seed}-review.json']:
            raise ValueError('exact tree review changed')
        oof_path = OUTPUT / 'trees' / f'seed{seed}-oof.npz'
        if sha(oof_path) != reviewed['oof_sha256']:
            raise ValueError('reviewed OOF predictions changed')
        resources[str(oof_path.relative_to(ROOT))] = sha(oof_path)
        with np.load(oof_path, allow_pickle=False) as saved:
            probability, margin = saved['probabilities'], saved['margin']
        results[str(seed)] = {}
        for representative, distribution in ((False, 'all_states'), (True, 'representatives')):
            late_weights = evaluation_weights(ids, progress, index.phases == 2, representative=representative, index=index)
            late = {name: describe(late_weights * mask, probability, margin, evaluation, final)
                    for name, mask in (('final_decision', final), ('earlier_decision', ~final))}
            bridge = {}
            for seat in (0, 1):
                mask = (index.phases == 0) & (styles == 'bridge-pressure') & (seats == seat)
                weights = evaluation_weights(ids, progress, mask, representative=representative, index=index)
                bridge[str(seat)] = {'overall': describe(weights, probability, margin, evaluation, final),
                                     'endpoints': {name: describe(weights * subgroup, probability, margin, evaluation, final)
                                                   for name, subgroup in (('final_decision', final), ('earlier_decision', ~final))},
                                     'families': {str(family): describe(weights * (families == family), probability, margin, evaluation, final)
                                                  for family in np.unique(families)}}
            results[str(seed)][distribution] = {'late_endpoint_groups': late, 'early_bridge_pressure': bridge}
        fitting_points[str(seed)] = {}
        for fold in range(4):
            path = OUTPUT / 'trees' / f'seed{seed}-fold{fold}' / 'report.json'
            fold_complete = path.parent / 'complete.json'
            if sha(fold_complete) != reviewed['audited_folds'][str(fold)]:
                raise ValueError('reviewed fitting completion changed')
            if sha(path) != json.loads(fold_complete.read_text())['artifacts']['report.json']:
                raise ValueError('reviewed fitting report changed')
            report = json.loads(path.read_text())
            resources[str(path.relative_to(ROOT))] = sha(path)
            fitting_points[str(seed)][str(fold)] = {distribution: {str(seat): report['fitting'][distribution][f'phase/early/seat/{seat}/style/bridge-pressure']
                                                                  for seat in (0, 1)}
                                                   for distribution in ('all_states', 'representatives')}
    validate()
    publish(result_path, {'status': 'complete-retrospective-expanded-error-localization', 'resources': resources,
                         'source_sha256': sha(__file__), 'held_family_error_groups': results, 'fitting_bridge_points': fitting_points,
                         'acceptance': False, 'model_or_weight_changes': False,
                         'scope': 'Training-only post-fit diagnostics. Endpoint position is retrospective grouping, never a model input. Conditional group weights are inherited from the original parent slice and normalized only for reporting; no acceptance gate is altered.'})
    print(json.dumps({'status': 'complete-retrospective-expanded-error-localization'}), flush=True)


if __name__ == '__main__':
    main()
