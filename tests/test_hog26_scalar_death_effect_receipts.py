import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import Building, Troop
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.torch_sim.diagnostics import battle_snapshot
from scripts.hog26_scalar_death_effect_receipts import (
    DeathAppearanceRule,
    ScalarDeathEffectRecorder,
    project_current_death_appearances,
)


def _fixture(card, owner):
    loader = CardDataLoader()
    battle = BattleState(rng=random.Random(73271))
    source = battle._spawn_entity(Building if card == "BombTower" else Troop,
                                  Position(9, 12), owner, loader.get_card(card))
    source.deploy_delay_remaining = 0
    source.placement_pending = False
    rule = DeathAppearanceRule.compile(card, source, loader,
                                       load_current_client_typed_vocabulary())
    return battle, source, rule


def _project(recorder):
    return project_current_death_appearances(recorder.receipts,
                                             visible_to=lambda *_: True)


@pytest.mark.parametrize("card", ["Balloon", "BombTower", "SkeletonBarrel", "IceGolem", "Lumberjack"])
@pytest.mark.parametrize("owner", [0, 1])
def test_actual_death_and_full_steps_preserve_physics_and_rng(card, owner):
    battle, source, rule = _fixture(card, owner)
    control, other, _ = _fixture(card, owner)
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: True) as recorder:
        source.take_damage(source.hitpoints + 1)
        other.take_damage(other.hitpoints + 1)
        if card == "Lumberjack":
            assert not recorder.receipts
            assert len(recorder.internal_containers) == 1
            assert _project(recorder) == ((), ())
        else:
            assert len(recorder.receipts) == 1
        observed = False
        for _ in range(140):
            assert battle_snapshot(battle) == battle_snapshot(control)
            assert battle.rng.getstate() == control.rng.getstate()
            current = [r for r in recorder.receipts if r.entity.is_alive]
            if card == "SkeletonBarrel" and current:
                assert rule.token == 0
                with pytest.raises(ValueError, match="no frozen vocabulary"):
                    _project(recorder)
            else:
                public = _project(recorder)
                observed |= bool(public[0])
                for r in current:
                    e = r.entity
                    # Perturb exclusively private/future fields; restore before
                    # physics continues so the control remains meaningful.
                    keys = ("explosion_timer", "explosion_damage", "death_spawn_data",
                            "spell_name", "source_name", "damage", "duration", "area_data")
                    old = {k: (k in vars(e), getattr(e, k, None)) for k in keys}
                    for k in keys:
                        setattr(e, k, {"secret": "future"} if k.endswith("data") else 99999)
                    assert _project(recorder) == public
                    for k, (existed, value) in old.items():
                        if existed:
                            setattr(e, k, value)
                        else:
                            vars(e).pop(k, None)
            battle.step()
            control.step()
        assert card == "SkeletonBarrel" or observed
        assert all(not r.entity.is_alive for r in recorder.receipts)
    assert all("update" not in vars(e) for e in recorder.internal_containers)
    assert all("on_death" not in vars(m) for m in source.mechanics)


def test_missing_body_identity_does_not_leak_when_source_was_unwitnessed():
    battle, source, rule = _fixture("SkeletonBarrel", 0)
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: False) as recorder:
        source.take_damage(source.hitpoints + 1)
        assert _project(recorder) == ((), ())


def test_explicit_current_visibility_required_and_exception_restoration():
    battle, source, rule = _fixture("Balloon", 0)
    with pytest.raises(RuntimeError, match="sentinel"), ScalarDeathEffectRecorder(
        battle, [(source, rule)], witnessed_visible_to=lambda *_: True,
    ) as recorder:
        source.take_damage(source.hitpoints + 1)
        assert project_current_death_appearances(recorder.receipts,
                                                visible_to=lambda *_: False) == ((), ())
        assert rule.category == "death_body"
        with pytest.raises(ValueError, match="already instrumented"), ScalarDeathEffectRecorder(
            battle, [(source, rule)], witnessed_visible_to=lambda *_: True,
        ):
            pass
        raise RuntimeError("sentinel")
    assert all("on_death" not in vars(m) for m in source.mechanics)


def test_explicit_extra_current_body_identity_and_invalid_mappings():
    battle, source, _ = _fixture("SkeletonBarrel", 0)
    loader = CardDataLoader()
    vocabulary = load_current_client_typed_vocabulary()
    key = "building_body:SkeletonContainerNew"
    token = len(vocabulary.token_names)
    rule = DeathAppearanceRule.compile("SkeletonBarrel", source, loader, vocabulary,
                                       extra_tokens={key: token})
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: True) as recorder:
        source.take_damage(source.hitpoints + 1)
        projected = _project(recorder)
        assert projected[0][0][:2] == (token, "death_body")
        assert projected[1][0][:2] == (token, "death_body")
        body = recorder.receipts[0].entity
        body.explosion_timer = 999
        body.death_spawn_name = "unobserved future"
        body.death_spawn_data = {"unobserved": "payload"}
        body.explosion_damage = 99999
        assert _project(recorder) == projected
    for mapping in ({"building_body:invented": token}, {key: token - 1}, {key: True}):
        with pytest.raises(ValueError, match="extra death"):
            DeathAppearanceRule.compile("SkeletonBarrel", source, loader, vocabulary,
                                         extra_tokens=mapping)


def test_internal_container_exclusion_is_exact_reference_registration():
    battle, source, rule = _fixture("Lumberjack", 0)
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: True) as recorder:
        source.take_damage(source.hitpoints + 1)
        registered = recorder.registered_internal_containers
        assert isinstance(registered, tuple) and len(registered) == 1
        assert battle.entities[registered[0].id] is registered[0]
        assert _project(recorder) == ((), ())
        for _ in range(12):
            battle.step()
        assert recorder.registered_internal_containers == registered
        assert len(recorder.receipts) == 1
        assert recorder.receipts[0].entity is not registered[0]


def test_mutated_death_payload_after_context_entry_rejected_before_emission():
    from copy import deepcopy

    from clasher.mechanics.shared.death_area import DeathAreaEffect

    battle, source, rule = _fixture("IceGolem", 0)
    mechanic = next(m for m in source.mechanics if type(m) is DeathAreaEffect)
    original_payload = mechanic.area_data
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: True) as recorder:
        mechanic.area_data = deepcopy(original_payload)
        mechanic.area_data["name"] = "Poison"
        before_ids = set(battle.entities)
        with pytest.raises(ValueError, match="changed before emission"):
            source.take_damage(source.hitpoints + 1)
        assert set(battle.entities) == before_ids
        assert not recorder.receipts
    mechanic.area_data = original_payload


def test_mutated_delayed_container_payload_rejected_before_birth():
    from copy import deepcopy

    battle, source, rule = _fixture("Lumberjack", 0)
    with ScalarDeathEffectRecorder(battle, [(source, rule)],
                                   witnessed_visible_to=lambda *_: True) as recorder:
        source.take_damage(source.hitpoints + 1)
        container = recorder.registered_internal_containers[0]
        container.area_data = deepcopy(container.area_data)
        container.area_data["name"] = "Poison"
        before_ids = set(battle.entities)
        with pytest.raises(ValueError, match="container payload changed"):
            battle.step()
        assert set(battle.entities) <= before_ids
        assert not recorder.receipts
