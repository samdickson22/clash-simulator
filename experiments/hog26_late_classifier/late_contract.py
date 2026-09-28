"""Fixed late-only supervised classifier authority; draw support remains absent."""

import json
from pathlib import Path

import numpy as np
from phase_contract import training_data
from scalar_evaluation import phase_ids
from screen_contract import validate as validate_supported
from value_contract import ROOT, publish, sha
from value_models import TREE_SETTINGS

PIN = ROOT / 'reports/hog26_late_classifier_pin_20260913.json'
OUTPUT = ROOT / 'reports/hog26_late_classifier_20260913'
SEEDS = (1279501, 1279502)


def sources():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    parent = validate_supported()
    evaluation, _, _, _, _ = training_data()
    late = phase_ids(evaluation[1]) == 2
    counts = {str(fold): int(np.count_nonzero(late & (evaluation[7] != fold))) for fold in range(4)}
    resources = dict(parent['resources'])
    resources.update(parent['sources'])
    for name in ('hog26_training_supported_metrics_pin_20260913.json', 'hog26_late_classifier_hypothesis_20260913.json',
                 'hog26_training_wdl_screen_20260913.json', 'hog26_training_wdl_screen_helper_pin_20260913.json'):
        p = ROOT / 'reports' / name
        resources[str(p.relative_to(ROOT))] = sha(p)
    for directory in ('hog26_phase_margin', 'hog26_overlap_margin'):
        resources.update({str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'experiments' / directory).glob('*.py')})
    publish(PIN, {'schema': 'clasher.hog26.late-classifier.v1', 'sources': sources(), 'resources': resources,
                  'seeds': list(SEEDS), 'folds': 4, 'rows': int(late.sum()), 'fit_rows': counts,
                  'settings': TREE_SETTINGS, 'loss': 'log_loss', 'classes': [0, 2],
                  'fit_threads': 8, 'inference_threads': 1, 'acceptance': False,
                  'scope': 'Late-only held-family training probe. Same WDL weights restricted to late rows and normalized mean1. No natural draw support, calibration, reserved data, or policy learning. Seeds expected identical below bin subsampling threshold.'})


def validate():
    validate_supported()
    pin = json.loads(PIN.read_text())
    if pin['sources'] != sources() or pin['settings'] != TREE_SETTINGS or pin['seeds'] != list(SEEDS) or pin['acceptance']:
        raise ValueError('late classifier authority changed')
    for name, expected in pin['resources'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('late classifier resource changed: ' + name)
    return pin
