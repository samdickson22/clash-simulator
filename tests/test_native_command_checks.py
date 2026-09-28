"""Timing acknowledgements must bind to the actual one-tick state transition."""

import copy

import pytest

from clasher.rl.native_command_checks import validate_command_step


def sample():
    before = {"tick": 90, "generation": 3, "stateEpoch": 3}
    after = before | {"tick": 91}
    receipt = {
        "ok": True,
        "kind": "card",
        "sequence": 9,
        "registeredAtTick": 90,
        "executeTick": 91,
        "generation": 3,
        "stateEpoch": 3,
    }
    return before, after, receipt


def test_valid_step_with_zero_or_multiple_commands():
    before, after, r = sample()
    validate_command_step(before, after, [])
    validate_command_step(before, after, [r, r | {"sequence": 10}])


@pytest.mark.parametrize(
    "fault",
    [
        "late_step",
        "new_epoch",
        "late_receipt",
        "old_receipt",
        "rejected",
        "duplicate",
        "boolean_tick",
    ],
)
def test_inconsistent_command_evidence_is_rejected(fault):
    before, after, r = sample()
    receipts = [r]
    if fault == "late_step":
        after["tick"] = 92
    elif fault == "new_epoch":
        after["generation"] = 4
    elif fault == "late_receipt":
        r["executeTick"] = 92
    elif fault == "old_receipt":
        r["stateEpoch"] = 2
    elif fault == "rejected":
        r["ok"] = False
    elif fault == "duplicate":
        receipts.append(copy.deepcopy(r))
    else:
        r["registeredAtTick"] = True
    with pytest.raises(ValueError):
        validate_command_step(before, after, receipts)
