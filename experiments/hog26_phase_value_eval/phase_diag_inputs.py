"""Load the unchanged decoder only after the separate phase evaluation pin."""

import json

from diagnostic_data import load_diagnostic
from phase_eval_contract import OLD_DIAGNOSTIC, OLD_PIN, validate_pin


def load_inputs():
    validate_pin()
    result = load_diagnostic(verified_pin=json.loads(OLD_PIN.read_text()))
    features, globals_x, offsets, _evaluation, audit = result
    expected = json.loads((OLD_DIAGNOSTIC / 'manifest.json').read_text())['data_audit']
    if audit != expected or features.shape != (155496, 814) or globals_x.shape != (155496, 36) or len(offsets) != 385:
        raise ValueError('unchanged phase diagnostic input audit required')
    return result
