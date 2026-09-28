"""Apply unchanged numerical rules separately to each held-family training fold."""

import json

import numpy as np
import torch
from natural_rules import full_phase_rules
from phase_contract import training_data
from scalar_evaluation import EvaluationIndex
from screen_contract import HARD, OVERLAP, PIN, PROTOCOL, REFERENCES, RESULT, validate
from value_contract import publish, sha

from scripts.hog26_public_slice_gates import evaluate_slices


def main():
    torch.set_num_threads(1)
    pin = validate()
    protocol = json.loads(PROTOCOL.read_text())
    evaluation, _, _, _, _ = training_data()
    ids, progress, labels, target, current, seats, styles, folds, clusters, _ = evaluation
    outcomes = labels - 1
    index = EvaluationIndex(ids, progress)
    phase_names = np.asarray(['early', 'middle', 'late'])[index.phases]
    scopes = {'declared_development_styles': tuple(protocol['development_selection']['opponents']),
              'all_training_styles': ('balanced', 'random', 'bridge-pressure', 'reactive-defense', 'slow-push', 'spell-control')}
    results = {}
    for seed in pin['seeds']:
        with np.load(REFERENCES / 'globals' / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            probability, prior_rows = saved['probabilities'], saved['prior']
        paths = {'joint_tree_with_globals': REFERENCES / 'trees' / f'seed{seed}-oof.npz',
                 'hard_phase': HARD / f'seed{seed}-oof.npz', 'overlap': OVERLAP / f'seed{seed}-oof.npz'}
        for design, path in paths.items():
            with np.load(path, allow_pickle=False) as saved:
                margin = saved['margin']
                if design != 'joint_tree_with_globals' and not np.array_equal(probability, saved['probabilities']):
                    raise ValueError('same globals probabilities required for every margin design')
            for fold in range(4):
                for scope, expected_styles in scopes.items():
                    mask = (folds == fold) & np.isin(styles, expected_styles)
                    representative = mask & index.representative_mask
                    prior = prior_rows[np.flatnonzero(mask)[0]]
                    if not np.all(prior_rows[mask] == prior):
                        raise ValueError('one matching fitting-only prior per excluded fold required')
                    reps = evaluate_slices(probabilities=probability[representative], predicted_margin=margin[representative],
                            target_margin=target[representative], outcomes=outcomes[representative], current_margin=current[representative],
                            phases=phase_names[representative], seats=seats[representative], styles=styles[representative],
                            clusters=clusters[representative], expected_styles=expected_styles, prior=prior,
                            gates=protocol['gates'], design=protocol['generalization_evaluation'], seed=pin['bootstrap_seed'])
                    full = full_phase_rules(ids, probability, margin, target, current, outcomes, clusters, index.phases,
                                            mask, protocol, pin['bootstrap_seed'])
                    key = f'{design}-seed{seed}-fold{fold}-{scope}'
                    results[key] = {'margin_design': design, 'seed': seed, 'fold': fold, 'scope': scope,
                                    'games': len(np.unique(ids[mask])), 'representatives': reps, 'full_phase': full,
                                    'numerical_metric_failures': [name for name, row in reps['slices'].items()
                                                                 if row['rows'] and not row['metrics_passed']],
                                    'coverage_failures': [name for name, row in reps['slices'].items() if not row['coverage_passed']],
                                    'acceptance': False}
                    print(json.dumps({'case': key, 'status': 'training-rule-screen-complete'}), flush=True)
    validate()
    publish(RESULT, {'status': 'complete-training-natural-rule-screen', 'pin_sha256': sha(PIN),
                     'cases': results, 'case_count': len(results), 'scope': pin['scope'], 'not_tested': pin['not_tested'],
                     'fitting': False, 'reserved_data_access': False, 'acceptance': False})


if __name__ == '__main__':
    main()
