"""Seven-arm S-default admission; X1/X7 share one stage3 recipe slot."""
import json
from experiment_x7 import load_experiment
from stage3_sdefault_admission import (frozen as original_frozen, context, allowed,
    load_receipt, arm_order, BASE, SMOKE_BASE)


def frozen(job):
    # Retain the exact original default-layer and block qualifications.
    load_experiment(job)  # Verifies every X7 source and seed addendum pin.
    return original_frozen(job)


def selection(job):
    arms=load_experiment(job)['arms'];survivors=[]
    for arm in arms:
        off=json.loads((job/'offline'/f'{arm}.json').read_text())
        if off['survives']:
            two=json.loads((job/'stage2'/f'{arm}.json').read_text())
            if two['survives']:
                survivors.append((two['loss'],-off['teacher']['metrics']['hard_action_agreement']['value'],int(arm[1:]),arm))
    ranked=sorted(survivors)
    family=next((row[-1] for row in ranked if row[-1] in ('X1','X7')),None)
    eligible=[row for row in ranked if row[-1] not in ('X1','X7') or row[-1]==family]
    return [row[-1] for row in eligible[:3]]
