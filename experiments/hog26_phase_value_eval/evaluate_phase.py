"""Evaluate every frozen phase bundle on the permanently opened diagnostic."""

import json

import numpy as np
import torch
from phase_diag_inputs import load_inputs
from phase_diag_models import infer
from phase_diag_reports import build_report
from phase_eval_contract import DESTINATION, PIN, validate_pin
from value_contract import publish, sha


def main():
    torch.set_num_threads(1)
    pin = validate_pin()
    if DESTINATION.exists():
        raise ValueError('preserve existing phase diagnostic')
    features, globals_x, offsets, evaluation, audit = load_inputs()
    DESTINATION.mkdir()
    publish(DESTINATION / 'manifest.json', {'pin_sha256': sha(PIN), 'data_audit': audit, 'fitting': False, 'acceptance': False})
    for seed in pin['seeds']:
        for fold in range(4):
            validate_pin()
            probability, margin, prior = infer(seed, fold, features, globals_x, offsets)
            stem = f'seed{seed}-fold{fold}'
            with (DESTINATION / f'{stem}-predictions.npz').open('xb') as stream:
                np.savez_compressed(stream, probabilities=probability, margin=margin)
            report = build_report(evaluation, probability, margin, prior, seed, fold, bootstrap=True,
                                  log=lambda row, seed=seed, fold=fold: print(json.dumps({'seed': seed, 'fold': fold, **row}), flush=True))
            publish(DESTINATION / f'{stem}-report.json', report)
            print(json.dumps({'seed': seed, 'fold': fold, 'status': 'phase-diagnostic-evaluated'}), flush=True)
    validate_pin()
    publish(DESTINATION / 'complete.json', {'status': 'complete-phase-margin-diagnostic', 'fits': 8,
            'pin_sha256': sha(PIN), 'fitting': False, 'acceptance': False,
            'artifacts': {path.name: sha(path) for path in sorted(DESTINATION.iterdir()) if path.is_file()}})


if __name__ == '__main__':
    main()
