"""Replay saved predictions, then score every late fold and declared style scope."""

import json
import pickle

import numpy as np
import torch
from late_contract import OUTPUT, PIN, SEEDS, validate
from natural_rules import full_phase_rules
from phase_contract import OUTPUT as HARD
from phase_contract import REFERENCES, training_data
from scalar_evaluation import EvaluationIndex
from screen_contract import PROTOCOL
from supported_slices import evaluate_slices
from value_contract import CACHE, publish, sha
from value_models import canonical_probabilities, new_trees
from value_storage import materialize_fitting

from scripts.hog26_public_slice_gates import clustered_mean_interval


def paired_nll(ids, clusters, labels, before, after, mask, *, representatives):
    positions = np.flatnonzero(mask)
    if not len(positions):
        return None
    gain = (-np.log(np.maximum(before[positions, labels[positions]], 1e-12))
            + np.log(np.maximum(after[positions, labels[positions]], 1e-12)))
    game_ids = ids[positions]
    unique, inverse = np.unique(game_ids, return_inverse=True)
    mean = np.bincount(inverse, weights=gain) / np.bincount(inverse)
    group_clusters = np.array([clusters[positions[np.flatnonzero(inverse == index)[0]]] for index in range(len(unique))])
    result = clustered_mean_interval(mean, group_clusters, replicates=2000, seed=1281101)
    result['distribution'] = 'late representatives' if representatives else 'equal-game late states'
    return result


def main():
    torch.set_num_threads(1)
    validate()
    fitting = json.loads((OUTPUT / 'fit-complete.json').read_text())
    for name, expected in fitting['artifacts'].items():
        if sha(OUTPUT / name) != expected:
            raise ValueError('fitting artifact changed')
    evaluation, _, _, shape, layout = training_data()
    ids, progress, labels, target, current, seats, styles, folds, clusters, _ = evaluation
    index = EvaluationIndex(ids, progress)
    rows = np.flatnonzero(index.phases == 2)
    features = materialize_fitting(CACHE / 'features.f32', shape, rows, layout)
    new_trees(0)  # Initialize the pinned sklearn import path before unpickling.
    protocol = json.loads(PROTOCOL.read_text())
    scopes = {'declared_development_styles': tuple(protocol['development_selection']['opponents']),
              'all_training_styles': ('balanced', 'random', 'bridge-pressure', 'reactive-defense', 'slow-push', 'spell-control')}
    reports, exact = {}, {}
    seed_predictions = []
    for seed in SEEDS:
        with np.load(OUTPUT / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            candidate = saved['probabilities']
            if not np.array_equal(rows, saved['rows']):
                raise ValueError('OOF row identity changed')
        seed_predictions.append(candidate)
        reference = {}
        for kind in ('globals', 'trees'):
            with np.load(REFERENCES / kind / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
                reference[kind] = saved['probabilities'][rows]
                prior_rows = saved['prior'][rows]
        with np.load(HARD / f'seed{seed}-oof.npz', allow_pickle=False) as saved:
            margin = saved['margin'][rows]
        for fold in range(4):
            directory = OUTPUT / f'seed{seed}-fold{fold}'
            with (directory / 'model.pkl').open('rb') as f:
                model = pickle.load(f)
            replay = canonical_probabilities(model, features)
            with np.load(directory / 'predictions.npz', allow_pickle=False) as saved:
                original = saved['probabilities']
                if not np.array_equal(saved['rows'], rows) or replay.dtype != original.dtype or replay.tobytes() != original.tobytes():
                    raise ValueError('serialized-model prediction replay differs')
            selected = folds[rows] == fold
            if not np.array_equal(candidate[selected], replay[selected]):
                raise ValueError('OOF membership or probabilities differ')
            exact[f'{seed}/{fold}'] = {'model_sha256': sha(directory / 'model.pkl'), 'prediction_rows': len(rows), 'exact': True}
            for scope, expected_styles in scopes.items():
                mask = selected & np.isin(styles[rows], expected_styles)
                rep = mask & index.representative_mask[rows]
                prior = prior_rows[np.flatnonzero(selected)[0]]
                if not np.all(prior_rows[selected] == prior):
                    raise ValueError('matching fitting-only prior required')
                for kind, probability in {**reference, 'late_classifier': candidate}.items():
                    reps = evaluate_slices(probabilities=probability[rep], predicted_margin=margin[rep],
                        target_margin=target[rows][rep], outcomes=labels[rows][rep] - 1,
                        current_margin=current[rows][rep], phases=np.repeat('late', int(rep.sum())),
                        seats=seats[rows][rep], styles=styles[rows][rep], clusters=clusters[rows][rep],
                        expected_styles=expected_styles, prior=prior, gates=protocol['gates'],
                        design=protocol['generalization_evaluation'], seed=1280901)
                    full = full_phase_rules(ids[rows], probability, margin, target[rows], current[rows], labels[rows] - 1,
                                           clusters[rows], index.phases[rows], mask, protocol, 1280901)['late']
                    reports[f'{kind}-seed{seed}-fold{fold}-{scope}'] = {'kind': kind, 'seed': seed, 'fold': fold, 'scope': scope,
                        'representatives': reps, 'full_late': full, 'native_prior_support_passed': False, 'acceptance': False}
                reports[f'paired-seed{seed}-fold{fold}-{scope}'] = {kind: {
                    'representatives': paired_nll(ids[rows], clusters[rows], labels[rows], probability, candidate, rep, representatives=True),
                    'all_states': paired_nll(ids[rows], clusters[rows], labels[rows], probability, candidate, mask, representatives=False)}
                    for kind, probability in reference.items()}
            print(f'exact replay and late metrics complete seed={seed} fold={fold}', flush=True)
    validate()
    publish(OUTPUT / 'review.json', {'status': 'complete-exact-late-classifier-review', 'pin_sha256': sha(PIN),
            'exact_models': exact, 'same_seed_predictions': bool(np.array_equal(*seed_predictions)),
            'reports': reports, 'scope': 'Late-only training evidence. Empty early/middle slices are outside this probe. No native acceptance or draw-support claim.', 'acceptance': False})
    publish(OUTPUT / 'complete.json', {'status': 'complete-late-classifier-fit-and-review', 'pin_sha256': sha(PIN),
            'fit_completion_sha256': sha(OUTPUT / 'fit-complete.json'), 'review_sha256': sha(OUTPUT / 'review.json'), 'acceptance': False})


if __name__ == '__main__':
    main()
