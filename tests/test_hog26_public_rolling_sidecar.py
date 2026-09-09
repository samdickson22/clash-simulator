import pytest
import torch

from clasher.torch_sim.simple_rolling_spells import FastRollingSpellState
from scripts.hog26_public_rolling_sidecar import project_public_rollers


def test_rolling_position_ignores_hit_ledger_and_future_payload():
    rollers = FastRollingSpellState.empty(1, max_rollers=1)
    rollers.active[:] = True
    rollers.source_card_id[:] = 1
    rollers.x_units[:] = 3500
    rollers.y_units[:] = 14500
    tokens = torch.tensor([0, 9])
    expected = project_public_rollers(rollers, tokens)
    rollers.hit_stable_ids[:] = 123
    rollers.target_y_units[:] = 31000
    rollers.damage[:] = 777
    rollers.impact_spawn_count[:] = 99
    for actual, reference in zip(project_public_rollers(rollers, tokens), expected, strict=True):
        torch.testing.assert_close(actual, reference, rtol=0, atol=0)
    rollers.active[:] = False
    assert not project_public_rollers(rollers, tokens)[2].any()


def test_unregistered_active_roller_is_rejected():
    rollers = FastRollingSpellState.empty(1, max_rollers=1)
    rollers.active[:] = True
    with pytest.raises(ValueError, match="appearance rule"):
        project_public_rollers(rollers, torch.tensor([0, 9]))
