"""Synthetic-only exact estimator-state comparison across OpenMP thread counts."""

import copy
import hashlib
import json
import pickle
import resource
import time
from pathlib import Path

import numpy as np
import torch
from value_models import new_trees


def digest(value):
    return hashlib.sha256(pickle.dumps(value, protocol=5)).hexdigest()


def canonical_state(model):
    copied = copy.deepcopy(model)
    # This parameter controls execution of the identical bin mapping at inference.
    copied._bin_mapper.n_threads = 1
    return digest(copied)


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / 'reports/hog26_tree_thread_synthetic_probe_20260913.json'
    if output.exists():
        raise ValueError('preserve existing synthetic proof')
    classifier, _ = new_trees(1279501)
    from sklearn.utils._openmp_helpers import _openmp_effective_n_threads
    from threadpoolctl import threadpool_limits

    rng = np.random.default_rng(71231)
    features = np.asfortranarray(rng.random((8192, 814)))
    features[:, 10:20] = features[:, :10]
    features[:, 100:231] = 0
    weights = np.exp(rng.uniform(-8, 8, len(features)))
    weights /= weights.mean()
    target = np.sin(features[:, 0] * 5) + features[:, 2] - features[:, 4]
    results = {}
    for classes in (2, 3):
        labels = (np.arange(len(features)) % 2) * 2 if classes == 2 else np.arange(len(features)) % 3
        reference = None
        group = {}
        for threads in (1, 8):
            classifier, regressor = new_trees(1279501)
            started = time.time()
            with threadpool_limits(limits=threads, user_api='openmp'):
                effective = _openmp_effective_n_threads()
                if effective != threads:
                    raise ValueError('requested OpenMP count did not take effect')
                classifier.fit(features, labels, sample_weight=weights)
                regressor.fit(features, target, sample_weight=weights)
            if torch.get_num_threads() != 1 or _openmp_effective_n_threads() != 1:
                raise ValueError('thread context failed to restore original runtime')
            state = {'classifier': canonical_state(classifier), 'regressor': canonical_state(regressor),
                     'probability': digest(classifier.predict_proba(features)), 'margin': digest(regressor.predict(features))}
            if reference is not None and state != reference:
                raise ValueError('changing threads changed estimator state or predictions')
            reference = state
            group[str(threads)] = {'elapsed_seconds': time.time() - started, 'effective_threads': effective, 'state': state}
        results[str(classes)] = group
    report = {'status': 'complete-exact-synthetic-thread-probe', 'rows': 8192, 'features': 814, 'iterations': 100,
              'classes': results, 'only_normalized_field': 'copied_estimator._bin_mapper.n_threads',
              'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'outcome_data_access': False, 'candidate_saved': False, 'full_corpus_equivalence': False,
              'changes_to_running_experiment': False, 'acceptance': False}
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
