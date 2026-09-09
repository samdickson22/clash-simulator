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
from clasher.entities import ChainLightning, Projectile, Troop
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.torch_sim.diagnostics import battle_snapshot
from scripts.hog26_scalar_chain_receipts import (
    ScalarChainReceiptRecorder,
    ScalarChainSourceDescriptor,
)
from scripts.hog26_scalar_public_effect_adapter import project_scalar_public_effects


def _fixture(card, owner):
    loader = CardDataLoader()
    battle = BattleState(rng=random.Random(1279034))

    def point(x, y):
        return Position(x if owner == 0 else 18 - x, y if owner == 0 else 32 - y)

    source = battle._spawn_entity(Troop, point(5, 14), owner, loader.get_card(card))
    source.deploy_delay_remaining = 0
    source.placement_pending = False
    targets = []
    for x, y in ((5, 16), (7.8, 16), (8.8, 18)):
        target = battle._spawn_entity(
            Troop, point(x, y), 1 - owner, loader.get_card("Knight")
        )
        target.deploy_delay_remaining = 0
        target.speed = target.damage = 0
        targets.append(target)
    descriptor = ScalarChainSourceDescriptor.compile(
        card, loader, load_current_client_typed_vocabulary()
    )
    return battle, source, targets, descriptor


def _hash(battle):
    snapshot = battle_snapshot(battle)
    snapshot["chains"] = [
        (
            entity.id,
            entity.origin.x,
            entity.origin.y,
            entity.remaining_bounces,
            entity.chain_range,
            entity.travel_speed,
            entity.fixed_hop_duration,
            entity.hop_time_remaining,
            sorted(entity.visited_ids),
            entity.current_target_id,
        )
        for entity in battle.entities.values()
        if isinstance(entity, ChainLightning)
    ]
    snapshot["projectiles"] = [
        (
            entity.id,
            entity.target_position.x,
            entity.target_position.y,
            entity.source_entity.id if entity.source_entity else None,
            entity.primary_target.id if entity.primary_target else None,
            entity.travel_speed,
            entity.damage,
        )
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
    ]
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize("card", ["ElectroDragon", "ElectroSpirit"])
@pytest.mark.parametrize("owner", [0, 1])
def test_real_full_step_chain_births_lifetimes_and_control(card, owner):
    battle, source, _, descriptor = _fixture(card, owner)
    control, _, _, _ = _fixture(card, owner)
    live_frames = {}
    with ScalarChainReceiptRecorder(battle, [(source, descriptor)]) as recorder:
        for _ in range(120):
            battle.step()
            control.step()
            assert _hash(battle) == _hash(control)
            assert battle.rng.getstate() == control.rng.getstate()
            known = {r.chain_id: r for r in recorder.chain_receipts}
            for entity in battle.entities.values():
                if type(entity) is ChainLightning:
                    assert known[entity.id].entity is entity
                    assert entity.is_visible_to(0) and entity.is_visible_to(1)
                    live_frames.setdefault(entity.id, []).append(
                        (entity.position.x, entity.position.y)
                    )
        assert recorder.chain_receipts
        assert live_frames and any(len(frames) > 1 for frames in live_frames.values())
        assert any(len(set(frames)) > 1 for frames in live_frames.values())
        assert all(not r.entity.is_alive for r in recorder.chain_receipts)
        if card == "ElectroSpirit":
            assert getattr(source, "_force_melee_attack", False)
            assert recorder.parent_appearances == ()
            assert recorder.parent_recorder.calls == 0
        else:
            assert recorder.parent_appearances
            assert all(a.token == 283 for a in recorder.parent_appearances)
    assert "_create_projectile" not in source.__dict__
    mechanic = next(m for m in source.mechanics if type(m) is descriptor.mechanic_type)
    assert descriptor.hook_name not in mechanic.__dict__


@pytest.mark.parametrize("card", ["ElectroDragon", "ElectroSpirit"])
def test_chain_family_token_alone_does_not_authorize_visible_appearance(card):
    battle, source, targets, descriptor = _fixture(card, 0)
    mechanic = next(m for m in source.mechanics if type(m) is descriptor.mechanic_type)
    with ScalarChainReceiptRecorder(battle, [(source, descriptor)]) as recorder:
        getattr(mechanic, descriptor.hook_name)(source, targets[0])
        chain = recorder.chain_receipts[0].entity
        assert recorder.chain_receipts[0].serialized_family_token in (283, 284)
        with pytest.raises(ValueError, match="no audited appearance"):
            project_scalar_public_effects(
                [chain], recorder.parent_appearances, visible_to=lambda *_: True
            )
        hidden = project_scalar_public_effects(
            [chain], recorder.parent_appearances, visible_to=lambda *_: False
        )
        assert hidden[0].shape == (1, 2, 0)


def test_synchronous_extra_child_does_not_change_exact_chain_receipt():
    battle, source, targets, descriptor = _fixture("ElectroDragon", 0)
    mechanic = next(m for m in source.mechanics if type(m) is descriptor.mechanic_type)
    original = mechanic.on_attack_hit

    def with_child(self, entity, target):
        chain_id = battle.next_entity_id
        original(entity, target)
        child = replace(battle.entities[chain_id], id=battle.next_entity_id)
        battle.entities[child.id] = child
        battle.next_entity_id += 1

    previous = MethodType(with_child, mechanic)
    mechanic.on_attack_hit = previous
    expected = battle.next_entity_id
    with ScalarChainReceiptRecorder(battle, [(source, descriptor)]) as recorder:
        mechanic.on_attack_hit(source, targets[0])
        assert len(recorder.chain_receipts) == 1
        assert recorder.chain_receipts[0].chain_id == expected
        assert recorder.chain_receipts[0].entity is battle.entities[expected]
        assert battle.entities[expected + 1] is not recorder.chain_receipts[0].entity
    assert mechanic.on_attack_hit is previous


def test_restore_on_error_and_reject_unknown_or_changed_source():
    battle, source, _, descriptor = _fixture("ElectroSpirit", 0)
    mechanic = next(m for m in source.mechanics if type(m) is descriptor.mechanic_type)
    with (
        pytest.raises(RuntimeError),
        ScalarChainReceiptRecorder(battle, [(source, descriptor)]),
    ):
        raise RuntimeError("fixture failure")
    assert descriptor.hook_name not in mechanic.__dict__
    source._force_melee_attack = False
    with (
        pytest.raises(ValueError, match="differs from compiled"),
        ScalarChainReceiptRecorder(battle, [(source, descriptor)]),
    ):
        pass
    assert descriptor.hook_name not in mechanic.__dict__
    with pytest.raises(ValueError, match="not audited"):
        ScalarChainSourceDescriptor.compile(
            "IceSpirit", CardDataLoader(), load_current_client_typed_vocabulary()
        )


@pytest.mark.parametrize("card", ["ElectroDragon", "ElectroSpirit"])
def test_explicit_chain_category_current_output_ignores_private_future(card):
    import torch

    battle, source, targets, descriptor = _fixture(card, 0)
    mechanic = next(m for m in source.mechanics if type(m) is descriptor.mechanic_type)
    with ScalarChainReceiptRecorder(battle, [(source, descriptor)]) as recorder:
        getattr(mechanic, descriptor.hook_name)(source, targets[0])
        chain = recorder.chain_receipts[0].entity

        def visible(entity, seat):
            return entity.is_visible_to(seat)

        def project():
            appearances = recorder.chain_appearances(
                category_name="public_effect:chain_bolt",
                category_token=701,
                visible_to=visible,
            )
            return project_scalar_public_effects(
                [chain], appearances, visible_to=visible
            )

        before = project()
        assert before[2].all() and (before[0] == 701).all()
        assert (before[1][..., 4] == 0).all() and (before[1][..., 5] == 1).all()
        chain.origin = Position(-1000, 1000)
        chain.current_target_id = 999999
        chain.visited_ids = {77777, 88888}
        chain.remaining_bounces = 777
        chain.hop_time_remaining = 12345
        chain.fixed_hop_duration = 9876
        chain.damage = 999999
        chain.chain_range = 5000
        chain.travel_speed = 33333
        chain.source_name = "private source label"
        after = project()
        for actual, expected in zip(after, before, strict=True):
            assert torch.equal(actual, expected)
        if card == "ElectroSpirit":
            assert recorder.parent_appearances == ()
        assert all(
            binding.token not in (283, 284)
            for binding in recorder.chain_appearances(
                category_name="public_effect:chain_bolt",
                category_token=701,
                visible_to=visible,
            )
        )


def test_hidden_or_dead_chain_has_no_output_and_category_is_explicit():
    battle, source, targets, descriptor = _fixture("ElectroSpirit", 0)
    mechanic = next(m for m in source.mechanics if type(m) is descriptor.mechanic_type)
    with ScalarChainReceiptRecorder(battle, [(source, descriptor)]) as recorder:
        getattr(mechanic, descriptor.hook_name)(source, targets[0])
        chain = recorder.chain_receipts[0].entity
        hidden = lambda *_: False
        appearances = recorder.chain_appearances(
            category_name="public_effect:chain_bolt",
            category_token=702,
            visible_to=hidden,
        )
        assert appearances == ()
        assert project_scalar_public_effects([chain], appearances, visible_to=hidden)[
            0
        ].shape == (1, 2, 0)
        first_seat = lambda entity, seat: seat == 0
        appearances = recorder.chain_appearances(
            category_name="public_effect:chain_bolt",
            category_token=702,
            visible_to=first_seat,
        )
        ids, features, mask = project_scalar_public_effects(
            [chain], appearances, visible_to=first_seat
        )
        assert mask[0, 0].all() and not mask[0, 1].any()
        assert not ids[0, 1].any() and not features[0, 1].any()
        chain.is_alive = False
        assert (
            recorder.chain_appearances(
                category_name="public_effect:chain_bolt",
                category_token=702,
                visible_to=lambda *_: True,
            )
            == ()
        )
        for name, token in (
            ("projectile:ElectroSpiritProjectile", 702),
            ("public_effect:chain_bolt", 284),
        ):
            with pytest.raises(ValueError):
                recorder.chain_appearances(
                    category_name=name, category_token=token, visible_to=hidden
                )
        with pytest.raises(TypeError, match="explicit current visibility"):
            recorder.chain_appearances(
                category_name="public_effect:chain_bolt",
                category_token=702,
                visible_to=None,
            )
