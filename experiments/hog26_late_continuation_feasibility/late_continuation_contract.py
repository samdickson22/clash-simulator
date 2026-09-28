"""Excluded late-state initialization probe; not ranking or natural calibration."""

import hashlib
import itertools
import json
import random
from pathlib import Path

import run_controls as rc
from order_contract import OUTPUT as EARLY_BASELINE
from order_contract import scenarios as old_scenarios
from paired_contract import validate as validate_pairs
from training_contract import scenarios as training_scenarios
from training_contract import validate as validate_training
from value_contract import ROOT, publish, sha

from scripts.hog26_scalar_openings import Scenario

PIN = ROOT / 'reports/hog26_late_continuation_feasibility_pin_20260913.json'
OUTPUT = ROOT / 'reports/hog26_late_continuation_feasibility_20260913'
RESULT = OUTPUT / 'complete.json'


def cases():
    excluded = {s.relative_decks[0] for s in (*old_scenarios(), *training_scenarios())}
    orders = [order for order in itertools.permutations(rc.DECK) if order not in excluded]
    domain = 'excluded-late-frozen-continuation-1281501'
    rng = random.Random(int(hashlib.sha256(domain.encode()).hexdigest(), 16))
    rng.shuffle(orders)
    result = []
    for ordinal, order in enumerate(orders[:8]):
        cluster = hashlib.sha256(json.dumps(order).encode()).hexdigest()
        for release in (4000, 4800):
            key = domain + ':' + str(ordinal) + ':' + str(release)
            streams = tuple((name, int(hashlib.sha256((key + ':' + name).encode()).hexdigest(), 16))
                            for name in ('battle', 'action-order'))
            scenario = Scenario(hashlib.sha256(key.encode()).hexdigest(), cluster, ordinal,
                                (order, order), streams, 1)
            result.append((f'order{ordinal}-release{release}', release, scenario))
    return tuple(result)


def sources():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    validate_pairs()
    validate_training()
    resources = {}
    for directory in ('hog26_scalar_paired_views', 'hog26_scalar_mirror_training', 'hog26_mirror_order_feasibility'):
        resources.update({str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'experiments' / directory).glob('*.py')})
    for name in ('order00.json', 'order00.npz'):
        p = EARLY_BASELINE / name
        resources[str(p.relative_to(ROOT))] = sha(p)
    publish(PIN, {'schema': 'clasher.hog26.excluded-late-continuation.v1', 'sources': sources(), 'resources': resources,
                  'cases': [{'name': name, 'release_tick': release, 'order': list(s.relative_decks[0]),
                             'scenario_id': s.scenario_id, 'cluster_id': s.cluster_id} for name, release, s in cases()],
                  'new_physical_runs': 16, 'opening_clusters': 8, 'extra_checks': ['zero-prefix original trajectory identity', 'exact first late-prefix replay'],
                  'scope': 'Excluded feasibility only. Eight fixed fresh mirrored orders, disjoint from16opened and256training-control orders. Both players pass through a real simulated prefix, then original frozen policy acts until actual terminal. No clock/state shortcut, physics change, policy learning, search, ranking or outcome filtering. Both actual views retained. Only post-release states have an unmodified-policy future, but ALL probe data remain excluded from fitting/calibration.',
                  'fitting': False, 'reserved_data_access': False, 'acceptance': False})


def validate():
    validate_pairs()
    validate_training()
    pin = json.loads(PIN.read_text())
    if pin['sources'] != sources() or pin['fitting'] or pin['acceptance']:
        raise ValueError('excluded continuation authority changed')
    for path, expected in pin['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('continuation source changed')
    return pin
