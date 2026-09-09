import pytest
import torch

from clasher.torch_sim.simple_effects import FastEffectState
from scripts.hog26_ordinary_projectile_sidecar import (
    OrdinaryProjectileRules,
    project_primary_effect_pool,
)


def fixture():
    rules = OrdinaryProjectileRules(torch.tensor([-1, 1, 0, 2]),
                                    torch.tensor([0, 17, 0, 0]), ("",) * 4)
    effects = FastEffectState.empty(1, max_effects=2)
    effects.active[:] = True
    effects.source_card_id[0] = torch.tensor([1, 2])
    effects.kind[0] = torch.tensor([0, 1])
    effects.x_units[:] = 1000
    return effects, rules


def test_registered_projectile_excludes_direct_hit_queue():
    effects, rules = fixture()
    tokens, features, mask = project_primary_effect_pool(effects, rules)
    assert tokens.tolist() == [[[17, 0], [17, 0]]]
    assert mask.tolist() == [[[True, False], [True, False]]]
    assert not features[..., 1, :].any()


@pytest.mark.parametrize("card,kind", [(0, 0), (3, 1), (99, 0), (1, 1)])
def test_unknown_area_tower_or_mismatched_event_stops_projection(card, kind):
    effects, rules = fixture()
    effects.source_card_id[0, 0] = card
    effects.kind[0, 0] = kind
    with pytest.raises(ValueError, match="enrichment must stop"):
        project_primary_effect_pool(effects, rules)


def test_private_combat_values_do_not_change_public_projection():
    effects, rules = fixture()
    expected = project_primary_effect_pool(effects, rules)
    effects.damage[:] = 9876
    effects.target_id[:] = 312
    effects.target_x_units[:] = 18000
    effects.lifetime_ticks[:] = 88
    effects.next_damage_tick[:] = 77
    actual = project_primary_effect_pool(effects, rules)
    for left, right in zip(actual, expected, strict=True):
        torch.testing.assert_close(left, right, rtol=0, atol=0)
