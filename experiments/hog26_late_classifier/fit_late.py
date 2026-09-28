"""Fit eight late classifiers without changing any reserved-data role."""

import gc
import pickle

import numpy as np
import torch
from fast_weights import fitting_weights
from late_contract import OUTPUT, PIN, SEEDS, validate
from phase_contract import training_data
from phase_storage import normalized_phase_weights
from scalar_evaluation import phase_ids
from value_contract import CACHE, publish, sha
from value_models import canonical_probabilities, new_trees
from value_storage import materialize_fitting


def main():
    torch.set_num_threads(1)
    pin = validate()
    evaluation, _, _, shape, layout = training_data()
    ids, progress, labels, _, _, _, _, folds, _, _ = evaluation
    rows = np.flatnonzero(phase_ids(progress) == 2)
    if len(rows) != pin['rows'] or not np.array_equal(np.unique(labels[rows]), [0, 2]):
        raise ValueError('fixed decisive late population required')
    if OUTPUT.exists():
        raise ValueError('preserve previous late classifier run')
    OUTPUT.mkdir()
    features = materialize_fitting(CACHE / 'features.f32', shape, rows, layout)
    publish(OUTPUT / 'manifest.json', {'pin_sha256': sha(PIN), 'rows': len(rows), 'classes': [0, 2], 'acceptance': False})
    for seed in SEEDS:
        oof = np.full((len(rows), 3), np.nan, dtype=np.float64)
        for fold in range(4):
            fit = folds != fold
            selected = fit[rows]
            if int(selected.sum()) != pin['fit_rows'][str(fold)]:
                raise ValueError('fit population changed')
            weights, _ = fitting_weights(ids, progress, fit)
            fit_weights = normalized_phase_weights(weights, rows[selected])
            x = np.asfortranarray(features[selected])
            y = labels[rows[selected]]
            model, _ = new_trees(seed + fold)
            from sklearn.utils._openmp_helpers import _openmp_effective_n_threads
            from threadpoolctl import threadpool_limits

            with threadpool_limits(limits=8, user_api='openmp'):
                if _openmp_effective_n_threads() != 8:
                    raise ValueError('eight fit threads required')
                model.fit(x, y, sample_weight=fit_weights)
            if _openmp_effective_n_threads() != 1 or torch.get_num_threads() != 1:
                raise ValueError('one inference thread required')
            if not np.array_equal(model.classes_, [0, 2]):
                raise ValueError('unexpected fitted classes')
            directory = OUTPUT / f'seed{seed}-fold{fold}'
            directory.mkdir()
            with (directory / 'model.pkl').open('xb') as f:
                pickle.dump(model, f)
            probability = canonical_probabilities(model, features)
            oof[~selected] = probability[~selected]
            with (directory / 'predictions.npz').open('xb') as f:
                np.savez_compressed(f, rows=rows, probabilities=probability)
            publish(directory / 'complete.json', {'seed': seed, 'fold': fold, 'fit_rows': len(y),
                    'pin_sha256': sha(PIN), 'model_sha256': sha(directory / 'model.pkl'),
                    'predictions_sha256': sha(directory / 'predictions.npz'), 'classes': [0, 2], 'acceptance': False})
            print(f'late classifier fitted seed={seed} fold={fold} rows={len(y)}', flush=True)
            del model, weights, x, fit_weights
            gc.collect()
        if not np.isfinite(oof).all() or np.any(oof[:, 1] != 0):
            raise ValueError('complete decisive-only OOF required')
        with (OUTPUT / f'seed{seed}-oof.npz').open('xb') as f:
            np.savez_compressed(f, rows=rows, probabilities=oof)
    validate()
    publish(OUTPUT / 'fit-complete.json', {'status': 'complete-late-classifier-fitting', 'pin_sha256': sha(PIN),
            'artifacts': {str(p.relative_to(OUTPUT)): sha(p) for p in sorted(OUTPUT.rglob('*')) if p.is_file()}, 'acceptance': False})


if __name__ == '__main__':
    main()
