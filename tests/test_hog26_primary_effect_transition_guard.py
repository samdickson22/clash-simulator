from types import SimpleNamespace

import pytest
import torch

from clasher.torch_sim.simple_effects import FastEffectState
from scripts.hog26_primary_effect_transition_guard import (
    require_supported_primary_births,
)


def receipt(*, area=False, projectile=False, slot=0):
    return SimpleNamespace(accepted=torch.tensor([[True]]), area=torch.tensor([[area]]),
                           projectile=torch.tensor([[projectile]]), effect_slot=torch.tensor([[slot]]))


def test_consumed_area_birth_cannot_silently_pass_empty_pool():
    effects = FastEffectState.empty(1, max_effects=1)
    with pytest.raises(ValueError, match="area birth"):
        require_supported_primary_births(receipt(area=True), effects)


def test_transient_projectile_needs_event_history():
    effects = FastEffectState.empty(1, max_effects=1)
    with pytest.raises(ValueError, match="transient projectile"):
        require_supported_primary_births(receipt(projectile=True), effects)
    effects.active[:] = True
    assert require_supported_primary_births(receipt(projectile=True), effects).all()


def test_direct_hit_queue_is_not_misclassified_as_area_spell():
    assert require_supported_primary_births(receipt(), FastEffectState.empty(1)).all()


def test_missing_projectile_receipt_is_rejected():
    with pytest.raises(ValueError, match="allocation receipt"):
        require_supported_primary_births(receipt(projectile=True, slot=-1), FastEffectState.empty(1))
