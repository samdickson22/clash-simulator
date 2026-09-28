"""Excluded scalar draw-control feasibility; no fitting or reserved data."""

import json
from pathlib import Path

from value_contract import ROOT, publish, sha

PIN = ROOT / 'reports/hog26_scalar_draw_feasibility_pin_20260913.json'
OUTPUT = ROOT / 'reports/hog26_scalar_draw_feasibility_20260913'
RESULT = OUTPUT / 'complete.json'
EXPANSION = ROOT / 'reports/hog26_training_expansion_frozen_plan_20260913.json'
CASES = (('mirror_a', 1281001, False), ('mirror_a_replay', 1281001, False),
         ('mirror_b', 1281002, False), ('noop_terminal', 1281003, True))


def sources():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(Path(__file__).parent.glob('*.py'))}


def source_authority():
    authority = json.loads(EXPANSION.read_text())['source_authority']
    for name, expected in authority['sources'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('scalar collection source changed: ' + name)
    for value in authority['resources'].values():
        if sha(value['path']) != value['sha256']:
            raise ValueError('scalar collection resource changed')
    return authority


def prepare():
    authority = source_authority()
    resources = {str(EXPANSION.relative_to(ROOT)): sha(EXPANSION),
                 'reports/hog26_procedural_outcome_protocol_reassessed_20260908.json': sha(ROOT / 'reports/hog26_procedural_outcome_protocol_reassessed_20260908.json')}
    for directory in ('hog26_online_value_features', 'hog26_training_expansion'):
        resources.update({str(path.relative_to(ROOT)): sha(path) for path in (ROOT / 'experiments' / directory).glob('*.py')})
    publish(PIN, {'schema': 'clasher.hog26.scalar-draw-feasibility.v1', 'sources': sources(), 'resources': resources,
                  'collection_authority_sha256': sha(EXPANSION), 'cases': CASES, 'physical_runs': 4, 'unique_scenarios': 3,
                  'policy_checkpoint': authority['resources']['checkpoint']['path'],
                  'settings': 'Unchanged scalar run(), expanded public receipts, identical fixed Hog decks, deterministic frozen policy on both sides; final case overrides both actions to no-op.',
                  'scope': 'Excluded feasibility only. Keep every outcome, including non-draws. One actor view per physical run; replay is not an independent game. No-op outcomes are not natural-draw calibration or a substitute for frozen-policy mirror controls.',
                  'fitting': False, 'reserved_data_access': False, 'policy_updates': False, 'acceptance': False})
    print(json.dumps({'status': 'scalar-draw-feasibility-pinned', 'sha256': sha(PIN)}), flush=True)


def validate():
    source_authority()
    pin = json.loads(PIN.read_text())
    if (pin['schema'] != 'clasher.hog26.scalar-draw-feasibility.v1' or pin['sources'] != sources()
            or pin['cases'] != [list(case) for case in CASES] or pin['collection_authority_sha256'] != sha(EXPANSION)
            or any(pin[key] is not False for key in ('fitting', 'reserved_data_access', 'policy_updates', 'acceptance'))):
        raise ValueError('excluded scalar control authority required')
    for path, expected in pin['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('scalar feasibility resource changed: ' + path)
    return pin
