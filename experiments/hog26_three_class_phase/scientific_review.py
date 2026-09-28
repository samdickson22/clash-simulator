"""Natural held-family numerical rules and paired probability-error comparisons."""

import json

import numpy as np
import torch
from natural_rules import full_phase_rules
from paired_errors import paired_error_intervals
from phase_contract import OUTPUT as HARD
from phase_contract import REFERENCES, training_data
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
from screen_contract import PROTOCOL
from three_class_contract import OUTPUT, PIN, SEEDS, validate
from value_contract import publish, sha
from value_metrics import report_predictions

from scripts.hog26_public_slice_gates import evaluate_slices


def main():
    torch.set_num_threads(1)
    validate(memory=True)
    evaluation, _, _, _, _ = training_data()
    ids, progress, labels, target, current, seats, styles, folds, clusters, families = evaluation
    index = EvaluationIndex(ids, progress)
    phase_names = np.asarray(['early', 'middle', 'late'])[index.phases]
    protocol = json.loads(PROTOCOL.read_text())
    scopes = {'declared_development_styles': tuple(protocol['development_selection']['opponents']),
              'all_training_styles': ('balanced', 'random', 'bridge-pressure', 'reactive-defense', 'slow-push', 'spell-control')}
    slices = slice_masks(progress, seats, styles, folds)
    slices.update({f'family/{family}': families == family for family in np.unique(families)})
    cases, points, paired, resources = {}, {}, {}, {}
    for seed in SEEDS:
        review_path = OUTPUT / f'seed{seed}-review.json'
        review = json.loads(review_path.read_text())
        oof_path = OUTPUT / f'seed{seed}-oof.npz'
        if review['status'] != 'complete-exact-three-class-seed-review' or review['oof_sha256'] != sha(oof_path):
            raise ValueError('exact reviewed OOF required')
        resources[review_path.name], resources[oof_path.name] = sha(review_path), sha(oof_path)
        with np.load(oof_path, allow_pickle=False) as saved:
            probability, priors = saved['probabilities'], saved['prior']
        with np.load(HARD / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            margin = saved['margin']
        points[str(seed)] = report_predictions(evaluation, probability, margin, priors)
        for fold in range(4):
            for scope, expected_styles in scopes.items():
                mask = (folds == fold) & np.isin(styles, expected_styles)
                representative = mask & index.representative_mask
                prior = priors[np.flatnonzero(mask)[0]]
                if not np.all(priors[mask] == prior) or not (prior > 0).all():
                    raise ValueError('actual positive combined fitting-only prior required')
                reps = evaluate_slices(probabilities=probability[representative], predicted_margin=margin[representative],
                    target_margin=target[representative], outcomes=labels[representative] - 1, current_margin=current[representative],
                    phases=phase_names[representative], seats=seats[representative], styles=styles[representative],
                    clusters=clusters[representative], expected_styles=expected_styles, prior=prior,
                    gates=protocol['gates'], design=protocol['generalization_evaluation'], seed=1280901)
                full = full_phase_rules(ids, probability, margin, target, current, labels - 1, clusters, index.phases,
                                        mask, protocol, 1280901)
                cases[f'seed{seed}-fold{fold}-{scope}'] = {'seed': seed, 'fold': fold, 'scope': scope,
                        'representatives': reps, 'full_phase': full, 'native_prior_support_passed': True,
                        'prior_scope': 'Combined actual training natural/control prior, not natural frequency.', 'acceptance': False}
        paired[str(seed)] = {}
        for kind in ('globals', 'trees'):
            with np.load(REFERENCES / kind / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
                reference = saved['probabilities']
            comparisons = {}
            for representative, distribution in ((False, 'all_states'), (True, 'representatives')):
                comparisons[distribution] = {}
                for name, mask in slices.items():
                    weights = evaluation_weights(ids, progress, mask, representative=representative, index=index)
                    value = paired_error_intervals(reference, probability, margin, margin, labels, target, weights, clusters)
                    value['scope'] = 'Natural held-family training OOF, same rows and weights; positive means candidate improvement. Not independent validation.'
                    comparisons[distribution][name] = value
                print(json.dumps({'seed': seed, 'reference': kind, 'distribution': distribution, 'status': 'paired-WDL-comparison'}), flush=True)
            paired[str(seed)][kind] = comparisons
    validate(memory=True)
    publish(OUTPUT / 'scientific-review.json', {'status': 'complete-three-class-phase-scientific-review',
            'pin_sha256': sha(PIN), 'resources': resources, 'natural_points': points, 'native_numerical_cases': cases,
            'paired_probability_comparisons': paired, 'scope': 'Training-only, controls are not natural frequency or validation. Phase-local fitting and added controls are not isolated causal changes.', 'acceptance': False})


if __name__ == '__main__':
    main()
