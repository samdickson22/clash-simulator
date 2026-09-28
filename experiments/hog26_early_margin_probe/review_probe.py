"""Exact checkpoint review and paired held-family early-margin comparisons."""

import json
import pickle

import numpy as np
import torch
from assay_metrics import masks, report
from margin_contract import OUTPUT, PLAN, validate
from margin_data import load_data
from margin_metrics import paired, score
from margin_model import predict
from value_contract import ROOT, publish, sha


def main():
    torch.set_num_threads(1)
    plan = validate(memory=True)
    destination = ROOT / 'reports/hog26_early_margin_probe_review_20260913.json'
    if destination.exists():
        raise ValueError('preserve completed early-margin review')
    complete = json.loads((OUTPUT / 'complete.json').read_text())
    if complete['status'] != 'complete-fixed-early-margin-fits' or complete['fits'] != 8 or complete['plan_sha256'] != sha(PLAN):
        raise ValueError('all eight fixed margin fits must complete')
    if {str(path.relative_to(OUTPUT)) for path in OUTPUT.rglob('*') if path.is_file()} != set(complete['artifacts']) | {'complete.json'}:
        raise ValueError('focused margin artifact inventory differs')
    for path, expected in complete['artifacts'].items():
        if sha(OUTPUT / path) != expected:
            raise ValueError('focused margin artifact changed: ' + path)
    data = load_data()
    if data.audit != plan['data_audit']:
        raise ValueError('focused margin data differs from frozen audit')
    oof = {}
    for representation in plan['representations']:
        x = np.asfortranarray(data.matrices[representation], dtype=np.float64)
        prediction = np.full(6144, np.nan)
        for fold in range(4):
            stem = f"seed{plan['seed']}-fold{fold}"
            directory = OUTPUT / representation
            with (directory / f'{stem}.pkl').open('rb') as stream:
                model = pickle.load(stream)
            if model.random_state != plan['seed'] + fold:
                raise ValueError('fixed estimator seed differs')
            actual = predict(model, x, data.current)
            with np.load(directory / f'{stem}-predictions.npz', allow_pickle=False) as saved:
                expected = saved['margin']
                if actual.shape != expected.shape or actual.dtype != expected.dtype or actual.tobytes() != expected.tobytes():
                    raise ValueError('focused margin checkpoint prediction bytes differ')
            fit = data.folds != fold
            saved_report = json.loads((directory / f'{stem}-report.json').read_text())
            expected_report = {'representation': representation, 'seed': plan['seed'], 'fold': fold,
                               'fit_games': int(fit.sum()), 'excluded_games': int((~fit).sum()),
                               'fitting': report(data, actual, fit), 'excluded': report(data, actual, ~fit)}
            if saved_report != expected_report:
                raise ValueError('focused margin fitting or excluded point metrics differ')
            prediction[~fit] = actual[~fit]
        if not np.isfinite(prediction).all():
            raise ValueError('complete held-family early-margin predictions required')
        oof[representation] = prediction
    predictions = {'current': data.current, **data.full_references, **oof}
    contrasts = {'history_minus_focused_base': ('base_public', 'entity_history')}
    for representation in oof:
        for reference in ('current', *data.full_references):
            contrasts[f'{representation}_minus_{reference}'] = (reference, representation)
    results = {}
    for name, mask in masks(data).items():
        results[name] = {'games': int(mask.sum()), 'clusters': len(np.unique(data.clusters[mask])),
                        'mae': {label: score(data.target[mask], values[mask]) for label, values in predictions.items()},
                        'paired_gain': {label: paired(data.target[mask], predictions[before][mask], predictions[after][mask], data.clusters[mask])
                                        for label, (before, after) in contrasts.items()}}
    oof_path = OUTPUT / 'reviewed-oof.npz'
    with oof_path.open('xb') as stream:
        np.savez_compressed(stream, **oof)
    validate(memory=True)
    publish(destination, {'status': 'complete-exact-early-margin-review', 'plan_sha256': sha(PLAN),
                          'completion_sha256': sha(OUTPUT / 'complete.json'), 'checkpoints_exact': 8,
                          'oof_sha256': sha(oof_path), 'results': results, 'full_phase_candidate': False, 'acceptance': False,
                          'scope': plan['scope'], 'interval_scope': 'Fixed paired scenario bootstrap, 2000 replicates. All 29 slices and seven contrasts retained; intervals are unadjusted diagnostics, not acceptance tests.'})


if __name__ == '__main__':
    main()
