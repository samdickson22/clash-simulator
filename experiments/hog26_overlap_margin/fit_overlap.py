"""Fit one fresh overlapping-expert bundle and pair with frozen globals."""

import argparse
import gc
import json
import pickle
import time

import numpy as np
import torch
from fast_weights import fitting_weights
from overlap_contract import OUTPUT, PLAN, SEEDS, training_data, validate
from overlap_storage import overlap_weights, predict_cache
from phase_contract import REFERENCES
from phase_model import fit_model
from phase_storage import normalized_phase_weights
from scalar_evaluation import empirical_prior
from value_contract import CACHE, publish, sha
from value_metrics import report_predictions
from value_storage import materialize_fitting


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, choices=SEEDS, required=True)
    parser.add_argument('--fold', type=int, choices=range(4), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    plan = validate(memory=True)
    evaluation, _, clusters, shape, layout = training_data()
    ids, progress, labels, target, current, _, _, folds, _, _ = evaluation
    gates, fit = overlap_weights(progress), folds != args.fold
    _, weights = fitting_weights(ids, progress, fit)
    prior = empirical_prior(ids, labels, fit)
    directory = OUTPUT / f'seed{args.seed}-fold{args.fold}'
    directory.mkdir(parents=True, exist_ok=False)
    publish(directory / 'manifest.json', {'plan_sha256': sha(PLAN), 'seed': args.seed, 'fold': args.fold,
            'expert_fit_rows': plan['expert_rows_by_fold'][str(args.fold)], 'clusters': clusters,
            'prior': prior.tolist(), 'fit_threads': 8, 'wdl_reference': str(REFERENCES / 'globals' / f'seed{args.seed}-fold{args.fold}'),
            'acceptance': False})
    started, models = time.time(), []
    for expert in range(3):
        rows = np.flatnonzero(fit & (gates[:, expert] > 0))
        if len(rows) != plan['expert_rows_by_fold'][str(args.fold)][expert]:
            raise ValueError('overlap fitting population changed')
        features = materialize_fitting(CACHE / 'features.f32', shape, rows, layout)
        model = fit_model(features, (target - current)[rows], normalized_phase_weights(weights * gates[:, expert], rows), args.seed + args.fold)
        with (directory / f'expert{expert}.pkl').open('xb') as stream:
            pickle.dump(model, stream)
        models.append(model)
        del features
        gc.collect()
        print(json.dumps({'seed': args.seed, 'fold': args.fold, 'expert': expert, 'status': 'overlap-regressor-fitted'}), flush=True)
    margin = predict_cache(models, CACHE / 'features.f32', shape, layout)
    del models, weights
    gc.collect()
    with np.load(REFERENCES / 'globals' / f'seed{args.seed}-fold{args.fold}' / 'predictions.npz', allow_pickle=False) as saved:
        probability = saved['probabilities']
    with (directory / 'predictions.npz').open('xb') as stream:
        np.savez_compressed(stream, probabilities=probability, margin=margin)
    publish(directory / 'report.json', {'fitting': report_predictions(evaluation, probability, margin, prior, fit_mask=fit),
            'excluded': report_predictions(evaluation, probability, margin, prior, fit_mask=~fit),
            'elapsed_seconds': time.time() - started})
    validate(memory=True)
    publish(directory / 'complete.json', {'status': 'complete-overlap-margin-fold', 'seed': args.seed, 'fold': args.fold,
            'plan_sha256': sha(PLAN), 'artifacts': {path.name: sha(path) for path in sorted(directory.iterdir()) if path.is_file()},
            'acceptance': False})
    print(json.dumps({'seed': args.seed, 'fold': args.fold, 'status': 'overlap-margin-fold-complete'}), flush=True)


if __name__ == '__main__':
    main()
