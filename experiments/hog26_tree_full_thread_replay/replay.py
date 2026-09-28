"""Replay the first serial tree pair with eight threads and require exact state."""

import gc
import hashlib
import json
import pickle
import resource
import time

import numpy as np
import torch
from cache_reader import read_complete_cache
from fast_weights import fitting_weights
from health_features import make_layout
from probe import canonical_state
from replay_contract import OUTPUT, PLAN, REFERENCE, validate
from value_contract import CACHE, publish, sha
from value_models import new_trees
from value_storage import materialize_fitting, predict_trees


def array_digest(value):
    value = np.ascontiguousarray(value)
    return {'shape': list(value.shape), 'dtype': value.dtype.str,
            'sha256': hashlib.sha256(memoryview(value).cast('B')).hexdigest()}


def main():
    torch.set_num_threads(1)
    plan = validate()
    OUTPUT.mkdir(exist_ok=False)
    mapped, evaluation, complete, _ = read_complete_cache(CACHE)
    shape = mapped.shape
    mapped._mmap.close()
    layout = make_layout(complete['feature_names'])
    ids, progress, labels, target, current, _, _, folds, _, _ = evaluation
    fit = folds != 0
    rows = np.flatnonzero(fit)
    if len(rows) != 1815256 or len(np.unique(ids[fit])) != 4608:
        raise ValueError('reference fitting population differs')
    wdl, margin_weights = fitting_weights(ids, progress, fit)
    with (REFERENCE / 'model.pkl').open('rb') as stream:
        reference = pickle.load(stream)
    features = materialize_fitting(CACHE / 'features.f32', shape, rows, layout)
    classifier, regressor = new_trees(1279501)
    from sklearn.utils._openmp_helpers import _openmp_effective_n_threads
    from threadpoolctl import threadpool_limits

    started = time.time()
    comparisons = {}
    for name, model, targets, weights in (('classifier', classifier, labels[fit], wdl[fit] * len(rows)),
                                          ('regressor', regressor, (target - current)[fit], margin_weights[fit] * len(rows))):
        began = time.time()
        with threadpool_limits(limits=8, user_api='openmp'):
            if _openmp_effective_n_threads() != 8:
                raise ValueError('eight-thread context not effective')
            model.fit(features, targets, sample_weight=weights)
        if torch.get_num_threads() != 1 or _openmp_effective_n_threads() != 1:
            raise ValueError('original thread count was not restored')
        expected, actual = canonical_state(reference[name]), canonical_state(model)
        row = {'reference_state_sha256': expected, 'replay_state_sha256': actual,
               'exact_normalized_state': actual == expected, 'elapsed_seconds': time.time() - began}
        publish(OUTPUT / f'{name}-state.json', row)
        if actual != expected:
            raise ValueError('full-size thread replay changed estimator state')
        comparisons[name] = row
        print(json.dumps({'component': name, **row}), flush=True)
    del features, reference
    gc.collect()
    probability, margin = predict_trees(classifier, regressor, CACHE / 'features.f32', shape, layout)
    arrays = {}
    with np.load(REFERENCE / 'predictions.npz', allow_pickle=False) as saved:
        for key, value in (('probabilities', probability), ('margin', margin)):
            actual, expected = array_digest(value), array_digest(saved[key])
            if actual != expected:
                raise ValueError('full-corpus prediction bytes differ')
            arrays[key] = actual
    with (OUTPUT / 'model.pkl').open('xb') as stream:
        pickle.dump({'classifier': classifier, 'regressor': regressor}, stream)
    np.savez_compressed(OUTPUT / 'predictions.npz', probabilities=probability, margin=margin)
    validate()
    publish(OUTPUT / 'complete.json', {'status': 'complete-exact-full-tree-thread-replay', 'plan_sha256': sha(PLAN),
            'components': comparisons, 'prediction_arrays': arrays, 'full_prediction_rows': plan['full_prediction_rows'],
            'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'elapsed_seconds': time.time() - started, 'remaining_fits_allowed': False, 'acceptance': False,
            'artifacts': {path.name: sha(path) for path in OUTPUT.iterdir() if path.is_file()}})
    print(json.dumps({'status': 'complete-exact-full-tree-thread-replay', 'elapsed_seconds': time.time() - started}), flush=True)


if __name__ == '__main__':
    main()
