"""Replay preserved natural-slice numerical rules on audited scalar predictions."""

import numpy as np

from scripts.hog26_public_slice_gates import (
    clustered_mean_interval,
    weighted_outcome_metrics,
)


def full_phase_rules(ids, probabilities, predicted, target, current, outcomes, clusters, phases, mask, protocol, seed):
    design, gates = protocol['generalization_evaluation'], protocol['gates']
    if design['full_phase_margin_gate']['weighting'] != 'equal-game-within-phase-v1':
        raise ValueError('unknown preserved phase weighting')
    results = {}
    for phase, name in enumerate(('early', 'middle', 'late')):
        selected = np.flatnonzero(mask & (phases == phase))
        records, weights = [], np.empty(len(selected), dtype=np.float64)
        if len(selected):
            game_ids = ids[selected]
            starts = np.r_[0, np.flatnonzero(np.diff(game_ids)) + 1]
            ends = np.r_[starts[1:], len(selected)]
            for begin, end in zip(starts, ends, strict=True):
                rows = selected[begin:end]
                if not np.all(clusters[rows] == clusters[rows[0]]) or not np.all(outcomes[rows] == outcomes[rows[0]]):
                    raise ValueError('constant audited game identity and outcome required')
                error = float(np.abs(predicted[rows] - target[rows]).mean())
                baseline = float(np.abs(current[rows] - target[rows]).mean())
                records.append({'cluster': clusters[rows[0]], 'outcome': int(outcomes[rows[0]]),
                                'mae': error, 'baseline_mae': baseline, 'gain': baseline - error})
                weights[begin:end] = 1 / len(rows)
        cluster_values = np.asarray([row['cluster'] for row in records])
        interval = clustered_mean_interval([row['gain'] for row in records], cluster_values,
                                           replicates=gates['cluster_bootstrap_replicates'], seed=seed + phase)
        counts = {str(label): len({row['cluster'] for row in records if row['outcome'] == label}) for label in (-1, 0, 1)}
        coverage = (len(set(cluster_values)) >= design['minimum_independent_matchup_clusters_per_slice']
                    and all(counts[str(label)] >= design['minimum_clusters_with_each_decisive_outcome_per_slice'] for label in (-1, 1)))
        margin_rule = design['phase_margin_learning_gate']
        margin_passed = (interval is not None and interval['point'] >= margin_rule['minimum_mae_improvement']
                         and interval['lower_95'] >= margin_rule['minimum_cluster_bootstrap_lower_95_improvement'])
        classification, classification_passed = None, False
        if records:
            classification = weighted_outcome_metrics(probabilities[selected], outcomes[selected], weights)
            classification_passed = (classification['ece_10'] <= gates['maximum_ece']
                    and max(classification['classwise_ece_10'].values()) <= gates['maximum_ece']
                    and classification['decisive_auc'] is not None
                    and classification['decisive_auc'] >= gates['minimum_natural_phase_auc']
                    and classification['mean_probability']['draw'] <= gates['maximum_natural_draw_probability'])
        results[name] = {'games': len(records), 'rows': len(selected), 'independent_clusters': len(set(cluster_values)),
                         'clusters_by_outcome': counts, 'coverage_passed': coverage, 'margin_passed': bool(margin_passed),
                         'classification_passed': bool(classification_passed), 'margin_interval': interval,
                         'mae': float(np.mean([row['mae'] for row in records])) if records else None,
                         'baseline_mae': float(np.mean([row['baseline_mae'] for row in records])) if records else None,
                         'classification': classification,
                         'passed': bool(coverage and margin_passed and (classification_passed or not design.get('full_phase_classification_gate')))}
    return results
