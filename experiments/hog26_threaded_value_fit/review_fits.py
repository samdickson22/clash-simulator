"""Reproduce all fold predictions and reports before held-seed evaluation."""

import argparse
import gc
import json
import pickle

import numpy as np
import torch
from cache_reader import read_complete_cache
from continuation_contract import OUTPUT, SERIAL, validate
from continuation_contract import PLAN as EXECUTION_PLAN
from health_features import make_layout
from scalar_evaluation import empirical_prior
from scalar_models import GlobalWDL
from value_contract import CACHE, PLAN, load_plan, publish, sha
from value_metrics import report_predictions
from value_storage import global_matrix, predict_globals, predict_trees


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('globals', 'trees'), required=True)
    parser.add_argument('--seed', type=int, choices=(1279501, 1279502), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    execution = validate()
    plan = load_plan()
    result_path = OUTPUT / args.kind / f'seed{args.seed}-review.json'
    if result_path.exists():
        raise ValueError('preserve previous review')
    mapped, evaluation, complete, cluster_names = read_complete_cache(CACHE)
    shape = mapped.shape
    mapped._mmap.close()
    layout = make_layout(complete['feature_names'])
    ids, labels, folds = evaluation[0], evaluation[2], evaluation[7]
    offsets = np.r_[0, np.cumsum([g['rows'] for g in complete['game_records']])]
    globals_x = global_matrix(CACHE / 'features.f32', shape, layout) if args.kind == 'globals' else None
    oof_probability = np.full((len(ids), 3), np.nan)
    oof_margin = np.full(len(ids), np.nan)
    oof_prior = np.full((len(ids), 3), np.nan)
    audited = {}
    for fold in range(4):
        directory = OUTPUT / args.kind / f'seed{args.seed}-fold{fold}'
        completion = json.loads((directory / 'complete.json').read_text())
        expected_names = {'manifest.json', 'predictions.npz', 'report.json', 'model.pt' if args.kind == 'globals' else 'model.pkl'}
        if (completion['status'] != 'complete-expanded-value-fold' or completion['kind'] != args.kind
                or completion['seed'] != args.seed or completion['fold'] != fold
                or completion['plan_sha256'] != sha(PLAN) or set(completion['artifacts']) != expected_names
                or {p.name for p in directory.iterdir()} != expected_names | {'complete.json'}):
            raise ValueError('fold completion or inventory differs')
        for name, expected in completion['artifacts'].items():
            if sha(directory / name) != expected:
                raise ValueError('fold artifact changed')
        manifest = json.loads((directory / 'manifest.json').read_text())
        if args.kind == 'globals':
            original_path = SERIAL / args.kind / f'seed{args.seed}-fold{fold}' / 'complete.json'
            if sha(directory / 'complete.json') != sha(original_path):
                raise ValueError('imported globals completion differs')
        elif (manifest.get('execution_plan_sha256') != sha(EXECUTION_PLAN)
              or manifest.get('execution_implementation') != execution['sources']
              or manifest.get('tree_fit_openmp_threads') != 8):
            raise ValueError('tree execution provenance differs')
        if (manifest['cluster_names'] != list(cluster_names) or manifest['cache_complete_sha256'] != sha(CACHE / 'complete.json')
                or manifest['plan_sha256'] != sha(PLAN) or manifest['implementation'] != plan.implementation
                or manifest['runtime'] != plan.runtime or manifest['kind'] != args.kind
                or manifest['base_seed'] != args.seed or manifest['fold'] != fold or manifest['seed'] != args.seed + fold):
            raise ValueError('fold data identity differs')
        fit = folds != fold
        prior = empirical_prior(ids, labels, fit)
        if not np.array_equal(prior, manifest['prior']):
            raise ValueError('fitting-only prior differs')
        if args.kind == 'globals':
            model = GlobalWDL()
            model.load_state_dict(torch.load(directory / 'model.pt', map_location='cpu', weights_only=True))
            model.eval()
            probability = predict_globals(model, globals_x, offsets)
            margin = evaluation[4].copy()
            del model
        else:
            with (directory / 'model.pkl').open('rb') as stream:
                model = pickle.load(stream)
            probability, margin = predict_trees(model['classifier'], model['regressor'], CACHE / 'features.f32', shape, layout)
            del model
        with np.load(directory / 'predictions.npz', allow_pickle=False) as saved:
            if set(saved.files) != {'probabilities', 'margin'} or not np.array_equal(saved['probabilities'], probability) or not np.array_equal(saved['margin'], margin):
                raise ValueError('checkpoint predictions do not reproduce exactly')
        report = json.loads((directory / 'report.json').read_text())
        for name, mask in (('fitting', fit), ('excluded', ~fit)):
            if report[name] != report_predictions(evaluation, probability, margin, prior, fit_mask=mask):
                raise ValueError('fold metrics do not reproduce exactly')
        oof_probability[~fit] = probability[~fit]
        oof_margin[~fit] = margin[~fit]
        oof_prior[~fit] = prior
        audited[str(fold)] = sha(directory / 'complete.json')
        del probability, margin
        gc.collect()
        print(json.dumps({'kind': args.kind, 'seed': args.seed, 'fold': fold, 'exact_checkpoint_and_metrics': True}), flush=True)
    if not all(np.isfinite(value).all() for value in (oof_probability, oof_margin, oof_prior)):
        raise ValueError('out-of-family predictions are incomplete')
    del globals_x
    gc.collect()
    oof_path = result_path.with_name(f'seed{args.seed}-oof.npz')
    if oof_path.exists():
        raise ValueError('preserve existing OOF file')
    np.savez_compressed(oof_path, probabilities=oof_probability, margin=oof_margin, prior=oof_prior)
    log = lambda row: print(json.dumps({'kind': args.kind, 'seed': args.seed, **row}), flush=True)
    summary = report_predictions(evaluation, oof_probability, oof_margin, oof_prior, bootstrap=True, log=log)
    validate()
    publish(result_path, {'status': 'complete-exact-expanded-fitting-review', 'kind': args.kind, 'seed': args.seed,
            'plan_sha256': sha(PLAN), 'execution_plan_sha256': sha(EXECUTION_PLAN), 'audited_folds': audited, 'oof_sha256': sha(oof_path), 'summary': summary,
            'acceptance': False, 'opened_diagnostic_allowed': False})


if __name__ == '__main__':
    main()
