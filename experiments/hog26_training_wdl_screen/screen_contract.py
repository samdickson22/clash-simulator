"""Numerical readiness screen only; no development, calibration or final labels."""

import json
from pathlib import Path

from overlap_contract import OUTPUT as OVERLAP
from overlap_contract import validate as validate_overlap
from phase_contract import OUTPUT as HARD
from phase_contract import REFERENCES
from value_contract import ROOT, publish, sha

PIN = ROOT / 'reports/hog26_training_wdl_screen_pin_20260913.json'
RESULT = ROOT / 'reports/hog26_training_wdl_screen_20260913.json'
PROTOCOL = ROOT / 'reports/hog26_procedural_outcome_protocol_reassessed_20260908.json'


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    validate_overlap(memory=True)
    resources = {str(PROTOCOL.relative_to(ROOT)): sha(PROTOCOL)}
    for output, status in ((OVERLAP, 'complete-overlap-margin-comparison'), (HARD, 'complete-phase-margin-comparison')):
        complete_path = output / 'complete.json'
        complete = json.loads(complete_path.read_text())
        science = output / 'scientific-review.json'
        if complete['status'] != status or complete['scientific_review_sha256'] != sha(science):
            raise ValueError('complete exact/scientific comparison required')
        resources[str(complete_path.relative_to(ROOT))], resources[str(science.relative_to(ROOT))] = sha(complete_path), sha(science)
        for relative, expected in json.loads(science.read_text())['resources'].items():
            resources[str((output / relative).relative_to(ROOT))] = expected
    for kind in ('globals', 'trees'):
        for seed in (1279501, 1279502):
            path = REFERENCES / kind / f'seed{seed}-review.json'
            review = json.loads(path.read_text())
            oof = REFERENCES / kind / f'seed{seed}-oof.npz'
            if sha(oof) != review['oof_sha256']:
                raise ValueError('reviewed reference OOF changed')
            resources[str(path.relative_to(ROOT))], resources[str(oof.relative_to(ROOT))] = sha(path), sha(oof)
    for name in ('hog26_public_slice_gates.py', 'hog26_scenario_clusters.py', 'train_hog26_actor_outcome.py'):
        path = ROOT / 'scripts' / name
        resources[str(path.relative_to(ROOT))] = sha(path)
    publish(PIN, {'schema': 'clasher.hog26.training-wdl-screen.v1', 'sources': sources(), 'resources': resources,
                  'seeds': [1279501, 1279502], 'folds': 4, 'margin_designs': ['hard_phase'], 'probability_designs': ['globals', 'trees'],
                  'scopes': ['declared_development_styles', 'all_training_styles'], 'bootstrap_seed': 1280901,
                  'scope': 'Training-only held-family WDL comparison with fixed hard-phase margins. Both existing reviewed probability models are evaluated, with no new fitting. Uses an explicitly diagnostic copy of the representative evaluator that permits zero prior mass only for unobserved labels; native positive-prior requirement remains failed. Other numerical rules are copied exactly and full-phase numerical helpers with scalar labels. This is not the complete acceptance procedure and cannot pass development/calibration/final/ranking gates.',
                  'not_tested': ['controlled-draw recognition', 'unseen validation seeds/families', 'one-time probability calibration', 'final-original challenge', 'counterfactual ranking'],
                  'fitting': False, 'reserved_data_access': False, 'acceptance': False})
    print(json.dumps({'status': 'training-wdl-screen-pinned', 'sha256': sha(PIN)}), flush=True)


def validate():
    validate_overlap(memory=True)
    pin = json.loads(PIN.read_text())
    if (pin['schema'] != 'clasher.hog26.training-wdl-screen.v1' or pin['sources'] != sources()
            or pin['fitting'] or pin['reserved_data_access'] or pin['acceptance']):
        raise ValueError('training-only numerical screen authority required')
    for path, expected in pin['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('numerical screen resource changed: ' + path)
    return pin
