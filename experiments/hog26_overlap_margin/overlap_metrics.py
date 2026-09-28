"""Unchanged slice metrics with proved reuse of identical WDL statistics."""

import numpy as np
from fixed_wdl_statistics import reuse_wdl_bootstrap
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
from value_metrics import report_predictions


def reviewed_summary(evaluation, probability, margin, prior, reference_probability, reference_prior, reference_summary, *, log=None):
    if not np.array_equal(prior, reference_prior):
        raise ValueError('unchanged fitting-only prior required for statistic reuse')
    ids, progress, labels, target, current, seats, styles, folds, clusters, families = evaluation
    index = EvaluationIndex(ids, progress)
    masks = slice_masks(progress, seats, styles, folds)
    masks.update({f'family/{family}': families == family for family in np.unique(families)})
    report = report_predictions(evaluation, probability, margin, prior)
    for representative, distribution in ((False, 'all_states'), (True, 'representatives')):
        if set(report[distribution]) != set(reference_summary[distribution]):
            raise ValueError('reference slice inventory differs')
        for name, value in report[distribution].items():
            reference = reference_summary[distribution][name]
            weights = evaluation_weights(ids, progress, masks[name], representative=representative, index=index)
            if not weights.any():
                if value != reference:
                    raise ValueError('reference empty slice differs')
                continue
            if value['coverage'] != reference['coverage']:
                raise ValueError('unchanged reference coverage required')
            value['intervals'] = reuse_wdl_bootstrap(probability, reference_probability, labels, margin, target, current,
                                                    weights, prior, clusters, reference['intervals'])
            if log:
                log({'distribution': distribution, 'slice': name})
    return report
