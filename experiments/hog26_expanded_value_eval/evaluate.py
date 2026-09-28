"""All frozen expanded models on the opened seed-transfer diagnostic, without fitting."""

import argparse
import json
import pickle

import numpy as np
import torch
from continuation_contract import OUTPUT
from diagnostic_data import load_diagnostic
from evaluation_authority import PIN, prepare_pin, validate_pin
from paired_errors import paired_error_intervals
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
from scalar_models import GlobalWDL
from value_contract import ROOT, publish, sha
from value_metrics import report_predictions
from value_models import canonical_probabilities
from value_storage import predict_globals

DESTINATION = ROOT / 'reports/hog26_expanded_value_seed_transfer_20260913'
OLD = ROOT / 'reports/hog26_scaling_seed_transfer_evaluation_20260912'


def predict_tree_bundle(bundle, features):
    probability = np.empty((len(features), 3), dtype=np.float64)
    margin = np.empty(len(features), dtype=np.float64)
    for start in range(0, len(features), 4096):
        block = features[start:start + 4096]
        probability[start:start + len(block)] = canonical_probabilities(bundle['classifier'], block)
        margin[start:start + len(block)] = np.clip(block[:, -1] + bundle['regressor'].predict(block), -1, 1)
    return probability, margin


def evaluate():
    pin = validate_pin(json.loads(PIN.read_text()))
    if DESTINATION.exists():
        raise ValueError('preserve existing diagnostic artifacts')
    features, globals_x, offsets, evaluation, audit = load_diagnostic(verified_pin=pin)
    ids, progress, labels, target, current, seats, styles, folds, clusters, families = evaluation
    slices = slice_masks(progress, seats, styles, folds)
    slices.update({f'family/{family}': families == family for family in np.unique(families)})
    index = EvaluationIndex(ids, progress)
    DESTINATION.mkdir()
    publish(DESTINATION / 'manifest.json', {'pin_sha256': sha(PIN), 'data_audit': audit, 'fitting': False, 'acceptance': False})
    for kind in ('globals', 'trees'):
        destination = DESTINATION / kind
        destination.mkdir()
        for seed in (1279501, 1279502):
            for fold in range(4):
                validate_pin(pin)
                stem = f'seed{seed}-fold{fold}'
                fitted = OUTPUT / kind / stem
                manifest = json.loads((fitted / 'manifest.json').read_text())
                prior = np.asarray(manifest['prior'])
                if kind == 'globals':
                    model = GlobalWDL()
                    model.load_state_dict(torch.load(fitted / 'model.pt', weights_only=True, map_location='cpu'))
                    probability = predict_globals(model.eval(), globals_x, offsets)
                    margin = current.copy()
                    del model
                    references = {'old_scaled_globals': OLD / f'globals-{stem}-predictions.npz'}
                else:
                    with (fitted / 'model.pkl').open('rb') as stream:
                        bundle = pickle.load(stream)
                    probability, margin = predict_tree_bundle(bundle, features)
                    del bundle
                    references = {'expanded_globals': DESTINATION / 'globals' / f'{stem}-predictions.npz',
                                  'old_scaled_tree': OLD / f'tree-seed1279501-fold{fold}-predictions.npz'}
                pairs = {}
                for name, path in references.items():
                    with np.load(path, allow_pickle=False) as saved:
                        pairs[name] = (saved['probabilities'], saved['margin'])
                np.savez_compressed(destination / f'{stem}-predictions.npz', probabilities=probability, margin=margin)
                report = {}
                for group, group_mask, count in (('fresh_seen_families', folds != fold, 288), ('fresh_excluded_families', folds == fold, 96)):
                    log = lambda row, group=group, kind=kind, seed=seed, fold=fold: print(json.dumps({'kind': kind, 'seed': seed, 'fold': fold, 'group': group, **row}), flush=True)
                    report[group] = report_predictions(evaluation, probability, margin, prior, fit_mask=group_mask, bootstrap=True, log=log)
                    for distribution, values in report[group].items():
                        if values['overall']['coverage']['games'] != count:
                            raise ValueError('fresh seen/excluded game membership differs')
                        for name, value in values.items():
                            if 'metrics' not in value:
                                continue
                            weights = evaluation_weights(ids, progress, slices[name] & group_mask,
                                                         representative=distribution == 'representatives', index=index)
                            value['paired'] = {key: paired_error_intervals(old_p, probability, old_m, margin, labels, target, weights, clusters)
                                               for key, (old_p, old_m) in pairs.items()}
                publish(destination / f'{stem}-report.json', report)
                print(json.dumps({'kind': kind, 'seed': seed, 'fold': fold, 'status': 'diagnostic-evaluated'}), flush=True)
        publish(destination / 'complete.json', {'status': 'complete-expanded-value-model-diagnostic', 'kind': kind, 'fits': 8, 'fitting': False, 'acceptance': False})
    validate_pin(pin)
    publish(DESTINATION / 'complete.json', {'status': 'complete-expanded-value-diagnostic', 'fits': 16,
                                          'fitting': False, 'acceptance': False, 'pin_sha256': sha(PIN),
                                          'artifacts': {str(path.relative_to(DESTINATION)): sha(path)
                                                        for path in sorted(DESTINATION.rglob('*')) if path.is_file()}})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pin', 'evaluate'), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.mode == 'pin':
        prepare_pin()
    else:
        evaluate()


if __name__ == '__main__':
    main()
