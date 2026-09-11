from dataclasses import fields

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, DeathAreaEffectContainer, Troop
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.rl.structured_obs import EntityCapacityError, StructuredObservationBuilder
from clasher.torch_sim.diagnostics import battle_snapshot
from scripts.hog26_scalar_actor_projection import compile_scalar_hand_lookup
from scripts.hog26_scalar_death_actor_adapter import ScalarDeathActorAdapter
from scripts.hog26_scalar_death_effect_receipts import (
    DeathAppearanceRule,
    ScalarDeathEffectRecorder,
)


def _fixture(card, owner=0, *, extension=False, capacity=128):
    battle = BattleState()
    vocab = load_current_client_typed_vocabulary()
    names = (*vocab.token_names, "building_body:SkeletonContainerNew") if extension else vocab.token_names
    builder = StructuredObservationBuilder(token_names=names, max_entities=capacity,
                                           card_semantics_version=3, canonical_lane_globals=True)
    source = battle._spawn_entity(Building if card == "BombTower" else Troop,
                                  Position(9, 12), owner, battle.card_loader.get_card(card))
    extra = {"building_body:SkeletonContainerNew": len(vocab.token_names)} if extension else None
    rule = DeathAppearanceRule.compile(card, source, battle.card_loader, vocab, extra_tokens=extra)
    return battle, builder, source, rule, compile_scalar_hand_lookup(builder, vocab)


@pytest.mark.parametrize("card", ["Balloon", "BombTower", "SkeletonBarrel", "IceGolem", "Lumberjack"])
@pytest.mark.parametrize("owner", [0, 1])
def test_registered_deaths_join_actor_without_combat_or_future_fields(card, owner):
    battle, builder, source, rule, hand_lookup = _fixture(card, owner, extension=card == "SkeletonBarrel")
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: True) as recorder:
        source.take_damage(source.hitpoints + 1)
        adapter = ScalarDeathActorAdapter(battle, builder, recorder, hand_lookup=hand_lookup, visible_to=lambda *_: True)
        if card == "Lumberjack":
            assert len(recorder.registered_internal_containers) == 1
            assert all(a.entity_mask.sum() == 6 for a in adapter.build())
            for _ in range(12):
                battle.step()
        before = battle_snapshot(battle)
        rng = battle.rng.getstate()
        actors = adapter.build()
        assert battle_snapshot(battle) == before and battle.rng.getstate() == rng
        for actor in actors:
            selected = actor.entity_ids == rule.token
            assert selected.sum() == 1
            row = actor.entity_features[selected][0]
            assert row[7] == 1 and not row[4:7].any()
            assert not row[9:].any()
        entity = recorder.receipts[0].entity
        entity.explosion_timer = 999999
        entity.explosion_damage = 999999
        entity.death_spawn_data = {"secret": "future payload"}
        entity.source_name = "private source"
        entity.spell_name = "future explosion"
        changed = adapter.build()
        for a, b in zip(actors, changed):
            for field in fields(a):
                assert np.array_equal(getattr(a, field.name), getattr(b, field.name))


def test_unregistered_container_is_not_silently_excluded():
    battle, builder, source, rule, hand_lookup = _fixture("Lumberjack")
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: True) as recorder:
        source.take_damage(source.hitpoints + 1)
        original = recorder.registered_internal_containers[0]
        unknown = DeathAreaEffectContainer(id=battle.next_entity_id, position=Position(8, 8),
            player_id=0, card_stats=None, hitpoints=1, max_hitpoints=1, damage=0, range=0, sight_range=0)
        battle.entities[unknown.id] = unknown
        assert unknown is not original
        with pytest.raises(ValueError, match="no audited appearance"):
            ScalarDeathActorAdapter(battle, builder, recorder, hand_lookup=hand_lookup, visible_to=lambda *_: True).build()


def test_missing_token_visibility_gates_and_capacity_reject():
    battle, builder, source, rule, hand_lookup = _fixture("SkeletonBarrel")
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: True) as recorder:
        source.take_damage(source.hitpoints + 1)
        with pytest.raises(ValueError, match="vocabulary identity"):
            ScalarDeathActorAdapter(battle, builder, recorder, hand_lookup=hand_lookup, visible_to=lambda *_: True).build()
        actors = ScalarDeathActorAdapter(battle, builder, recorder, hand_lookup=hand_lookup,
                                         visible_to=lambda e, _: e is not recorder.receipts[0].entity).build()
        assert all(a.entity_mask.sum() == 6 for a in actors)
    battle, builder, source, rule, hand_lookup = _fixture("Balloon", capacity=6)
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: True) as recorder:
        source.take_damage(source.hitpoints + 1)
        with pytest.raises(EntityCapacityError):
            ScalarDeathActorAdapter(battle, builder, recorder, hand_lookup=hand_lookup, visible_to=lambda *_: True).build()


def test_witness_gate_removes_unwitnessed_seat_and_foreign_recorder_rejected():
    battle, builder, source, rule, hand_lookup = _fixture("Balloon")
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda _, seat: seat == 0) as recorder:
        source.take_damage(source.hitpoints + 1)
        actors = ScalarDeathActorAdapter(battle, builder, recorder, hand_lookup=hand_lookup, visible_to=lambda *_: True).build()
        assert (actors[0].entity_ids == rule.token).sum() == 1
        assert not (actors[1].entity_ids == rule.token).any()
        with pytest.raises(ValueError, match="another battle"):
            ScalarDeathActorAdapter(BattleState(), builder, recorder, hand_lookup=hand_lookup, visible_to=lambda *_: True)


def test_adapter_uses_setup_hand_aliases_and_rejects_foreign_lookup():
    battle, builder, source, rule, hand_lookup = _fixture("Balloon")
    vocab = load_current_client_typed_vocabulary()
    battle.players[0].hand[:] = ["Skeletons", "Log", "Fireball", "Knight"]
    battle.players[0].cycle_queue.clear()
    battle.players[0].cycle_queue.append("IceSpirits")
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: True) as recorder:
        adapter = ScalarDeathActorAdapter(battle, builder, recorder,
                                         hand_lookup=hand_lookup, visible_to=lambda *_: True)
        assert adapter.build()[0].hand_ids.tolist() == [
            vocab.resolve(name, "card_action")
            for name in ("Skeletons", "Log", "Fireball", "Knight", "IceSpirits")
        ]
        other_builder = StructuredObservationBuilder(token_names=vocab.token_names,
            max_entities=128, card_semantics_version=3, canonical_lane_globals=True)
        other_lookup = compile_scalar_hand_lookup(other_builder, vocab)
        with pytest.raises(ValueError, match="another builder"):
            ScalarDeathActorAdapter(battle, builder, recorder,
                                    hand_lookup=other_lookup, visible_to=lambda *_: True)
