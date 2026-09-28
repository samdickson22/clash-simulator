"""Prospective unfiltered training controls, disjoint from excluded mirror deals."""

import hashlib
import itertools
import json
import random
from pathlib import Path

import run_controls as rc
from order_contract import scenarios as excluded_scenarios
from paired_contract import OUTPUT as PROOF
from paired_contract import PIN as PROOF_PIN
from paired_contract import validate as validate_proof
from value_contract import ROOT, publish, sha

from scripts.hog26_scalar_openings import Scenario

PIN = ROOT / 'reports/hog26_scalar_mirror_training_pin_20260913.json'
OUTPUT = ROOT / 'datasets/derived/hog26_scalar_mirror_training_controls_seed1281301_20260913'
ROLE = 'train-scalar-mirror-controls'
COUNT = 256
WORKERS = 4


def scenarios():
    excluded = {case.relative_decks[0] for case in excluded_scenarios()}
    orders = [order for order in itertools.permutations(rc.DECK) if order not in excluded]
    domain = ROLE + ':1281301'
    rng = random.Random(int(hashlib.sha256((domain + ':opening').encode()).hexdigest(), 16))
    rng.shuffle(orders)
    cases = []
    for ordinal, order in enumerate(orders[:COUNT]):
        key = domain + ':' + str(ordinal) + ':' + json.dumps(order)
        streams = tuple((name, int(hashlib.sha256((key + ':' + name).encode()).hexdigest(), 16))
                        for name in ('battle', 'action-order'))
        cases.append(Scenario(hashlib.sha256(key.encode()).hexdigest(),
                              hashlib.sha256(json.dumps(order).encode()).hexdigest(),
                              ordinal, (order, order), streams, 1))
    return tuple(cases)


def sources():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    validate_proof()
    proof = json.loads((PROOF / 'complete.json').read_text())
    if proof['status'] != 'complete-excluded-paired-view-proof' or len(proof['cases']) != 3:
        raise ValueError('complete real paired-view proof required')
    if not all(row['full_trajectory_exact'] and row['seat0_arrays_exact'] for row in proof['cases'].values()):
        raise ValueError('exact observational capture required')
    guard = ROOT / 'reports/hog26_scalar_paired_views_guard_20260913.json'
    if json.loads(guard.read_text())['exit_code'] != 0:
        raise ValueError('successful paired-view supervisor required')
    resources = {str(PROOF_PIN.relative_to(ROOT)): sha(PROOF_PIN), str(guard.relative_to(ROOT)): sha(guard),
                 str((PROOF / 'complete.json').relative_to(ROOT)): sha(PROOF / 'complete.json')}
    for directory in ('hog26_scalar_paired_views', 'hog26_mirror_order_feasibility', 'hog26_scalar_draw_feasibility'):
        resources.update({str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'experiments' / directory).glob('*.py')})
    cases = scenarios()
    publish(PIN, {'schema': 'clasher.hog26.scalar-mirror-training.v1', 'sources': sources(), 'resources': resources,
                  'role': ROLE, 'physical_games': COUNT, 'actor_views': 2 * COUNT, 'workers': WORKERS,
                  'cases': [{'ordinal': c.ordinal, 'scenario_id': c.scenario_id, 'cluster_id': c.cluster_id,
                             'deck_order': list(c.relative_decks[0]), 'streams': {k: str(v) for k, v in c.stream_seeds}} for c in cases],
                  'scope': 'Separate prospective training controls only.256unique mirrored Hog orders sampled without outcomes, excluding16opened feasibility orders. Keep every complete outcome and both actual public views from each physical game. Shared cluster per pair; no manufactured independence. Deterministic frozen policy, scalar rules unchanged. Controls never estimate natural class frequency or provide validation/calibration evidence.',
                  'reserved_data_access': False, 'policy_learning': False, 'acceptance': False,
                  'mixing': 'No silent merge into natural corpus. Any later supervised WDL fit requires a separate frozen plan recording natural/control roles and weights. No fitting occurs in this collection.'})


def validate():
    validate_proof()
    pin = json.loads(PIN.read_text())
    if (pin['sources'] != sources() or pin['role'] != ROLE or pin['physical_games'] != COUNT
            or pin['workers'] != WORKERS or pin['reserved_data_access'] or pin['policy_learning'] or pin['acceptance']):
        raise ValueError('training-control authority differs')
    for name, expected in pin['resources'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('training-control resource changed: ' + name)
    return pin
