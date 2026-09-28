from __future__ import annotations

import hashlib
import json
import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import (
    Building,
    ChainLightning,
    Projectile,
    RollingProjectile,
    Troop,
)
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.diagnostics import battle_snapshot
from scripts.hog26_scalar_public_effect_adapter import project_scalar_public_effects
from scripts.hog26_scalar_receipt_session import ScalarReceiptSession


def _initial(cards):
    loader = CardDataLoader()
    vocabulary = load_current_client_typed_vocabulary()
    battle = BattleState(rng=random.Random(1279040))
    session = ScalarReceiptSession(
        battle,
        cards,
        loader,
        vocabulary,
        visible_to=lambda entity, seat: entity.is_visible_to(seat),
    )
    return battle, session, loader, vocabulary


def _spawn(battle, loader, card, owner, x, y):
    stats = loader.get_card(card)
    source = battle._spawn_entity(
        Building if stats.card_type == "Building" else Troop,
        Position(x, y),
        owner,
        stats,
    )
    source.deploy_delay_remaining = 0
    source.placement_pending = False
    return source


def _hash(battle):
    snapshot = battle_snapshot(battle)
    snapshot["effects"] = [
        (
            e.id,
            e.position.x,
            e.position.y,
            getattr(e, "travel_speed", None),
            getattr(e, "remaining_bounces", None),
            getattr(e, "current_target_id", None),
            sorted(getattr(e, "visited_ids", ())),
            getattr(e, "spawn_delay", None),
            (e.target_position.x, e.target_position.y)
            if isinstance(e, Projectile)
            else None,
        )
        for e in battle.entities.values()
        if isinstance(e, (Projectile, RollingProjectile, ChainLightning))
    ]
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def test_mixed_live_frames_and_context_restoration_match_control():
    cards = (
        "Musketeer",
        "Bowler",
        "ElectroDragon",
        "Firecracker",
        "IceGolem",
        "Poison",
    )
    battle, session, loader, vocabulary = _initial(cards)
    control = BattleState(rng=random.Random(1279040))
    actors, control_actors = [], []
    for card, x in (
        ("Musketeer", 3),
        ("Bowler", 6),
        ("ElectroDragon", 9),
        ("Firecracker", 12),
    ):
        actors.append(_spawn(battle, loader, card, 0, x, 14))
        control_actors.append(_spawn(control, loader, card, 0, x, 14))
        _spawn(battle, loader, "Knight", 1, x, 17).damage = 0
        _spawn(control, loader, "Knight", 1, x, 17).damage = 0
    ice = _spawn(battle, loader, "IceGolem", 0, 15, 14)
    control_ice = _spawn(control, loader, "IceGolem", 0, 15, 14)
    with session:
        for tick in range(100):
            session.synchronize_sources()
            if tick == 8:
                ice.take_damage(ice.hitpoints)
                control_ice.take_damage(control_ice.hitpoints)
            battle.step()
            control.step()
            assert _hash(battle) == _hash(control)
            assert battle.rng.getstate() == control.rng.getstate()
        assert session.ordinary_appearances
        assert session.line_appearances
        assert session.special_appearances
        assert session.receipts == session.death_receipts and session.death_receipts
        assert session.token_names[:494] == vocabulary.token_names
        assert session.extra_public_effect_tokens == (
            "projectile:TowerPrincessProjectile",
            "public_tower_shot:king",
            "public_effect:chain_bolt",
            "building_body:SkeletonContainerNew",
        )
        assert len({id(a.entity) for a in session.appearances}) == len(
            session.appearances
        )
    for source in [*actors, ice]:
        assert "_create_projectile" not in source.__dict__
        for mechanic in source.mechanics:
            assert "on_attack_hit" not in mechanic.__dict__
            assert "on_death" not in mechanic.__dict__
    for appearance in session.special_appearances:
        assert "_spawn_impact_projectiles" not in appearance.entity.__dict__
    assert "cast" not in SPELL_REGISTRY["Poison"].__dict__


def test_late_sources_internal_spawn_variants_and_persistent_special_children():
    battle, session, loader, _ = _initial(("LavaHound", "GoblinGang", "Firecracker"))
    with session:
        target = _spawn(battle, loader, "Knight", 1, 5, 17)
        for parent, path in (
            ("LavaHound", ("summonCharacterData", "deathSpawnCharacterData")),
            ("GoblinGang", ("summonCharacterSecondData",)),
        ):
            body = loader.get_card(parent)._raw_entry
            for key in path:
                body = body[key]
            source = battle._spawn_entity(
                Troop, Position(5, 14), 0, troop_from_character_data(body["name"], body)
            )
            session.synchronize_sources()
            source._create_projectile(target, battle)
        assert {a.token for a in session.ordinary_appearances} == {312, 338}
        firecracker = _spawn(battle, loader, "Firecracker", 0, 8, 14)
        session.synchronize_sources()
        firecracker._create_projectile(target, battle)
        parent = session.special_appearances[-1].entity
        assert "_spawn_impact_projectiles" in parent.__dict__
        for _ in range(20):
            session.synchronize_sources()
            battle.step()
        assert any(a.token == 290 for a in session.special_appearances)
    assert "_spawn_impact_projectiles" not in parent.__dict__


def test_death_container_hooks_survive_later_synchronizations_until_exit():
    battle, session, loader, _ = _initial(("Lumberjack",))
    source = _spawn(battle, loader, "Lumberjack", 0, 9, 14)
    with session:
        source.take_damage(source.hitpoints)
        assert session.registered_internal_containers
        container = session.registered_internal_containers[0]
        assert "update" in container.__dict__
        for _ in range(80):
            session.synchronize_sources()
            battle.step()
        assert session.death_receipts
        assert session.receipts == session.death_receipts
        assert "update" in container.__dict__
    assert "update" not in container.__dict__


def test_undeclared_visible_effect_is_not_hidden_or_given_guessed_identity():
    battle, session, loader, _ = _initial(("Musketeer",))
    unknown = _spawn(battle, loader, "BabyDragon", 0, 5, 14)
    target = _spawn(battle, loader, "Knight", 1, 5, 17)
    with session:
        expected = battle.next_entity_id
        unknown._create_projectile(target, battle)
        effect = battle.entities[expected]
        assert all(a.entity is not effect for a in session.appearances)
        with pytest.raises(ValueError, match="no audited appearance"):
            project_scalar_public_effects(
                [effect], session.appearances, visible_to=lambda *_: True
            )


def test_bad_payload_fails_and_partial_session_cleanup_restores_hooks():
    battle, session, loader, _ = _initial(("Musketeer",))
    source = _spawn(battle, loader, "Musketeer", 0, 5, 14)
    source._force_melee_attack = True
    with pytest.raises(ValueError, match="no compiled receipt"), session:
        pass
    assert "_create_projectile" not in source.__dict__
    for tower in list(battle.entities.values())[:6]:
        assert "_create_projectile" not in tower.__dict__
    with pytest.raises(RuntimeError, match="active session"):
        session.synchronize_sources()


@pytest.mark.parametrize("owner", [0, 1])
def test_royal_delivery_session_projects_only_actual_recruit_and_restores(owner):
    from clasher.rl.structured_obs import StructuredObservationBuilder
    from scripts.hog26_scalar_actor_projection import compile_scalar_hand_lookup
    from scripts.hog26_scalar_death_actor_adapter import ScalarDeathActorAdapter

    battle, session, _, vocab = _initial(("RoyalDelivery",))
    control = BattleState(rng=random.Random(1279040))
    builder = StructuredObservationBuilder(
        token_names=session.token_names, max_entities=128,
        card_semantics_version=3, canonical_lane_globals=True,
    )
    hand_lookup = compile_scalar_hand_lookup(builder, vocab)
    adapter = ScalarDeathActorAdapter(battle, builder, session,
                                      hand_lookup=hand_lookup, visible_to=lambda *_: True)
    token = vocab.resolve("DeliveryRecruit", "troop_body")
    position = Position(9, 12 if owner == 0 else 20)
    assert session.unavailable_public_observations == (
        "RoyalDelivery falling flight is not modeled by scalar",
    )
    with session:
        SPELL_REGISTRY["RoyalDelivery"].cast(battle, owner, position)
        SPELL_REGISTRY["RoyalDelivery"].cast(control, owner, position)
        scheduler = session.registered_royal_delivery_schedulers[0]
        assert session.registered_internal_containers == ()
        for _ in range(70):
            session.synchronize_sources()
            battle.step()
            control.step()
            assert _hash(battle) == _hash(control)
            assert battle.rng.getstate() == control.rng.getstate()
            actors = adapter.build(appearances=session.appearances)
            for actor in actors:
                assert (actor.entity_ids == token).sum() == len(session.royal_delivery_recruits)
            assert not any(a.entity is scheduler for a in session.appearances)
        assert len(session.royal_delivery_recruits) == 1
    assert "cast" not in vars(SPELL_REGISTRY["RoyalDelivery"])
    assert "update" not in vars(scheduler)
    assert "_spawn_units" not in vars(scheduler)


def test_royal_delivery_exact_scheduler_exclusion_does_not_hide_unregistered_copy():
    from copy import copy

    from clasher.rl.structured_obs import StructuredObservationBuilder
    from scripts.hog26_scalar_actor_projection import compile_scalar_hand_lookup
    from scripts.hog26_scalar_death_actor_adapter import ScalarDeathActorAdapter

    battle, session, _, vocab = _initial(("RoyalDelivery",))
    builder = StructuredObservationBuilder(token_names=session.token_names, max_entities=128,
                                           card_semantics_version=3, canonical_lane_globals=True)
    hand_lookup = compile_scalar_hand_lookup(builder, vocab)
    adapter = ScalarDeathActorAdapter(battle, builder, session,
                                      hand_lookup=hand_lookup, visible_to=lambda *_: True)
    with session:
        SPELL_REGISTRY["RoyalDelivery"].cast(battle, 0, Position(9, 12))
        scheduler = session.registered_royal_delivery_schedulers[0]
        scheduler.activation_delay = 0  # Projection still excludes this exact receipt.
        assert all(a.entity_mask.sum() == 6 for a in adapter.build())
        unknown = copy(scheduler)
        unknown.id = battle.next_entity_id
        battle.entities[unknown.id] = unknown
        with pytest.raises(ValueError, match="no audited appearance"):
            adapter.build()
