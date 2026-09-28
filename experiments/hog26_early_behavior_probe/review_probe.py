"""Reproduce auxiliary checkpoints and compare public-history information."""

import json
import pickle

import numpy as np
import torch
from binary_metrics import paired_scores, scores
from probe_contract import OUTPUT, PLAN, validate
from probe_data import load_data
from probe_model import probability
from value_contract import ROOT, publish, sha


def main():
    torch.set_num_threads(1)
    plan = validate(require_memory=True)
    result_path = ROOT / 'reports/hog26_early_behavior_probe_review_20260913.json'
    if result_path.exists():
        raise ValueError('preserve completed auxiliary review')
    complete = json.loads((OUTPUT / 'complete.json').read_text())
    if complete['status'] != 'complete-fixed-early-behavior-fits' or complete['fits'] != 16 or complete['plan_sha256'] != sha(PLAN):
        raise ValueError('all fixed auxiliary fits must complete')
    if {str(path.relative_to(OUTPUT)) for path in OUTPUT.rglob('*') if path.is_file()} != set(complete['artifacts']) | {'complete.json'}:
        raise ValueError('auxiliary artifact inventory differs')
    for path, expected in complete['artifacts'].items():
        if sha(OUTPUT / path) != expected:
            raise ValueError('auxiliary artifact changed')
    data = load_data()
    if data.audit != plan['data_audit']:
        raise ValueError('auxiliary data differs from frozen audit')
    oof, priors = {}, {}
    for representation in plan['representations']:
        x = np.asfortranarray(data.matrices[representation], dtype=np.float64)
        oof[representation], priors[representation] = {}, {}
        for seed in plan['seeds']:
            predictions = np.full(6144, np.nan)
            prior_rows = np.full(6144, np.nan)
            for fold in range(4):
                stem = f'seed{seed}-fold{fold}'
                directory = OUTPUT / representation
                with (directory / f'{stem}.pkl').open('rb') as stream:
                    model = pickle.load(stream)
                actual = probability(model, x)
                with np.load(directory / f'{stem}-predictions.npz', allow_pickle=False) as saved:
                    if actual.dtype != saved['bridge_probability'].dtype or actual.tobytes() != saved['bridge_probability'].tobytes():
                        raise ValueError('auxiliary checkpoint predictions differ')
                fit = data.folds != fold
                prior = float(data.labels[fit].mean())
                report = json.loads((directory / f'{stem}-report.json').read_text())
                if (report['prior'] != prior or report['fitting'] != scores(data.labels[fit], actual[fit], prior)
                        or report['excluded'] != scores(data.labels[~fit], actual[~fit], prior)):
                    raise ValueError('auxiliary fitting or excluded point metrics differ')
                predictions[~fit] = actual[~fit]
                prior_rows[~fit] = prior
            if not np.isfinite(predictions).all() or not np.isfinite(prior_rows).all():
                raise ValueError('complete held-family auxiliary predictions required')
            oof[representation][seed], priors[representation][seed] = predictions, prior_rows
    masks = {'overall': np.ones(6144, dtype=bool), 'seat/0': data.seats == 0, 'seat/1': data.seats == 1}
    masks.update({f'family/{family}': data.families == family for family in np.unique(data.families)})
    results = {}
    for seed in plan['seeds']:
        if not np.array_equal(priors['base_public'][seed], priors['entity_history'][seed]):
            raise ValueError('paired auxiliary priors differ')
        results[str(seed)] = {}
        for name, mask in masks.items():
            prior = float(priors['base_public'][seed][mask][0])
            if not np.all(priors['base_public'][seed][mask] == prior):
                raise ValueError('equal style populations should produce a common fitting prior')
            results[str(seed)][name] = {'base_public': scores(data.labels[mask], oof['base_public'][seed][mask], prior),
                    'entity_history': scores(data.labels[mask], oof['entity_history'][seed][mask], prior),
                    'paired': paired_scores(data.labels[mask], oof['base_public'][seed][mask], oof['entity_history'][seed][mask], data.clusters[mask])}
        np.savez_compressed(OUTPUT / f'seed{seed}-reviewed-oof.npz', base_probability=oof['base_public'][seed],
                            history_probability=oof['entity_history'][seed], prior=priors['base_public'][seed])
    validate(require_memory=True)
    publish(result_path, {'status': 'complete-exact-early-behavior-information-review', 'plan_sha256': sha(PLAN),
                          'completion_sha256': sha(OUTPUT / 'complete.json'), 'checkpoints_exact': 16, 'results': results,
                          'outcome_fitting': False, 'acceptance': False,
                          'scope': 'Auxiliary behavior identifiability at fixed early training representatives only. This neither proves outcome improvement nor authorizes a policy or model promotion.'})


if __name__ == '__main__':
    main()
