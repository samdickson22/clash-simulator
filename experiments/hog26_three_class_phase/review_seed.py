"""Exact checkpoint replay and held-family OOF assembly for one training seed."""

import argparse
import gc
import json
import pickle

import numpy as np
import torch
from combined_data import load_data
from combined_storage import predict
from fast_weights import fitting_weights
from phase_contract import OUTPUT as HARD
from three_class_contract import OUTPUT, PIN, SEEDS, validate
from value_contract import publish, sha
from value_metrics import report_predictions
from value_models import new_trees

from scripts.hog26_public_slice_gates import weighted_outcome_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, choices=SEEDS, required=True)
    seed = parser.parse_args().seed
    torch.set_num_threads(1)
    pin = validate(memory=True)
    data = load_data()
    n = data['natural_rows']
    oof, priors = np.full((n, 3), np.nan), np.full((n, 3), np.nan)
    new_trees(0)
    resources = {}
    for fold in range(4):
        directory = OUTPUT / f'seed{seed}-fold{fold}'
        complete = json.loads((directory / 'complete.json').read_text())
        if complete['status'] != 'complete-three-class-phase-fold' or complete['pin_sha256'] != sha(PIN):
            raise ValueError('complete matching fold required')
        for name, expected in complete['artifacts'].items():
            if sha(directory / name) != expected:
                raise ValueError('fitted fold artifact changed')
        models = []
        for phase in range(3):
            with (directory / f'phase{phase}.pkl').open('rb') as stream:
                model = pickle.load(stream)
            if model.classes_.tolist() != pin['phase_classes'][str(fold)][phase]:
                raise ValueError('saved phase support differs')
            models.append(model)
        replay = predict(data, models)
        with np.load(directory / 'predictions.npz', allow_pickle=False) as saved:
            probability = saved['probabilities']
        if replay.shape != probability.shape or replay.dtype != probability.dtype or replay.tobytes() != probability.tobytes():
            raise ValueError('saved multiclass prediction replay differs')
        fit = data['folds'] != fold
        weights, _ = fitting_weights(data['ids'], data['progress'], fit)
        prior = np.asarray(pin['priors'][str(fold)]['combined'])
        with np.load(HARD / f'seed{seed}-fold{fold}' / 'predictions.npz', allow_pickle=False) as saved:
            margin = saved['margin']
        report = {'natural_excluded': report_predictions(data['natural'], replay[:n], margin, prior,
                  fit_mask=data['natural'][7] == fold),
                  'control_fitting_only': weighted_outcome_metrics(replay[n:], data['labels'][n:] - 1, weights[n:]),
                  'control_validation': False, 'prior_combined': prior.tolist(), 'prior_natural': pin['priors'][str(fold)]['natural']}
        if report != json.loads((directory / 'report.json').read_text()):
            raise ValueError('point report replay differs')
        selected = data['natural'][7] == fold
        oof[selected], priors[selected] = replay[:n][selected], prior
        resources[str((directory / 'complete.json').relative_to(OUTPUT))] = sha(directory / 'complete.json')
        print(json.dumps({'seed': seed, 'fold': fold, 'status': 'exact-three-class-fold-review'}), flush=True)
        del models, model, replay, probability, weights, report
        gc.collect()
    if not np.isfinite(oof).all() or not np.allclose(oof.sum(1), 1) or not (priors > 0).all():
        raise ValueError('complete naturally held-out OOF and supported fitting priors required')
    with (OUTPUT / f'seed{seed}-oof.npz').open('xb') as stream:
        np.savez_compressed(stream, probabilities=oof, prior=priors)
    validate(memory=True)
    publish(OUTPUT / f'seed{seed}-review.json', {'status': 'complete-exact-three-class-seed-review', 'seed': seed,
            'pin_sha256': sha(PIN), 'resources': resources, 'oof_sha256': sha(OUTPUT / f'seed{seed}-oof.npz'),
            'natural_rows': n, 'all_model_prediction_rows_each_fold': data['rows'], 'models': 12, 'acceptance': False})


if __name__ == '__main__':
    main()
