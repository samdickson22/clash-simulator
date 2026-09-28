"""All fixed diagnostic slices and paired margin-only contrasts."""

import numpy as np
from paired_errors import paired_error_intervals
from phase_eval_contract import OLD_DIAGNOSTIC
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
from value_metrics import report_predictions


def build_report(evaluation, probability, margin, prior, seed, fold, *, bootstrap, log=None):
    ids, progress, labels, target, current, seats, styles, folds, clusters, families = evaluation
    slices = slice_masks(progress, seats, styles, folds)
    slices.update({f'family/{family}': families == family for family in np.unique(families)})
    index = EvaluationIndex(ids, progress)
    with np.load(OLD_DIAGNOSTIC / 'trees' / f'seed{seed}-fold{fold}-predictions.npz', allow_pickle=False) as saved:
        old_margin = saved['margin']
    result = {}
    for group, mask, games in (('fresh_seen_families', folds != fold, 288), ('fresh_excluded_families', folds == fold, 96)):
        callback = (lambda row, group=group: log({'group': group, **row})) if log else None
        result[group] = report_predictions(evaluation, probability, margin, prior, fit_mask=mask, bootstrap=bootstrap, log=callback)
        for distribution, groups in result[group].items():
            if groups['overall']['coverage']['games'] != games:
                raise ValueError('phase diagnostic seen/excluded populations differ')
            for name, value in groups.items():
                if 'metrics' not in value:
                    continue
                weights = evaluation_weights(ids, progress, slices[name] & mask,
                                             representative=distribution == 'representatives', index=index)
                pairs = {}
                for label, before in (('current_margin', current), ('previous_full_tree_margin', old_margin)):
                    pair = paired_error_intervals(probability, probability, before, margin, labels, target, weights, clusters)
                    pair['scope'] = 'Opened diagnostic only, paired same rows/scenarios. Positive means phase-margin improvement; both forecasts use identical expanded-global WDL probabilities.'
                    pairs[label] = pair
                value['paired'] = pairs
    return result
