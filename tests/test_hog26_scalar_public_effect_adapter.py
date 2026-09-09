import random

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.dynamic_spells import create_spell_from_json, load_dynamic_spells
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


@pytest.mark.parametrize("owner", [0, 1])
@pytest.mark.parametrize("card,token,kind", [
    ("Fireball", 289, 1), ("GiantSnowball", 336, 1), ("Rocket", 331, 1),
    ("Log", 316, 1), ("BarbLog", 272, 1), ("GoblinBarrel", 297, 1),
    ("Poison", 40, 2), ("BarbarianBarrel", 272, 1),
    ("Earthquake", 16, 2), ("Freeze", 24, 2),
    ("Tornado", 51, 2), ("Graveyard", 34, 2),
])
def test_serialized_spell_lifecycle_and_no_private_payload(card, token, kind, owner):
    from scripts.hog26_scalar_public_effect_adapter import ScalarSpellAppearance

    loader = CardDataLoader()
    vocabulary = load_current_client_typed_vocabulary()
    assert len(vocabulary.token_names) == 494
    rule = ScalarSpellAppearance.compile(card, loader, vocabulary)
    assert rule.token == token
    battle = BattleState(rng=random.Random(19))
    before = set(battle.entities)
    spell = create_spell_from_json(loader.get_card(card)._raw_entry,
                                   loader.load_card_definitions())
    if card == "Graveyard":
        spell = load_dynamic_spells(loader.data_file)["Graveyard"]
    target = Position(9, 16)
    assert spell.cast(battle, owner, target)
    born = [e for key, e in battle.entities.items() if key not in before]
    bindings = rule.bind_cast(born)
    entity = born[0]
    seen_visible = False
    for tick in range(260):
        ids, features, mask = _project(born, bindings)
        pending = (isinstance(entity, RollingProjectile)
                   and entity.time_alive + 1e-9 < entity.spawn_delay)
        expected = int(entity.is_alive and not pending)
        assert ids.shape == (1, 2, expected)
        if expected:
            seen_visible = True
            assert (ids == token).all() and mask.all()
            assert (features[..., 3 + kind] == 1).all()
            # Mutations of labels and combat payload do not affect this frame.
            saved = {key: getattr(entity, key, None) for key in
                     ("damage", "source_name", "spell_name", "spawn_character_data",
                      "target_position", "crown_tower_damage", "spawn_offsets", "spawn_deadlines",
                      "skeleton_data", "attract_percentage", "push_speed_factor")}
            entity.damage = 999999
            entity.source_name = "unobservable source"
            entity.spell_name = "unobservable cast name"
            entity.spawn_character_data = {"secret": "future unit"}
            entity.target_position = Position(-999, 999)
            entity.crown_tower_damage = 999
            entity.spawn_offsets = ((999, 999),)
            entity.spawn_deadlines = (999,)
            entity.skeleton_data = {"secret": "future skeleton"}
            entity.attract_percentage = 999
            entity.push_speed_factor = 999
            changed = _project(born, bindings)
            for a, b in zip((ids, features, mask), changed):
                assert torch.equal(a, b)
            for key, value in saved.items():
                setattr(entity, key, value)
        if not entity.is_alive:
            break
        entity.update(.05, battle)
    assert seen_visible and not entity.is_alive
    assert tick < 259


def test_unknown_registry_identity_and_wrong_cast_receipts_fail_closed():
    from types import SimpleNamespace

    from scripts.hog26_scalar_public_effect_adapter import ScalarSpellAppearance

    loader = CardDataLoader()
    vocab = load_current_client_typed_vocabulary()
    with pytest.raises(ValueError, match="no audited"):
        ScalarSpellAppearance.compile("Lightning", loader, vocab)
    with pytest.raises(ValueError, match="no audited"):
        ScalarSpellAppearance.compile("Poison", loader,
                                      SimpleNamespace(resolve=lambda *_: 1))
    _, born, _, _, _ = _cast(0)
    rule = ScalarSpellAppearance.compile("Poison", loader, vocab)
    with pytest.raises(ValueError, match="lifecycle"):
        rule.bind_cast(born[:1])


def test_zap_has_no_persistent_appearance_and_rejects_unresolved_children():
    from scripts.hog26_scalar_public_effect_adapter import ScalarSpellAppearance

    loader = CardDataLoader()
    rule = ScalarSpellAppearance.compile("Zap", loader, load_current_client_typed_vocabulary())
    assert rule.token == 0 and rule.entity_type is None and rule.appearance_kind == 0
    assert rule.bind_cast(()) == ()
    _, born, _, _, _ = _cast(0)
    with pytest.raises(ValueError, match="unresolved child"):
        rule.bind_cast(born[:1])
