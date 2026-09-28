"""Fit one three-phase WDL bundle with an explicit controlled-data role."""

import argparse
import gc
import json
import pickle

import numpy as np
import torch
from combined_data import load_data
from combined_storage import materialize, predict
from fast_weights import fitting_weights
from phase_contract import OUTPUT as HARD
from phase_storage import normalized_phase_weights
from scalar_evaluation import empirical_prior
from three_class_contract import OUTPUT, PIN, SEEDS, validate
from three_class_model import fit_classifier
from value_contract import publish, sha
from value_metrics import report_predictions

from scripts.hog26_public_slice_gates import weighted_outcome_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, choices=SEEDS, required=True)
    parser.add_argument('--fold', type=int, choices=range(4), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    pin = validate(memory=True)
    data = load_data()
    fit = data['folds'] != args.fold
    weights, _ = fitting_weights(data['ids'], data['progress'], fit)
    prior = empirical_prior(data['ids'], data['labels'], fit)
    if prior.tolist() != pin['priors'][str(args.fold)]['combined'] or not (prior > 0).all():
        raise ValueError('actual supported combined prior required')
    directory = OUTPUT / f'seed{args.seed}-fold{args.fold}'
    directory.mkdir(parents=True, exist_ok=False)
    publish(directory / 'manifest.json', {'seed': args.seed, 'fold': args.fold, 'pin_sha256': sha(PIN),
            'prior_combined': prior.tolist(), 'prior_natural': pin['priors'][str(args.fold)]['natural'],
            'natural_fit_games': 4608, 'control_fit_views': 512, 'physical_control_clusters': 256,
            'control_role': 'training controls, not natural calibration frequency', 'acceptance': False})
    models = []
    for phase in range(3):
        rows = np.flatnonzero(fit & (data['phases'] == phase))
        if len(rows) != pin['phase_fit_rows'][str(args.fold)][phase]:
            raise ValueError('phase fitting population changed')
        features = materialize(data, rows)
        model = fit_classifier(features, data['labels'][rows], normalized_phase_weights(weights, rows), args.seed + args.fold)
        if model.classes_.tolist() != pin['phase_classes'][str(args.fold)][phase]:
            raise ValueError('observed phase classes differ')
        with (directory / f'phase{phase}.pkl').open('xb') as stream:
            pickle.dump(model, stream)
        models.append(model)
        print(json.dumps({'seed': args.seed, 'fold': args.fold, 'phase': phase, 'rows': len(rows),
                          'classes': model.classes_.tolist(), 'status': 'phase-WDL-fitted'}), flush=True)
        del features, model
        gc.collect()
    probability = predict(data, models)
    with (directory / 'predictions.npz').open('xb') as stream:
        np.savez_compressed(stream, probabilities=probability)
    n = data['natural_rows']
    with np.load(HARD / f'seed{args.seed}-fold{args.fold}' / 'predictions.npz', allow_pickle=False) as saved:
        margin = saved['margin']
    controls = weighted_outcome_metrics(probability[n:], data['labels'][n:] - 1, weights[n:])
    publish(directory / 'report.json', {'natural_excluded': report_predictions(data['natural'], probability[:n], margin, prior,
            fit_mask=data['natural'][7] == args.fold), 'control_fitting_only': controls, 'control_validation': False,
            'prior_combined': prior.tolist(), 'prior_natural': pin['priors'][str(args.fold)]['natural']})
    validate(memory=True)
    publish(directory / 'complete.json', {'status': 'complete-three-class-phase-fold', 'pin_sha256': sha(PIN),
            'seed': args.seed, 'fold': args.fold, 'artifacts': {p.name: sha(p) for p in sorted(directory.iterdir()) if p.is_file()},
            'acceptance': False})


if __name__ == '__main__':
    main()
