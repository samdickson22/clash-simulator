"""Reproduce phase margin and unchanged globals checkpoints on every row."""

import argparse
import gc
import json
import pickle

import numpy as np
import torch
from phase_contract import OUTPUT, PLAN, REFERENCES, SEEDS, training_data, validate
from phase_storage import predict_cache
from scalar_evaluation import empirical_prior
from scalar_models import GlobalWDL
from value_contract import CACHE, publish, sha
from value_metrics import report_predictions
from value_storage import global_matrix, predict_globals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, choices=SEEDS, required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    validate(memory=True)
    destination = OUTPUT / f'seed{args.seed}-review.json'
    if destination.exists():
        raise ValueError('preserve completed phase review')
    evaluation, complete, clusters, shape, layout = training_data()
    ids, labels, folds = evaluation[0], evaluation[2], evaluation[7]
    offsets = np.r_[0, np.cumsum([game['rows'] for game in complete['game_records']])]
    globals_x = global_matrix(CACHE / 'features.f32', shape, layout)
    oof_p, oof_m, oof_prior = np.full((len(ids), 3), np.nan), np.full(len(ids), np.nan), np.full((len(ids), 3), np.nan)
    audited = {}
    for fold in range(4):
        directory = OUTPUT / f'seed{args.seed}-fold{fold}'
        completion = json.loads((directory / 'complete.json').read_text())
        names = {'manifest.json', 'phase0.pkl', 'phase1.pkl', 'phase2.pkl', 'predictions.npz', 'report.json'}
        if (completion['status'] != 'complete-phase-margin-fold' or completion['seed'] != args.seed or completion['fold'] != fold
                or completion['plan_sha256'] != sha(PLAN) or set(completion['artifacts']) != names
                or {path.name for path in directory.iterdir()} != names | {'complete.json'}):
            raise ValueError('phase fold completion differs')
        for name, expected in completion['artifacts'].items():
            if sha(directory / name) != expected:
                raise ValueError('phase fold artifact changed')
        fit = folds != fold
        prior = empirical_prior(ids, labels, fit)
        manifest = json.loads((directory / 'manifest.json').read_text())
        if (manifest['clusters'] != list(clusters) or manifest['plan_sha256'] != sha(PLAN)
                or manifest['seed'] != args.seed or manifest['fold'] != fold or not np.array_equal(manifest['prior'], prior)):
            raise ValueError('phase fold provenance differs')
        models = []
        for phase in range(3):
            with (directory / f'phase{phase}.pkl').open('rb') as stream:
                model = pickle.load(stream)
            if model.random_state != args.seed + fold:
                raise ValueError('phase estimator seed differs')
            models.append(model)
        margin = predict_cache(models, CACHE / 'features.f32', shape, layout)
        model = GlobalWDL()
        model.load_state_dict(torch.load(REFERENCES / 'globals' / f'seed{args.seed}-fold{fold}' / 'model.pt', map_location='cpu', weights_only=True))
        model.eval()
        probability = predict_globals(model, globals_x, offsets)
        with np.load(directory / 'predictions.npz', allow_pickle=False) as saved:
            for name, actual in (('probabilities', probability), ('margin', margin)):
                expected = saved[name]
                if actual.shape != expected.shape or actual.dtype != expected.dtype or actual.tobytes() != expected.tobytes():
                    raise ValueError('phase/global checkpoint prediction bytes differ')
        report = json.loads((directory / 'report.json').read_text())
        for name, mask in (('fitting', fit), ('excluded', ~fit)):
            if report[name] != report_predictions(evaluation, probability, margin, prior, fit_mask=mask):
                raise ValueError('phase fold point metrics differ')
        oof_p[~fit], oof_m[~fit], oof_prior[~fit] = probability[~fit], margin[~fit], prior
        audited[str(fold)] = sha(directory / 'complete.json')
        del models, model, probability, margin
        gc.collect()
        print(json.dumps({'seed': args.seed, 'fold': fold, 'status': 'phase-checkpoint-and-metrics-exact'}), flush=True)
    if not all(np.isfinite(value).all() for value in (oof_p, oof_m, oof_prior)):
        raise ValueError('full held-family phase coverage required')
    del globals_x
    gc.collect()
    path = OUTPUT / f'seed{args.seed}-oof.npz'
    with path.open('xb') as stream:
        np.savez_compressed(stream, probabilities=oof_p, margin=oof_m, prior=oof_prior)
    summary = report_predictions(evaluation, oof_p, oof_m, oof_prior, bootstrap=True,
                                  log=lambda row: print(json.dumps({'seed': args.seed, **row}), flush=True))
    validate(memory=True)
    publish(destination, {'status': 'complete-exact-phase-margin-review', 'seed': args.seed, 'plan_sha256': sha(PLAN),
                          'audited_folds': audited, 'oof_sha256': sha(path), 'summary': summary, 'acceptance': False})


if __name__ == '__main__':
    main()
