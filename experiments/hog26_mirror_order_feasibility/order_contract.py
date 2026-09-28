"""Fixed unfiltered mirror-order feasibility, excluded from every model role."""

import hashlib
import json
from pathlib import Path

import run_controls as rc
from value_contract import ROOT, publish, sha

from scripts.hog26_scalar_openings import Scenario

PIN = ROOT / 'reports/hog26_mirror_order_feasibility_pin_20260913.json'
OUTPUT = ROOT / 'reports/hog26_mirror_order_feasibility_20260913'
RESULT = OUTPUT / 'complete.json'


def scenarios():
    values = []
    for direction, deck in enumerate((rc.DECK, tuple(reversed(rc.DECK)))):
        for shift in range(8):
            ordinal = direction * 8 + shift
            order = deck[shift:] + deck[:shift]
            domain = f'excluded-scalar-mirror-order-feasibility-1281201:{ordinal}'
            streams = tuple((name, int(hashlib.sha256((domain + ':' + name).encode()).hexdigest(), 16))
                            for name in ('battle', 'action-order'))
            identity = hashlib.sha256(domain.encode()).hexdigest()
            cluster = hashlib.sha256(json.dumps(order).encode()).hexdigest()
            values.append(Scenario(identity, cluster, ordinal, (order, order), streams, 1))
    return tuple(values)


def sources():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    rc.validate()
    cases = scenarios()
    if len({case.relative_decks for case in cases}) != 16:
        raise ValueError('sixteen distinct mirrored orders required')
    resources = {str(rc.PIN.relative_to(ROOT)): sha(rc.PIN)}
    resources.update({str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'experiments/hog26_scalar_draw_feasibility').glob('*.py')})
    publish(PIN, {'schema': 'clasher.hog26.excluded-mirror-order.v1', 'sources': sources(), 'resources': resources,
                  'orders': [list(case.relative_decks[0]) for case in cases], 'count': 16, 'replay_ordinal': 0,
                  'scope': 'Excluded feasibility only. Fixed eight cyclic orders and eight reversed cyclic orders, both seats identical, same frozen policy and unchanged scalar physics. Retain every result, no outcome filtering. No no-op or scripted action overrides. One actor view per physical run; replay not independent.',
                  'fitting': False, 'reserved_data_access': False, 'acceptance': False})


def validate():
    rc.validate()
    pin = json.loads(PIN.read_text())
    if pin['sources'] != sources() or pin['orders'] != [list(s.relative_decks[0]) for s in scenarios()]:
        raise ValueError('mirror order authority changed')
    for path, expected in pin['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('mirror order resource changed')
    return pin
