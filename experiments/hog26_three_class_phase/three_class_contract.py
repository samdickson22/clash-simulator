"""Separate fitting authority for natural games plus marked mirror controls."""

import json
from pathlib import Path

import numpy as np
from combined_data import load_data
from controls_cache_contract import OUTPUT as CONTROLS
from controls_cache_contract import PIN as CONTROL_PIN
from controls_cache_contract import validate as validate_controls
from phase_contract import OUTPUT as HARD
from scalar_evaluation import empirical_prior
from screen_contract import validate as validate_supported
from value_contract import ROOT, publish, runtime, sha
from value_models import TREE_SETTINGS

PIN = ROOT / 'reports/hog26_three_class_phase_pin_20260913.json'
OUTPUT = ROOT / 'reports/hog26_three_class_phase_20260913'
MEMORY = ROOT / 'reports/hog26_three_class_phase_memory_20260913.json'
SEEDS = (1279501, 1279502)


def sources():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    supported = validate_supported()
    control = validate_controls()
    data = load_data()
    phase_counts, phase_classes, priors = {}, {}, {}
    for fold in range(4):
        fit = data['folds'] != fold
        phase_counts[str(fold)] = [int(np.count_nonzero(fit & (data['phases'] == phase))) for phase in range(3)]
        phase_classes[str(fold)] = [np.unique(data['labels'][fit & (data['phases'] == phase)]).tolist() for phase in range(3)]
        natural = data['natural']
        priors[str(fold)] = {'combined': empirical_prior(data['ids'], data['labels'], fit).tolist(),
                            'natural': empirical_prior(natural[0], natural[2], natural[7] != fold).tolist()}
    resources = {**supported['resources'], **supported['sources'], **control['resources'], **control['sources']}
    paths = [CONTROL_PIN, CONTROLS / 'complete.json', CONTROLS / 'features.f32', CONTROLS / 'rows.npz',
             ROOT / 'reports/hog26_three_class_phase_hypothesis_20260913.json']
    for seed in SEEDS:
        for fold in range(4):
            paths += [HARD / f'seed{seed}-fold{fold}' / 'predictions.npz', HARD / f'seed{seed}-fold{fold}' / 'complete.json']
    resources.update({str(p.relative_to(ROOT)): sha(p) for p in paths})
    publish(PIN, {'schema': 'clasher.hog26.three-class-phase.v1', 'sources': sources(), 'resources': resources,
                  'runtime': runtime(), 'seeds': list(SEEDS), 'folds': 4, 'classifier_fits': 24,
                  'natural_games': 6144, 'control_views': 512, 'physical_control_clusters': 256,
                  'natural_rows': data['natural_rows'], 'rows': data['rows'], 'features': 814,
                  'phase_fit_rows': phase_counts, 'phase_classes': phase_classes, 'priors': priors,
                  'tree_settings': TREE_SETTINGS, 'loss': 'log_loss', 'fit_threads': 8, 'inference_threads': 1,
                  'weights': 'Existing WDL equal-game/reached-phase across fitting natural games and all marked controls; restrict per phase and normalize mean1. No class reweighting or pseudocount.',
                  'margin': 'Unchanged matching hard-phase natural margin predictions; no regressor refit.',
                  'scope': 'Natural held-family training comparison. Controlled predictions are fitting diagnostics only. Combined prior is not natural draw frequency. Phase-specific absent classes remain explicit. No reserved data, probability calibration or policy updates.',
                  'acceptance': False})


def validate(*, memory=False):
    validate_supported()
    validate_controls()
    pin = json.loads(PIN.read_text())
    if (pin['sources'] != sources() or pin['runtime'] != runtime() or pin['tree_settings'] != TREE_SETTINGS
            or pin['seeds'] != list(SEEDS) or pin['classifier_fits'] != 24 or pin['acceptance']):
        raise ValueError('three-class phase authority changed')
    for name, expected in pin['resources'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('three-class phase resource changed: ' + name)
    if memory:
        proof = json.loads(MEMORY.read_text())
        guard = json.loads((ROOT / 'reports/hog26_three_class_phase_memory_guard_20260913.json').read_text())
        if (proof['status'] != 'complete-three-class-synthetic-memory' or proof['pin_sha256'] != sha(PIN)
                or proof['rows'] != max(max(x) for x in pin['phase_fit_rows'].values())
                or proof['classes'] != [0, 1, 2] or proof['real_labels_used'] or proof['checkpoint_saved']
                or guard['exit_codes'] != [0] or guard['memory_limit_terminated'] or guard['pin_sha256'] != sha(PIN)
                or guard['peak_rss_bytes'] + 2 * 1024**3 > 18 * 1024**3):
            raise ValueError('largest-phase memory proof and2GiB headroom required')
    return pin
