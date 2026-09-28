"""An unchanged saved estimator is the negative control for state fingerprinting."""

import json
import pickle

import torch
from probe import canonical_state
from state_fields import state_fields
from value_contract import OUTPUT, ROOT, load_plan, publish, sha


def main():
    torch.set_num_threads(1)
    load_plan()
    source = OUTPUT / 'trees/seed1279501-fold0/model.pkl'
    with source.open('rb') as stream:
        models = pickle.load(stream)
    controls = {}
    for name, model in models.items():
        roundtrip = pickle.loads(pickle.dumps(model, protocol=5))
        first, second = state_fields(model), state_fields(roundtrip)
        if first != second:
            raise ValueError('field checker is not stable on the unchanged serial estimator')
        controls[name] = {'whole_object_before': canonical_state(model), 'whole_object_after': canonical_state(roundtrip),
                          'all_fields_exact': True, 'field_count': len(first['fields']), 'state_fields': first}
    if controls['classifier']['whole_object_before'] == controls['classifier']['whole_object_after']:
        raise ValueError('observed whole-pickle false rejection did not reproduce')
    result = {'status': 'complete-unchanged-estimator-serialization-control', 'reference_sha256': sha(source),
              'controls': controls, 'source_sha256': sha(__file__), 'checker_sha256': sha(__file__.replace('check_serialization.py', 'state_fields.py')),
              'learned_fields_ignored': [], 'only_normalized_field': 'copied_estimator._bin_mapper.n_threads',
              'thread_equivalence_proven': False, 'acceptance': False}
    publish(ROOT / 'reports/hog26_tree_state_serialization_control_20260913.json', result)
    print(json.dumps({'status': result['status'], 'all_fields_exact': True}), flush=True)


if __name__ == '__main__':
    main()
