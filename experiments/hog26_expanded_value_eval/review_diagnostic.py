"""Reproduce diagnostic checkpoints, point metrics, and paired intervals for all fits."""

import json
import pickle

import numpy as np
import torch
from continuation_contract import OUTPUT
from diagnostic_data import load_diagnostic
from evaluate import DESTINATION, OLD, predict_tree_bundle
from evaluation_authority import PIN, validate_pin
from paired_errors import paired_error_intervals
from review_completed import summarize_slices
from scalar_evaluation import EvaluationIndex, evaluation_weights, slice_masks
from scalar_models import GlobalWDL
from value_contract import ROOT, publish, sha
from value_metrics import report_predictions
from value_storage import predict_globals

RESULT = ROOT / 'reports/hog26_expanded_value_diagnostic_review_20260913.json'


def main():
    torch.set_num_threads(1)
    pin = validate_pin(json.loads(PIN.read_text()))
    if RESULT.exists():
        raise ValueError('preserve completed diagnostic review')
    completion = json.loads((DESTINATION / 'complete.json').read_text())
    if (completion['status'] != 'complete-expanded-value-diagnostic' or completion['fits'] != 16
            or completion['pin_sha256'] != sha(PIN)):
        raise ValueError('complete diagnostic required')
    inventory = {str(p.relative_to(DESTINATION)) for p in DESTINATION.rglob('*') if p.is_file()}
    if len(inventory) != 36 or inventory != set(completion['artifacts']) | {'complete.json'}:
        raise ValueError('diagnostic inventory differs')
    for path, expected in completion['artifacts'].items():
        if sha(DESTINATION / path) != expected:
            raise ValueError('diagnostic artifact changed')
    features, globals_x, offsets, evaluation, audit = load_diagnostic(verified_pin=pin)
    if audit != json.loads((DESTINATION / 'manifest.json').read_text())['data_audit']:
        raise ValueError('diagnostic audit changed')
    ids, progress, labels, target, current, seats, styles, folds, clusters, families = evaluation
    masks = slice_masks(progress, seats, styles, folds)
    masks.update({f'family/{family}': families == family for family in np.unique(families)})
    index = EvaluationIndex(ids, progress)
    reviewed = {}
    for kind in ('globals', 'trees'):
        reviewed[kind] = {}
        for seed in (1279501, 1279502):
            for fold in range(4):
                stem = f'seed{seed}-fold{fold}'
                fitted = OUTPUT / kind / stem
                prior = np.asarray(json.loads((fitted / 'manifest.json').read_text())['prior'])
                if kind == 'globals':
                    model = GlobalWDL()
                    model.load_state_dict(torch.load(fitted / 'model.pt', weights_only=True, map_location='cpu'))
                    probability = predict_globals(model.eval(), globals_x, offsets)
                    margin = current.copy()
                    del model
                    references = {'old_scaled_globals': OLD / f'globals-{stem}-predictions.npz'}
                else:
                    with (fitted / 'model.pkl').open('rb') as stream:
                        model = pickle.load(stream)
                    probability, margin = predict_tree_bundle(model, features)
                    del model
                    references = {'expanded_globals': DESTINATION / 'globals' / f'{stem}-predictions.npz',
                                  'old_scaled_tree': OLD / f'tree-seed1279501-fold{fold}-predictions.npz'}
                with np.load(DESTINATION / kind / f'{stem}-predictions.npz', allow_pickle=False) as saved:
                    if not np.array_equal(saved['probabilities'], probability) or not np.array_equal(saved['margin'], margin):
                        raise ValueError('diagnostic checkpoint predictions differ')
                pairs = {}
                for key, path in references.items():
                    with np.load(path, allow_pickle=False) as saved:
                        pairs[key] = saved['probabilities'], saved['margin']
                report = json.loads((DESTINATION / kind / f'{stem}-report.json').read_text())
                reviewed[kind][stem] = {}
                for group, group_mask in (('fresh_seen_families', folds != fold), ('fresh_excluded_families', folds == fold)):
                    points = report_predictions(evaluation, probability, margin, prior, fit_mask=group_mask)
                    if set(points) != set(report[group]):
                        raise ValueError('diagnostic evaluation distributions differ')
                    for distribution, slices in points.items():
                        if set(slices) != set(report[group][distribution]):
                            raise ValueError('diagnostic slice inventory differs')
                        for name, point in slices.items():
                            row = report[group][distribution][name]
                            if 'metrics' not in point:
                                if row != point:
                                    raise ValueError('empty diagnostic slice changed')
                                continue
                            if row['coverage'] != point['coverage'] or row['metrics'] != point['metrics']:
                                raise ValueError('diagnostic point metrics differ')
                            weights = evaluation_weights(ids, progress, masks[name] & group_mask,
                                                         representative=distribution == 'representatives', index=index)
                            expected = {key: paired_error_intervals(old_p, probability, old_m, margin, labels, target, weights, clusters)
                                        for key, (old_p, old_m) in pairs.items()}
                            if row['paired'] != expected:
                                raise ValueError('diagnostic paired intervals differ')
                        reviewed[kind][stem].setdefault(group, {})[distribution] = summarize_slices(report[group][distribution])
                print(json.dumps({'kind': kind, 'seed': seed, 'fold': fold, 'checkpoint_points_and_pairs_exact': True}), flush=True)
    validate_pin(pin)
    publish(RESULT, {'status': 'complete-expanded-value-diagnostic-review', 'fits': 16, 'artifacts': 36,
                     'pin_sha256': sha(PIN), 'completion_sha256': sha(DESTINATION / 'complete.json'),
                     'checkpoint_predictions_exact': True, 'point_metrics_exact': True, 'paired_intervals_exact': True,
                     'all_slices': reviewed, 'fitting': False, 'acceptance': False,
                     'scope': 'Opened seed-transfer diagnostic only. All reserved roles and public calibration/ranking gates remain unchanged.'})


if __name__ == '__main__':
    main()
