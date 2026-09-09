from __future__ import annotations

import hashlib
import json
import random
from dataclasses import replace
from types import MethodType

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import Building, Projectile, RollingProjectile, Troop
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.torch_sim.diagnostics import battle_snapshot
from scripts.hog26_scalar_line_projectile_receipts import (
    ScalarLineProjectileDescriptor,
    ScalarLineProjectileReceiptRecorder,
)
from scripts.hog26_scalar_public_effect_adapter import project_scalar_public_effects

CASES = (
    ("Bowler", 280, RollingProjectile),
    ("MagicArcher", 285, Projectile),
    ("Wallbreakers", 345, Projectile),
)


def _fixture(card, owner):
    loader = CardDataLoader()
    battle = BattleState(rng=random.Random(1279033))
    descriptor = ScalarLineProjectileDescriptor.compile(
        card, loader, load_current_client_typed_vocabulary()
    )
    source = battle._spawn_entity(
        Troop, Position(5, 14 if owner == 0 else 18), owner, loader.get_card(card)
    )
    target = battle._spawn_entity(
        Building,
        Position(5, 15 if owner == 0 else 17),
        1 - owner,
        loader.get_card("Cannon"),
    )
    source.deploy_delay_remaining = target.deploy_delay_remaining = 0
    source.placement_pending = target.placement_pending = False
    target.damage = 0
    return battle, source, target, descriptor


def _hash(battle):
    snapshot = battle_snapshot(battle)
    snapshot["line_effects"] = [
        (
            entity.id,
            entity.source_entity.id if entity.source_entity else None,
            entity.primary_target.id if entity.primary_target else None,
            entity.travel_speed,
            getattr(entity, "pierces", None),
            getattr(entity, "projectile_range", None),
            (entity.target_position.x, entity.target_position.y)
            if isinstance(entity, Projectile)
            else None,
            getattr(entity, "distance_traveled", None),
            sorted(getattr(entity, "hit_entities", ())),
        )
        for entity in battle.entities.values()
        if isinstance(entity, (Projectile, RollingProjectile))
    ]
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize("card,token,entity_type", CASES)
@pytest.mark.parametrize("owner", [0, 1])
def test_actual_full_step_emissions_and_physics_rng_controls(
    card, token, entity_type, owner
):
    battle, source, _, descriptor = _fixture(card, owner)
    control, _, _, _ = _fixture(card, owner)
    exposed = 0
    with ScalarLineProjectileReceiptRecorder(
        battle, [(source, descriptor)]
    ) as recorder:
        for _ in range(100):
            battle.step()
            control.step()
            assert _hash(battle) == _hash(control)
            assert battle.rng.getstate() == control.rng.getstate()
            effects = [receipt.appearance.entity for receipt in recorder.receipts]
            ids, features, mask = project_scalar_public_effects(
                effects,
                recorder.appearances,
                visible_to=lambda entity, seat: entity.is_visible_to(seat),
            )
            if mask.any():
                exposed += 1
                assert (ids[mask] == token).all()
                assert features.shape[-1] == 6
        assert recorder.receipts
        assert all(type(r.appearance.entity) is entity_type for r in recorder.receipts)
        assert all(
            r.appearance.token == token and r.source_id == source.id
            for r in recorder.receipts
        )
        if card == "Wallbreakers":
            assert len(recorder.receipts) == 1
            assert not source.is_alive
            # Actual birth is registered even though the object has already
            # resolved and been cleaned up at every observation boundary.
            assert exposed == 0
            assert recorder.receipts[0].projectile_id not in battle.entities
        else:
            assert exposed > 0
    assert "_create_projectile" not in source.__dict__


@pytest.mark.parametrize("owner", [0, 1])
def test_no_wallbreaker_birth_when_source_cannot_attack(owner):
    battle, source, _, descriptor = _fixture("Wallbreakers", owner)
    source.take_damage(source.hitpoints)
    before = battle.next_entity_id
    with ScalarLineProjectileReceiptRecorder(
        battle, [(source, descriptor)]
    ) as recorder:
        battle.step()
        assert recorder.receipts == [] and recorder.calls == 0
    assert battle.next_entity_id == before


@pytest.mark.parametrize("owner", [0, 1])
def test_magic_archer_synchronous_start_collision_uses_exact_reserved_id(owner):
    battle, source, target, descriptor = _fixture("MagicArcher", owner)
    loader = CardDataLoader()
    # Place a real death-spawner in the launch collision, so its new bodies
    # allocate IDs before _create_projectile returns.
    target.card_stats = loader.get_card("Tombstone")
    target.mechanics = []
    battle._attach_card_mechanics(target, target.card_stats)
    target.hitpoints = 1
    expected = battle.next_entity_id
    with ScalarLineProjectileReceiptRecorder(
        battle, [(source, descriptor)]
    ) as recorder:
        source._create_projectile(target, battle)
        assert not target.is_alive
        assert battle.next_entity_id > expected + 1
        assert len(recorder.receipts) == 1
        assert recorder.receipts[0].projectile_id == expected
        assert recorder.receipts[0].appearance.entity is battle.entities[expected]


def test_unknown_synchronous_child_never_inherits_appearance(monkeypatch):
    battle, source, target, descriptor = _fixture("MagicArcher", 0)
    original = Projectile.resolve_start_collision

    def with_child(self, state):
        original(self, state)
        child = replace(self, id=state.next_entity_id, source_entity=None)
        state.entities[child.id] = child
        state.next_entity_id += 1

    monkeypatch.setattr(Projectile, "resolve_start_collision", with_child)
    expected = battle.next_entity_id
    with ScalarLineProjectileReceiptRecorder(
        battle, [(source, descriptor)]
    ) as recorder:
        source._create_projectile(target, battle)
        assert recorder.receipts[0].projectile_id == expected
        with pytest.raises(ValueError, match="no audited appearance"):
            project_scalar_public_effects(
                [battle.entities[expected + 1]],
                recorder.appearances,
                visible_to=lambda *_: True,
            )


def test_instance_override_restoration_and_unknown_route_rejection():
    battle, source, _, descriptor = _fixture("Bowler", 0)

    def no_birth(self, target, state, *, target_position=None):
        return None

    previous = MethodType(no_birth, source)
    source._create_projectile = previous
    with ScalarLineProjectileReceiptRecorder(
        battle, [(source, descriptor)]
    ) as recorder:
        source._create_projectile(None, battle)
        assert recorder.calls == recorder.zero_birth_calls == 1
        assert recorder.receipts == []
    assert source._create_projectile is previous
    with (
        pytest.raises(RuntimeError),
        ScalarLineProjectileReceiptRecorder(battle, [(source, descriptor)]),
    ):
        raise RuntimeError("fixture failure")
    assert source._create_projectile is previous
    loader = CardDataLoader()
    for card in ("IceSpirit", "ElectroSpirit", "Princess", "Firecracker"):
        with pytest.raises(ValueError, match="not audited"):
            ScalarLineProjectileDescriptor.compile(
                card, loader, load_current_client_typed_vocabulary()
            )
