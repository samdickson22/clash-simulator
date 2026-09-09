from dataclasses import fields

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.dynamic_spells import create_spell_from_json
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.rl.structured_obs import EntityCapacityError, StructuredObservationBuilder
from scripts.hog26_scalar_actor_projection import build_scalar_reference_actors
from scripts.hog26_scalar_public_effect_adapter import ScalarArrowsAppearance


def fixture(capacity=128):
    battle = BattleState()
    vocabulary = load_current_client_typed_vocabulary()
    builder = StructuredObservationBuilder(token_names=vocabulary.token_names,
                                           max_entities=capacity, card_semantics_version=3,
                                           canonical_lane_globals=True)
    before = set(battle.entities)
    spell = create_spell_from_json(battle.card_loader.get_card("Arrows")._raw_entry,
                                   battle.card_loader.load_card_definitions())
    assert spell.cast(battle, 0, Position(3.5, 25.5))
    born = [entity for key, entity in battle.entities.items() if key not in before]
    bindings = ScalarArrowsAppearance.compile(battle.card_loader, vocabulary).bind_cast(born)
    return battle, builder, born, bindings


def project(battle, builder, bindings):
    return build_scalar_reference_actors(
        battle, builder, appearances=bindings,
        visible_to=lambda entity, seat: entity.is_visible_to(seat),
    )


def test_fixed_actor_projection_uses_typed_launched_effects_and_no_critic(monkeypatch):
    battle, builder, _, bindings = fixture()

    def forbidden(*args, **kwargs):
        raise AssertionError("critic or unreviewed entity builder used")

    monkeypatch.setattr(builder, "build", forbidden)
    monkeypatch.setattr(builder, "build_actor", forbidden)
    monkeypatch.setattr(builder, "_entity_row", forbidden)
    actors = project(battle, builder, bindings)
    for actor in actors:
        assert actor.entity_features.shape == (128, 32)
        assert int(actor.entity_mask.sum()) == 16  # six towers and first ten arrows
        arrow = actor.entity_mask & (actor.entity_features[:, 6] == 1)
        assert int(arrow.sum()) == 10
        assert (actor.entity_ids[arrow] == bindings[0].token).all()
        assert not actor.entity_features[arrow, 9:].any()
        assert not actor.entity_features[~actor.entity_mask].any()
        assert all(not field.name.startswith("critic") for field in fields(actor))


def test_enemy_private_state_and_future_effect_payload_do_not_change_seat_zero():
    battle, builder, born, bindings = fixture()
    before = project(battle, builder, bindings)[0]
    battle.players[1].elixir = 9.876
    battle.players[1].hand[:] = ["Rocket"] * 4
    battle.players[1].cycle_queue.clear()
    battle.players[1].cycle_queue.extend(["Poison"] * 4)
    battle.rng.seed(888888)
    for entity in battle.entities.values():
        entity.target_id = 999999
        entity.damage = 999999
        entity.stun_timer = 1.234
    for entity in born:
        entity.target_position = Position(17, 1)
        entity.spell_name = "unobserved source"
        entity.damage_group_hit_entity_ids = {999999}
    after = project(battle, builder, bindings)[0]
    for field in fields(before):
        np.testing.assert_array_equal(getattr(before, field.name), getattr(after, field.name))


def test_unresolved_effects_and_visible_capacity_overflow_reject():
    battle, builder, _, bindings = fixture()
    with pytest.raises(ValueError, match="no audited appearance"):
        project(battle, builder, ())
    battle, builder, _, bindings = fixture(capacity=8)
    with pytest.raises(EntityCapacityError):
        project(battle, builder, bindings)


def test_other_seat_visible_effect_count_cannot_change_hidden_seat_padding():
    battle, builder, born, bindings = fixture()
    identities = {id(entity) for entity in born}

    def views():
        return build_scalar_reference_actors(
            battle, builder, appearances=bindings,
            visible_to=lambda entity, seat: id(entity) not in identities or seat == 1,
        )

    before = views()
    for entity in born:
        entity.launch_delay = 0
    after = views()
    assert int(before[1].entity_mask.sum()) == 16
    assert int(after[1].entity_mask.sum()) == 36
    for field in fields(before[0]):
        np.testing.assert_array_equal(getattr(before[0], field.name), getattr(after[0], field.name))
