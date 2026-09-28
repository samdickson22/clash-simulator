"""Reproduce all phase diagnostic checkpoints, points and paired intervals."""

import json

import numpy as np
import torch
from phase_diag_inputs import load_inputs
from phase_diag_models import infer
from phase_diag_reports import build_report
from phase_eval_contract import DESTINATION, PIN, REVIEW, validate_pin
from value_contract import publish, sha


def main():
    torch.set_num_threads(1)
    pin = validate_pin()
    if REVIEW.exists():
        raise ValueError('preserve completed phase diagnostic review')
    completion = json.loads((DESTINATION / 'complete.json').read_text())
    if (completion['status'] != 'complete-phase-margin-diagnostic' or completion['fits'] != 8
            or completion['pin_sha256'] != sha(PIN) or len(completion['artifacts']) != 17
            or {path.name for path in DESTINATION.iterdir()} != set(completion['artifacts']) | {'complete.json'}):
        raise ValueError('all18 phase diagnostic artifacts required')
    for path, expected in completion['artifacts'].items():
        if sha(DESTINATION / path) != expected:
            raise ValueError('phase diagnostic artifact changed')
    features, globals_x, offsets, evaluation, audit = load_inputs()
    if audit != json.loads((DESTINATION / 'manifest.json').read_text())['data_audit']:
        raise ValueError('phase diagnostic data audit changed')
    results = {}
    for seed in pin['seeds']:
        for fold in range(4):
            probability, margin, prior = infer(seed, fold, features, globals_x, offsets)
            stem = f'seed{seed}-fold{fold}'
            with np.load(DESTINATION / f'{stem}-predictions.npz', allow_pickle=False) as saved:
                for name, actual in (('probabilities', probability), ('margin', margin)):
                    expected = saved[name]
                    if actual.shape != expected.shape or actual.dtype != expected.dtype or actual.tobytes() != expected.tobytes():
                        raise ValueError('phase diagnostic checkpoint prediction bytes differ')
            report = json.loads((DESTINATION / f'{stem}-report.json').read_text())
            actual = build_report(evaluation, probability, margin, prior, seed, fold, bootstrap=False)
            if set(report) != set(actual):
                raise ValueError('phase diagnostic group inventory differs')
            for group, distributions in actual.items():
                if set(report[group]) != set(distributions):
                    raise ValueError('phase diagnostic distribution inventory differs')
                for distribution, groups in distributions.items():
                    if set(report[group][distribution]) != set(groups):
                        raise ValueError('phase diagnostic slice inventory differs')
                    for name, value in groups.items():
                        saved = report[group][distribution][name]
                        if 'metrics' not in value:
                            if saved != value:
                                raise ValueError('phase diagnostic empty slice differs')
                        elif any(saved[key] != value[key] for key in ('coverage', 'metrics', 'paired')):
                            raise ValueError('phase diagnostic points or paired intervals differ')
            results[stem] = report
            print(json.dumps({'seed': seed, 'fold': fold, 'status': 'phase-diagnostic-checkpoints-points-pairs-exact'}), flush=True)
    validate_pin()
    publish(REVIEW, {'status': 'complete-exact-phase-margin-diagnostic-review', 'fits': 8, 'artifacts': 18,
                     'pin_sha256': sha(PIN), 'completion_sha256': sha(DESTINATION / 'complete.json'),
                     'checkpoint_predictions_exact': True, 'point_metrics_exact': True, 'paired_intervals_exact': True,
                     'all_slices': results, 'fitting': False, 'acceptance': False,
                     'scope': 'Opened diagnostic only; model cases overlap games and are not independent replications. No selection, calibration, reserved data or fitting authority.'})


if __name__ == '__main__':
    main()
