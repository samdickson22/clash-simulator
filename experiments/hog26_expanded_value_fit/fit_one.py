"""One predeclared fold, with exclusive artifacts and complete public-data checks."""

import argparse
import gc
import json
import pickle
import time

import numpy as np
import torch
from cache_reader import read_complete_cache
from fast_weights import fitting_weights
from health_features import make_layout
from scalar_evaluation import empirical_prior
from value_contract import CACHE, OUTPUT, PLAN, load_plan, publish, sha
from value_metrics import report_predictions
from value_models import fit_cached_globals, new_trees
from value_storage import (
    global_matrix,
    materialize_fitting,
    predict_globals,
    predict_trees,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('globals', 'trees'), required=True)
    parser.add_argument('--seed', type=int, choices=(1279501, 1279502), required=True)
    parser.add_argument('--fold', type=int, choices=range(4), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    plan = load_plan()
    directory = OUTPUT / args.kind / f'seed{args.seed}-fold{args.fold}'
    directory.mkdir(parents=True, exist_ok=False)
    mapped, evaluation, complete, cluster_names = read_complete_cache(CACHE)
    shape = mapped.shape
    mapped._mmap.close()
    layout = make_layout(complete['feature_names'])
    ids, progress, labels, target, current, _, _, folds, _, _ = evaluation
    fit = folds != args.fold
    excluded = ~fit
    if len(np.unique(ids[fit])) != 4608 or len(np.unique(ids[excluded])) != 1536:
        raise ValueError('whole-family fitting game counts differ')
    rows = np.flatnonzero(fit)
    wdl, margin_weights = fitting_weights(ids, progress, fit)
    prior = empirical_prior(ids, labels, fit)
    publish(directory / 'manifest.json', {'plan_sha256': sha(PLAN), 'cache_complete_sha256': sha(CACHE / 'complete.json'),
            'kind': args.kind, 'base_seed': args.seed, 'fold': args.fold, 'seed': args.seed + args.fold,
            'fitting_rows': len(rows), 'cluster_names': cluster_names, 'implementation': plan.implementation,
            'runtime': plan.runtime, 'prior': prior.tolist(), 'acceptance': False})
    log = lambda row: print(json.dumps({'kind': args.kind, 'base_seed': args.seed, 'fold': args.fold, **row}), flush=True)
    started = time.time()
    if args.kind == 'globals':
        features = global_matrix(CACHE / 'features.f32', shape, layout)
        model = fit_cached_globals(features[fit], labels[fit], wdl[fit], seed=args.seed + args.fold,
                                   epochs=plan.globals_epochs, batch_rows=plan.batch_rows, log=log)
        offsets = np.r_[0, np.cumsum([g['rows'] for g in complete['game_records']])]
        probabilities = predict_globals(model, features, offsets)
        predicted = current.copy()
        torch.save(model.state_dict(), directory / 'model.pt')
        del features, model
    else:
        features = materialize_fitting(CACHE / 'features.f32', shape, rows, layout)
        classifier, regressor = new_trees(args.seed + args.fold)
        classifier.fit(features, labels[fit], sample_weight=wdl[fit] * len(rows))
        log({'status': 'classifier-fitted', 'classes': classifier.classes_.tolist()})
        regressor.fit(features, (target - current)[fit], sample_weight=margin_weights[fit] * len(rows))
        log({'status': 'regressor-fitted'})
        del features
        gc.collect()
        probabilities, predicted = predict_trees(classifier, regressor, CACHE / 'features.f32', shape, layout)
        with (directory / 'model.pkl').open('xb') as stream:
            pickle.dump({'classifier': classifier, 'regressor': regressor}, stream)
        del classifier, regressor
    gc.collect()
    np.savez_compressed(directory / 'predictions.npz', probabilities=probabilities, margin=predicted)
    report = {'fitting': report_predictions(evaluation, probabilities, predicted, prior, fit_mask=fit),
              'excluded': report_predictions(evaluation, probabilities, predicted, prior, fit_mask=excluded),
              'elapsed_seconds': time.time() - started}
    publish(directory / 'report.json', report)
    load_plan()
    publish(directory / 'complete.json', {'status': 'complete-expanded-value-fold', 'kind': args.kind,
            'seed': args.seed, 'fold': args.fold, 'plan_sha256': sha(PLAN),
            'artifacts': {p.name: sha(p) for p in sorted(directory.iterdir()) if p.is_file()}, 'acceptance': False})
    log({'status': 'fold-complete', 'elapsed_seconds': time.time() - started})


if __name__ == '__main__':
    main()
