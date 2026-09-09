from __future__ import annotations

import hashlib
import json
import random
from types import MethodType

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import Projectile, Troop
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.torch_sim.diagnostics import battle_snapshot
from scripts.hog26_scalar_public_effect_adapter import project_scalar_public_effects
from scripts.hog26_scalar_special_projectile_receipts import (
    ScalarSpecialProjectileDescriptor,
    ScalarSpecialProjectileReceiptRecorder,
    _with_constructor,
)


def fixture(name, owner=0, target_name="Knight", target_hp=7000):
    loader = CardDataLoader()
    vocabulary = load_current_client_typed_vocabulary()
    battle = BattleState(rng=random.Random(1279161))
    source = battle._spawn_entity(Troop, Position(5, 14 if owner == 0 else 18),
                                 owner, loader.get_card(name))
    target = battle._spawn_entity(Troop, Position(5, 18 if owner == 0 else 14),
                                 1 - owner, loader.get_card(target_name))
    for entity in (source, target):
        entity.deploy_delay_remaining = 0
        entity.placement_pending = False
        entity.attack_cooldown = 0
    target.hitpoints = target_hp
    target.apply_stun(20)
    descriptor = ScalarSpecialProjectileDescriptor.compile(name, loader, vocabulary)
    return battle, source, target, descriptor


def physics_hash(battle):
    snapshot = battle_snapshot(battle)
    snapshot["projectile_details"] = [
        (p.id, p.target_position.x, p.target_position.y, p.travel_speed,
         p.splash_radius, p.launch_delay, p.tracks_target, p.pierces,
         p.source_entity.id if p.source_entity else None,
         p.primary_target.id if p.primary_target else None, p.source_name,
         p.crown_tower_damage, p.crown_tower_damage_multiplier,
         p.start_collision_resolved, p.spawn_projectile_data,
         sorted(p.damage_group_hit_entity_ids or ()))
        for p in battle.entities.values() if type(p) is Projectile
    ]
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize("name", ["Princess", "Firecracker"])
@pytest.mark.parametrize("owner", [0, 1])
def test_actual_full_steps_preserve_physics_rng_and_bind_distinct_routes(name, owner):
    battle, source, _, descriptor = fixture(name, owner)
    control, _, _, _ = fixture(name, owner)
    original_method = Troop._create_projectile
    original_child_method = Projectile._spawn_impact_projectiles
    with ScalarSpecialProjectileReceiptRecorder(battle, [(source, descriptor)]) as recorder:
        for _ in range(80):
            battle.step()
            control.step()
            assert physics_hash(battle) == physics_hash(control)
            assert battle.rng.getstate() == control.rng.getstate()
        assert Troop._create_projectile is original_method
        assert Projectile._spawn_impact_projectiles is original_child_method
        assert recorder.receipts
        ids = [receipt.projectile_id for receipt in recorder.receipts]
        assert ids == sorted(set(ids))
        parents = [receipt for receipt in recorder.receipts if receipt.route == "attack"]
        children = [receipt for receipt in recorder.receipts if receipt.route == "impact_child"]
        assert all(receipt.source_id == source.id for receipt in parents)
        if name == "Princess":
            assert {receipt.appearance.token for receipt in parents} == {326}
            assert not children
            assert all(receipt.appearance.token != 327 for receipt in recorder.receipts)
        else:
            assert {receipt.appearance.token for receipt in parents} == {292}
            assert children and {receipt.appearance.token for receipt in children} == {290}
            assert {receipt.source_id for receipt in children} <= {receipt.projectile_id for receipt in parents}
    assert "_create_projectile" not in source.__dict__
    assert all("_spawn_impact_projectiles" not in r.appearance.entity.__dict__
               for r in recorder.receipts)
    assert physics_hash(battle) == physics_hash(control)


def test_synchronous_child_hits_have_receipts_before_death_spawns(monkeypatch):
    battle, source, target, descriptor = fixture("Firecracker", target_name="Golem", target_hp=1)
    control, control_source, control_target, _ = fixture("Firecracker", target_name="Golem", target_hp=1)
    with ScalarSpecialProjectileReceiptRecorder(battle, [(source, descriptor)]) as recorder:
        source._create_projectile(target, battle)
        control_source._create_projectile(control_target, control)
        parent = recorder.receipts[0].appearance.entity
        control_parent = next(e for e in control.entities.values() if type(e) is Projectile)
        seen_child_at_damage = []
        damage = target.take_damage

        def observe_damage(*args, **kwargs):
            seen_child_at_damage.append(any(r.route == "impact_child" for r in recorder.receipts))
            return damage(*args, **kwargs)

        monkeypatch.setattr(target, "take_damage", observe_damage)
        for _ in range(80):
            parent.update(0.05, battle)
            control_parent.update(0.05, control)
            assert physics_hash(battle) == physics_hash(control)
            assert battle.rng.getstate() == control.rng.getstate()
            if not parent.is_alive:
                break
        assert not parent.is_alive
        assert any(seen_child_at_damage)
        children = [r for r in recorder.receipts if r.route == "impact_child"]
        assert len(children) == 5
        assert all(r.appearance.token == 290 for r in children)
        children_ids = [r.projectile_id for r in children]
        assert children_ids != list(range(children_ids[0], children_ids[0] + 5))
        unbound = [e for e in battle.entities.values()
                   if children_ids[0] < e.id < children_ids[-1] and type(e) is not Projectile]
        assert unbound
        assert not {id(e) for e in unbound} & {id(r.appearance.entity) for r in recorder.receipts}


@pytest.mark.parametrize("name", ["Princess", "Firecracker"])
def test_appearance_never_uses_runtime_labels_or_private_payload(name):
    battle, source, target, descriptor = fixture(name)
    with ScalarSpecialProjectileReceiptRecorder(battle, [(source, descriptor)]) as recorder:
        source._create_projectile(target, battle)
        projectile = recorder.receipts[0].appearance.entity
        before = project_scalar_public_effects([projectile], recorder.appearances,
                                              visible_to=lambda *_: True)
        projectile.source_name = "PrincessProjectileDeco"
        projectile.damage = 98765
        projectile.target_position = Position(17, 30)
        projectile.primary_target = None
        projectile.crown_tower_damage = 12345
        after = project_scalar_public_effects([projectile], recorder.appearances,
                                             visible_to=lambda *_: True)
        assert all(torch.equal(a, b) for a, b in zip(before, after, strict=True))
        hidden = project_scalar_public_effects([projectile], recorder.appearances,
                                              visible_to=lambda *_: False)
        assert not hidden[2].any()


def test_context_error_restores_parent_and_source_hooks():
    battle, source, target, descriptor = fixture("Firecracker")
    recorder = ScalarSpecialProjectileReceiptRecorder(battle, [(source, descriptor)])
    with pytest.raises(RuntimeError, match="intentional"), recorder:
        source._create_projectile(target, battle)
        assert "_spawn_impact_projectiles" in recorder.receipts[0].appearance.entity.__dict__
        raise RuntimeError("intentional")
    assert "_create_projectile" not in source.__dict__
    assert "_spawn_impact_projectiles" not in recorder.receipts[0].appearance.entity.__dict__


def test_partial_entry_override_and_duplicate_registration_fail_closed():
    battle, source, _, descriptor = fixture("Princess")
    other = battle._spawn_entity(Troop, Position(7, 14), 0, battle.card_loader.get_card("Firecracker"))
    with pytest.raises(ValueError, match="differs"), ScalarSpecialProjectileReceiptRecorder(
        battle, [(source, descriptor), (other, descriptor)]
    ):
        pass
    assert "_create_projectile" not in source.__dict__
    with ScalarSpecialProjectileReceiptRecorder(battle) as recorder:
        recorder.bind_source(source, descriptor)
        with pytest.raises(ValueError, match="duplicate"):
            recorder.bind_source(source, descriptor)
    previous = MethodType(lambda *args, **kwargs: None, source)
    source._create_projectile = previous
    with pytest.raises(ValueError, match="unaudited"), ScalarSpecialProjectileReceiptRecorder(
        battle, [(source, descriptor)]
    ):
        pass
    assert source._create_projectile is previous


def test_constructor_type_checks_and_changed_payload_are_rejected():
    def unaudited(value):
        return isinstance(value, Projectile)

    with pytest.raises(ValueError, match="direct constructor site"):
        _with_constructor(unaudited, lambda **_: None)
    battle, source, target, descriptor = fixture("Firecracker")
    with ScalarSpecialProjectileReceiptRecorder(battle, [(source, descriptor)]) as recorder:
        source._create_projectile(target, battle)
        parent = recorder.receipts[0].appearance.entity
        parent.spawn_projectile_data = {"name": "not FirecrackerExplosion"}
        with pytest.raises(ValueError, match="binding changed"):
            parent._spawn_impact_projectiles(battle)


@pytest.mark.parametrize("method", [Troop._create_projectile, Projectile._spawn_impact_projectiles])
def test_constructor_hook_preserves_exact_method_code_defaults_and_closure(method):
    constructor = lambda **kwargs: Projectile(**kwargs)
    local = _with_constructor(method, constructor)
    assert local.__code__ is method.__code__
    assert local.__defaults__ is method.__defaults__
    assert local.__kwdefaults__ is method.__kwdefaults__
    assert local.__closure__ is method.__closure__
    assert local.__globals__["Projectile"] is constructor
    assert method.__globals__["Projectile"] is Projectile
    assert all(local.__globals__[key] is value for key, value in method.__globals__.items()
               if key != "Projectile")


def test_global_constructor_change_rejected_before_creation(monkeypatch):
    import clasher.entities as entity_module

    battle, source, target, descriptor = fixture("Princess")
    with ScalarSpecialProjectileReceiptRecorder(battle, [(source, descriptor)]):
        before = battle.next_entity_id
        with monkeypatch.context() as patch:
            patch.setattr(entity_module, "Projectile", object)
            with pytest.raises(ValueError, match="constructor authority changed"):
                source._create_projectile(target, battle)
        assert battle.next_entity_id == before
    assert "_create_projectile" not in source.__dict__
