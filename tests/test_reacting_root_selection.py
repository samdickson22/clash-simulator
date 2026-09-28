import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "root_selector",
    Path(__file__).resolve().parents[1] / "scripts/select_reacting_public_root.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def loader():
    return SimpleNamespace(
        get_card=lambda name: SimpleNamespace(
            _raw_entry={
                "id": {"Cannon": 27000000, "Goblins": 26000002, "HogRider": 26000021}[
                    name
                ]
            }
        )
    )


def command(tick, card="Cannon", owner=1, accepted=True):
    return {
        "submitted_tick": tick,
        "owner": owner,
        "name": card,
        "native_acceptance_spend_evidence": accepted,
    }


def rule():
    return MODULE.SelectionRule(
        owner=1,
        earliest_tick=1800,
        card_ids=[27000000, 26000002],
        x_offsets=[-1, 1],
        response_seeds=[3, 4],
    )


def test_rule_uses_first_eligible_command_not_later_alternative():
    rows = [
        command(2300),
        command(1770),
        command(1810, "HogRider"),
        command(1800, owner=0),
        command(1830, accepted=False),
        command(1860, "Goblins"),
    ]
    assert MODULE.first_root(rows, rule(), loader()) == rows[-1]


def test_no_eligible_root_fails_without_fallback():
    with pytest.raises(ValueError, match="No root"):
        MODULE.first_root(
            [command(1799), command(1800, accepted=False)], rule(), loader()
        )


def test_finite_window_does_not_substitute_a_later_root():
    bounded = rule().model_copy(update={"latest_tick": 2100})
    assert (
        MODULE.first_root([command(2100)], bounded, loader())["submitted_tick"] == 2100
    )
    with pytest.raises(ValueError, match="No root"):
        MODULE.first_root([command(2101)], bounded, loader())


def test_reversed_selection_window_fails():
    with pytest.raises(ValueError, match="ends before"):
        MODULE.first_root(
            [command(1800)], rule().model_copy(update={"latest_tick": 1700}), loader()
        )


def test_event_sampling_is_deterministic_and_ignores_outcomes():
    rows = [command(t) for t in (900, 1200, 2100, 2700)]
    sampled = rule().model_copy(
        update={"earliest_tick": 90, "latest_tick": 6000, "event_selection_seed": 42}
    )
    first = MODULE.first_root(rows, sampled, loader())
    modified = [row | {"winner": 999, "terminal_hp": -999999} for row in reversed(rows)]
    second = MODULE.first_root(modified, sampled, loader())
    assert first["submitted_tick"] == second["submitted_tick"]
    choices = {
        MODULE.first_root(
            rows, sampled.model_copy(update={"event_selection_seed": seed}), loader()
        )["submitted_tick"]
        for seed in range(30)
    }
    assert choices == {900, 1200, 2100, 2700}


def test_event_sampling_still_fails_when_no_eligible_play_exists():
    sampled = rule().model_copy(
        update={"earliest_tick": 90, "latest_tick": 6000, "event_selection_seed": 42}
    )
    with pytest.raises(ValueError, match="No root"):
        MODULE.first_root([command(900, accepted=False)], sampled, loader())
