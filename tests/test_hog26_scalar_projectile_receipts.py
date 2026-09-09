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
from clasher.entities import Building, Projectile, Troop
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.torch_sim.diagnostics import battle_snapshot
from scripts.hog26_scalar_projectile_receipts import (
    ScalarOrdinaryProjectileDescriptor,
    ScalarProjectileReceiptRecorder,
)
from scripts.hog26_scalar_public_effect_adapter import project_scalar_public_effects


def _fixture():
    loader = CardDataLoader()
    vocabulary = load_current_client_typed_vocabulary()
    battle = BattleState(rng=random.Random(1279011))
    sources = []
    for name, kind, owner, position in (
        ("Musketeer", Troop, 0, Position(5, 14)),
        ("Cannon", Building, 1, Position(5, 18)),
    ):
        source = battle._spawn_entity(kind, position, owner, loader.get_card(name))
        source.deploy_delay_remaining = 0
        source.placement_pending = False
        source.attack_cooldown = 0
        source.load_time = 0
        sources.append(source)
    descriptors = [
        ScalarOrdinaryProjectileDescriptor.compile(name, loader, vocabulary)
        for name in ("Musketeer", "Cannon")
    ]
    return battle, sources, descriptors


def _physics_hash(battle):
    # Existing broad battle snapshot plus ordinary projectile flight/recipient
    # fields that its entity summary does not include. This is fixture evidence,
    # not a claim of exhaustive simulator serialization.
    snapshot = battle_snapshot(battle)
    snapshot["projectile_details"] = [
        (
            p.id,
            p.target_position.x,
            p.target_position.y,
            p.travel_speed,
            p.splash_radius,
            p.launch_delay,
            p.tracks_target,
            p.pierces,
            p.source_entity.id if p.source_entity else None,
            p.primary_target.id if p.primary_target else None,
            p.crown_tower_damage,
            p.crown_tower_damage_multiplier,
            p.source_name,
            sorted(p.damage_group_hit_entity_ids or ()),
        )
        for p in battle.entities.values()
        if isinstance(p, Projectile)
    ]
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def test_actual_full_steps_preserve_physics_rng_and_source_order():
    instrumented, sources, descriptors = _fixture()
    control, _, _ = _fixture()
    hashes = []
    with ScalarProjectileReceiptRecorder(
        instrumented, zip(sources, descriptors, strict=True)
    ) as recorder:
        assert _physics_hash(instrumented) == _physics_hash(control)
        for _ in range(80):
            instrumented.step()
            control.step()
            actual = _physics_hash(instrumented)
            assert actual == _physics_hash(control)
            assert instrumented.rng.getstate() == control.rng.getstate()
            hashes.append(actual)
        assert len(set(hashes)) == 80
        assert {receipt.source_id for receipt in recorder.receipts} == {
            s.id for s in sources
        }
        ids = [receipt.projectile_id for receipt in recorder.receipts]
        assert ids == sorted(ids) and len(ids) == len(set(ids))
        tokens = {sources[0].id: 324, sources[1].id: 342}
        for ordinal, receipt in enumerate(recorder.receipts):
            assert receipt.ordinal == ordinal
            assert receipt.appearance.token == tokens[receipt.source_id]
            assert receipt.appearance.entity.source_entity.id == receipt.source_id
        assert recorder.calls == len(recorder.receipts)
    assert all("_create_projectile" not in source.__dict__ for source in sources)
    assert _physics_hash(instrumented) == _physics_hash(control)


@pytest.mark.parametrize("index", [0, 1])
def test_exact_birth_binding_ignores_runtime_source_labels(index):
    battle, sources, descriptors = _fixture()
    source, target = sources[index], sources[1 - index]
    expected_id = battle.next_entity_id
    with ScalarProjectileReceiptRecorder(
        battle, [(source, descriptors[index])]
    ) as recorder:
        source._create_projectile(target, battle)
        assert len(recorder.receipts) == 1
        entity = battle.entities[expected_id]
        entity.source_name = "not an appearance authority"
        ids, _, mask = project_scalar_public_effects(
            [entity], recorder.appearances, visible_to=lambda *_: True
        )
        assert mask.all()
        assert (ids == descriptors[index].token).all()


def test_zero_birth_restores_preexisting_instance_override():
    battle, sources, descriptors = _fixture()
    source = sources[0]

    def no_birth(self, target, state, *, target_position=None):
        return "no projectile"

    previous = MethodType(no_birth, source)
    source._create_projectile = previous
    before = _physics_hash(battle)
    with ScalarProjectileReceiptRecorder(
        battle, [(source, descriptors[0])]
    ) as recorder:
        assert source._create_projectile(None, battle) == "no projectile"
        assert recorder.calls == recorder.zero_birth_calls == 1
        assert recorder.appearances == ()
    assert source._create_projectile is previous
    assert _physics_hash(battle) == before


def test_synchronous_child_does_not_inherit_parent_appearance(monkeypatch):
    battle, sources, descriptors = _fixture()
    original = Projectile.resolve_start_collision

    def with_child(self, state):
        original(self, state)
        child = replace(self, id=state.next_entity_id, source_entity=None)
        state.entities[child.id] = child
        state.next_entity_id += 1

    monkeypatch.setattr(Projectile, "resolve_start_collision", with_child)
    expected_id = battle.next_entity_id
    with ScalarProjectileReceiptRecorder(
        battle, [(sources[0], descriptors[0])]
    ) as recorder:
        sources[0]._create_projectile(sources[1], battle)
        assert recorder.receipts[0].projectile_id == expected_id
        assert len(recorder.receipts) == 1
        child = battle.entities[expected_id + 1]
        with pytest.raises(ValueError, match="no audited appearance"):
            project_scalar_public_effects(
                [child], recorder.appearances, visible_to=lambda *_: True
            )


def test_context_exception_and_partial_entry_restore():
    battle, sources, descriptors = _fixture()
    with (
        pytest.raises(RuntimeError, match="body failure"),
        ScalarProjectileReceiptRecorder(battle, [(sources[0], descriptors[0])]),
    ):
        raise RuntimeError("body failure")
    assert "_create_projectile" not in sources[0].__dict__
    with (
        pytest.raises(ValueError, match="differs from compiled"),
        ScalarProjectileReceiptRecorder(
            battle, [(sources[0], descriptors[0]), (sources[1], descriptors[0])]
        ),
    ):
        pass
    assert all("_create_projectile" not in source.__dict__ for source in sources)


def test_tower_unknown_and_nested_binding_rejected():
    battle, sources, descriptors = _fixture()
    loader = CardDataLoader()
    vocabulary = load_current_client_typed_vocabulary()
    with pytest.raises(ValueError, match="not audited"):
        ScalarOrdinaryProjectileDescriptor.compile("Tower", loader, vocabulary)
    tower = next(e for e in battle.entities.values() if e.id < sources[0].id)
    with (
        pytest.raises(ValueError, match="differs from compiled"),
        ScalarProjectileReceiptRecorder(battle, [(tower, descriptors[1])]),
    ):
        pass
    with (
        ScalarProjectileReceiptRecorder(battle, [(sources[0], descriptors[0])]),
        pytest.raises(ValueError, match="already has"),
        ScalarProjectileReceiptRecorder(battle, [(sources[0], descriptors[0])]),
    ):
        pass
    assert "_create_projectile" not in sources[0].__dict__


def test_changed_source_descriptor_rejected_before_physics():
    battle, sources, descriptors = _fixture()
    with ScalarProjectileReceiptRecorder(
        battle, [(sources[0], descriptors[0])]
    ) as recorder:
        original_stats = sources[0].card_stats
        sources[0].card_stats = sources[1].card_stats
        before = _physics_hash(battle)
        with pytest.raises(ValueError, match="differs from compiled"):
            sources[0]._create_projectile(sources[1], battle)
        assert _physics_hash(battle) == before
        assert recorder.appearances == ()
        sources[0].card_stats = original_stats
