"""A remaining fixed tree pair under the separately verified thread continuation."""

import argparse
import gc
import json
import pickle
import time

import numpy as np
import torch
from cache_reader import read_complete_cache
from continuation_contract import OUTPUT, validate
from continuation_contract import PLAN as EXECUTION_PLAN
from fast_weights import fitting_weights
from health_features import make_layout
from scalar_evaluation import empirical_prior
from value_contract import CACHE, PLAN, load_plan, publish, sha
from value_metrics import report_predictions
from value_models import new_trees
from value_storage import materialize_fitting, predict_trees


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, choices=(1279501, 1279502), required=True)
    parser.add_argument('--fold', type=int, choices=range(4), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    execution, original = validate(), load_plan()
    directory = OUTPUT / 'trees' / f'seed{args.seed}-fold{args.fold}'
    directory.mkdir(parents=True, exist_ok=False)
    mapped, evaluation, complete, cluster_names = read_complete_cache(CACHE)
    shape = mapped.shape
    mapped._mmap.close()
    layout = make_layout(complete['feature_names'])
    ids, progress, labels, target, current, _, _, folds, _, _ = evaluation
    fit = folds != args.fold
    if len(np.unique(ids[fit])) != 4608 or len(np.unique(ids[~fit])) != 1536:
        raise ValueError('whole-family populations differ')
    rows = np.flatnonzero(fit)
    wdl, margin_weights = fitting_weights(ids, progress, fit)
    prior = empirical_prior(ids, labels, fit)
    publish(directory / 'manifest.json', {'plan_sha256': sha(PLAN), 'execution_plan_sha256': sha(EXECUTION_PLAN),
            'cache_complete_sha256': sha(CACHE / 'complete.json'), 'kind': 'trees', 'base_seed': args.seed,
            'fold': args.fold, 'seed': args.seed + args.fold, 'fitting_rows': len(rows), 'cluster_names': cluster_names,
            'implementation': original.implementation, 'execution_implementation': execution['sources'],
            'runtime': original.runtime, 'tree_fit_openmp_threads': 8, 'prior': prior.tolist(), 'acceptance': False})
    log = lambda row: print(json.dumps({'kind': 'trees', 'base_seed': args.seed, 'fold': args.fold, **row}), flush=True)
    started = time.time()
    features = materialize_fitting(CACHE / 'features.f32', shape, rows, layout)
    classifier, regressor = new_trees(args.seed + args.fold)
    from sklearn.utils._openmp_helpers import _openmp_effective_n_threads
    from threadpoolctl import threadpool_limits

    with threadpool_limits(limits=8, user_api='openmp'):
        if _openmp_effective_n_threads() != 8:
            raise ValueError('eight-thread fitting context is not effective')
        classifier.fit(features, labels[fit], sample_weight=wdl[fit] * len(rows))
        log({'status': 'classifier-fitted', 'classes': classifier.classes_.tolist()})
        regressor.fit(features, (target - current)[fit], sample_weight=margin_weights[fit] * len(rows))
        log({'status': 'regressor-fitted'})
    if torch.get_num_threads() != 1 or _openmp_effective_n_threads() != 1:
        raise ValueError('original inference runtime was not restored')
    del features
    gc.collect()
    probability, margin = predict_trees(classifier, regressor, CACHE / 'features.f32', shape, layout)
    with (directory / 'model.pkl').open('xb') as stream:
        pickle.dump({'classifier': classifier, 'regressor': regressor}, stream)
    del classifier, regressor
    gc.collect()
    np.savez_compressed(directory / 'predictions.npz', probabilities=probability, margin=margin)
    publish(directory / 'report.json', {'fitting': report_predictions(evaluation, probability, margin, prior, fit_mask=fit),
            'excluded': report_predictions(evaluation, probability, margin, prior, fit_mask=~fit),
            'elapsed_seconds': time.time() - started})
    validate()
    publish(directory / 'complete.json', {'status': 'complete-expanded-value-fold', 'kind': 'trees', 'seed': args.seed,
            'fold': args.fold, 'plan_sha256': sha(PLAN), 'execution_plan_sha256': sha(EXECUTION_PLAN),
            'artifacts': {p.name: sha(p) for p in sorted(directory.iterdir()) if p.is_file()}, 'acceptance': False})
    log({'status': 'fold-complete', 'elapsed_seconds': time.time() - started})


if __name__ == '__main__':
    main()
