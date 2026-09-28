"""Three excluded real-game parity controls for observational paired capture."""

import json
from pathlib import Path

from order_contract import OUTPUT as BASELINE
from order_contract import PIN as ORDER_PIN
from order_contract import validate as validate_orders
from value_contract import ROOT, publish, sha

PIN = ROOT / 'reports/hog26_scalar_paired_views_pin_20260913.json'
OUTPUT = ROOT / 'reports/hog26_scalar_paired_views_20260913'
RESULT = OUTPUT / 'complete.json'
ORDINALS = (0, 6, 12)


def sources():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    validate_orders()
    complete = json.loads((BASELINE / 'complete.json').read_text())
    resources = {str(ORDER_PIN.relative_to(ROOT)): sha(ORDER_PIN),
                 str((BASELINE / 'complete.json').relative_to(ROOT)): sha(BASELINE / 'complete.json')}
    for ordinal in ORDINALS:
        for suffix in ('.json', '.npz', '-audit.json'):
            p = BASELINE / f'order{ordinal:02}{suffix}'
            if sha(p) != complete['artifacts'][p.name]:
                raise ValueError('baseline control changed')
            resources[str(p.relative_to(ROOT))] = sha(p)
    publish(PIN, {'schema': 'clasher.hog26.excluded-paired-view-proof.v1', 'sources': sources(), 'resources': resources,
                  'ordinals': list(ORDINALS), 'scope': 'Excluded replay of one loss and both draw controls. Exact original seat0 arrays and full battle trace; independently validated seat1 labels and public arrays. One physical run and policy call per decision. No fitting, calibration, reserved data or physics changes.', 'acceptance': False})


def validate():
    validate_orders()
    pin = json.loads(PIN.read_text())
    if pin['sources'] != sources() or pin['ordinals'] != list(ORDINALS):
        raise ValueError('paired proof authority changed')
    for path, expected in pin['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('paired proof resource changed')
    return pin
