from types import SimpleNamespace

import pytest
import torch

from clasher.torch_sim.simple_effects import FastEffectState
from scripts.hog26_ordinary_projectile_sidecar import (
    OrdinaryProjectileRules,
    project_primary_effect_pool,
)
from scripts.hog26_public_tower_shot_rules import with_public_tower_shots


def fixture():
    original = ("<none>", "projectile:Other")
    spec = SimpleNamespace(x_units=torch.tensor([[3500, 14500, 9000]] * 2),
                           y_units=torch.tensor([[6500, 6500, 2500], [25500, 25500, 29500]]))
    base = OrdinaryProjectileRules(torch.tensor([-1]), torch.tensor([0]), ("tower",))
    rules, names = with_public_tower_shots(base, spec, original, "TowerPrincessProjectile")
    effects = FastEffectState.empty(1, max_effects=2)
    effects.active[:] = True
    effects.source_x_units[0] = torch.tensor([3500, 9000])
    effects.source_y_units[0] = torch.tensor([6500, 2500])
    effects.x_units[:] = 5000
    effects.y_units[:] = 7000
    return original, rules, names, effects


def test_tower_categories_preserve_policy_vocabulary_prefix():
    original, rules, names, effects = fixture()
    assert names[:len(original)] == original
    tokens, _, mask = project_primary_effect_pool(effects, rules)
    assert tokens[0, 0].tolist() == [2, 3]
    assert mask.all()


@pytest.mark.parametrize("field,value", [("source_x_units", 3501), ("source_owner", 1)])
def test_unknown_launch_origin_or_owner_is_rejected(field, value):
    _, rules, _, effects = fixture()
    getattr(effects, field)[0, 0] = value
    with pytest.raises(ValueError, match="enrichment must stop"):
        project_primary_effect_pool(effects, rules)


def test_future_target_and_damage_do_not_affect_tower_frames():
    _, rules, _, effects = fixture()
    expected = project_primary_effect_pool(effects, rules)
    effects.target_x_units[:] = 18000
    effects.target_y_units[:] = 30000
    effects.damage[:] = 9000
    actual = project_primary_effect_pool(effects, rules)
    for left, right in zip(actual, expected, strict=True):
        torch.testing.assert_close(left, right, rtol=0, atol=0)
