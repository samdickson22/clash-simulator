import random

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.dynamic_spells import create_spell_from_json
from clasher.entities import RollingProjectile
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from scripts.hog26_scalar_public_effect_adapter import (
    ScalarArrowsAppearance,
    project_scalar_public_effects,
)


def _cast(owner):
    loader = CardDataLoader()
    vocabulary = load_current_client_typed_vocabulary()
    rule = ScalarArrowsAppearance.compile(loader, vocabulary)
    battle = BattleState(rng=random.Random(12019))
    before = set(battle.entities)
    spell = create_spell_from_json(loader.get_card("Arrows")._raw_entry,
                                   loader.load_card_definitions())
    assert spell.cast(battle, owner, Position(9, 16))
    born = [e for key, e in battle.entities.items() if key not in before]
    return battle, born, rule.bind_cast(born), vocabulary, rule


def _project(born, bindings):
    return project_scalar_public_effects(
        born, bindings, visible_to=lambda entity, seat: entity.is_visible_to(seat),
    )


@pytest.mark.parametrize("owner", [0, 1])
def test_actual_arrows_launch_boundaries_and_typed_identity(owner):
    battle, born, bindings, vocabulary, rule = _cast(owner)
    assert vocabulary.token_names[rule.token].startswith("projectile:")
    for tick in range(10):
        ids, features, mask = _project(born, bindings)
        expected = sum(e.launch_delay <= 0 and e.is_alive for e in born)
        assert expected in {10, 20, 30}
        assert ids.shape == (1, 2, expected)
        assert features.shape == (1, 2, expected, 6)
        assert mask.all() and (ids == rule.token).all()
        assert (features[0, owner, :, 2] == 1).all()
        assert (features[..., 4] == 1).all() and (features[..., 5] == 0).all()
        torch.testing.assert_close(features[0, 0, :, :2] + features[0, 1, :, :2],
                                   torch.ones((expected, 2)))
        if tick == 0:
            assert expected == 10
        if tick == 5:
            assert expected == 20
        if tick == 9:
            assert expected == 30
        for entity in born:
            entity.update(.05, battle)


@pytest.mark.parametrize("owner", [0, 1])
def test_private_future_perturbations_do_not_change_current_output(owner):
    _, born, bindings, _, _ = _cast(owner)
    before = _project(born, bindings)
    for index, entity in enumerate(born):
        entity.target_position = Position(100 + index, -100)
        entity.damage = 999999
        entity.crown_tower_damage = 77777
        entity.source_name = "secret source"
        entity.spell_name = "secret spell"
        entity.spawn_character = "secret payload"
        entity.damage_group_hit_entity_ids = {999, 1000}
        entity.travel_speed = 987
        if entity.launch_delay > 0:
            entity.position = Position(-999, 999)
            entity.launch_delay += 10
    after = _project(born, bindings)
    for a, b in zip(before, after):
        assert torch.equal(a, b)


def test_explicit_visibility_hidden_slots_and_unresolved_fail_closed():
    _, born, bindings, _, _ = _cast(0)
    ids, features, mask = project_scalar_public_effects(
        born, bindings, visible_to=lambda entity, seat: seat == 0,
    )
    assert mask[0, 0].all() and not mask[0, 1].any()
    assert not ids[0, 1].any() and not features[0, 1].any()
    empty = project_scalar_public_effects(born, (), visible_to=lambda *_: False)
    assert empty[0].shape == (1, 2, 0)
    with pytest.raises(ValueError, match="no audited appearance"):
        _project(born, ())
    with pytest.raises(ValueError, match="30 distinct"):
        ScalarArrowsAppearance(2).bind_cast(born[:10])


def test_queued_roller_is_not_an_observed_effect_then_fails_unresolved():
    roller = RollingProjectile(id=999, position=Position(5, 5), player_id=0,
                               card_stats=None, hitpoints=1, max_hitpoints=1,
                               damage=1, range=0, sight_range=0, spawn_delay=.65, time_alive=0)
    assert _project([roller], ())[0].shape == (1, 2, 0)
    roller.time_alive = .65
    with pytest.raises(ValueError, match="no audited appearance"):
        _project([roller], ())
